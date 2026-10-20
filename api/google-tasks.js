const { collectDailyTasks, noStoreHeaders, unavailablePayload } = require('../lib/google-tasks-live');

module.exports = async function handler(req, res) {
  const headers = noStoreHeaders();
  for (const [key, value] of Object.entries(headers)) res.setHeader(key, value);
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).json(unavailablePayload());
  }
  try {
    return res.status(200).json(await collectDailyTasks());
  } catch {
    return res.status(502).json(unavailablePayload());
  }
};
