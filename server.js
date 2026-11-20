const express = require('express');
const path = require('path');
const fs = require('fs');
const dotenv = require('dotenv');
const email = require('./email');
const contacts = require('./contacts');
const vault = require('./vault');
const integrations = require('./integrations');

const envPath = path.join(__dirname, '.env');
if (fs.existsSync(envPath)) {
  dotenv.config({ path: envPath });
} else {
  dotenv.config();
}

const resolveDataDir = (dir) => {
  if (!dir) {
    return path.join(__dirname, 'data');
  }
  return path.isAbsolute(dir) ? dir : path.join(__dirname, dir);
};

const DATA_DIR = resolveDataDir(process.env.PIXEL_DATA_DIR);
fs.mkdirSync(DATA_DIR, { recursive: true });

const DASHBOARD_PASSWORD = process.env.DASHBOARD_PASSWORD || 'pixeladmin';

// LiteLLM API configuration (OpenAI-compatible)
const LITELLM_API_URL = process.env.LITELLM_API_URL || 'https://litellm.blacktech.dev';
const LITELLM_API_KEY = process.env.LITELLM_API_KEY || '';
const LITELLM_MODEL = process.env.LITELLM_MODEL || 'glm-5.3-flash';

const dataPath = (filename) => path.join(DATA_DIR, filename);
const CONFIG_PATH = dataPath('pixel-config.json');
const AGENTS_PATH = dataPath('agents.json');
const LOG_PATH = dataPath('pixel_actions.jsonl');
const MAP_PATH = dataPath('map.json');
const COLLISION_PATH = dataPath('pixel_collision.json');
const ROOMS_PATH = dataPath('pixel_rooms.json');
const agentMessagePath = (id) => dataPath(`agent_${id}_message.txt`);
const ARRIVED_OFFICE_PATH = dataPath('pep_arrived_office');
const ARRIVED_CONCIERGE_PATH = dataPath('pep_arrived_concierge');

const readJSONFile = (filePath) => {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (error) {
    return null;
  }
};

const writeJSONFile = (filePath, data) => {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
};

const loadAgentsFromDisk = () => {
  const agentsData = readJSONFile(AGENTS_PATH);
  if (Array.isArray(agentsData) && agentsData.length) {
    return agentsData;
  }
  const legacyConfig = readJSONFile(CONFIG_PATH);
  if (legacyConfig && Array.isArray(legacyConfig.agents)) {
    return legacyConfig.agents;
  }
  return null;
};

const persistAgents = (agents) => {
  if (Array.isArray(agents)) {
    writeJSONFile(AGENTS_PATH, agents);
  }
};

const loadMapData = () => {
  const mapData = readJSONFile(MAP_PATH);
  if (mapData) {
    return mapData;
  }
  return {
    collision: readJSONFile(COLLISION_PATH),
    rooms: readJSONFile(ROOMS_PATH)
  };
};

const persistMapData = (updates = {}) => {
  const current = loadMapData() || {};
  const merged = {
    ...current,
    ...updates,
    updatedAt: new Date().toISOString()
  };
  writeJSONFile(MAP_PATH, merged);
  if (merged.rooms) {
    writeJSONFile(ROOMS_PATH, merged.rooms);
  }
  if (merged.collision) {
    writeJSONFile(COLLISION_PATH, merged.collision);
  }
  return merged;
};

const app = express();
const PORT = parseInt(process.env.PORT, 10) || 19000;

app.use(express.json());
app.use(express.static(path.join(__dirname)));

// Initial config: all agents available, activated based on checks
let config = {
  agents: [
    { id: 0, name: "Curator", role: "Archivist", room: "Archives", color: 0, x: 320, y: 680, state: "idle", active: true },
    { id: 2, name: "Charon", role: "Concierge", room: "Reception", color: 2, x: 320, y: 220, state: "idle", active: true },
    { id: 3, name: "Wardog", role: "Security Chief", room: "Workstations", color: 3, x: 180, y: 440, state: "idle", active: true },
    { id: 4, name: "Fixer", role: "Maintenance", room: "Workstations", color: 4, x: 320, y: 440, state: "idle", active: true },
    { id: 5, name: "Tailor", role: "Attendant", room: "Workstations", color: 5, x: 460, y: 440, state: "idle", active: true },
    { id: 6, name: "Ghostface", role: "Owner", room: "Reception", color: 6, x: 420, y: 180, state: "idle", active: true }
  ],
  rooms: [
    { name: "Reception", x: 320, y: 220 },
    { name: "Workstations", x: 320, y: 440 },
    { name: "Archives", x: 320, y: 680 }
  ]
};

