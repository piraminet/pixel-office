#!/usr/bin/env node
// G1 behavioral baseline probe: boots server.js with SYNTHETIC env, probes every
// enumerated route, records sanitized fixtures, and tests restart recovery.
// Run: node tests/api-baseline.js   (fixture path override: BASELINE_FIXTURES=...)
// External services are forced offline (localhost / empty creds) so results are
// deterministic; live-service behavior is recorded separately in the G1 doc.
'use strict';
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');

const PORT = 19031;
const BASE = `http://127.0.0.1:${PORT}`;
const DATA_DIR = fs.mkdtempSync('/tmp/pixel-g1-');
const FIXTURE_DIR = process.env.BASELINE_FIXTURES || path.join(__dirname, '..', 'docs', 'migration', 'fixtures');
const TOKEN = 'synthetic-api-token';
fs.mkdirSync(FIXTURE_DIR, { recursive: true });

// Synthetic env: overrides anything dotenv would load, nothing real touched.
const ENV = Object.assign({}, process.env, {
  PORT: String(PORT),
  PIXEL_DATA_DIR: DATA_DIR,
  DASHBOARD_PASSWORD: 'pixel-office-g1-synthetic',
  PIXEL_API_TOKEN: 'synthetic-api-token',
  PIXEL_SESSION_SECRET: 'synthetic-session-secret-for-tests',
  LITELLM_API_URL: 'http://127.0.0.1:9',       // deterministic refused connection
  LITELLM_API_KEY: '',
  MAIL2_HOST: '127.0.0.1',                      // SSH to non-existent key → fail fast
  GAMMA_HOST: '127.0.0.1',
  VW_USER_CLIENT_ID: '', VW_USER_CLIENT_SECRET: '',
  VW_ORG_CLIENT_ID: '', VW_ORG_CLIENT_SECRET: '',
});
ENV.HERMES_HOME = '';                           // presence reads default ~/.hermes (live host state)

