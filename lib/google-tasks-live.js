const LIST_TITLE = 'Daily';
const MAX_TASKS = 5;
const GOOGLE_API = 'https://tasks.googleapis.com/tasks/v1';

function noStoreHeaders() {
  return {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store, max-age=0',
    Pragma: 'no-cache',
  };
}

async function jsonFetch(fetchImpl, url, options) {
  const response = await fetchImpl(url, { cache: 'no-store', ...options });
  if (!response.ok) throw new Error(`upstream HTTP ${response.status}`);
  return response.json();
}

async function accessToken(fetchImpl, env) {
  const clientId = env.GOOGLE_CLIENT_ID;
  const clientSecret = env.GOOGLE_CLIENT_SECRET;
  const refreshToken = env.GOOGLE_TASKS_REFRESH_TOKEN;
  if (!clientId || !clientSecret || !refreshToken) throw new Error('Google Tasks credentials unavailable');
  const body = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    refresh_token: refreshToken,
    grant_type: 'refresh_token',
  });
  const data = await jsonFetch(fetchImpl, 'https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  if (!data.access_token) throw new Error('Google OAuth response omitted an access token');
  return data.access_token;
}

async function allPages(fetchImpl, baseUrl, headers) {
  const items = [];
  let pageToken = '';
  do {
    const url = new URL(baseUrl);
    if (pageToken) url.searchParams.set('pageToken', pageToken);
    const page = await jsonFetch(fetchImpl, url, { headers });
    if (Array.isArray(page.items)) items.push(...page.items);
    pageToken = String(page.nextPageToken || '');
  } while (pageToken);
  return items;
}

async function collectDailyTasks({ fetchImpl = fetch, env = process.env, now = () => new Date() } = {}) {
  const token = await accessToken(fetchImpl, env);
  const headers = { Authorization: `Bearer ${token}` };
  const listsUrl = new URL(`${GOOGLE_API}/users/@me/lists`);
  listsUrl.searchParams.set('maxResults', '100');
  const lists = await allPages(fetchImpl, listsUrl, headers);
  const matching = lists.filter((item) => item && item.title === LIST_TITLE);
  if (matching.length !== 1 || !matching[0].id) throw new Error(`expected exactly one ${LIST_TITLE} task list`);

  const tasksUrl = new URL(`${GOOGLE_API}/lists/${encodeURIComponent(matching[0].id)}/tasks`);
  tasksUrl.searchParams.set('showCompleted', 'false');
  tasksUrl.searchParams.set('showHidden', 'false');
  tasksUrl.searchParams.set('maxResults', '100');
  const items = await allPages(fetchImpl, tasksUrl, headers);
  const tasks = items
    .filter((item) => item && item.status === 'needsAction' && !item.deleted && !item.hidden)
    .map((item) => String(item.title || '').trim())
    .filter(Boolean)
    .slice(0, MAX_TASKS);
  return { ok: true, listTitle: LIST_TITLE, tasks, fetchedAt: now().toISOString(), refreshState: 'live' };
}

function unavailablePayload() {
  return { ok: false, listTitle: LIST_TITLE, tasks: [], fetchedAt: null, refreshState: 'unavailable' };
}

function makeHandler({ fetchImpl = fetch } = {}) {
  return async function handler(_request, env = process.env) {
    try {
      const payload = await collectDailyTasks({ fetchImpl, env });
      return new Response(JSON.stringify(payload), { status: 200, headers: noStoreHeaders() });
    } catch {
      return new Response(JSON.stringify(unavailablePayload()), { status: 502, headers: noStoreHeaders() });
    }
  };
}

module.exports = { collectDailyTasks, makeHandler, noStoreHeaders, unavailablePayload };
