# -*- coding: utf-8 -*-
"""gpu.py — rasterizar na placa de video, com queda limpa pra CPU.

POR QUE
  Perfil de uma cena de 284 camadas em 1920x1080:

      avaliar (Python)     0.8%
      pintar  (Skia)      99.2%   —  346 us por camada-frame

  e dentro do pintar, UMA elipse de raio 980 custava 92,5% do frame. Nao era o
  degrade: o mesmo circulo com cor chapada custava ainda mais. E AREA — tres
  milhoes de pixels com antialias, a ~100 M pixel/s de CPU.

  Encher pixel e exatamente o que uma GPU faz. Medido nesta maquina, mesma
  cena, mesmos 120 frames:

      CPU   12,24 s   =    9,8 fps
      GPU    0,78 s   =  154,8 fps        15,8x

  A leitura de volta (GPU -> CPU, que o ffmpeg exige) custa 3 ms por frame —
  0,37 s dos 0,78. Nao e gargalo.

E O DESENHO MUDA?
  Quase nada, e nao muda de forma estrutural. Comparado pixel a pixel contra a
  CPU em quatro cenas:

      diferenca media   0,20 a 0,46  de 255
      pixels > 2/255    0,14% a 3,2% do quadro

  Sao as bordas de letra e de traco fino, onde o antialias da GPU e o da CPU
  discordam por um nivel. Ampliei 3x e nao da pra distinguir. (Comparacao util:
  uma otimizacao que eu tentei antes desta dava 3,6 de media E uma borda dura
  visivel num disco de fundo. Aquela foi revertida; esta nao tem artefato.)

  MSAA nao ajuda: com 4 amostras a diferenca AUMENTA de leve e o custo sobe.
  Fica em 0.

QUANDO NAO DA
  Maquina sem OpenGL, sem `glfw` instalado, sessao remota sem aceleracao. Nesse
  caso `superficie()` devolve a de CPU e o render sai igual, so mais devagar —
  a unica coisa que nao pode acontecer e o video nao sair.
"""
from __future__ import annotations

import os
import threading

import skia

_ctx = None
_janela = None
_estado = "nao tentado"
_thread = None


def _abrir():
    """Abre UMA vez o contexto de GL. Falhar aqui nao e erro: e CPU."""
    global _ctx, _janela, _estado, _thread
    if _estado != "nao tentado":
        return _ctx
    if os.environ.get("KLIPE_SEM_GPU"):
        _estado = "desligada por KLIPE_SEM_GPU"
        return None
    try:
        import glfw
        if not glfw.init():
            _estado = "glfw nao iniciou"
            return None
        # Janela OCULTA: o contexto de GL precisa de uma superficie de janela,
        # mas ninguem precisa ver. `STENCIL_BITS` porque o Skia usa stencil pra
        # recorte de path — sem isso ele cai pra caminhos mais lentos.
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        glfw.window_hint(glfw.STENCIL_BITS, 8)
        _janela = glfw.create_window(64, 64, "klipe", None, None)
        if not _janela:
            _estado = "nao criou janela"
            return None
        glfw.make_context_current(_janela)
        _ctx = skia.GrDirectContext.MakeGL()
        # Contexto de GL pertence a UMA thread. Guardar qual e o que impede o
        # modo de falha pior que existe aqui: usar de outra thread nao levanta
        # excecao — desenha errado, ou nao desenha, calado.
        _thread = threading.get_ident()
        _estado = "ligada" if _ctx else "MakeGL devolveu None"
    except ImportError:
        _estado = "glfw nao instalado"
    except Exception as e:
        _estado = f"{type(e).__name__}: {e}"
    return _ctx


def superficie(w: int, h: int):
    """Devolve `(surface, fechar_frame)`.

    `fechar_frame()` empurra os comandos pra placa antes de ler os pixels. Na
    CPU ele nao faz nada, entao quem chama trata os dois casos igual — o laco
    de render nao precisa saber onde esta desenhando.
    """
    ctx = _abrir()
    if ctx is not None and threading.get_ident() != _thread:
        # `preview_server.py` e um ThreadingHTTPServer: cada requisicao vem numa
        # thread nova. Sem esta recusa, ligar a GPU la daria corrupcao
        # silenciosa. Aqui ele so cai pra CPU, que e o certo.
        return skia.Surface(w, h), (lambda: None)
    if ctx is not None:
        info = skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType,
                                   skia.kPremul_AlphaType)
        try:
            s = skia.Surface.MakeRenderTarget(
                ctx, skia.Budgeted.kNo, info, 0,
                skia.kBottomLeft_GrSurfaceOrigin, None, False)
            if s is not None:
                return s, ctx.flushAndSubmit
        except Exception as e:
            globals()["_estado"] = f"MakeRenderTarget: {type(e).__name__}"
    return skia.Surface(w, h), (lambda: None)


def onde() -> str:
    """Pra quem renderiza poder DIZER onde desenhou. Render que fica lento sem
    explicacao vira suspeita de bug; dizendo 'CPU, glfw nao instalado' vira uma
    linha de instalacao."""
    _abrir()
    if _ctx is None:
        return f"CPU ({_estado})"
    if threading.get_ident() != _thread:
        return "CPU (contexto de GL e de outra thread)"
    return "GPU"
