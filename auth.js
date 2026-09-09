// Autenticacao do Klipe: hash de senha (scrypt), users CRUD, sessoes.
// Padrao copiado do Cove (VoiceVIP/backend/src/users.js), adaptado pra
// CommonJS e sem nanoid (usa crypto.randomBytes).

const crypto = require('node:crypto');
const { db } = require('./db.js');

const SCRYPT_KEY_LEN = 64;
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 dias
const SESSION_COOKIE = 'klipe_session';

function hashPassword(password, salt) {
  return crypto.scryptSync(password, salt, SCRYPT_KEY_LEN).toString('hex');
}
function newSalt() { return crypto.randomBytes(16).toString('hex'); }
function newId()   { return crypto.randomBytes(8).toString('hex');  }
function newToken(){ return crypto.randomBytes(24).toString('hex'); }

function safeCompare(a, b) {
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(Buffer.from(a, 'hex'), Buffer.from(b, 'hex'));
}

// ─── Users ────────────────────────────────────────────────────────────

function createUser({ username, password, role = 'member', displayName = null }) {
  const clean = (username || '').trim().toLowerCase();
  if (!/^[a-z0-9_.-]{3,32}$/.test(clean)) throw new Error('invalid_username');
  if (!password || password.length < 6)   throw new Error('weak_password');
  const salt = newSalt();
  const hash = hashPassword(password, salt);
  const id = newId();
  const now = Date.now();
  try {
    db.prepare(`
      INSERT INTO users (id, username, password_hash, password_salt, role, created_at, display_name)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(id, clean, hash, salt, role, now, displayName);
  } catch (e) {
    if (e.code === 'SQLITE_CONSTRAINT_UNIQUE') throw new Error('username_taken');
    throw e;
  }
  return findById(id);
}

function findByUsername(username) {
  return db.prepare(`SELECT * FROM users WHERE username = ?`).get((username || '').trim().toLowerCase()) || null;
}
function findById(id) {
  return db.prepare(`SELECT * FROM users WHERE id = ?`).get(id) || null;
}
function listUsers() {
  return db.prepare(`SELECT id, username, role, created_at, display_name FROM users ORDER BY created_at ASC`).all();
}
function deleteUser(id) {
  db.prepare(`DELETE FROM users WHERE id = ?`).run(id);
}
function countUsers() {
  return db.prepare(`SELECT COUNT(*) AS n FROM users`).get().n;
}
function countActiveAdmins() {
  return db.prepare(`SELECT COUNT(*) AS n FROM users WHERE role = 'admin'`).get().n;
}

function verifyPassword(user, password) {
  if (!user || !password) return false;
  const hashed = hashPassword(password, user.password_salt);
  return safeCompare(hashed, user.password_hash);
}

function publicUser(user) {
  if (!user) return null;
  return {
    id: user.id,
    username: user.username,
    displayName: user.display_name,
    role: user.role,
    createdAt: user.created_at,
  };
}

// ─── Sessions ────────────────────────────────────────────────────────

function createSession(userId) {
  const token = newToken();
  const now = Date.now();
  db.prepare(`
    INSERT INTO sessions (token, user_id, expires_at, created_at)
    VALUES (?, ?, ?, ?)
  `).run(token, userId, now + SESSION_TTL_MS, now);
  return { token, expiresAt: now + SESSION_TTL_MS };
}

function findUserBySessionToken(token) {
  if (!token) return null;
  const row = db.prepare(`
    SELECT u.*, s.expires_at AS _sx
    FROM sessions s JOIN users u ON u.id = s.user_id
    WHERE s.token = ?
  `).get(token);
  if (!row) return null;
  if (row._sx < Date.now()) { deleteSession(token); return null; }
  return row;
}

function deleteSession(token) {
  if (!token) return;
  db.prepare(`DELETE FROM sessions WHERE token = ?`).run(token);
}

// Limpa expiradas 1x/hora (best-effort, nao trava restart)
const cleaner = setInterval(() => {
  try { db.prepare(`DELETE FROM sessions WHERE expires_at < ?`).run(Date.now()); } catch {}
}, 60 * 60 * 1000);
cleaner.unref?.();

// ─── Cookie helpers ──────────────────────────────────────────────────
// Node http puro nao tem cookie parser — implemento local.

function parseCookies(req) {
  const raw = req.headers.cookie || '';
  const out = {};
  for (const part of raw.split(';')) {
    const [k, ...rest] = part.trim().split('=');
    if (!k) continue;
    out[k] = decodeURIComponent(rest.join('='));
  }
  return out;
}

function sessionCookieHeader(token, expiresAt) {
  // HttpOnly pra scripts nao lerem, SameSite=Lax pra proteger CSRF minimo.
  // Sem Secure pq roda tambem via http local — em prod via Cloudflare Tunnel
  // o browser ve https e o cookie e' aceito mesmo sem flag Secure.
  const exp = new Date(expiresAt).toUTCString();
  return `${SESSION_COOKIE}=${token}; Path=/; HttpOnly; SameSite=Lax; Expires=${exp}`;
}

function clearSessionCookieHeader() {
  return `${SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`;
}

// Extrai user autenticado do request (cookie ou Authorization: Bearer).
// Retorna user OU null. NAO manda resposta.
function getRequestUser(req) {
  const cookies = parseCookies(req);
  let token = cookies[SESSION_COOKIE];
  if (!token) {
    const auth = req.headers.authorization || '';
    if (auth.startsWith('Bearer ')) token = auth.slice(7).trim();
  }
  return findUserBySessionToken(token);
}

module.exports = {
  // users
  createUser, findByUsername, findById, listUsers, deleteUser,
  countUsers, countActiveAdmins, verifyPassword, publicUser,
  // sessions
  createSession, findUserBySessionToken, deleteSession,
  // cookies
  parseCookies, sessionCookieHeader, clearSessionCookieHeader,
  getRequestUser, SESSION_COOKIE,
};
