"""
preview_server.py — o MotionCore desenhando títulos sob demanda, pro preview.

Por que um servidor e não um script por chamada: o custo do MotionCore está
quase todo na PARTIDA (importar o skia, varrer e registrar as fontes). Desenhar
o quadro em si é barato. Um processo que fica de pé paga isso uma vez; um
script por clique pagaria a cada mexida de slider.

É a peça que tira O motor de navegador do preview: em vez de uma segunda implementação
dos estilos em JS — que foi exatamente o que produziu os bugs de fonte errada
e scan line faltando — o preview passa a mostrar O MESMO desenho que o render
usa. Uma implementação só.

Só escuta em 127.0.0.1. Não é pra ficar exposto.

    python -m motioncore.preview_server [porta]
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import skia

from .fonts import FontRegistry
from .scene import Title, TitleRenderer
from .styles import STYLES

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "public" / ".preview_cache"
# Uma trava por clipe: sem isso, apertar play com 5 titulos na tela dispara 5
# renders do MESMO arquivo ao mesmo tempo, e eles se sobrescrevem pela metade.
_TRAVAS: dict[str, threading.Lock] = {}
_TRAVAS_MUTEX = threading.Lock()

_REG: FontRegistry | None = None
# TitleRenderer mede o texto no __init__ (shaping), e isso é o caro por título.
# Enquanto o usuário arrasta um slider, o título é o mesmo — então guardar o
# renderer por assinatura faz o arraste custar só o desenho.
_CACHE: dict[str, TitleRenderer] = {}
_MAX_CACHE = 64


def _registry() -> FontRegistry:
    global _REG
    if _REG is None:
        t0 = time.time()
        _REG = FontRegistry()
        print(f"[preview] fontes carregadas em {time.time()-t0:.2f}s", flush=True)
    return _REG


def _renderer(spec: dict, w: int, h: int, fps: float) -> TitleRenderer:
    chave = json.dumps([spec, w, h, fps], sort_keys=True, ensure_ascii=False)
    r = _CACHE.get(chave)
    if r is None:
        if len(_CACHE) >= _MAX_CACHE:
            _CACHE.pop(next(iter(_CACHE)))
        r = TitleRenderer(Title.from_dict(spec), w, h, fps=fps, registry=_registry())
        _CACHE[chave] = r
    return r


def desenhar(corpo: dict) -> bytes:
    """PNG com alpha de UM quadro do título."""
    spec = dict(corpo.get("title") or {})
    # o preview manda em escala reduzida: o layout é proporcional, então o
    # desenho é o mesmo, só que com menos pixel pra encher
    w = int(corpo.get("width") or 1080)
    h = int(corpo.get("height") or 1920)
    fps = float(corpo.get("fps") or 30)

    # Sem tempo no spec o TitleRenderer não sabe a duração; o preview manda
    # `frame` e `durationFrames` direto pra poder desenhar qualquer instante.
    spec.setdefault("startSec", 0.0)
    dur_frames = corpo.get("durationFrames")
    if dur_frames:
        spec["endSec"] = spec["startSec"] + float(dur_frames) / fps

    r = _renderer(spec, w, h, fps)
    img = r.render_still(float(corpo.get("frame") or 0))
    # encodeToData() sem argumento = PNG. A forma com formato exige tambem o
    # `quality`, e passar so o formato levanta TypeError.
    return bytes(img.encodeToData())


# O render guarda cada titulo em .forge_cache/titles_indiv/<hash>.mov, com chave
# INDEPENDENTE DE POSICAO (mover na timeline nao invalida). Aqui a gente reusa
# essa mesma chave pra descobrir se o desenho ja existe.
CACHE_RENDER = RAIZ / "output" / ".forge_cache" / "titles_indiv"
# Resolvido em tempo de execucao (env > Configuracoes > C:/ffmpeg > PATH):
# cravar o caminho aqui fazia o render morrer em qualquer maquina que nao
# fosse a de quem escreveu. Ver motioncore/ffbin.py.
from .ffbin import ffmpeg as _ffmpeg
FFMPEG = _ffmpeg()


def _hash_render(spec: dict, w: int, h: int, fps: float) -> str:
    """Reproduz `title_hash()` do forge_render — se divergir, o reuso nunca acerta."""
    import hashlib as _h
    t = {k: v for k, v in spec.items() if k not in ("startSec", "endSec", "id")}
    t["_dur"] = round(float(spec["endSec"]) - float(spec["startSec"]), 2)
    payload = {"t": t, "w": w, "h": h, "fps": fps}
    return _h.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _mov_do_render(spec: dict, w: int, h: int, fps: float) -> Path | None:
    p = CACHE_RENDER / f"{_hash_render(spec, w, h, fps)}.mov"
    return p if p.exists() and p.stat().st_size > 1000 else None


def _transcodificar(mov: Path, destino: Path, w: int, h: int) -> bool:
    """QTRLE com alpha -> H.264 cor+alpha lado a lado, sem redesenhar nada."""
    import subprocess
    lw = max(2, (w // 2) // 2 * 2)
    lh = max(2, (h // 2) // 2 * 2)
    r = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(mov),
         "-filter_complex",
         f"[0:v]scale={lw}:{lh},format=rgba,split=2[c][a];"
         f"[c]format=yuv420p[cc];[a]alphaextract,format=yuv420p[aa];"
         f"[cc][aa]hstack=inputs=2",
         "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "26",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(destino)],
        capture_output=True)
    return r.returncode == 0 and destino.exists() and destino.stat().st_size > 1000


def assar(corpo: dict) -> dict:
    """
    Renderiza o título inteiro num MP4 que o navegador toca (cor à esquerda,
    alpha em cinza à direita) e devolve o caminho. Cacheado pelo conteúdo: o
    mesmo título com os mesmos parâmetros não é renderizado duas vezes.
    """
    from .render import render_title_mov

    spec = dict(corpo.get("title") or {})
    w = int(corpo.get("width") or 1080)
    h = int(corpo.get("height") or 1920)
    fps = float(corpo.get("fps") or 30)
    # o clipe nasce ancorado em t=0; quem posiciona na linha do tempo é o player
    dur = float(spec.get("endSec", 0)) - float(spec.get("startSec", 0))
    spec["startSec"], spec["endSec"] = 0.0, max(dur, 1.0 / fps)

    chave = hashlib.sha1(
        json.dumps([spec, w, h, fps], sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]
    destino = CACHE / f"{chave}.mp4"
    rel = f".preview_cache/{chave}.mp4"
    if destino.exists() and destino.stat().st_size > 1000:
        return {"src": rel, "cache": True}

    with _TRAVAS_MUTEX:
        trava = _TRAVAS.setdefault(chave, threading.Lock())
    with trava:
        if destino.exists() and destino.stat().st_size > 1000:
            return {"src": rel, "cache": True}
        CACHE.mkdir(parents=True, exist_ok=True)
        t0 = time.time()

        # Se o RENDER ja desenhou este titulo, nao desenha de novo: transcodifica
        # o QTRLE cacheado. Desenhar custa de 4s a 80s (o sensoryStorm redesenha
        # a scan line em todo frame); transcodificar custa ~1s, porque so muda
        # de recipiente. E o mesmo desenho, entao nao ha risco de divergir.
        mov = _mov_do_render(spec, w, h, fps)
        if mov:
            if _transcodificar(mov, destino, w, h):
                dt = time.time() - t0
                print(f"[preview] {spec.get('style')} reaproveitado do render "
                      f"em {dt:.1f}s (sem redesenhar)", flush=True)
                return {"src": rel, "cache": False, "reuso": True,
                        "segundos": round(dt, 1)}

        r = render_title_mov(spec, destino, w, h, fps=fps, codec="preview")
        print(f"[preview] assou {spec.get('style')} {r['frames']}f em "
              f"{time.time()-t0:.1f}s ({r['size_mb']} MB)", flush=True)
        return {"src": rel, "cache": False, "segundos": round(time.time() - t0, 1),
                "frames": r["frames"], "mb": r["size_mb"]}


def miniatura(corpo: dict) -> dict:
    """
    PNG de UM quadro, guardado em disco. É o que a galeria de templates mostra
    em cada cartão: em vez de o usuário adivinhar pelo nome do estilo, ele vê o
    título desenhado — pelo mesmo motor que vai desenhar no render.

    Cacheado por conteúdo, então a galeria só paga o desenho na primeira vez.
    """
    spec = dict(corpo.get("title") or {})
    w = int(corpo.get("width") or 1080)
    h = int(corpo.get("height") or 1920)
    fps = float(corpo.get("fps") or 30)
    # Instante fixo no miolo da animação: entrada e saída deixam o título
    # meio transparente ou fora de posição, e aí a miniatura não representa
    # o estilo. 60% é depois do spring assentar e antes da saída começar.
    dur = float(corpo.get("duracaoSeg") or 4.0)
    spec["startSec"], spec["endSec"] = 0.0, dur
    frame = round(dur * fps * 0.6)

    chave = hashlib.sha1(
        json.dumps([spec, w, h, fps, frame, "thumb"], sort_keys=True,
                   ensure_ascii=False).encode()).hexdigest()[:16]
    destino = CACHE / f"m_{chave}.png"
    rel = f".preview_cache/m_{chave}.png"
    if destino.exists() and destino.stat().st_size > 200:
        return {"src": rel, "cache": True}

    with _TRAVAS_MUTEX:
        trava = _TRAVAS.setdefault(chave, threading.Lock())
    with trava:
        if destino.exists() and destino.stat().st_size > 200:
            return {"src": rel, "cache": True}
        CACHE.mkdir(parents=True, exist_ok=True)
        png = desenhar({"title": spec, "width": w, "height": h, "fps": fps,
                        "durationFrames": round(dur * fps), "frame": frame})
        destino.write_bytes(png)
        return {"src": rel, "cache": False}


def miniatura_legenda(corpo: dict) -> dict:
    """
    PNG de uma legenda de exemplo, desenhada pelo MOTOR.

    Os cartões do painel eram imitação em HTML/CSS — mostravam uma coisa e o
    render entregava outra. Aqui o cartão passa a ser o desenho real: se a
    miniatura está certa, a legenda vai sair assim.

    Recorta só a faixa da legenda, que é onde o conteúdo mora.
    """
    from .captions import CaptionRenderer

    estilo = corpo.get("estilo") or "outline"
    texto = corpo.get("texto") or "é assim que fica a sua legenda"
    base = json.loads((RAIZ / "public" / "edit_config.json").read_text(encoding="utf-8"))

    # legenda única cobrindo o instante que a gente desenha; o resto do
    # projeto (fonte, tamanho, cores) vem do config real, então o cartão
    # reflete AS SUAS configurações, não um exemplo genérico
    cfg = dict(base)
    cfg["captionStyle"] = estilo
    cfg["captions"] = [{"startSec": 0.0, "endSec": 3.0, "text": texto}]
    cfg["showProgressBar"] = False
    if corpo.get("preset"):
        cfg["captionPreset"] = corpo["preset"]
    w = int(cfg.get("width") or 1080)
    h = int(cfg.get("height") or 1920)
    fps = float(cfg.get("fps") or 30)

    chave = hashlib.sha1(json.dumps(
        [estilo, texto, corpo.get("preset"), w, h, fps,
         cfg.get("captionFont"), cfg.get("captionFontSize"), cfg.get("captionColor"),
         cfg.get("captionHighlightColor"), cfg.get("captionMaxLines"),
         cfg.get("captionWordGap"), "legenda-thumb"],
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    destino = CACHE / f"cl_{chave}.png"
    rel = f".preview_cache/cl_{chave}.png"
    if destino.exists() and destino.stat().st_size > 200:
        return {"src": rel, "cache": True}

    with _TRAVAS_MUTEX:
        trava = _TRAVAS.setdefault(chave, threading.Lock())
    with trava:
        if destino.exists() and destino.stat().st_size > 200:
            return {"src": rel, "cache": True}
        r = CaptionRenderer(cfg, w, h, fps=fps, registry=_registry())
        y0, y1 = r.band()
        if y1 <= y0:
            return {"error": "estilo nao desenhou nada"}
        surf = skia.Surface(w, y1 - y0)
        cv = surf.getCanvas()
        cv.clear(skia.Color4f(0, 0, 0, 0))
        cv.save()
        cv.translate(0, -y0)
        # 40% da duração: já passou a entrada, a palavra do meio está ativa
        r.draw_frame(cv, round(3.0 * fps * 0.4))
        cv.restore()
        CACHE.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(bytes(surf.makeImageSnapshot().encodeToData()))
        return {"src": rel, "cache": False, "faixa": [y0, y1]}


JANELA_S = 30.0        # tamanho do pedaço de legenda

# Progresso das tiras em andamento, por `job` que o cliente inventa.
#
# Medido: uma janela fria leva de 4 a 6 segundos. Nesse tempo o vídeo roda sem
# legenda e nada na tela diz que algo está sendo feito — quem está editando
# conclui que quebrou. O progresso é REAL (quadros desenhados / total), não
# uma barra estimada por relógio: com cache, uma estimativa erraria feio,
# mostrando 40% numa tira que já voltou pronta.
_PROGRESSO: dict[str, dict] = {}
_PROG_MUTEX = threading.Lock()


def _marcar(job, feitos, total, fase="desenhando"):
    if not job:
        return
    with _PROG_MUTEX:
        _PROGRESSO[job] = {"feitos": feitos, "total": total, "fase": fase,
                           "pct": round(100 * feitos / max(1, total))}


def _esquecer(job):
    if not job:
        return
    with _PROG_MUTEX:
        _PROGRESSO.pop(job, None)


def legenda(corpo: dict) -> dict:
    """
    Assa um PEDAÇO do overlay (legenda + barra de progresso) pro preview.

    Em pedaços e não inteiro porque o vídeo todo leva minutos: assim só o
    trecho que você está vendo é pago, e mexer numa legenda invalida só o
    pedaço dela em vez dos 17 minutos.

    Lê o `edit_config.json` salvo — então legenda editada e não salva ainda
    aparece no preview antigo. É o preço de não subir 330 legendas a cada
    pedaço; salvar resolve.
    """
    from .overlay import render_overlay_mov

    cfg = json.loads((RAIZ / "public" / "edit_config.json").read_text(encoding="utf-8"))
    # O cliente manda o estado ATUAL (estilo + as legendas da janela). Sem isso
    # o preview só mudava depois de salvar, o que na prática era "o estilo da
    # legenda não muda". O disco fica só como base — duração, tamanho, fps.
    if corpo.get("estilo"):
        cfg.update({k: v for k, v in corpo["estilo"].items() if v is not None})
    if corpo.get("captions") is not None:
        cfg["captions"] = corpo["captions"]
    fps = float(cfg.get("fps", 30))
    idx = int(corpo.get("pedaco") or 0)
    ini_f = round(idx * JANELA_S * fps)
    n_total = round(float(cfg["videoDuration"]) * fps)
    n = min(round(JANELA_S * fps), n_total - ini_f)
    if n <= 0:
        return {"vazio": True}

    # A assinatura tem que cobrir tudo que muda o desenho: as legendas, o
    # estilo delas e a barra. Sem isso, editar uma legenda devolveria o
    # pedaço velho do cache.
    marca = json.dumps([
        cfg.get("captions"), cfg.get("showCaptions"), cfg.get("captionStyle"),
        cfg.get("captionFont"), cfg.get("captionFontSize"), cfg.get("captionColor"),
        cfg.get("captionHighlightColor"), cfg.get("captionKaraoke"),
        cfg.get("captionMaxLines"), cfg.get("captionWordGap"), cfg.get("captionLineGap"),
        cfg.get("captionX"), cfg.get("captionY"),
        cfg.get("showProgressBar"), cfg.get("barColor"), cfg.get("barHeight"),
        cfg.get("width"), cfg.get("height"), fps, idx,
    ], sort_keys=True, ensure_ascii=False)
    chave = hashlib.sha1(marca.encode()).hexdigest()[:16]
    destino = CACHE / f"l_{chave}.mp4"
    rel = f".preview_cache/l_{chave}.mp4"
    if destino.exists() and destino.stat().st_size > 1000:
        return {"src": rel, "cache": True, "inicio": ini_f / fps}

    with _TRAVAS_MUTEX:
        trava = _TRAVAS.setdefault(chave, threading.Lock())
    with trava:
        if destino.exists() and destino.stat().st_size > 1000:
            return {"src": rel, "cache": True, "inicio": ini_f / fps}
        CACHE.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        job = corpo.get("job")
        try:
            # Medido numa janela de 30s: 6,2s no total, mas o laço de quadros
            # é só ~1,5s disso. O resto é medir texto e calcular a faixa
            # (antes) e o ffmpeg fechar o arquivo (depois). Uma barra só de
            # quadros ficaria parada em 0% por 4 segundos e depois voaria —
            # por isso a FASE vai junto: o número diz quanto, a fase diz o quê.
            _marcar(job, 0, n, "preparando")
            render_overlay_mov(cfg, destino, registry=_registry(), codec="preview",
                               frame_ini=ini_f, n_frames=n,
                               progresso=lambda i, tot: _marcar(job, i, tot, "desenhando"))
            # o desenho acabou, mas o ffmpeg ainda esta fechando o arquivo —
            # dizer 100% aqui faria a barra encher e a legenda so aparecer
            # depois, que e a versao pior de nao ter barra
            _marcar(job, n, n, "codificando")
        except ValueError:
            # "nada pra desenhar": legenda desligada e barra desligada
            return {"vazio": True}
        except KeyError as e:
            # Estilo de legenda que o motor ainda nao desenha. O painel oferece
            # 13 e so 2 estao portados; sem esta resposta explicita a legenda
            # sumia da tela sem dizer por que.
            from .captions import ESTILOS
            return {"naoPortado": str(cfg.get("captionStyle")),
                    "portados": list(ESTILOS),
                    "error": f"estilo de legenda {cfg.get('captionStyle')!r} "
                             f"ainda nao portado ({e})"}
        print(f"[preview] legenda pedaco {idx} em {time.time()-t0:.1f}s", flush=True)
        _esquecer(job)
        return {"src": rel, "cache": False, "inicio": ini_f / fps,
                "segundos": round(time.time() - t0, 1)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):     # silencia o log por request
        pass

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/saude":
            return self._json(200, {"ok": True, "estilos": sorted(STYLES)})
        # /progresso?job=... — quanto da tira ja foi desenhada.
        # Precisa ser GET numa conexao PROPRIA: o POST da tira fica preso ate
        # o fim, entao perguntar por ele nunca responderia a tempo.
        if self.path.startswith("/progresso"):
            from urllib.parse import urlparse, parse_qs
            job = (parse_qs(urlparse(self.path).query).get("job") or [""])[0]
            with _PROG_MUTEX:
                p = _PROGRESSO.get(job)
            return self._json(200, p or {"fase": "ocioso"})
        self._json(404, {"error": "rota desconhecida"})

    def do_POST(self):
        if self.path not in ("/frame", "/clip", "/thumb", "/legenda", "/thumb-legenda"):
            return self._json(404, {"error": "rota desconhecida"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            corpo = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._json(400, {"error": f"corpo invalido: {e}"})

        if self.path == "/thumb-legenda":
            try:
                return self._json(200, miniatura_legenda(corpo))
            except KeyError as e:
                from .captions import ESTILOS
                return self._json(200, {"naoPortado": corpo.get("estilo"),
                                        "portados": list(ESTILOS), "error": str(e)})
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})

        if self.path == "/legenda":
            try:
                return self._json(200, legenda(corpo))
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})

        estilo = (corpo.get("title") or {}).get("style")
        if estilo not in STYLES:
            # Erro explícito em vez de quadro vazio: se o preview silenciasse
            # aqui, o estilo não portado apareceria como "título sumiu".
            return self._json(422, {"error": f"estilo {estilo!r} ainda nao portado",
                                    "portados": sorted(STYLES)})

        if self.path in ("/clip", "/thumb"):
            fn = assar if self.path == "/clip" else miniatura
            try:
                return self._json(200, fn(corpo))
            except Exception as e:
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})

        try:
            png = desenhar(corpo)
        except Exception as e:
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(png)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(png)


def main() -> int:
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 3011
    _registry()                      # paga a partida antes de aceitar request
    srv = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    print(f"[preview] MotionCore ouvindo em http://127.0.0.1:{porta}", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
