'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {execFile} = require('node:child_process');
const {promisify} = require('node:util');
const exec = promisify(execFile);
const OFFICIAL = 'https://github.com/neuroinovatech-lab/Klipe.git';
const protectedPath = name => /^(public\/(projects|\.config_backups|fonts)\/|config\/|projects\/|models\/|renders\/|output\/|\.venv|node_modules\/|\.klipe-runtime|klipe_settings|\.env(?:$|\.))|\.(db|sqlite3?)(?:$|-)/i.test(name);
const requiresInstaller = name => /^(package(?:-lock)?\.json|requirements[^/]*\.txt|tools\/(?:ffmpeg-release\.json|.*(?:install|runtime|ffmpeg).*\.ps1)|app\/(?!README\.md).*)$/.test(name);

class Updater {
  constructor(root, {remote = OFFICIAL, busy = () => false} = {}) {
    this.root = root;
    this.remote = remote;
    this.busy = busy;
    this.state = {phase: 'idle', message: 'Verifique se ha uma nova versao.'};
    this.lock = path.join(root, '.klipe-update.lock');
    this.token = crypto.randomBytes(32).toString('hex');
  }

  async git(args) {
    try {
      return (await exec('git', ['-c', 'core.hooksPath=/dev/null', ...args], {
        cwd: this.root, windowsHide: true, timeout: 120000, maxBuffer: 4 * 1024 * 1024,
        env: {...process.env, GIT_TERMINAL_PROMPT: '0', GCM_INTERACTIVE: 'never'},
      })).stdout;
    } catch (error) {
      if (error.code === 'ENOENT') throw new Error('Git nao encontrado. Instale Git for Windows e reabra o Klipe.');
      if ((error.stderr || '').includes('dubious ownership')) {
        throw new Error('O Git bloqueou esta pasta porque ela pertence a outro usuario do Windows. Peca ao seu agente para revisar a permissao. Nenhum arquivo foi alterado.');
      }
      throw new Error((error.stderr || error.message).trim().slice(-1200));
    }
  }

  async local() {
    if (!fs.existsSync(path.join(this.root, '.git'))) {
      throw new Error('Esta copia veio de ZIP. O botao requer uma instalacao feita com git clone; consulte docs/ATUALIZACOES.md. Seus projetos nao foram alterados.');
    }
    const top = (await this.git(['rev-parse', '--show-toplevel'])).trim();
    if (fs.realpathSync(top).toLowerCase() !== fs.realpathSync(this.root).toLowerCase()) {
      throw new Error('O Klipe precisa ser a raiz do repositorio Git.');
    }
    const branch = (await this.git(['symbolic-ref', '--short', 'HEAD'])).trim();
    if (branch !== 'main') throw new Error('Atualizacao automatica disponivel somente na branch main.');
    const origin = (await this.git(['remote', 'get-url', 'origin'])).trim();
    if (origin !== this.remote) throw new Error('O repositorio nao usa a origem oficial do Klipe. Nenhum arquivo foi alterado.');
    if ((await this.git(['status', '--porcelain', '--untracked-files=normal', '--', '.', ':(exclude).klipe-update.lock'])).trim()) {
      throw new Error('Existem alteracoes locais no codigo. Salve-as com ajuda do seu agente antes de atualizar. Nada sera descartado.');
    }
    return (await this.git(['rev-parse', 'HEAD'])).trim();
  }

  async plan() {
    const current = await this.local();
    await this.git(['fetch', '--no-tags', this.remote, 'refs/heads/main']);
    const latest = (await this.git(['rev-parse', 'FETCH_HEAD'])).trim();
    try { await this.git(['merge-base', '--is-ancestor', current, latest]); }
    catch { throw new Error('O historico local divergiu do GitHub. A atualizacao automatica nao faz reset nem substitui commits locais.'); }
    const files = (await this.git(['diff', '--name-only', '-z', '--no-renames', current, latest])).split('\0').filter(Boolean);
    const tracked = new Set((await this.git(['ls-files', '-z'])).split('\0').map(x => x.toLowerCase()));
    for (const name of files) {
      if (protectedPath(name)) throw new Error('Atualizacao recusada: inclui dados locais protegidos (' + name + ').');
      if (!tracked.has(name.toLowerCase()) && fs.existsSync(path.join(this.root, name))) {
        throw new Error('Um arquivo local seria substituido: ' + name + '. Nada foi alterado.');
      }
      // A junction/symlink must never redirect an update into user data.
      let parent = path.dirname(path.join(this.root, name));
      while (parent !== this.root && parent.startsWith(this.root + path.sep)) {
        if (fs.existsSync(parent) && fs.lstatSync(parent).isSymbolicLink()) throw new Error('Pasta vinculada impede a atualizacao: ' + name);
        parent = path.dirname(parent);
      }
    }
    return {current, latest, files, needsInstaller: files.some(requiresInstaller)};
  }

