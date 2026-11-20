#!/usr/bin/env node
/**
 * G22 B1 — environment system behavioral tests.
 * Boots server.js with synthetic env (same harness as tests/api-baseline.js) and
 * probes the environment registry, selection persistence, restart recovery and
 * the manifest-collision/rooms gating for non-default environments.
 *
 * Run: node tests/environments.js
 */
'use strict';
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');

const PORT = 19032;
const BASE = `http://127.0.0.1:${PORT}`;
const DATA_DIR = fs.mkdtempSync('/tmp/pixel-g22-b1-');
const TOKEN = 'synthetic-api-token';
const AUTH = { 'Authorization': `Bearer ${TOKEN}` };
const TEST_PACK_ID = 'g22-test-pack';
const TEST_PACK_DIR = path.join(__dirname, '..', 'assets', 'environments', TEST_PACK_ID);

const ENV = Object.assign({}, process.env, {
  PORT: String(PORT),
  PIXEL_DATA_DIR: DATA_DIR,
  DASHBOARD_PASSWORD: 'pixel-office-g22-synthetic',
  PIXEL_API_TOKEN: TOKEN,
  PIXEL_SESSION_SECRET: 'synthetic-session-secret-for-tests',
  LITELLM_API_URL: 'http://127.0.0.1:9',
  LITELLM_API_KEY: '',
  MAIL2_HOST: '127.0.0.1',
  GAMMA_HOST: '127.0.0.1',
  VW_USER_CLIENT_ID: '', VW_USER_CLIENT_SECRET: '',
  VW_ORG_CLIENT_ID: '', VW_ORG_CLIENT_SECRET: '',
});
ENV.HERMES_HOME = '';

