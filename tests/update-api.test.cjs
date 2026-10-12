'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {execFileSync} = require('node:child_process');
const {Updater, createUpdateAPI, sameOrigin} = require('../update-api');

function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'klipe update '));
  const source = path.join(dir, 'source'), local = path.join(dir, 'local');
  fs.mkdirSync(source);
  const git = (cwd, ...args) => execFileSync('git', ['-c', 'user.name=Klipe Test', '-c', 'user.email=test@example.invalid', ...args], {cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe']}).trim();
  const write = (root, file, text) => { fs.mkdirSync(path.dirname(path.join(root, file)), {recursive: true}); fs.writeFileSync(path.join(root, file), text); };
  const commit = () => { git(source, 'add', '-A'); git(source, 'commit', '-m', 'test'); };
  git(source, 'init', '-b', 'main');
  write(source, '.gitignore', 'public/projects/\nprivate.tmp\n');
  write(source, 'editor.js', 'old'); commit();
  git(dir, 'clone', source, local);
  const updater = new Updater(local, {remote: source});
  t.after(() => fs.rmSync(dir, {recursive: true, force: true}));
  return {dir, source, local, git, write, commit, updater};
}

test('fast-forward preserves ignored projects and records previous commit', async t => {
  const f = fixture(t);
  f.write(f.local, 'public/projects/client/edit_config.json', '{"keep":true}');
  f.write(f.source, 'editor.js', 'new'); f.commit();
  const plan = await f.updater.run('check');
  assert.equal(plan.phase, 'available');
  const result = await f.updater.run('apply', plan.latest);
  assert.equal(result.phase, 'updated');
  assert.equal(fs.readFileSync(path.join(f.local, 'editor.js'), 'utf8'), 'new');
  assert.equal(fs.readFileSync(path.join(f.local, 'public/projects/client/edit_config.json'), 'utf8'), '{"keep":true}');
  assert.equal(f.git(f.local, 'rev-parse', result.backup), plan.current);
  assert.equal(fs.existsSync(f.updater.lock), false);
});

test('dirty code is not overwritten', async t => {
  const f = fixture(t); f.write(f.local, 'editor.js', 'personal');
  assert.equal((await f.updater.run('check')).phase, 'error');
  assert.equal(fs.readFileSync(path.join(f.local, 'editor.js'), 'utf8'), 'personal');
});

test('untracked code, wrong origin, non-main and divergence stop update', async t => {
  for (const mode of ['untracked', 'origin', 'branch', 'diverged']) {
    const f = fixture(t);
    if (mode === 'untracked') f.write(f.local, 'custom.js', 'mine');
    if (mode === 'origin') f.git(f.local, 'remote', 'set-url', 'origin', 'https://example.invalid/wrong.git');
    if (mode === 'branch') f.git(f.local, 'checkout', '-b', 'feature');
    if (mode === 'diverged') {
      f.write(f.local, 'editor.js', 'local commit'); f.git(f.local, 'add', '.'); f.git(f.local, 'commit', '-m', 'personal');
      f.write(f.source, 'editor.js', 'remote commit'); f.commit();
    }
    const before = f.git(f.local, 'rev-parse', 'HEAD');
    assert.equal((await f.updater.run('check')).phase, 'error', mode);
    assert.equal(f.git(f.local, 'rev-parse', 'HEAD'), before);
  }
});

test('protected project paths and ignored file collisions are refused', async t => {
  for (const file of ['public/projects/client/edit_config.json', 'private.tmp']) {
    const f = fixture(t);
    f.write(f.local, file, 'local private'); f.write(f.source, file, 'remote');
    f.git(f.source, 'add', '-f', file); f.git(f.source, 'commit', '-m', 'collision');
    assert.equal((await f.updater.run('check')).phase, 'error');
    assert.equal(fs.readFileSync(path.join(f.local, file), 'utf8'), 'local private');
  }
});

test('dependency changes require the closed installer before any merge', async t => {
  const f = fixture(t); f.write(f.source, 'requirements.txt', 'example'); f.commit();
  const before = f.git(f.local, 'rev-parse', 'HEAD');
  assert.equal((await f.updater.run('check')).phase, 'installer');
  assert.equal(f.git(f.local, 'rev-parse', 'HEAD'), before);
});

test('closed updater allows dependency update without deleting project', async t => {
  const f = fixture(t); f.write(f.source, 'requirements.txt', 'example'); f.commit();
  assert.equal((await f.updater.run('install')).phase, 'updated');
});

test('unexpected remote version, render and another process lock prevent apply', async t => {
  const f = fixture(t); f.write(f.source, 'editor.js', 'new'); f.commit();
  const before = f.git(f.local, 'rev-parse', 'HEAD');
  assert.equal((await f.updater.run('apply', 'a'.repeat(40))).phase, 'error');
  f.updater.busy = () => true;
  assert.equal((await f.updater.run('check')).phase, 'error');
  fs.writeFileSync(f.updater.lock, 'another instance');
  await assert.rejects(f.updater.run('check'), /Outra instancia/);
  assert.equal(fs.readFileSync(f.updater.lock, 'utf8'), 'another instance');
  assert.equal(f.git(f.local, 'rev-parse', 'HEAD'), before);
});

test('ZIP and network failure have useful errors without modifying code', async t => {
  const f = fixture(t);
  const zip = new Updater(f.dir);
  assert.match((await zip.run('check')).message, /ZIP/);
  fs.renameSync(f.source, f.source + '-offline');
  assert.equal((await f.updater.run('check')).phase, 'error');
  assert.equal(fs.readFileSync(path.join(f.local, 'editor.js'), 'utf8'), 'old');
});

test('same-origin validation rejects hostile sites, local cross-port and DNS rebinding', () => {
  const req = headers => ({headers});
  assert.ok(sameOrigin(req({host:'127.0.0.1:3002', origin:'http://127.0.0.1:3002'})));
  assert.equal(sameOrigin(req({host:'127.0.0.1:3002', origin:'http://localhost:3003'})), false);
  assert.equal(sameOrigin(req({host:'evil.example', origin:'http://evil.example'})), false);
  assert.equal(sameOrigin(req({host:'localhost:3002', 'sec-fetch-site':'cross-site'})), false);
});

test('HTTP API requires token and checked revision, then performs real update', async t => {
  const f = fixture(t); f.write(f.source, 'editor.js', 'new'); f.commit();
  const handler = createUpdateAPI({root: f.local, remote: f.source});
  const server = http.createServer((req, res) => handler(req, res, new URL(req.url, 'http://localhost')));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => {server.closeAllConnections(); server.close(resolve);}));
  const base = 'http://127.0.0.1:' + server.address().port;
  assert.equal((await fetch(base + '/api/updates/check', {method:'POST'})).status, 403);
  assert.equal((await fetch(base + '/api/updates', {headers:{Origin:'https://evil.example'}})).status, 403);
  const initial = await (await fetch(base + '/api/updates')).json();
  const headers = {'X-Klipe-Update': initial.token};
  assert.equal((await fetch(base + '/api/updates/apply', {method:'POST', headers})).status, 409);
  assert.equal((await fetch(base + '/api/updates/check', {method:'POST', headers})).status, 202);
  let state;
  for (let i=0; i<100; i++) {
    state = await (await fetch(base + '/api/updates')).json();
    if (state.phase !== 'checking') break;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  assert.equal(state.phase, 'available');
  headers['X-Klipe-Version'] = state.latest;
  assert.equal((await fetch(base + '/api/updates/apply', {method:'POST', headers})).status, 202);
  for (let i=0; i<100; i++) {
    state = await (await fetch(base + '/api/updates')).json();
    if (state.phase !== 'updating') break;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  assert.equal(state.phase, 'updated');
});
