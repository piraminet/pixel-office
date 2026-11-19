const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

// Configuration from env
const MAIL2_HOST = process.env.MAIL2_HOST || '159.65.183.161';
const MAIL2_USER = process.env.MAIL2_USER || 'root';
const SSH_KEY_PATH = process.env.SSH_KEY_PATH || '/app/ssh/id_ed25519';
const EMAIL_IMAP_HOST = process.env.EMAIL_IMAP_HOST || '127.0.0.1';
const EMAIL_IMAP_PORT = process.env.EMAIL_IMAP_PORT || '993';

// === Nocturnal Inc Account Configuration ===
// Passwords loaded from env vars: EMAIL_PASS_<ID> (uppercased, @ and . replaced with _)
// Or from EMAIL_USER/EMAIL_PASSWORD as the default account
const DEFAULT_EMAIL = process.env.EMAIL_USER || '';
const DEFAULT_PASS = process.env.EMAIL_PASSWORD || '';

const ACCOUNTS = [
  // Owner
  { id: 'jb', email: 'jb@theblacktech.com', name: 'Owner', category: 'owner', icon: '👤', color: '#dc2626',
    password: process.env.EMAIL_PASSWORD || (DEFAULT_EMAIL === 'jb@theblacktech.com' ? DEFAULT_PASS : '') },
  { id: 'jon-jj', email: 'jon@j-johnson.com', name: 'JCB Equity', category: 'owner', icon: '👔', color: '#b91c1c',
    password: process.env.EMAIL_2_PASSWORD || '' },

  // Operations
  { id: 'jon', email: 'jon@nocturnalinc.com', name: 'Operations', category: 'operations', icon: '🏢', color: '#2563eb',
    password: process.env.EMAIL_PASS_JON || (DEFAULT_EMAIL === 'jon@nocturnalinc.com' ? DEFAULT_PASS : '') },
  { id: 'accounts', email: 'accounts@nocturnalinc.com', name: 'Accounts', category: 'operations', icon: '💰', color: '#10b981',
    password: process.env.EMAIL_PASS_ACCOUNTS || (DEFAULT_EMAIL === 'accounts@nocturnalinc.com' ? DEFAULT_PASS : '') },
  { id: 'contact', email: 'contact@nocturnalinc.com', name: 'Contact', category: 'operations', icon: '📧', color: '#06b6d4',
    password: process.env.EMAIL_PASS_CONTACT || (DEFAULT_EMAIL === 'contact@nocturnalinc.com' ? DEFAULT_PASS : '') },

  // Support
  { id: 'helpdesk', email: 'helpdesk@nocturnalinc.com', name: 'Helpdesk', category: 'support', icon: '🎫', color: '#f59e0b',
    password: process.env.EMAIL_PASS_HELPDESK || (DEFAULT_EMAIL === 'helpdesk@nocturnalinc.com' ? DEFAULT_PASS : '') },

  // Notifications
  { id: 'nightchute', email: 'nightchute@nocturnalinc.com', name: 'Nightchute', category: 'notifications', icon: '🔔', color: '#8b5cf6',
    password: process.env.EMAIL_PASS_NIGHTCHUTE || (DEFAULT_EMAIL === 'nightchute@nocturnalinc.com' ? DEFAULT_PASS : '') },
  { id: 'notification', email: 'notification@nocturnalinc.com', name: 'Notifications', category: 'notifications', icon: '📣', color: '#a78bfa',
    password: process.env.EMAIL_PASS_NOTIFICATION || (DEFAULT_EMAIL === 'notification@nocturnalinc.com' ? DEFAULT_PASS : '') },

  // Services
  { id: 'openproject', email: 'openproject@nocturnalinc.com', name: 'OpenProject', category: 'services', icon: '📋', color: '#6366f1',
    password: process.env.EMAIL_PASS_OPENPROJECT || (DEFAULT_EMAIL === 'openproject@nocturnalinc.com' ? DEFAULT_PASS : '') },
  { id: 'charon', email: 'charon@nocturnalinc.com', name: 'Charon Agent', category: 'services', icon: '🤖', color: '#ec4899',
    password: process.env.EMAIL_PASS_CHARON || (DEFAULT_EMAIL === 'charon@nocturnalinc.com' ? DEFAULT_PASS : '') },

  // NocturnalPost (Filtering Service)
  { id: 'rua', email: 'rua@nocturnalpost.com', name: 'NocturnalPost', category: 'filtering', icon: '🛡️', color: '#64748b',
    password: process.env.EMAIL_PASS_NOCTURNALPOST || (DEFAULT_EMAIL === 'rua@nocturnalpost.com' ? DEFAULT_PASS : '') },
];