const defaultAgents = JSON.parse(JSON.stringify(config.agents));
const defaultRooms = JSON.parse(JSON.stringify(config.rooms));

// Load saved configuration
try {
  const storedAgents = loadAgentsFromDisk();
  if (storedAgents) {
    // Migration: drop placeholder "Off Duty" agents; ensure Ghostface (Owner) exists
    let migrated = storedAgents.filter(a => a.name !== 'Off Duty');
    if (!migrated.some(a => a.name === 'Ghostface')) {
      migrated.push(JSON.parse(JSON.stringify(defaultAgents.find(a => a.name === 'Ghostface'))));
    }
    config.agents = migrated;
    persistAgents(config.agents);
    console.log('Agents loaded from disk (migrated)');
  } else if (fs.existsSync(CONFIG_PATH)) {
    const savedConfig = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
    if (Array.isArray(savedConfig.agents)) {
      config.agents = savedConfig.agents;
    }
    if (Array.isArray(savedConfig.rooms)) {
      config.rooms = savedConfig.rooms;
    }
    persistAgents(config.agents);
    console.log('Configuration loaded (legacy)');
  } else {
    console.log('Using initial configuration');
  }
} catch (e) {
  console.log('Using initial configuration');
}

const initialMapData = loadMapData() || {};
if (Array.isArray(initialMapData.rooms) && initialMapData.rooms.length) {
  config.rooms = initialMapData.rooms;
} else if (!Array.isArray(initialMapData.rooms)) {
  initialMapData.rooms = defaultRooms;
}
if (!fs.existsSync(MAP_PATH)) {
  persistMapData({
    rooms: initialMapData.rooms,
    collision: initialMapData.collision || null
  });
}

if (!fs.existsSync(AGENTS_PATH)) {
  persistAgents(config.agents);
}

app.get('/api/config', (req, res) => {
  res.json({
    agents: config.agents,
    rooms: config.rooms
  });
});

// LiteLLM AI proxy endpoint — OpenAI-compatible, no client API keys needed
app.post('/api/ai/chat', async (req, res) => {
  try {
    const { prompt, systemPrompt } = req.body || {};
    if (!prompt) {
      return res.status(400).json({ error: 'Missing prompt' });
    }

    // If the prompt mentions status/briefing, inject real data as context
    const lowerPrompt = (prompt || '').toLowerCase();
    const isBriefing = lowerPrompt.includes('status') || lowerPrompt.includes('briefing') || lowerPrompt.includes('overview') || lowerPrompt.includes('report');
    let briefingContext = '';
    if (isBriefing) {
      try {
        const accounts = email.getAccountsList();
        const emailLines = accounts.map(a => `  - ${a.name} (${a.email}): ${a.configured ? 'connected' : 'not configured'}`).join('\n');
        const agentLines = (config.agents || []).map(a => `  - ${a.name}: ${a.role} in ${a.room || 'off duty'}`).join('\n');
        const configured = accounts.filter(a => a.configured).length;
        briefingContext = `\n\nCURRENT SYSTEM DATA:\nEmail: ${configured}/${accounts.length} accounts connected\n${emailLines}\n\nAgents on duty:\n${agentLines}\n\nVault: connected to bw.theblacktech.com\nAI: running on ${LITELLM_MODEL} via LiteLLM`;
      } catch(e) { /* ignore briefing context errors */ }
    }

    // Use client-provided system prompt if present; otherwise use a general office context
    const defaultContext = `You are the AI Director of Nocturnal Inc Pixel Office. Keep responses brief.`;
    const fullSystemPrompt = systemPrompt
      ? `${systemPrompt}${briefingContext}`
      : `${defaultContext}${briefingContext}`;

    const litellmResponse = await fetch(`${LITELLM_API_URL}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${LITELLM_API_KEY}`
      },
      body: JSON.stringify({
        model: LITELLM_MODEL,
        messages: [
          { role: 'system', content: fullSystemPrompt },
          { role: 'user', content: prompt }
        ],
        stream: false,
        max_tokens: 2048
      })
    });

    if (!litellmResponse.ok) {
      const errText = await litellmResponse.text();
      console.error('LiteLLM API error:', litellmResponse.status, errText);
      return res.status(502).json({ error: `LiteLLM API error: ${litellmResponse.status}` });
    }

    const data = await litellmResponse.json();
    const content = data.choices?.[0]?.message?.content || '';
    res.json({ response: content, model: data.model || LITELLM_MODEL });
  } catch (err) {
    console.error('AI chat proxy error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

// LiteLLM model info endpoint
app.get('/api/ai/status', async (req, res) => {
  try {
    const response = await fetch(`${LITELLM_API_URL}/v1/models`, {
      headers: { 'Authorization': `Bearer ${LITELLM_API_KEY}` }
    });
    if (!response.ok) throw new Error(`LiteLLM API returned ${response.status}`);
    const data = await response.json();
    res.json({
      available: true,
      url: LITELLM_API_URL,
      model: LITELLM_MODEL,
      models: (data.data || []).map(m => m.id)
    });
  } catch (err) {
    res.json({
      available: false,
      url: LITELLM_API_URL,
      model: LITELLM_MODEL,
      error: err.message
    });
  }
});

console.log('Dashboard auth route ready');
app.post('/api/auth/login', (req, res) => {
  const { password } = req.body || {};
  if (!DASHBOARD_PASSWORD) {
    return res.json({ success: true });
  }
  if (password && password === DASHBOARD_PASSWORD) {
    return res.json({ success: true });
  }
  return res.status(401).json({ success: false });
});

app.post('/api/config', (req, res) => {
  config = req.body || {};
  if (!Array.isArray(config.agents)) {
    config.agents = defaultAgents;
  }
  if (!Array.isArray(config.rooms)) {
    config.rooms = defaultRooms;
  }
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2));
  persistAgents(config.agents);
  persistMapData({ rooms: config.rooms });
  console.log('Configuration saved');
  res.json({ success: true, config });
});

