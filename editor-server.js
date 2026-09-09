const http = require("http");
const fs = require("fs");
const path = require("path");
const os = require("os");
const crypto = require("crypto");
const { spawn } = require("child_process");
const auth = require("./auth.js");

const PORT = Number(process.env.PORT) || 3002;
const CONFIG_PATH = path.join(__dirname, "public", "edit_config.json");
const custos = require("./custos");
const PUBLIC_DIR = path.join(__dirname, "public");
const ANALYZE_SCRIPT = path.join(__dirname, "analyze_styles.py");
const PROJECTS_DIR = path.join(__dirname, "projects");
// Cada projeto tem seu proprio job. Um unico global fazia o modal de qualquer
// aba mostrar e abrir o ultimo render iniciado em OUTRO projeto.
const FORGE_RENDERS = new Map();
const chaveForge = (slug) => slugSeguro(slug) || "_global";

// Normaliza o primeiro intervalo HTTP pedido por players de mídia. Chromium
// alterna entre `bytes=inicio-`, `bytes=inicio-fim` e `bytes=-sufixo` ao
// procurar o índice e os keyframes. O fim sempre precisa ser limitado ao EOF;
// anunciar Content-Length maior do que o stream realmente entrega deixa o
// elemento <video> preso para sempre em `seeking`.
function intervaloBytes(cabecalho, tamanho) {
  const texto = String(cabecalho || "").replace(/^bytes=/i, "").split(",")[0].trim();
  const m = /^(\d*)-(\d*)$/.exec(texto);
  if (!m || (!m[1] && !m[2])) return null;

  let start;
  let end;
  if (!m[1]) {
    const sufixo = Number(m[2]);
    if (!Number.isFinite(sufixo) || sufixo <= 0) return null;
    start = Math.max(0, tamanho - sufixo);
    end = tamanho - 1;
  } else {
    start = Number(m[1]);
    end = m[2] ? Math.min(Number(m[2]), tamanho - 1) : tamanho - 1;
  }
  if (!Number.isInteger(start) || !Number.isInteger(end)
      || start < 0 || start >= tamanho || end < start) return null;
  return { start, end };
}

// ─── AJUSTES ────────────────────────────────────────────────────────────
// Uma casa so para o que o usuario configura: chaves, GPU, encoder.
// NAO mora na pasta do projeto, e sim em %LOCALAPPDATA%\Klipe\ - junto do
// ffmpeg que o instalador poe la. Instalar noutro PC e copiar a pasta; com
// as chaves dentro dela, as chaves de quem copiou iriam junto, e quem
// instala tem que por a sua. O .gitignore protegia o repositorio, nao a copia.
//
const AJUSTES_DIR = path.join(process.env.LOCALAPPDATA || os.homedir(), "Klipe");
const AJUSTES_PATH = path.join(AJUSTES_DIR, "klipe_settings.json");

// Migracao de quem ja tinha o arquivo na pasta antiga. A ordem importa:
// copia, LE DE VOLTA para confirmar que chegou inteiro, guarda um .bak e
// so entao apaga o original - se qualquer passo falhar, o antigo continua la.
(function migrarAjustes() {
  const antigo = path.join(__dirname, "klipe_settings.json");
  if (!fs.existsSync(antigo) || fs.existsSync(AJUSTES_PATH)) return;
  try {
    fs.mkdirSync(AJUSTES_DIR, { recursive: true });
    fs.copyFileSync(antigo, AJUSTES_PATH);
    JSON.parse(fs.readFileSync(AJUSTES_PATH, "utf8"));   // chegou legivel?
    // O .bak vai para o perfil, NAO para a pasta do projeto: um backup com as
    // chaves dentro do que vai ser copiado anula o motivo da mudanca.
    fs.copyFileSync(antigo, AJUSTES_PATH + ".bak_migrado");
    fs.unlinkSync(antigo);
    console.log(`[Klipe] chaves movidas para ${AJUSTES_PATH}`);
    console.log(`        (copia de seguranca em ${path.basename(antigo)}.bak_migrado)`);
  } catch (e) {
    console.log(`[Klipe] nao consegui mover as chaves (${e.message}); seguindo com as antigas`);
  }
})();

const PADRAO = {
  gemini_key: "",          // VEO + OMNI
  anthropic_key: "",       // direcao por IA
  pexels_key: "",          // busca de b-roll
  veo_model: "veo-3.1-generate-preview",
  gpu: "auto",             // auto | sim | nao
  codec: "h264",           // h264 | h265 | av1
  python_exe: "",          // vazio = usa PYTHON_EXE do env, ou o caminho padrao
  // Vazio = procura sozinho (env KLIPE_FFMPEG > C:/ffmpeg/bin > PATH). Existe
  // porque o caminho vinha CRAVADO em cinco arquivos: noutra maquina o render
  // morria apontando pra uma pasta que a pessoa nunca viu.
  ffmpeg_path: "",
  // Gerador de SFX: DESLIGADO por padrao. Ele mora fora do Klipe
  // (ferramentas/gerador_sfx/), pesa GB em modelo e quase ninguem vai usar,
  // porque som pronto ganha. Ligar e uma escolha, nao um estado inicial.
  sfx_gerador: false,
  sfx_python: "",          // python do ambiente separado; vazio = o mesmo do Klipe
  // Tarifas em US$ para o medidor de gasto. O Klipe conta os segundos com
  // exatidao; o PRECO do segundo muda com modelo, regiao e data, entao fica
  // aqui para voce conferir em ai.google.dev/pricing. Mostrar um valor errado
  // com confianca e pior que nao mostrar nada.
  tarifa_veo_seg: 0.40,    // por segundo de video gerado pelo Veo
  tarifa_omni_seg: 0.30,   // por segundo de video enviado ao OMNI
  tarifa_gemini_mtok_in: 0.10,   // US$ por milhao de tokens de entrada
  tarifa_gemini_mtok_out: 0.40,  // US$ por milhao de tokens de saida
};

// Nunca sai do servidor em texto claro: o GET devolve so `•••` + 4 digitos.
const SEGREDOS = new Set(["gemini_key", "anthropic_key", "pexels_key"]);

function lerAjustes() {
  let salvo = {};
  try { salvo = JSON.parse(fs.readFileSync(AJUSTES_PATH, "utf8")); } catch {}
  return { ...PADRAO, ...salvo };
}

function gravarAjustes(mudancas) {
  let salvo = {};
  try { salvo = JSON.parse(fs.readFileSync(AJUSTES_PATH, "utf8")); } catch {}
  for (const [k, v] of Object.entries(mudancas)) {
    if (!(k in PADRAO)) continue;                       // campo desconhecido nao entra
    if (v === null || v === "" || v === PADRAO[k]) delete salvo[k];  // volta ao padrao
    else salvo[k] = v;
  }
  fs.writeFileSync(AJUSTES_PATH, JSON.stringify(salvo, null, 2));
  return lerAjustes();
}

const mascara = (v) => (v && v.length > 4 ? "•••" + v.slice(-4) : v ? "•••" : "");

// O que o navegador pode ver: segredo vira mascara, resto vai inteiro.
// `padrao` diz quais campos ainda estao no valor de fabrica — e o que
// acende o "voltar ao padrao" so onde ele tem o que desfazer.
function ajustesParaTela() {
  const a = lerAjustes();
  let salvo = {};
  try { salvo = JSON.parse(fs.readFileSync(AJUSTES_PATH, "utf8")); } catch {}
  const fora = {};
  for (const k of Object.keys(PADRAO)) {
    fora[k] = SEGREDOS.has(k) ? mascara(a[k]) : a[k];
  }
  return { valores: fora, padrao: PADRAO, mexidos: Object.keys(salvo) };
}

// A chave pode vir daqui ou do ambiente. O arquivo ganha, porque foi o
// usuario que digitou; o env fica como saida para quem roda em servidor.
function chave(nome, envNome) {
  return (lerAjustes()[nome] || process.env[envNome] || "").trim();
}

// Qual python roda o motor.
//
// Antes isto era o caminho de UMA maquina, escrito por extenso — e o ambiente
// era o `openvoice_gpu2`, montado para clonagem de voz. O Klipe rodava
// emprestado ali, carregando torch, Coqui TTS e OpenVoice sem usar nada disso.
// Noutro PC, o caminho simplesmente nao existia.
//
// Agora a ordem e: o que a pessoa configurou > variavel de ambiente > o
// ambiente `klipe` nos lugares onde conda costuma instalar > o python do
// PATH. As dependencias estao em requirements.txt — seis pacotes, sem torch.
// Onde o instalador do Klipe poe o ffmpeg. Estava DENTRO do endpoint que
// instala — e o ffbin() aqui embaixo, que roda a cada spawn, estourava
// "FFMPEG_DIR is not defined". Escopo de modulo porque tem dois donos.
const FFMPEG_DIR = path.join(process.env.LOCALAPPDATA || require("os").homedir(),
                             "Klipe", "ffmpeg", "bin");

// Mesma ordem do motioncore/ffbin.py, e pelo mesmo motivo: oito spawns aqui
// chamavam "ffmpeg"/"ffprobe" pelo nome cru, contando com o PATH. Quem instala
// pelo botao de Configuracoes recebe o binario em %LOCALAPPDATA%\Klipe, que
// NAO entra no PATH — entao o Klipe instalava o ffmpeg e continuava sem achar.
function ffbin(nome) {
  const cfg = (lerAjustes()[`${nome}_path`] || "").trim();
  if (cfg && fs.existsSync(cfg)) return cfg;
  const irmao = (lerAjustes().ffmpeg_path || "").trim();
  if (irmao) {
    const cand = path.join(path.dirname(irmao), nome + path.extname(irmao));
    if (fs.existsSync(cand)) return cand;
  }
  for (const dir of [FFMPEG_DIR, "C:\ffmpeg\bin"]) {
    for (const ext of [".exe", ""]) {
      const cand = path.join(dir, nome + ext);
      if (fs.existsSync(cand)) return cand;
    }
  }
  return nome;   // erro diagnosticavel, nao caminho inventado
}

function pythonExe() {
  const escolhido = (lerAjustes().python_exe || "").trim() || process.env.PYTHON_EXE;
  if (escolhido) return escolhido;

  const lar = process.env.USERPROFILE || process.env.HOME || "";
  const candidatos = [
    path.join(lar, "anaconda3", "envs", "klipe", "python.exe"),
    path.join(lar, "miniconda3", "envs", "klipe", "python.exe"),
    path.join(lar, ".conda", "envs", "klipe", "python.exe"),
  ];
  for (const c of candidatos) if (fs.existsSync(c)) return c;
  // ultimo recurso: o que estiver no PATH. Se faltar dependencia, o script
  // reclama com nome de pacote — melhor que "arquivo nao encontrado" de um
  // caminho que so existia no computador de quem escreveu.
  return "python";
}

// ─── INSTRUCOES (os .md que dirigem a geracao) ──────────────────────────
// O arquivo de fabrica em motioncore/cena/ NUNCA e escrito. A edicao do
// usuario vai para config/instrucoes/<mesmo caminho>, e a leitura prefere a
// dele. "Voltar ao padrao" e apagar esse arquivo — o de fabrica sempre
// esteve la, intacto, entao nao ha como perder o original editando.
const DOCS_DIR = path.join(__dirname, "motioncore", "cena");
const DOCS_USER = path.join(__dirname, "config", "instrucoes");

// Aceita so .md dentro de motioncore/cena. Resolve antes de comparar para
// que "../../.." nao passe.
function docResolver(rel) {
  const limpo = String(rel || "").replace(/\\/g, "/").replace(/^\/+/, "");
  if (!limpo.endsWith(".md")) return null;
  const fabrica = path.resolve(DOCS_DIR, limpo);
  if (!fabrica.startsWith(path.resolve(DOCS_DIR) + path.sep)) return null;
  return { rel: limpo, fabrica, usuario: path.resolve(DOCS_USER, limpo) };
}

function docLer(rel) {
  const p = docResolver(rel);
  if (!p) return null;
  const editado = fs.existsSync(p.usuario);
  const alvo = editado ? p.usuario : p.fabrica;
  if (!fs.existsSync(alvo)) return null;
  return { rel: p.rel, texto: fs.readFileSync(alvo, "utf8"), editado };
}

// Varre a pasta em vez de manter uma lista: estilo novo aparece sozinho,
// que e o ponto — o catalogo cresce sem alguem lembrar de registrar.
function docsListar() {
  const achados = [];
  const anda = (dir, prefixo) => {
    let itens = [];
    try { itens = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
    for (const it of itens) {
      const rel = prefixo ? `${prefixo}/${it.name}` : it.name;
      if (it.isDirectory()) anda(path.join(dir, it.name), rel);
      else if (it.name.endsWith(".md")) {
        const d = docLer(rel);
        if (!d) continue;
        const h1 = /^#\s+(.+)$/m.exec(d.texto);
        achados.push({
          rel,
          titulo: h1 ? h1[1].trim() : rel,
          editado: d.editado,
          bytes: Buffer.byteLength(d.texto, "utf8"),
        });
      }
    }
  };
  anda(DOCS_DIR, "");
  return achados.sort((a, b) => a.rel.localeCompare(b.rel));
}

function docGravar(rel, texto) {
  const p = docResolver(rel);
  if (!p || !fs.existsSync(p.fabrica)) return false;
  fs.mkdirSync(path.dirname(p.usuario), { recursive: true });
  fs.writeFileSync(p.usuario, texto, "utf8");
  return true;
}

function docRestaurar(rel) {
  const p = docResolver(rel);
  if (!p) return false;
  if (fs.existsSync(p.usuario)) fs.unlinkSync(p.usuario);
  return true;
}

// Processo do MotionCore que desenha os titulos do preview. Sobe sozinho na
// primeira vez que alguem pede um quadro e fica de pe — a partida (skia +
// fontes) e o custo real, o desenho em si e barato.
const MC_PORTA = Number(process.env.MOTIONCORE_PORT) || 3011;
let _mcProc = null;
function _subirMotionCore() {
  if (_mcProc && !_mcProc.killed) return new Promise(r => setTimeout(r, 400));
  const py = pythonExe();
  _mcProc = spawn(py, ["-m", "motioncore.preview_server", String(MC_PORTA)],
                  { cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] });
  _mcProc.stdout.on("data", d => process.stdout.write("[MotionCore] " + d));
  _mcProc.stderr.on("data", d => process.stderr.write("[MotionCore] " + d));
  _mcProc.on("exit", (c) => { console.log(`[MotionCore] saiu (${c})`); _mcProc = null; });
  // espera o "ouvindo" aparecer, com teto — carregar o skia leva alguns segundos
  return new Promise((ok) => {
    const t0 = Date.now();
    const olha = (d) => { if (String(d).includes("ouvindo")) { _mcProc.stdout.off("data", olha); ok(); } };
    _mcProc.stdout.on("data", olha);
    const tick = setInterval(() => {
      if (Date.now() - t0 > 30000 || !_mcProc) { clearInterval(tick); ok(); }
    }, 500);
  });
}
process.on("exit", () => { if (_mcProc) try { _mcProc.kill(); } catch {} });

// Jobs do OMNI em andamento. TEM que viver aqui fora: o handler roda uma vez
// por request, entao um Map declarado la dentro nasceria vazio no /status e
// todo job voltaria como "desconhecido".
const _omniJobs = new Map();

// Rotas que NAO exigem sessao (login page, endpoints de auth, favicon).
const PUBLIC_ROUTES = new Set(["/login", "/auth/login", "/auth/logout", "/auth/me", "/favicon.ico"]);

// Le body JSON de request POST. Retorna promise.
function readJsonBody(req) {
  return new Promise((resolve) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      try { resolve(JSON.parse(body || "{}")); } catch { resolve(null); }
    });
  });
}

// ─── QUAL CONFIG ESTA REQUISICAO ESTA EDITANDO ──────────────────────────
// Ate aqui existia UM edit_config.json para o sistema inteiro, e abrir um
// projeto COPIAVA o dele por cima desse arquivo. Com duas abas abertas isso
// e uma bomba: a aba 2 troca o que a aba 1 esta editando, e o save da aba 1
// grava por cima do projeto da aba 2 — calado, sem nada na tela.
//
// Agora o projeto viaja na requisicao (?projeto=slug ou cabecalho X-Projeto)
// e cada aba le e grava o arquivo DELA. Sem slug, cai no global de antes —
// e o que mantem funcionando tudo que ja existia.
function slugSeguro(s) {
  if (!s) return null;
  const limpo = String(s).replace(/[^a-zA-Z0-9._-]/g, "");   // sem barra, sem ".."
  return limpo && limpo !== "." && limpo !== ".." ? limpo : null;
}

function caminhoConfig(slug) {
  const s = slugSeguro(slug);
  if (!s) return CONFIG_PATH;
  const p = path.join(PUBLIC_DIR, "projects", s, "edit_config.json");
  if (fs.existsSync(p)) return p;

  // Slug pedido que NAO existe caía no config global, calado. O resultado era
  // a mesma armadilha do caminho-vs-query: a URL diz um projeto, os dados sao
  // de outro, e um salvar depois grava no lugar errado. Acontece com pasta que
  // tem midia mas nao e projeto (ex.: uma pasta so de b-roll), com link antigo
  // e com erro de digitacao.
  //
  // Continua devolvendo o global — mudar isso agora quebraria quem depende do
  // fallback —, mas para de ser silencioso.
  console.log(`[Klipe] projeto "${s}" nao tem edit_config.json; usando o config global. `
            + `Se era para abrir um projeto, confira o nome em /api/projects.`);
  return CONFIG_PATH;
}

// Tres portas, em ordem de precedencia:
//   1. /p/<slug>          — a URL que a pessoa cola numa aba nova
//   2. ?projeto=<slug>    — compatibilidade (e o ?project= antigo)
//   3. X-Projeto          — o que o editor manda em toda chamada de API,
//                           porque /api/... nao carrega o /p/<slug> no caminho
function projetoDaReq(url, req) {
  const naRota = /^\/p\/([a-zA-Z0-9._-]+)\/?$/.exec(url.pathname);
  const doPath = naRota && naRota[1];
  const daQuery = url.searchParams.get("projeto") || url.searchParams.get("project");

  // Caminho e query discordando e sintoma de URL montada errado, e o estrago e
  // GRAVE: a aba carrega um projeto e grava no outro, calada. Aconteceu de
  // verdade — "abrir projeto" navegava para `<caminho antigo>?project=<novo>`,
  // e o config de um projeto foi sobrescrito com o conteudo de outro, duas
  // vezes. A navegacao foi corrigida para /p/<slug>; isto aqui e a tranca:
  // se voltar a acontecer, aparece no log em vez de comer o arquivo.
  if (doPath && daQuery && doPath !== daQuery) {
    console.log(`[Klipe] URL contraditoria: caminho diz "${doPath}", query diz "${daQuery}". `
              + `Usando o caminho. Se a intencao era abrir "${daQuery}", va para /p/${daQuery}.`);
  }
  return slugSeguro(doPath || daQuery || req.headers["x-projeto"]);
}

function readConfig() {
  return JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));
}

function revisaoConfig(alvo) {
  try {
    return crypto.createHash("sha1").update(fs.readFileSync(alvo)).digest("hex").slice(0, 16);
  } catch {
    return null;
  }
}

// Nome proprio porque o handler sombreia `writeConfig` com uma versao que ja
// sabe o projeto; de la dentro nao da pra alcancar a de fora pelo mesmo nome.
function gravarConfig(data, alvo = CONFIG_PATH) {
  // ─── TRANCA DE IDENTIDADE ───────────────────────────────────────────
  // Um projeto foi sobrescrito com o conteudo de outro DUAS vezes, e os dois
  // consertos anteriores foram por hipotese — nao pegaram a causa. Nao consegui
  // reproduzir ao vivo, entao paro de adivinhar: em vez de tapar o caminho que
  // eu imagino, o arquivo passa a saber de quem ele e.
  //
  // Cada config carrega `projectName`. Se chega uma gravacao dizendo ser de
  // outro projeto, ela e RECUSADA — venha de onde vier, por qualquer caminho,
  // incluindo os que eu ainda nao conheco.
  const donoDaPasta = alvo === CONFIG_PATH ? null : path.basename(path.dirname(alvo));
  if (donoDaPasta) {
    const donoDoDado = data && data.projectName;
    if (donoDoDado && donoDoDado !== donoDaPasta) {
      console.log(`[Klipe] RECUSADO: tentaram gravar dados de "${donoDoDado}" `
                + `dentro de "${donoDaPasta}". Nada foi escrito.`);
      const erro = new Error(`config de "${donoDoDado}" nao pode ser gravado em "${donoDaPasta}"`);
      erro.codigo = "DONO_ERRADO";
      throw erro;
    }
    // Carimba o dono. Config antigo sem carimbo ganha o dele agora, e da
    // proxima vez a tranca ja funciona para ele tambem.
    data.projectName = donoDaPasta;
  }

  // RASTRO DE ESCRITA. Um projeto foi sobrescrito com o conteudo de outro duas
  // vezes, e os consertos por hipotese nao pegaram a causa. Isto registra QUEM
  // gravou O QUE e ONDE, para o proximo caso apontar o culpado em vez de me
  // fazer adivinhar de novo.
  try {
    const anterior = fs.existsSync(alvo) ? JSON.parse(fs.readFileSync(alvo, "utf8")) : {};
    const de = String(anterior.videoSrc || "-"), para = String(data.videoSrc || "-");
    const legDe = (anterior.captions || []).length, legPara = (data.captions || []).length;
    if (de !== para || legPara < legDe) {
      console.log(`[Klipe/config] ${path.basename(path.dirname(alvo))}: `
                + `videoSrc "${de}" -> "${para}", legendas ${legDe} -> ${legPara}`
                + `${legPara < legDe ? "  <-- PERDA" : ""}`);
    }
  } catch (e) { /* o rastro nunca pode impedir a gravacao */ }
  // Auto-backup ANTES de sobrescrever: preserva o estado atual com timestamp
  // Mantem ate 20 backups mais recentes (rotaciona auto)
  // O backup vai para uma pasta POR ARQUIVO: com varios projetos, um sozinho
  // que salvasse 20 vezes expulsaria os backups de todos os outros.
  try {
    if (fs.existsSync(alvo)) {
      const dono = alvo === CONFIG_PATH ? "_ativo" : path.basename(path.dirname(alvo));
      const backupDir = path.join(PUBLIC_DIR, ".config_backups", dono);
      if (!fs.existsSync(backupDir)) fs.mkdirSync(backupDir, { recursive: true });
      const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
      const backupPath = path.join(backupDir, `edit_config_${ts}.json`);
      fs.copyFileSync(alvo, backupPath);
      // Rotaciona: mantem so os 20 mais recentes
      const backups = fs.readdirSync(backupDir)
        .filter(f => f.startsWith("edit_config_") && f.endsWith(".json"))
        .sort();
      while (backups.length > 20) {
        try { fs.unlinkSync(path.join(backupDir, backups.shift())); } catch {}
      }
    }
  } catch (e) {
    console.error("[Backup] WARN:", e.message);
  }
  fs.mkdirSync(path.dirname(alvo), { recursive: true });
  fs.writeFileSync(alvo, JSON.stringify(data, null, 2), "utf-8");
}

