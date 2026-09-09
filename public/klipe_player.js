/**
 * klipe_player.js — o preview do Klipe sem motor de navegador.
 *
 * Compõe num canvas: vídeo principal (com zoom e correção de cor), b-rolls por
 * cima, e títulos desenhados pelo MotionCore.
 *
 * O ponto que justifica tudo: os títulos NÃO são redesenhados aqui. Eles vêm
 * assados do MotionCore — o mesmo código que desenha o arquivo final. Uma
 * segunda implementação dos estilos em JS foi o que produziu a fonte errada do
 * sensoryStorm e as scan lines faltando; este caminho torna essa classe de bug
 * impossível, porque não existe segunda implementação.
 *
 * Como o <video> não carrega alpha em H.264, cada título vem com a cor na
 * metade esquerda e o alpha em cinza na direita, e o shader remonta os dois.
 * Medido: 157 fps compondo, contra os 30 que precisamos.
 */

// O zoom expande a GEOMETRIA (`p` vai alem de +-1 e o excesso e cortado pelo
// viewport). O UV NAO pode sair de `p` direto: os dois cresceriam juntos e o
// resultado visivel seria identico ao sem zoom — foi exatamente esse o bug, o
// preview nunca mostrou zoom enquanto o render mostrava. Dividindo por
// `zoom` antes, o UV volta pra [0,1] e a imagem realmente amplia.
// `uv` sai do vértice ORIGINAL e só o `gl_Position` é transformado — é isso que
// permite mover e redimensionar uma camada sem arrastar a textura junto. Antes o
// uv vinha do mesmo `p` que ia pra tela, então qualquer deslocamento puxava a
// imagem com ele e posX/posY/scale de b-roll não tinham como funcionar.
// Com desloc=(0,0) e escala=1 o resultado é idêntico ao de antes.
// `rot` gira em ESPACO DE PIXEL (multiplica por dim antes, divide depois):
// girar direto no clip-space, que vai de -1 a 1 nos dois eixos de um quadro
// que nao e quadrado, esmagaria o titulo na diagonal. Positivo = horario,
// igual ao skia do motor (y desce la, y sobe aqui — dai o sinal trocado no
// seno). Com rot=0 a conta colapsa na antiga: pr == p*escala.
const VS_FONTE = `attribute vec2 p; varying vec2 uv;
  uniform float zoom; uniform vec2 desloc; uniform float escala;
  uniform float rot; uniform vec2 dim; uniform vec2 uvOff;
  void main(){
    vec2 t = p / zoom;
    uv = vec2((t.x+1.0)/2.0, 1.0-(t.y+1.0)/2.0) + uvOff;
    vec2 px = p * escala * dim;
    float c = cos(rot), s = sin(rot);
    vec2 pr = vec2(c*px.x + s*px.y, -s*px.x + c*px.y);
    gl_Position = vec4(pr / dim + desloc, 0, 1);
  }`;

// duas amostragens: opaco (vídeo normal) e lado-a-lado (título com alpha)
const FS_FONTE = `precision mediump float;
  varying vec2 uv;
  uniform sampler2D tex;
  uniform float temAlphaLateral;   // 1 = metade esquerda cor, direita alpha
  uniform float opacidade;
  // brilho, contraste, saturação, temperatura — todos 0 = neutro.
  // Reproduz o que o render faz: eq=brightness/contrast/saturation seguido de
  // colorbalance pra temperatura. Se as contas divergissem, o preview
  // mostraria uma cor e o arquivo sairia com outra.
  uniform vec4 cc;    // brightness, contrast, saturation, temperature
  uniform vec4 cc2;   // hue(graus), highlight, shadow, intensidade(0..1)

  // Rotacao de matiz em YIQ — a mesma conta do hue-rotate do CSS, que e o
  // que o card do filtro usa no painel. Se divergisse, o preset apareceria
  // de uma cor no thumbnail e de outra na tela.
  vec3 girarMatiz(vec3 c, float graus) {
    if (abs(graus) < 0.001) return c;
    float a = radians(graus), co = cos(a), si = sin(a);
    float y =  0.299*c.r + 0.587*c.g + 0.114*c.b;
    float i =  0.596*c.r - 0.274*c.g - 0.322*c.b;
    float q =  0.211*c.r - 0.523*c.g + 0.312*c.b;
    float i2 = i*co - q*si, q2 = i*si + q*co;
    return vec3(y + 0.956*i2 + 0.621*q2,
                y - 0.272*i2 - 0.647*q2,
                y - 1.106*i2 + 1.703*q2);
  }

  void main(){
    vec3 cor; float a;
    if (temAlphaLateral > 0.5) {
      cor = texture2D(tex, vec2(uv.x*0.5, uv.y)).rgb;
      a   = texture2D(tex, vec2(uv.x*0.5 + 0.5, uv.y)).r;
    } else {
      cor = texture2D(tex, uv).rgb;
      a   = 1.0;
    }
    float forca = cc2.w;
    if (forca > 0.001 && (cc != vec4(0.0) || cc2.xyz != vec3(0.0))) {
      vec3 org = cor;
      cor += cc.x / 100.0;                                   // brightness
      cor = (cor - 0.5) * (1.0 + cc.y / 100.0) + 0.5;        // contrast
      float luma = dot(cor, vec3(0.299, 0.587, 0.114));      // saturation
      cor = mix(vec3(luma), cor, 1.0 + cc.z / 100.0);
      cor.r += cc.w / 200.0;                                 // colorbalance rs
      cor.b -= cc.w / 200.0;                                 // colorbalance bs
      cor = girarMatiz(cor, cc2.x);                          // hue
      // highlight/shadow pesam pelas PONTAS da curva, nao pela imagem toda —
      // e o que permite levantar sombra sem estourar o branco
      float L = dot(clamp(cor, 0.0, 1.0), vec3(0.299, 0.587, 0.114));
      cor += (cc2.y / 100.0) * smoothstep(0.5, 1.0, L);         // highlight
      cor += (cc2.z / 100.0) * (1.0 - smoothstep(0.0, 0.5, L)); // shadow
      cor = clamp(cor, 0.0, 1.0);
      // filterIntensity do painel. Sem isso o slider nao fazia nada: o
      // preset entrava sempre inteiro ou nao entrava.
      cor = mix(org, cor, forca);
    }
    gl_FragColor = vec4(cor, a * opacidade);
  }`;

