"""
overlay.py — o overlay de VIDEO INTEIRO (legenda + barra) sem motor de navegador.

Esse e o alvo grande do MotionCore. Titulo e pontual: dura 4 s, some. Legenda
acompanha o video do comeco ao fim — num video de 18 min sao ~930 s de render monolitico por navegador, mais que todo o resto do render somado.

O problema de renderizar overlay de video inteiro nao e desenhar, e a vazao:
frame RGBA de 1080x1920 tem 8,3 MB. Um video de 18 min a 30 fps dariam 270 GB
so passando pelo cano.

A saida e que o overlay e quase todo transparente. O conteudo mora em duas
tiras: a barra de progresso no topo (5 px) e a legenda embaixo (~25% da tela).
Entao a gente desenha e transporta SO as tiras, e o ffmpeg recompoe o frame
cheio com `pad` + `overlay` do outro lado do cano. Mesmo MOV de saida que o
motor de navegador entregava — o composite nao muda em nada.

Cada tira tem assinatura propria: quando so a legenda muda, a barra nao e
redesenhada, e vice-versa. Quando nenhuma muda, o frame inteiro e reaproveitado.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import numpy as np
import skia

from .captions import CaptionRenderer
from .fonts import FontRegistry
from .text import css_color

# Resolvido em tempo de execucao (env > Configuracoes > C:/ffmpeg > PATH):
# cravar o caminho aqui fazia o render morrer em qualquer maquina que nao
# fosse a de quem escreveu. Ver motioncore/ffbin.py.
from .ffbin import ffmpeg as _ffmpeg
FFMPEG = _ffmpeg()


class BarraProgresso:
    """
    Porta do `ProgressBar` (o template antigo ~5799). No TitlesOverlay ela
    entra com `top=0`.

    A largura do preenchimento e arredondada pra MEIO PIXEL, e isso e o que
    torna o overlay barato.

    O comentario antigo dizia 1/20 de pixel mas o codigo arredondava a 1/100.
    Num video de 12 min a barra cresce 0,09 px por frame — mais que 0,01 —
    entao ela mudava em TODO frame, marcava o cano inteiro como sujo e a
    legenda (que fica parada entre uma palavra e outra) nunca era
    reaproveitada: 22.200 frames, 0 repetidos.

    Meio pixel de quantizacao muda a barra a cada ~6 frames. O desvio maximo e
    0,25 px na ponta de uma barra de 5 px de altura — invisivel — e libera o
    reaproveitamento dos frames em que so a legenda importa.
    """
    QUANTIZACAO = 0.5

    def __init__(self, cfg: dict, width: int, height: int, duration_frames: int):
        self.w = width
        self.altura = int(cfg.get("barHeight", 6))
        self.cor = cfg.get("barColor", "#FF6B00")
        self.total = max(1, duration_frames)
        self.y0, self.y1 = 0, self.altura

    def _largura(self, frame: float) -> float:
        q = self.QUANTIZACAO
        return round(self.w * (frame / self.total) / q) * q

    def signature(self, frame: float):
        return ("barra", self._largura(frame))

    def draw(self, canvas: skia.Canvas, frame: float):
        fundo = skia.Paint(AntiAlias=True, Color=css_color("rgba(255,255,255,0.08)"))
        canvas.drawRect(skia.Rect.MakeXYWH(0, 0, self.w, self.altura), fundo)

        larg = self._largura(frame)
        if larg <= 0:
            return
        r = max(1.0, self.altura / 2.0)
        # cantos arredondados so na ponta direita (`border-radius: 0 r r 0`)
        rrect = skia.RRect()
        rrect.setRectRadii(skia.Rect.MakeXYWH(0, 0, larg, self.altura),
                           [skia.Point(0, 0), skia.Point(r, r),
                            skia.Point(r, r), skia.Point(0, 0)])

        # `box-shadow: 0 0 12px cor99, 0 0 4px corcc` — sombra da CAIXA, atras dela
        for blur, alpha_hex in ((12, "99"), (4, "cc")):
            p = skia.Paint(AntiAlias=True, Color=css_color(self.cor + alpha_hex))
            p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur / 2.0))
            canvas.drawRRect(rrect, p)

        # `linear-gradient(90deg, cor, cordd)`
        p = skia.Paint(AntiAlias=True)
        p.setShader(skia.GradientShader.MakeLinear(
            points=[(0, 0), (larg, 0)],
            colors=[css_color(self.cor), css_color(self.cor + "dd")]))
        canvas.drawRRect(rrect, p)


class FaixaLegenda:
    """Adapta o CaptionRenderer pro protocolo de tira."""

    def __init__(self, renderer: CaptionRenderer):
        self.r = renderer
        self.y0, self.y1 = renderer.band()

    @property
    def altura(self):
        return self.y1 - self.y0

    def signature(self, frame: float):
        return self.r.signature(frame)

    def draw(self, canvas: skia.Canvas, frame: float):
        self.r.draw_frame(canvas, frame)


def montar_tiras(cfg: dict, width: int, height: int, fps: float,
                 duration_frames: int, registry: FontRegistry | None = None,
                 com_legendas: bool = True):
    """Devolve as tiras com conteudo, de cima pra baixo."""
    tiras = []
    if bool(cfg.get("showProgressBar", True)):
        barra = BarraProgresso(cfg, width, height, duration_frames)
        if barra.altura > 0:
            tiras.append(barra)

    quer_legenda = (com_legendas and bool(cfg.get("showCaptions", True))
                    and len(cfg.get("captions") or []) > 0)
    if quer_legenda:
        faixa = FaixaLegenda(CaptionRenderer(cfg, width, height, fps, registry))
        if faixa.altura > 0:
            tiras.append(faixa)

    tiras.sort(key=lambda t: t.y0)
    return tiras


def draw_overlay_frame(canvas: skia.Canvas, tiras, frame: float):
    """
    Desenha as tiras nas posicoes ABSOLUTAS do frame cheio.

    E assim que a paridade compara com o still do motor de navegador: o render de
    verdade transporta so as tiras, mas o resultado tem que ser o mesmo frame.
    """
    for t in tiras:
        canvas.save()
        canvas.clipRect(skia.Rect.MakeXYWH(0, t.y0, canvas.getBaseLayerSize().width(),
                                           t.altura))
        t.draw(canvas, frame)
        canvas.restore()


def _filtro_recompoe(tiras, width: int, height: int) -> str:
    """
    Monta o filter_complex que devolve as tiras pro frame cheio.

    O cano carrega as tiras empilhadas; aqui cada uma volta pra sua altura
    original com `pad` e todas se somam com `overlay`.
    """
    partes = []
    n = len(tiras)
    if n == 1:
        t = tiras[0]
        return (f"[0:v]unpremultiply=inplace=1,"
                f"pad={width}:{height}:0:{t.y0}:color=black@0[v]")

    partes.append(f"[0:v]unpremultiply=inplace=1,split={n}"
                  + "".join(f"[s{i}]" for i in range(n)) + ";")
    off = 0
    for i, t in enumerate(tiras):
        partes.append(f"[s{i}]crop={width}:{t.altura}:0:{off},"
                      f"pad={width}:{height}:0:{t.y0}:color=black@0[p{i}];")
        off += t.altura
    ent = "[p0]"
    for i in range(1, n):
        saida = "[v]" if i == n - 1 else f"[m{i}]"
        partes.append(f"{ent}[p{i}]overlay=0:0:format=auto{saida};")
        ent = saida
    return "".join(partes).rstrip(";")


def _sufixo_codec(codec: str, width: int, height: int) -> str:
    """O que entra DEPOIS do recompoe, antes de gravar."""
    if codec == "qtrle":
        return ""
    if codec == "preview":
        # mesmo empacotamento dos titulos: cor a esquerda, alpha em cinza a
        # direita, porque <video> em H.264 nao carrega canal alpha. O
        # `format=rgba` antes do split nao e opcional — sem ele o
        # alphaextract falha com "Requested planes not available".
        w, h = max(2, (width // 2) // 2 * 2), max(2, (height // 2) // 2 * 2)
        return (f";[v]scale={w}:{h},format=rgba,split=2[pc][pa];"
                f"[pc]format=yuv420p[pcc];[pa]alphaextract,format=yuv420p[paa];"
                f"[pcc][paa]hstack=inputs=2[vp]")
    raise ValueError(f"codec desconhecido: {codec!r}")


def _flags_codec(codec: str) -> list[str]:
    if codec == "qtrle":
        return ["-c:v", "qtrle", "-pix_fmt", "argb"]
    if codec == "preview":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "26",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    raise ValueError(f"codec desconhecido: {codec!r}")


def render_overlay_mov(cfg: dict, out_path: str | Path, ffmpeg: str = FFMPEG,
                       registry: FontRegistry | None = None,
                       com_legendas: bool = True, loglevel: str = "error",
                       codec: str = "qtrle", frame_ini: int = 0,
                       n_frames: int | None = None,
                       progresso=None) -> dict:
    """
    Renderiza o overlay (legenda + barra) num arquivo com alpha.

    codec="qtrle" (padrao): MOV do video inteiro, o que o composite do render
    final consome — identico ao monolitico que O motor de navegador produzia.

    codec="preview" + janela: H.264 com cor e alpha lado a lado, pro <video>
    do preview. A janela existe porque assar o video inteiro leva minutos; em
    pedacos de 30s cada um sai em segundos, so o pedaco que voce esta vendo e
    pago, e editar uma legenda invalida so o pedaco dela.
    """
    t0 = time.time()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    width = int(cfg.get("width", 1080))
    height = int(cfg.get("height", 1920))
    fps = float(cfg.get("fps", 30))
    n_total = round(float(cfg["videoDuration"]) * fps)
    n = n_total if n_frames is None else min(int(n_frames), n_total - frame_ini)
    if n <= 0:
        raise ValueError("janela vazia")

    # As tiras medem a partir do video INTEIRO (a barra de progresso precisa
    # saber a duracao total pra saber onde esta), entao passa n_total aqui e
    # a janela e aplicada so no laco de frames.
    tiras = montar_tiras(cfg, width, height, fps, n_total, registry, com_legendas)
    if not tiras:
        raise ValueError("nada pra desenhar no overlay (sem legenda e sem barra)")

    altura_cano = sum(t.altura for t in tiras)
    proc = subprocess.Popen(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", loglevel,
         "-f", "rawvideo", "-pixel_format", "rgba",
         "-video_size", f"{width}x{altura_cano}", "-framerate", str(fps),
         "-i", "-",
         "-filter_complex", _filtro_recompoe(tiras, width, height) + _sufixo_codec(codec, width, height),
         "-map", "[vp]" if codec == "preview" else "[v]",
         "-an", *_flags_codec(codec), str(out_path)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    surface = skia.Surface(width, altura_cano)
    canvas = surface.getCanvas()
    buf = np.empty((altura_cano, width, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(width, altura_cano, skia.kRGBA_8888_ColorType,
                               skia.kPremul_AlphaType)
    transparente = skia.Color4f(0, 0, 0, 0)

    # offset de cada tira dentro do canvas do cano
    offs, acc = [], 0
    for t in tiras:
        offs.append(acc)
        acc += t.altura

    sigs = [object()] * len(tiras)
    bytes_ant = None
    repetidos = 0
    try:
        for f in range(frame_ini, frame_ini + n):
            # `progresso` e opcional de proposito: quem desenha nao precisa
            # saber que existe um servidor esperando. Sem callback, nada muda.
            # A cada 15 quadros (meio segundo) — chamar a cada quadro so
            # gastaria tempo no que a pessoa nem consegue enxergar.
            if progresso is not None and (f - frame_ini) % 15 == 0:
                progresso(f - frame_ini, n)
            sujas = []
            for i, t in enumerate(tiras):
                s = t.signature(f)
                if s != sigs[i]:
                    sigs[i] = s
                    sujas.append(i)

            if not sujas and bytes_ant is not None:
                proc.stdin.write(bytes_ant)
                repetidos += 1
                continue

            for i in sujas:
                t, off = tiras[i], offs[i]
                canvas.save()
                canvas.clipRect(skia.Rect.MakeXYWH(0, off, width, t.altura))
                # so a tira suja e limpa e redesenhada; as outras ficam como
                # estavam no frame anterior
                canvas.clear(transparente)
                canvas.translate(0, off - t.y0)
                t.draw(canvas, f)
                canvas.restore()

            surface.readPixels(info, buf, width * 4, 0, 0)
            bytes_ant = buf.tobytes()
            proc.stdin.write(bytes_ant)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    except Exception:
        proc.kill()
        raise

    _, err = proc.communicate(timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg saiu {proc.returncode}: "
                           f"{err.decode(errors='replace')[-800:]}")
    if not out_path.exists() or out_path.stat().st_size <= 1000:
        raise RuntimeError("MOV do overlay saiu vazio")

    dt = time.time() - t0
    return {"frames": n, "frame_ini": frame_ini, "seconds": round(dt, 2),
            "fps_render": round(n / dt, 1) if dt else 0.0,
            "repetidos": repetidos,
            "tiras": [(t.__class__.__name__, t.y0, t.y1) for t in tiras],
            "altura_cano": altura_cano,
            "size_mb": round(out_path.stat().st_size / 1e6, 2)}


# ─── CLI ────────────────────────────────────────────────────────────────
# Existe para o export do DaVinci, que precisa do overlay em PEDACOS (um MOV
# por segmento da linha do tempo) e rodava isso spawnando `npx motor de navegador render
# TitlesOverlay`. A funcao acima ja sabia fazer janela de frames desde que o
# preview foi escrito; faltava so uma porta de entrada por linha de comando.
#
#   python -m motioncore.overlay config.json saida.mov --frame-ini 300 --frames 150
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Overlay com alpha (legenda + titulos).")
    ap.add_argument("config", help="edit_config.json do projeto")
    ap.add_argument("saida", help="arquivo .mov de saida")
    ap.add_argument("--frame-ini", type=int, default=0)
    ap.add_argument("--frames", type=int, default=None,
                    help="quantos frames a partir do inicio; vazio = ate o fim")
    ap.add_argument("--sem-legendas", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    m = render_overlay_mov(cfg, args.saida,
                           com_legendas=not args.sem_legendas,
                           frame_ini=args.frame_ini,
                           n_frames=args.frames)
    # Uma linha de JSON no stdout: quem chamou le sem precisar interpretar log.
    print(json.dumps(m, default=str))
