import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { collectDailyTasks, makeHandler } = require('../lib/google-tasks-live.js');

const calls = [];
const fakeFetch = async (url, options = {}) => {
  calls.push({ url: String(url), options });
  const parsed = new URL(String(url));
  if (parsed.hostname === 'oauth2.googleapis.com') {
    return new Response(JSON.stringify({ access_token: 'server-only-access-token' }), { status: 200 });
  }
  assert.equal(options.headers.Authorization, 'Bearer server-only-access-token');
  if (parsed.pathname === '/tasks/v1/users/@me/lists' && !parsed.searchParams.get('pageToken')) {
    return new Response(JSON.stringify({ items: [{ id: 'other', title: 'Other' }], nextPageToken: 'lists-2' }), { status: 200 });
  }
  if (parsed.pathname === '/tasks/v1/users/@me/lists') {
    return new Response(JSON.stringify({ items: [{ id: 'daily-private-id', title: 'Daily' }] }), { status: 200 });
  }
  if (!parsed.searchParams.get('pageToken')) {
    assert.equal(parsed.searchParams.get('showCompleted'), 'false');
    assert.equal(parsed.searchParams.get('showHidden'), 'false');
    return new Response(JSON.stringify({
      items: [
        { id: 'deleted', title: 'Deleted', status: 'needsAction', deleted: true },
        { id: 'hidden', title: 'Hidden', status: 'needsAction', hidden: true },
        { id: 'done', title: 'Done', status: 'completed' },
        { id: 'one', title: 'One', status: 'needsAction' },
        { id: 'two', title: 'Two', status: 'needsAction' },
      ],
      nextPageToken: 'tasks-2',
    }), { status: 200 });
  }
  return new Response(JSON.stringify({ items: [
    { id: 'three', title: 'Three', status: 'needsAction' },
    { id: 'four', title: 'Four', status: 'needsAction' },
    { id: 'five', title: 'Five', status: 'needsAction' },
    { id: 'six', title: 'Six', status: 'needsAction' },
  ] }), { status: 200 });
};

const result = await collectDailyTasks({
  fetchImpl: fakeFetch,
  env: { GOOGLE_CLIENT_ID: 'client', GOOGLE_CLIENT_SECRET: 'secret', GOOGLE_TASKS_REFRESH_TOKEN: 'refresh' },
  now: () => new Date('2026-10-20T02:00:00Z'),
});
assert.deepEqual(result, {
  ok: true,
  listTitle: 'Daily',
  tasks: ['One', 'Two', 'Three', 'Four', 'Five'],
  fetchedAt: '2026-10-20T02:00:00.000Z',
  refreshState: 'live',
});
assert.equal(calls.length, 5);
assert.equal(JSON.stringify(result).includes('daily-private-id'), false);

const handler = makeHandler({ fetchImpl: async () => new Response('no', { status: 503 }) });
const response = await handler(new Request('https://novairesignal.com/api/google-tasks'), {
  GOOGLE_CLIENT_ID: 'client', GOOGLE_CLIENT_SECRET: 'secret', GOOGLE_TASKS_REFRESH_TOKEN: 'refresh',
});
assert.equal(response.status, 502);
assert.equal(response.headers.get('cache-control'), 'no-store, max-age=0');
assert.deepEqual(await response.json(), {
  ok: false,
  listTitle: 'Daily',
  tasks: [],
  fetchedAt: null,
  refreshState: 'unavailable',
});

console.log('daily tasks API contracts passed');
