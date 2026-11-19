const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// CRM database path — copied to /tmp for sqlite3 access
const CRM_DB_SOURCE = process.env.CRM_DB_PATH || '/home/node/.openclaw/workspace/crm/crm.db';
const CRM_DB_TMP = '/tmp/crm_pixel_copy.db';
const SQLITE3 = process.env.SQLITE3_PATH || '/home/node/.openclaw/bin/sqlite3';
const SYNC_STATE_PATH = process.env.SYNC_STATE_PATH || '/home/node/.openclaw/workspace/crm/unified-sync-state.json';

// Copy CRM DB to tmp for querying (sqlite3 can't open files under OPENCLAW_STATE_DIR)
function ensureFreshDb() {
  try {
    if (!fs.existsSync(CRM_DB_TMP) || isStale(CRM_DB_TMP, CRM_DB_SOURCE)) {
      fs.copyFileSync(CRM_DB_SOURCE, CRM_DB_TMP);
    }
    return CRM_DB_TMP;
  } catch (e) {
    return null;
  }
}

function isStale(tmp, src) {
  try {
    const tmpStat = fs.statSync(tmp);
    const srcStat = fs.statSync(src);
    return srcStat.mtimeMs > tmpStat.mtimeMs;
  } catch {
    return true;
  }
}