// Remove /public/ or public/ prefix from paths so staticFile() doesn't throw
// "value is already prefixed with static base /public"
function stripPub(p) {
  if (!p || typeof p !== "string") return p;
  return p.replace(/^\/?public\//, "");
}

// List available b-roll files — scoped to active project folder + public/ root.
// When activeVideoSrc is provided (e.g. "projects/niveis-suporte-adulta/video_preview.mp4"),
// only that project's b-rolls are shown. Keeps media library clean per-project.
function listBrolls(activeVideoSrc) {
  const brolls = [];
  // A raiz de public/ NAO e mais varrida. Ela era lida sempre, entao qualquer
  // `broll_*.mp4` largado ali aparecia na biblioteca de TODOS os projetos —
  // um b-roll fantasma que ninguem usava e que seguia a pessoa de projeto em
  // projeto. Contradizia o proprio comentario acima ("clean per-project").
  // Agora b-roll mora na pasta do projeto a que pertence, e ponto.
  // Determine active project folder from videoSrc
  let activeProjName = null;
  if (activeVideoSrc && activeVideoSrc.includes("/")) {
    const parts = activeVideoSrc.split("/");
    if (parts[0] === "projects" && parts.length >= 2) activeProjName = parts[1];
  }
  // Scan project + project/brolls/ subfolders — active project se conhecido, senao todos
  const projRoot = path.join(PUBLIC_DIR, "projects");
  if (fs.existsSync(projRoot)) {
    const projsToScan = activeProjName ? [activeProjName] : fs.readdirSync(projRoot);
    for (const proj of projsToScan) {
      const projDir = path.join(projRoot, proj);
      if (!fs.existsSync(projDir) || !fs.statSync(projDir).isDirectory()) continue;
      // Root of project
      for (const f of fs.readdirSync(projDir)) {
        if (f.startsWith("broll_") && f.endsWith(".mp4")) {
          brolls.push(`projects/${proj}/${f}`);
        }
      }
      // gravacoes/ — o que a pessoa gravou pela barra de gravacao. Entra na
      // mesma lista de midia: gravar e so o comeco, o que ela quer e cortar e
      // posicionar isso na edicao, e para isso o arquivo precisa APARECER.
      const gravDir = path.join(projDir, "gravacoes");
      if (fs.existsSync(gravDir) && fs.statSync(gravDir).isDirectory()) {
        for (const f of fs.readdirSync(gravDir)) {
          if (f.endsWith(".mp4")) brolls.push(`projects/${proj}/gravacoes/${f}`);
        }
      }

      // brolls/ subfolder (download_brolls.py salva ai)
      const brollsSubDir = path.join(projDir, "brolls");
      if (fs.existsSync(brollsSubDir) && fs.statSync(brollsSubDir).isDirectory()) {
        for (const f of fs.readdirSync(brollsSubDir)) {
          if (f.endsWith(".mp4")) {
            brolls.push(`projects/${proj}/brolls/${f}`);
          }
        }
      }
    }
  }
  return brolls.sort();
}

// List available music files (legacy music_*.ext in root + categorized public/music/*/ or public/music/*.ext)
function listMusic() {
  const out = [];
  for (const f of fs.readdirSync(PUBLIC_DIR)) {
    if (f.startsWith("music_") && /\.(mp3|wav|ogg)$/i.test(f)) out.push(f);
  }
  const musicRoot = path.join(PUBLIC_DIR, "music");
  if (fs.existsSync(musicRoot)) {
    for (const entry of fs.readdirSync(musicRoot)) {
      const full = path.join(musicRoot, entry);
      if (fs.statSync(full).isDirectory()) {
        for (const f of fs.readdirSync(full)) {
          if (/\.(mp3|wav|ogg)$/i.test(f)) out.push({ src: `music/${entry}/${f}`, name: f, category: entry });
        }
      } else if (/\.(mp3|wav|ogg)$/i.test(entry)) {
        out.push({ src: `music/${entry}`, name: entry, category: "geral" });
      }
    }
  }
  return out;
}

// List available SFX files — scans public/ root + public/sfx/ categorized subfolders
function listSfx() {
  const out = [];
  // Scan public/ root for legacy sfx_*.ext files
  for (const f of fs.readdirSync(PUBLIC_DIR)) {
    if (f.startsWith("sfx_") && /\.(mp3|wav|ogg)$/i.test(f)) out.push(f);
  }
  // Scan public/sfx/ categorized subfolders
  const sfxRoot = path.join(PUBLIC_DIR, "sfx");
  if (fs.existsSync(sfxRoot)) {
    for (const cat of fs.readdirSync(sfxRoot)) {
      const catDir = path.join(sfxRoot, cat);
      if (!fs.statSync(catDir).isDirectory()) continue;
      for (const f of fs.readdirSync(catDir)) {
        if (/\.(mp3|wav|ogg)$/i.test(f)) {
          out.push({ src: `sfx/${cat}/${f}`, name: f, category: cat });
        }
      }
    }
  }
  return out.sort((a, b) => {
    const an = typeof a === "string" ? a : a.name;
    const bn = typeof b === "string" ? b : b.name;
    return an.localeCompare(bn);
  });
}

// List ambient/other audio files
function listAmbient() {
  return fs.readdirSync(PUBLIC_DIR)
    .filter(f => f.startsWith("ambient_") && /\.(mp3|wav|ogg)$/i.test(f))
    .sort();
}

// Erro nao tratado DENTRO de uma requisicao deixava a resposta pendurada: o
// navegador ficava carregando pra sempre e nada no log dizia por que. Agora
// vira 500 com o motivo, e o servidor segue vivo para a proxima.
function comRede(handler) {
  return async (req, res) => {
    try {
      await handler(req, res);
    } catch (e) {
      console.error(`[Klipe] erro em ${req.method} ${req.url}:`, e);
      if (!res.headersSent) {
        res.writeHead(500, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: e.message || String(e) }));
      } else {
        res.end();
      }
    }
  };
}

