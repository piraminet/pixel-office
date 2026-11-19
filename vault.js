const { Client } = require('ssh2');
const fs = require('fs');

// Configuration
const SSH_HOST = process.env.MAIL2_HOST || '159.65.183.161';
const SSH_USER = process.env.MAIL2_USER || 'root';
const SSH_KEY_PATH = process.env.SSH_KEY_PATH || '/app/ssh/id_ed25519';

// Gamma SSH for rbw access (rbw is installed on gateway, not on mail2)
// We'll use gamma since that's where the pixel office runs
const GAMMA_HOST = process.env.GAMMA_HOST || '192.168.15.230';
const GAMMA_USER = process.env.GAMMA_USER || 'bageera';

// Vaultwarden API credentials (from env or secrets)
const VW_BASE_URL = process.env.VW_BASE_URL || 'https://bw.theblacktech.com';
const VW_USER_CLIENT_ID = process.env.VW_USER_CLIENT_ID || '';
const VW_USER_CLIENT_SECRET = process.env.VW_USER_CLIENT_SECRET || '';
const VW_ORG_CLIENT_ID = process.env.VW_ORG_CLIENT_ID || '';
const VW_ORG_CLIENT_SECRET = process.env.VW_ORG_CLIENT_SECRET || '';

// Cache
let sshKeyCache = null;
let tokenCache = null;
let tokenExpiry = 0;

function getSSHKey() {
  if (sshKeyCache) return sshKeyCache;
  try {
    sshKeyCache = fs.readFileSync(SSH_KEY_PATH, 'utf8');
    return sshKeyCache;
  } catch (e) {
    throw new Error(`Cannot read SSH key: ${e.message}`);
  }
}

// Run command on gamma via SSH
function runOnGamma(cmd, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const conn = new Client();
    const t = setTimeout(() => { conn.end(); reject(new Error('SSH timeout')); }, timeoutMs);

    conn.on('ready', () => {
      conn.exec(cmd, (err, stream) => {
        if (err) { clearTimeout(t); conn.end(); reject(err); return; }
        let out = '', errOut = '';
        stream.on('data', d => out += d.toString());
        stream.stderr.on('data', d => errOut += d.toString());
        stream.on('close', () => {
          clearTimeout(t);
          conn.end();
          resolve({ out: out.trim(), errOut: errOut.trim() });
        });
      });
    });

    conn.on('error', err => { clearTimeout(t); reject(err); });
    conn.connect({
      host: GAMMA_HOST, port: 22, username: GAMMA_USER,
      privateKey: getSSHKey(), readyTimeout: 10000
    });
  });
}

// Get OAuth token from Vaultwarden API
async function getToken(useOrg = false) {
  if (tokenCache && Date.now() < tokenExpiry && !useOrg) {
    return tokenCache;
  }

  const clientId = useOrg ? VW_ORG_CLIENT_ID : VW_USER_CLIENT_ID;
  const clientSecret = useOrg ? VW_ORG_CLIENT_SECRET : VW_USER_CLIENT_SECRET;
  const scope = useOrg ? 'api.organization' : 'api';

  if (!clientId || !clientSecret) {
    return { error: 'Vaultwarden credentials not configured' };
  }

  return new Promise((resolve) => {
    const url = new URL('/identity/connect/token', VW_BASE_URL);
    const body = `grant_type=client_credentials&client_id=${encodeURIComponent(clientId)}&client_secret=${encodeURIComponent(clientSecret)}&deviceIdentifier=pixel-office-1&scope=${encodeURIComponent(scope)}`;

    const https = require('https');
    const req = https.request({
      hostname: url.hostname,
      port: 443,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(body)
      }
    }, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.access_token) {
            if (!useOrg) {
              tokenCache = parsed.access_token;
              tokenExpiry = Date.now() + (parsed.expires_in - 60) * 1000;
            }
            resolve({ token: parsed.access_token });
          } else {
            resolve({ error: parsed.error || 'No token in response', raw: data.substring(0, 200) });
          }
        } catch (e) {
          resolve({ error: `Parse error: ${e.message}`, raw: data.substring(0, 200) });
        }
      });
    });

    req.on('error', err => resolve({ error: err.message }));
    req.write(body);
    req.end();
  });
}

// Vaultwarden API call
async function vwApi(method, path, body = null, useOrg = false) {
  const tokenResult = await getToken(useOrg);
  if (tokenResult.error) return tokenResult;

  return new Promise((resolve) => {
    const url = new URL(path, VW_BASE_URL);
    const https = require('https');

    const opts = {
      hostname: url.hostname,
      port: 443,
      path: url.pathname + url.search,
      method: method,
      headers: {
        'Authorization': `Bearer ${tokenResult.token}`,
        'Content-Type': 'application/json'
      }
    };

    if (body) {
      opts.headers['Content-Length'] = Buffer.byteLength(JSON.stringify(body));
    }

    const req = https.request(opts, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try {
          if (data.trim()) {
            resolve(JSON.parse(data));
          } else {
            resolve({ success: true, status: res.statusCode });
          }
        } catch (e) {
          resolve({ error: `Parse error: ${e.message}`, raw: data.substring(0, 500), status: res.statusCode });
        }
      });
    });

    req.on('error', err => resolve({ error: err.message }));
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

