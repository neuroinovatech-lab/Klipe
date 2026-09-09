// SQLite single-file DB pro Klipe. Guarda users e sessions (multi-tenant).
// Arquivo em data/klipe.db (gitignored). O restante dos dados por-usuario
// (edit_configs, projetos) vai em data/users/<userId>/... — mas isso e' o
// namespacing da Fase 2. Aqui e' so o db.

const path = require('node:path');
const fs = require('node:fs');
const Database = require('better-sqlite3');

const DATA_DIR = path.resolve(__dirname, 'data');
const DB_FILE = process.env.KLIPE_DB_PATH || path.join(DATA_DIR, 'klipe.db');

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

const db = new Database(DB_FILE);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    password_salt  TEXT NOT NULL,
    role           TEXT NOT NULL DEFAULT 'member',   -- 'admin' | 'member'
    created_at     INTEGER NOT NULL,
    display_name   TEXT
  );

  CREATE TABLE IF NOT EXISTS sessions (
    token          TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL,
    expires_at     INTEGER NOT NULL,
    created_at     INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
  );
  CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
`);

process.on('SIGINT',      () => { try { db.close(); } catch {} });
process.on('SIGTERM',     () => { try { db.close(); } catch {} });
process.on('beforeExit',  () => { try { db.close(); } catch {} });

console.log(`[Klipe/db] SQLite pronto em ${DB_FILE}`);

module.exports = { db, DATA_DIR };