const server = http.createServer(comRede(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  // Resolve UMA vez por requisicao qual config esta em jogo, e sombreia as
  // duas funcoes do modulo. As ~29 chamadas de readConfig()/writeConfig()
  // espalhadas pelo handler passam a falar com o arquivo do projeto certo
  // sem precisar receber o slug uma por uma — e sem chance de esquecer uma,
  // que e como abas cruzadas comeriam o trabalho uma da outra.
  const _projeto = projetoDaReq(url, req);
  const _configPath = caminhoConfig(_projeto);
  const readConfig = () => JSON.parse(fs.readFileSync(_configPath, "utf-8"));
  const writeConfig = (data) => gravarConfig(data, _configPath);

  // CORS restrito a origens locais.
  //
  // Era "*". Com o servidor lendo e gravando arquivo no disco, isso
  // significava que QUALQUER site aberto no navegador podia chamar
  // http://127.0.0.1:3002 por JavaScript e LER a resposta - o bind em
  // 127.0.0.1 impede a rede, mas nao impede a aba do lado.
  //
  // O front do Klipe e mesma-origem e nao usa CORS para nada (conferido:
  // nenhuma busca cross-origin no editor.html nem no klipe_player.js).
  // Refletir so localhost mantem ferramenta local funcionando e corta o resto.
  const _origem = req.headers.origin || "";
  if (/^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/.test(_origem)) {
    res.setHeader("Access-Control-Allow-Origin", _origem);
    res.setHeader("Vary", "Origin");
  }
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type,Authorization");
  res.setHeader("Access-Control-Allow-Credentials", "true");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }

  // ─── Auth endpoints (publicos) ────────────────────────────────────────
  if (url.pathname === "/auth/login" && req.method === "POST") {
    const body = await readJsonBody(req);
    if (!body) { res.writeHead(400, {"Content-Type":"application/json"}); return res.end('{"error":"bad_json"}'); }
    const user = auth.findByUsername(body.username);
    if (!user || !auth.verifyPassword(user, body.password)) {
      res.writeHead(401, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ ok: false, error: "invalid_credentials" }));
    }
    const s = auth.createSession(user.id);
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Set-Cookie": auth.sessionCookieHeader(s.token, s.expiresAt),
    });
    return res.end(JSON.stringify({ ok: true, user: auth.publicUser(user) }));
  }
  if (url.pathname === "/auth/logout" && req.method === "POST") {
    const cookies = auth.parseCookies(req);
    auth.deleteSession(cookies[auth.SESSION_COOKIE]);
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Set-Cookie": auth.clearSessionCookieHeader(),
    });
    return res.end(JSON.stringify({ ok: true }));
  }
  if (url.pathname === "/auth/me" && req.method === "GET") {
    const u = auth.getRequestUser(req);
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify({ user: u ? auth.publicUser(u) : null }));
  }
  if (url.pathname === "/login" && req.method === "GET") {
    const loginPath = path.join(__dirname, "login.html");
    if (fs.existsSync(loginPath)) {
      res.writeHead(200, {"Content-Type":"text/html; charset=utf-8"});
      return res.end(fs.readFileSync(loginPath, "utf-8"));
    }
    res.writeHead(500); return res.end("login.html not found");
  }

  // Admin: painel de usuarios (apenas admin logado)
  if (url.pathname === "/admin/users" && req.method === "GET") {
    const user = auth.getRequestUser(req);
    if (!user) { res.writeHead(302, { Location: "/login" }); return res.end(); }
    if (user.role !== "admin") { res.writeHead(403, {"Content-Type":"text/plain"}); return res.end("Somente admins."); }
    const p = path.join(__dirname, "admin-users.html");
    if (fs.existsSync(p)) {
      res.writeHead(200, {"Content-Type":"text/html; charset=utf-8"});
      return res.end(fs.readFileSync(p, "utf-8"));
    }
    res.writeHead(500); return res.end("admin-users.html not found");
  }

  // Pipeline interna (forge_render/build_davinci chamam do proprio host):
  // sync do bundle liberado SO pra loopback — sem isso o render leva 401 e o
  // Root.tsx pode ficar com duracao de outro projeto.
  const _remote = req.socket && req.socket.remoteAddress;
  const _isLoopback = _remote === "127.0.0.1" || _remote === "::1" || _remote === "::ffff:127.0.0.1";
  const _internalRoute = false;   // era a excecao do /api/sync (removido), que saiu

  // ─── Sem login (pedido do user, 05/08) ──────────────────────────────
  // O que protegia o editor era a sessao. Com ela fora, quem segura e o
  // BIND EM 127.0.0.1 la embaixo: o servidor le e grava arquivo, roda ffmpeg
  // e abre pasta, entao ele nao pode ficar alcancavel pela rede.
  //
  // Se um dia precisar expor pra outra maquina (tunnel, celular, outro PC),
  // o login TEM que voltar junto — ou vira acesso irrestrito ao disco.
  if (!_isLoopback && !_internalRoute) {
    res.writeHead(403, {"Content-Type":"text/plain; charset=utf-8"});
    return res.end("O Klipe roda sem login e por isso so aceita conexao local.");
  }
  req.user = auth.getRequestUser(req) || { username: "local", role: "admin" };

  // ─── Admin: CRUD de users ────────────────────────────────────────────
  if (url.pathname === "/api/admin/users" && req.method === "GET") {
    if (req.user.role !== "admin") { res.writeHead(403); return res.end('{"error":"forbidden"}'); }
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify({ users: auth.listUsers() }));
  }
  if (url.pathname === "/api/admin/users" && req.method === "POST") {
    if (req.user.role !== "admin") { res.writeHead(403); return res.end('{"error":"forbidden"}'); }
    const body = await readJsonBody(req);
    if (!body) { res.writeHead(400); return res.end('{"error":"bad_json"}'); }
    try {
      const u = auth.createUser({
        username: body.username,
        password: body.password,
        role: body.role || "member",
        displayName: body.displayName || null,
      });
      res.writeHead(200, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ ok: true, user: auth.publicUser(u) }));
    } catch (e) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ ok: false, error: e.message }));
    }
  }
  const delUserMatch = url.pathname.match(/^\/api\/admin\/users\/([a-z0-9]+)$/i);
  if (delUserMatch && req.method === "DELETE") {
    if (req.user.role !== "admin") { res.writeHead(403); return res.end('{"error":"forbidden"}'); }
    const targetId = delUserMatch[1];
    if (targetId === req.user.id) { res.writeHead(400); return res.end('{"error":"cant_delete_self"}'); }
    // Nao deixa deletar ultimo admin
    const target = auth.findById(targetId);
    if (target && target.role === "admin" && auth.countActiveAdmins() <= 1) {
      res.writeHead(400); return res.end('{"error":"last_admin"}');
    }
    auth.deleteUser(targetId);
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify({ ok: true }));
  }

  // ─── PREVIA DE AUDIO: aplica a EQ do clip num trecho curto pra ouvir ──
  // A EQ so existe no render (ffmpeg). Sem isso o user mexe no slider e nao
  // ouve nada, parecendo que a funcao esta quebrada.
  if (url.pathname === "/api/audio/previa" && req.method === "POST") {
    try {
      const b = await readJsonBody(req);
      const cfg = readConfig();
      const src = path.join(__dirname, "public", cfg.videoSrc);
      const t0 = Math.max(0, Number(b.startSec) || 0);
      const dur = Math.min(20, Math.max(3, Number(b.dur) || 12));
      const af = [];
      if (Number(b.treble)) af.push(`treble=g=${Number(b.treble)}:f=3000`);
      if (Number(b.mid)) af.push(`equalizer=f=1200:t=q:w=1.2:g=${Number(b.mid)}`);
      if (Number(b.bass)) af.push(`bass=g=${Number(b.bass)}:f=200`);
      if (Number(b.highpass)) af.push(`highpass=f=${Number(b.highpass)}`);
      if (Number(b.denoise)) af.push(`afftdn=nr=${Number(b.denoise)}:nf=-25`);
      if (b.loudnorm) af.push("loudnorm=I=-16:TP=-1.5:LRA=11");
      const outDir = path.join(__dirname, "public", ".previa");
      if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
      const nome = `previa_${Date.now()}.m4a`;
      const args = ["-y", "-v", "error", "-ss", String(t0), "-t", String(dur), "-i", src, "-vn"];
      if (af.length) args.push("-af", af.join(","));
      args.push("-c:a", "aac", "-b:a", "192k", path.join(outDir, nome));
      const child = spawn(ffbin("ffmpeg"), args);
      child.on("close", (code) => {
        // limpa previas antigas pra nao acumular
        try {
          for (const f of fs.readdirSync(outDir)) {
            if (f !== nome && Date.now() - fs.statSync(path.join(outDir, f)).mtimeMs > 300e3) {
              fs.unlinkSync(path.join(outDir, f));
            }
          }
        } catch {}
        res.writeHead(code === 0 ? 200 : 500, {"Content-Type":"application/json"});
        res.end(JSON.stringify(code === 0 ? { ok: true, url: `/.previa/${nome}` } : { error: "ffmpeg falhou" }));
      });
      return;
    } catch (e) {
      res.writeHead(500, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: e.message }));
    }
  }

  // ─── TRACK DE CORTE: detectar (propoe) e aplicar (commita) ──────────
  if ((url.pathname === "/api/cortes/detectar" || url.pathname === "/api/cortes/aplicar")
      && req.method === "POST") {
    const acao = url.pathname.endsWith("detectar") ? "detectar" : "aplicar";
    const py = pythonExe();
    console.log(`[Cortes] ${acao}...`);
    const child = spawn(py, ["cortes_track.py", acao], { cwd: __dirname });
    let out = "", err = "";
    child.stdout.on("data", d => { out += d; });
    child.stderr.on("data", d => { err += d; });
    child.on("close", (code) => {
      let j = null;
      // a ultima linha JSON e o resultado (o resto e log do whisper/ffmpeg)
      for (const ln of out.trim().split("\n").reverse()) {
        try { j = JSON.parse(ln.trim()); break; } catch {}
      }
      if (code !== 0 || !j) {
        res.writeHead(500, {"Content-Type":"application/json"});
        return res.end(JSON.stringify({ error: (err || out).slice(-400) || "falhou" }));
      }
      console.log(`[Cortes] ${acao} OK`);
      res.writeHead(200, {"Content-Type":"application/json"});
      res.end(JSON.stringify(j));
    });
    return;
  }

  // ─── CONFIGURACOES ──────────────────────────────────────────────────
  if (url.pathname === "/api/ajustes" && req.method === "GET") {
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify(ajustesParaTela()));
  }

  if (url.pathname === "/api/ajustes" && req.method === "POST") {
    let corpo = "";
    req.on("data", c => corpo += c);
    req.on("end", () => {
      try {
        const m = JSON.parse(corpo || "{}");
        // A mascara ("•••1234") e o que o GET devolveu. Se ela voltar sem o
        // usuario ter digitado nada, e o campo intocado — gravar isso apagaria
        // a chave e trocaria por lixo.
        //
        // O teste e "contem bolinha", nao "comeca com •••": chave de API nunca
        // tem esse caractere, entao qualquer valor com ele so pode ser mascara
        // voltando. Casar o prefixo exato quebra no dia em que a mascara mudar
        // de formato — e o estrago seria apagar a chave do usuario.
        for (const k of SEGREDOS) {
          if (typeof m[k] === "string" && m[k].includes("•")) delete m[k];
        }
        gravarAjustes(m);
        res.writeHead(200, {"Content-Type":"application/json"});
        res.end(JSON.stringify(ajustesParaTela()));
      } catch (e) {
        res.writeHead(400, {"Content-Type":"application/json"});
        res.end(JSON.stringify({ erro: e.message }));
      }
    });
    return;
  }

  if (url.pathname === "/api/gastos" && req.method === "GET") {
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify(custos.resumo()));
  }

  if (url.pathname === "/api/ajustes/restaurar" && req.method === "POST") {
    try { fs.unlinkSync(AJUSTES_PATH); } catch {}
    try { fs.rmSync(DOCS_USER, { recursive: true, force: true }); } catch {}
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify(ajustesParaTela()));
  }

  // ─── FFMPEG: onde esta, e instalar se nao houver ──────────────────────
  // Portado do VTrans Pro (server.py:/api/ffmpeg/install), com uma mudanca
  // que importa: la o destino era C:\ffmpeg, que nesta maquina exige
  // ADMINISTRADOR (testado: OSError sem elevacao) — ou dispara UAC ou falha
  // calado. Aqui vai pra %LOCALAPPDATA%\Klipe\ffmpeg, onde ninguem precisa
  // de permissao. O resolvedor (motioncore/ffbin.py) procura la primeiro.

  if (url.pathname === "/api/ffmpeg/status" && req.method === "GET") {
    const p = spawn(pythonExe(), ["-c",
      "import json,sys;sys.path.insert(0,r'" + __dirname.replace(/\\/g, "\\\\") + "');"
      + "from motioncore.ffbin import diagnostico;print(json.dumps(diagnostico()))"]);
    let saida = "", erro = "";
    p.stdout.on("data", d => saida += d);
    p.stderr.on("data", d => erro += d);
    p.on("error", (e) => {
      res.writeHead(200, {"Content-Type":"application/json"});
      res.end(JSON.stringify({ erro: e.message }));
    });
    p.on("close", () => {
      if (res.headersSent) return;
      res.writeHead(200, {"Content-Type":"application/json"});
      try { res.end(JSON.stringify({ ...JSON.parse(saida.trim().split("\n").pop()), destino: FFMPEG_DIR })); }
      catch { res.end(JSON.stringify({ erro: (erro || "falhou").slice(-300), destino: FFMPEG_DIR })); }
    });
    return;
  }

  if (url.pathname === "/api/ffmpeg/install" && req.method === "POST") {
    if (process.platform !== "win32") {
      res.writeHead(200, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ ok: false,
        erro: "instalador automatico so existe no Windows — no Linux use o gerenciador "
            + "de pacotes (apt install ffmpeg), no macOS brew install ffmpeg" }));
    }
    // Console PROPRIO e visivel: sao ~100 MB de download e alguns minutos.
    // Rodar escondido deixaria a pessoa achando que travou — foi por isso que
    // o VTrans Pro tambem abre janela.
    const bat = [
      "@echo off",
      "title Klipe - instalando FFmpeg",
      `set "DEST=${FFMPEG_DIR}"`,
      'if exist "%DEST%\\ffmpeg.exe" (echo FFmpeg ja esta instalado aqui: & echo   %DEST% & echo. & "%DEST%\\ffmpeg.exe" -version & pause & exit /b)',
      "echo Baixando FFmpeg (~100 MB). Pode levar alguns minutos...",
      'set "URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"',
      'set "ZIP=%TEMP%\\klipe_ffmpeg.zip"',
      'set "XDIR=%TEMP%\\klipe_ffmpeg_tmp"',
      `powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%'"`,
      "if errorlevel 1 (echo. & echo FALHOU o download. Verifique a internet. & pause & exit /b 1)",
      "echo Extraindo...",
      `powershell -NoProfile -Command "Expand-Archive -Force '%ZIP%' -DestinationPath '%XDIR%'"`,
      'mkdir "%DEST%" 2>nul',
      'for /D %%D in ("%XDIR%\\ffmpeg-*") do (xcopy "%%D\\bin\\*" "%DEST%\\" /E /I /Y >nul)',
      'del "%ZIP%" >nul 2>&1 & rd /s /q "%XDIR%" >nul 2>&1',
      'if not exist "%DEST%\\ffmpeg.exe" (echo. & echo FALHOU a instalacao. & pause & exit /b 1)',
      "echo. & echo FFmpeg instalado em %DEST%",
      '"%DEST%\\ffmpeg.exe" -version | findstr /B "ffmpeg version"',
      "echo. & echo Pode fechar esta janela e voltar ao Klipe.",
      "pause",
    ].join("\r\n");

    try {
      const bat_path = path.join(require("os").tmpdir(), `klipe_ffmpeg_${Date.now()}.bat`);
      fs.writeFileSync(bat_path, bat, "utf-8");
      spawn("cmd.exe", ["/c", "start", '""', bat_path], { detached: true, stdio: "ignore" }).unref();
      res.writeHead(200, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ ok: true, destino: FFMPEG_DIR,
        msg: "Instalador aberto numa janela separada. Quando terminar, clique em Verificar." }));
    } catch (e) {
      res.writeHead(200, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ ok: false, erro: e.message }));
    }
  }

  // Testa a GPU de verdade: encoda um quadro. A lista `ffmpeg -encoders` so
  // prova que o binario foi compilado com NVENC, nao que ha placa na maquina —
  // e o render inteiro falhando no fim e um jeito caro de descobrir isso.
  if (url.pathname === "/api/ajustes/testar-gpu" && req.method === "GET") {
    const codec = { h264: "h264_nvenc", h265: "hevc_nvenc", av1: "av1_nvenc" }[lerAjustes().codec] || "h264_nvenc";
    const p = spawn(ffbin("ffmpeg"), ["-hide_banner", "-loglevel", "error", "-f", "lavfi",
                             "-i", "color=c=black:s=320x240:d=0.1",
                             "-c:v", codec, "-f", "null", "-"]);
    let erro = "";
    p.stderr.on("data", d => erro += d);
    p.on("error", (e) => {
      res.writeHead(200, {"Content-Type":"application/json"});
      res.end(JSON.stringify({ ok: false, codec, erro: e.message }));
    });
    p.on("close", (code) => {
      if (res.headersSent) return;
      res.writeHead(200, {"Content-Type":"application/json"});
      res.end(JSON.stringify({
        ok: code === 0, codec,
        erro: code === 0 ? "" : (erro.trim().split("\n").pop() || `ffmpeg saiu ${code}`),
      }));
    });
    return;
  }

  // ─── INSTRUCOES (.md) ───────────────────────────────────────────────
  if (url.pathname === "/api/instrucoes" && req.method === "GET") {
    const rel = url.searchParams.get("f");
    if (!rel) {
      res.writeHead(200, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ docs: docsListar() }));
    }
    const d = docLer(rel);
    res.writeHead(d ? 200 : 404, {"Content-Type":"application/json"});
    return res.end(JSON.stringify(d || { erro: "nao encontrado" }));
  }

  if (url.pathname === "/api/instrucoes" && req.method === "POST") {
    let corpo = "";
    req.on("data", c => corpo += c);
    req.on("end", () => {
      try {
        const { f, texto, restaurar } = JSON.parse(corpo || "{}");
        const ok = restaurar ? docRestaurar(f) : docGravar(f, String(texto ?? ""));
        if (!ok) { res.writeHead(400, {"Content-Type":"application/json"}); return res.end(JSON.stringify({ erro: "caminho invalido" })); }
        res.writeHead(200, {"Content-Type":"application/json"});
        res.end(JSON.stringify(docLer(f)));
      } catch (e) {
        res.writeHead(400, {"Content-Type":"application/json"});
        res.end(JSON.stringify({ erro: e.message }));
      }
    });
    return;
  }

  // ─── VEO 3: gerar broll por IA quando nao tem footage boa ───────────
  // Chave fica em klipe_settings.json (gemini_key) ou env GEMINI_API_KEY.
  // Fluxo: POST /api/veo/generate -> {operation} ; GET /api/veo/status?op=... ate done.
  const _klipeSettingsPath = AJUSTES_PATH;
  const _readKlipeSettings = lerAjustes;
  const _veoKey = () => chave("gemini_key", "GEMINI_API_KEY");

  if (url.pathname === "/api/veo/settings" && req.method === "GET") {
    const k = _veoKey();
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify({
      configured: !!k,
      hint: k ? "•••" + k.slice(-4) : "",
      model: _readKlipeSettings().veo_model || "veo-3.1-generate-preview",
    }));
  }

  if (url.pathname === "/api/veo/settings" && req.method === "POST") {
    const body = await readJsonBody(req);
    const cur = _readKlipeSettings();
    if (typeof body.gemini_key === "string" && body.gemini_key.trim()) cur.gemini_key = body.gemini_key.trim();
    if (typeof body.veo_model === "string" && body.veo_model.trim()) cur.veo_model = body.veo_model.trim();
    fs.writeFileSync(_klipeSettingsPath, JSON.stringify(cur, null, 2));
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify({ ok: true, configured: !!cur.gemini_key }));
  }

  if (url.pathname === "/api/veo/generate" && req.method === "POST") {
    const key = _veoKey();
    if (!key) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "Sem chave Gemini. Configure em Ajustes > Veo (a chave e sua, fica so nesta maquina)." }));
    }
    const body = await readJsonBody(req);
    const prompt = (body.prompt || "").trim();
    if (!prompt) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "prompt vazio" }));
    }
    const model = body.model || _readKlipeSettings().veo_model || "veo-3.1-generate-preview";
    const aspect = body.aspectRatio || "9:16";
    try {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:predictLongRunning`, {
        method: "POST",
        headers: { "x-goog-api-key": key, "Content-Type": "application/json" },
        body: JSON.stringify({ instances: [{ prompt }], parameters: { aspectRatio: aspect } }),
      });
      const j = await r.json();
      if (!r.ok || !j.name) {
        res.writeHead(r.ok ? 500 : r.status, {"Content-Type":"application/json"});
        return res.end(JSON.stringify({ error: (j.error && j.error.message) || "falha ao iniciar geracao", detail: j }));
      }
      console.log(`[Veo] gerando (${model}, ${aspect}): "${prompt.slice(0, 70)}"`);
      // Anota aqui, e nao no /status: a cobranca acontece por ter pedido a
      // geracao. Se anotassemos so quando o video chega, uma operacao que
      // falha no meio sairia do livro tendo custado igual.
      const _g = custos.registrar({
        tipo: "veo", modelo: model, segundos: custos.VEO_SEG_PADRAO,
        projeto: _projeto || "", ajustes: lerAjustes(),
      });
      res.writeHead(200, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ operation: j.name, gasto: _g }));
    } catch (e) {
      res.writeHead(500, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: e.message }));
    }
  }

  if (url.pathname === "/api/veo/status" && req.method === "GET") {
    const key = _veoKey();
    const op = url.searchParams.get("op") || "";
    const project = (url.searchParams.get("project") || "").replace(/[^a-zA-Z0-9_-]/g, "");
    const nome = (url.searchParams.get("name") || "veo").replace(/[^a-zA-Z0-9_-]/g, "") || "veo";
    if (!key || !op) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "faltou chave ou operation" }));
    }
    try {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/${op}`, {
        headers: { "x-goog-api-key": key },
      });
      const j = await r.json();
      if (!j.done) {
        res.writeHead(200, {"Content-Type":"application/json"});
        return res.end(JSON.stringify({ done: false }));
      }
      if (j.error) {
        res.writeHead(200, {"Content-Type":"application/json"});
        return res.end(JSON.stringify({ done: true, error: j.error.message || "geracao falhou" }));
      }
      // Extrai o video (uri assinada OU base64, dependendo do modelo)
      const resp = j.response || {};
      const sample = (resp.generateVideoResponse && resp.generateVideoResponse.generatedSamples &&
                      resp.generateVideoResponse.generatedSamples[0])
                  || (resp.generatedVideos && resp.generatedVideos[0]) || {};
      const vid = sample.video || {};
      const destDir = project
        ? path.join(__dirname, "public", "projects", project, "brolls")
        : path.join(__dirname, "public", "brolls");
      fs.mkdirSync(destDir, { recursive: true });
      const stamp = String(Date.now()).slice(-6);
      const fname = `veo_${nome}_${stamp}.mp4`;
      const dest = path.join(destDir, fname);

      if (vid.uri) {
        const vr = await fetch(vid.uri, { headers: { "x-goog-api-key": key } });
        if (!vr.ok) throw new Error("download do video falhou: HTTP " + vr.status);
        fs.writeFileSync(dest, Buffer.from(await vr.arrayBuffer()));
      } else if (vid.videoBytes || vid.bytesBase64Encoded) {
        fs.writeFileSync(dest, Buffer.from(vid.videoBytes || vid.bytesBase64Encoded, "base64"));
      } else {
        res.writeHead(200, {"Content-Type":"application/json"});
        return res.end(JSON.stringify({ done: true, error: "resposta sem video", detail: resp }));
      }
      const rel = project ? `projects/${project}/brolls/${fname}` : `brolls/${fname}`;
      console.log(`[Veo] salvo: ${rel} (${(fs.statSync(dest).size/1e6).toFixed(1)} MB)`);
      res.writeHead(200, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ done: true, src: rel, file: fname }));
    } catch (e) {
      res.writeHead(500, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ done: true, error: e.message }));
    }
  }

  // ─── OMNI: manda um trecho curto pro Gemini editar de verdade ──────────
  // Diferente do Veo (que INVENTA um clipe do zero), o OMNI recebe o trecho
  // dela e devolve o MESMO trecho alterado: palavra na parede atras dela,
  // objeto trocado, luz mudada, roupa diferente.
  //
  // Medido em 03/08: 8s de video voltaram em 112s e 270s, mantendo os 8s
  // exatos e — o que importa — o TEMPO quadro a quadro (correlacao de
  // movimento 0.991 no lag zero). Por isso o audio original continua batendo
  // com a boca dela, e o resultado entra como broll (que e so imagem).
  //
  // Fluxo: POST /api/omni/editar -> {job} ; GET /api/omni/status?job=... ate done.
  const OMNI_MAX_S = 10;   // acima disso ele degrada/recusa

  // fetch() do Node corta em 300s (headersTimeout do undici) e a chamada
  // medida ja bateu 270s. Vai de https cru pra poder esperar mais.
  const _postLongo = (endpoint, headers, corpo, timeoutMs) => new Promise((ok, falhou) => {
    const https = require("https");
    const dados = Buffer.from(JSON.stringify(corpo));
    const u = new URL(endpoint);
    const r = https.request({
      hostname: u.hostname, path: u.pathname + u.search, method: "POST",
      headers: { ...headers, "Content-Length": dados.length },
    }, (resp) => {
      const pedacos = [];
      resp.on("data", (c) => pedacos.push(c));
      resp.on("end", () => {
        const txt = Buffer.concat(pedacos).toString("utf8");
        try { ok({ status: resp.statusCode, json: JSON.parse(txt) }); }
        catch { ok({ status: resp.statusCode, json: null, texto: txt.slice(0, 800) }); }
      });
    });
    r.setTimeout(timeoutMs, () => r.destroy(new Error(`OMNI nao respondeu em ${timeoutMs / 1000}s`)));
    r.on("error", falhou);
    r.end(dados);
  });

  // Varre a resposta atras do primeiro bloco de video. O formato e
  // steps[].content[] com {type:"video", mime_type, data(base64)}, mas o
  // modelo tambem devolve steps type:"thought" — por isso procura fundo.
  const _acharVideo = (o) => {
    if (Array.isArray(o)) { for (const x of o) { const v = _acharVideo(x); if (v) return v; } return null; }
    if (o && typeof o === "object") {
      if (o.type === "video" && typeof o.data === "string" && o.data.length > 5000) return o.data;
      for (const k of Object.keys(o)) { const v = _acharVideo(o[k]); if (v) return v; }
    }
    return null;
  };
  const _acharTexto = (o, saco = []) => {
    if (Array.isArray(o)) o.forEach((x) => _acharTexto(x, saco));
    else if (o && typeof o === "object") {
      for (const [k, v] of Object.entries(o)) {
        if (k === "text" && typeof v === "string") saco.push(v); else _acharTexto(v, saco);
      }
    }
    return saco;
  };

  // O formato pedido ao OMNI tem que seguir o VIDEO, nao ser chumbado. Estava
  // "9:16" fixo — num projeto 16:9 ele devolvia vertical e o resultado entrava
  // deitado na timeline. A lista e a que a API aceita; escolhe a mais proxima
  // da proporcao real em vez de adivinhar.
  function _proporcaoDoProjeto(w, h) {
    const alvo = (Number(w) || 1080) / (Number(h) || 1920);
    const opcoes = [["9:16", 9 / 16], ["16:9", 16 / 9], ["1:1", 1],
                    ["4:5", 4 / 5], ["3:4", 3 / 4], ["4:3", 4 / 3]];
    return opcoes.reduce((melhor, o) =>
      Math.abs(o[1] - alvo) < Math.abs(melhor[1] - alvo) ? o : melhor)[0];
  }

  async function _rodarOmni(job, { srcAbs, inicio, dur, instrucao, project, key,
                                   proporcao, alturaEnvio }) {
    const marca = (fase) => { const j = _omniJobs.get(job); if (j) j.fase = fase; };
    const tmp = path.join(require("os").tmpdir(), `omni_${job}.mp4`);
    try {
      marca("cortando o trecho");
      const alt = [480, 720, 1080].includes(Number(alturaEnvio)) ? Number(alturaEnvio) : 720;
      await new Promise((ok, no) => {
        // Altura do que se ENVIA. 720 e o padrao: o OMNI cobra por token de
        // video, e mais pixel de entrada nem sempre melhora a saida. 1080 fica
        // como opcao pra trecho com detalhe fino (texto na parede, textura).
        const c = spawn(ffbin("ffmpeg"), ["-y", "-hide_banner", "-loglevel", "error",
          "-ss", inicio.toFixed(3), "-i", srcAbs, "-t", dur.toFixed(3),
          "-vf", `scale=-2:${alt}`, "-c:v", "libx264", "-preset", "veryfast",
          "-crf", "26", "-c:a", "aac", "-movflags", "+faststart", tmp]);
        c.on("close", (code) => (code === 0 ? ok() : no(new Error("ffmpeg falhou ao cortar"))));
        c.on("error", no);
      });
      const bytes = fs.statSync(tmp).size;
      console.log(`[OMNI] trecho ${inicio.toFixed(2)}s +${dur.toFixed(1)}s = ${(bytes / 1e6).toFixed(2)} MB`);

      const _go = custos.registrar({
        tipo: "omni", modelo: "gemini-omni-flash-preview", segundos: dur,
        projeto: project || "", ajustes: lerAjustes(),
      });
      if (_go) {
        const j0 = _omniJobs.get(job);
        if (j0) j0.gasto = _go;
        console.log(`[OMNI] ${dur.toFixed(1)}s x US$ ${_go.tarifa}/s = US$ ${_go.custo.toFixed(2)}`);
      }
      marca("o OMNI esta editando (leva 2 a 5 min)");
      const t0 = Date.now();
      const { status, json, texto } = await _postLongo(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        { "x-goog-api-key": key, "Content-Type": "application/json" },
        {
          model: "models/gemini-omni-flash-preview",
          input: [{ type: "user_input", content: [
            { type: "video", data: fs.readFileSync(tmp).toString("base64"), mime_type: "video/mp4" },
            { type: "text", text: instrucao },
          ] }],
          response_format: { type: "video", aspect_ratio: proporcao || "9:16" },
        }, 900000);
      const seg = ((Date.now() - t0) / 1000).toFixed(0);
      if (!json) throw new Error(`resposta ilegivel (HTTP ${status}): ${texto || ""}`);
      if (status >= 400) throw new Error((json.error && json.error.message) || `HTTP ${status}`);

      const b64 = _acharVideo(json);
      if (!b64) {
        // Sem video = ele respondeu por escrito (recusa ou so descreveu).
        // Devolve o texto dele em vez de um erro generico.
        const fala = _acharTexto(json).join(" ").trim().slice(0, 300);
        throw new Error(fala ? `o OMNI respondeu por escrito em vez de editar: "${fala}"`
                             : "o OMNI nao devolveu video");
      }

      marca("salvando");
      const destDir = project
        ? path.join(__dirname, "public", "projects", project, "omni")
        : path.join(__dirname, "public", "omni");
      fs.mkdirSync(destDir, { recursive: true });
      const fname = `omni_${inicio.toFixed(1).replace(".", "_")}s_${String(Date.now()).slice(-6)}.mp4`;
      fs.writeFileSync(path.join(destDir, fname), Buffer.from(b64, "base64"));
      const rel = project ? `projects/${project}/omni/${fname}` : `omni/${fname}`;
      const mb = (fs.statSync(path.join(destDir, fname)).size / 1e6).toFixed(1);
      console.log(`[OMNI] pronto em ${seg}s: ${rel} (${mb} MB)`);
      _omniJobs.set(job, { done: true, src: rel, segundos: Number(seg), mb: Number(mb) });
    } catch (e) {
      console.error(`[OMNI] ${e.message}`);
      _omniJobs.set(job, { done: true, error: e.message });
    } finally {
      try { fs.unlinkSync(tmp); } catch {}
    }
  }

  if (url.pathname === "/api/omni/editar" && req.method === "POST") {
    const key = _veoKey();
    if (!key) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "Sem chave Gemini. Configure em Ajustes > Veo." }));
    }
    const body = await readJsonBody(req) || {};
    const inicio = Number(body.startSec), fim = Number(body.endSec);
    const instrucao = (body.instrucao || "").trim();
    if (!Number.isFinite(inicio) || !Number.isFinite(fim) || fim <= inicio) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "trecho invalido" }));
    }
    const dur = fim - inicio;
    if (dur > OMNI_MAX_S) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: `O trecho tem ${dur.toFixed(1)}s. O OMNI so aguenta ate ${OMNI_MAX_S}s — encurte a selecao.` }));
    }
    if (!instrucao) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "escreva o que voce quer que ele faca" }));
    }
    const cfg = readConfig();
    const srcAbs = path.join(PUBLIC_DIR, cfg.videoSrc || "");
    if (!cfg.videoSrc || !fs.existsSync(srcAbs)) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "video do projeto nao encontrado" }));
    }
    const project = (String(cfg.videoSrc).match(/^projects\/([^/]+)\//) || [])[1] || "";
    // A proporcao sai do PROJETO, nao do cliente — assim ela nunca diverge do
    // que o render vai montar. A altura de envio o usuario escolhe.
    const proporcao = _proporcaoDoProjeto(cfg.width, cfg.height);
    const alturaEnvio = Number(body.alturaEnvio) || 720;
    const job = crypto.randomBytes(6).toString("hex");
    _omniJobs.set(job, { done: false, fase: "comecando" });
    _rodarOmni(job, { srcAbs, inicio, dur, instrucao, project, key,
                      proporcao, alturaEnvio });
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify({ job, duracao: dur, proporcao, alturaEnvio }));
  }

  if (url.pathname === "/api/omni/status" && req.method === "GET") {
    const j = _omniJobs.get(url.searchParams.get("job") || "");
    if (!j) {
      res.writeHead(404, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ done: true, error: "job desconhecido" }));
    }
    if (j.done) _omniJobs.delete(url.searchParams.get("job"));
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify(j));
  }

  // ─── Preview de titulo desenhado pelo MotionCore ───────────────────────
  // Substitui O motor de navegador no preview SEM criar uma segunda implementacao dos
  // estilos: quem desenha aqui e o mesmo codigo que desenha no render final.
  //
  // O MotionCore vive num processo Python separado porque o caro dele e a
  // PARTIDA (importar skia + registrar fontes). De pe, cada quadro sai em
  // ~48ms; um script por clique pagaria a partida a cada mexida de slider.
  // /frame = UM quadro em PNG, pra mexer em slider (114ms).
  // /clip  = o titulo inteiro num MP4 que o <video> toca, pra REPRODUZIR.
  //          Cacheado por conteudo; leva de 4s a ~80s dependendo do estilo.
  // /thumb = miniatura da galeria de templates, PNG guardado em disco.
  // Quanto da tira de legenda ja foi desenhada. Conexao propria: o POST da
  // tira fica preso ate o fim, entao a barra tem que perguntar por fora.
  if (url.pathname === "/api/preview/legenda/progresso" && req.method === "GET") {
    const job = encodeURIComponent(url.searchParams.get("job") || "");
    require("http").get({ hostname: "127.0.0.1", port: MC_PORTA, path: `/progresso?job=${job}` },
      (r) => {
        const p = [];
        r.on("data", (c) => p.push(c));
        r.on("end", () => {
          res.writeHead(200, {"Content-Type": "application/json", "Cache-Control": "no-store"});
          res.end(Buffer.concat(p));
        });
      }).on("error", () => {
        // MotionCore ainda subindo: nao e erro, so nao ha o que informar
        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ fase: "subindo" }));
      });
    return;
  }

  if (["/api/preview/frame", "/api/preview/clip", "/api/preview/thumb", "/api/preview/legenda", "/api/preview/thumb-legenda"].includes(url.pathname)
      && req.method === "POST") {
    const rotaMC = "/" + url.pathname.split("/").pop();
    const corpo = await readJsonBody(req) || {};
    const pedir = () => new Promise((ok, no) => {
      const http2 = require("http");
      const dados = Buffer.from(JSON.stringify(corpo));
      const r = http2.request({
        hostname: "127.0.0.1", port: MC_PORTA, path: rotaMC, method: "POST",
        headers: { "Content-Type": "application/json", "Content-Length": dados.length },
      }, (resp) => {
        const p = [];
        resp.on("data", (c) => p.push(c));
        resp.on("end", () => ok({ status: resp.statusCode, tipo: resp.headers["content-type"], corpo: Buffer.concat(p) }));
      });
      // assar um titulo pesado (sensoryStorm, 285 frames com scan line) leva
      // ~80s — o teto tem que caber nisso, senao o clipe morre no meio
      r.setTimeout(["/clip", "/legenda"].includes(rotaMC) ? 300000 : 20000,
                   () => r.destroy(new Error("MotionCore nao respondeu")));
      r.on("error", no);
      r.end(dados);
    });

    try {
      let r;
      try {
        r = await pedir();
      } catch {
        await _subirMotionCore();     // nao estava de pe — sobe e tenta de novo
        r = await pedir();
      }
      res.writeHead(r.status, { "Content-Type": r.tipo || "application/octet-stream", "Cache-Control": "no-store" });
      return res.end(r.corpo);
    } catch (e) {
      res.writeHead(503, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "MotionCore indisponivel: " + e.message }));
    }
  }

  // ─── Templates de titulo ───────────────────────────────────────────────
  // Ficam num arquivo PROPRIO, nao dentro do edit_config: template e do
  // usuario e vale pra todo projeto; o edit_config e de UM video.
  const _tplPath = path.join(__dirname, "public", "title_templates.json");
  const _lerTpls = () => {
    try { const j = JSON.parse(fs.readFileSync(_tplPath, "utf8")); return Array.isArray(j) ? j : []; }
    catch { return []; }
  };

  // ─── GERAR SFX ───────────────────────────────────────────────────────
  // A ferramenta mora FORA (ferramentas/gerador_sfx/) e nao sabe que o Klipe
  // existe. Aqui so ha o atalho, atras de um interruptor desligado por padrao.
  const SFX_TOOL = path.resolve(__dirname, "..", "..", "..",
                                "ferramentas", "gerador_sfx", "gerar_sfx.py");
  const _sfxPy = () => (lerAjustes().sfx_python || "").trim() || pythonExe();

  if (url.pathname === "/api/sfx/modelos" && req.method === "GET") {
    const a = lerAjustes();
    if (!fs.existsSync(SFX_TOOL)) {
      res.writeHead(200, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ erro: "ferramenta nao encontrada em " + SFX_TOOL }));
    }
    const p = spawn(_sfxPy(), [SFX_TOOL, "--custos"]);
    let saida = "", erro = "";
    p.stdout.on("data", d => saida += d);
    p.stderr.on("data", d => erro += d);
    p.on("error", (e) => {
      res.writeHead(200, {"Content-Type":"application/json"});
      res.end(JSON.stringify({ erro: e.message }));
    });
    p.on("close", () => {
      if (res.headersSent) return;
      res.writeHead(200, {"Content-Type":"application/json"});
      try { res.end(JSON.stringify({ ligado: !!a.sfx_gerador, modelos: JSON.parse(saida) })); }
      catch { res.end(JSON.stringify({ erro: (erro || "falhou").slice(-400) })); }
    });
    return;
  }

  if (url.pathname === "/api/sfx/gerar" && req.method === "POST") {
    if (!lerAjustes().sfx_gerador) {
      res.writeHead(200, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ ok: false, erro: "o gerador esta desligado — ligue em Configuracoes > Sons" }));
    }
    const b = await readJsonBody(req) || {};
    const texto = String(b.texto || "").trim();
    if (!texto) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ ok: false, erro: "diga o som que voce quer" }));
    }
    // Nome versionado: gerar de novo com o mesmo texto tem que dar arquivo
    // NOVO, senao o navegador serve a copia velha e parece que nao mudou.
    const base = texto.normalize("NFD").replace(/[̀-ͯ]/g, "")
                      .replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 40).toLowerCase() || "som";
    const destino = path.join(PUBLIC_DIR, "sfx", "gerados", `${base}_${Date.now().toString(36)}.wav`);

    // PROCESSO CURTO: carrega, gera e MORRE. `empty_cache()` devolve memoria
    // ao alocador do torch, nao ao sistema — modelo residente ficaria com GB
    // presos pra sempre. Processo que termina devolve tudo.
    const p = spawn(_sfxPy(), [SFX_TOOL, texto, "--saida", destino,
      "--modelo", ["pequeno", "grande"].includes(b.modelo) ? b.modelo : "pequeno",
      "--segundos", String(Math.max(0.5, Math.min(47, Number(b.segundos) || 4)))]);
    let saida = "", erro = "";
    p.stdout.on("data", d => saida += d);
    p.stderr.on("data", d => erro += d);
    p.on("error", (e) => {
      if (res.headersSent) return;
      res.writeHead(200, {"Content-Type":"application/json"});
      res.end(JSON.stringify({ ok: false, erro: e.message }));
    });
    p.on("close", () => {
      if (res.headersSent) return;
      res.writeHead(200, {"Content-Type":"application/json"});
      let j = null;
      try { j = JSON.parse(saida.trim().split("\n").pop()); } catch {}
      if (j && j.ok) {
        const rel = path.relative(PUBLIC_DIR, j.arquivo).replace(/\\/g, "/");
        return res.end(JSON.stringify({ ...j, src: rel }));
      }
      // falha PREVISTA vem com causa e receita — repassar inteira, senao o
      // corte abaixo joga fora justamente a explicacao
      if (j) return res.end(JSON.stringify(j));
      res.end(JSON.stringify({ ok: false, erro: (erro || saida || "falhou").slice(-600) }));
    });
    return;
  }


  // Miniatura de um projeto: um quadro do video dele, cacheado.
  //
  // A lista de projetos era so texto — num editor de VIDEO, distinguir oito
  // projetos por nome e data e pedir pra pessoa lembrar de cor. Um quadro
  // resolve na hora.
  if (url.pathname === "/api/projects/poster" && req.method === "GET") {
    const nome = String(url.searchParams.get("nome") || "");
    const seguro = nome.replace(/[<>:"/\\|?*]/g, "_");
    if (!seguro) { res.writeHead(400); return res.end("sem nome"); }

    const cacheDir = path.join(PUBLIC_DIR, ".posters");
    const destino = path.join(cacheDir, `${seguro}.jpg`);
    if (fs.existsSync(destino)) {
      res.writeHead(200, {"Content-Type": "image/jpeg", "Cache-Control": "max-age=3600"});
      return res.end(fs.readFileSync(destino));
    }

    // Onde mora o video deste projeto. Os snapshots antigos guardaram
    // `videoSrc` de tres jeitos diferentes (relativo ao public, relativo a
    // propria pasta, e vazio) — por isso a busca tenta varios lugares em vez
    // de confiar num so.
    let cfg = null;
    for (const p of [path.join(PUBLIC_DIR, "projects", seguro, "edit_config.json"),
                     path.join(PROJECTS_DIR, seguro, "edit_config.json")]) {
      if (fs.existsSync(p)) { try { cfg = JSON.parse(fs.readFileSync(p, "utf8")); } catch {} break; }
    }
    const src = cfg && cfg.videoSrc ? String(cfg.videoSrc) : "";
    const tentativas = [
      src && path.join(PUBLIC_DIR, src),
      src && path.join(PROJECTS_DIR, seguro, path.basename(src)),
      path.join(PUBLIC_DIR, "projects", seguro, "video.mp4"),
      path.join(PUBLIC_DIR, "projects", seguro, "video_preview.mp4"),
      path.join(PROJECTS_DIR, seguro, "video_preview.mp4"),
    ].filter(Boolean);
    const video = tentativas.find(p => fs.existsSync(p));
    if (!video) { res.writeHead(404); return res.end("sem video"); }

    fs.mkdirSync(cacheDir, { recursive: true });
    const em = Math.max(1, Math.min(30, (Number(cfg && cfg.videoDuration) || 20) * 0.12));
    const p = spawn(ffbin("ffmpeg"), ["-y", "-v", "error", "-ss", String(em.toFixed(2)),
                               "-i", video, "-frames:v", "1",
                               "-vf", "scale=200:-2", "-q:v", "4", destino]);
    p.on("error", () => { if (!res.headersSent) { res.writeHead(500); res.end("ffmpeg"); } });
    p.on("close", () => {
      if (res.headersSent) return;
      if (!fs.existsSync(destino)) { res.writeHead(404); return res.end("falhou"); }
      res.writeHead(200, {"Content-Type": "image/jpeg", "Cache-Control": "max-age=3600"});
      res.end(fs.readFileSync(destino));
    });
    return;
  }

  if (url.pathname === "/api/templates" && req.method === "GET") {
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify(_lerTpls()));
  }

  if (url.pathname === "/api/templates" && req.method === "POST") {
    const body = await readJsonBody(req) || {};
    const lista = _lerTpls();
    if (body.remover) {
      const fora = lista.filter(t => t.nome !== body.remover);
      fs.writeFileSync(_tplPath, JSON.stringify(fora, null, 1));
      res.writeHead(200, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ ok: true, templates: fora }));
    }
    const t = body.template;
    if (!t || !t.nome || !t.style) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "template precisa de nome e style" }));
    }
    // mesmo nome = sobrescreve (e o que a pessoa espera ao "salvar de novo")
    const fora = lista.filter(x => x.nome !== t.nome);
    fora.push(t);
    fs.writeFileSync(_tplPath, JSON.stringify(fora, null, 1));
    console.log(`[Templates] salvo "${t.nome}" (${t.style}) — ${fora.length} no total`);
    res.writeHead(200, {"Content-Type":"application/json"});
    return res.end(JSON.stringify({ ok: true, templates: fora }));
  }

  // API: GET waveform — peaks REAIS via ffmpeg (estilo CapCut/DaVinci).
  // Resolucao proporcional a duracao (25 bins/s) e sem baixar o MP4 pro browser
  // (o analyzeAudio antigo puxava 1.2GB pra RAM e usava 200 bins fixos pro video
  // inteiro = 1 barra a cada 5s, waveform "falso"). Cache em public/.wave_cache.
  if (url.pathname === "/api/waveform" && req.method === "GET") {
    const srcRel = (url.searchParams.get("src") || "").replace(/^\/+/, "");
    const srcPath = path.join(__dirname, "public", srcRel);
    if (!srcRel || srcRel.includes("..") || !fs.existsSync(srcPath)) {
      res.writeHead(404, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "src nao encontrado" }));
    }
    try {
      const st = fs.statSync(srcPath);
      const cacheDir = path.join(__dirname, "public", ".wave_cache");
      if (!fs.existsSync(cacheDir)) fs.mkdirSync(cacheDir, { recursive: true });
      const key = require("crypto").createHash("md5").update(srcRel + "|" + st.size + "|" + st.mtimeMs).digest("hex").slice(0, 16);
      const cacheFile = path.join(cacheDir, key + ".json");
      if (fs.existsSync(cacheFile)) {
        res.writeHead(200, {"Content-Type":"application/json"});
        return res.end(fs.readFileSync(cacheFile, "utf8"));
      }
      // Decode mono 4kHz s16le direto do ffmpeg (rapido: ~2s pra 18min)
      const SR = 4000;
      const child = spawn(ffbin("ffmpeg"), ["-v", "error", "-i", srcPath, "-vn", "-ac", "1", "-ar", String(SR), "-f", "s16le", "-"]);
      const chunks = [];
      child.stdout.on("data", d => chunks.push(d));
      child.on("close", (code) => {
        try {
          const pcm = Buffer.concat(chunks);
          const n = Math.floor(pcm.length / 2);
            // A guarda era `n < SR / 10`: qualquer coisa abaixo de 1/10 de
            // segundo virava "sem audio". Mas um clique E um som de 85 ms — a
            // biblioteca de SFX tem um assim, e ele dava 500 no painel de midia
            // toda vez que a aba de som abria. Sem amostra NENHUMA e que e sem audio.
            if (code !== 0 || n === 0) {
              res.writeHead(500, {"Content-Type":"application/json"});
              return res.end(JSON.stringify({ error: code !== 0
                ? "ffmpeg nao conseguiu ler o arquivo" : "o arquivo nao tem audio" }));
            }
          const duration = n / SR;
          const bins = Math.min(30000, Math.max(240, Math.round(duration * 25)));
          const spb = Math.max(1, Math.floor(n / bins));
          const peaks = [];
          for (let i = 0; i < bins; i++) {
            let mn = 0, mx = 0;
            const a = i * spb, b = Math.min(n, a + spb);
            for (let j = a; j < b; j++) {
              const v = pcm.readInt16LE(j * 2) / 32768;
              if (v < mn) mn = v;
              if (v > mx) mx = v;
            }
            peaks.push([Math.round(mn * 1000) / 1000, Math.round(mx * 1000) / 1000]);
          }
          const out = JSON.stringify({ duration: Math.round(duration * 100) / 100, peaks });
          fs.writeFileSync(cacheFile, out);
          res.writeHead(200, {"Content-Type":"application/json"});
          res.end(out);
        } catch (e) {
          res.writeHead(500, {"Content-Type":"application/json"});
          res.end(JSON.stringify({ error: e.message }));
        }
      });
      child.on("error", (e) => {
        res.writeHead(500, {"Content-Type":"application/json"});
        res.end(JSON.stringify({ error: "spawn ffmpeg: " + e.message }));
      });
      return;
    } catch (e) {
      res.writeHead(500, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: e.message }));
    }
  }

  // API: revisao leve para sincronizacao entre o navegador e editores externos.
  if (url.pathname === "/api/config/version" && req.method === "GET") {
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    res.end(JSON.stringify({ revision: revisaoConfig(_configPath) }));
    return;
  }

  // API: GET config
  if (url.pathname === "/api/config" && req.method === "GET") {
    const config = readConfig();
    config._revision = revisaoConfig(_configPath);
    config._availableBrolls = listBrolls(config.videoSrc);
    config._availableMusic = listMusic();
    config._availableSfx = listSfx();
    config._availableAmbient = listAmbient();
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    res.end(JSON.stringify(config));
    return;
  }

  // API: POST config (save all) — opcionalmente persiste tambem no projeto via ?project=slug
  if (url.pathname === "/api/config" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const esperada = String(req.headers["x-config-revision"] || "").trim();
        const atual = revisaoConfig(_configPath);
        if (esperada && atual && esperada !== atual) {
          res.writeHead(409, {"Content-Type": "application/json"});
          res.end(JSON.stringify({
            error: "o projeto mudou desde a ultima leitura",
            revision: atual,
          }));
          return;
        }
        const data = JSON.parse(body);
        delete data._revision;
        delete data._availableBrolls;
        delete data._availableMusic;
        delete data._availableSfx;
        delete data._availableAmbient;
        writeConfig(data);
        // ?project=<slug> tambem persiste no projeto (so reload nao perde mudancas)
        const slug = url.searchParams.get("project");
        if (slug) {
          const slugSafe = slug.replace(/[<>:"/\\|?*]/g, "_");
          const projCfg = path.join(__dirname, "public", "projects", slugSafe, "edit_config.json");
          if (fs.existsSync(path.dirname(projCfg))) {
            try {
              fs.writeFileSync(projCfg, JSON.stringify(data, null, 2), "utf-8");
              console.log(`[Klipe] Config persisted to project: ${slugSafe}`);
            } catch(e) {
              console.error(`[Klipe] Failed to persist project config: ${e.message}`);
            }
          }
        }
        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ok: true, revision: revisaoConfig(_configPath)}));
      } catch(e) {
        res.writeHead(400); res.end(JSON.stringify({error: e.message}));
      }
    });
    return;
  }

  // API: POST config/snapshot — save named snapshot of current config (for TRIBE optimization undo)
  if (url.pathname === "/api/config/snapshot" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const { name } = JSON.parse(body);
        if (!name) throw new Error("name required");
        const snapshotDir = path.join(__dirname, "snapshots");
        if (!fs.existsSync(snapshotDir)) fs.mkdirSync(snapshotDir, { recursive: true });
        const config = readConfig();
        fs.writeFileSync(
          path.join(snapshotDir, `${name}.json`),
          JSON.stringify(config, null, 2),
          "utf-8"
        );
        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ ok: true, snapshot: name }));
      } catch(e) {
        res.writeHead(400); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: POST config/restore — restore a named snapshot
  if (url.pathname === "/api/config/restore" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const { name } = JSON.parse(body);
        if (!name) throw new Error("name required");
        const snapshotPath = path.join(__dirname, "snapshots", `${name}.json`);
        if (!fs.existsSync(snapshotPath)) throw new Error("snapshot not found: " + name);
        const config = JSON.parse(fs.readFileSync(snapshotPath, "utf-8"));
        writeConfig(config);
        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ ok: true, restored: name }));
      } catch(e) {
        res.writeHead(400); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: SFX presets (combos salvos) — GET / POST
  if (url.pathname === "/api/sfx-presets" && req.method === "GET") {
    const file = path.join(PUBLIC_DIR, "sfx_presets.json");
    let data = {};
    if (fs.existsSync(file)) {
      try { data = JSON.parse(fs.readFileSync(file, "utf8")); } catch {}
    }
    res.writeHead(200, {"Content-Type": "application/json"});
    res.end(JSON.stringify(data));
    return;
  }
  if (url.pathname === "/api/sfx-presets" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const input = JSON.parse(body);
        const file = path.join(PUBLIC_DIR, "sfx_presets.json");
        let data = {};
        if (fs.existsSync(file)) {
          try { data = JSON.parse(fs.readFileSync(file, "utf8")); } catch {}
        }
        if (input.delete && input.id) {
          delete data[input.id];
        } else if (input.id && input.preset) {
          data[input.id] = input.preset;
        } else {
          res.writeHead(400); res.end('{"error":"need id+preset or id+delete"}'); return;
        }
        fs.writeFileSync(file, JSON.stringify(data, null, 2));
        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ ok: true, presets: data }));
      } catch (e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: GET config/snapshots — list available snapshots
  if (url.pathname === "/api/config/snapshots" && req.method === "GET") {
    const snapshotDir = path.join(__dirname, "snapshots");
    if (!fs.existsSync(snapshotDir)) {
      res.writeHead(200, {"Content-Type": "application/json"});
      res.end(JSON.stringify([]));
      return;
    }
    const snapshots = fs.readdirSync(snapshotDir)
      .filter(f => f.endsWith(".json"))
      .map(f => {
        const stat = fs.statSync(path.join(snapshotDir, f));
        return { name: f.replace(".json", ""), created: stat.mtime.toISOString(), size: stat.size };
      })
      .sort((a, b) => b.created.localeCompare(a.created));
    res.writeHead(200, {"Content-Type": "application/json"});
    res.end(JSON.stringify(snapshots));
    return;
  }

  // API: pastas do usuario para os atalhos do importador de b-roll.
  if (url.pathname === "/api/user-folders" && req.method === "GET") {
    const home = os.homedir();
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      home,
      downloads: path.join(home, "Downloads"),
      videos: path.join(home, process.platform === "darwin" ? "Movies" : "Videos"),
      desktop: path.join(home, "Desktop"),
    }));
    return;
  }

  // API: POST browse folder — list video files in a given directory
  if (url.pathname === "/api/browse-folder" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const { folder } = JSON.parse(body);
        if (!folder || !fs.existsSync(folder)) {
          res.writeHead(400); res.end(JSON.stringify({ error: "Pasta não encontrada" })); return;
        }
        const stat = fs.statSync(folder);
        if (!stat.isDirectory()) {
          res.writeHead(400); res.end(JSON.stringify({ error: "Não é uma pasta" })); return;
        }
        const videoExts = ['.mp4', '.webm', '.mov', '.avi', '.mkv'];
        const files = [];
        // List files in folder (non-recursive for safety)
        for (const f of fs.readdirSync(folder)) {
          const ext = path.extname(f).toLowerCase();
          if (videoExts.includes(ext)) {
            const fullPath = path.join(folder, f);
            const fstat = fs.statSync(fullPath);
            files.push({ name: f, path: fullPath, size: fstat.size });
          }
        }
        // Also list subdirectories for navigation
        const subdirs = [];
        for (const f of fs.readdirSync(folder)) {
          const fullPath = path.join(folder, f);
          try { if (fs.statSync(fullPath).isDirectory() && !f.startsWith('.')) subdirs.push(f); } catch(e) {}
        }
        const parentDir = path.dirname(folder);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ folder, parentDir, subdirs, files }));
      } catch(e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: POST import-broll — copy a video file into public/ as broll
  if (url.pathname === "/api/import-broll" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const { sourcePath, targetName } = JSON.parse(body);
        if (!sourcePath || !fs.existsSync(sourcePath)) {
          res.writeHead(400); res.end(JSON.stringify({ error: "Arquivo não encontrado" })); return;
        }
        // Generate target filename
        const existing = listBrolls();
        let finalName = targetName;
        if (!finalName) {
          // Auto-name: broll_XX.mp4
          const nums = existing.map(f => parseInt(f.match(/broll_(\d+)/)?.[1] || '0'));
          const next = (Math.max(0, ...nums) + 1).toString().padStart(2, '0');
          const ext = path.extname(sourcePath) || '.mp4';
          finalName = `broll_${next}${ext}`;
        }
        const destPath = path.join(PUBLIC_DIR, finalName);
        // Copy file
        fs.copyFileSync(sourcePath, destPath);
        res.writeHead(200, { "Content-Type": "application/json" });
        const cfg = readConfig();
        res.end(JSON.stringify({ ok: true, filename: finalName, brolls: listBrolls(cfg.videoSrc) }));
      } catch(e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: POST import-broll-batch — import multiple files at once
  if (url.pathname === "/api/import-broll-batch" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const { files } = JSON.parse(body);
        const imported = [];
        const existing = listBrolls();
        let nums = existing.map(f => parseInt(f.match(/broll_(\d+)/)?.[1] || '0'));
        let nextNum = Math.max(0, ...nums) + 1;
        for (const srcPath of files) {
          if (!fs.existsSync(srcPath)) continue;
          const ext = path.extname(srcPath) || '.mp4';
          const finalName = `broll_${nextNum.toString().padStart(2, '0')}${ext}`;
          fs.copyFileSync(srcPath, path.join(PUBLIC_DIR, finalName));
          imported.push(finalName);
          nextNum++;
        }
        res.writeHead(200, { "Content-Type": "application/json" });
        const cfg = readConfig();
        res.end(JSON.stringify({ ok: true, imported, brolls: listBrolls(cfg.videoSrc) }));
      } catch(e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // API: POST sync to Root.tsx

  // --- Extracted sync logic so render can reuse it ---
  function _syncRootTsx(config) {
      const rootPath = path.join(__dirname, "src", "Root.tsx");

      // Prefer captions from edit_config.json (they include subStyle, font1/2/3, etc.)
      // Fall back to transcription.json if config.captions is empty
      let captionsData = Array.isArray(config.captions) ? config.captions : [];
      if (captionsData.length === 0) {
        let transcriptionPath = null;
        if (config.videoSrc && config.videoSrc.includes("/")) {
          const projDir = path.dirname(path.join(__dirname, "public", config.videoSrc));
          const projTranscription = path.join(projDir, "transcription.json");
          if (fs.existsSync(projTranscription)) transcriptionPath = projTranscription;
        }
        if (!transcriptionPath) {
          const rootTranscription = path.join(__dirname, "public", "transcription.json");
          if (fs.existsSync(rootTranscription)) transcriptionPath = rootTranscription;
        }
        if (transcriptionPath) {
          const transcription = JSON.parse(fs.readFileSync(transcriptionPath, "utf-8"));
          captionsData = transcription.map(seg => ({
            startSec: seg.start,
            endSec: seg.end,
            text: seg.text
          }));
        }
      }

      // Generate captions array preserving subStyle & font1/2/3
      const captionsStr = captionsData.map(c => {
        const parts = [
          `startSec: ${c.startSec}`,
          `endSec: ${c.endSec}`,
          `text: ${JSON.stringify(c.text)}`,
        ];
        if (c.subStyle) parts.push(`subStyle: ${JSON.stringify(c.subStyle)}`);
        if (c.font1) parts.push(`font1: ${JSON.stringify(c.font1)}`);
        if (c.font2) parts.push(`font2: ${JSON.stringify(c.font2)}`);
        if (c.font3) parts.push(`font3: ${JSON.stringify(c.font3)}`);
        return `  { ${parts.join(", ")} }`;
      }).join(",\n");

      // Generate titles array
      const titlesStr = config.titles.map(t => {
        let s = `            { startSec: ${t.startSec}, endSec: ${t.endSec}, text: ${JSON.stringify(t.text)}, style: "${t.style}" as const`;
        if (t.posX) s += `, posX: ${t.posX}`;
        if (t.posY) s += `, posY: ${t.posY}`;
        s += " }";
        return s;
      }).join(",\n");

      // Generate brolls array — handles generated (programmatic) brolls with empty src
      const brollsStr = config.brolls.map(b => {
        const parts = [`startSec: ${b.startSec}`, `endSec: ${b.endSec}`];
        if (b.src && b.src.trim() !== "") {
          parts.push(`src: staticFile(${JSON.stringify(stripPub(b.src))})`);
        } else {
          parts.push(`src: ""`);
        }
        if (b.label) parts.push(`label: ${JSON.stringify(b.label)}`);
        if (b.speed && b.speed !== 1) parts.push(`speed: ${b.speed}`);
        if (b.generated) parts.push(`generated: true`);
        if (b.generatedStyle) parts.push(`generatedStyle: ${JSON.stringify(b.generatedStyle)}`);
        if (b.generatedText) parts.push(`generatedText: ${JSON.stringify(b.generatedText)}`);
        if (b.generatedSubtext) parts.push(`generatedSubtext: ${JSON.stringify(b.generatedSubtext)}`);
        if (b.generatedColor) parts.push(`generatedColor: ${JSON.stringify(b.generatedColor)}`);
        return `            { ${parts.join(", ")} }`;
      }).join(",\n");

      // Generate zooms array (with easing support)
      const zoomsStr = config.zooms.map(z => {
        let s = `            { startSec: ${z.startSec}, endSec: ${z.endSec}, direction: "${z.direction}" as const, intensity: ${z.intensity}`;
        if (z.easing) s += `, easing: "${z.easing}" as const`;
        if (z.originY !== undefined) s += `, originY: ${z.originY}`;
        s += " }";
        return s;
      }).join(",\n");

      // Generate segments — derivado dos videoClips (necessario pro VideoEditor renderizar o video principal!)
      const segmentsStr = ((config.videoClips || []).length > 0
        ? config.videoClips.map(vc => `            { startSec: ${vc.startSec}, endSec: ${vc.endSec} }`).join(",\n")
        : `            { startSec: 0, endSec: ${config.videoDuration || 0} }`);

      // Generate sfx array
      const sfxStr = (config.sfx || []).map(s => {
        const parts = [
          `startSec: ${s.startSec}`,
          `endSec: ${s.endSec}`,
          `src: staticFile(${JSON.stringify(stripPub(s.src))})`,
        ];
        if (typeof s.volume === 'number') parts.push(`volume: ${s.volume}`);
        if (typeof s.fadeIn === 'number' && s.fadeIn) parts.push(`fadeIn: ${s.fadeIn}`);
        if (typeof s.fadeOut === 'number' && s.fadeOut) parts.push(`fadeOut: ${s.fadeOut}`);
        if (typeof s.speed === 'number' && s.speed !== 1) parts.push(`speed: ${s.speed}`);
        if (typeof s.srcStart === 'number' && s.srcStart) parts.push(`srcStart: ${s.srcStart}`);
        return `            { ${parts.join(", ")} }`;
      }).join(",\n");

      // Generate musicTracks array
      const musicStr = (config.musicTracks || []).map(m => {
        const parts = [
          `startSec: ${m.startSec}`,
          `endSec: ${m.endSec}`,
          `src: staticFile(${JSON.stringify(stripPub(m.src))})`,
        ];
        if (typeof m.volume === 'number') parts.push(`volume: ${m.volume}`);
        if (typeof m.fadeIn === 'number' && m.fadeIn) parts.push(`fadeIn: ${m.fadeIn}`);
        if (typeof m.fadeOut === 'number' && m.fadeOut) parts.push(`fadeOut: ${m.fadeOut}`);
        if (typeof m.speed === 'number' && m.speed !== 1) parts.push(`speed: ${m.speed}`);
        if (typeof m.srcStart === 'number' && m.srcStart) parts.push(`srcStart: ${m.srcStart}`);
        return `            { ${parts.join(", ")} }`;
      }).join(",\n");

      // Generate shapes array (se houver)
      const shapesStr = (config.shapes || []).map(sh => {
        const parts = [
          `startSec: ${sh.startSec}`,
          `endSec: ${sh.endSec}`,
          `kind: ${JSON.stringify(sh.kind || 'rectangle')}`,
          `width: ${sh.width || 200}`,
          `height: ${sh.height || 200}`,
        ];
        if (typeof sh.posX === 'number' && sh.posX) parts.push(`posX: ${sh.posX}`);
        if (typeof sh.posY === 'number' && sh.posY) parts.push(`posY: ${sh.posY}`);
        if (typeof sh.rotation === 'number' && sh.rotation) parts.push(`rotation: ${sh.rotation}`);
        if (typeof sh.opacity === 'number' && sh.opacity !== 1) parts.push(`opacity: ${sh.opacity}`);
        if (sh.color) parts.push(`color: ${JSON.stringify(sh.color)}`);
        if (sh.borderColor) parts.push(`borderColor: ${JSON.stringify(sh.borderColor)}`);
        if (typeof sh.borderWidth === 'number' && sh.borderWidth) parts.push(`borderWidth: ${sh.borderWidth}`);
        if (typeof sh.cornerRadius === 'number' && sh.cornerRadius) parts.push(`cornerRadius: ${sh.cornerRadius}`);
        if (sh.behindPerson) parts.push(`behindPerson: true`);
        return `            { ${parts.join(", ")} }`;
      }).join(",\n");

      // Aqui era gerado um src/Root.tsx com as composicoes do motor de navegador, para o
      // Studio recompilar o bundle. Sem motor de navegador, virou um arquivo escrito a
      // cada import de b-roll para ninguem nunca ler.
      console.log("[sync] Root.tsx regenerated from edit_config.json");
  }

  // API: POST analyze-video (Gemini style analysis)
  if (url.pathname === "/api/analyze-video" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const params = JSON.parse(body);
        const videoPath = params.videoPath || params.videoUrl || "";
        const apiKey = params.apiKey || chave("gemini_key", "GEMINI_API_KEY");
        const model = params.model || process.env.GEMINI_MODEL || "gemini-2.0-flash";

        if (!videoPath) {
          res.writeHead(400, {"Content-Type": "application/json"});
          res.end(JSON.stringify({error: "videoPath or videoUrl is required"}));
          return;
        }

        // Determine Python executable (prefer conda env)
        // `pyExe`, nao `pythonExe`: o nome antigo sombrearia a funcao do modulo.
        const pyExe = pythonExe();

        const args = [ANALYZE_SCRIPT, videoPath, "--clips"];
        if (apiKey) args.push("--api-key", apiKey);
        if (model) args.push("--model", model);

        console.log(`[MotionForge] Running: ${pyExe} ${args.join(" ")}`);

        const child = spawn(pyExe, args, {
          env: { ...process.env, GEMINI_API_KEY: apiKey, GEMINI_MODEL: model },
          timeout: 600000  // 10 min timeout
        });

        let stdout = "";
        let stderr = "";
        child.stdout.on("data", d => stdout += d);
        child.stderr.on("data", d => {
          stderr += d;
          console.log("[MotionForge Analyzer]", d.toString().trim());
        });

        child.on("close", code => {
          if (code !== 0 && !stdout.trim()) {
            res.writeHead(500, {"Content-Type": "application/json"});
            res.end(JSON.stringify({error: `Analysis failed (exit ${code}): ${stderr.slice(0, 500)}`}));
            return;
          }
          try {
            const result = JSON.parse(stdout.trim());
            res.writeHead(200, {"Content-Type": "application/json"});
            res.end(JSON.stringify(result));
          } catch(e) {
            res.writeHead(500, {"Content-Type": "application/json"});
            res.end(JSON.stringify({error: "Failed to parse analysis output", raw: stdout.slice(0, 1000)}));
          }
        });

        child.on("error", err => {
          res.writeHead(500, {"Content-Type": "application/json"});
          res.end(JSON.stringify({error: `Failed to spawn Python: ${err.message}. Set PYTHON_EXE env if needed.`}));
        });

      } catch(e) {
        res.writeHead(400, {"Content-Type": "application/json"});
        res.end(JSON.stringify({error: e.message}));
      }
    });
    return;
  }

  // API: GET available videos in public for analysis
  if (url.pathname === "/api/videos" && req.method === "GET") {
    const videos = fs.readdirSync(PUBLIC_DIR)
      .filter(f => /\.(mp4|webm|mov|avi)$/i.test(f))
      .map(f => ({ name: f, path: path.join(PUBLIC_DIR, f), size: fs.statSync(path.join(PUBLIC_DIR, f)).size }))
      .sort((a,b) => a.name.localeCompare(b.name));
    res.writeHead(200, {"Content-Type": "application/json"});
    res.end(JSON.stringify(videos));
    return;
  }

  // API: POST audio processing (normalize + denoise via ffmpeg)
  if (url.pathname === "/api/audio-process" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const params = JSON.parse(body);
        const config = readConfig();
        const videoFile = path.join(PUBLIC_DIR, config.videoSrc || "video_preview.mp4");

        if (!fs.existsSync(videoFile)) {
          res.writeHead(404, {"Content-Type": "application/json"});
          res.end(JSON.stringify({error: "Video file not found: " + config.videoSrc}));
          return;
        }

        const normalize = params.normalize !== false;  // default true
        const denoise = params.denoise !== false;       // default true
        const noiseReduction = params.noiseReduction || 0.21;  // afftdn noise floor
        const loudnessTarget = params.loudnessTarget || -16;   // LUFS target
        const highpass = params.highpass || 80;   // Hz, cut rumble
        const deesser = params.deesser || false;

        // Build ffmpeg audio filter chain
        const filters = [];

        // 1. High-pass filter to remove low rumble
        if (highpass > 0) {
          filters.push(`highpass=f=${highpass}`);
        }

        // 2. Noise reduction (afftdn)
        if (denoise) {
          filters.push(`afftdn=nf=-${Math.abs(noiseReduction * 100)}:nt=w:om=o`);
        }

        // 3. De-esser (reduce sibilance)
        if (deesser) {
          filters.push(`equalizer=f=7500:t=q:w=2:g=-6`);
        }

        // 4. Compressor for consistent levels
        filters.push(`acompressor=threshold=-24dB:ratio=3:attack=5:release=50:makeup=2`);

        // 5. Loudness normalization (EBU R128)
        if (normalize) {
          filters.push(`loudnorm=I=${loudnessTarget}:TP=-1.5:LRA=11`);
        }

        const filterChain = filters.join(',');
        const ext = path.extname(videoFile);
        const baseName = path.basename(videoFile, ext);
        const outputFile = path.join(PUBLIC_DIR, `${baseName}_audio_processed${ext}`);

        console.log(`[MotionForge Audio] Processing: ${filterChain}`);
        console.log(`[MotionForge Audio] Input: ${videoFile}`);
        console.log(`[MotionForge Audio] Output: ${outputFile}`);

        const ffmpegArgs = [
          '-y', '-i', videoFile,
          '-af', filterChain,
          '-c:v', 'copy',  // don't re-encode video
          outputFile
        ];

        const child = spawn('ffmpeg', ffmpegArgs, { timeout: 600000 });
        let stderr = "";
        child.stderr.on("data", d => {
          stderr += d;
        });

        child.on("close", code => {
          if (code !== 0) {
            console.error(`[MotionForge Audio] ffmpeg failed (exit ${code})`);
            res.writeHead(500, {"Content-Type": "application/json"});
            res.end(JSON.stringify({error: `ffmpeg failed (exit ${code})`, details: stderr.slice(-500)}));
            return;
          }

          // Update config to use processed file
          const newSrc = `${baseName}_audio_processed${ext}`;
          config.videoSrc = newSrc;
          config.audioProcessed = {
            normalize, denoise, noiseReduction, loudnessTarget, highpass, deesser,
            originalSrc: `${baseName}${ext}`,
            processedAt: new Date().toISOString()
          };
          writeConfig(config);

          console.log(`[MotionForge Audio] Done! Output: ${newSrc}`);
          res.writeHead(200, {"Content-Type": "application/json"});
          res.end(JSON.stringify({
            ok: true,
            newVideoSrc: newSrc,
            filters: filterChain,
            message: "Audio processed successfully"
          }));
        });

        child.on("error", err => {
          res.writeHead(500, {"Content-Type": "application/json"});
          res.end(JSON.stringify({error: `Failed to run ffmpeg: ${err.message}. Make sure ffmpeg is installed.`}));
        });

      } catch(e) {
        res.writeHead(400, {"Content-Type": "application/json"});
        res.end(JSON.stringify({error: e.message}));
      }
    });
    return;
  }

  // API: POST revert audio to original
  if (url.pathname === "/api/audio-revert" && req.method === "POST") {
    try {
      const config = readConfig();
      if (config.audioProcessed && config.audioProcessed.originalSrc) {
        config.videoSrc = config.audioProcessed.originalSrc;
        delete config.audioProcessed;
        writeConfig(config);
        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ok: true, videoSrc: config.videoSrc, message: "Reverted to original audio"}));
      } else {
        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ok: true, message: "No processed audio to revert"}));
      }
    } catch(e) {
      res.writeHead(500, {"Content-Type": "application/json"});
      res.end(JSON.stringify({error: e.message}));
    }
    return;
  }

  // Os endpoints /api/video-stabilize e /api/video-stabilize-revert sairam
  // junto com o painel. O vidstab funcionava, mas neste material aumentava o
  // movimento entre quadros em vez de reduzir — ver a nota na barra do editor.

  // ── RENDER ──
  // ── RENDER (chunked by default — 3min chunks, auto-concat) ──

  // Render status

  // Cancel render

  // ── SEND TO DAVINCI ──
  // Executa build_davinci_from_klipe.py em background — pipeline completa:
  // audio stems + render TitlesOverlay + render BrollsOverlay + DaVinci build + keyframe inject
  if (url.pathname === "/api/send-to-davinci" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const { project } = JSON.parse(body || "{}");
        if (!project) {
          res.writeHead(400, {"Content-Type": "application/json"});
          res.end(JSON.stringify({ error: "missing project name" }));
          return;
        }

        if (global._davinciSend && global._davinciSend.status === "running") {
          res.writeHead(409, {"Content-Type": "application/json"});
          res.end(JSON.stringify({ error: "already running" }));
          return;
        }

        global._davinciSend = {
          status: "running",
          project,
          startedAt: Date.now(),
          log: [],
          phase: "starting",
        };

        const pyExe = pythonExe();
        const child = spawn(pyExe, ["build_davinci_from_klipe.py", project], {
          cwd: __dirname,
          stdio: ["ignore", "pipe", "pipe"],
        });
        global._davinciSend.childProcess = child;

        const collect = data => {
          const lines = data.toString().split("\n").filter(l => l.trim());
          for (const line of lines) {
            global._davinciSend.log.push(line);
            // Detect phase from output
            if (line.includes("STEP 1:")) global._davinciSend.phase = "audio_stems";
            else if (line.includes("STEP 2:")) global._davinciSend.phase = "title_overlays";
            else if (line.includes("STEP 3:")) global._davinciSend.phase = "brolls_overlay";
            else if (line.includes("Creating new")) global._davinciSend.phase = "creating_project";
            else if (line.includes("STEP 4:")) global._davinciSend.phase = "building_timeline";
            else if (line.includes("STEP 5:")) global._davinciSend.phase = "injecting_keyframes";
            else if (line.includes("DONE")) global._davinciSend.phase = "complete";
          }
          // Keep last 100 lines
          if (global._davinciSend.log.length > 100) {
            global._davinciSend.log = global._davinciSend.log.slice(-100);
          }
        };
        child.stdout.on("data", collect);
        child.stderr.on("data", collect);
        child.on("close", code => {
          global._davinciSend.status = code === 0 ? "done" : "error";
          global._davinciSend.exitCode = code;
          global._davinciSend.finishedAt = Date.now();
        });

        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ ok: true, message: "DaVinci pipeline iniciado" }));
      } catch (e) {
        res.writeHead(500, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // ── SEND TO DAVINCI status ──
  if (url.pathname === "/api/send-to-davinci/status" && req.method === "GET") {
    const r = global._davinciSend;
    if (!r) {
      res.writeHead(200, {"Content-Type": "application/json"});
      res.end(JSON.stringify({ status: "idle" }));
      return;
    }
    const elapsed = ((Date.now() - r.startedAt) / 1000).toFixed(0);
    res.writeHead(200, {"Content-Type": "application/json"});
    res.end(JSON.stringify({
      status: r.status,
      phase: r.phase,
      project: r.project,
      elapsed: elapsed + "s",
      log: r.log.slice(-20),
      exitCode: r.exitCode,
    }));
    return;
  }

  // ── GENERATE PERSON MASK (RVM — Robust Video Matting) ──
  // Body: { videoSrc, startSec?, endSec?, model?, device? }
  // Generates a transparent video (WebM VP9 alpha) with only the person
  if (url.pathname === "/api/generate-person-mask" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", async () => {
      try {
        const { videoSrc, startSec, endSec, model, device } = JSON.parse(body || "{}");
        if (!videoSrc) {
          res.writeHead(400, {"Content-Type": "application/json"});
          res.end(JSON.stringify({ error: "videoSrc required" }));
          return;
        }
        // Resolve absolute paths
        const cleanSrc = stripPub(videoSrc);
        const inputAbs = path.join(PUBLIC_DIR, cleanSrc);
        if (!fs.existsSync(inputAbs)) {
          res.writeHead(404, {"Content-Type": "application/json"});
          res.end(JSON.stringify({ error: `input not found: ${inputAbs}` }));
          return;
        }
        // Output next to input, same folder
        const dir = path.dirname(inputAbs);
        const base = path.basename(inputAbs, path.extname(inputAbs));
        const suffix = (startSec != null || endSec != null)
          ? `_person_${Math.round(startSec || 0)}-${Math.round(endSec || 0)}`
          : "_person";
        // WebM/VP9 with native alpha (yuva420p) — direct browser compositing
        const outputAbs = path.join(dir, `${base}${suffix}.webm`);
        // Relative path (for config) — keep the same scheme as videoSrc
        const outputRel = path.relative(PUBLIC_DIR, outputAbs).replace(/\\/g, "/");

        // Track status globally so UI can poll
        global._personMaskJob = {
          status: "running",
          input: cleanSrc,
          output: outputRel,
          startSec: startSec ?? null,
          endSec: endSec ?? null,
          startedAt: Date.now(),
          progress: "",
          log: [], // full log lines (stdout + stderr) for UI display
          error: null,
        };
        const pushLog = (stream, raw) => {
          const lines = String(raw).replace(/\r/g, "\n").split("\n");
          for (const ln of lines) {
            const t = ln.trim();
            if (!t) continue;
            global._personMaskJob.log.push({
              t: Date.now(),
              s: stream, // 'out' | 'err' | 'sys'
              m: t.slice(0, 500),
            });
            // Cap at last 400 lines
            if (global._personMaskJob.log.length > 400) {
              global._personMaskJob.log.splice(0, global._personMaskJob.log.length - 400);
            }
          }
        };

        const scriptPath = path.join(__dirname, "tools", "extract_person_rvm.py");
        const args = [
          "-u", // unbuffered stdout/stderr so we see lines as they happen
          scriptPath,
          "--input", inputAbs,
          "--output", outputAbs,
          "--model", model || "mobilenetv3",
          "--device", device || "auto",
        ];
        if (startSec != null) { args.push("--start", String(startSec)); }
        if (endSec != null) { args.push("--end", String(endSec)); }

        // Call python.exe directly from the conda env — avoids the whole conda activate mess.
        // Env used: openvoice_gpu2 (user has torch installed there)
        const pyExe = pythonExe();
        const pyIsPath = path.isAbsolute(pyExe);
        if (pyIsPath && !fs.existsSync(pyExe)) {
          global._personMaskJob.status = "error";
          global._personMaskJob.error = `Python não encontrado: ${pyExe}`;
          pushLog("sys", global._personMaskJob.error);
          res.writeHead(500, {"Content-Type": "application/json"});
          res.end(JSON.stringify({ error: global._personMaskJob.error }));
          return;
        }
        if (!fs.existsSync(scriptPath)) {
          global._personMaskJob.status = "error";
          global._personMaskJob.error = `script não encontrado: ${scriptPath}`;
          pushLog("sys", global._personMaskJob.error);
          res.writeHead(500, {"Content-Type": "application/json"});
          res.end(JSON.stringify({ error: global._personMaskJob.error }));
          return;
        }

        const spawnMsg = `spawn: ${pyExe} ${args.join(" ")}`;
        console.log("[PersonMask]", spawnMsg);
        pushLog("sys", spawnMsg);
        pushLog("sys", `input: ${inputAbs}`);
        pushLog("sys", `output: ${outputAbs}`);
        if (startSec != null || endSec != null) {
          pushLog("sys", `range: ${startSec ?? 0}s → ${endSec ?? '?'}s`);
        }

        const proc = spawn(pyExe, args, {
          windowsHide: true,
          env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
        });

        let stderr = "";
        proc.stdout.on("data", d => {
          const s = d.toString();
          console.log("[PersonMask stdout]", s.trim());
          global._personMaskJob.progress = s.trim().slice(-200);
          pushLog("out", s);
        });
        proc.stderr.on("data", d => {
          const s = d.toString();
          stderr += s;
          console.log("[PersonMask stderr]", s.trim());
          pushLog("err", s);
        });
        proc.on("error", err => {
          console.log("[PersonMask] spawn error:", err.message);
          pushLog("sys", `spawn error: ${err.message}`);
          global._personMaskJob.status = "error";
          global._personMaskJob.error = err.message;
        });
        proc.on("close", code => {
          if (code === 0 && fs.existsSync(outputAbs)) {
            global._personMaskJob.status = "done";
            global._personMaskJob.elapsed = Date.now() - global._personMaskJob.startedAt;
            pushLog("sys", `✅ done (exit 0) → ${outputRel}`);
            console.log("[PersonMask] OK:", outputRel);
          } else {
            global._personMaskJob.status = "error";
            global._personMaskJob.error = stderr.slice(-500) || `exit ${code}`;
            pushLog("sys", `❌ failed (exit ${code})`);
            console.log("[PersonMask] FAILED:", global._personMaskJob.error);
          }
        });

        res.writeHead(202, {"Content-Type": "application/json"});
        res.end(JSON.stringify({
          ok: true,
          message: "person mask generation started",
          output: outputRel,
        }));
      } catch(e) {
        res.writeHead(500, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // ── PERSON MASK STATUS ──
  if (url.pathname === "/api/generate-person-mask/status" && req.method === "GET") {
    const job = global._personMaskJob || { status: "idle" };
    // Support ?since=<ms timestamp> to return only new log lines
    const sinceStr = url.searchParams.get("since");
    const since = sinceStr ? parseInt(sinceStr, 10) : 0;
    const fullLog = Array.isArray(job.log) ? job.log : [];
    const log = since > 0 ? fullLog.filter(l => l.t > since) : fullLog;
    const payload = {
      status: job.status || "idle",
      progress: job.progress || "",
      error: job.error || null,
      elapsed: job.elapsed || (job.startedAt ? Date.now() - job.startedAt : 0),
      output: job.output || null,
      log,
      logCount: fullLog.length,
      lastT: fullLog.length ? fullLog[fullLog.length - 1].t : 0,
    };
    res.writeHead(200, {"Content-Type": "application/json"});
    res.end(JSON.stringify(payload));
    return;
  }

  // ── FEATHER PERSON MASK (FFmpeg: apply Gaussian blur to alpha, re-encode) ──
  // Body: { src: <relative-path-to-webm>, sigma: <number> }
  // Strategy: extract alpha channel (alphaextract), Gaussian blur it (gblur),
  // then merge it back with the original RGB (alphamerge) and re-encode to VP9.
  // This bakes the feather into the file so final motor de navegador renders keep it.
  if (url.pathname === "/api/feather-person-mask" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const { src, sigma } = JSON.parse(body || "{}");
        if (!src) {
          res.writeHead(400, {"Content-Type": "application/json"});
          res.end(JSON.stringify({ error: "src required" }));
          return;
        }
        const sigmaVal = Math.max(0.3, Math.min(10, parseFloat(sigma) || 1.0));
        const cleanSrc = stripPub(src);
        const inputFile = path.join(PUBLIC_DIR, cleanSrc);
        if (!fs.existsSync(inputFile)) {
          res.writeHead(404, {"Content-Type": "application/json"});
          res.end(JSON.stringify({ error: "Mask file not found: " + cleanSrc }));
          return;
        }

        // Write to a sibling file first, then atomically replace original.
        const ext = path.extname(inputFile);
        const base = inputFile.slice(0, -ext.length);
        const tmpFile = `${base}.feather_tmp${ext}`;

        // FFmpeg filter chain:
        //   split → one branch keeps RGB; other extracts alpha, blurs it → alphamerge
        //
        // Filter graph:
        //   [0:v]split=2[rgb][a];
        //   [a]alphaextract,gblur=sigma=S[blurred_a];
        //   [rgb][blurred_a]alphamerge[out]
        //
        // Encode output as VP9 with yuva420p to preserve alpha.
        const filterGraph =
          `[0:v]split=2[rgb][a];` +
          `[a]alphaextract,gblur=sigma=${sigmaVal}[blurred_a];` +
          `[rgb][blurred_a]alphamerge[out]`;

        const startedAt = Date.now();
        const { spawn } = require("child_process");
        const args = [
          "-y",
          "-i", inputFile,
          "-filter_complex", filterGraph,
          "-map", "[out]",
          "-c:v", "libvpx-vp9",
          "-pix_fmt", "yuva420p",
          "-b:v", "0",
          "-crf", "28",
          "-row-mt", "1",
          "-auto-alt-ref", "0", // required for alpha
          tmpFile,
        ];
        console.log("[feather-person-mask] ffmpeg", args.join(" "));
        const ff = spawn(ffbin("ffmpeg"), args);
        let stderr = "";
        ff.stderr.on("data", d => { stderr += d.toString(); });
        ff.on("error", (err) => {
          try { if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile); } catch {}
          res.writeHead(500, {"Content-Type": "application/json"});
          res.end(JSON.stringify({ error: "Failed to spawn ffmpeg: " + err.message }));
        });
        ff.on("close", (code) => {
          if (code !== 0) {
            try { if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile); } catch {}
            console.error("[feather-person-mask] ffmpeg failed:\n" + stderr);
            res.writeHead(500, {"Content-Type": "application/json"});
            res.end(JSON.stringify({
              error: "ffmpeg exited with code " + code,
              stderr: stderr.split("\n").slice(-10).join("\n"),
            }));
            return;
          }
          // Atomic swap: rename tmp → original
          try {
            fs.renameSync(tmpFile, inputFile);
          } catch (e) {
            res.writeHead(500, {"Content-Type": "application/json"});
            res.end(JSON.stringify({ error: "Failed to replace mask file: " + e.message }));
            return;
          }
          const elapsed = ((Date.now() - startedAt) / 1000).toFixed(1);
          console.log(`[feather-person-mask] ✓ done in ${elapsed}s (sigma=${sigmaVal})`);
          res.writeHead(200, {"Content-Type": "application/json"});
          res.end(JSON.stringify({
            ok: true,
            newSrc: cleanSrc, // same path — we overwrote
            sigma: sigmaVal,
            elapsed,
          }));
        });
      } catch (e) {
        res.writeHead(400, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // O endpoint /api/render-overlay-segments (POST + /status) foi removido:
  // spawnava o render por navegador, e O motor de navegador saiu do Klipe.
  // Era otimizacao de quando o overlay levava 11 min; o MotionCore faz em 3,3s.


  // ── EXPORT DAVINCI FULL (automated multi-track pipeline) ──
  if (url.pathname === "/api/export-davinci-full" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", async () => {
      const RESOLVEFORGE = "http://localhost:8020";
      const http_fetch = async (fetchUrl, opts = {}) => {
        return new Promise((_res, _rej) => {
          const u = new URL(fetchUrl);
          const lib = require("http");
          const r = lib.request({ hostname: u.hostname, port: u.port, path: u.pathname, method: opts.method || "GET", headers: opts.headers || {} }, resp => {
            let d = "";
            resp.on("data", c => d += c);
            resp.on("end", () => { try { _res(JSON.parse(d)); } catch(e) { _res({ raw: d }); } });
          });
          r.on("error", _rej);
          if (opts.body) r.write(opts.body);
          r.end();
        });
      };

      global._davinciExport = {
        status: "running",
        step: 1,
        totalSteps: 5,
        stepName: "Gerando overlay segments...",
        startedAt: Date.now(),
        error: null,
      };

      const updateStep = (step, name) => {
        global._davinciExport.step = step;
        global._davinciExport.stepName = name;
        console.log(`[DaVinci Full] Step ${step}/5: ${name}`);
      };

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true, message: "DaVinci Full export started (5 steps)" }));

      // Run pipeline async
      (async () => {
        try {
          // Step 1: Render overlay segments
          updateStep(1, "Renderizando overlay segments (ProRes 4444 alpha)...");
          const config = readConfig();
          const titles = config.titles || [];
          const fps = config.fps || 30;

          if (titles.length > 0) {
            const totalDur = config.videoDuration || 0;
            const totalFrames = Math.ceil(totalDur * fps);
            const maxFrame = Math.max(0, totalFrames - 1);

            const sorted = [...titles].sort((a, b) => a.startSec - b.startSec);
            const segments = [];
            let seg = { start: Math.max(0, sorted[0].startSec - 0.5), end: sorted[0].endSec + 0.5, titles: [sorted[0]] };
            for (let i = 1; i < sorted.length; i++) {
              if (sorted[i].startSec - seg.end < 2) {
                seg.end = sorted[i].endSec + 0.5;
                seg.titles.push(sorted[i]);
              } else {
                segments.push(seg);
                seg = { start: Math.max(0, sorted[i].startSec - 0.5), end: sorted[i].endSec + 0.5, titles: [sorted[i]] };
              }
            }
            segments.push(seg);

            const overlayDir = path.join(__dirname, "output", "overlay_segments");
            if (!fs.existsSync(overlayDir)) fs.mkdirSync(overlayDir, { recursive: true });

            // Render segments using TitlesOverlay composition
            for (let i = 0; i < segments.length; i++) {
              const s = segments[i];
              const startFrame = Math.max(0, Math.floor(s.start * fps));
              // Clamp endFrame ao max valido da composicao (totalFrames - 1) — evita off-by-one no ultimo segmento
              const endFrame = Math.min(maxFrame, Math.ceil(Math.min(totalDur, s.end) * fps));
              const outFile = path.join(overlayDir, `overlay_${String(i).padStart(3, "0")}.mov`);

              updateStep(1, `Overlay segment ${i + 1}/${segments.length}...`);

              // Era o render por navegador com ProRes 4444. O
              // MotionCore ja fazia exatamente este overlay com alpha e ja
              // aceitava janela de frames desde que o preview foi escrito —
              // faltava so a porta de linha de comando, que agora existe.
              // Medido: 30 frames em 0,89s, sem subir Chrome nenhum.
              //
              // qtrle no lugar do ProRes 4444: os dois carregam alpha e o
              // Resolve le os dois; o qtrle e sem perdas e nao depende de
              // codec proprietario instalado na maquina do cliente.
              await new Promise((resolve, reject) => {
                let stderr = "";
                const child = spawn(pythonExe(), [
                  "-m", "motioncore.overlay",
                  _configPath, outFile,
                  "--frame-ini", String(startFrame),
                  "--frames", String(Math.max(1, endFrame - startFrame + 1)),
                ], { cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] });
                child.stdout.on("data", d => console.log("[Overlay]", d.toString().trim()));
                child.stderr.on("data", d => { stderr += d.toString(); console.error("[Overlay ERR]", d.toString().trim()); });
                child.on("error", e => reject(new Error(`Overlay segment ${i} spawn error: ${e.message}`)));
                child.on("close", code => code === 0 ? resolve() : reject(new Error(`Overlay segment ${i} failed (${code}): ${stderr.slice(-300)}`)));
              });
            }
            console.log(`[DaVinci Full] ${segments.length} overlay segments rendered`);
          }

          // Step 2: Generate FCPXML
          updateStep(2, "Gerando FCPXML multi-track...");
          // Call our own export-davinci endpoint internally
          const exportResult = await new Promise((_res2, _rej2) => {
            let data = "";
            const req2 = require("http").request({ hostname: "localhost", port: PORT, path: "/api/export-davinci", method: "POST", headers: { "Content-Type": "application/json" } }, resp2 => {
              resp2.on("data", c => data += c);
              resp2.on("end", () => { try { _res2(JSON.parse(data)); } catch(e) { _rej2(e); } });
            });
            req2.on("error", _rej2);
            req2.end("{}");
          });

          if (!exportResult.ok) throw new Error("FCPXML generation failed: " + (exportResult.error || "unknown"));
          const fcpxmlPath = exportResult.path;
          console.log(`[DaVinci Full] FCPXML saved: ${fcpxmlPath}`);

          // Step 3: Check ResolveForge is running + DaVinci connected
          updateStep(3, "Conectando ao DaVinci Resolve...");
          try {
            const info = await http_fetch(`${RESOLVEFORGE}/api/info`);
            if (!info.connected) {
              global._davinciExport.status = "waiting_resolve";
              global._davinciExport.stepName = "DaVinci Resolve não está aberto. Abra o DaVinci e tente novamente.";
              return;
            }
          } catch(e) {
            global._davinciExport.status = "error";
            global._davinciExport.error = "ResolveForge não está rodando (porta 8020). Inicie com: python -m uvicorn server:app --port 8020";
            return;
          }

          // Step 4: Create new project + Import FCPXML into DaVinci
          updateStep(4, "Criando projeto e importando timeline no DaVinci...");
          const timestamp = new Date().toISOString().slice(0,16).replace(/[T:]/g, "-");
          const projName = `MotionForge_${timestamp}`;
          const luaPath = fcpxmlPath.replace(/\\/g, "/");
          const importResult = await http_fetch(`${RESOLVEFORGE}/api/lua/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              script: `
                resolve = bmd.scriptapp("Resolve")
                if not resolve then print("FAIL:no_resolve") return end
                local pm = resolve:GetProjectManager()
                local proj = pm:CreateProject("${projName}")
                if not proj then
                    proj = pm:GetCurrentProject()
                    if not proj then print("FAIL:no_project") return end
                end
                print("PROJECT:" .. proj:GetName())
                local pool = proj:GetMediaPool()
                local tl = pool:ImportTimelineFromFile("${luaPath}", {importSourceClips = true})
                if tl then
                    proj:SetCurrentTimeline(tl)
                    print("OK:" .. tl:GetName())
                else
                    print("FAIL:import_nil")
                end
              `,
              timeout: 60
            })
          });

          if (!importResult.success) {
            throw new Error("DaVinci import failed: " + (importResult.output || JSON.stringify(importResult)));
          }
          console.log(`[DaVinci Full] Timeline imported into DaVinci: ${importResult.output}`);

          // Step 5: Apply zooms via Lua script
          updateStep(5, "Aplicando zooms via Fusion...");
          const zoomScript = path.join(__dirname, "output", "_apply_zooms_v2.lua");
          if (fs.existsSync(zoomScript)) {
            const luaResult = await http_fetch(`${RESOLVEFORGE}/api/lua/run`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ file_path: zoomScript, timeout: 120 })
            });
            console.log(`[DaVinci Full] Zoom script result: ${JSON.stringify(luaResult)}`);
          } else {
            console.log(`[DaVinci Full] No zoom script found, skipping`);
          }

          // Done!
          global._davinciExport.status = "done";
          global._davinciExport.stepName = "Exportação completa! Timeline no DaVinci com multi-track + zooms.";
          global._davinciExport.finishedAt = Date.now();
          const elapsed = ((Date.now() - global._davinciExport.startedAt) / 1000).toFixed(0);
          console.log(`[DaVinci Full] Complete in ${elapsed}s`);

        } catch(e) {
          global._davinciExport.status = "error";
          global._davinciExport.error = e.message;
          console.error("[DaVinci Full] Error:", e.message);
        }
      })();
    });
    return;
  }

  // DaVinci Full export status
  if (url.pathname === "/api/export-davinci-full/status" && req.method === "GET") {
    const r = global._davinciExport;
    if (!r) {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "idle" }));
      return;
    }
    const elapsed = ((Date.now() - r.startedAt) / 1000).toFixed(0);
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: r.status,
      step: r.step,
      totalSteps: r.totalSteps,
      stepName: r.stepName,
      elapsed: elapsed + "s",
      error: r.error,
    }));
    return;
  }

  // Serve rendered files — supports Range requests pra streaming inline em <video>
  if (url.pathname.startsWith("/output/")) {
    const filePath = path.join(__dirname, url.pathname);
    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      const stat = fs.statSync(filePath);
      const fileSize = stat.size;
      const range = req.headers.range;
      // Force download via ?download=1 query param; default = inline streaming
      const forceDownload = url.searchParams && url.searchParams.get("download") === "1";
      const dispositionInline = forceDownload
        ? `attachment; filename="${path.basename(filePath)}"`
        : `inline; filename="${path.basename(filePath)}"`;
      if (range) {
        const intervalo = intervaloBytes(range, fileSize);
        if (!intervalo) {
          res.writeHead(416, { "Content-Range": `bytes */${fileSize}` });
          res.end();
          return;
        }
        const { start, end } = intervalo;
        const chunkSize = end - start + 1;
        res.writeHead(206, {
          "Content-Range": `bytes ${start}-${end}/${fileSize}`,
          "Accept-Ranges": "bytes",
          "Content-Length": chunkSize,
          "Content-Type": "video/mp4",
          "Content-Disposition": dispositionInline,
          "Cache-Control": "no-cache, must-revalidate",
        });
        fs.createReadStream(filePath, { start, end }).pipe(res);
      } else {
        res.writeHead(200, {
          "Content-Type": "video/mp4",
          "Content-Length": fileSize,
          "Accept-Ranges": "bytes",
          "Content-Disposition": dispositionInline,
          "Cache-Control": "no-cache, must-revalidate",
        });
        fs.createReadStream(filePath).pipe(res);
      }
      return;
    }
  }

  // ── PROJECT MANAGEMENT ──

  // List saved projects
  if (url.pathname === "/api/projects" && req.method === "GET") {
    if (!fs.existsSync(PROJECTS_DIR)) fs.mkdirSync(PROJECTS_DIR, { recursive: true });
    const projects = [];
    const seen = new Set();

    // 1) Projetos REAIS em public/projects/ (criados por YouTube import, pipeline DaVinci, etc)
    const publicProjs = path.join(PUBLIC_DIR, "projects");
    if (fs.existsSync(publicProjs)) {
      for (const name of fs.readdirSync(publicProjs)) {
        const projDir = path.join(publicProjs, name);
        if (!fs.statSync(projDir).isDirectory()) continue;
        const configPath = path.join(projDir, "edit_config.json");
        if (!fs.existsSync(configPath)) continue;
        const stat = fs.statSync(configPath);
        let cfg = {};
        try { cfg = JSON.parse(fs.readFileSync(configPath, "utf-8")); } catch(e) {}
        projects.push({
          name,
          savedAt: stat.mtime.toISOString(),
          videoSrc: cfg.videoSrc || '',
          duration: cfg.videoDuration || 0,
          source: 'public',
        });
        seen.add(name);
      }
    }

    // 2) Snapshots em motionforge/projects/ (salvos via "Save Project")
    for (const name of fs.readdirSync(PROJECTS_DIR)) {
      const projDir = path.join(PROJECTS_DIR, name);
      if (!fs.statSync(projDir).isDirectory()) continue;
      const configPath = path.join(projDir, "edit_config.json");
      if (!fs.existsSync(configPath)) continue;
      if (seen.has(name)) continue;  // ja listado de public/projects/
      const stat = fs.statSync(configPath);
      let meta = {};
      const metaPath = path.join(projDir, "meta.json");
      if (fs.existsSync(metaPath)) {
        try { meta = JSON.parse(fs.readFileSync(metaPath, "utf-8")); } catch(e) {}
      }
      projects.push({
        name,
        savedAt: meta.savedAt || stat.mtime.toISOString(),
        videoSrc: meta.videoSrc || '',
        duration: meta.duration || 0,
        source: 'snapshot',
      });
    }
    projects.sort((a, b) => new Date(b.savedAt) - new Date(a.savedAt));
    res.writeHead(200, {"Content-Type": "application/json"});
    res.end(JSON.stringify(projects));
    return;
  }

  // Save current project
  if (url.pathname === "/api/projects/save" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const { name } = JSON.parse(body);
        if (!name || name.trim().length === 0) {
          res.writeHead(400); res.end(JSON.stringify({ error: "Nome do projeto é obrigatório" })); return;
        }
        const safeName = name.trim().replace(/[<>:"/\\|?*]/g, '_');
        const projDir = path.join(PROJECTS_DIR, safeName);
        if (!fs.existsSync(projDir)) fs.mkdirSync(projDir, { recursive: true });

        // Copy current config
        const config = readConfig();
        fs.writeFileSync(path.join(projDir, "edit_config.json"), JSON.stringify(config, null, 2), "utf-8");

        // Save meta
        const meta = {
          savedAt: new Date().toISOString(),
          videoSrc: config.videoSrc || '',
          duration: config.videoDuration || 0,
          titleCount: (config.titles || []).length,
          brollCount: (config.brolls || []).length,
        };
        fs.writeFileSync(path.join(projDir, "meta.json"), JSON.stringify(meta, null, 2), "utf-8");

        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ ok: true, name: safeName, savedAt: meta.savedAt }));
      } catch(e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // Load a saved project — tenta public/projects/ primeiro, depois projects/
  if (url.pathname === "/api/projects/load" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const { name } = JSON.parse(body);
        // Uma aba em /p/<slug> nunca deve "carregar" outro projeto copiando
        // dados sobre o arquivo que ela ja edita. O front atual navega para a
        // URL propria; esta trava protege tambem abas antigas ainda abertas.
        if (_projeto) {
          res.writeHead(409, {"Content-Type": "application/json"});
          res.end(JSON.stringify({
            error: "Abra o projeto pela URL propria",
            redirect: `/p/${encodeURIComponent(name || "")}`,
          }));
          return;
        }
        // Try public/projects/ first (real projects)
        let configPath = path.join(PUBLIC_DIR, "projects", name, "edit_config.json");
        if (!fs.existsSync(configPath)) {
          // Fall back to motionforge/projects/ (snapshots)
          configPath = path.join(PROJECTS_DIR, name, "edit_config.json");
        }
        if (!fs.existsSync(configPath)) {
          res.writeHead(404); res.end(JSON.stringify({ error: "Projeto não encontrado" })); return;
        }
        const config = JSON.parse(fs.readFileSync(configPath, "utf-8"));
        writeConfig(config);
        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ ok: true, name }));
      } catch(e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // Upload video file to a project — POST raw bytes with X-Project-Slug header
  // Saves to public/projects/<slug>/video_preview.<ext>, runs ffprobe, updates config
  // ─── GRAVACAO DE TELA / CAMERA ──────────────────────────────────────
  // Recebe o WebM que o MediaRecorder produziu e devolve MP4 no projeto.
  if (url.pathname === "/api/gravacao" && req.method === "POST") {
    const slug = slugSeguro(req.headers["x-projeto"] || _projeto || "") || "";
    if (!slug) {
      res.writeHead(400, {"Content-Type":"application/json"});
      return res.end(JSON.stringify({ error: "sem projeto: grave com um projeto aberto" }));
    }
    const dir = path.join(PUBLIC_DIR, "projects", slug, "gravacoes");
    fs.mkdirSync(dir, { recursive: true });

    const carimbo = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const tipo = (req.headers["x-tipo"] || "tela").toString().replace(/[^a-z]/gi, "") || "tela";
    const bruto = path.join(dir, `${tipo}_${carimbo}.webm`);
    const final = path.join(dir, `${tipo}_${carimbo}.mp4`);

    const escrita = fs.createWriteStream(bruto);
    let bytes = 0;
    req.on("data", c => { bytes += c.length; escrita.write(c); });
    req.on("end", () => {
      escrita.end(() => {
        if (bytes < 2000) {
          try { fs.unlinkSync(bruto); } catch {}
          res.writeHead(400, {"Content-Type":"application/json"});
          return res.end(JSON.stringify({ error: "gravacao vazia" }));
        }
        // scale para largura/altura PAR: janela de tela costuma vir impar e o
        // H.264 recusa. Arredonda para baixo, sem esticar a imagem.
        const ff = spawn(ffbin("ffmpeg"), ["-y", "-hide_banner", "-loglevel", "error",
          "-i", bruto,
          "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
          final]);
        let erro = "";
        ff.stderr.on("data", d => { erro += d.toString(); });
        ff.on("close", code => {
          if (code !== 0 || !fs.existsSync(final)) {
            res.writeHead(500, {"Content-Type":"application/json"});
            return res.end(JSON.stringify({ error: "conversao falhou: " + erro.slice(-300) }));
          }
          // o .webm fica: se a conversao ficou ruim, o original ainda existe
          const rel = `projects/${slug}/gravacoes/${path.basename(final)}`;
          const mb = (fs.statSync(final).size / 1e6).toFixed(1);
          console.log(`[Gravacao] ${rel} (${mb} MB)`);
          res.writeHead(200, {"Content-Type":"application/json"});
          res.end(JSON.stringify({ ok: true, src: rel, mb: Number(mb) }));
        });
      });
    });
    return;
  }


  if (url.pathname === "/api/projects/upload-video" && req.method === "POST") {
    try {
      const slug = (req.headers["x-project-slug"] || "").toString().trim();
      const filenameHdr = (req.headers["x-filename"] || "video.mp4").toString().trim();
      const ext = (filenameHdr.match(/\.(\w+)$/) || [, "mp4"])[1].toLowerCase();
      if (!slug) {
        res.writeHead(400); res.end(JSON.stringify({ error: "X-Project-Slug obrigatorio" })); return;
      }
      const safeSlug = slug.replace(/[^a-z0-9\-]/gi, "");
      const projDir = path.join(PUBLIC_DIR, "projects", safeSlug);
      if (!fs.existsSync(projDir)) fs.mkdirSync(projDir, { recursive: true });

      const targetName = `video_preview.${ext}`;
      const targetPath = path.join(projDir, targetName);
      const writeStream = fs.createWriteStream(targetPath);
      let totalBytes = 0;
      req.on("data", chunk => { totalBytes += chunk.length; writeStream.write(chunk); });
      req.on("end", () => {
        writeStream.end(() => {
          // Probe with ffprobe
          const ffprobe = spawn(ffbin("ffprobe"), [
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            targetPath
          ]);
          let probeOut = ""; let probeErr = "";
          ffprobe.stdout.on("data", d => probeOut += d);
          ffprobe.stderr.on("data", d => probeErr += d);
          ffprobe.on("close", code => {
            let meta = { width: 1920, height: 1080, fps: 30, duration: 0 };
            try {
              const probe = JSON.parse(probeOut);
              const stream = probe.streams && probe.streams[0];
              if (stream) {
                meta.width = stream.width || meta.width;
                meta.height = stream.height || meta.height;
                meta.duration = parseFloat(stream.duration || probe.format?.duration || 0);
                if (stream.r_frame_rate) {
                  const [n, d] = stream.r_frame_rate.split("/").map(Number);
                  if (d) meta.fps = Math.round(n / d);
                }
              }
            } catch(e) { /* fall back to defaults */ }

            // Update edit_config.json in the project
            const cfgPath = path.join(projDir, "edit_config.json");
            let cfg = {};
            if (fs.existsSync(cfgPath)) {
              try { cfg = JSON.parse(fs.readFileSync(cfgPath, "utf-8")); } catch {}
            }
            cfg.videoSrc = `projects/${safeSlug}/${targetName}`;
            cfg.videoDuration = meta.duration;
            cfg.width = meta.width;
            cfg.height = meta.height;
            cfg.fps = meta.fps;
            cfg.titles = cfg.titles || [];
            cfg.brolls = cfg.brolls || [];
            cfg.zooms = cfg.zooms || [];
            cfg.captions = cfg.captions || [];
            cfg.sfx = cfg.sfx || [];
            cfg.musics = cfg.musics || [];
            cfg.shorts = cfg.shorts || [];
            cfg.motionforge_clips = cfg.motionforge_clips || [];
            fs.writeFileSync(cfgPath, JSON.stringify(cfg, null, 2), "utf-8");
            // Also activate
            writeConfig(cfg);

            res.writeHead(200, {"Content-Type": "application/json"});
            res.end(JSON.stringify({ ok: true, slug: safeSlug, videoSrc: cfg.videoSrc, ...meta, bytes: totalBytes }));
          });
        });
      });
      req.on("error", e => {
        try { writeStream.destroy(); fs.unlinkSync(targetPath); } catch {}
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      });
    } catch(e) {
      res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // Copy LOCAL video file (path on disk) to project — much faster than upload for big files
  if (url.pathname === "/api/projects/import-local-video" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const opts = body ? JSON.parse(body) : {};
        const slug = (opts.slug || "").trim().replace(/[^a-z0-9\-]/gi, "");
        const localPath = (opts.path || "").trim();
        if (!slug || !localPath) {
          res.writeHead(400); res.end(JSON.stringify({ error: "slug e path obrigatorios" })); return;
        }
        if (!fs.existsSync(localPath)) {
          res.writeHead(404); res.end(JSON.stringify({ error: `arquivo nao existe: ${localPath}` })); return;
        }
        const projDir = path.join(PUBLIC_DIR, "projects", slug);
        if (!fs.existsSync(projDir)) fs.mkdirSync(projDir, { recursive: true });
        const ext = (path.extname(localPath) || ".mp4").toLowerCase().replace(".", "");
        const targetName = `video_preview.${ext}`;
        const targetPath = path.join(projDir, targetName);
        // Copy file (fast since it's same disk in most cases)
        fs.copyFileSync(localPath, targetPath);

        // Probe
        const ffprobe = spawn(ffbin("ffprobe"), [
          "-v", "error",
          "-select_streams", "v:0",
          "-show_entries", "stream=width,height,r_frame_rate,duration",
          "-show_entries", "format=duration",
          "-of", "json",
          targetPath
        ]);
        let probeOut = "";
        ffprobe.stdout.on("data", d => probeOut += d);
        ffprobe.on("close", () => {
          let meta = { width: 1920, height: 1080, fps: 30, duration: 0 };
          try {
            const probe = JSON.parse(probeOut);
            const stream = probe.streams && probe.streams[0];
            if (stream) {
              meta.width = stream.width || meta.width;
              meta.height = stream.height || meta.height;
              meta.duration = parseFloat(stream.duration || probe.format?.duration || 0);
              if (stream.r_frame_rate) {
                const [n, d] = stream.r_frame_rate.split("/").map(Number);
                if (d) meta.fps = Math.round(n / d);
              }
            }
          } catch {}

          const cfgPath = path.join(projDir, "edit_config.json");
          let cfg = {};
          if (fs.existsSync(cfgPath)) {
            try { cfg = JSON.parse(fs.readFileSync(cfgPath, "utf-8")); } catch {}
          }
          cfg.videoSrc = `projects/${slug}/${targetName}`;
          cfg.videoDuration = meta.duration;
          cfg.width = meta.width;
          cfg.height = meta.height;
          cfg.fps = meta.fps;
          cfg.titles = cfg.titles || [];
          cfg.brolls = cfg.brolls || [];
          cfg.zooms = cfg.zooms || [];
          cfg.captions = cfg.captions || [];
          cfg.sfx = cfg.sfx || [];
          cfg.musics = cfg.musics || [];
          cfg.shorts = cfg.shorts || [];
          cfg.motionforge_clips = cfg.motionforge_clips || [];
          fs.writeFileSync(cfgPath, JSON.stringify(cfg, null, 2), "utf-8");
          writeConfig(cfg);

          res.writeHead(200, {"Content-Type": "application/json"});
          res.end(JSON.stringify({ ok: true, slug, videoSrc: cfg.videoSrc, ...meta }));
        });
      } catch(e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // Create a NEW empty project — folder + minimal edit_config.json
  // POST { slug, videoSrc? } → cria public/projects/<slug>/edit_config.json
  if (url.pathname === "/api/projects/create" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const opts = body ? JSON.parse(body) : {};
        let slug = (opts.slug || "").trim();
        const videoSrc = (opts.videoSrc || "").trim();
        const aspectRatio = opts.aspectRatio || "16:9";
        const width = opts.width || 1920;
        const height = opts.height || 1080;
        const fps = opts.fps || 30;

        if (!slug) {
          res.writeHead(400); res.end(JSON.stringify({ error: "slug obrigatorio" })); return;
        }
        // sanitize slug: lowercase, alphanumeric + dash only
        slug = slug.toLowerCase().replace(/[^a-z0-9\-]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
        if (!slug) {
          res.writeHead(400); res.end(JSON.stringify({ error: "slug invalido apos sanitizar" })); return;
        }

        const projDir = path.join(PUBLIC_DIR, "projects", slug);
        if (fs.existsSync(projDir) && fs.existsSync(path.join(projDir, "edit_config.json"))) {
          res.writeHead(409); res.end(JSON.stringify({ error: `projeto "${slug}" ja existe` })); return;
        }
        fs.mkdirSync(projDir, { recursive: true });

        // Minimal but valid edit_config skeleton
        const skeleton = {
          videoSrc: videoSrc || `projects/${slug}/video_preview.mp4`,
          videoDuration: 0,
          aspectRatio,
          width,
          height,
          fps,
          titles: [],
          brolls: [],
          zooms: [],
          captions: [],
          sfx: [],
          musics: [],
          shorts: [],
          motionforge_clips: [],
          createdAt: new Date().toISOString(),
        };
        fs.writeFileSync(path.join(projDir, "edit_config.json"), JSON.stringify(skeleton, null, 2), "utf-8");

        // Also activate (so on reload the editor picks it up)
        writeConfig(skeleton);

        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ ok: true, slug, path: `projects/${slug}/` }));
      } catch(e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // Delete a saved project
  if (url.pathname === "/api/projects/delete" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const { name } = JSON.parse(body);
        const projDir = path.join(PROJECTS_DIR, name);
        if (!fs.existsSync(projDir)) {
          res.writeHead(404); res.end(JSON.stringify({ error: "Projeto não encontrado" })); return;
        }
        fs.rmSync(projDir, { recursive: true, force: true });
        res.writeHead(200, {"Content-Type": "application/json"});
        res.end(JSON.stringify({ ok: true }));
      } catch(e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // ── IMPORT YOUTUBE (download + preview + transcribe + skeleton config) ──
  // POST { url, slug? } → roda import_youtube.py em background
  if (url.pathname === "/api/import-youtube" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const opts = body ? JSON.parse(body) : {};
        const ytUrl = (opts.url || "").trim();
        const slug = (opts.slug || "").trim() || "auto";
        if (!ytUrl) {
          res.writeHead(400); res.end(JSON.stringify({ error: "url obrigatorio" })); return;
        }

        if (global._importYoutube && global._importYoutube.status === "running") {
          res.writeHead(409); res.end(JSON.stringify({ error: "ja existe import rodando" })); return;
        }

        const condaPython = pythonExe();
        const args = ["import_youtube.py", ytUrl, slug];
        console.log(`[ImportYT] Spawning: ${condaPython} ${args.join(" ")}`);

        global._importYoutube = {
          status: "running",
          startedAt: Date.now(),
          url: ytUrl,
          slug: slug === "auto" ? null : slug,
          phase: "starting",
          logTail: [],
          error: null,
        };

        const child = spawn(condaPython, args, {
          cwd: __dirname,
          stdio: ["ignore", "pipe", "pipe"],
          shell: false,
          env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        });
        global._importYoutube.childProcess = child;

        const captureLine = (line) => {
          const s = line.trim();
          if (!s) return;
          console.log("[ImportYT]", s);
          global._importYoutube.logTail.push(s);
          if (global._importYoutube.logTail.length > 80) global._importYoutube.logTail.shift();
          // Parse phase: lines like "[DOWNLOAD] ..." update phase
          const m = s.match(/^\[([A-Z]+)\]/);
          if (m) {
            global._importYoutube.phase = m[1].toLowerCase();
            // Capture slug from "[INFO] slug derivado: xxx"
            const slugMatch = s.match(/slug derivado:\s*(\S+)/);
            if (slugMatch) global._importYoutube.slug = slugMatch[1];
            // Or from final "[DONE] slug=xxx"
            const doneMatch = s.match(/\[DONE\]\s*slug=(\S+)/);
            if (doneMatch) global._importYoutube.slug = doneMatch[1];
          }
        };
        let stdoutBuf = "", stderrBuf = "";
        child.stdout.on("data", d => {
          stdoutBuf += d.toString();
          const lines = stdoutBuf.split("\n");
          stdoutBuf = lines.pop();
          lines.forEach(captureLine);
        });
        child.stderr.on("data", d => {
          stderrBuf += d.toString();
          const lines = stderrBuf.split("\n");
          stderrBuf = lines.pop();
          lines.forEach(captureLine);
        });
        child.on("close", code => {
          if (stdoutBuf) captureLine(stdoutBuf);
          if (stderrBuf) captureLine(stderrBuf);
          const elapsed = Math.round((Date.now() - global._importYoutube.startedAt) / 1000);
          global._importYoutube.elapsed = elapsed;
          if (code === 0) {
            global._importYoutube.status = "done";
            global._importYoutube.phase = "done";
            console.log(`[ImportYT] DONE em ${elapsed}s | slug=${global._importYoutube.slug}`);
          } else {
            global._importYoutube.status = "error";
            global._importYoutube.error = `exit code ${code}`;
            console.error(`[ImportYT] FAIL exit=${code} em ${elapsed}s`);
          }
        });

        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, message: "Import iniciado" }));
      } catch (e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // GET status do import-youtube
  if (url.pathname === "/api/import-youtube/status" && req.method === "GET") {
    const s = global._importYoutube;
    if (!s) {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "idle" }));
      return;
    }
    const elapsed = s.elapsed != null ? s.elapsed : Math.round((Date.now() - s.startedAt) / 1000);
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: s.status,
      phase: s.phase,
      slug: s.slug,
      elapsed: `${elapsed}s`,
      logTail: s.logTail,
      error: s.error,
    }));
    return;
  }

  // API: POST export-davinci — generate FCPXML 1.9 for DaVinci Resolve import
  if (url.pathname === "/api/export-davinci" && req.method === "POST") {
    try {
      const config = readConfig();
      const fps = config.fps || 24;
      const totalDur = config.videoDuration || 0;
      // Use original video (not preview) for DaVinci
      const videoSrc = fs.existsSync(path.join(PUBLIC_DIR, "video.mp4")) ? "video.mp4" : (config.videoSrc || "video.mp4");
      const videoAbsPath = path.resolve(PUBLIC_DIR, videoSrc).replace(/\\/g, "/");
      const seqName = "MotionForge Export";

      // Detect real fps: 23.976 uses 1001/24000, 29.97 uses 1001/30000, else integer
      const is2397 = (fps === 24 || fps === 23.976);
      const is2997 = (fps === 30 || fps === 29.97);
      const timeBase = is2397 ? 24000 : is2997 ? 30000 : fps * 1000;
      const frameDurNum = is2397 ? 1001 : is2997 ? 1001 : 1000;
      const frameDur = `${frameDurNum}/${timeBase}s`;
      // Time conversion: seconds to FCPXML rational time
      // For 23.976fps: sec * 24000 / 1001 = frames, expressed as "frames*1001/24000s"
      const toTime = (sec) => {
        const frames = Math.round(sec * timeBase / frameDurNum);
        return `${frames * frameDurNum}/${timeBase}s`;
      };
      const toFrameTime = toTime;

      function escXml(str) {
        return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");
      }

      // ── Build resources (assets) ──
      const brolls = config.brolls || [];
      const musicTracks = config.musicTracks || [];
      const sfx = config.sfx || [];
      const titles = config.titles || [];
      const zooms = config.zooms || [];

      let resources = "";
      const fmtName = is2397 ? "FFVideoFormat1080p2398" : is2997 ? "FFVideoFormat1080p2997" : `FFVideoFormat1080p${fps}`;
      resources += `    <format id="r0" name="${fmtName}" frameDuration="${frameDur}" width="1920" height="1080"/>\n`;

      // Main video asset
      resources += `    <asset id="r1" name="${escXml(videoSrc)}" start="0s" duration="${toTime(totalDur)}" hasVideo="1" hasAudio="1" format="r0">\n`;
      resources += `      <media-rep kind="original-media" src="file:///${videoAbsPath}"/>\n`;
      resources += `    </asset>\n`;

      // B-roll assets
      let assetId = 2;
      const brollAssets = {};
      for (const b of brolls) {
        const bPath = path.resolve(PUBLIC_DIR, b.src).replace(/\\/g, "/");
        if (!brollAssets[bPath]) {
          const id = `r${assetId++}`;
          const bDur = (b.endSec || b.startSec + 5) - b.startSec;
          resources += `    <asset id="${id}" name="${escXml(b.label || b.src)}" start="0s" duration="${toTime(bDur)}" hasVideo="1" hasAudio="0" format="r0">\n`;
          resources += `      <media-rep kind="original-media" src="file:///${bPath}"/>\n`;
          resources += `    </asset>\n`;
          brollAssets[bPath] = id;
        }
      }

      // (Music/SFX assets removidos — ver nota abaixo no spine sobre incompatibilidade)
      const musicAssets = {};
      const sfxAssets = {};

      // ── Build connected clips (all lanes go INSIDE the main asset-clip) ──
      let connectedClips = "";

      // B-roll lane (video lane 1)
      for (const b of brolls) {
        const bPath = path.resolve(PUBLIC_DIR, b.src).replace(/\\/g, "/");
        const refId = brollAssets[bPath];
        const dur = (b.endSec || b.startSec + 5) - b.startSec;
        connectedClips += `              <asset-clip ref="${refId}" lane="1" offset="${toTime(b.startSec)}" name="${escXml(b.label || b.src)}" duration="${toTime(dur)}" start="0s" format="r0"/>\n`;
      }

      // Titles lane (video lane 2) — use overlay segments if available, otherwise gap markers
      const overlayDir = path.join(__dirname, "output", "overlay_segments");
      const overlayFiles = fs.existsSync(overlayDir) ? fs.readdirSync(overlayDir).filter(f => f.endsWith(".mov")).sort() : [];

      if (overlayFiles.length > 0) {
        // Group titles into segments (same logic as DaVinci Full render)
        const sorted = [...titles].sort((a, b) => a.startSec - b.startSec);
        const titleSegments = [];
        if (sorted.length > 0) {
          let seg = { start: Math.max(0, sorted[0].startSec - 0.5), end: sorted[0].endSec + 0.5 };
          for (let i = 1; i < sorted.length; i++) {
            if (sorted[i].startSec - seg.end < 2) {
              seg.end = sorted[i].endSec + 0.5;
            } else {
              titleSegments.push(seg);
              seg = { start: Math.max(0, sorted[i].startSec - 0.5), end: sorted[i].endSec + 0.5 };
            }
          }
          titleSegments.push(seg);
        }

        // Add overlay segment assets
        const overlayAssetIds = [];
        for (let oi = 0; oi < Math.min(overlayFiles.length, titleSegments.length); oi++) {
          const id = `r${assetId++}`;
          const oPath = path.resolve(overlayDir, overlayFiles[oi]).replace(/\\/g, "/");
          const seg = titleSegments[oi];
          const dur = seg.end - seg.start;
          resources += `    <asset id="${id}" name="overlay_${String(oi).padStart(3, '0')}" start="0s" duration="${toTime(dur)}" hasVideo="1" hasAudio="0" format="r0">\n`;
          resources += `      <media-rep kind="original-media" src="file:///${oPath}"/>\n`;
          resources += `    </asset>\n`;
          overlayAssetIds.push({ id, seg });
        }

        // Add overlay clips on lane 2 (V3)
        for (const oa of overlayAssetIds) {
          const dur = oa.seg.end - oa.seg.start;
          connectedClips += `              <asset-clip ref="${oa.id}" lane="2" offset="${toTime(oa.seg.start)}" name="Title Overlay" duration="${toTime(dur)}" start="0s" format="r0"/>\n`;
        }
      } else {
        // Fallback: gap markers for titles
        for (const t of titles) {
          const dur = (t.endSec || t.startSec + 5) - t.startSec;
          const titleText = (t.text || "").replace(/\n/g, " / ");
          const styleTag = (t.style || "title").toUpperCase();
          connectedClips += `              <gap name="[${escXml(styleTag)}] ${escXml(titleText)}" lane="2" offset="${toTime(t.startSec)}" duration="${toTime(dur)}">\n`;
          connectedClips += `                <note>${escXml(titleText)}</note>\n`;
          connectedClips += `              </gap>\n`;
        }
      }

      // Zooms lane (video lane 3)
      for (let zi = 0; zi < zooms.length; zi++) {
        const z = zooms[zi];
        const dur = (z.endSec || z.startSec + 3) - z.startSec;
        const intensity = z.intensity || 1.3;
        const scalePercent = Math.round(intensity * 100);
        const dir = (z.direction || 'in').replace(/([A-Z])/g, ' $1').trim().toUpperCase();
        connectedClips += `              <gap name="[ZOOM ${dir} ${scalePercent}%]" lane="3" offset="${toTime(z.startSec)}" duration="${toTime(dur)}">\n`;
        connectedClips += `                <note>Zoom ${dir} ${scalePercent}% ${z.focusX != null ? 'x:' + z.focusX + ' y:' + z.focusY : 'center'}</note>\n`;
        connectedClips += `              </gap>\n`;
      }

      // NOTA: Música e SFX foram REMOVIDOS do FCPXML porque DaVinci Resolve não importa
      // assets de áudio standalone via FCPXML 1.9 (retorna nil em ImportTimelineFromFile).
      // Solução: editar áudio no Klipe e exportar render direto, ou adicionar tracks
      // manualmente no DaVinci via Media Pool drag-and-drop.

      // ── Assemble FCPXML ──
      const xml = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.9">
  <resources>
${resources}  </resources>
  <library>
    <event name="MotionForge">
      <project name="${escXml(seqName)}">
        <sequence format="r0" duration="${toTime(totalDur)}" tcStart="0s" tcFormat="NDF">
          <spine>
            <asset-clip ref="r1" offset="0s" name="Main Video" duration="${toTime(totalDur)}" start="0s" format="r0" tcFormat="NDF">
${connectedClips}            </asset-clip>
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>`;

      // Save to output folder
      const outputDir = path.join(__dirname, "output");
      if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
      const xmlFilename = `motionforge_davinci_${timestamp}.fcpxml`;
      const xmlPath = path.join(outputDir, xmlFilename);
      fs.writeFileSync(xmlPath, xml, "utf-8");

      console.log(`[DaVinci Export] Saved FCPXML to ${xmlPath}`);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        ok: true,
        path: xmlPath.replace(/\\/g, "/"),
        filename: xmlFilename,
        tracks: {
          V1: "Main video",
          V2: `${brolls.length} b-roll clips (lane 1)`,
          V3: `${titles.length} title markers (lane 2)`,
          V4: `${zooms.length} zoom markers (lane 3)`,
          A1: "Main audio (embedded)",
          A2: `${musicTracks.length} music clips — SKIP (mixe no Klipe)`,
          A3: `${sfx.length} SFX clips — SKIP (mixe no Klipe)`
        }
      }));
    } catch (e) {
      console.error("[DaVinci Export] Error:", e);
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // ── ANALYZE SHORTS (auto-detect best clips) ──
  if (url.pathname === "/api/analyze-shorts" && req.method === "POST") {
    try {
      const config = readConfig();
      const videoDuration = config.videoDuration || 0;
      const titles = config.titles || [];
      const brolls = config.brolls || [];

      // Load transcription
      let transcription = [];
      let transcriptionPath = null;
      if (config.videoSrc && config.videoSrc.includes("/")) {
        const projDir = path.dirname(path.join(__dirname, "public", config.videoSrc));
        const projT = path.join(projDir, "transcription.json");
        if (fs.existsSync(projT)) transcriptionPath = projT;
      }
      if (!transcriptionPath) {
        const rootT = path.join(__dirname, "public", "transcription.json");
        if (fs.existsSync(rootT)) transcriptionPath = rootT;
      }
      if (transcriptionPath) {
        transcription = JSON.parse(fs.readFileSync(transcriptionPath, "utf-8"));
      }

      // --- HELPERS: snap em fronteiras de caption (Whisper) com bonus pra fim de frase
      // Captions do Whisper já vêm cortadas em pausas naturais (palavras inteiras).
      // Caption boundaries (cap.start/cap.end) são EXATAS no tempo do áudio.
      // Bonus quando a caption termina/começa em pontuação (.!?) — fim de frase ideal.
      const TERMINAL = /[.!?…]\s*$/;
      const startsWithPunct = (text) => /^[A-ZÁÉÍÓÚÂÊÔÃÕÇ]/.test((text || "").trim());

      const startCandidates = []; // { time, quality: 2=after period, 1=after comma, 0=just caption boundary }
      const endCandidates = [];
      for (let i = 0; i < transcription.length; i++) {
        const cap = transcription[i];
        const text = (cap.text || "").trim();
        // Caption start
        let startQ = 0;
        if (i === 0) startQ = 2;
        else {
          const prev = transcription[i - 1];
          const prevText = (prev.text || "").trim();
          if (TERMINAL.test(prevText)) startQ = 2;
          else if (prevText.endsWith(",")) startQ = 1;
          else if ((cap.start - prev.end) > 0.4) startQ = 1;
        }
        startCandidates.push({ time: cap.start, q: startQ });
        // Caption end
        let endQ = 0;
        if (TERMINAL.test(text)) endQ = 2;
        else if (text.endsWith(",")) endQ = 1;
        else if (i + 1 < transcription.length && (transcription[i + 1].start - cap.end) > 0.4) endQ = 1;
        else if (i === transcription.length - 1) endQ = 2;
        endCandidates.push({ time: cap.end, q: endQ });
      }

      // Score = quality bonus minus distance penalty
      const pickBest = (cands, target, lower, upper, preferBefore = false) => {
        let best = null;
        for (const c of cands) {
          if (c.time < lower || c.time > upper) continue;
          const dist = Math.abs(c.time - target);
          const distPenalty = preferBefore && c.time > target ? dist * 1.5 : dist;
          // quality 2 vale ~3s de proximidade, quality 1 vale ~1s
          const score = c.q * 3 - distPenalty;
          if (!best || score > best.score) best = { time: c.time, score };
        }
        return best ? best.time : null;
      };

      const snapStart = (target) => pickBest(startCandidates, target, target - 4, target + 3) ?? target;
      const snapEnd = (target, hardMax) => {
        // Busca COM folga até target+3 (mesmo se passa do hardMax) — clamp só no resultado
        const t = pickBest(endCandidates, target, target - 8, target + 3, true) ?? target;
        return Math.min(t + 0.3, hardMax);
      };

      // --- NOVA LÓGICA: análise semântica direta da transcrição ---
      // Ideia: extrair FRASES individuais do transcript (com timestamps via interpolação)
      // → detectar HOOKS (perguntas, dados, declarações fortes)
      // → pra cada hook, achar o PAYOFF mais natural 25-180s depois
      // → scorear arco completo (hook + densidade + duração + payoff)
      // → retornar top 10 não-sobrepostos

      // 1) Extrai frases do transcript
      const SENT_END_G = /[.!?…]+/g;
      const sentences = [];
      for (const cap of transcription) {
        const text = (cap.text || "").trim();
        const dur = cap.end - cap.start;
        if (!text || dur <= 0) continue;
        const tPerChar = dur / text.length;
        let lastPos = 0;
        let m;
        SENT_END_G.lastIndex = 0;
        while ((m = SENT_END_G.exec(text)) !== null) {
          const endPos = m.index + m[0].length;
          const sentText = text.slice(lastPos, endPos).trim();
          if (sentText.length > 2) {
            const endChar = endPos;
            sentences.push({
              startT: cap.start + lastPos * tPerChar,
              endT: Math.min(cap.end, cap.start + endChar * tPerChar),
              text: sentText,
              type: m[0].includes("?") ? "question" : m[0].includes("!") ? "exclaim" : "statement",
            });
          }
          lastPos = endPos;
          while (lastPos < text.length && /\s/.test(text[lastPos])) lastPos++;
        }
        // fragmento final sem pontuação
        if (lastPos < text.length) {
          const sentText = text.slice(lastPos).trim();
          if (sentText.length > 2) {
            sentences.push({
              startT: cap.start + lastPos * tPerChar,
              endT: cap.end,
              text: sentText,
              type: "fragment",
              noPunct: true,
            });
          }
        }
      }

      // 2) Hook score por frase
      const STRONG_WORDS = ["cuidado","atenção","nunca","sempre","jamais","importante","grave","sério","fatal","mito","verdade","real","chocante","incrível","perigoso","essencial","crucial","fundamental"];
      const STAT_RE = /\d+\s*%|\d+\s*mil|\d+\s*milh|\d+\s*a\s*\d+|\d+\s*(vezes|x)\b/;
      const PAYOFF_RE = /\b(por isso|então|resumindo|é por isso|ou seja|moral da história|no final|conclus|entende|percebe)\b/;
      const ENG_WORDS = ["nunca","sempre","importante","cuidado","atenção","perigoso","incrível","chocante","verdade","mentira","mito","real","precisa","deve","grave","sério","fatal","diagnóstico","tratamento","sintoma","déficit","funcional","suporte","dificuldade","autonomia"];

      const hookScore = (sent) => {
        let s = 0;
        const t = sent.text.toLowerCase();
        if (sent.type === "question") s += 10;
        if (sent.type === "exclaim") s += 6;
        if (STAT_RE.test(t)) s += 8;
        let strongCount = 0;
        for (const w of STRONG_WORDS) if (t.includes(w)) strongCount++;
        s += Math.min(strongCount * 3, 9);
        if (t.length >= 20 && t.length <= 90) s += 4;
        if (sent.type === "question" && t.length < 70) s += 3;
        return s;
      };

      // Helper: snapa um tempo para o cap.start que CONTÉM esse tempo (pro começo)
      // ou cap.end que contém/vem logo depois (pro fim).
      // Para END: estende até a PRÓXIMA caption que termina em `.!?` — evita cortar
      // no meio de uma lista (ex: "Trabalhar, estudar, cozinhar...")
      const snapToCapStart = (t) => {
        let best = t;
        for (const cap of transcription) {
          if (cap.start <= t + 0.5 && cap.end > t) { best = cap.start; break; }
        }
        return Math.max(0, best);
      };
      // Whisper captions raramente terminam em .!? (segmenta por pausa, não por frase).
      // Lógica: acha o LAST `.!?` que cai dentro do range [t, maxT+5] varrendo todas
      // as captions nesse range. Retorna o TIMESTAMP exato desse ponto (não cap.end).
      // Resultado: clip termina EXATO no fim de uma frase real, mesmo que isso fique
      // mid-caption. Captions são cropadas no client.
      const startsCapital = (txt) => {
        const f = (txt || "").trim()[0] || "";
        return f && f === f.toUpperCase() && f !== f.toLowerCase();
      };
      const snapToCapEnd = (t, maxT) => {
        const upper = (maxT !== undefined) ? maxT + 5 : Infinity;
        // Coleta TODAS as posições de .!? em [t, upper]
        const sentEnds = [];
        for (let i = 0; i < transcription.length; i++) {
          const cap = transcription[i];
          if (cap.end < t) continue;
          if (cap.start > upper) break;
          const text = (cap.text || "").trim();
          if (!text) continue;
          const dur = cap.end - cap.start;
          if (dur <= 0) continue;
          const tPerChar = dur / text.length;
          const re = /[.!?…]+/g;
          let m;
          while ((m = re.exec(text)) !== null) {
            const pos = m.index + m[0].length;
            const time = cap.start + pos * tPerChar;
            if (time >= t && time <= upper) {
              // Verifica se é "verdadeiro fim" — próximo char é maiúsculo ou cap acabou
              const nextChars = text.slice(pos).trim();
              const nextStartsCapital = nextChars.length === 0 || startsCapital(nextChars);
              sentEnds.push({ time, nextCapital: nextStartsCapital, capIdx: i });
            }
          }
        }
        if (sentEnds.length === 0) {
          for (const cap of transcription) {
            if (cap.start < t && cap.end >= t - 0.5) return cap.end;
          }
          return t;
        }
        // Prefere o PRIMEIRO `.!?` ≥ t cujo próximo char é MAIÚSCULA (frase realmente
        // terminada — próxima começa nova ideia). Se nenhum, primeiro `.!?` qualquer.
        const withCapital = sentEnds.find(s => s.nextCapital);
        const chosen = withCapital || sentEnds[0];
        return chosen.time + 0.2; // +0.2s pra captura a respiração após o ponto
      };

      // 3) Pra cada hook ≥ threshold, construir clip candidato
      const HOOK_THRESHOLD = 8;
      const MIN_DUR = 20, IDEAL_MIN = 30, IDEAL_MAX = 120, MAX_DUR = 180;
      const candidates = [];

      for (let i = 0; i < sentences.length; i++) {
        const hook = sentences[i];
        const hs = hookScore(hook);
        if (hs < HOOK_THRESHOLD) continue;

        // Contexto antes: começa ~1s antes se a frase anterior fluir naturalmente
        let clipStart = hook.startT;
        if (i > 0 && hook.startT - sentences[i - 1].endT < 0.6) {
          clipStart = Math.max(hook.startT - 1.5, sentences[i - 1].startT);
        }
        clipStart = Math.max(0, clipStart);
        // Snap para o INÍCIO da caption que contém esse tempo — vídeo + legenda alinhados
        clipStart = snapToCapStart(clipStart);

        // Achar melhor END: passar pela lista de frases, pegar o endT com maior score local
        let best = null;
        for (let j = i + 1; j < sentences.length; j++) {
          const s2 = sentences[j];
          const dur = s2.endT - clipStart;
          if (dur < MIN_DUR) continue;
          if (dur > MAX_DUR) break;
          if (s2.noPunct) continue;

          let localScore = 0;
          const s2t = s2.text.toLowerCase();
          if (PAYOFF_RE.test(s2t)) localScore += 5;
          if (s2.type === "statement" && dur >= IDEAL_MIN && dur <= IDEAL_MAX) localScore += 3;
          if (s2.type === "exclaim") localScore += 2;
          // Sentenças finais (sem conectivo de continuação) ganham bonus
          if (!/^(e |mas |porque |então |aí )/i.test(s2.text)) localScore += 1;
          // Preferência por duração ideal
          if (dur >= IDEAL_MIN && dur <= IDEAL_MAX) localScore += 2;

          if (!best || localScore > best.localScore) {
            best = { endT: s2.endT, localScore, payoffText: s2.text };
          }
        }
        if (!best) continue;

        // Snap END: estende até próxima caption terminando em .!? (até maxT+5s)
        const maxT = clipStart + MAX_DUR;
        const clipEnd = snapToCapEnd(best.endT, maxT);
        const dur = clipEnd - clipStart;

        // 4) Score total do clip
        const clipSents = sentences.filter(s => s.startT >= clipStart && s.endT <= clipEnd + 0.5);
        const clipText = clipSents.map(s => s.text).join(" ").toLowerCase();
        let score = hs + best.localScore;
        let engCount = 0;
        for (const w of ENG_WORDS) if (clipText.includes(w)) engCount++;
        score += Math.min(engCount, 8);
        const qCount = clipSents.filter(s => s.type === "question").length;
        score += Math.min(qCount * 2, 6);
        const statCount = (clipText.match(/\d+\s*%/g) || []).length;
        score += statCount * 3;
        if (dur >= IDEAL_MIN && dur <= IDEAL_MAX) score += 5;
        else if (dur < 20) score -= 10;
        else if (dur > 180) score -= 5;
        const overlapTitles = titles.filter(t => t.endSec > clipStart && t.startSec < clipEnd);
        score += Math.min(overlapTitles.length * 2, 8);

        const heroT = overlapTitles.find(t => t.style === "hero" || t.style === "flash");
        const topic = heroT?.text || hook.text.replace(/[.?!…]+$/, "").slice(0, 55);

        candidates.push({
          startSec: clipStart,
          endSec: clipEnd,
          duration: dur,
          score,
          topic,
          hookText: hook.text,
          payoffText: best.payoffText,
          titleCount: overlapTitles.length,
          titles: overlapTitles.map(t => t.text),
          titleObjects: overlapTitles,
        });
      }

      // 5) Ordenar por score, remover overlaps, pegar top 10
      candidates.sort((a, b) => b.score - a.score);
      const selected = [];
      for (const c of candidates) {
        const overlaps = selected.some(s =>
          c.startSec < s.endSec - 1 && c.endSec > s.startSec + 1
        );
        if (!overlaps) selected.push(c);
        if (selected.length >= 10) break;
      }

      // 6) Auto-assign styles baseado em conteúdo
      const styles = ["talkingHead", "splitScreen", "zoomPunchIn", "squareBlur", "letterbox", "textHeavy", "progressHook", "floatingHead", "memeCommentary"];
      let styleIdx = 0;
      for (const clip of selected) {
        if (clip.titleCount >= 4) clip.style = "textHeavy";
        else if (clip.titles.some(t => STAT_RE.test(t))) clip.style = "splitScreen";
        else if (clip.score >= 30) clip.style = "zoomPunchIn";
        else { clip.style = styles[styleIdx % styles.length]; styleIdx++; }
      }
      // Ordenar por tempo pra exibir
      selected.sort((a, b) => a.startSec - b.startSec);

      res.writeHead(200, {"Content-Type": "application/json"});
      res.end(JSON.stringify({
        ok: true,
        totalCandidates: candidates.length,
        clips: selected.map((c, i) => {
          const clipBrolls = brolls.filter(b => b.endSec > c.startSec && b.startSec < c.endSec);
          return {
            index: i + 1,
            startSec: Math.round(c.startSec * 10) / 10,
            endSec: Math.round(c.endSec * 10) / 10,
            duration: Math.round(c.duration * 10) / 10,
            topic: c.topic,
            score: c.score,
            style: c.style,
            hookText: c.hookText,
            payoffText: c.payoffText,
            titleCount: c.titleCount,
            titles: c.titles,
            titleObjects: c.titleObjects,
            brollObjects: clipBrolls,
          };
        })
      }));
    } catch(e) {
      res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // ── FORGE RENDER (ffmpeg + NVENC GPU end-to-end) ──
  // Pipeline alternativo ao motor de navegador direto: usa overlays alpha do motor de navegador (cached)
  // + ffmpeg externo NVENC pra composite. Esperado ~4-5min cold, ~1min cache hit.
  if (url.pathname === "/api/render-forge" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const opts = body ? JSON.parse(body) : {};
        let outName = opts.output || `forge_${Date.now()}.mp4`;
        // Pasta de destino escolhida no modal (padrao de editor). Sem ela,
        // continua caindo em output/ como antes.
        const outDir = (opts.outputDir || "").toString().trim();
        if (outDir) {
          try {
            if (fs.existsSync(outDir) && fs.statSync(outDir).isDirectory()) {
              outName = path.join(outDir, path.basename(outName));
            } else {
              console.warn(`[Klipe] pasta de saida inexistente: ${outDir} — usando output/`);
            }
          } catch (e) {}
        }
        const noCache = opts.noCache === true;
        const audioFromSource = opts.audioFromSource === true;
        const bitrate = opts.bitrate || "12M";
        const codec = opts.codec || "h264"; // h264 | h265 | av1
        // showCaptions/showTitles default true; user pode desligar pelo modal
        const showCaptions = opts.showCaptions !== false;
        const showTitles = opts.showTitles !== false;
        const perTitle = opts.perTitle === true;
        const testDuration = opts.testDuration; // se setado, renderiza so primeiros N segundos

        const condaPython = pythonExe();
        // O codec do modal manda; onde encodar vem das Configuracoes, porque
        // e propriedade da MAQUINA e nao desta renderizacao.
        const encoder = { auto: "auto", sim: "gpu", nao: "cpu" }[lerAjustes().gpu] || "auto";
        const args = ["forge_render.py", "--out", outName, "--bitrate", bitrate, "--codec", codec,
                      "--encoder", encoder, "--config", _configPath];
        if (noCache) args.push("--no-cache");
        if (audioFromSource) args.push("--audio-from-source");
        if (!showCaptions) args.push("--no-captions");
        if (!showTitles) args.push("--no-titles");
        if (perTitle) args.push("--per-title");
        if (testDuration) args.push("--test-duration", String(testDuration));

        console.log(`[ForgeRender] Spawning: ${condaPython} ${args.join(" ")}`);

        const renderKey = chaveForge(_projeto);
        const forgeJob = {
          status: "running",
          startedAt: Date.now(),
          outputName: outName,
          outputPath: null,
          project: _projeto || null,
          logTail: [],
          fileSize: null,
          error: null,
        };
        FORGE_RENDERS.set(renderKey, forgeJob);

        const child = spawn(condaPython, args, {
          cwd: __dirname,
          stdio: ["ignore", "pipe", "pipe"],
          shell: false,
        });
        forgeJob.childProcess = child;

        const captureLine = (line) => {
          const s = line.trim();
          if (!s) return;
          console.log("[ForgeRender]", s);
          forgeJob.logTail.push(s);
          if (forgeJob.logTail.length > 50) forgeJob.logTail.shift();
        };
        let stdoutBuf = "";
        let stderrBuf = "";
        child.stdout.on("data", d => {
          stdoutBuf += d.toString();
          const lines = stdoutBuf.split("\n");
          stdoutBuf = lines.pop();
          lines.forEach(captureLine);
        });
        child.stderr.on("data", d => {
          stderrBuf += d.toString();
          const lines = stderrBuf.split("\n");
          stderrBuf = lines.pop();
          lines.forEach(captureLine);
        });
        child.on("close", code => {
          if (stdoutBuf) captureLine(stdoutBuf);
          if (stderrBuf) captureLine(stderrBuf);
          const elapsed = Math.round((Date.now() - forgeJob.startedAt) / 1000);
          if (code === 0) {
            // Replica a pasta padrao do forge_render.py: projeto/renders para
            // configs de projeto, output/ apenas para o config global.
            const finalPath = path.isAbsolute(outName)
              ? outName
              : (_projeto
                  ? path.join(path.dirname(_configPath), "renders", path.basename(outName))
                  : path.join(__dirname, "output", path.basename(outName)));
            const sz = fs.existsSync(finalPath) ? fs.statSync(finalPath).size : 0;
            forgeJob.status = "done";
            forgeJob.outputPath = finalPath;
            forgeJob.fileSize = sz;
            forgeJob.elapsed = elapsed;
            console.log(`[ForgeRender] DONE em ${elapsed}s | ${(sz/1024/1024).toFixed(1)} MB`);
          } else {
            forgeJob.status = "error";
            forgeJob.error = `exit code ${code}`;
            forgeJob.elapsed = elapsed;
            console.error(`[ForgeRender] FAIL exit=${code} em ${elapsed}s`);
          }
        });

        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({
          ok: true,
          message: "ForgeRender started",
          outputName: outName,
          options: { noCache, audioFromSource, bitrate },
        }));
      } catch (e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // ── FORGE RENDER STATUS ──
  if (url.pathname === "/api/render-forge/status" && req.method === "GET") {
    const f = FORGE_RENDERS.get(chaveForge(_projeto)) || { status: "idle" };
    const elapsed = f.status !== "running" && Number.isFinite(f.elapsed)
      ? f.elapsed
      : (f.startedAt ? Math.round((Date.now() - f.startedAt) / 1000) : 0);
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: f.status || "idle",
      outputName: f.outputName || null,
      elapsed: `${elapsed}s`,
      fileSize: f.fileSize ? `${(f.fileSize/1024/1024).toFixed(1)} MB` : null,
      logTail: (f.logTail || []).slice(-15),
      error: f.error || null,
    }));
    return;
  }

  // Download sempre aponta para o ultimo render DESTE projeto. Isso tambem
  // funciona quando a pasta escolhida fica fora de public/ e nao tem URL.
  if (url.pathname === "/api/render-forge/file" && req.method === "GET") {
    const f = FORGE_RENDERS.get(chaveForge(_projeto));
    const alvo = f && f.outputPath ? path.resolve(f.outputPath) : null;
    if (!alvo || !fs.existsSync(alvo) || !fs.statSync(alvo).isFile()) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "render deste projeto nao encontrado" }));
      return;
    }
    const nome = path.basename(alvo);
    res.writeHead(200, {
      "Content-Type": "video/mp4",
      "Content-Length": fs.statSync(alvo).size,
      "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(nome)}`,
    });
    fs.createReadStream(alvo).pipe(res);
    return;
  }

  // ── ESCOLHER PASTA DE DESTINO (dialogo nativo do Windows) ──
  // O navegador nao sabe pedir uma pasta do sistema — so arquivo pra upload.
  // Entao o dialogo abre no servidor, que e a mesma maquina. Loopback so, pelo
  // mesmo motivo do /api/open-folder.
  if (url.pathname === "/api/pick-folder" && req.method === "POST") {
    const remoto = req.socket.remoteAddress;
    const ehLocal = remoto === "127.0.0.1" || remoto === "::1" || remoto === "::ffff:127.0.0.1";
    if (!ehLocal) {
      res.writeHead(403, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: false, error: "so no PC que roda o Klipe" }));
      return;
    }
    // O dialogo precisa de uma janela DONA, senao o Windows o abre atras do
    // Chrome: ele fica esperando resposta, o usuario nao ve nada, e parece que
    // o botao nao funciona. Foi exatamente o que aconteceu — e como o `spawn`
    // fica pendurado esperando, o render nunca comeca.
    //
    // A dona e um formulario invisivel e TopMost; passando ele pro ShowDialog,
    // o dialogo herda a frente.
    const ps = [
      "Add-Type -AssemblyName System.Windows.Forms",
      "$dona = New-Object System.Windows.Forms.Form",
      "$dona.Width = 1",
      "$dona.Height = 1",
      "$dona.StartPosition = 'CenterScreen'",
      "$dona.ShowInTaskbar = $false",
      // Opacity 0 faz o Windows recusar foco em algumas configuracoes. Quase
      // invisivel ainda serve como dona real do dialogo e aceita foreground.
      "$dona.Opacity = 0.01",
      "$dona.Show()",
      "$dona.TopMost = $true",
      "$dona.BringToFront()",
      "$dona.Activate()",
      "$d = New-Object System.Windows.Forms.FolderBrowserDialog",
      "$d.Description = 'Onde salvar o video'",
      "$d.ShowNewFolderButton = $true",
      "if ($d.ShowDialog($dona) -eq 'OK') { Write-Output $d.SelectedPath }",
      "$dona.Close()",
    ].join("; ");
    const p = require("child_process").spawn(
      "powershell.exe", ["-NoProfile", "-STA", "-Command", ps],
      { windowsHide: true });
    let saida = "";
    p.stdout.on("data", (c) => { saida += c; });
    p.on("close", () => {
      const pasta = saida.trim();
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: !!pasta, path: pasta || null }));
    });
    return;
  }

  // ── ABRIR A PASTA DO ARQUIVO NO EXPLORER ──
  // Abre o Explorer com o arquivo JA SELECIONADO (`/select,`), que e o que se
  // espera de "mostrar na pasta".
  //
  // Duas travas, porque isto executa programa na maquina do servidor:
  //  - so loopback: de outro aparelho da rede nao faz sentido nenhum abrir
  //    uma janela AQUI, e abriria porta pra quem estiver na mesma rede;
  //  - so dentro de output/: o caminho e resolvido e conferido, entao um
  //    `../..` no nome nao leva pra fora.
  if (url.pathname === "/api/open-folder" && req.method === "POST") {
    const remoto = req.socket.remoteAddress;
    const ehLocal = remoto === "127.0.0.1" || remoto === "::1" || remoto === "::ffff:127.0.0.1";
    if (!ehLocal) {
      res.writeHead(403, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: false, error: "so funciona no PC que roda o Klipe" }));
      return;
    }
    let corpo = "";
    req.on("data", (c) => { corpo += c; });
    req.on("end", () => {
      let nome = "", tipo = "output", slug = "";
      try {
        const j = JSON.parse(corpo || "{}");
        nome = (j.name || "").toString();
        tipo = (j.kind || "output").toString();
        slug = (j.project || "").toString();
      } catch (e) {}

      // `kind: "project"` abre onde o PROJETO esta salvo, com o
      // edit_config.json ja selecionado. O caminho e montado AQUI a partir do
      // slug, nunca recebido pronto do cliente — assim continua impossivel
      // pedir uma pasta arbitraria.
      if (tipo === "project") {
        const slugSafe = slug.replace(/[<>:"/\\|?*]/g, "_");
        const doProjeto = slugSafe
          ? path.join(__dirname, "public", "projects", slugSafe, "edit_config.json")
          : null;
        const alvoProj = (doProjeto && fs.existsSync(doProjeto)) ? doProjeto : CONFIG_PATH;
        try {
          require("child_process").spawn("explorer.exe", ["/select,", alvoProj], {
            detached: true, stdio: "ignore",
          }).unref();
        } catch (e) {}
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, path: alvoProj }));
        return;
      }

      // O render passou a sair DENTRO do projeto (public/projects/<slug>/
      // renders), e este botao continuava abrindo o `output/` global — que
      // agora esta vazio. O slug e derivado AQUI, do videoSrc do config, pela
      // mesma regra do forge_render.py: o cliente nunca manda pasta pronta.
      let raizRenders = null;
      try {
        const cfg = readConfig();
        const m = String(cfg.videoSrc || "").replace(/\\/g, "/").match(/projects\/([^/]+)\//);
        const projetoAtual = slugSeguro(_projeto || slug || (m && m[1]));
        if (projetoAtual) {
          const p = path.resolve(__dirname, "public", "projects", projetoAtual, "renders");
          if (fs.existsSync(p)) raizRenders = p;
        }
      } catch (e) {}

      const raizOut = path.resolve(__dirname, "output");
      // pasta preferida quando nao vem nome: a do projeto, se existir
      const raizPadrao = raizRenders || raizOut;
      // o arquivo pode estar em qualquer uma das duas — tenta a do projeto
      // primeiro, porque e onde os renders novos caem
      const candidatos = (raizRenders ? [raizRenders, raizOut] : [raizOut])
        .map((raiz) => ({ raiz, alvo: path.resolve(raiz, nome) }))
        .filter(({ raiz, alvo }) =>
          (alvo === raiz || alvo.startsWith(raiz + path.sep)) && fs.existsSync(alvo));

      // ultimo recurso: o proprio servidor sabe onde gravou o ultimo render
      // (pasta escolhida pelo usuario no modal, fora das duas raizes)
      let doUltimoRender = null;
      try {
        const f = FORGE_RENDERS.get(chaveForge(_projeto || slug));
        if (f && f.outputName && nome && path.basename(String(f.outputName)) === path.basename(nome)) {
          const abs = f.outputPath || (path.isAbsolute(f.outputName)
            ? f.outputName : path.resolve(raizPadrao, f.outputName));
          if (fs.existsSync(abs)) doUltimoRender = abs;
        }
      } catch (e) {}

      const alvo = candidatos.length ? candidatos[0].alvo
                 : (doUltimoRender || (nome ? null : raizPadrao));
      const ehAPasta = !!alvo && !nome;
      if (!alvo || !fs.existsSync(alvo)) {
        res.writeHead(404, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: false, error: "arquivo nao encontrado" }));
        return;
      }
      // `explorer` devolve codigo de saida != 0 mesmo quando abre certo —
      // nao da pra usar o returncode como sinal de erro aqui.
      try {
        const args = ehAPasta ? [alvo] : ["/select,", alvo];
        require("child_process").spawn("explorer.exe", args, {
          detached: true, stdio: "ignore",
        }).unref();
      } catch (e) {}
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true, path: alvo }));
    });
    return;
  }

  // ── FORGE RENDER CANCEL ──
  if (url.pathname === "/api/render-forge/cancel" && req.method === "POST") {
    const f = FORGE_RENDERS.get(chaveForge(_projeto));
    if (f && f.childProcess && f.status === "running") {
      try { f.childProcess.kill(); } catch (e) {}
      f.status = "cancelled";
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true, message: "Cancelled" }));
    } else {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: false, message: "No active forge render" }));
    }
    return;
  }

  // ── AUTO-EDIT: Silence + Filler Detection ──
  // Le transcription.json do projeto + detecta silencios/fillers/false starts.
  // Retorna cuts pra UI mostrar pro user aprovar.
  if (url.pathname === "/api/auto-edit/silence-detect" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const opts = body ? JSON.parse(body) : {};
        // Detecta projeto pelo cfg ativo (pega de edit_config.videoSrc)
        const cfg = readConfig();
        let project = opts.project;
        if (!project && cfg.videoSrc) {
          // videoSrc tipo "projects/barreiras-academico/video_preview.mp4"
          const m = cfg.videoSrc.match(/^projects\/([^\/]+)\//);
          if (m) project = m[1];
        }
        if (!project) {
          res.writeHead(400);
          res.end(JSON.stringify({ error: "Could not detect project name from edit_config.videoSrc" }));
          return;
        }
        const silenceMin = opts.silenceMin || 0.5;
        const fillerMaxDur = opts.fillerMaxDur || 2.0;

        const condaPython = pythonExe();
        const args = ["silence_detect.py", project,
                      "--silence-min", String(silenceMin),
                      "--filler-max-dur", String(fillerMaxDur)];

        console.log(`[AutoEdit] Detecting silences for ${project} (silence>=${silenceMin}s)`);

        let stdout = "";
        let stderr = "";
        const child = spawn(condaPython, args, {
          cwd: __dirname,
          stdio: ["ignore", "pipe", "pipe"],
          shell: false,
        });
        child.stdout.on("data", d => { stdout += d.toString(); });
        child.stderr.on("data", d => { stderr += d.toString(); });
        child.on("close", code => {
          if (code !== 0) {
            console.error(`[AutoEdit] silence_detect.py FAIL (exit ${code}): ${stderr}`);
            res.writeHead(500);
            res.end(JSON.stringify({ error: `silence_detect failed: ${stderr.slice(-500)}` }));
            return;
          }
          // Extrai JSON da output (depois do separador "--- JSON output ---")
          const jsonMarker = stdout.indexOf("--- JSON output ---");
          let jsonStr = jsonMarker >= 0 ? stdout.slice(jsonMarker + "--- JSON output ---".length).trim() : stdout.trim();
          // Pega ultima linha que comeca com {
          const lines = jsonStr.split("\n").reverse();
          for (const line of lines) {
            const t = line.trim();
            if (t.startsWith("{")) { jsonStr = t; break; }
          }
          try {
            const result = JSON.parse(jsonStr);
            res.writeHead(200, { "Content-Type": "application/json" });
            res.end(JSON.stringify(result));
          } catch (e) {
            res.writeHead(500);
            res.end(JSON.stringify({ error: `Could not parse output: ${e.message}`, raw: stdout.slice(-500) }));
          }
        });
      } catch (e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // ── JUNTAR CORTES (Consolidate Cuts — estilo CapCut "remove gaps") ──
  // Aplica cuts no source de fato (ffmpeg+NVENC) + reset config pra 1 video clip
  if (url.pathname === "/api/consolidate-cuts" && req.method === "POST") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      try {
        const cfg = readConfig();
        let project = null;
        if (cfg.videoSrc) {
          const m = cfg.videoSrc.match(/^projects\/([^\/]+)\//);
          if (m) project = m[1];
        }
        if (!project) {
          res.writeHead(400);
          res.end(JSON.stringify({ error: "Could not detect project name" }));
          return;
        }
        const condaPython = pythonExe();
        const args = ["consolidate_cuts.py", project];
        console.log(`[Consolidate] Spawning: ${condaPython} ${args.join(" ")}`);

        let stdout = "", stderr = "";
        const child = spawn(condaPython, args, {
          cwd: __dirname,
          stdio: ["ignore", "pipe", "pipe"],
          shell: false,
        });
        child.stdout.on("data", d => { stdout += d.toString(); console.log("[Consolidate]", d.toString().trim()); });
        child.stderr.on("data", d => { stderr += d.toString(); });
        child.on("close", code => {
          if (code !== 0) {
            console.error(`[Consolidate] FAIL exit=${code}: ${stderr}`);
            res.writeHead(500); res.end(JSON.stringify({ error: stderr.slice(-500) || "Falhou" }));
            return;
          }
          // Tenta parsear JSON do output
          let result = { ok: true };
          for (const line of stdout.split("\n").reverse()) {
            const t = line.trim();
            if (t.endsWith("}")) {
              try { result = JSON.parse(t); break; } catch (e) {}
            }
          }
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify(result));
        });
      } catch (e) {
        res.writeHead(500); res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // ── BATCH RENDER SHORTS ──
  if (url.pathname === "/api/render-shorts-batch" && req.method === "POST") {
    // Em fila, nao em paralelo: cada short ja usa a GPU inteira no encode, e
    // dois ao mesmo tempo so disputam o mesmo recurso e terminam depois.
    let corpo = "";
    req.on("data", c => corpo += c);
    req.on("end", async () => {
      try {
        const o = JSON.parse(corpo || "{}");
        const clipes = Array.isArray(o.clips) ? o.clips : [];
        if (!clipes.length) {
          res.writeHead(400, {"Content-Type":"application/json"});
          return res.end(JSON.stringify({ ok: false, error: "nenhum clipe" }));
        }
        global._shortsRender = { status: "rendering", total: clipes.length, completed: 0,
                                 startedAt: Date.now(), logTail: [], error: null };
        res.writeHead(200, {"Content-Type":"application/json"});
        res.end(JSON.stringify({ ok: true, total: clipes.length }));

        for (let i = 0; i < clipes.length; i++) {
          if (global._shortsRender.cancelado) break;
          const c = clipes[i];
          const nome = `short_${String(i + 1).padStart(2, "0")}_${Date.now()}.mp4`;
          const args = ["montar_short.py", _configPath,
                        "--inicio", String(Number(c.startSec) || 0),
                        "--fim", String(Number(c.endSec) || 0),
                        "--saida", nome,
                        "--face-x", String(Number(c.faceX) || 50),
                        "--face-y", String(Number(c.faceY) || 35),
                        "--crf", String(Number(o.crf) || 18)];
          if (c.topic) args.push("--gancho", String(c.topic));
          if (c.accentColor) args.push("--cor", String(c.accentColor));
          global._shortsRender.logTail.push(`short ${i + 1}/${clipes.length}: ${nome}`);
          await new Promise(ok => {
            const ch = spawn(pythonExe(), args, { cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] });
            global._shortsRender.childProcess = ch;
            const anota = d => {
              const s = d.toString().trim();
              if (s) { console.log("[Short]", s.slice(0, 120));
                       global._shortsRender.logTail.push(s.slice(0, 200));
                       if (global._shortsRender.logTail.length > 40) global._shortsRender.logTail.shift(); }
            };
            ch.stdout.on("data", anota); ch.stderr.on("data", anota);
            ch.on("close", code => { if (code === 0) global._shortsRender.completed++; ok(); });
          });
        }
        global._shortsRender.status = "done";
        global._shortsRender.elapsed = Math.round((Date.now() - global._shortsRender.startedAt) / 1000);
      } catch (e) {
        if (global._shortsRender) { global._shortsRender.status = "error"; global._shortsRender.error = e.message; }
      }
    });
    return;
  }

  // ── RENDER SHORTS ──
  if (url.pathname === "/api/render-short" && req.method === "POST") {
    // Um short e um render do Klipe de um PEDACO, noutro enquadramento — nao
    // uma composicao a parte. Por isso aqui so monta o pedido; quem recorta,
    // deriva o projeto e chama o forge_render e o montar_short.py.
    let corpo = "";
    req.on("data", c => corpo += c);
    req.on("end", () => {
      try {
        const o = JSON.parse(corpo || "{}");
        const ini = Number(o.startSec) || 0;
        const fim = Number(o.endSec) || 0;
        if (fim <= ini) {
          res.writeHead(400, {"Content-Type":"application/json"});
          return res.end(JSON.stringify({ ok: false, error: "fim tem que ser maior que inicio" }));
        }
        const nome = (o.output || `short_${Date.now()}.mp4`).replace(/[^\w.-]/g, "");
        const args = ["montar_short.py", _configPath,
                      "--inicio", String(ini), "--fim", String(fim), "--saida", nome,
                      "--face-x", String(Number(o.faceX) || 50),
                      "--face-y", String(Number(o.faceY) || 35),
                      "--crf", String(Number(o.crf) || 18)];
        if (o.hookText) args.push("--gancho", String(o.hookText));
        if (o.topText) args.push("--topo", String(o.topText));
        if (o.accentColor) args.push("--cor", String(o.accentColor));

        global._shortsRender = { status: "rendering", outputName: nome, total: 1, completed: 0,
                                 startedAt: Date.now(), logTail: [], error: null };
        const child = spawn(pythonExe(), args, { cwd: __dirname, stdio: ["ignore", "pipe", "pipe"] });
        global._shortsRender.childProcess = child;
        const anota = d => {
          const s = d.toString().trim();
          if (!s) return;
          console.log("[Short]", s.slice(0, 120));
          global._shortsRender.logTail.push(s.slice(0, 200));
          if (global._shortsRender.logTail.length > 40) global._shortsRender.logTail.shift();
        };
        child.stdout.on("data", anota);
        child.stderr.on("data", anota);
        child.on("close", code => {
          global._shortsRender.status = code === 0 ? "done" : "error";
          global._shortsRender.completed = code === 0 ? 1 : 0;
          if (code !== 0) global._shortsRender.error = `saiu ${code}`;
          global._shortsRender.elapsed = Math.round((Date.now() - global._shortsRender.startedAt) / 1000);
        });
        res.writeHead(200, {"Content-Type":"application/json"});
        res.end(JSON.stringify({ ok: true, nome }));
      } catch (e) {
        res.writeHead(500, {"Content-Type":"application/json"});
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // Shorts render status (works for both single and batch)
  if (url.pathname === "/api/render-short/status" && req.method === "GET") {
    const r = global._shortsRender;
    if (!r) {
      res.writeHead(200, {"Content-Type": "application/json"});
      res.end(JSON.stringify({ status: "idle" }));
      return;
    }
    const elapsed = ((Date.now() - r.startedAt) / 1000).toFixed(0);
    res.writeHead(200, {"Content-Type": "application/json"});
    res.end(JSON.stringify({
      status: r.status,
      elapsed: elapsed + "s",
      total: r.total || 1,
      completed: r.completed || 0,
      current: r.current || 0,
      currentTopic: r.currentTopic || "",
      outputName: r.outputName,
      fileSize: r.fileSize,
      error: r.error,
      results: r.results || [],
    }));
    return;
  }

  // Cancel shorts render
  if (url.pathname === "/api/render-short/cancel" && req.method === "POST") {
    if (global._shortsRender && global._shortsRender.status === "rendering") {
      global._shortsRender.cancelled = true;
      global._shortsRender.status = "cancelled";
      if (global._shortsRender.childProcess) {
        try { global._shortsRender.childProcess.kill("SIGTERM"); } catch(e) {}
      }
      res.writeHead(200, {"Content-Type": "application/json"});
      res.end(JSON.stringify({ ok: true, message: "Shorts render cancelled" }));
    } else {
      res.writeHead(200, {"Content-Type": "application/json"});
      res.end(JSON.stringify({ ok: true, message: "No shorts render running" }));
    }
    return;
  }

  // Serve editor HTML
  // /p/<slug> — a URL de um projeto. Serve o mesmo editor; quem diz de qual
  // projeto se trata e o caminho, e o cliente o repassa em cada requisicao.
  const rotaProjeto = /^\/p\/([a-zA-Z0-9._-]+)\/?$/.exec(url.pathname);

  if (url.pathname === "/" || url.pathname === "/editor" || rotaProjeto) {
    // ANTES: `?project=<slug>` COPIAVA o config do projeto por cima do global.
    // Era isso que impedia duas abas — abrir a segunda trocava o que a
    // primeira estava editando. Agora nada e copiado: o slug so viaja com as
    // requisicoes e cada aba fala com o arquivo dela.
    if (_projeto) console.log(`[Klipe] servindo editor do projeto: ${_projeto}`);
    const editorPath = path.join(__dirname, "editor.html");
    if (fs.existsSync(editorPath)) {
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8",
                          "Cache-Control": "no-cache, must-revalidate"});
      res.end(fs.readFileSync(editorPath, "utf-8"));
    } else {
      res.writeHead(404); res.end("editor.html not found");
    }
    return;
  }

  // Serve shorts player HTML
  // As rotas /shorts-player e /shorts-player-bundle.js serviam ao navegador
  // um bundle com O motor de navegador dentro. Sairam: enquanto o arquivo viajasse
  // junto, o Klipe distribuiria motor de navegador para o cliente.

  // Serve shorts player bundle

  // Serve player HTML (o player do motor antigo embed)

  // Serve player bundle JS

  // Serve static files from public/ (videos, fonts, json, images)
  // WITH range request support for video seeking (required by o player do motor antigo)
  // decodeURIComponent required so UTF-8 filenames (e.g. "SoundConteúdo.wav") resolve on disk
  let decodedPath;
  try { decodedPath = decodeURIComponent(url.pathname); }
  catch { decodedPath = url.pathname; }
  const filePath = path.join(PUBLIC_DIR, decodedPath);

  // O decodeURIComponent acima e necessario para nome de arquivo em UTF-8,
  // mas abria travessia de diretorio: o parser de URL normaliza ".." de
  // verdade, e NAO decodifica %2f. Entao /a%2f..%2f..%2fklipe_settings.json
  // chegava aqui intacto, virava /a/../../klipe_settings.json no decode, e o
  // path.join saia do public/. Testado contra o servidor: devolvia 200 com as
  // chaves de API. Por isso a checagem vem DEPOIS do join, sobre o caminho ja
  // resolvido - conferir a string da URL antes nao pega o caso codificado.
  const _raizPublica = path.resolve(PUBLIC_DIR) + path.sep;
  if (!path.resolve(filePath).startsWith(_raizPublica)) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    return res.end("Not found");
  }
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes = {
      ".mp4":"video/mp4", ".webm":"video/webm", ".json":"application/json",
      ".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".png":"image/png", ".gif":"image/gif",
      ".ttf":"font/ttf", ".otf":"font/otf", ".woff":"font/woff", ".woff2":"font/woff2",
      ".mp3":"audio/mpeg", ".wav":"audio/wav", ".ogg":"audio/ogg",
      ".css":"text/css", ".js":"application/javascript", ".svg":"image/svg+xml",
      // sem .html aqui, o fallback octet-stream faz o navegador BAIXAR a
      // pagina em vez de abrir
      ".html":"text/html; charset=utf-8", ".htm":"text/html; charset=utf-8",
      ".txt":"text/plain; charset=utf-8"
    };
    const contentType = mimeTypes[ext] || "application/octet-stream";
    const stat = fs.statSync(filePath);
    const fileSize = stat.size;

    // Handle Range requests (needed for video/audio seeking)
    const range = req.headers.range;
    if (range) {
      const intervalo = intervaloBytes(range, fileSize);
      if (!intervalo) {
        res.writeHead(416, { "Content-Range": `bytes */${fileSize}` });
        res.end();
        return;
      }
      const { start, end } = intervalo;
      const chunkSize = end - start + 1;
      res.writeHead(206, {
        "Content-Range": `bytes ${start}-${end}/${fileSize}`,
        "Accept-Ranges": "bytes",
        "Content-Length": chunkSize,
        "Content-Type": contentType,
        "Cache-Control": "no-cache, must-revalidate",
      });
      fs.createReadStream(filePath, { start, end }).pipe(res);
    } else {
      // Tudo em public/ pode mudar durante a edição, inclusive MP4s e imagens
      // substituídos no mesmo caminho. Revalidar evita misturar o config novo
      // com bytes antigos mantidos por uma hora pelo cache do navegador.
      res.writeHead(200, {
        "Content-Length": fileSize,
        "Content-Type": contentType,
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache, must-revalidate",
      });
      fs.createReadStream(filePath).pipe(res);
    }
    return;
  }

  res.writeHead(404); res.end("Not found");
}));

