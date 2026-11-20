#!/usr/bin/env node
/**
 * G22 — Isometric environment manifest library.
 *
 * A "pack" is a directory: assets/environments/<id>/manifest.json (+ background.png).
 * The server lists packs generically — adding a pack is a drop-in directory, no
 * backend changes (G22 requirement). Invalid packs are skipped with a warning
 * instead of breaking the API (missing assets fail gracefully).
 */
'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_ENV_ID = 'continental';
const SCHEMA_VERSION = 1;
const GRID_VALUES = [0, 1, 2, 3]; // 0=Floor 1=Wall/Solid 2=Door 3=Chair
const TILES_WALKABLE = [0, 2, 3]; // chars may occupy these
const FACES = ['up', 'down', 'left', 'right'];
const INTERACTION_ACTIONS = ['idle', 'working', 'sitting', 'drinking', 'reading', 'phone'];
const SLOT_KEYS = ['reception', 'workstations', 'archives'];
const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp'];

const slugOk = (s) => typeof s === 'string' && /^[a-z][a-z0-9-]{1,39}$/.test(s);

function walkableAt(manifest, x, y) {
  const row = manifest.collision && manifest.collision[y];
  return Array.isArray(row) && GRID_VALUES.includes(row[x]) && row[x] !== 1;
}

/**
 * Validate a parsed manifest object. Returns { ok, errors } — structural rules only;
 * on-disk asset availability is checked separately (listPacks).
 */
function validateManifest(manifest, opts) {
  const errors = [];
  const fail = (msg) => errors.push(msg);
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) {
    return { ok: false, errors: ['manifest: not an object'] };
  }
  const m = manifest;
  if (m.schema !== SCHEMA_VERSION) fail(`schema: expected ${SCHEMA_VERSION}, got ${JSON.stringify(m.schema)}`);
  if (!slugOk(m.id)) fail('id: must be a lowercase kebab slug (2-40 chars)');

  // grid
  const g = m.grid || {};
  const cols = g.cols, rows = g.rows, tile = g.tile;
  for (const [k, v] of [['grid.cols', cols], ['grid.rows', rows]]) {
    if (!Number.isInteger(v) || v < 8 || v > 64) fail(`${k}: integer 8..64 required`);
  }
  if (![16, 32, 64].includes(tile)) fail('grid.tile: must be one of 16, 32, 64');

  // collision
  if (!Array.isArray(m.collision) || m.collision.length !== rows) {
    fail(`collision: must have ${rows} rows`);
  } else {
    m.collision.forEach((row, y) => {
      if (!Array.isArray(row) || row.length !== cols) {
        fail(`collision[${y}]: must have ${cols} cells`);
      } else if (row.some((v) => !GRID_VALUES.includes(v))) {
        fail(`collision[${y}]: values must be in ${GRID_VALUES.join(',')}`);
      }
    });
  }

  const at = (x, y) => (m.collision[y] || [])[x];
  const inBounds = (p) => Array.isArray(p) && Number.isInteger(p[0]) && Number.isInteger(p[1]) && p[0] >= 0 && p[0] < cols && p[1] >= 0 && p[1] < rows;
  const walkable = (p) => inBounds(p) && TILES_WALKABLE.includes(at(p[0], p[1]));

  // spawn
  if (!walkable(m.spawn)) fail('spawn: must be an in-bounds walkable [x,y]');

  // rooms
  const roomIds = new Set();
  const slotRooms = new Set();
  if (!Array.isArray(m.rooms) || m.rooms.length < 1 || m.rooms.length > 16) {
    fail('rooms: 1..16 rooms required');
  } else {
    for (const r of m.rooms) {
      if (!r || typeof r !== 'object') { fail('rooms: non-object entry'); continue; }
      if (!slugOk(r.id)) { fail(`room.id: invalid slug ${JSON.stringify(r.id)}`); continue; }
      if (roomIds.has(r.id)) fail(`room.id: duplicate ${r.id}`);
      roomIds.add(r.id);
      if (typeof r.name !== 'string' || r.name.length < 1 || r.name.length > 48) {
        fail(`room ${r.id}: name required (1..48 chars)`);
      }
      if (r.slot !== undefined) {
        if (!SLOT_KEYS.includes(r.slot)) {
          fail(`room ${r.id}: slot must be one of ${SLOT_KEYS.join(',')}`);
        } else if (slotRooms.has(r.slot)) {
          fail(`room ${r.id}: slot ${r.slot} already assigned`);
        } else {
          slotRooms.add(r.slot);
        }
      }
      const tiles = Array.isArray(r.tiles) ? r.tiles : [];
      if (tiles.length < 1 || tiles.length > 400) {
        fail(`room ${r.id}: tiles must have 1..400 entries`);
      } else {
        const seen = new Set();
        for (const t of tiles) {
          const [x, y] = t;
          if (!inBounds(t)) { fail(`room ${r.id}: tile out of bounds ${JSON.stringify(t)}`); break; }
          if (seen.has(`${x},${y}`)) { fail(`room ${r.id}: duplicate tile ${x},${y}`); break; }
          seen.add(`${x},${y}`);
          if (!TILES_WALKABLE.includes(at(x, y))) {
            fail(`room ${r.id}: tile ${x},${y} is not walkable (value ${at(x, y)})`);
            break;
          }
        }
      }
      if (r.anchor !== undefined && !inBounds(r.anchor)) {
        fail(`room ${r.id}: anchor out of bounds`);
      }
    }
  }

  // workstations
  if (!Array.isArray(m.workstations) || m.workstations.length < 1 || m.workstations.length > 16) {
    fail('workstations: 1..16 required');
  } else {
    const ids = new Set();
    for (const w of m.workstations) {
      if (!w || !slugOk(w.id)) { fail('workstations: entry missing valid id'); continue; }
      if (ids.has(w.id)) fail(`workstations: duplicate ${w.id}`);
      ids.add(w.id);
      if (!inBounds([w.x, w.y])) { fail(`workstation ${w.id}: out of bounds`); continue; }
      if (![0, 3].includes(at(w.x, w.y))) {
        fail(`workstation ${w.id}: must sit on floor (0) or chair (3), got ${at(w.x, w.y)}`);
      }
      if (!FACES.includes(w.face)) fail(`workstation ${w.id}: face must be one of ${FACES.join(',')}`);
    }
  }

  // interactions
  if (m.interactions !== undefined) {
    if (!Array.isArray(m.interactions) || m.interactions.length > 16) {
      fail('interactions: at most 16');
    } else {
      const ids = new Set();
      for (const i of m.interactions) {
        if (!i || !slugOk(i.id)) { fail('interactions: entry missing valid id'); continue; }
        if (ids.has(i.id)) fail(`interactions: duplicate ${i.id}`);
        ids.add(i.id);
        if (!inBounds([i.x, i.y])) { fail(`interaction ${i.id}: out of bounds`); continue; }
        if (!TILES_WALKABLE.includes(at(i.x, i.y))) {
          fail(`interaction ${i.id}: must be on a walkable tile (0/2/3)`);
        }
        if (!INTERACTION_ACTIONS.includes(i.action)) {
          fail(`interaction ${i.id}: action must be one of ${INTERACTION_ACTIONS.join(',')}`);
        }
        if (i.face !== undefined && !FACES.includes(i.face)) fail(`interaction ${i.id}: invalid face`);
      }
    }
  }

  // placement (semantic slot → room id used when remapping agent bindings)
  if (m.placement !== undefined) {
    if (typeof m.placement !== 'object' || Array.isArray(m.placement)) {
      fail('placement: must be an object');
    } else {
      for (const [slot, roomId] of Object.entries(m.placement)) {
        if (!SLOT_KEYS.includes(slot)) fail(`placement: unknown slot ${slot}`);
        else if (!roomIds.has(roomId)) fail(`placement: slot ${slot} → unknown room ${roomId}`);
      }
    }
  }

  // assets
  const assets = m.assets || {};
  const bg = assets.background;
  if (typeof bg !== 'string' || !IMAGE_EXTENSIONS.some((ext) => bg.endsWith(ext))) {
    fail('assets.background: must end in an image extension');
  } else if (!bg.startsWith(`/assets/environments/${m.id}/`)) {
    fail('assets.background: must live under the pack directory');
  }

  if (opts && opts.id) {
    // Enforce directory↔id consistency when loading from disk. Structural
    // validation (tests use synthetic ids) skips this.
    if (m.id !== opts.id) fail(`id: manifest declares "${m.id}" but directory is "${opts.id}"`);
  }

  return { ok: errors.length === 0, errors };
}

