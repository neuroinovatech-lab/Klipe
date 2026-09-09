"""
merge_titles.py — junta os MOVs de título num só, antes do composite.

O composite paga caro por ENTRADA, não por operação. Medido em 60s do material
real: um overlay alpha custa +0,4s; o zoom dinâmico custa +0,6s. Mas os 44
títulos entrando como 44 entradas separadas custam ~3,3 min no vídeo inteiro,
porque cada um abre um decoder próprio e o filter_complex vira uma corrente de
44 `overlay` encadeados (20 mil caracteres).

Aqui eles viram UM arquivo de comprimento total, e o composite passa a ver uma
entrada em vez de 44.

O truque é não re-codificar nada. Como os títulos não se sobrepõem no tempo, dá
pra montar a fita com `concat` em modo cópia: os buracos entre um título e outro
são pedaços de um arquivo transparente gerado uma vez. QTRLE é todo
intra-quadro, então todo frame é chave e o corte cai exato em qualquer ponto —
sem re-encode, sem perda, e o custo vira basicamente cópia de bytes.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

# Resolvido em tempo de execucao (env > Configuracoes > C:/ffmpeg > PATH):
# cravar o caminho aqui fazia o render morrer em qualquer maquina que nao
# fosse a de quem escreveu. Ver motioncore/ffbin.py.
from .ffbin import ffmpeg as _ffmpeg
FFMPEG = _ffmpeg()


def _frames(path: Path, ffmpeg: str) -> int | None:
    """Quantos frames tem o MOV — precisa ser exato pra fita não desalinhar."""
    ffprobe = str(Path(ffmpeg).with_name(Path(ffmpeg).name.replace("ffmpeg", "ffprobe")))
    r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0",
                        "-count_packets", "-show_entries", "stream=nb_read_packets",
                        "-of", "json", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return int(json.loads(r.stdout)["streams"][0]["nb_read_packets"])
    except Exception:
        return None


def _e_transparente(mov: Path, ffmpeg: str) -> bool:
    """
    O preenchimento e mesmo transparente?

    Vale conferir em vez de confiar: um preenchimento opaco nao quebra o
    render, nao dá erro nenhum — só apaga o video calado nos trechos sem
    titulo. Foi exatamente o que aconteceu, e so apareceu quando o video foi
    assistido.
    """
    r = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(mov),
         "-vframes", "1", "-vf", "format=rgba,alphaextract",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return False
    return max(r.stdout) < 8


def merge(titulos: list[tuple[Path, float, float]], destino: Path,
          width: int, height: int, fps: float, duracao: float,
          ffmpeg: str = FFMPEG, log=print) -> Path | None:
    """
    `titulos` = [(caminho, startSec, endSec)] — a mesma lista que o composite
    receberia. Devolve o MOV único, ou None se não der (aí o chamador segue
    com as entradas separadas, que continuam funcionando).
    """
    if len(titulos) < 2:
        return None

    t0 = time.time()
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.parent / "_merge"
    tmp.mkdir(exist_ok=True)
    total_frames = round(duracao * fps)

    # ordena por tempo e descarta sobreposição (a fita é sequencial: dois
    # títulos ao mesmo tempo não cabem num arquivo só)
    itens = sorted(titulos, key=lambda x: x[1])
    fita: list[tuple[Path, int, int]] = []      # (arquivo, frame_inicial, n_frames)
    cursor = 0
    sobrepostos = 0
    for caminho, ini, _fim in itens:
        n = _frames(Path(caminho), ffmpeg)
        if not n:
            log(f"    merge: nao consegui contar frames de {Path(caminho).name} — abortando")
            return None
        f_ini = round(float(ini) * fps)
        if f_ini < cursor:
            sobrepostos += 1
            continue
        fita.append((Path(caminho), f_ini, n))
        cursor = f_ini + n
    if sobrepostos:
        log(f"    merge: {sobrepostos} titulo(s) sobrepostos ficam como entrada separada")
    if not fita:
        return None
    if cursor > total_frames:
        total_frames = cursor

    # um arquivo transparente serve de recheio pra TODOS os buracos
    maior_buraco = 0
    pos = 0
    for _, f_ini, n in fita:
        maior_buraco = max(maior_buraco, f_ini - pos)
        pos = f_ini + n
    maior_buraco = max(maior_buraco, total_frames - pos)

    vazio = tmp / "vazio.mov"
    if maior_buraco > 0:
        # `format=argb` NAO e opcional. O `color` sai num formato SEM canal
        # alpha; sem forcar aqui, o ffmpeg converte pra argb na gravacao e
        # preenche o alpha com 255 — o "transparente" vira PRETO OPACO e tapa o
        # video em todo trecho sem titulo.
        r = subprocess.run(
            [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i",
             f"color=c=black@0:s={width}x{height}:r={fps}:"
             f"d={maior_buraco/fps + 1:.3f},format=argb",
             "-c:v", "qtrle", "-pix_fmt", "argb", str(vazio)],
            capture_output=True, text=True)
        if r.returncode != 0 or not vazio.exists():
            log("    merge: nao consegui gerar o preenchimento transparente")
            return None
        # confere que saiu transparente mesmo, em vez de confiar
        if not _e_transparente(vazio, ffmpeg):
            log("    merge: o preenchimento saiu OPACO — abortando o merge")
            return None

    # lista do concat: recheio, titulo, recheio, titulo...
    linhas, pos = [], 0
    def _bloco(arq: Path, nframes: int):
        linhas.append(f"file '{arq.as_posix()}'")
        linhas.append("inpoint 0")
        linhas.append(f"outpoint {nframes / fps:.6f}")

    for caminho, f_ini, n in fita:
        if f_ini > pos:
            _bloco(vazio, f_ini - pos)
        _bloco(caminho, n)
        pos = f_ini + n
    if total_frames > pos:
        _bloco(vazio, total_frames - pos)

    lista = tmp / "fita.txt"
    lista.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    # `-c copy`: sem re-encode. QTRLE e todo intra, entao cortar em qualquer
    # frame e legitimo e o custo e copia de bytes.
    r = subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", str(lista),
         "-c", "copy", str(destino)],
        capture_output=True, text=True)
    if r.returncode != 0 or not destino.exists() or destino.stat().st_size < 1000:
        erro = (r.stderr or "").strip().splitlines()
        log(f"    merge: concat falhou ({erro[-1][:120] if erro else '?'})")
        return None

    dt = time.time() - t0
    log(f"    merge: {len(fita)} titulos -> 1 arquivo em {dt:.1f}s "
        f"({destino.stat().st_size/1e6:.0f} MB, sem re-encode)")
    return destino


def limpar_cache_morto(cache_base: Path, hashes_vivos: set[str], log=print) -> float:
    """
    Apaga overlays de renders antigos.

    Cada render com config diferente cria uma pasta com hash novo, e a antiga
    nunca era removida. Achei 2,48 GB de overlay morto de 3 renders anteriores
    contra 0,12 GB de cache util.
    """
    liberado = 0.0
    for d in cache_base.iterdir():
        if not d.is_dir() or d.name == "titles_indiv" or d.name in hashes_vivos:
            continue
        try:
            tam = sum(p.stat().st_size for p in d.rglob("*") if p.is_file())
            import shutil
            shutil.rmtree(d, ignore_errors=True)
            if not d.exists():
                liberado += tam
        except Exception:
            continue
    if liberado:
        log(f"  Cache: {liberado/1e9:.2f} GB de overlays antigos removidos")
    return liberado