// Bootstrap: se nao ha usuarios, cria admin com senha via KLIPE_ADMIN_PASSWORD
// env ou uma random (imprime no console pra user copiar).
(function bootstrapAdmin() {
  if (auth.countUsers() > 0) return;
  let pw = process.env.KLIPE_ADMIN_PASSWORD;
  let generated = false;
  if (!pw) {
    pw = crypto.randomBytes(6).toString("hex");
    generated = true;
  }
  auth.createUser({ username: "admin", password: pw, role: "admin" });
  if (generated) {
    console.log("\n==============================================");
    console.log(" [Klipe] ADMIN criado na primeira execucao");
    console.log("   username: admin");
    console.log(`   senha:    ${pw}`);
    console.log(" (troca setando KLIPE_ADMIN_PASSWORD env)");
    console.log("==============================================\n");
  } else {
    console.log("[Klipe] admin criado a partir de KLIPE_ADMIN_PASSWORD");
  }
})();

// 127.0.0.1 e nao 0.0.0.0. Antes escutava em TODAS as interfaces e quem
// barrava a rede era o login; sem login, o bind e a unica trava que sobra.
// Rede de seguranca do PROCESSO. Sem isto, qualquer erro solto (um callback
// de fs, um stream que quebra) derrubava o Klipe inteiro - e pra quem esta
// usando isso aparece como "fechou sozinho", sem explicacao.
//
// Optamos por seguir vivo em vez de sair. O manual do Node recomenda
// reiniciar apos uncaughtException porque o estado pode estar corrompido;
// aqui o trabalho e por requisicao (roda ffmpeg, le e grava arquivo) e quase
// nao ha estado global mutavel para envenenar a proxima. Perder o editor
// aberto e uma perda maior que o risco.
process.on("uncaughtException", (e) => {
  console.error("[Klipe] erro nao tratado (o servidor continua):", e);
});
process.on("unhandledRejection", (e) => {
  console.error("[Klipe] promessa rejeitada sem tratamento (o servidor continua):", e);
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`\n  Klipe rodando em http://127.0.0.1:${PORT}  (sem login, so local)\n`);
});

// Segundo ouvinte no loopback IPv6. Medido: escutando so em 127.0.0.1, um
// pedido para `localhost` custava 2 SEGUNDOS a mais que o mesmo pedido para
// 127.0.0.1 — no Windows `localhost` resolve para ::1 primeiro, leva recusa,
// e so entao tenta IPv4. Dois segundos por conexao nova, em tudo.
//
// Continua so local: ::1 e o loopback, nao a rede. Bind em `::` abriria a
// maquina inteira, que e outra coisa.
const server6 = http.createServer(server.listeners("request")[0]);
server6.on("error", (e) => {
  // maquina sem IPv6, ou a porta ja tomada: o IPv4 sozinho da conta
  console.log(`  (sem ouvinte IPv6: ${e.code})`);
});
server6.listen(PORT, "::1", () => {
  console.log(`  tambem em http://[::1]:${PORT} - e o que faz 'localhost' responder na hora\n`);
});