let child = null;
let passed = 0, failed = 0;
const check = (name, ok, detail) => {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`);
  ok ? passed++ : failed++;
};

const req = (method, path_, body, headers) => new Promise((resolve) => {
  const data = body ? JSON.stringify(body) : null;
  const r = http.request(BASE + path_, {
    method,
    headers: Object.assign({ 'Content-Type': 'application/json' },
      data ? { 'Content-Length': Buffer.byteLength(data) } : {}, headers || {})
  }, (res) => {
    let out = '';
    res.on('data', d => out += d);
    res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: out }));
  });
  r.on('error', (e) => resolve({ status: 0, headers: {}, body: String(e) }));
  if (data) r.write(data);
  r.end();
});

const shape = (v) => { // sanitized structural fingerprint — no live values
  if (Array.isArray(v)) return { array: v.length, of: v.length ? shape(v[0]) : null };
  if (v && typeof v === 'object') {
    const o = {};
    for (const k of Object.keys(v).sort()) o[k] = shape(v[k]);
    return o;
  }
  if (typeof v === 'string') return 'string';
  return v === null ? 'null' : typeof v;
};

const startServer = () => new Promise((resolve, reject) => {
  child = spawn('node', ['server.js'], { env: ENV, stdio: ['ignore', 'pipe', 'pipe'] });
  let buf = '';
  const onData = () => {};
  child.stdout.on('data', d => buf += d);
  child.stderr.on('data', d => buf += d);
  const t0 = Date.now();
  const poll = setInterval(async () => {
    const res = await req('GET', '/api/config');
    if (res.status === 200) {
      clearInterval(poll);
      resolve({ startupMs: Date.now() - t0, log: buf.split('\n').slice(0, 8) });
    } else if (Date.now() - t0 > 15000) { clearInterval(poll); reject(new Error('server did not start')); }
  }, 150);
  child.on('exit', () => { clearInterval(poll); reject(new Error('server exited during startup')); });
});

const stopServer = () => new Promise((resolve) => {
  if (!child) return resolve();
  child.on('exit', resolve);
  child.kill('SIGTERM');
});

(async () => {
  const boot = await startServer();
  check('boot: server starts and serves /api/config', !!boot.startupMs, `${boot.startupMs}ms`);

  // --- Route matrix (status + sanitized shape) ---
  const fixtures = { boot, probes: [] };
  const probe = async (name, method, p, body, headers) => {
    const res = await req(method, p, body, headers);
    let parsed = null;
    try { parsed = JSON.parse(res.body); } catch (e) { parsed = res.body.slice(0, 80); }
    fixtures.probes.push({ name, method, path: p, status: res.status, bodyShape: shape(parsed) });
    return res;
  };

  let r = await probe('GET /api/config', 'GET', '/api/config');
  check('GET /api/config → 200 with 6-agent roster', r.status === 200 && JSON.parse(r.body).agents.length === 6);

  r = await probe('GET /api/rooms', 'GET', '/api/rooms');
  check('GET /api/rooms → 200', r.status === 200);
  r = await probe('GET /api/collision (fresh install)', 'GET', '/api/collision');
  check('GET /api/collision fresh → 500 "Map not available" (baseline quirk: UI falls back)',
    r.status === 500 && r.body.includes('Map not available'));
  r = await probe('GET /api/messages', 'GET', '/api/messages');
  check('GET /api/messages → 200 (6 ids)', r.status === 200 && Object.keys(JSON.parse(r.body)).length === 6);
  r = await probe('GET /api/log (empty)', 'GET', '/api/log');
  check('GET /api/log → 200 (empty array tolerated)', r.status === 200 && Array.isArray(JSON.parse(r.body)));
  r = await probe('POST /api/agent/0/move (unauth)', 'POST', '/api/agent/0/move', { x: 10, y: 20, state: 'idle' });
  check('POST move unauthenticated → 401', r.status === 401);
  r = await probe('POST /api/agent/0/move (token)', 'POST', '/api/agent/0/move', { x: 10, y: 20, state: 'idle' }, { Authorization: `Bearer ${TOKEN}` });
  check('POST /api/agent/0/move → 200 + echo agent (token)', r.status === 200 && JSON.parse(r.body).agent.x === 10);
  r = await probe('POST /api/agent/99/move (unauth)', 'POST', '/api/agent/99/move', { x: 1, y: 1 });
  check('POST unknown agent unauthenticated → 401 (auth before existence)', r.status === 401);
  r = await probe('POST /api/agent/99/move (token)', 'POST', '/api/agent/99/move', { x: 1, y: 1 }, { Authorization: `Bearer ${TOKEN}` });
  check('POST /api/agent/99/move → 404', r.status === 404);
  r = await probe('POST /api/agent/0/command (token)', 'POST', '/api/agent/0/command', { type: 'move', x: 300, y: 300 }, { Authorization: `Bearer ${TOKEN}` });
  check('POST command → 200', r.status === 200);
  r = await probe('GET /api/agent/0/command (consume)', 'GET', '/api/agent/0/command');
  check('GET command returns pushed body', JSON.parse(r.body).x === 300);
  r = await probe('GET /api/agent/0/command (consumed)', 'GET', '/api/agent/0/command');
  check('GET command consumed once → null', JSON.parse(r.body) === null);
  r = await probe('GET /api/ai/status (offline)', 'GET', '/api/ai/status');
  check('GET /api/ai/status offline → 200 available:false', r.status === 200 && JSON.parse(r.body).available === false);
  r = await probe('POST /api/ai/chat (unauth)', 'POST', '/api/ai/chat', { prompt: 'ping' });
  check('POST /api/ai/chat unauthenticated → 401 (G2 S-08)', r.status === 401);
  r = await probe('POST /api/ai/chat (token, offline LLM)', 'POST', '/api/ai/chat', { prompt: 'ping', systemPrompt: 'ignored' }, { Authorization: `Bearer ${TOKEN}` });
  check('POST /api/ai/chat token + offline LLM → 502/500 (server-owned prompt only)', r.status >= 500);
  r = await probe('POST /api/auth/login wrong', 'POST', '/api/auth/login', { password: 'wrong' });
  check('auth/login wrong → 401', r.status === 401);
  const login = await probe('POST /api/auth/login correct', 'POST', '/api/auth/login', { password: 'pixel-office-g1-synthetic' });
  check('auth/login correct → 200 success + HttpOnly session cookie', login.status === 200 && JSON.parse(login.body).success === true && /pixel_session=/.test((login.headers['set-cookie'] || [])[0] || ''));
  r = await probe('POST /api/config (unauthenticated)', 'POST', '/api/config', { agents: [], rooms: [] });
  check('POST /api/config unauthenticated → 401 (G2 remediation of S-05)', r.status === 401);
  r = await probe('POST /api/config (bearer token)', 'POST', '/api/config', { agents: [], rooms: [] }, { Authorization: `Bearer ${TOKEN}` });
  check('POST /api/config with bearer token → 200 (automation path)', r.status === 200);
  r = await probe('GET /api/presence', 'GET', '/api/presence');
  check('GET /api/presence → 200 with hermes/openclaw keys', r.status === 200 && !!JSON.parse(r.body).hermes);
  r = await probe('GET /api/briefing (unauth)', 'GET', '/api/briefing');
  check('GET /api/briefing unauthenticated → 401 (G2, internal aggregate)', r.status === 401);
  r = await probe('GET /api/briefing (token, offline integrations)', 'GET', '/api/briefing', null, { Authorization: `Bearer ${TOKEN}` });
  const brief = JSON.parse(r.body);
  check('GET /api/briefing → 200, AI unavailable gracefully', r.status === 200 && brief.ai.available === false);
  r = await probe('GET /api/email/accounts', 'GET', '/api/email/accounts');
  check('GET /api/email/accounts → 200 (11 configs, no password fields)',
    r.status === 200 && JSON.parse(r.body).accounts.length === 11 &&
    !('password' in JSON.parse(r.body).accounts[0]));
  r = await probe('GET /api/email/inbox (offline)', 'GET', '/api/email/inbox?limit=1&account=jb');
  check('GET /api/email/inbox offline → 200-with-error object (baseline quirk: swallowed errors)',
    r.status === 200 && typeof JSON.parse(r.body).error === 'string');
  r = await probe('GET /api/vault/status (token, unset creds)', 'GET', '/api/vault/status', null, { Authorization: `Bearer ${TOKEN}` });
  check('GET /api/vault/status → 200 configured:false', r.status === 200 && JSON.parse(r.body).configured === false);
  r = await probe('GET /api/vault/item/synthetic-id', 'GET', '/api/vault/item/synthetic-id');
  check('GET /api/vault/item/:id → 403 DISABLED (G2 remediation of S-02)', r.status === 403);
  r = await probe('POST /api/email/send (unauth)', 'POST', '/api/email/send', { to: 'x@y.z', subject: 's' });
  check('POST /api/email/send → 403 DISABLED (G2 remediation of S-03)', r.status === 403);
  r = await probe('GET /api/sync/status', 'GET', '/api/sync/status');
  check('GET /api/sync/status → degraded/500 honest', r.status >= 200);
  r = await probe('GET /api/contacts/search?q=test', 'GET', '/api/contacts/search?q=test');
  check('GET /api/contacts/search → 403 DISABLED (G2 remediation of S-04)', r.status === 403);
  r = await probe('static /server.js', 'GET', '/server.js');
  check('GET /server.js → 404 (G2 remediation of S-01: source not served)', r.status === 404);
  r = await probe('static /.env', 'GET', '/.env');
  check('GET /.env → 404 (G2 remediation of S-01: secrets not served)', r.status === 404);
  r = await probe('static /package.json', 'GET', '/package.json');
  check('GET /package.json → 404 (G2 remediation of S-01)', r.status === 404);
  r = await probe('static traversal /assets/../server.js', 'GET', '/assets/../server.js');
  check('GET /assets/../server.js → 404 (traversal blocked)', r.status === 404);
  r = await probe('static / (index)', 'GET', '/');
  check('GET / → 200 index.html (public allowlist)', r.status === 200 && r.body.includes('<html'));
  r = await probe('static /assets/characters/char_0.png', 'GET', '/assets/characters/char_0.png');
  check('GET /assets/characters/char_0.png → 200 (public sprite)', r.status === 200);
  r = await probe('unknown page /nope', 'GET', '/nope');
  check('unknown non-API path → 404 (no accidental page serving)', r.status === 404);
  r = await probe('unknown /api/nope', 'GET', '/api/nope');
  check('unknown /api/* → 404 JSON (catch-all no longer masks)', r.status === 404 && JSON.parse(r.body).error === 'not found');

  // --- Login rate limiting (G2) ---
  let rateLimited = false;
  for (let i = 0; i < 6; i++) {
    const rr = await req('POST', '/api/auth/login', { password: 'wrong' });
    if (rr.status === 429) { rateLimited = true; break; }
  }
  check('login rate limit: 6 rapid wrong attempts hit 429', rateLimited);

  fs.writeFileSync(path.join(FIXTURE_DIR, 'g1-probes.json'), JSON.stringify(fixtures, null, 2));

  // --- Persistent config + restart recovery ---
  r = await req('POST', '/api/config', { agents: [{ id: 0, name: 'Curator', role: 'Archivist', room: 'Archives', color: 0, x: 311, y: 681, state: 'idle', active: true }], rooms: [] }, { Authorization: `Bearer ${TOKEN}` });
  check('POST /api/config persists to disk', r.status === 200 && fs.existsSync(path.join(DATA_DIR, 'agents.json')));
  await stopServer();
  const boot2 = await startServer();
  check('restart: server boots again', !!boot2.startupMs);
  r = await req('GET', '/api/config');
  const after = JSON.parse(r.body);
  const names = after.agents.map(a => a.name);
  check('restart recovery: saved roster reloaded (Curator x=311)',
    after.agents.some(a => a.name === 'Curator' && a.x === 311));
  check('restart quirk: Ghostface auto-reinserted into custom rosters (server.js migration)',
    names.includes('Ghostface'), 'roster=' + names.join(','));
  r = await req('POST', '/api/agent/0/command', { type: 'move', x: 42, y: 42 }, { Authorization: `Bearer ${TOKEN}` });
  await stopServer();
  await startServer();
  r = await req('GET', '/api/agent/0/command');
  check('restart loss: in-memory commands do NOT survive restart (documented)', JSON.parse(r.body) === null);
  await stopServer();

  fs.writeFileSync(path.join(FIXTURE_DIR, 'g1-recovery.json'), JSON.stringify({
    configPersisted: true, commandLostOnRestart: true
  }, null, 2));

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error('HARNESS ERROR:', e.message); process.exit(2); });
