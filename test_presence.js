// Presence integration self-check: run with `npm test`.
const { getPresence, hermesPresence, openclawPresence } = require('./integrations');

let failed = 0;
const check = (name, cond) => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}`);
  if (!cond) failed++;
};

// Adapter shapes
const h = hermesPresence();
check('hermes shape', h && typeof h === 'object' && 'online' in h && Array.isArray(h.sessions) && h.gateway);
check('hermes home set', !!h.home);
check('hermes online (gateway or live sessions)', h.online === true);
check('hermes gateway running', h.gateway.state === 'running');
check('hermes platform list present', Array.isArray(h.platforms));

// Flat roster
check('openclaw adapter exported', typeof openclawPresence === 'function');

(async () => {
  const p = await getPresence();
  check('presence has hermes+openclaw+agents', !!(p.hermes && p.openclaw && Array.isArray(p.agents)));
  check('presence checkedAt', typeof p.checkedAt === 'string');
  check('roster hermes gateway entry', p.agents.some(a => a.key === 'hermes:gateway' && a.runtime === 'hermes'));
  // OpenClaw is expected offline unless a gateway is running — must never throw.
  check('openclaw resolves without throwing', p.openclaw && typeof p.openclaw.online === 'boolean');

  // Caching: second call immediately must hit cache (same object identity is fine for value equality)
  const p2 = await getPresence();
  check('presence cached', p2.checkedAt === p.checkedAt);

  process.exit(failed ? 1 : 0);
})();