function query(sql) {
  const db = ensureFreshDb();
  if (!db) return '';
  try {
    const escaped = sql.replace(/'/g, "'\\''");
    const output = execSync(`${SQLITE3} "${db}" "${escaped}"`, { encoding: 'utf8', timeout: 5000 });
    return output.trim();
  } catch (e) {
    return '';
  }
}

// Load unified sync state to see which platforms each contact is on
function loadSyncState() {
  try {
    return JSON.parse(fs.readFileSync(SYNC_STATE_PATH, 'utf8'));
  } catch {
    return { contacts: {}, organizations: {}, lastSync: null };
  }
}

// Search contacts by name, email, or organization
function searchContacts(term, limit = 20) {
  if (!term || term.length < 2) return [];
  
  const escapedTerm = term.replace(/'/g, "''");
  const sql = `
    SELECT DISTINCT
      c.id, c.display_name, c.first_name, c.last_name, c.type, c.status, c.source,
      GROUP_CONCAT(e.email, '||') as emails,
      GROUP_CONCAT(p.phone, '||') as phones,
      GROUP_CONCAT(o.name, '||') as orgs
    FROM contacts c
    LEFT JOIN contact_emails e ON c.id = e.contact_id
    LEFT JOIN contact_phones p ON c.id = p.contact_id
    LEFT JOIN contact_organizations co ON c.id = co.contact_id
    LEFT JOIN organizations o ON co.organization_id = o.id
    WHERE c.status = 'active'
      AND (
        c.display_name LIKE '%${escapedTerm}%'
        OR c.first_name LIKE '%${escapedTerm}%'
        OR c.last_name LIKE '%${escapedTerm}%'
        OR e.email LIKE '%${escapedTerm}%'
        OR o.name LIKE '%${escapedTerm}%'
      )
    GROUP BY c.id
    LIMIT ${parseInt(limit) || 20}
  `;
  
  const raw = query(sql);
  if (!raw) return [];
  
  return raw.split('\n').filter(Boolean).map(line => {
    const parts = line.split('|');
    return {
      id: parseInt(parts[0]) || 0,
      displayName: parts[1] || '',
      firstName: parts[2] || '',
      lastName: parts[3] || '',
      type: parts[4] || 'person',
      status: parts[5] || 'active',
      source: parts[6] || '',
      emails: parts[7] ? parts[7].split('||').filter(Boolean) : [],
      phones: parts[8] ? parts[8].split('||').filter(Boolean) : [],
      organizations: parts[9] ? parts[9].split('||').filter(Boolean) : []
    };
  });
}

// Get a single contact by ID with full details
function getContact(id) {
  const numId = parseInt(id);
  if (!numId) return null;
  
  const sql = `
    SELECT
      c.id, c.display_name, c.first_name, c.last_name, c.type, c.status, c.source, c.notes,
      c.created_at, c.updated_at,
      GROUP_CONCAT(e.email || '::' || e.label || '::' || e.is_primary, '||') as emails,
      GROUP_CONCAT(p.phone || '::' || p.label, '||') as phones,
      GROUP_CONCAT(o.id || '::' || o.name, '||') as orgs
    FROM contacts c
    LEFT JOIN contact_emails e ON c.id = e.contact_id
    LEFT JOIN contact_phones p ON c.id = p.contact_id
    LEFT JOIN contact_organizations co ON c.id = co.contact_id
    LEFT JOIN organizations o ON co.organization_id = o.id
    WHERE c.id = ${numId}
    GROUP BY c.id
  `;
  
  const raw = query(sql);
  if (!raw) return null;
  
  const parts = raw.split('|');
  const contact = {
    id: parseInt(parts[0]) || 0,
    displayName: parts[1] || '',
    firstName: parts[2] || '',
    lastName: parts[3] || '',
    type: parts[4] || 'person',
    status: parts[5] || 'active',
    source: parts[6] || '',
    notes: parts[7] || '',
    createdAt: parts[8] || '',
    updatedAt: parts[9] || '',
    emails: [],
    phones: [],
    organizations: [],
    platforms: {}
  };
  
  if (parts[10]) {
    contact.emails = parts[10].split('||').filter(Boolean).map(e => {
      const [email, label, isPrimary] = e.split('::');
      return { email, label, isPrimary: isPrimary === '1' };
    });
  }
  if (parts[11]) {
    contact.phones = parts[11].split('||').filter(Boolean).map(p => {
      const [phone, label] = p.split('::');
      return { phone, label };
    });
  }
  if (parts[12]) {
    contact.organizations = parts[12].split('||').filter(Boolean).map(o => {
      const [orgId, name] = o.split('::');
      return { id: parseInt(orgId), name };
    });
  }
  
  // Add platform presence from sync state
  const syncState = loadSyncState();
  const primaryEmail = contact.emails.find(e => e.isPrimary)?.email || contact.emails[0]?.email;
  if (primaryEmail && syncState.contacts[primaryEmail.toLowerCase()]) {
    const mapping = syncState.contacts[primaryEmail.toLowerCase()];
    contact.platforms = {
      crm: { id: contact.id, present: true },
      odoo: mapping.odooId ? { id: mapping.odooId, present: true } : { present: false },
      openproject: mapping.openprojectId ? { id: mapping.openprojectId, present: true } : { present: false },
      nextcloud: mapping.nextcloudUid ? { id: mapping.nextcloudUid, present: true } : { present: false },
      paperless: mapping.paperlessId ? { id: mapping.paperlessId, present: true } : { present: false }
    };
  } else {
    contact.platforms = {
      crm: { id: contact.id, present: true },
      odoo: { present: false },
      openproject: { present: false },
      nextcloud: { present: false },
      paperless: { present: false }
    };
  }
  
  return contact;
}

// List recent interactions for a contact
function getInteractions(contactId, limit = 10) {
  const numId = parseInt(contactId);
  if (!numId) return [];
  
  const sql = `
    SELECT id, type, summary, details, interaction_date, follow_up_date, follow_up_completed
    FROM interactions WHERE contact_id = ${numId}
    ORDER BY interaction_date DESC
    LIMIT ${parseInt(limit) || 10}
  `;
  
  const raw = query(sql);
  if (!raw) return [];
  
  return raw.split('\n').filter(Boolean).map(line => {
    const parts = line.split('|');
    return {
      id: parseInt(parts[0]) || 0,
      type: parts[1] || '',
      summary: parts[2] || '',
      details: parts[3] || '',
      date: parts[4] || '',
      followUpDate: parts[5] || '',
      followUpCompleted: parts[6] === '1'
    };
  });
}

// Get sync status summary
function getSyncStatus() {
  const syncState = loadSyncState();
  const contactCount = query(`SELECT COUNT(*) FROM contacts WHERE status='active';`);
  const orgCount = query(`SELECT COUNT(*) FROM organizations;`);
  const withEmail = query(`SELECT COUNT(DISTINCT contact_id) FROM contact_emails;`);
  
  // Count platform mappings
  const contacts = syncState.contacts || {};
  let odooMapped = 0, opMapped = 0, ncMapped = 0, plMapped = 0;
  Object.values(contacts).forEach(m => {
    if (m.odooId) odooMapped++;
    if (m.openprojectId) opMapped++;
    if (m.nextcloudUid) ncMapped++;
    if (m.paperlessId) plMapped++;
  });
  
  return {
    lastSync: syncState.lastSync || null,
    crm: {
      contacts: parseInt(contactCount) || 0,
      organizations: parseInt(orgCount) || 0,
      withEmail: parseInt(withEmail) || 0
    },
    mappings: {
      odoo: odooMapped,
      openproject: opMapped,
      nextcloud: ncMapped,
      paperless: plMapped,
      total: Object.keys(contacts).length
    },
    organizations: Object.keys(syncState.organizations || {}).length
  };
}

// List organizations
function searchOrganizations(term, limit = 20) {
  if (!term || term.length < 2) return [];
  
  const escapedTerm = term.replace(/'/g, "''");
  const sql = `
    SELECT o.id, o.name, o.type,
      GROUP_CONCAT(c.display_name, '||') as contacts,
      COUNT(co.contact_id) as contact_count
    FROM organizations o
    LEFT JOIN contact_organizations co ON o.id = co.organization_id
    LEFT JOIN contacts c ON co.contact_id = c.id AND c.status = 'active'
    WHERE o.name LIKE '%${escapedTerm}%'
    GROUP BY o.id
    LIMIT ${parseInt(limit) || 20}
  `;
  
  const raw = query(sql);
  if (!raw) return [];
  
  return raw.split('\n').filter(Boolean).map(line => {
    const parts = line.split('|');
    return {
      id: parseInt(parts[0]) || 0,
      name: parts[1] || '',
      type: parts[2] || 'organization',
      contacts: parts[3] ? parts[3].split('||').filter(Boolean) : [],
      contactCount: parseInt(parts[4]) || 0
    };
  });
}

module.exports = {
  searchContacts,
  getContact,
  getInteractions,
  getSyncStatus,
  searchOrganizations,
  loadSyncState
};