let passed = 0, failed = 0;
const check = (name, ok, detail) => {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`);
  ok ? passed++ : failed++;
};

const req = (method, p, body, headers) => new Promise((resolve) => {
  const data = body ? JSON.stringify(body) : null;
  const r = http.request(BASE + p, {
    method,
    headers: Object.assign({ 'Content-Type': 'application/json' },
      data ? { 'Content-Length': Buffer.byteLength(data) } : {}, headers || {})
  }, (res) => {
    let out = '';
    res.on('data', d => out += d);
    res.on('end', () => resolve({ status: res.statusCode, body: out, parsed: safeJSON(out) }));
  });
  r.on('error', (e) => resolve({ status: 0, parsed: null, body: String(e) }));
  if (data) r.write(data);
  r.end();
});
const safeJSON = (s) => { try { return JSON.parse(s); } catch (e) { return null; } };

const startServer = () => new Promise((resolve, reject) => {
  child = spawn('node', ['server.js'], { env: ENV, stdio: ['ignore', 'pipe', 'pipe'] });
  let buf = '';
  child.stdout.on('data', d => buf += d);
  child.stderr.on('data', d => buf += d);
  const t0 = Date.now();
  const poll = setInterval(async () => {
    const res = await req('GET', '/api/config');
    if (res.status === 200) {
      clearInterval(poll);
      resolve({ startupMs: Date.now() - t0, log: buf });
    } else if (Date.now() - t0 > 15000) {
      clearInterval(poll); reject(new Error('server did not start'));
    }
  }, 150);
  child.on('exit', () => { clearInterval(poll); reject(new Error('server exited during startup')); });
});
const stopServer = () => new Promise((resolve) => {
  if (!child) return resolve();
  child.on('exit', resolve);
  child.kill('SIGTERM');
});

// Synthetic second pack (valid per environments.js validator), removed on cleanup.
function writeTestPack(withBackground) {
  const collision = [];
  for (let y = 0; y < 10; y++) {
    collision.push(Array.from({ length: 10 }, (_, x) =>
      (y === 0 || y === 9 || x === 0 || x === 9) ? 1 : 0));
  }
  collision[4][4] = 3;
  const manifest = {
    schema: 1,
    id: TEST_PACK_ID,
    name: 'Test Deck',
    style: 'test',
    blurb: 'Synthetic G22 test pack',
    default: false,
    grid: { cols: 10, rows: 10, tile: 32 },
    assets: { background: `/assets/environments/${TEST_PACK_ID}/background.png` },
    collision,
    rooms: [{ id: 'bridge', name: 'Bridge', slot: 'reception',
      anchor: [5, 5], tiles: [[5, 5], [4, 5], [5, 4]] }],
    workstations: [{ id: 'ws1', x: 4, y: 4, face: 'up' }],
    interactions: [{ id: 'helm', x: 5, y: 6, action: 'working', face: 'up' }],
    spawn: [5, 4],
    placement: { reception: 'bridge', workstations: 'bridge', archives: 'bridge' }
  };
  fs.mkdirSync(TEST_PACK_DIR, { recursive: true });
  fs.writeFileSync(path.join(TEST_PACK_DIR, 'manifest.json'), JSON.stringify(manifest, null, 2));
  if (withBackground) {
    fs.writeFileSync(path.join(TEST_PACK_DIR, 'background.png'), 'png-placeholder');
  }
}

// Invalid pack: must not be listed (graceful skip).
const BAD_PACK_ID = 'g22-bad-pack';
function writeBadPack() {
  const dir = path.join(__dirname, '..', 'assets', 'environments', BAD_PACK_ID);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'manifest.json'), JSON.stringify({ schema: 2, id: BAD_PACK_ID }));
  return dir;
}

let child = null;

(async () => {
  await runSuite();

  const packsCleaned = cleanupPackDirs();
  check('cleanup: synthetic packs removed from repo assets', packsCleaned);
  await stopServer();
  console.log(`\n${passed} passed, ${failed} failed (G22 B1 environments)`);
  process.exit(failed ? 1 : 0);

  // ---- suite ----
  async function runSuite() {
    const badDir = writeBadPack();

    // Phase 1: default env, single pack (continental)
    const boot = await startServer();
    check('boot: server starts with environments registry', !!boot.startupMs, `${boot.startupMs}ms`);
    fs.rmSync(badDir, { recursive: true, force: true });

    let r = await req('GET', '/api/environments');
    const list = r.parsed;
    check('GET /api/environments → 200', r.status === 200);
    check('default environment is continental', r.status === 200 && list.default === 'continental');
    check('active default on fresh install (first deployment)', list.active === 'continental');
    check('continental pack listed and available',
      list.count === 1 && list.environments[0].id === 'continental' && list.environments[0].available === true);
    check('invalid pack (schema 2) not listed', !list.environments.some(e => e.id === BAD_PACK_ID));

    r = await req('GET', '/api/environment');
    check('GET /api/environment → manifest of active env',
      r.status === 200 && r.parsed.id === 'continental' && r.parsed.manifest &&
      r.parsed.manifest.grid.cols === 18 && r.parsed.manifest.grid.rows === 22);
    check('continental manifest carries 7 rooms + 16 workstations + placement',
      r.parsed.manifest.rooms.length === 7 &&
      r.parsed.manifest.workstations.length === 16 &&
      r.parsed.manifest.placement.reception === 'reception' &&
      r.parsed.manifest.spawn[1] === 20);

    r = await req('GET', '/api/environment/continental/manifest');
    check('GET manifest by id → 200', r.status === 200 && r.parsed.manifest.id === 'continental');
    r = await req('GET', '/api/environment/g22-test-pack/manifest');
    check('GET manifest of unknown pack → 404', r.status === 404);
    r = await req('GET', '/api/environment/..%2F..%2Fserver.js/manifest');
    check('GET manifest path traversal → 404', r.status === 404);

    // write routes still auth-gated
    r = await req('POST', '/api/environment', { id: 'continental' });
    check('POST /api/environment unauthenticated → 401', r.status === 401);
    r = await req('POST', '/api/collision', [[0]]);
    check('POST /api/collision unauthenticated → 401 (unchanged)', r.status === 401);

    // default env keeps painted-map endpoints
    r = await req('POST', '/api/collision', [[1, 1], [1, 0]], AUTH);
    check('POST /api/collision (default env, auth) → 200 legacy behavior', r.status === 200);
    r = await req('GET', '/api/collision');
    check('GET /api/collision (default env) → painted collision', r.status === 200 &&
      Array.isArray(r.parsed) && r.parsed.length === 2);
    r = await req('POST', '/api/rooms', [{ name: 'Reception', x: 10, y: 7, tiles: [{ x: 10, y: 7 }] }], AUTH);
    check('POST /api/rooms (default env, auth) → 200 legacy behavior', r.status === 200);

    // ---- Phase 2: second pack, switching + gating + persistence ----
    writeTestPack(false);
    r = await req('GET', '/api/environments');
    check('second pack listed with availability flag',
      r.status === 200 && r.parsed.count === 2 &&
      r.parsed.environments.some(e => e.id === TEST_PACK_ID && e.available === false));

    r = await req('POST', '/api/environment', {}, AUTH);
    check('POST /api/environment missing id → 400', r.status === 400);
    r = await req('POST', '/api/environment', { id: 'nonexistent' }, AUTH);
    check('POST /api/environment unknown pack → 404', r.status === 404);
    r = await req('POST', '/api/environment', { id: TEST_PACK_ID }, AUTH);
    check('POST /api/environment switch → 200', r.status === 200 && r.parsed.id === TEST_PACK_ID);

    r = await req('GET', '/api/environment');
    check('active env switched (GET reflects selection)', r.status === 200 && r.parsed.id === TEST_PACK_ID);
    check('selection persisted to data/environment.json',
      (safeJSON(fs.readFileSync(path.join(DATA_DIR, 'environment.json'), 'utf8')) || {}).id === TEST_PACK_ID);

    r = await req('GET', '/api/collision');
    check('GET /api/collision (non-default) → manifest collision (10 rows)', r.status === 200 &&
      JSON.stringify(r.parsed[4]) === JSON.stringify([1, 0, 0, 0, 3, 0, 0, 0, 0, 1]));
    r = await req('GET', '/api/rooms');
    check('GET /api/rooms (non-default) → manifest rooms in quick format',
      r.status === 200 && Array.isArray(r.parsed) && r.parsed[0].id === 'bridge' &&
      r.parsed[0].name === 'Bridge' &&
      Array.isArray(r.parsed[0].tiles) && r.parsed[0].tiles[0].x === 5);
    r = await req('POST', '/api/collision', [[0]], AUTH);
    check('POST /api/collision (non-default) → 409', r.status === 409);
    r = await req('POST', '/api/rooms', [], AUTH);
    check('POST /api/rooms (non-default) → 409', r.status === 409);

    // config/roster unchanged by environment
    r = await req('GET', '/api/config');
    check('agent roster unaffected by environment selection',
      r.status === 200 && Array.isArray(r.parsed.agents) && r.parsed.agents.length === 6);

    // ---- Phase 3: restart persistence + graceful missing-pack fallback ----
    await stopServer();
    const envFileBefore = fs.existsSync(path.join(DATA_DIR, 'environment.json'));
    check('environment.json survived shutdown', envFileBefore);
    await startServer();
    r = await req('GET', '/api/environment');
    check('restart: selection restored from persistence', r.status === 200 && r.parsed.id === TEST_PACK_ID);

    await stopServer();
    fs.rmSync(TEST_PACK_DIR, { recursive: true, force: true });
    await startServer();
    r = await req('GET', '/api/environments');
    check('deleted selected pack: registry has no selection pack', r.status === 200 && r.parsed.count === 1);
    r = await req('GET', '/api/environment');
    check('deleted selected pack: graceful fallback to continental', r.status === 200 && r.parsed.id === 'continental');
    r = await req('POST', '/api/environment', { id: TEST_PACK_ID }, AUTH);
    check('switch to deleted pack → 404 with warnings', r.status === 404 && r.parsed.error === 'environment not found');
  }

  function cleanupPackDirs() {
    try {
      fs.rmSync(TEST_PACK_DIR, { recursive: true, force: true });
      fs.rmSync(path.join(__dirname, '..', 'assets', 'environments', BAD_PACK_ID), { recursive: true, force: true });
      return !fs.existsSync(TEST_PACK_DIR);
    } catch (e) {
      return false;
    }
  }
})();