// Category metadata
const CATEGORIES = [
  { id: 'owner', name: 'Owner', icon: '👤', color: '#dc2626' },
  { id: 'operations', name: 'Operations', icon: '🏢', color: '#2563eb' },
  { id: 'support', name: 'Support', icon: '🎫', color: '#f59e0b' },
  { id: 'notifications', name: 'Notifications', icon: '🔔', color: '#8b5cf6' },
  { id: 'services', name: 'Services', icon: '⚙️', color: '#6366f1' },
  { id: 'filtering', name: 'NocturnalPost', icon: '🛡️', color: '#64748b' },
];

// Get account by id
function getAccount(accountId) {
  return ACCOUNTS.find(a => a.id === accountId);
}

// Get accounts list (without passwords)
function getAccountsList() {
  return ACCOUNTS.map(a => ({
    id: a.id,
    email: a.email,
    name: a.name,
    category: a.category,
    icon: a.icon,
    color: a.color,
    configured: !!a.password
  }));
}

// Cache for SSH key
let sshKeyCache = null;
function getSSHKey() {
  if (sshKeyCache) return sshKeyCache;
  try {
    sshKeyCache = fs.readFileSync(SSH_KEY_PATH, 'utf8');
    return sshKeyCache;
  } catch (e) {
    throw new Error(`Cannot read SSH key at ${SSH_KEY_PATH}: ${e.message}`);
  }
}

// Run a Python script on mail2 via SSH
function runOnMail2(scriptContent, envVars = {}) {
  return new Promise((resolve, reject) => {
    const conn = new Client();
    let stdout = '';
    let stderr = '';
    const timeout = setTimeout(() => {
      conn.end();
      reject(new Error('SSH timeout (30s)'));
    }, 30000);

    conn.on('ready', () => {
      conn.sftp((err, sftp) => {
        if (err) {
          clearTimeout(timeout);
          conn.end();
          reject(new Error(`SFTP error: ${err.message}`));
          return;
        }

        const scriptPath = `/tmp/pixel_email_${Date.now()}.py`;
        sftp.writeFile(scriptPath, scriptContent, (err) => {
          if (err) {
            clearTimeout(timeout);
            conn.end();
            reject(new Error(`SFTP write error: ${err.message}`));
            return;
          }

          const envPrefix = Object.entries(envVars)
            .filter(([k, v]) => v !== undefined && v !== null && v !== '')
            .map(([k, v]) => `${k}=${JSON.stringify(String(v))}`)
            .join(' ');

          conn.exec(
            `${envPrefix} python3 ${scriptPath} 2>&1; rm -f ${scriptPath}`,
            (err, stream) => {
              if (err) {
                clearTimeout(timeout);
                conn.end();
                reject(new Error(`Exec error: ${err.message}`));
                return;
              }

              stream.on('data', (d) => { stdout += d.toString(); });
              stream.stderr.on('data', (d) => { stderr += d.toString(); });
              stream.on('close', () => {
                clearTimeout(timeout);
                conn.end();
                if (stderr && !stdout) {
                  reject(new Error(stderr));
                } else {
                  resolve(stdout);
                }
              });
            }
          );
        });
      });
    });

    conn.on('error', (err) => {
      clearTimeout(timeout);
      reject(new Error(`SSH connection error: ${err.message}`));
    });

    try {
      conn.connect({
        host: MAIL2_HOST,
        port: 22,
        username: MAIL2_USER,
        privateKey: getSSHKey(),
        readyTimeout: 10000
      });
    } catch (e) {
      clearTimeout(timeout);
      reject(new Error(`SSH connect failed: ${e.message}`));
    }
  });
}

// Parse JSON from SSH output
function parseSSHJson(output) {
  try {
    const lines = output.trim().split('\n');
    const jsonLine = lines.find(l => l.trim().startsWith('{'));
    if (jsonLine) return JSON.parse(jsonLine);
    return { error: 'No JSON in output', raw: output.substring(0, 500) };
  } catch (e) {
    return { error: `Parse error: ${e.message}`, raw: output.substring(0, 500) };
  }
}