function manifestPath(environmentsRoot, envId) {
  return path.join(environmentsRoot, envId, 'manifest.json');
}

function readManifest(environmentsRoot, envId) {
  let raw;
  try {
    raw = fs.readFileSync(manifestPath(environmentsRoot, envId), 'utf8');
  } catch (e) {
    return { manifest: null, warnings: [`read failed: ${e.code || e.message}`] };
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    return { manifest: null, warnings: ['manifest.json: invalid JSON'] };
  }
  const { ok, errors } = validateManifest(parsed, { id: envId });
  if (!ok) {
    return { manifest: null, warnings: errors.map((e) => `manifest: ${e}`) };
  }
  return { manifest: parsed, warnings: [] };
}

/**
 * Scan the environments root. Directories without a valid manifest are skipped
 * (with warnings). Returns { environments: [...], warnings: [...] }.
 */
function listPacks(environmentsRoot) {
  const environments = [];
  const warnings = [];
  let entries;
  try {
    entries = fs.readdirSync(environmentsRoot, { withFileTypes: true });
  } catch (e) {
    return { environments, warnings: [`environments dir not readable: ${e.code || e.message}`] };
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (!slugOk(entry.name)) {
      warnings.push(`skipped directory "${entry.name}": not a valid pack id`);
      continue;
    }
    const { manifest, warnings: w } = readManifest(environmentsRoot, entry.name);
    warnings.push(...w);
    if (!manifest) continue;
    const bgAbs = path.join(environmentsRoot, entry.name, path.basename(manifest.assets.background));
    environments.push({
      id: manifest.id,
      name: manifest.name,
      style: manifest.style || '',
      blurb: manifest.blurb || '',
      default: manifest.default === true,
      // Runtime availability (graceful missing-asset handling is the caller's job).
      available: fs.existsSync(bgAbs),
    });
  }
  return { environments, warnings };
}

module.exports = {
  DEFAULT_ENV_ID,
  SCHEMA_VERSION,
  GRID_VALUES,
  TILES_WALKABLE,
  FACES,
  INTERACTION_ACTIONS,
  SLOT_KEYS,
  validateManifest,
  readManifest,
  listPacks,
  manifestPath,
  walkableAt,
};
