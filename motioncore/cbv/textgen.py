# -*- coding: utf-8 -*-
"""textgen.py — a cena Text Generation do CreativlyBrandVideo.

Fundo claro (:146 `COLORS.bgWhite`) com a marca d'agua "GENERATE" em degrade
girando de -18 para -15 graus (:60-68), uma janela de navegador 1100x620 que
entra por mola em frame 8 (:71-78) e um LLM digitando o roteiro dentro dela.
A digitacao e o gesto central: no original e o `Typewriter` a 3 caracteres por
frame com pausa de 10 frames apos o 50o (:534-542); aqui cada linha e uma
camada com `revelar` correndo em LINEAR entre o instante do seu primeiro e do
seu ultimo caractere — mesma matematica, wipe no lugar do slice de string.
Fecha com as tres pilulas de modelo entrando defasadas 6 frames (:558-566) e a
regua de acento crescendo de 0 a 300 px no rodape (:600-624).
"""
from .base import *
import math

__all__ = ["cena"]

# ── CSS do .tsx -> coordenadas de camada (origem no centro, y para cima) ──
def lx(x: float) -> float:
    return x - W / 2


def ly(y: float) -> float:
    return H / 2 - y


def _mix(a: str, b: str, k: float) -> str:
    """Degrade de texto nao existe no motor: a cor sai interpolada por letra."""
    pa = [int(a[1 + 2 * i:3 + 2 * i], 16) for i in range(3)]
    pb = [int(b[1 + 2 * i:3 + 2 * i], 16) for i in range(3)]
    return "#" + "".join(f"{round(pa[i] + (pb[i] - pa[i]) * k):02X}" for i in range(3))


# Larguras MEDIDAS no proprio motor (mesmo TextBlock que desenha, Inter).
# `larg_texto()` erra ate 12% em frase minuscula, e como `x` de texto e o
# CENTRO do bloco, esse erro vira margem esquerda serrilhada num bloco de
# roteiro — que e exatamente o que a cena mostra em close.
MEDIDO = {
    "Certainly! Here is a script for a 30-second commercial:": 481.3,
    "[SCENE START]": 149.3,
    "INT. FUTURISTIC OFFICE - DAY": 296.3,
    "A young creative director sits at a holographic desk.": 456.9,
    "DIRECTOR": 104.1,
    "(To camera)": 106.7,
    "What if you could turn your wildest ideas into reality... instantly?": 559.9,
    "User:": 51.1,
    "Write a script for a 30s tech commercial": 350.8,
    "creativly.ai / ": 57.3,
    "LLM Screenplay Assistant": 126.6,
    "GPT-5": 43.5,
    "Claude Opus": 92.3,
    "Gemini": 51.0,
    "AI POWERED": 156.2,
}


def _w(txt: str, tam: float) -> float:
    return MEDIDO.get(txt) or larg_texto(txt, tam)


def luz(x: float, y: float, r: float, cor: str, t: float = 0.0,
        op: float = 0.35, s: int = 1) -> dict:
    """`brilho()` apaga em "#00000000" — em fundo CLARO isso passa pelo cinza
    e a mancha vira fumaca. Aqui a ponta transparente e a propria cor."""
    return {**brilho(x, y, r, cor, t, op, s),
            "cor": {"tipo": "radial", "cores": [cor, cor + "00"], "raio": r}}


def _rnd(i: int, k: int) -> float:
    """`random("spark-x-3")` do Remotion nao e portavel; o que importa e o
    espalhamento determinista."""
    return ((i * 2654435761 + k * 40503 + 12345) % 65536) / 65536.0


def _estrela(r: float, pontas: int = 4) -> str:
    """:224-228 — makeStar(points 4, innerRadius = 0.3 * outer)."""
    p = []
    for k in range(pontas * 2):
        a = -math.pi / 2 + k * math.pi / pontas
        rr = r if k % 2 == 0 else r * 0.3
        p.append(f"{rr * math.cos(a):.2f} {rr * math.sin(a):.2f}")
    return "M " + " L ".join(p) + " Z"


# ── a janela (:424-434): 1100x620, marginTop 160 num flex centrado ───────
BW, BH, CAB = 1100, 620, 44
B_ESQ, B_TOP = (W - BW) / 2, (H - (BH + 160)) / 2 + 160        # 410, 310
B_DIR, B_BASE = B_ESQ + BW, B_TOP + BH                         # 1510, 930
PAD = 50                                                        # :444
CONT_X, CONT_Y = B_ESQ + PAD, B_TOP + CAB + PAD                # 460, 404