// List inbox emails for a specific account
async function listInbox(limit = 20, folder = 'INBOX', accountId = null) {
  const account = accountId ? getAccount(accountId) : null;
  const emailUser = account ? account.email : DEFAULT_EMAIL;
  const emailPass = account ? account.password : DEFAULT_PASS;

  if (!emailUser || !emailPass) {
    return { error: `Account "${accountId}" not configured`, emails: [], count: 0 };
  }

  const script = `
import imaplib, email, json, os
from email.header import decode_header

def decode_str(s):
    if s is None:
        return ''
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or 'utf-8', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)

try:
    m = imaplib.IMAP4_SSL(os.environ['IMAP_HOST'], int(os.environ['IMAP_PORT']))
    m.login(os.environ['EMAIL_USER'], os.environ['EMAIL_PASS'])
    m.select('"${folder}"', readonly=True)
    status, data = m.search(None, 'ALL')
    if status != 'OK':
        print(json.dumps({'error': 'Search failed'}))
        m.logout()
        exit()
    ids = data[0].split()
    ids.reverse()
    ids = ids[:${limit}]
    emails = []
    for mid in ids:
        status, msg_data = m.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)] FLAGS)')
        if status != 'OK':
            continue
        raw = msg_data[0][1] if msg_data and msg_data[0] else b''
        msg = email.message_from_bytes(raw)
        flags = ''
        if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
            flags = str(msg_data[0][0])
        seen = '\\\\Seen' in flags
        emails.append({
            'id': mid.decode(),
            'from': decode_str(msg.get('From','')),
            'to': decode_str(msg.get('To','')),
            'subject': decode_str(msg.get('Subject','')),
            'date': msg.get('Date',''),
            'seen': seen
        })
    m.logout()
    print(json.dumps({'emails': emails, 'folder': '${folder}', 'count': len(emails), 'account': '${emailUser}'}))
except Exception as e:
    print(json.dumps({'error': str(e)}))
`;

  const output = await runOnMail2(script, {
    IMAP_HOST: EMAIL_IMAP_HOST,
    IMAP_PORT: EMAIL_IMAP_PORT,
    EMAIL_USER: emailUser,
    EMAIL_PASS: emailPass
  });

  return parseSSHJson(output);
}

// Get full email by ID
async function getEmail(uid, folder = 'INBOX', accountId = null) {
  const account = accountId ? getAccount(accountId) : null;
  const emailUser = account ? account.email : DEFAULT_EMAIL;
  const emailPass = account ? account.password : DEFAULT_PASS;

  if (!emailUser || !emailPass) {
    return { error: `Account "${accountId}" not configured` };
  }

  const script = `
import imaplib, email, json, os
from email.header import decode_header

def decode_str(s):
    if s is None:
        return ''
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or 'utf-8', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)

def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain':
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or 'utf-8', errors='replace')
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/html':
                payload = part.get_payload(decode=True)
                if payload:
                    return '[HTML] ' + payload.decode(part.get_content_charset() or 'utf-8', errors='replace')[:500]
        return '(no plain text body)'
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(msg.get_content_charset() or 'utf-8', errors='replace')
        return msg.get_payload()

try:
    m = imaplib.IMAP4_SSL(os.environ['IMAP_HOST'], int(os.environ['IMAP_PORT']))
    m.login(os.environ['EMAIL_USER'], os.environ['EMAIL_PASS'])
    m.select('"${folder}"', readonly=True)
    status, data = m.fetch('${uid}', '(RFC822)')
    if status != 'OK':
        print(json.dumps({'error': 'Fetch failed'}))
        m.logout()
        exit()
    raw = data[0][1]
    msg = email.message_from_bytes(raw)
    result = {
        'id': '${uid}',
        'from': decode_str(msg.get('From','')),
        'to': decode_str(msg.get('To','')),
        'cc': decode_str(msg.get('Cc','')),
        'subject': decode_str(msg.get('Subject','')),
        'date': msg.get('Date',''),
        'body': get_body(msg)[:10000]
    }
    m.logout()
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({'error': str(e)}))
`;

  const output = await runOnMail2(script, {
    IMAP_HOST: EMAIL_IMAP_HOST,
    IMAP_PORT: EMAIL_IMAP_PORT,
    EMAIL_USER: emailUser,
    EMAIL_PASS: emailPass
  });

  return parseSSHJson(output);
}