app.post('/api/agent/:id/move', (req, res) => {
  const id = parseInt(req.params.id);
  const { x, y, state } = req.body;
  const agent = config.agents.find(a => a.id === id);
  if (agent) {
    if (x !== undefined) agent.x = x;
    if (y !== undefined) agent.y = y;
    if (state) agent.state = state;
    console.log(`[${agent.name}] Move to (${x}, ${y})`);
    res.json({ success: true, agent });
  } else {
    res.status(404).json({ error: 'Agent not found' });
  }
});

// API to get action log
app.get('/api/log', (req, res) => {
  try {
    const logData = fs.readFileSync(LOG_PATH, 'utf8')
      .split('\n')
      .filter(line => line.trim())
      .map(line => JSON.parse(line))
      .slice(-50);
    res.json(logData);
  } catch (e) {
    res.json([]);
  }
});

// API to clear log
app.post('/api/log/clear', (req, res) => {
  try {
    fs.writeFileSync(LOG_PATH, '');
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Status briefing — aggregates real data, no AI dependency
app.get('/api/briefing', async (req, res) => {
  const briefing = {
    timestamp: new Date().toISOString(),
    organization: 'Nocturnal Inc',
    email: { accounts: [], totalConfigured: 0, totalAccounts: 0, totalUnread: 0 },
    vault: { configured: false },
    contacts: { total: 0, organizations: 0 },
    ai: { available: false, model: LITELLM_MODEL },
    agents: []
  };

  // Email accounts + unread counts
  try {
    const accounts = email.getAccountsList();
    briefing.email.totalAccounts = accounts.length;
    for (const acct of accounts) {
      briefing.email.accounts.push({
        id: acct.id, name: acct.name, email: acct.email,
        icon: acct.icon, category: acct.category,
        configured: acct.configured, unread: null
      });
      if (acct.configured) briefing.email.totalConfigured++;
    }
  } catch (e) {
    briefing.email.error = e.message;
  }

  // Vault status
  try {
    briefing.vault = await vault.getStatus();
  } catch (e) {
    briefing.vault = { configured: false, error: e.message };
  }

  // Contact counts
  try {
    const syncStatus = contacts.getSyncStatus();
    briefing.contacts = {
      total: syncStatus.totalContacts || 0,
      organizations: syncStatus.totalOrganizations || 0,
      lastSync: syncStatus.lastSync || null
    };
  } catch (e) {
    briefing.contacts = { error: e.message };
  }

  // AI/LiteLLM status
  try {
    const aiRes = await fetch(`${LITELLM_API_URL}/v1/models`, {
      headers: { 'Authorization': `Bearer ${LITELLM_API_KEY}` },
      signal: AbortSignal.timeout(3000)
    });
    if (aiRes.ok) {
      const aiData = await aiRes.json();
      briefing.ai = {
        available: true,
        model: LITELLM_MODEL,
        models: (aiData.data || []).map(m => m.id)
      };
    }
  } catch (e) {
    briefing.ai = { available: false, model: LITELLM_MODEL, error: e.message };
  }

  // Agent roster
  briefing.agents = (config.agents || []).map(a => ({
    id: a.id, name: a.name, role: a.role, room: a.room, state: a.state
  }));

  res.json(briefing);
});

// AI-generated Nocturnal briefing — Charon delivers a natural language status report
app.get('/api/briefing/ai', async (req, res) => {
  try {
    // Gather briefing data (reuse the same logic)
    const briefing = {
      timestamp: new Date().toISOString(),
      organization: 'Nocturnal Inc',
      email: { accounts: [], totalConfigured: 0, totalAccounts: 0, totalUnread: 0 },
      vault: { configured: false },
      contacts: { total: 0, organizations: 0 },
      ai: { available: false, model: LITELLM_MODEL },
      agents: []
    };

    try {
      const accounts = email.getAccountsList();
      briefing.email.totalAccounts = accounts.length;
      for (const acct of accounts) {
        briefing.email.accounts.push({
          id: acct.id, name: acct.name, email: acct.email,
          icon: acct.icon, category: acct.category,
          configured: acct.configured, unread: null
        });
        if (acct.configured) briefing.email.totalConfigured++;
      }
    } catch (e) { briefing.email.error = e.message; }

    try {
      briefing.vault = await vault.getStatus();
    } catch (e) { briefing.vault = { configured: false, error: e.message }; }

    try {
      const syncStatus = contacts.getSyncStatus();
      briefing.contacts = {
        total: syncStatus.totalContacts || 0,
        organizations: syncStatus.totalOrganizations || 0,
        lastSync: syncStatus.lastSync || null
      };
    } catch (e) { briefing.contacts = { error: e.message }; }

    try {
      const aiRes = await fetch(`${LITELLM_API_URL}/v1/models`, {
        headers: { 'Authorization': `Bearer ${LITELLM_API_KEY}` },
        signal: AbortSignal.timeout(3000)
      });
      if (aiRes.ok) {
        const aiData = await aiRes.json();
        briefing.ai = { available: true, model: LITELLM_MODEL, models: (aiData.data || []).map(m => m.id) };
      }
    } catch (e) { briefing.ai = { available: false, model: LITELLM_MODEL, error: e.message }; }

    briefing.agents = (config.agents || []).map(a => ({
      id: a.id, name: a.name, role: a.role, room: a.room, state: a.state
    }));

    // Build the prompt for Charon's briefing
    const agentRoster = briefing.agents.map(a => `${a.name} (${a.role}) — ${a.state} in ${a.room}`).join('; ');
    const emailSummary = briefing.email.accounts.map(a => `${a.name} (${a.email}): ${a.configured ? 'configured' : 'not configured'}`).join('; ');
    const time = new Date().toLocaleString('en-US', { timeZone: 'America/New_York', weekday: 'long', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' });

    const systemPrompt = `You are Charon, the control-plane agent and concierge of Nocturnal Inc's virtual office. You are delivering a comprehensive morning briefing to Jb, the operator. Be professional, personable, and thorough — like a chief of staff briefing the CEO of a small conglomerate. Cover:

1. Time and date with operating-hours context (Nocturnal is a night-shift operation)
2. Agent roster status (who's on duty, their roles, where they are, any anomalies). Ghostface is the Owner — Charon reports to Ghostface. Ghostface handles owner email (jb@theblacktech.com).
3. Business entity overview — Nocturnal Innovations (parent), with sub-entities: Bethea Brothers (real estate), Tercum LLC (consulting), JCB Equity (investments/dividends)
4. Products & Services portfolio:
   - NocturnalPost: Newsletter/publication and email filtering/scrubbing service for clients (rua@nocturnalpost.com)
   - NightChute: Internal email notification service managing notifications across all domains hosted by nocturnalinc.com
5. Hosted domains status (mail2.nocturnalinc.com / Mailcow): nocturnalinc.com, betheabrothers.com, tercumllc.com, nocturnalpost.com, theblacktech.com, blacktech.dev
6. Email accounts status (11 accounts: 2 owner + 9 operational across hosted domains). Ghostface handles owner inboxes: jb@theblacktech.com (11,600+ messages) and jon@j-johnson.com (JCB Equity). Charon triages and routes from there.
7. Infrastructure highlights: gamma k3s cluster, delta (media/arr services), LiteLLm AI inference, OpenProject (op.nocturnalinc.com), Odoo ERP, Paperless document mgmt, Vaultwarden, Grafana monitoring, rustfs/S3 storage, ChromaDB vectors
8. Vault status (Vaultwarden)
9. Contacts database status (CRM)
10. AI system status (LiteLLM models)
11. OpenProject status — Nocturnal Innovations (ID 5) with 4 sub-projects: Nocturnal Corporate (ID 9), Nocturnal Products (ID 10), assylummadetrack (ID 6), mchenryteam-realestate (ID 7)
12. Any items needing attention, risks, or recommendations

Aim for 400-600 words. Use natural prose with clear section transitions, not bullet points. Sign off as Charon.`;

    const userPrompt = `Current time: ${time}
Organization: Nocturnal Innovations (parent company)
Operating hours: Night-shift (Nocturnal operates primarily during overnight hours)

=== AGENT ROSTER ===
Agents on duty:
${agentRoster}

=== BUSINESS ENTITIES ===
Nocturnal Innovations — Parent company, operations management, customer service
  Sub-entities:
  - Bethea Brothers — Real estate operations
  - Tercum LLC — Consulting services
  - JCB Equity — Investment portfolio (dividend income for UBI project, ~$76/mo from 12 positions)

=== PRODUCTS & SERVICES ===
NocturnalPost — Newsletter/publication platform and email filtering/scrubbing service for clients. Email: rua@nocturnalpost.com. Status: active.
NightChute — Internal email notification service managing email notifications for all domains hosted by nocturnalinc.com. Status: operational.

=== HOSTED DOMAINS (mail2.nocturnalinc.com / Mailcow) ===
- nocturnalinc.com — Primary business domain
- betheabrothers.com — Real estate domain
- tercumllc.com — Consulting domain
- nocturnalpost.com — Publication/filtering service domain
- theblacktech.com — Internal infrastructure (Vaultwarden, GitLab, Nextcloud, Immich)
- blacktech.dev — Internal services (Mattermost, Paperless, Odoo, rustfs, Grafana, HA)

=== EMAIL ACCOUNTS ===
Email accounts (${briefing.email.totalConfigured}/${briefing.email.totalAccounts} configured):
${emailSummary}
${briefing.email.error ? 'Email error: ' + briefing.email.error : ''}

=== VAULT ===
Vault: ${briefing.vault.configured ? 'Configured' : 'Not configured'}${briefing.vault.orgConfigured ? ' (org connected)' : ''}${briefing.vault.error ? ' — error: ' + briefing.vault.error : ''}
(Vaultwarden: 782 ciphers, 60 folders)

=== CONTACTS (CRM) ===
Contacts: ${briefing.contacts.total} contacts, ${briefing.contacts.organizations} organizations${briefing.contacts.error ? ' — error: ' + briefing.contacts.error : ''}

=== AI SYSTEMS ===
AI: ${briefing.ai.available ? 'Online (' + briefing.ai.model + ', ' + (briefing.ai.models || []).length + ' models available)' : 'Offline'}${briefing.ai.error ? ' — error: ' + briefing.ai.error : ''}
(LiteLLM proxy at litellm.blacktech.dev, models include: glm-5.2, glm-5.3, glm-5.3-flash, deepseek-v4-pro, kimi-k2.7-code, nemotron-3-ultra, llama3.2, llama3.2-gamma, nomic-embed-text, deepseek-v4.1-flash)

=== INFRASTRUCTURE ===
- gamma (192.168.15.230): k3s cluster, LiteLLM, rustfs/S3, ChromaDB, Rundeck, Prowlarr
- delta (192.168.15.207): Radarr, Sonarr, Lidarr, qBittorrent
- alpha (192.168.15.75): auxiliary services
- OpenProject (op.nocturnalinc.com): Project management, 3 projects + 4 sub-projects
- Odoo (odoo.blacktech.dev): ERP, invoicing, partner management
- Paperless (paperless.blacktech.dev): Document management
- Vaultwarden (bw.theblacktech.com): Password/secrets management
- Grafana: Monitoring and dashboards
- Graylog: Centralized logging
- Mattermost (mm.blacktech.dev): Team communications
- GitLab: Code repositories
- Nextcloud: File collaboration
- Immich: Photo management

=== OPENPROJECT STRUCTURE ===
Nocturnal Innovations (ID 5, parent) with 4 sub-projects:
  - Nocturnal Corporate (ID 9, nocturnal-corp) — corp tasks, admin, compliance, business ops
  - Nocturnal Products (ID 10, nocturnal-products) — product dev: NocturnalPost, NightChute
  - assylummadetrack (ID 6) — legacy project
  - mchenryteam-realestate (ID 7) — real estate tracking
Also: Bethea Brothers (separate project), JCB Equity (separate project)

Deliver the briefing.`;

    const aiRes = await fetch(`${LITELLM_API_URL}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${LITELLM_API_KEY}`
      },
      body: JSON.stringify({
        model: LITELLM_MODEL,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt }
        ],
        temperature: 0.7,
        max_tokens: 4000
      }),
      signal: AbortSignal.timeout(30000)
    });

    if (!aiRes.ok) {
      const errText = await aiRes.text();
      return res.status(502).json({ error: 'LiteLLM error', status: aiRes.status, detail: errText });
    }

    const aiData = await aiRes.json();
    const choice = aiData.choices?.[0]?.message;
    // Reasoning models (e.g. glm-5.3-flash) may put output in reasoning_content
    // when max_tokens is too low. Prefer content, fall back to reasoning_content.
    const briefingText = choice?.content || choice?.reasoning_content || 'No response from AI.';

    res.json({
      briefing: briefingText,
      model: LITELLM_MODEL,
      timestamp: briefing.timestamp,
      rawData: briefing
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API to get agent commands (movements)
const agentCommands = {};
const commandTimestamps = {};

app.get('/api/agent/:id/command', (req, res) => {
  const id = parseInt(req.params.id);
  const cmd = agentCommands[id];
  
  // If command exists and is less than 30 seconds old, return and consume it immediately
  if (cmd && commandTimestamps[id]) {
    const age = Date.now() - commandTimestamps[id];
    if (age < 30000) { // Command valid for 30 seconds
      // Consume immediately to prevent other browsers from reading it
      agentCommands[id] = null;
      commandTimestamps[id] = null;
      return res.json(cmd);
    } else {
      // Command expired, clean up
      agentCommands[id] = null;
      commandTimestamps[id] = null;
    }
  }
  res.json(null);
});

// Endpoint to confirm agent physically arrived at destination
app.post('/api/agent/:id/arrived', (req, res) => {
  const id = parseInt(req.params.id);
  const { location } = req.body;
  
  // Create signaling file for the controller
  if (location === 'office') {
    fs.writeFileSync(ARRIVED_OFFICE_PATH, '1');
  } else if (location === 'concierge') {
    fs.writeFileSync(ARRIVED_CONCIERGE_PATH, '1');
  }
  
  console.log(`[Arrival] Agent ${id} arrived at: ${location}`);
  res.json({ success: true });
});
app.post('/api/agent/:id/command/ack', (req, res) => {
  const id = parseInt(req.params.id);
  agentCommands[id] = null;
  commandTimestamps[id] = null;
  res.json({ success: true });
});

app.post('/api/agent/:id/command', (req, res) => {
  const id = parseInt(req.params.id);
  agentCommands[id] = req.body;
  commandTimestamps[id] = Date.now();
  console.log(`[Command] Agent ${id}:`, req.body);
  res.json({ success: true });
});
app.get('/api/messages', (req, res) => {
  const messages = {};
  for (let i = 0; i < 6; i++) {
    try {
      messages[i] = fs.readFileSync(agentMessagePath(i), 'utf8');
    } catch (e) {
      messages[i] = "";
    }
  }
  res.json(messages);
});

// === Agent runtime presence (Hermes + OpenClaw) ===

// Live roster of real agent runtimes; read-only, cached 5s in integrations.js
app.get('/api/presence', async (req, res) => {
  try {
    res.json(await integrations.getPresence());
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// API to save collision map
app.post('/api/collision', (req, res) => {
  try {
    persistMapData({ collision: req.body });
    console.log('Collision map saved');
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// API to save rooms
app.post('/api/rooms', (req, res) => {
  try {
    const updated = persistMapData({ rooms: req.body });
    if (Array.isArray(updated.rooms)) {
      config.rooms = updated.rooms;
    }
    console.log('Rooms saved');
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});
app.get('/api/collision', (req, res) => {
  try {
    const mapData = loadMapData();
    if (!mapData || !mapData.collision) {
      throw new Error('Map not available');
    }
    res.json(mapData.collision);
  } catch (e) {
    res.status(500).json({ error: e.message || 'Map not available' });
  }
});

// API to get rooms
app.get('/api/rooms', (req, res) => {
  try {
    const mapData = loadMapData();
    if (mapData && Array.isArray(mapData.rooms)) {
      return res.json(mapData.rooms);
    }
  } catch (e) {
    // ignore and fallback below
  }
  res.json(config.rooms.map(r => ({ name: r.name, x: r.x, y: r.y, tiles: [] })));
});

// === Contacts API (CRM) ===

// Search contacts
app.get('/api/contacts/search', (req, res) => {
  try {
    const term = req.query.q || '';
    const limit = parseInt(req.query.limit) || 20;
    const results = contacts.searchContacts(term, limit);
    res.json({ results, count: results.length });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get contact by ID
app.get('/api/contacts/:id', (req, res) => {
  try {
    const contact = contacts.getContact(req.params.id);
    if (!contact) return res.status(404).json({ error: 'Contact not found' });
    res.json(contact);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get contact interactions
app.get('/api/contacts/:id/interactions', (req, res) => {
  try {
    const interactions = contacts.getInteractions(req.params.id);
    res.json({ interactions, count: interactions.length });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Search organizations
app.get('/api/orgs/search', (req, res) => {
  try {
    const term = req.query.q || '';
    const limit = parseInt(req.query.limit) || 20;
    const results = contacts.searchOrganizations(term, limit);
    res.json({ results, count: results.length });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Sync status across all platforms
app.get('/api/sync/status', (req, res) => {
  try {
    const status = contacts.getSyncStatus();
    res.json(status);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// === Email API ===

// Get accounts list (metadata only, no passwords)
app.get('/api/email/accounts', (req, res) => {
  res.json({
    accounts: email.getAccountsList(),
    categories: email.CATEGORIES
  });
});

// Get unread counts for all accounts (batch)
app.get('/api/email/unread/all', async (req, res) => {
  try {
    const results = await email.getAllUnreadCounts();
    res.json(results);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get unread count for a specific account (fast polling)
app.get('/api/email/unread', async (req, res) => {
  try {
    const accountId = req.query.account || null;
    const result = await email.getUnreadCount('INBOX', accountId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message, unread: 0 });
  }
});

// List inbox emails for a specific account
app.get('/api/email/inbox', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 20;
    const folder = req.query.folder || 'INBOX';
    const accountId = req.query.account || null;
    const result = await email.listInbox(limit, folder, accountId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get full email by ID
app.get('/api/email/:id', async (req, res) => {
  try {
    const folder = req.query.folder || 'INBOX';
    const accountId = req.query.account || null;
    const result = await email.getEmail(req.params.id, folder, accountId);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Send email
app.post('/api/email/send', async (req, res) => {
  try {
    const { to, subject, body, account } = req.body || {};
    if (!to || !subject) {
      return res.status(400).json({ error: 'Missing to or subject' });
    }
    const result = await email.sendEmail(to, subject, body || '', account || null);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// === Vaultwarden API ===

// Get vault status
app.get('/api/vault/status', async (req, res) => {
  try {
    const status = await vault.getStatus();
    res.json(status);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Search vault items
app.get('/api/vault/search', async (req, res) => {
  try {
    const query = req.query.q || '';
    const type = req.query.type ? parseInt(req.query.type) : null;
    if (!query) {
      return res.json({ items: [], count: 0 });
    }
    const result = await vault.searchItems(query, type);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get full item details
app.get('/api/vault/item/:id', async (req, res) => {
  try {
    const result = await vault.getItem(req.params.id);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// List folders
app.get('/api/vault/folders', async (req, res) => {
  try {
    const result = await vault.listFolders();
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// List collections
app.get('/api/vault/collections', async (req, res) => {
  try {
    const result = await vault.listCollections();
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.use((req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Pixel Office v3 on http://0.0.0.0:${PORT}`);
  console.log('Active agents:', config.agents.filter(a => a.active).map(a => a.name).join(', '));
  console.log(`LiteLLM API: ${LITELLM_API_URL} (model: ${LITELLM_MODEL})`);
});