// Sync vault (get all items)
let syncCache = null;
let syncCacheTime = 0;
const SYNC_CACHE_TTL = 60000; // 1 minute

async function syncVault() {
  if (syncCache && Date.now() - syncCacheTime < SYNC_CACHE_TTL) {
    return syncCache;
  }

  const result = await vwApi('GET', '/api/sync');
  if (result.error) return result;

  syncCache = result;
  syncCacheTime = Date.now();
  return result;
}

// Search vault items
async function searchItems(query, type = null) {
  const sync = await syncVault();
  if (sync.error) return sync;

  let items = sync.Ciphers || [];
  if (type) {
    items = items.filter(i => i.Type === type);
  }

  const q = query.toLowerCase();
  const matches = items.filter(i => {
    const name = (i.Name || '').toLowerCase();
    const notes = (i.Notes || '').toLowerCase();
    const username = i.Login && i.Login.Username ? i.Login.Username.toLowerCase() : '';
    const uris = i.Login && i.Login.Uris ? i.Login.Uris.map(u => (u.Uri || '').toLowerCase()) : [];
    const fields = (i.Fields || []).map(f => (f.Name || '').toLowerCase() + ' ' + (f.Value || '').toLowerCase());

    return name.includes(q) || notes.includes(q) || username.includes(q) ||
           uris.some(u => u.includes(q)) || fields.some(f => f.includes(q));
  });

  return {
    items: matches.map(i => ({
      id: i.Id,
      name: i.Name,
      type: i.Type, // 1=login, 2=secureNote, 3=card, 4=identity
      typeText: ['login', 'secureNote', 'card', 'identity'][i.Type - 1] || 'unknown',
      username: i.Login ? i.Login.Username : null,
      uris: i.Login && i.Login.Uris ? i.Login.Uris.map(u => u.Uri) : [],
      notes: i.Notes ? true : false,
      folderName: i.FolderId ? (sync.Folders || []).find(f => f.Id === i.FolderId)?.Name : null,
      collectionIds: i.CollectionIds || [],
      collectionNames: (i.CollectionIds || []).map(cid => (sync.Collections || []).find(c => c.Id === cid)?.Name).filter(Boolean),
      favorite: i.Favorite,
      revisionDate: i.RevisionDate
    })),
    count: matches.length
  };
}

// Get full item details (including password)
async function getItem(id) {
  const result = await vwApi('GET', `/api/ciphers/${id}`);
  if (result.error) return result;

  const item = result;
  return {
    id: item.Id,
    name: item.Name,
    type: item.Type,
    typeText: ['login', 'secureNote', 'card', 'identity'][item.Type - 1] || 'unknown',
    username: item.Login ? item.Login.Username : null,
    password: item.Login ? item.Login.Password : null,
    uris: item.Login && item.Login.Uris ? item.Login.Uris.map(u => u.Uri) : [],
    notes: item.Notes || '',
    fields: (item.Fields || []).map(f => ({ name: f.Name, value: f.Value, type: f.Type })),
    folderName: null, // would need sync for this
    totp: item.Login && item.Login.Totp ? true : false,
    revisionDate: item.RevisionDate
  };
}

// List folders
async function listFolders() {
  const result = await vwApi('GET', '/api/folders');
  if (result.error) return result;

  if (result.Data) {
    return {
      folders: result.Data.map(f => ({ id: f.Id, name: f.Name })),
      count: result.Data.length
    };
  }
  return { folders: [], count: 0 };
}

// List collections (org)
async function listCollections() {
  const result = await vwApi('GET', '/api/collections', null, false);
  if (result.error) return result;

  if (result.Data) {
    return {
      collections: result.Data.map(c => ({ id: c.Id, name: c.Name, orgId: c.OrganizationId })),
      count: result.Data.length
    };
  }
  return { collections: [], count: 0 };
}

// Get vault status
async function getStatus() {
  return {
    baseUrl: VW_BASE_URL,
    configured: !!(VW_USER_CLIENT_ID && VW_USER_CLIENT_SECRET),
    orgConfigured: !!(VW_ORG_CLIENT_ID && VW_ORG_CLIENT_SECRET),
    tokenCached: !!tokenCache && Date.now() < tokenExpiry
  };
}

module.exports = {
  searchItems,
  getItem,
  listFolders,
  listCollections,
  getStatus,
  syncVault
};