function _compilar(gl, tipo, src) {
  const s = gl.createShader(tipo);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    const erro = gl.getShaderInfoLog(s);
    gl.deleteShader(s);
    throw new Error('shader: ' + erro);
  }
  return s;
}

class KlipePlayer {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {object} config  o edit_config (videoSrc, width, height, fps, titles, brolls…)
   */
  constructor(canvas, config) {
    this.canvas = canvas;
    this.cfg = config || {};
    this.w = this.cfg.width || 1080;
    this.h = this.cfg.height || 1920;
    canvas.width = this.w;
    canvas.height = this.h;

    this.tocando = false;
    this.t = 0;                // segundo atual
    this._titulos = new Map(); // chave de bake -> {video, pronto, erro}
    this._tituloPronto = new Map(); // id do clip -> ultimo clipe PRONTO (anti-pisca)
    this._brolls = new Map();
    this._overlays = new Map(); // indice do pedaco -> legenda + barra
    this._velhos = new Map();   // pedaco anterior, desenhado enquanto o novo assa
    // O motor de navegador tocava SFX e musica DENTRO da composicao; este player nao
    // herdou isso e o preview ficou mudo fora da voz — "nenhuma sfx funciona".
    this._audios = new Map();   // id do clip -> <audio>
    this.aoAtualizar = null;   // callback(segundo) pra timeline acompanhar

    this._montarGL();
    this._montarVideo();
  }

  // ── WebGL ────────────────────────────────────────────────────────────
  _montarGL() {
    const gl = this.canvas.getContext('webgl', { premultipliedAlpha: false, alpha: false });
    if (!gl) throw new Error('sem WebGL neste navegador');
    this.gl = gl;

    const prog = gl.createProgram();
    gl.attachShader(prog, _compilar(gl, gl.VERTEX_SHADER, VS_FONTE));
    gl.attachShader(prog, _compilar(gl, gl.FRAGMENT_SHADER, FS_FONTE));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
    gl.useProgram(prog);
    this.prog = prog;
    this.uAlpha = gl.getUniformLocation(prog, 'temAlphaLateral');
    this.uOpac = gl.getUniformLocation(prog, 'opacidade');
    this.uCC = gl.getUniformLocation(prog, 'cc');
    this.uCC2 = gl.getUniformLocation(prog, 'cc2');
    this.uZoom = gl.getUniformLocation(prog, 'zoom');
    this.uDesloc = gl.getUniformLocation(prog, 'desloc');
    this.uEscala = gl.getUniformLocation(prog, 'escala');
    this.uRot = gl.getUniformLocation(prog, 'rot');
    this.uDim = gl.getUniformLocation(prog, 'dim');
    this.uUvOff = gl.getUniformLocation(prog, 'uvOff');
    const cc = this.cfg.colorCorrection || {};
    // só o vídeo entra na correção de cor: no render ela é aplicada na fonte,
    // ANTES dos overlays. Corrigir o título junto mudaria a cor que você
    // escolheu pra ele.
    // Guardado so como valor inicial. A correcao de verdade e recalculada a
    // cada frame em `_ccAtual()`: congelada aqui, trocar de filtro no painel
    // nao mudava nada — o player seguia com o que leu ao carregar, e era esse
    // o motivo de "os filtros nao funcionam".
    this._cc = [cc.brightness || 0, cc.contrast || 0,
                cc.saturation || 0, cc.temperature || 0];

    this.buf = gl.createBuffer();
    const loc = gl.getAttribLocation(prog, 'p');
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    this._locP = loc;

    // uma textura por camada: trocar o conteúdo de UMA textura entre camadas
    // no mesmo frame força sincronização da GPU e derruba o fps
    this._texturas = new Map();

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.viewport(0, 0, this.w, this.h);
  }

  _textura(chave) {
    let t = this._texturas.get(chave);
    if (!t) {
      const gl = this.gl;
      t = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      this._texturas.set(chave, t);
    }
    return t;
  }

  /** Correção de cor do frame atual, lida direto do cfg — nunca cacheada. */
  _ccAtual() {
    const cc = this.cfg.colorCorrection || {};
    // filtro escolhido no painel respeita a intensidade; ajuste manual (sem
    // `filterName`) vale sempre inteiro
    const f = cc.filterName
      ? (typeof cc.filterIntensity === 'number' ? cc.filterIntensity : 100) / 100
      : 1;
    return {
      a: [cc.brightness || 0, cc.contrast || 0, cc.saturation || 0, cc.temperature || 0],
      b: [cc.hue || 0, cc.highlight || 0, cc.shadow || 0, f],
    };
  }

  /** Desenha uma fonte de vídeo/imagem cobrindo o quadro inteiro. */
  _camada(chave, fonte, { alphaLateral = false, opacidade = 1, recorte = null,
                          corrigirCor = false,
                          posX = 0, posY = 0, escala = 1, rotacao = 0 } = {}) {
    if (!fonte || !fonte.videoWidth && !fonte.width) return;
    const gl = this.gl;
    gl.bindTexture(gl.TEXTURE_2D, this._textura(chave));
    try {
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, fonte);
    } catch { return; }   // frame ainda não decodificado

