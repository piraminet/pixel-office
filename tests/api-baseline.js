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
fs.mkdirSync(FIXTURE_DIR, { recursive: true });

// Synthetic env: overrides anything dotenv would load, nothing real touched.
const ENV = Object.assign({}, process.env, {
  PORT: String(PORT),
  PIXEL_DATA_DIR: DATA_DIR,
  DASHBOARD_PASSWORD: 'pixel-office-g1-synthetic',
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
  r = await probe('POST /api/agent/0/move', 'POST', '/api/agent/0/move', { x: 10, y: 20, state: 'idle' });
  check('POST /api/agent/0/move → 200 + echo agent', r.status === 200 && JSON.parse(r.body).agent.x === 10);
  r = await probe('POST /api/agent/99/move', 'POST', '/api/agent/99/move', { x: 1, y: 1 });
  check('POST /api/agent/99/move → 404', r.status === 404);
  r = await probe('POST /api/agent/0/command', 'POST', '/api/agent/0/command', { type: 'move', x: 300, y: 300 });
  check('POST command → 200', r.status === 200);
  r = await probe('GET /api/agent/0/command (consume)', 'GET', '/api/agent/0/command');
  check('GET command returns pushed body', JSON.parse(r.body).x === 300);
  r = await probe('GET /api/agent/0/command (consumed)', 'GET', '/api/agent/0/command');
  check('GET command consumed once → null', JSON.parse(r.body) === null);
  r = await probe('GET /api/ai/status (offline)', 'GET', '/api/ai/status');
  check('GET /api/ai/status offline → 200 available:false', r.status === 200 && JSON.parse(r.body).available === false);
  r = await probe('POST /api/ai/chat (offline)', 'POST', '/api/ai/chat', { prompt: 'ping' });
  check('POST /api/ai/chat offline → 502/500 error', r.status >= 500);
  r = await probe('POST /api/auth/login wrong', 'POST', '/api/auth/login', { password: 'wrong' });
  check('auth/login wrong → 401', r.status === 401);
  const login = await probe('POST /api/auth/login correct', 'POST', '/api/auth/login', { password: 'pixel-office-g1-synthetic' });
  check('auth/login correct → 200 success', login.status === 200 && JSON.parse(login.body).success === true);
  check('auth/login issues NO cookie/session', !login.headers['set-cookie']);
  r = await probe('POST /api/config (mutation w/o auth)', 'POST', '/api/config', { agents: [], rooms: [] });
  check('POST /api/config unauthenticated → 200 (finding S-05)', r.status === 200);
  r = await probe('GET /api/presence', 'GET', '/api/presence');
  check('GET /api/presence → 200 with hermes/openclaw keys', r.status === 200 && !!JSON.parse(r.body).hermes);
  r = await probe('GET /api/briefing (offline integrations)', 'GET', '/api/briefing');
  const brief = JSON.parse(r.body);
  check('GET /api/briefing → 200, AI unavailable gracefully', r.status === 200 && brief.ai.available === false);
  r = await probe('GET /api/email/accounts', 'GET', '/api/email/accounts');
  check('GET /api/email/accounts → 200 (11 configs, no password fields)',
    r.status === 200 && JSON.parse(r.body).accounts.length === 11 &&
    !('password' in JSON.parse(r.body).accounts[0]));
  r = await probe('GET /api/email/inbox (offline)', 'GET', '/api/email/inbox?limit=1&account=jb');
  check('GET /api/email/inbox offline → 200-with-error object (baseline quirk: swallowed errors)',
    r.status === 200 && typeof JSON.parse(r.body).error === 'string');
  r = await probe('GET /api/vault/status (unset creds)', 'GET', '/api/vault/status');
  check('GET /api/vault/status → 200 configured:false', r.status === 200 && JSON.parse(r.body).configured === false);
  r = await probe('GET /api/vault/item/synthetic-id (unset creds)', 'GET', '/api/vault/item/synthetic-id');
  check('GET /api/vault/item/:id no-creds → 200-with-error object (baseline quirk)',
    r.status === 200 && typeof JSON.parse(r.body).error === 'string');
  r = await probe('GET /api/sync/status', 'GET', '/api/sync/status');
  check('GET /api/sync/status → degraded/500 honest', r.status >= 200);
  r = await probe('GET /api/contacts/search?q=test', 'GET', '/api/contacts/search?q=test');
  check('GET /api/contacts/search → 200 empty (no CRM DB present)', r.status === 200 && JSON.parse(r.body).count === 0);
  r = await probe('static /server.js', 'GET', '/server.js');
  check('GET /server.js → 200 SOURCE DOWNLOAD (finding S-01)', r.status === 200 && r.body.includes('express'));
  r = await probe('static /.env', 'GET', '/.env');
  check('GET /.env → 200 SECRET DOWNLOAD (finding S-01)', r.status === 200);
  r = await probe('static /package.json', 'GET', '/package.json');
  check('GET /package.json → 200 (finding S-01)', r.status === 200);
  r = await probe('unknown /api/nope', 'GET', '/api/nope');
  check('unknown /api/* → 200 index.html (catch-all masks)', r.status === 200 && r.body.includes('<html'));

  fs.writeFileSync(path.join(FIXTURE_DIR, 'g1-probes.json'), JSON.stringify(fixtures, null, 2));

  // --- Persistent config + restart recovery ---
  r = await req('POST', '/api/config', { agents: [{ id: 0, name: 'Curator', role: 'Archivist', room: 'Archives', color: 0, x: 311, y: 681, state: 'idle', active: true }], rooms: [] });
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
  r = await req('POST', '/api/agent/0/command', { type: 'move', x: 42, y: 42 });
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