  async run(action, expected) {
    if (['checking', 'updating'].includes(this.state.phase)) throw new Error('Uma atualizacao ja esta em andamento.');
    if (this.state.phase === 'updated') throw new Error('Feche e abra o Klipe antes de verificar novamente.');
    let fd;
    try { fd = fs.openSync(this.lock, 'wx'); }
    catch { throw new Error('Outra instancia esta atualizando. Se houve queda de energia, consulte docs/ATUALIZACOES.md.'); }
    this.state = {phase: action === 'check' ? 'checking' : 'updating', message: 'Consultando o GitHub...'};
    try {
      if (this.busy()) throw new Error('Espere os renders e processamentos terminarem antes de atualizar.');
      const plan = await this.plan();
      if (action === 'apply' && (expected !== plan.latest || !/^[a-f0-9]{40,64}$/.test(expected || ''))) {
        throw new Error('A versao disponivel mudou. Verifique novamente antes de instalar.');
      }
      if (!plan.files.length) {
        this.state = {...plan, phase: 'current', message: 'O Klipe ja esta atualizado.'};
      } else if (plan.needsInstaller && action !== 'install') {
        this.state = {...plan, phase: 'installer', message: 'Esta versao tambem altera dependencias ou o Desktop. Salve, feche e use Atualizar Klipe.bat para concluir a atualizacao.'};
      } else if (action === 'check') {
        this.state = {...plan, phase: 'available', message: 'Nova versao disponivel.'};
      } else {
        if (this.busy() || await this.local() !== plan.current) throw new Error('O estado local mudou. Verifique novamente.');
        const backup = 'refs/klipe/backups/' + Date.now();
        await this.git(['update-ref', backup, plan.current]);
        this.state.message = 'Aplicando atualizacao...';
        await this.git(['merge', '--ff-only', '--no-edit', plan.latest]);
        this.state = {...plan, backup, phase: 'updated', message: 'Atualizado. Salve qualquer outra janela aberta, feche o Klipe e abra novamente.'};
      }
    } catch (error) {
      this.state = {phase: 'error', message: error.message};
    } finally {
      fs.closeSync(fd);
      fs.unlinkSync(this.lock);
    }
    return this.state;
  }
}

function sameOrigin(req) {
  const host = req.headers.host || '';
  if (!/^(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$/.test(host)) return false;
  if (req.headers.origin && req.headers.origin !== 'http://' + host) return false;
  return !req.headers['sec-fetch-site'] || ['same-origin', 'none'].includes(req.headers['sec-fetch-site']);
}

function createUpdateAPI(options) {
  const updater = new Updater(options.root, options);
  const handler = async (req, res, url) => {
    if (!url.pathname.startsWith('/api/updates')) return false;
    const reply = (code, value) => {
      res.writeHead(code, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'});
      res.end(JSON.stringify(value));
      return true;
    };
    if (!sameOrigin(req)) return reply(403, {error: 'Origem nao permitida.'});
    if (req.method === 'GET' && url.pathname === '/api/updates') return reply(200, {...updater.state, token: updater.token});
    if (req.method !== 'POST' || !['/api/updates/check', '/api/updates/apply'].includes(url.pathname)) return reply(404, {error: 'Rota nao encontrada.'});
    if (req.headers['x-klipe-update'] !== updater.token) return reply(403, {error: 'Reabra o painel de atualizacoes.'});
    if (['checking', 'updating', 'updated'].includes(updater.state.phase)) return reply(409, {error: 'Atualizacao em andamento ou aguardando reinicio.'});
    const action = url.pathname.endsWith('/apply') ? 'apply' : 'check';
    if (action === 'apply' && (updater.state.phase !== 'available' || req.headers['x-klipe-version'] !== updater.state.latest)) return reply(409, {error: 'Verifique a versao antes de instalar.'});
    updater.run(action, req.headers['x-klipe-version']).catch(error => { updater.state = {phase: 'error', message: error.message}; });
    return reply(202, {accepted: true});
  };
  handler.isUpdating = () => updater.state.phase === 'updating';
  return handler;
}

module.exports = {Updater, createUpdateAPI, sameOrigin, protectedPath, requiresInstaller};

if (require.main === module && process.argv[2] === '--closed-update') {
  const updater = new Updater(__dirname);
  updater.run('install').then(state => {
    console.log(state.message);
    if (state.phase === 'error') process.exitCode = 1;
  }).catch(error => { console.error(error.message); process.exitCode = 1; });
}