    // recorte = [x0,y0,x1,y1] em coordenadas -1..1, pro zoom
    const q = recorte || [-1, -1, 1, 1];
    // o fator sai da propria expansao do quadro; sem ele o UV acompanharia
    // a geometria e o zoom se anularia
    gl.uniform1f(this.uZoom, recorte ? Math.max(0.01, q[2]) : 1.0);
    // q[4] = deslocamento vertical de UV do zoom (originY). Sempre escrito,
    // mesmo zero: uniform e estado global e vazaria pra proxima camada.
    gl.uniform2f(this.uUvOff, 0, (recorte && recorte.length > 4) ? recorte[4] : 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
      q[0], q[1], q[2], q[1], q[0], q[3], q[2], q[3],
    ]), gl.DYNAMIC_DRAW);
    gl.vertexAttribPointer(this._locP, 2, gl.FLOAT, false, 0, 0);

    // Sempre escritos, mesmo neutros: uniform é estado global do programa, e
    // sem reescrever, o deslocamento de uma camada vazaria pra próxima.
    // posX/posY vêm em PIXELS da composição; posY interno é positivo pra BAIXO
    // (o painel já inverte), e o clip-space do WebGL é positivo pra cima.
    const cw = this.cfg.width || this.canvas.width || 1080;
    const chh = this.cfg.height || this.canvas.height || 1920;
    gl.uniform2f(this.uDesloc, (2 * posX) / cw, (-2 * posY) / chh);
    gl.uniform1f(this.uEscala, escala || 1);
    // graus -> radianos; dim nunca pode ser zero (divide no shader)
    gl.uniform1f(this.uRot, (rotacao || 0) * Math.PI / 180);
    gl.uniform2f(this.uDim, Math.max(1, cw / 2), Math.max(1, chh / 2));

    gl.uniform1f(this.uAlpha, alphaLateral ? 1 : 0);
    gl.uniform1f(this.uOpac, opacidade);
    const _c = this._ccAtual();
    gl.uniform4fv(this.uCC, corrigirCor ? _c.a : [0, 0, 0, 0]);
    gl.uniform4fv(this.uCC2, corrigirCor ? _c.b : [0, 0, 0, 0]);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  // ── mídia ────────────────────────────────────────────────────────────
  _novoVideo(src, { mudo = true } = {}) {
    const v = document.createElement('video');
    v.src = src;
    v.muted = mudo;
    v.playsInline = true;
    v.preload = 'auto';
    v.crossOrigin = 'anonymous';
    // b-roll, título e legenda nascem depois que a velocidade já foi mudada;
    // sem herdar aqui, eles andariam num ritmo e o vídeo em outro
    v.playbackRate = this._vel || 1;
    return v;
  }

  /**
   * "Acorda" o decoder de um <video> recém-criado que nunca tocou.
   *
   * `readyState`/`currentTime` relatam certo mesmo num vídeo que nunca deu
   * play, mas medido: sem uma reprodução real ter começado ao menos uma vez,
   * o decoder não produz NENHUM frame amostrável por `texImage2D` — nem no
   * frame 0 — então a camada some da tela sem erro nenhum, pro sempre,
   * mesmo com `_sincronizar` esperando certinho por `requestVideoFrameCallback`
   * depois. Este método só ativa o decoder; a posição final ainda é
   * responsabilidade do `_sincronizar` de cada desenho. Usa
   * `requestVideoFrameCallback` (quando existe) pra saber que o primeiro
   * frame chegou de verdade, em vez de um timeout de valor chutado.
   */
  async _cutucar(v, alvo = null) {
    // O navegador bloqueia play() programático com áudio. Para o aquecimento
    // do decoder não precisamos ouvi-lo: silencia só durante este frame e
    // restaura o estado original antes de devolver o controle ao player.
    const estavaMudo = v.muted;
    v.muted = true;
    try {
      const inicio = v.play();
      if (inicio && typeof inicio.catch === 'function') inicio.catch(() => {});
      await Promise.race([
        new Promise(resolve => {
          if (!v.requestVideoFrameCallback) return setTimeout(resolve, 150);
          const conferir = (_agora, meta) => {
            // O primeiro callback depois de mudar currentTime ainda pode ser
            // do quadro antigo. Só libera o pause quando o frame apresentado
            // chegou perto do segundo realmente solicitado.
            if (alvo == null || Math.abs((meta && meta.mediaTime) - alvo) < 0.3) resolve();
            else v.requestVideoFrameCallback(conferir);
          };
          v.requestVideoFrameCallback(conferir);
        }),
        // Alguns MP4s locais já exibem o quadro buscado, mas o Chromium não
        // encerra `seeking` nem chama rVFC. Não deixa o aquecimento pendurado.
        new Promise(resolve => setTimeout(resolve, 2000)),
      ]);
    } catch {}
    try { v.pause(); } catch {}
    v.muted = estavaMudo;
  }

  /**
   * Velocidade de reprodução do preview. Vale pra TODAS as camadas: se só o
   * vídeo acelerasse, o título e a legenda ficariam pra trás entre as
   * correções de sincronia e a legenda apareceria fora da fala.
   */
  velocidade(v) {
    this._vel = Math.max(0.25, Math.min(4, Number(v) || 1));
    const todos = [this.video, ...this._brolls.values(),
                   ...[...this._titulos.values()].map(e => e.video),
                   ...[...this._overlays.values()].map(e => e.video),
                   ...this._audios.values()];
    for (const el of todos) if (el) el.playbackRate = this._vel;
  }

  /** Projeto SEM vídeo principal — catálogo de títulos, cartela, peça só de
   *  motion. Sem isto o player tentava carregar "/" , o `onerror` disparava e
   *  o preview inteiro morria antes de desenhar qualquer coisa. */
  get semFonte() { return !String(this.cfg.videoSrc || '').trim(); }

  _montarVideo() {
    if (this.semFonte) { this.video = null; return; }
    const caminho = '/' + String(this.cfg.videoSrc || '').replace(/^\/+/, '');
    this.video = this._novoVideo(caminho, { mudo: false });
    // Chromium pode manter um <video> destacado preso em `seeking`, mesmo
    // com o range já disponível. Ligado ao DOM ele usa o pipeline normal de
    // decodificação. Fica fora da tela e transparente: WebGL continua sendo
    // a única imagem visível do preview.
    this.video.style.cssText = 'position:fixed;left:0;top:0;width:2px;height:2px;'
      + 'opacity:.001;pointer-events:none;z-index:0';
    if (document.body) document.body.appendChild(this.video);
    this.video.volume = this.cfg.videoMuted ? 0 : (this.cfg.videoVolume ?? 1);
  }

  async carregar() {
    if (this.semFonte) {
      // A duração vem do config, não do arquivo — é o único lugar que sabe
      // quanto dura uma peça que não tem fonte.
      this.duracao = this.cfg.videoDuration || 10;
      for (const b of (this.cfg.brolls || [])) this._pedirBroll(b);
      this.seek(0);
      return this;
    }
    await new Promise((ok, no) => {
      if (this.video.readyState >= 2) return ok();
      this.video.onloadeddata = ok;
      this.video.onerror = () => no(new Error('vídeo principal não carregou'));
    });
    this.duracao = this.cfg.videoDuration || this.video.duration;
    // O vídeo principal também nasce destacado do DOM. Sem uma reprodução
    // mínima, alguns Chromium mantêm readyState/currentTime corretos, mas não
    // entregam nenhum frame para texImage2D: o canvas fica preto no início e
    // congelado depois dos seeks. Acorda o decoder antes do primeiro desenho.
    await this._cutucar(this.video);
    // B-rolls são pedidos quando entram na janela ativa. Abrir todos aqui
    // ocupa as conexões HTTP do Chromium com preloads e pode deixar o range
    // do vídeo principal esperando atrás deles durante um seek.
    this.t = Math.min(this.video.currentTime || 0, this.duracao);
    this.desenhar();
    if (this.aoAtualizar) this.aoAtualizar(this.t);
    return this;
  }

  /**
   * Manda o MotionCore assar um título e guarda o <video>. Assíncrono de
   * propósito: assar leva de 4s a ~80s dependendo do estilo, então o preview
   * segue rodando e o título aparece quando ficar pronto — em vez de travar.
   */
  /**
   * A chave é o CONTEÚDO do título, não o id.
   *
   * Com chave por id, trocar o estilo devolvia o clipe velho do cache e nada
   * mudava na tela — o título continuava com a aparência anterior. Agora
   * qualquer mudança de estilo, texto, fonte, cor ou duração gera chave nova
   * e o clipe é reassado.
   */
  _chaveTitulo(t) {
    // Esta lista É o que faz o preview re-ASSAR. Campo que não está aqui
    // não muda a chave e o clipe em cache é reaproveitado.
    // posX/posY/scale/rotation/opacity ficam FORA de propósito: são aplicados
    // na composição (_camada), então mexer neles não re-assa nada — o ajuste
    // é instantâneo. Foi o conserto do "mudo o X e o título some": com eles
    // na chave, cada tweak disparava um re-bake de segundos no servidor.
    // Campo novo que mude o DESENHO entra aqui; que mude só o ENQUADRAMENTO,
    // entra na chamada de _camada do laço de desenho.
    const campos = ['style', 'text', 'partes', 'cena',
                    'fontFamily', 'color',
                    'fontSize',
                    'font1', 'font2', 'font3', 'color1', 'color2', 'color3',
                    'scale1', 'scale2', 'scale3',
                    'offsetX1', 'offsetY1', 'offsetX2', 'offsetY2',
                    'offsetX3', 'offsetY3'];
    const dur = Math.round(((t.endSec ?? 0) - (t.startSec ?? 0)) * 100) / 100;
    return JSON.stringify([campos.map(k => t[k] ?? null), dur]);
  }

  _pedirTitulo(t) {
    const chave = this._chaveTitulo(t);
    let e = this._titulos.get(chave);
    if (e) return e;
    e = { pronto: false, erro: null, video: null };
    this._titulos.set(chave, e);

    // FILA, nao disparo direto. Cada titulo e um pedido que pode levar
    // dezenas de segundos (medido: echoWords 39s, sensoryStorm 31s), e o
    // navegador so mantem ~6 conexoes por origem. Sem fila, os primeiros
    // resolviam e o resto ficava preso atras dos lentos — num projeto com 24
    // titulos, so os primeiros apareciam e os outros pareciam quebrados.
    // O bake vai NEUTRO: as transformacoes de composicao nao entram no clipe
    // (o _camada as aplica na hora). Mandar o titulo inteiro faria o servidor
    // assar um MOV por posicao — cache novo a cada pixel de ajuste.
    const neutro = { ...t };
    delete neutro.posX; delete neutro.posY; delete neutro.scale;
    delete neutro.rotation; delete neutro.opacity;
    this._naFila(() => fetch('/api/preview/clip', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: neutro, width: this.w, height: this.h,
                             fps: this.cfg.fps || 30 }),
    })
      .then(r => r.json())
      .then(j => {
        if (j.error) {
          e.erro = j.error;
          // Estilo que o motor ainda nao desenha: sem este aviso o titulo
          // simplesmente SOME da tela e nao ha como saber por que.
          if (/nao portado|não portado/i.test(j.error) && this._avisadoT !== t.style) {
            this._avisadoT = t.style;
            const m = `Estilo de título "${t.style}" ainda não é desenhado pelo nosso `
                    + `motor — o título não vai aparecer. Os portados estão sem o ⚠ na lista.`;
            if (typeof NLE !== 'undefined' && NLE.showToast) NLE.showToast(m, true);
            else console.warn('[Klipe] ' + m);
          }
          return;
        }
        const v = this._novoVideo('/' + j.src);
        v.onloadeddata = () => {
          this._cutucar(v).then(() => {
            e.pronto = true;
            // memoriza o clipe BOM deste titulo: enquanto uma edicao de texto/
            // estilo re-assa, o laco desenha este no lugar — o titulo nao pisca
            // nem some da tela durante o bake
            this._tituloPronto.set(t.id ?? t.startSec, e);
            this._redesenhar();
          });
        };
        e.video = v;
      })
      .catch(err => { e.erro = err.message; }));
    return e;
  }

  /** Duas por vez. Uma sozinha deixaria o preview lento a toa; sem limite, o
   *  navegador engasga. O `finally` roda mesmo em erro — senao um pedido que
   *  falha trava a fila pra sempre. */
  _naFila(tarefa) {
    if (!this._fila) { this._fila = []; this._emVoo = 0; }
    this._fila.push(tarefa);
    const anda = () => {
      while (this._emVoo < 2 && this._fila.length) {
        this._emVoo++;
        const f = this._fila.shift();
        Promise.resolve()
          .then(f)
          .catch(() => {})
          .finally(() => { this._emVoo--; anda(); });
      }
    };
    anda();
  }

  /**
   * O pedaço de overlay que cobre o segundo `t` — legenda E barra de progresso
   * vêm no MESMO arquivo, porque o MotionCore desenha as duas na mesma passada.
   *
   * Em pedaços de 30s: assar os 17 min de uma vez levaria minutos, e editar
   * uma legenda invalidaria tudo. Assim só o trecho visível é pago.
   */
  _pedirOverlay(t) {
    const idx = Math.floor(t / KlipePlayer.JANELA_S);
    if (idx < 0) return null;
    let e = this._overlays.get(idx);
    if (e) return e;
    e = { pronto: false, vazio: false, erro: null, video: null, inicio: idx * KlipePlayer.JANELA_S };
    this._overlays.set(idx, e);

    // Manda o estado ATUAL junto. Antes o servidor lia o edit_config do disco,
    // e aí mexer no estilo da legenda não mudava nada no preview até salvar —
    // que na prática é a legenda "não mudar de estilo".
    // Só as legendas da janela vão no corpo (~15 de 349), então continua leve.
    const ini = idx * KlipePlayer.JANELA_S, fim = ini + KlipePlayer.JANELA_S;
    const c = this.cfg;

    // Medido: uma janela fria leva de 4 a 6s. Sem sinal nenhum na tela, quem
    // está editando vê o vídeo rodar sem legenda e conclui que quebrou. O
    // `job` é o que liga este pedido ao progresso que o motor publica.
    const job = `l${idx}-${this._seqJob = (this._seqJob || 0) + 1}`;
    e.job = job;
    e.pct = 0;
    const sonda = setInterval(async () => {
      if (e.pronto || e.vazio || e.erro) { clearInterval(sonda); e.pct = null; return; }
      try {
        const p = await (await fetch(`/api/preview/legenda/progresso?job=${job}`)).json();
        // só mostra depois que houver progresso real; tira em cache volta
        // antes da primeira sondagem e piscar 0% seria ruído
        if (typeof p.pct === 'number') { e.pct = p.pct; e.fase = p.fase; }
      } catch {}
    }, 350);
    e._sonda = sonda;

    fetch('/api/preview/legenda', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pedaco: idx, job,
        captions: (c.captions || []).filter(x => x.endSec > ini && x.startSec < fim),
        estilo: {
          showCaptions: c.showCaptions, captionStyle: c.captionStyle,
          captionFont: c.captionFont, captionFontSize: c.captionFontSize,
          captionColor: c.captionColor, captionHighlightColor: c.captionHighlightColor,
          captionKaraoke: c.captionKaraoke, captionMaxLines: c.captionMaxLines,
          captionWordGap: c.captionWordGap, captionLineGap: c.captionLineGap,
          captionX: c.captionX, captionY: c.captionY,
          showProgressBar: c.showProgressBar, barColor: c.barColor, barHeight: c.barHeight,
        },
      }),
    })
      .then(r => r.json())
      .then(j => {
        if (j.vazio) { e.vazio = true; return; }
        if (j.naoPortado) {
          // avisa UMA vez por estilo, senão vira enxurrada de toast a cada pedaço
          e.erro = j.error;
          if (this._avisado !== j.naoPortado) {
            this._avisado = j.naoPortado;
            const m = `Legenda "${j.naoPortado}" ainda não é desenhada pelo nosso motor `
                    + `— só ${j.portados.join(' e ')}. A legenda não vai aparecer neste estilo.`;
            if (typeof NLE !== 'undefined' && NLE.showToast) NLE.showToast(m, true);
            else console.warn('[Klipe] ' + m);
          }
          return;
        }
        if (j.error) { e.erro = j.error; return; }
        e.inicio = j.inicio ?? e.inicio;
        const v = this._novoVideo('/' + j.src);
        v.onloadeddata = () => {
          this._cutucar(v).then(() => {
            e.pronto = true;
            const antigo = this._velhos.get(idx);
            if (antigo) { antigo.video.src = ''; this._velhos.delete(idx); }
            this._redesenhar();
          });
        };
        e.video = v;
      })
      .catch(err => { e.erro = err.message; })
      // sempre: se o pedido morrer sem marcar pronto/vazio/erro, a sonda
      // ficaria batendo no servidor pra sempre
      .finally(() => { clearInterval(sonda); e.pct = null; this._redesenhar(); });
    return e;
  }

  /** O pedaço que cobre `t` ainda está sendo assado? {pct, fase} ou null. */
  estadoLegenda(t) {
    const e = this._overlays.get(Math.floor(t / KlipePlayer.JANELA_S));
    if (!e || e.pronto || e.vazio || e.erro) return null;
    return { pct: typeof e.pct === 'number' ? e.pct : 0, fase: e.fase || 'preparando' };
  }

  _pedirBroll(b) {
    const id = b.id || b.src;
    let v = this._brolls.get(id);
    if (!v) {
      v = this._novoVideo('/' + String(b.src).replace(/^\/+/, ''));
      this._brolls.set(id, v);
      // B-roll criado enquanto o preview esta pausado nunca chega a produzir
      // um frame decodificado sozinho. Acorda o decoder como ja fazemos com
      // titulos e legendas; depois redesenha o canvas no quadro atual.
      const acordar = () => {
        // loadeddata pode chegar antes do primeiro frame ficar amostravel pelo
        // WebGL. Redesenhos curtos cobrem as duas etapas sem exigir que o
        // usuario mova o playhead uma segunda vez.
        this._redesenhar();
        setTimeout(() => this._redesenhar(), 180);
        this._cutucar(v).finally(() => this._redesenhar());
      };
      if (v.readyState >= 2) acordar();
      else v.addEventListener('loadeddata', acordar, { once: true });
    }
    return v;
  }

  /**
   * Põe uma camada no instante certo.
   *
   * `currentTime = x` num <video> é ASSÍNCRONO: o quadro novo só existe
   * quando o evento `seeked` dispara. Tocando isso não importa, porque o laço
   * redesenha 30x por segundo e o quadro chega no próximo. PAUSADO importa
   * muito — desenha-se uma vez só, com o quadro VELHO, e a camada parece
   * congelada: a legenda não muda e não some quando deveria.
   *
   * Por isso, pausado, agenda um redesenho para quando o quadro chegar. Mas
   * `seeked` sozinho AVISA CEDO DEMAIS pra vídeo que nunca tocou (título e
   * legenda nascem assim): o evento diz que a posição mudou, não que o
   * decoder já produziu um frame amostrável — medido, `texImage2D` sobe
   * frame vazio/velho nesse instante, e a camada some da tela sem erro
   * nenhum. `requestVideoFrameCallback` é a API feita pra isso (dispara só
   * quando um frame novo está pronto pra composição, inclusive parado);
   * onde não existe, cai pro `seeked` de antes — pior cobertura, não pior
   * que o comportamento anterior.
   */
  _sincronizar(v, rel, tolerancia = 0.12) {
    if (!v) return;
    if (Math.abs(v.currentTime - rel) > tolerancia) {
      try {
        v.currentTime = rel;
        if (!this.tocando) {
          if (v.requestVideoFrameCallback) v.requestVideoFrameCallback(() => this._redesenhar());
          else v.addEventListener('seeked', () => this._redesenhar(), { once: true });
        }
      } catch {}
    }
    if (this.tocando && v.paused) v.play().catch(() => {});
  }

  /** Redesenho único no próximo quadro (junta várias camadas numa passada).
   *
   * CANCELA o pedido anterior em vez de só checar se ele existe. Um `rAF`
   * que nunca dispara — aba sem foco, thread ocupada — deixava `_pedido`
   * travado num id não-zero pra sempre, e todo `_redesenhar()` seguinte
   * virava no-op silencioso: título/legenda parava de acompanhar o seek até
   * um F5. `cancelAnimationFrame` num id já disparado ou inválido não faz
   * nada, então cancelar sempre é seguro mesmo quando não há o que cancelar.
   */
  _redesenhar() {
    if (this.tocando) return;
    if (this._pedido) cancelAnimationFrame(this._pedido);
    this._pedido = requestAnimationFrame(() => { this._pedido = 0; this.desenhar(); });
  }

  /** SFX e música: um <audio> por clipe, sincronizado como as camadas de vídeo. */
  _tocarAudios(t) {
    const clips = [...(this.cfg.sfx || []), ...(this.cfg.musicTracks || [])];
    const ativos = new Set();
    for (const c of clips) {
      // PRE-CARREGA 3s antes da janela: criar o <audio> na hora de tocar
      // custa 100-300ms de rede+decodificacao, e isso atrasava os SFX que
      // comecam EXATOS no gancho (os do zoom). Os de titulo nao sofriam
      // porque ja nascem 0,2s adiantados — a folga escondia a latencia.
      if (t >= c.startSec - 3 && t < c.startSec) {
        const k = c.id || (c.src + '@' + c.startSec);
        if (!this._audios.has(k)) {
          const pre = new Audio('/' + String(c.src).replace(/^\/+/, ''));
          pre.preload = 'auto';
          this._audios.set(k, pre);
        }
        continue;
      }
      if (t < c.startSec || t >= c.endSec) continue;
      // O estado do editor entrega os SFX SEM id — com chave `undefined`,
      // os 20 clipes dividiam UM <audio> e saia sempre o mesmo som. A chave
      // precisa ser unica por clipe mesmo sem id.
      const chave = c.id || (c.src + '@' + c.startSec);
      ativos.add(chave);
      let a = this._audios.get(chave);
      if (!a) {
        a = new Audio('/' + String(c.src).replace(/^\/+/, ''));
        a.preload = 'auto';
        this._audios.set(chave, a);
      }
      // volume do clipe É a propriedade editável — ler aqui, a cada quadro,
      // é o que faz o slider de volume valer na hora
      // Fade de entrada e saida. O RENDER ja aplicava (afade in/out) e o
      // preview tocava seco — e a timeline ainda desenhava o triangulo do
      // fade, reforcando a ilusao de que estava funcionando. Rampa linear,
      // igual a do ffmpeg, pra os dois lados fazerem a mesma conta.
      const relC = t - c.startSec;
      const restante = c.endSec - t;
      let ganho = Math.max(0, Math.min(1, c.volume ?? 1));
      const fi = Number(c.fadeIn) || 0;
      const fo = Number(c.fadeOut) || 0;
      if (fi > 0 && relC < fi) ganho *= Math.max(0, relC / fi);
      if (fo > 0 && restante < fo) ganho *= Math.max(0, restante / fo);
      a.volume = Math.max(0, Math.min(1, ganho));
      a.playbackRate = this._vel || 1;
      const rel = (t - c.startSec) + (c.srcStart || 0);
      if (Math.abs(a.currentTime - rel) > 0.3) { try { a.currentTime = rel; } catch {} }
      if (this.tocando && a.paused) a.play().catch(() => {});
      if (!this.tocando && !a.paused) a.pause();
    }
    // saiu da janela = para na hora, senão o whoosh vaza pelo clipe seguinte
    for (const [id, a] of this._audios) {
      if (!ativos.has(id) && !a.paused) a.pause();
    }
  }

  // ── zoom ─────────────────────────────────────────────────────────────
  // Devolve o retângulo -1..1 pro vídeo principal, aplicando o zoom ativo.
  // ESTA CONTA E COPIA DE `build_zoom_expression` DO forge_render.py.
  // Se uma mudar, a outra tem que mudar junto — é o preview e o render
  // desenhando a mesma coisa, e divergir aqui é a falha mais cara que existe:
  // a pessoa escolhe no painel, vê uma coisa, e só descobre no arquivo final.
  //
  // Antes daqui divergiam 5 das 6 direções:
  //   breathe  — o preview mostrava empurrão que ficava; o render vai e volta
  //   slowIn   — preview em easeInOut; render em p^1.7
  //   hardOut  — preview empurrava; no render é 1.0, ou seja, zoom nenhum
  //   hardIn   — preview subia em p*3; no render é constante desde o quadro 1
  //   in/out   — preview sempre easeInOut; o render lê `easing`, que é LINEAR
  //              por padrão
  _recorteZoom(t) {
    const z = (this.cfg.zooms || []).find(z => t >= z.startSec && t < z.endSec);
    if (!z) return null;
    const p = Math.min(1, Math.max(0, (t - z.startSec) / Math.max(0.001, z.endSec - z.startSec)));
    const alvo = Number(z.intensity) || 1.15;
    const d = alvo - 1;

    // `applyEasing` do Klipe: o padrão é LINEAR, não suave.
    const suavizar = (nome, x) => {
      if (nome === 'easeInOut') return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;
      if (nome === 'easeIn') return Math.pow(x, 3);
      if (nome === 'easeOut') return 1 - Math.pow(1 - x, 3);
      if (nome === 'smooth') return x * x * (3 - 2 * x);
      return x;
    };
    const q = suavizar(z.easing || 'linear', p);

    let f;
    switch (z.direction || 'in') {
      case 'slowIn':  f = d * Math.pow(p, 1.7); break;
      case 'breathe': f = d * Math.sin(Math.PI * p); break;   // vai e volta
      case 'hardIn':  f = d; break;                            // constante
      case 'hardOut': f = 0; break;                            // sem zoom
      case 'out':     f = d * (1 - q); break;
      default:        f = d * q; break;                        // in
    }
    const e = 1 + f;
    // originY: onde o zoom "olha" na vertical. O render desloca o corte
    // (crop_y = h*(zf-1)*originY/100, default 40); sem isto o preview
    // centrava sempre e zoom em rosto mostrava o peito no arquivo final.
    // A conta vira deslocamento de UV — mover o quad nao funciona, porque
    // uv nasce de p e geometria e amostragem se cancelariam.
    // uvOffY = fracao da textura que o centro da tela desloca:
    //   originY=50 -> 0 (centro), 100 -> mostra a base, 0 -> mostra o topo.
    const oy = (z.originY == null) ? 40 : Number(z.originY);
    const uvOffY = ((oy - 50) / 100) * (1 - 1 / Math.max(1.0001, e));
    return [-e, -e, e, e, uvOffY];
  }

  // ── desenho ──────────────────────────────────────────────────────────
  desenhar() {
    const gl = this.gl, t = this.t;
    this._tocarAudios(t);
    // volume/mudo do vídeo principal são propriedades editáveis — reler
    // sempre, senão mexer no painel não muda nada até recarregar
    if (this.video) this.video.volume = this.cfg.videoMuted ? 0 : (this.cfg.videoVolume ?? 1);
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);

    // Sem fonte, o quadro preto que o `clear` acabou de pintar E o fundo:
    // o catalogo desenha os titulos sobre ele, como folha em branco.
    if (this.video) this._camada('fonte', this.video, { recorte: this._recorteZoom(t), corrigirCor: true });

    for (const b of (this.cfg.brolls || [])) {
      if (t < b.startSec || t >= b.endSec) continue;
      const v = this._pedirBroll(b);
      // `rel` é o tempo dentro do CLIPE — é o que os fades medem.
      // O <video> tem que ser sincronizado com o tempo dentro da FONTE, que é
      // `rel + srcStart`. Sem somar o srcStart, aparar o início do b-roll movia
      // a borda na timeline e o vídeo continuava tocando do segundo 0: o corte
      // de entrada não existia. O áudio já somava (`_tocarAudios`); o b-roll não.
      const rel = t - b.startSec;
      // Velocidade: 1s de timeline consome `vel` s de fonte — a mesma conta que
      // o `clip.endSec = startSec + baseDurationSec/speed` do editor assume.
      // Não era aplicada: o player nunca tocou no `playbackRate` do b-roll, e o
      // render também ignorava. Os dois ignoravam junto, então o controle
      // existia e não fazia nada em lugar nenhum.
      const vel = Math.min(10, Math.max(0.1, b.speed || 1));
      if (v.playbackRate !== vel) { try { v.playbackRate = vel; } catch {} }
      this._sincronizar(v, (b.srcStart || 0) + rel * vel, 0.25);
      let op = 1;
      if (b.fadeIn) op = Math.min(op, rel / b.fadeIn);
      if (b.fadeOut) op = Math.min(op, (b.endSec - t) / b.fadeOut);
      // A opacidade do CLIPE multiplica os fades. Não era lida: o painel
      // gravava `opacity` no estado e o player desenhava sempre em 1, então
      // mexer no controle não mudava nada na tela.
      if (b.opacity !== undefined) op *= Math.max(0, Math.min(1, b.opacity));
      // `alpha` = clipe assado no formato lado-a-lado (cor | alpha), o mesmo
      // que os titulos usam. E o que permite CAMADA DE EFEITO sobre o video
      // principal em vez de efeito FUNDIDO nele: a base continua trocavel.
      this._camada('b' + (b.id || b.src), v,
                   { opacidade: Math.max(0, Math.min(1, op)),
                     alphaLateral: !!b.alpha,
                     posX: b.posX || 0, posY: b.posY || 0,
                     escala: b.scale || 1 });
    }

    for (const tt of (this.cfg.titles || [])) {
      if (t < tt.startSec || t >= tt.endSec) continue;
      let e = this._pedirTitulo(tt);
      if (!e.pronto || !e.video) {
        // o clipe novo ainda esta assando — desenha o ultimo bom deste
        // titulo em vez de sumir com ele da tela
        const velho = this._tituloPronto.get(tt.id ?? tt.startSec);
        if (velho && velho.pronto && velho.video) e = velho;
      }
      if (!e.pronto || !e.video) continue;
      this._sincronizar(e.video, t - tt.startSec);
      // As transformacoes moram AQUI, nao no clipe assado — mesma conta do
      // render (scale/rotate/overlay) e do motor. posY do painel e positivo
      // pra cima; o _camada quer positivo pra baixo, dai o sinal.
      this._camada('t' + (tt.id || tt.startSec), e.video, {
        alphaLateral: true,
        posX: tt.posX || 0,
        posY: -(tt.posY || 0),
        escala: tt.scale == null ? 1 : tt.scale,
        rotacao: tt.rotation || 0,
        opacidade: tt.opacity == null ? 1 : tt.opacity,
      });
    }

    // legenda + barra por último: no render elas ficam por cima de tudo
    const ov = this._pedirOverlay(t);
    const velho = this._velhos.get(Math.floor(t / KlipePlayer.JANELA_S));
    const usar = (ov && ov.pronto && ov.video) ? ov : velho;
    if (usar && usar.video) {
      this._sincronizar(usar.video, t - usar.inicio);
      this._camada('ov', usar.video, { alphaLateral: true });
    }
    // pede o próximo pedaço antes de chegar nele, senão a legenda pisca no
    // corte a cada 30s enquanto o novo assa
    if (this.tocando && (t % KlipePlayer.JANELA_S) > KlipePlayer.JANELA_S - 8) {
      this._pedirOverlay(t + KlipePlayer.JANELA_S);
    }
  }

  // ── transporte ───────────────────────────────────────────────────────
  seek(sec) {
    this.t = Math.max(0, Math.min(sec, this.duracao || sec));
    // Seek pausado precisa pintar direto. requestAnimationFrame pode ficar
    // estrangulado numa aba sem foco e deixar o canvas no quadro anterior,
    // mesmo depois de o <video> já ter decodificado a nova posição.
    const pintarSeek = () => {
      if (!this.tocando) {
        if (this._pedido) cancelAnimationFrame(this._pedido);
        this._pedido = 0;
        this.desenhar();
      }
    };
    // O vídeo principal também busca de forma assíncrona. Redesenhar logo
    // depois de atribuir currentTime mantém o quadro anterior congelado no
    // canvas até outro evento qualquer disparar. No vídeo principal, espera
    // explicitamente `seeked` antes de pedir o frame: registrar somente um
    // requestVideoFrameCallback logo após mudar currentTime pode devolver o
    // quadro que ainda estava apresentado antes da busca.
    if (this.video && Math.abs(this.video.currentTime - this.t) > 0.03) {
      const v = this.video;
      // Buscar exatamente no começo de um range/keyframe pode deixar alguns
      // Chromium em readyState=1 mesmo com o intervalo já no buffer. Um frame
      // para dentro evita a borda sem deslocar o tempo lógico da composição.
      const alvoVideo = this.t > 0
        ? Math.min(this.t + 1 / Math.max(1, this.cfg.fps || 30), this.duracao)
        : 0;
      if (!this.tocando) {
        v.addEventListener('seeked', () => {
          pintarSeek();
          if (v.requestVideoFrameCallback) {
            v.requestVideoFrameCallback(pintarSeek);
          }
          setTimeout(pintarSeek, 120);
        }, { once: true });
      }
      try { v.currentTime = alvoVideo; } catch {}
      // Vídeo destacado do DOM pode não concluir o seek enquanto permanece
      // pausado. Acordar só dentro de `seeked` criava um ciclo: o evento
      // esperava a decodificação, e a decodificação esperava o evento.
      if (!this.tocando) this._cutucar(v, alvoVideo).finally(pintarSeek);
      // Em certos builds do Chromium o quadro novo fica disponível para
      // texImage2D sem `seeked` nem rVFC. Redesenhos baratos e limitados
      // cobrem esse caminho sem manter um laço permanente.
      for (const atraso of [120, 300, 700, 1300]) setTimeout(pintarSeek, atraso);
    }
    // pausado também precisa redesenhar, senão o canvas fica no frame velho.
    // Por `_redesenhar()` (que cancela/reagenda), não por um rAF cru próprio:
    // dois agendamentos concorrentes e sem coordenação com `_pedido` é o
    // mesmo risco de perder o pedido que motivou o cancelAnimationFrame ali.
    pintarSeek();
    if (this.aoAtualizar) this.aoAtualizar(this.t);
  }

  play() {
    if (this.tocando) return;
    this.tocando = true;
    if (this.video) {
      this.video.muted = false;
      this.video.play().catch(() => {});
    }
    const laco = () => {
      if (!this.tocando) return;
      // sem fonte nao ha relogio de video: o tempo anda pelo proprio laco
      if (this.video) this.t = this.video.currentTime;
      this.desenhar();
      if (this.aoAtualizar) this.aoAtualizar(this.t);
      this._raf = requestAnimationFrame(laco);
    };
    laco();
  }

  pause() {
    this.tocando = false;
    cancelAnimationFrame(this._raf);
    if (this.video) this.video.pause();
    for (const v of this._brolls.values()) v.pause();
    for (const e of this._titulos.values()) if (e.video) e.video.pause();
    for (const e of this._overlays.values()) if (e.video) e.video.pause();
    for (const a of this._audios.values()) a.pause();
  }

  /** Chamar quando um título mudar: joga fora o clipe assado pra reassar. */
  invalidarTitulo(id) { this._titulos.delete(id); }

  /**
   * O estilo da legenda mudou: o pedaço assado ficou velho.
   *
   * NÃO joga o vídeo fora — guarda como `velho` e continua desenhando ele até
   * o novo ficar pronto. Assar leva uns 5s; sem isso a legenda SOME da tela
   * nesse intervalo, e quem está ajustando estilo vê a legenda piscando fora
   * a cada clique.
   */
  invalidarLegendas() {
    const antigos = [...this._overlays.entries()];
    this._overlays.clear();
    for (const [idx, e] of antigos) {
      if (e.pronto && e.video) this._velhos.set(idx, { video: e.video, inicio: e.inicio });
      else if (e.video) e.video.src = '';
    }
  }

  destruir() {
    this.pause();
    if (this.video) this.video.src = '';
    for (const v of this._brolls.values()) v.src = '';
    for (const e of this._titulos.values()) if (e.video) e.video.src = '';
    this.invalidarLegendas();
    for (const a of this._audios.values()) { a.pause(); a.src = ''; }
    this._audios.clear();
    this._titulos.clear();
    this._brolls.clear();
  }
}

// Tem que bater com o JANELA_S do preview_server.py: se divergirem, o player
// pede o pedaco 3 e recebe outro trecho do video.
KlipePlayer.JANELA_S = 30;

if (typeof window !== 'undefined') window.KlipePlayer = KlipePlayer;
