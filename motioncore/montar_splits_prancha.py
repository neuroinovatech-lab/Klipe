# -*- coding: utf-8 -*-
"""
montar_splits_prancha.py — split entre ela e a prancha, com fusao suave.

Mesma tecnica do projeto anterior: ela em cima, o desenho embaixo, e uma zona
de gradiente no meio pra nao existir linha de corte. Ela sobe um pouco pra
caber inteira na metade de cima — sem isso o split a cortaria no peito.

O material de baixo vem da METADE ESQUERDA do `prancha_overlay.mp4`: o overlay
e lado-a-lado (cor | alpha), entao a esquerda ja e a prancha achatada. Nas
janelas escolhidas o papel e opaco, entao nao falta nada.

    python -m motioncore.montar_splits_prancha
"""
from __future__ import annotations

import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PUB = RAIZ / "public"
PROJ = PUB / "projects" / "eli-prancha"
ELA = PUB / "projects" / "eli-premiere" / "video.mp4"
OVER = PROJ / "prancha_overlay.mp4"   # so pra checar que a prancha existe
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

W, H = 1080, 1920
ENTRADA = 960     # onde o desenho comeca — a metade exata
SUBIR = 300       # quanto ela sobe pra caber inteira em cima
FUSAO = 250       # altura da zona de gradiente
# de onde a faixa de baixo e recortada na folha. O centro do diagrama cai em
# y~840. Com 400 o recorte pegava a linha do titulo e "TEMPORAL" aparecia
# cortado ao meio, lendo como erro. 500 passa por baixo do titulo e ainda pega
# o diagrama inteiro.
FOCO = 500

# Janelas escolhidas: nenhuma colide com os seis cortes do OMNI, e em todas a
# prancha tem figura que justifica dividir a tela.
# Cada split usa um motion COMPOSTO pra faixa (montar_faixa.py), nao um
# recorte da prancha vertical. Recorte sempre comprometia: pegava margem vazia
# ou cortava titulo ao meio. Composicao espremida nao e composicao.
JANELAS = [
    (22.60, 26.60, "sensorial"),   # a grade de quadrados se formando
    # 45,60–48,40 caiu DENTRO da janela de imagem (35,60–48,60), onde o papel
    # sai e o overlay fica transparente — a metade de baixo veio preta. Split so
    # funciona onde a folha existe.
    (26.80, 30.80, "irregularidade"),  # o quadrado vermelho e o anel que o acha
    (50.60, 54.40, "dualidade"),   # a folha se dividindo — o tema e o proprio
]


def mascara(altura: int) -> Path:
    p = PROJ / f"feather_{altura}.png"
    if p.exists():
        return p
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-f", "lavfi",
         "-i", f"color=c=black:s={W}x{altura}",
         "-vf", f"format=gray,geq=lum='clip(Y*255/{FUSAO},0,255)'",
         "-frames:v", "1", str(p)], check=True)
    return p


def montar(ini: float, fim: float, nome: str) -> Path | None:
    alt = H - ENTRADA
    m = mascara(alt)
    saida = PROJ / f"split_{nome}.mp4"
    r = subprocess.run(
        [FFMPEG, "-y", "-v", "error",
         "-ss", f"{ini:.3f}", "-t", f"{fim-ini:.3f}", "-i", str(ELA),
         "-i", str(PROJ / f"faixa_{nome}.mp4"),
         "-i", str(m),
         "-filter_complex",
         # ela sobe: corta a partir de `SUBIR` e preenche o topo
         f"[0:v]crop={W}:{H-SUBIR}:0:{SUBIR},pad={W}:{H}:0:0:black,"
         f"eq=saturation=0.30:contrast=1.10,colorbalance=rs=0.16:bs=-0.12,"
         f"setpts=PTS-STARTPTS[cima];"
         # metade ESQUERDA do overlay = a prancha achatada; pega a faixa de baixo
         # ja vem no tamanho exato da faixa — nada de crop, nada de escala
         f"[1:v]setpts=PTS-STARTPTS[baixo];"
         "[2:v]format=gray[m];[baixo][m]alphamerge[ba];"
         f"[cima][ba]overlay=0:{ENTRADA}[v]",
         "-map", "[v]", "-an", "-c:v", "h264_nvenc", "-preset", "p5",
         "-cq", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         str(saida)], capture_output=True)
    if r.returncode or not saida.exists():
        print(f"  ! falhou {nome}: {r.stderr.decode('utf-8','ignore')[:160]}")
        return None
    print(f"  {nome:<12} {ini:6.2f}–{fim:5.2f}  {saida.stat().st_size/1e6:.1f} MB")
    return saida


def main() -> int:
    faltando = [n for _, _, n in JANELAS if not (PROJ / f"faixa_{n}.mp4").exists()]
    if faltando:
        raise SystemExit(f"faltam motions de faixa {faltando} — rode montar_faixa")
    PROJ.mkdir(parents=True, exist_ok=True)
    for ini, fim, nome in JANELAS:
        montar(ini, fim, nome)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