# ── o texto gerado (:31-41) e o relogio do Typewriter (:534-542) ─────────
GERADO = (
    "Certainly! Here is a script for a 30-second commercial:\n"
    "\n"
    "[SCENE START]\n"
    "\n"
    "INT. FUTURISTIC OFFICE - DAY\n"
    "\n"
    "A young creative director sits at a holographic desk.\n"
    "\n"
    "DIRECTOR\n"
    "(To camera)\n"
    "What if you could turn your wildest ideas into reality... instantly?"
)
VEL, PAUSA_EM, PAUSA = 3.0, 50, 10        # speed / pauseAfter / pauseDuration
F0_DIGITA = 5 + 20 + 5                    # Sequence 5 + Sequence 20 + delay 5


def t_letra(n: int) -> float:
    p = n / VEL if n <= PAUSA_EM else PAUSA_EM / VEL + PAUSA + (n - PAUSA_EM) / VEL
    return (F0_DIGITA + p) * F


LINHAS = []
_i = 0
for _k, _ln in enumerate(GERADO.split("\n")):
    LINHAS.append((_k, _ln, _i, _i + len(_ln)))
    _i += len(_ln) + 1

# ── os sete diamantes flutuantes (:255-329): tamanho, x, y, vel, atraso ──
DIAMANTES = [
    (55, 100, 80, 0.7, 3, "#FFD6002E", True),
    (38, 1720, 120, 1.2, 10, "#FFD60024", True),
    (72, 160, 820, 0.5, 6, "#FFD6001A", True),
    (30, 1640, 780, 1.4, 16, "#FFD60038", False),
    (48, 920, 40, 0.9, 13, "#FFD6001F", True),
    (40, 60, 450, 0.6, 20, "#FFD60014", False),
    (25, 1780, 500, 1.1, 8, "#FFD60029", False),
]
MODELOS = ["GPT-5", "Claude Opus", "Gemini"]      # :558
N_FAISCA = 18            # :44 tem 24; 18 segura a cena na faixa de camadas