// Send email via SMTP through mail2
async function sendEmail(to, subject, body, accountId = null) {
  const account = accountId ? getAccount(accountId) : null;
  const fromAddr = account ? account.email : DEFAULT_EMAIL;
  const emailPass = account ? account.password : DEFAULT_PASS;

  if (!fromAddr || !emailPass) {
    return { error: `Account "${accountId}" not configured` };
  }

  const safeSubject = subject.replace(/'/g, "\\'");
  const safeBody = body.replace(/'/g, "\\'");
  const safeTo = to.replace(/'/g, "\\'");
  const safeFrom = fromAddr.replace(/'/g, "\\'");

  const script = `
import smtplib, json, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    msg = MIMEMultipart()
    msg['From'] = '${safeFrom}'
    msg['To'] = '${safeTo}'
    msg['Subject'] = '${safeSubject}'
    msg.attach(MIMEText('''${safeBody}''', 'plain'))

    s = smtplib.SMTP('127.0.0.1', 587)
    s.starttls()
    s.login(os.environ['EMAIL_USER'], os.environ['EMAIL_PASS'])
    s.sendmail('${safeFrom}', '${safeTo}'.split(','), msg.as_string())
    s.quit()
    print(json.dumps({'success': True, 'from': '${safeFrom}', 'to': '${safeTo}', 'subject': '${safeSubject}'}))
except Exception as e:
    print(json.dumps({'error': str(e)}))
`;

  const output = await runOnMail2(script, {
    EMAIL_USER: fromAddr,
    EMAIL_PASS: emailPass
  });

  return parseSSHJson(output);
}

// Get unread count for an account
async function getUnreadCount(folder = 'INBOX', accountId = null) {
  const account = accountId ? getAccount(accountId) : null;
  const emailUser = account ? account.email : DEFAULT_EMAIL;
  const emailPass = account ? account.password : DEFAULT_PASS;

  if (!emailUser || !emailPass) {
    return { unread: 0, error: 'not configured' };
  }

  const script = `
import imaplib, json, os

try:
    m = imaplib.IMAP4_SSL(os.environ['IMAP_HOST'], int(os.environ['IMAP_PORT']))
    m.login(os.environ['EMAIL_USER'], os.environ['EMAIL_PASS'])
    m.select('"${folder}"', readonly=True)
    status, data = m.search(None, 'UNSEEN')
    count = len(data[0].split()) if data[0] else 0
    m.logout()
    print(json.dumps({'unread': count, 'folder': '${folder}', 'account': '${emailUser}'}))
except Exception as e:
    print(json.dumps({'error': str(e)}))
`;

  const output = await runOnMail2(script, {
    IMAP_HOST: EMAIL_IMAP_HOST,
    IMAP_PORT: EMAIL_IMAP_PORT,
    EMAIL_USER: emailUser,
    EMAIL_PASS: emailPass
  });

  try {
    const lines = output.trim().split('\n');
    const jsonLine = lines.find(l => l.trim().startsWith('{'));
    if (jsonLine) return JSON.parse(jsonLine);
    return { unread: 0 };
  } catch (e) {
    return { unread: 0, error: e.message };
  }
}

// Get unread counts for all configured accounts (batch)
async function getAllUnreadCounts() {
  const results = {};
  const configured = ACCOUNTS.filter(a => a.password);

  // Run them in parallel (each opens its own SSH connection)
  const promises = configured.map(async (account) => {
    try {
      const result = await getUnreadCount('INBOX', account.id);
      results[account.id] = {
        email: account.email,
        name: account.name,
        category: account.category,
        icon: account.icon,
        color: account.color,
        unread: result.unread || 0,
        error: result.error || null
      };
    } catch (e) {
      results[account.id] = {
        email: account.email,
        name: account.name,
        category: account.category,
        icon: account.icon,
        color: account.color,
        unread: 0,
        error: e.message
      };
    }
  });

  await Promise.all(promises);
  return results;
}

module.exports = {
  listInbox,
  getEmail,
  sendEmail,
  getUnreadCount,
  getAllUnreadCounts,
  getAccountsList,
  getAccount,
  CATEGORIES,
  ACCOUNTS
};
