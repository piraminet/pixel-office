// Agent runtime presence — first-class Hermes Agent + OpenClaw integration.
// Read-only adapters, no new deps. Used by GET /api/presence.
const fs = require('fs');
const os = require('os');
const path = require('path');

const CACHE_TTL_MS = 5000;

const hermesHome = () => process.env.HERMES_HOME || path.join(os.homedir(), '.hermes');

const readJSON = (filePath) => {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (e) {
    return null;
  }
};

const pidAlive = (pid) => {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return false;
  }
};

// Container consumers can't verify host PIDs (separate PID namespace), so they
// opt into HERMES_PRESENCE_TRUST_FILES=1: online-state + liveness come from the
// files themselves, bounded by mtime freshness. gateway_state.json is
// heartbeat-rewritten by the gateway daemon (short window); active_sessions.json
// is event-driven and only rewritten on lease changes (long window — stale
// sessions are bounded by Hermes' own lease GC, not the writer's clock).
const TRUST_FILE_MODE = () => process.env.HERMES_PRESENCE_TRUST_FILES === '1';
const GATEWAY_FRESHNESS_MS = 5 * 60 * 1000;
const SESSIONS_FRESHNESS_MS = 30 * 60 * 1000;
const fileFresh = (filePath, freshnessMs) => {
  try {
    return Date.now() - fs.statSync(filePath).mtimeMs < freshnessMs;
  } catch (e) {
    return false;
  }
};

// Hermes: one entry per live session. Sources of truth:
//   $HERMES_HOME/runtime/active_sessions.json — per-process session leases (pid, surface, session_id)
//   $HERMES_HOME/gateway_state.json           — gateway daemon state + channel platforms
const hermesPresence = () => {
  const home = hermesHome();
  const sessionsPath = path.join(home, 'runtime', 'active_sessions.json');
  const gatewayPath = path.join(home, 'gateway_state.json');
  const sessionsFile = readJSON(sessionsPath);
  const gatewayFile = readJSON(gatewayPath);

  const entries = (sessionsFile && Array.isArray(sessionsFile.entries)) ? sessionsFile.entries : [];
  const live = entries
    .filter(s => TRUST_FILE_MODE() ? fileFresh(sessionsPath, SESSIONS_FRESHNESS_MS) : pidAlive(s.pid))
    .map(s => ({
      session_id: s.session_id,
      surface: s.surface,
      pid: s.pid,
      started_at: s.started_at || null
    }));

  const gatewayState = gatewayFile ? gatewayFile.gateway_state : null;
  const gatewayPid = gatewayFile ? gatewayFile.pid : null;
  const gateway = gatewayState === 'running' &&
    (TRUST_FILE_MODE() ? fileFresh(gatewayPath, GATEWAY_FRESHNESS_MS) : pidAlive(gatewayPid));

  const platforms = Object.entries((gatewayFile && gatewayFile.platforms) || {})
    .filter(([, p]) => p && p.state === 'connected')
    .map(([name]) => name);

  return {
    runtime: 'hermes',
    home,
    online: gateway || live.length > 0,
    gateway: {
      state: gateway ? 'running' : 'offline',
      pid: gatewayPid || null,
      active_agents: gatewayFile ? gatewayFile.active_agents || 0 : 0
    },
    platforms,
    sessions: live
  };
};

// OpenClaw: probe the gateway's OpenAI-compatible HTTP surface.
// ponytail: online/offline only, no session detail — that needs the gateway WS
// RPC (hello-ok snapshot.presence); add it once an OpenClaw gateway is actually
// running (OPENCLAW_GATEWAY_URL + OPENCLAW_GATEWAY_TOKEN).
const openclawPresence = async () => {
  const url = (process.env.OPENCLAW_GATEWAY_URL || 'http://127.0.0.1:18789').replace(/\/$/, '');
  const token = process.env.OPENCLAW_GATEWAY_TOKEN || '';
  const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

  try {
    const res = await fetch(`${url}/v1/models`, {
      headers,
      signal: AbortSignal.timeout(2500)
    });
    if (res.ok) {
      const data = await res.json();
      return {
        runtime: 'openclaw', online: true, url: url, auth: 'ok',
        models: ((data && data.data) || []).map(m => m.id)
      };
    }
    if (res.status === 401 || res.status === 403) {
      return { runtime: 'openclaw', online: true, url: url, auth: 'rejected', models: [] };
    }
    return { runtime: 'openclaw', online: false, url: url, auth: 'ok', error: `HTTP ${res.status}` };
  } catch (e) {
    return { runtime: 'openclaw', online: false, url: url, auth: 'ok', error: e.message };
  }
};

// Flat roster of live runtime agents for clients that just want "who's here".
const toRoster = (presence) => {
  const roster = [];
  const h = presence.hermes;
  if (h) {
    if (h.gateway.state === 'running') {
      roster.push({
        key: 'hermes:gateway', name: 'Hermes Gateway', runtime: 'hermes', surface: 'gateway',
        detail: `${h.gateway.active_agents} active agent(s), ${h.platforms.length} channel(s): ${h.platforms.join(', ') || 'none'}`
      });
    }
    h.sessions.filter(s => !String(s.surface || '').startsWith('gateway')).forEach(s => {
      roster.push({
        key: `hermes:${s.surface}:${s.session_id}`, name: 'Hermes CLI', runtime: 'hermes',
        surface: s.surface, detail: `session ${s.session_id}`
      });
    });
  }
  const oc = presence.openclaw;
  if (oc && oc.online) {
    roster.push({
      key: 'openclaw:gateway', name: 'OpenClaw Gateway', runtime: 'openclaw', surface: 'gateway',
      detail: oc.auth === 'ok' ? `${oc.models.length} model(s) at ${oc.url}` : `gateway up, auth rejected at ${oc.url}`
    });
  }
  return roster;
};

let cache = null;

const getPresence = async () => {
  if (cache && Date.now() - cache.fetchedAt < CACHE_TTL_MS) return cache.value;
  const hermes = hermesPresence();
  const openclaw = await openclawPresence();
  const value = {
    hermes,
    openclaw,
    agents: toRoster({ hermes, openclaw }),
    checkedAt: new Date().toISOString()
  };
  cache = { fetchedAt: Date.now(), value };
  return value;
};

module.exports = { getPresence, hermesPresence, openclawPresence };