def cena(dur: float) -> dict:
    cs: list[dict] = []

    # ── marca d'agua "GENERATE" (:152-177) ────────────────────────────
    # 250px, italica, letterSpacing 20, degrade 135deg #3B82F6 -> #06B6D4,
    # opacidade 0->0.04 em 30 frames, rotacao -18 -> -15 em 60.
    palavra, tamw, espw = "GENERATE", 250, 20
    largs = [larg_char(c, tamw) for c in palavra]
    total = sum(largs) + espw * (len(palavra) - 1)
    ang = math.radians(-16.5)
    u = -total / 2
    rot = [[0.0, -18.0, "outCubic"], [2.0, -15.0]]
    for i, ch in enumerate(palavra):
        m = u + largs[i] / 2
        cs.append({**marca_dagua(ch, tamw, _mix(MARCA, CIANO, i / (len(palavra) - 1)),
                                 0.0, 0.06),
                   "espacamento": 0, "rotacao": rot,
                   "x": m * math.cos(ang), "y": -m * math.sin(ang)})
        u += largs[i] + espw

    # ── radial de acento (:202-214): 900x900, blur 80, a cor troca em ──
    # [0, 50, 105] entre brand -> brandDark -> brand. Como `cor` nao anima,
    # sao duas manchas cruzando por opacidade.
    cs.append({**luz(0, ly(432), 450, MARCA, 0.0, 0.10, 3), "blur": 60,
               "opacidade": [[0, 0, "outCubic"], [0.6, 0.11], [1.667, 0.02],
                             [3.5, 0.11]]})
    cs.append({**luz(0, ly(432), 450, MARCA_ESCURA, 0.0, 0.10, 4), "blur": 60,
               "opacidade": [[0, 0, "outCubic"], [0.6, 0.01], [1.667, 0.11],
                             [3.5, 0.01]]})

    # ── o brilho grande atras da janela (:180-199) ────────────────────
    # 1200x600 em top 55%/-30%, entrada por mola em frame 6, pulso de
    # opacidade 0.08-0.22 e de escala 0.92-1.08.
    cs.append({**luz(0, ly(714), 600, MARCA, 0.2, 0.18, 7), "escalaY": 0.5,
               "escala": pulso(1.0, 0.08, 0.007, 71)})
    cs.append({**luz(0, ly(714), 700, CIANO, 0.3, 0.10, 8), "escalaY": 0.45,
               "opacidade": pulso(0.10, 0.045, 0.02, 33), "inicio": 0.35})

    # ── faiscas: estrelas de 4 pontas girando (:217-252) ──────────────
    for i in range(N_FAISCA):
        s = _rnd(i, 3) * 5 + 2
        vel = _rnd(i, 4) * 0.5 + 0.3
        atr = _rnd(i, 5) * 40 * F
        cor = MARCA if i % 3 == 0 else (TEXTO_PRETO if i % 3 == 1 else MARCA_ESCURA)
        cs.append({
            "tipo": "path", "d": _estrela(s * 1.8), "centrar": False, "cor": cor,
            **viva(lx(_rnd(i, 1) * W), ly(_rnd(i, 2) * H), 14, 400 + i),
            "rotacao": [[0, 0, "linear"], [dur, dur * FPS * vel * 2]],
            "opacidade": pulso(0.17, 0.10, 0.03 * vel, 600 + i),
            "inicio": atr,
        })

    # ── os sete diamantes (:255-329) ──────────────────────────────────
    # rotateX/rotateY 3D viram rotacao no plano + esmagamento em escalaX:
    # o que o olho le do original e um losango tombando, e e isso que fica.
    for i, (tam, cx, cy, vel, atr, cor, tem_luz) in enumerate(DIAMANTES):
        x, y = lx(cx + tam / 2), ly(cy + tam / 2)
        t = atr * F
        if tem_luz:
            cs.append({**luz(x, y, tam * 1.6, MARCA, t, 0.22, 90 + i),
                       "blur": 18})
        cs.append({
            "tipo": "retangulo", "larg": tam, "alt": tam, "cor": cor,
            **viva(x, y, 12, 40 + i),
            "rotacao": [[0, 45, "linear"], [dur, 45 + dur * FPS * 1.5 * vel]],
            "escalaX": pulso(0.72, 0.28, 0.05, 200 + i),
            "escala": {"mola": MOLA_ESTADO, "em": t, "de": 0.0, "para": 1.0},
            "opacidade": [[t, 0], [t + 0.4, 0.8, "outCubic"]],
        })

    # ── cabecalho (:332-377): "Text" 30px italico + "GENERATION" 100px ─
    cs.append({**rotulo("Text", 0.0, ly(52), TEXTO_PRETO, 30, 0.0, 8, 700),
               "italico": True})
    cs += titulo("GENERATION", 3 * F, ly(115), 100, TEXTO_PRETO, 900, LETRA)

    # ── rotulo lateral girado -90 (:381-418) ──────────────────────────
    cs.append({"tipo": "texto", "texto": "AI POWERED", "tamanho": 14, "peso": 900,
               "cor": MARCA, "espacamento": 6, "rotacao": -90,
               **viva(lx(51), ly(432 - _w("AI POWERED", 14) / 2), 4, 77),
               "opacidade": [[0.5, 0], [0.85, 0.7, "outCubic"]]})
    cs.append({"tipo": "retangulo", "larg": 60, "alt": 2, "raio": 1,
               "rotacao": -90, "x": lx(66), "y": ly(402),
               "cor": {"tipo": "linear", "cores": [MARCA, CIANO],
                       "de": [-30, 0], "para": [30, 0]},
               "opacidade": [[0.5, 0], [0.85, 0.35, "outCubic"]]})

    # ── a janela (:436-441): sombra desenhada, chrome escuro, corpo branco ─
    tj = 8 * F
    yj = ly(B_TOP + BH / 2)
    cs += sombra(0, yj, BW, BH, tj, 16, 3)
    # o painel inteiro no tom do chrome: rgba(15,15,17,0.6) sobre #FAFAFA
    cs.append({**card(0, yj, BW, BH, tj, "#6D6D6E", "#FFFFFF40", 16, 11),
               "escala": {"mola": MOLA_ESTADO, "em": tj, "de": 0.88, "para": 1.0}})
    ycorpo = ly(B_TOP + CAB + (BH - CAB) / 2)
    cs.append({"tipo": "retangulo", "larg": BW, "alt": BH - CAB, "raio": 16,
               "cor": "#FFFFFF", **viva(0, ycorpo, 2.5, 11),
               "opacidade": entra(tj, 0.3)})
    cs.append({"tipo": "retangulo", "larg": BW, "alt": 26, "cor": "#FFFFFF",
               **viva(0, ly(B_TOP + CAB + 13), 2.5, 11),
               "opacidade": entra(tj, 0.3)})
    cs.append({"tipo": "linha", "de": [-BW / 2, 0], "para": [BW / 2, 0],
               "contorno": "#FFFFFF1A", "contorno_larg": 1,
               "x": 0, "y": ly(B_TOP + CAB), "opacidade": entra(tj, 0.3)})
    for i, cor in enumerate(("#FF5F56", "#FFBD2E", "#27C93F")):
        cs.append({"tipo": "elipse", "raio": 6, "cor": cor,
                   **viva(lx(B_ESQ + 26 + i * 20), ly(B_TOP + 22), 1.5, 60 + i),
                   "opacidade": entra(tj + i * F, 0.3)})
    # 20 de padding + 3 bolinhas de 12 com gap 8 (=52) + gap 16 do flex
    xpil, wpil = lx((B_ESQ + 88 + B_DIR - 20) / 2), (B_DIR - 20) - (B_ESQ + 88)
    cs.append({"tipo": "retangulo", "larg": wpil, "alt": 24, "raio": 6,
               "cor": "#00000030", "contorno": "#FFFFFF0D", "contorno_larg": 1,
               **viva(xpil, ly(B_TOP + 22), 1.5, 64), "opacidade": entra(tj, 0.3)})
    a, b = "creativly.ai / ", "LLM Screenplay Assistant"
    wa, wb = _w(a, 11), _w(b, 11)
    x0 = xpil - (wa + wb) / 2
    cs.append({"tipo": "texto", "texto": a, "tamanho": 11, "peso": 500,
               "cor": "#a1a1aa80", "x": x0 + wa / 2, "y": ly(B_TOP + 22),
               "opacidade": entra(tj + 0.1, 0.3)})
    cs.append({"tipo": "texto", "texto": b, "tamanho": 11, "peso": 500,
               "cor": TEXTO, "x": x0 + wa + wb / 2, "y": ly(B_TOP + 22),
               "opacidade": entra(tj + 0.1, 0.3)})

    # ── a linha do prompt do usuario (:454-483) ───────────────────────
    tp = 15 * F
    yp = ly(CONT_Y + 17)
    cs.append({**luz(lx(CONT_X + 17), yp, 30, MARCA, tp, 0.40, 88), "blur": 14})
    cs.append({
        "tipo": "elipse", "raio": 17, **viva(lx(CONT_X + 17), yp, 2, 88),
        "cor": {"tipo": "linear", "cores": [MARCA, CIANO],
                "de": [-17, -17], "para": [17, 17]},
        "opacidade": entra(tp, 0.3),
        "escala": {"mola": MOLA_DESTAQUE, "em": tp, "de": 0.4, "para": 1.0},
    })
    xu = CONT_X + 34 + 14
    wu = _w("User:", 20)
    cs.append({"tipo": "texto", "texto": "User:", "tamanho": 20, "peso": 600,
               "cor": TEXTO_PRETO, **viva(lx(xu + wu / 2), yp, 1.5, 91),
               "opacidade": entra(tp, 0.3)})
    frase = "Write a script for a 30s tech commercial"
    wf = _w(frase, 20)
    cs.append({"tipo": "texto", "texto": frase, "tamanho": 20, "peso": 400,
               "cor": MUDO_ESCURO,
               **viva(lx(xu + wu + 30 + wf / 2), yp, 1.5, 93),
               "opacidade": entra(tp + 3 * F, 0.3)})

    # ── a guia vertical que "cresce" enquanto o modelo digita (:495-532) ─
    # :84-89 — evolvePath de frame 20 a 80, outCubic. 580px no original;
    # aqui 440, que e o que cabe antes da base da janela (nao ha recorte).
    tl0, tl1 = (5 + 20) * F, (5 + 80) * F
    ytop, alt = CONT_Y + 66, 440
    cs.append({"tipo": "retangulo", "larg": 8, "alt": alt, "blur": 6,
               "x": lx(CONT_X), "y": ly(ytop + alt / 2),
               "cor": {"tipo": "linear",
                       "cores": ["#3B82F600", MARCA, "#3B82F600"],
                       "de": [0, -alt / 2], "para": [0, alt / 2]},
               "opacidade": pulso(0.32, 0.14, 0.03, 55),
               "revelar": {"prog": [[tl0, (W / 2 - alt / 2) / W, "outCubic"],
                                    [tl1, (W / 2 + alt / 2) / W]], "dir": "cima"}})
    cs.append({"tipo": "linha", "de": [0, 0], "para": [0, alt],
               "contorno": MARCA, "contorno_larg": 2.5,
               "x": lx(CONT_X), "y": ly(ytop), "opacidade": 0.5,
               "traco": [[tl0, 0.0, "outCubic"], [tl1, 1.0]]})

    # ── a resposta digitada: uma camada por linha, `revelar` em LINEAR ──
    xesq = CONT_X + 44
    for k, ln, ini, fim in LINHAS:
        if not ln.strip():
            continue
        w = _w(ln, 20)
        t0, t1 = t_letra(ini), t_letra(fim)
        cs.append({
            "tipo": "texto", "texto": ln, "tamanho": 20, "peso": 400,
            "cor": TEXTO_PRETO, "entrelinha": 1.0,
            "x": lx(xesq + w / 2), "y": ly(CONT_Y + 66 + 16 + k * 32),
            "inicio": t0,
            "revelar": [[t0, (W / 2 - w / 2 - 5) / W, "linear"],
                        [t1, (W / 2 + w / 2 + 5) / W]],
        })

    # ── o cursor, que persegue o fim do texto (:545-556) ──────────────
    kx, ky, ant = [], [], -1.0
    for k, ln, ini, fim in LINHAS:
        if not ln.strip():
            continue
        w = _w(ln, 20)
        y = ly(CONT_Y + 66 + 16 + k * 32) - 2
        for t, xv in ((max(t_letra(ini), ant + 1e-3), xesq + 4),
                      (t_letra(fim), xesq + w + 4)):
            t = max(t, ant + 1e-3)
            kx.append([t, lx(xv), "linear"])
            ky.append([t, y, "linear"])
            ant = t
    cs.append({"tipo": "retangulo", "larg": 3, "alt": 20, "cor": MARCA,
               "x": kx, "y": ky, "inicio": kx[0][0],
               "opacidade": entra(kx[0][0], 0.1)})

    # ── as tres pilulas de modelo (:548-593) ──────────────────────────
    tam = 14
    ws = [_w(m, tam) + 40 for m in MODELOS]
    xb = (B_DIR - 30) - (sum(ws) + 32)
    yb = ly(B_BASE - 30 - 19)
    for i, m in enumerate(MODELOS):
        t = (45 + i * 6) * F
        xc = lx(xb + ws[i] / 2)
        cs.append({
            "tipo": "retangulo", "larg": ws[i], "alt": 38, "raio": 10,
            "cor": {"tipo": "linear", "cores": ["#FFFDF2", "#FFFFFF", "#FFFCEF"],
                    "de": [-ws[i] / 2, -19], "para": [ws[i] / 2, 19]},
            "contorno": "#3B82F64D", "contorno_larg": 1.5,
            **viva(xc, yb, 2, 700 + i), "opacidade": entra(t, 0.3),
            "escala": {"mola": MOLA_TEXTO, "em": t, "de": 0.5, "para": 1.0},
        })
        cs.append({"tipo": "texto", "texto": m, "tamanho": tam, "peso": 700,
                   "cor": TEXTO_PRETO, "espacamento": 0.5,
                   **viva(xc, yb, 2, 700 + i), "opacidade": entra(t, 0.3)})
        xb += ws[i] + 16

    # ── a regua de acento no rodape (:600-624): 0 -> 300 px, mola ─────
    cs.append({"tipo": "retangulo", "alt": 3, "raio": 2, "y": ly(H - 60 - 1.5),
               "larg": {"mola": {"damping": 20, "stiffness": 80}, "em": 12 * F,
                        "de": 0.0, "para": 300.0},
               "cor": {"tipo": "linear",
                       "cores": ["#3B82F600", MARCA, CIANO, "#06B6D400"],
                       "paradas": [0.0, 0.35, 0.65, 1.0],
                       "de": [-150, 0], "para": [150, 0]},
               "opacidade": [[12 * F, 0], [12 * F + 0.5, 0.6, "outCubic"]]})

    return {"duracao": dur, "fundo": BG_BRANCO, "camadas": cs}
