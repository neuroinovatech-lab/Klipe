#!/usr/bin/env python3
"""
ForgeRender Lite — Motor de render GPU end-to-end do Klipe (NLE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

(Pasta historica: motionforge/. Sistema renomeado para Klipe — pasta legado.)

Arquitetura:
  1. Reusa o motor de navegador pra renderizar overlays alpha (TitlesOverlay + BrollsOverlay)
     em PARALELO. Cache por hash do edit_config.
  2. Audio mix completo via ffmpeg (source voice + 87 SFX + 5 music tracks).
  3. Composite final via ffmpeg + h264_nvenc (NVENC GPU).

Performance esperada:
  - Cold start (overlays nao cached): ~4-5 min
  - Cache hit (overlays existem): ~1 min
  - vs Klipe direto atual: 12min39s

Uso:
  python forge_render.py [--out NAME] [--no-cache] [--audio-from-source]
  python forge_render.py --out final.mp4
  python forge_render.py --out preview.mp4 --no-cache
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
OUTPUT = ROOT / "output"
EDIT_CONFIG = PUBLIC / "edit_config.json"
# Resolvido em tempo de execucao (env > Configuracoes > C:/ffmpeg > PATH):
# cravar o caminho aqui fazia o render morrer em qualquer maquina que nao
# fosse a de quem escreveu. Ver motioncore/ffbin.py.
from motioncore.ffbin import ffmpeg as _ffmpeg
FFMPEG_EXTERNAL = _ffmpeg()
CACHE_BASE = OUTPUT / ".forge_cache"

OUTPUT.mkdir(exist_ok=True)
CACHE_BASE.mkdir(exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def log(msg, end="\n"):
    """Log com timestamp + flush imediato pra logs em pipe."""
    print(f"[ForgeRender] {msg}", end=end, flush=True)


def cfg_hash(cfg, force_no_captions=False):
    """Hash deterministico das overlay_props (TODAS as flags + arrays que vao pro motor de navegador)."""
    props = build_overlay_props(cfg, force_no_captions=force_no_captions)
    payload = {
        "props": props,
        "videoDuration": cfg.get("videoDuration"),
        "fps": cfg.get("fps"),
    }
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def build_overlay_props(cfg, force_no_captions=False):
    """Constroi inputProps pra passar pro motor de navegador TitlesOverlay composition.
    Pega tudo que afeta visual de overlay alpha do edit_config.

    showCaptions e showProgressBar lidos LITERAIS do cfg (default True) —
    nao derivar de outros campos pra evitar mostrar UI quando nao deveria.

    force_no_captions: override (vindo de --no-captions CLI). Quando True, invalida cache.
    """
    captions_list = cfg.get("captions") or []
    show_captions_from_cfg = bool(cfg.get("showCaptions", True)) and len(captions_list) > 0
    return {
        "titles": cfg.get("titles", []),
        "playbackRate": cfg.get("playbackRate", 1.0),
        # showCaptions: literal do cfg (Klipe set explicito via UI). Se missing -> True
        # (mesmo default do VideoEditor composition). Captions vazios = nao renderiza nada.
        "showCaptions": show_captions_from_cfg and not force_no_captions,
        "captions": captions_list,
        # showProgressBar: literal do cfg. Se missing -> True (mesmo default do VideoEditor).
        "showProgressBar": bool(cfg.get("showProgressBar", True)),
        "captionBg": cfg.get("captionBg", True),
        "captionFontSize": cfg.get("captionFontSize", 100),
        "captionStyle": cfg.get("captionStyle", "words"),
        "captionFont": cfg.get("captionFont", "Montserrat"),
        "captionX": cfg.get("captionX", 0),
        "captionY": cfg.get("captionY", 0),
        "captionColor": cfg.get("captionColor", "#FFFFFF"),
        "captionHighlightColor": cfg.get("captionHighlightColor", "#E8940A"),
        "captionKaraoke": cfg.get("captionKaraoke", True),
        "captionMaxLines": cfg.get("captionMaxLines", 2),
        "captionContrast": cfg.get("captionContrast", 55),
        "captionWordGap": cfg.get("captionWordGap", 14),
        "captionLineGap": cfg.get("captionLineGap", 6),
        "captionFontPower": cfg.get("captionFontPower", ""),
        "captionFontNormal": cfg.get("captionFontNormal", ""),
        "captionFontSmall": cfg.get("captionFontSmall", ""),
        # Partes da legenda (cor / escala / offset por papel) — mesmo painel do compound
        **{f"caption{k}{suf}": cfg.get(f"caption{k}{suf}", 1 if k == "Scale" else (0 if k.startswith("Off") else ""))
           for k in ("Color", "Scale", "OffX", "OffY") for suf in ("Power", "Normal", "Small")},
        "shapes": cfg.get("shapes", []),
        "barColor": cfg.get("barColor", "#FF6B00"),
        "barHeight": cfg.get("barHeight", 6),
        # Composição vertical (9:16) ou landscape — lido pelo calculateMetadata da TitlesOverlay
        "compWidth": int(cfg.get("width", 1920)),
        "compHeight": int(cfg.get("height", 1080)),
    }


# render_overlay_parallel saiu junto com O motor de navegador: era o unico spawn de
# `npx motor de navegador render` que restava aqui, e ficou sem nenhum chamador.

def ler_saida_node(proc, timeout=3600, prefixo="[BATCH]"):
    """
    Le o stdout do o batch de titulos por navegador sem risco de travar pra sempre.

    `for line in proc.stdout` parece inofensivo mas nao tem saida: o node
    spawna Chrome, o Chrome herda o handle do cano, e se um deles fica orfao o
    cano NUNCA fecha — o loop bloqueia mesmo com o node ja morto e o
    `proc.wait(timeout=...)` logo abaixo nunca chega a rodar. Aconteceu aqui:
    render de 3 min parado 12 min com 0% de CPU e o MOV ja pronto em disco.

    Aqui a leitura vive numa thread daemon; se ela nao terminar no prazo, o
    processo e morto e a vida segue com o que ja foi lido.
    """
    import threading

    linhas, ultimo_json = [], None

    def _ler():
        try:
            for linha in proc.stdout:
                linha = linha.rstrip()
                if not linha:
                    continue
                if linha.startswith(prefixo):
                    log("    " + linha[len(prefixo) + 1:])
                elif linha.startswith("{") and '"results"' in linha:
                    try:
                        linhas.append(json.loads(linha))
                    except Exception:
                        pass
                else:
                    linhas.append(linha[:200])
        except Exception:
            pass

    t = threading.Thread(target=_ler, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        log(f"  WARN: node nao fechou a saida em {timeout}s — encerrando o processo")
        try:
            proc.kill()
        except Exception:
            pass
        t.join(10)
    try:
        proc.wait(timeout=30)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    for item in linhas:
        if isinstance(item, dict):
            ultimo_json = item
    return ultimo_json, [x for x in linhas if isinstance(x, str)]


def try_overlay_motioncore(cfg, out_path, force_no_captions=False):
    """
    Tenta renderizar o overlay monolitico (legenda + barra) no MotionCore.

    Devolve o caminho do MOV se der certo, ou None — e ai O motor de navegador assume.
    So aceita quando TODO o conteudo do overlay cabe no que ja foi portado:
    sem formas, sem titulo (o modo --per-title ja tira os titulos daqui) e com
    estilo de legenda conhecido. Meio-termo nao existe: ou o overlay sai
    inteiro certo, ou nao sai.
    """
    from motioncore.captions import ESTILOS as MC_ESTILOS_LEGENDA

    if cfg.get("shapes"):
        return None
    if cfg.get("titles"):
        return None

    quer_legenda = (bool(cfg.get("showCaptions", True))
                    and len(cfg.get("captions") or []) > 0
                    and not force_no_captions)
    if quer_legenda and cfg.get("captionStyle", "words") not in MC_ESTILOS_LEGENDA:
        log(f"  MotionCore: estilo de legenda {cfg.get('captionStyle')!r} ainda nao portado "
            f"— overlay vai pro motor de navegador")
        return None
    if not quer_legenda and not bool(cfg.get("showProgressBar", True)):
        return None

    try:
        from motioncore.overlay import render_overlay_mov
        t0 = time.time()
        m = render_overlay_mov(cfg, out_path, ffmpeg=FFMPEG_EXTERNAL,
                               com_legendas=quer_legenda)
        tiras = ", ".join(f"{n} y{a}..{b}" for n, a, b in m["tiras"])
        log(f"  MotionCore overlay: {m['frames']} frames em {m['seconds']}s "
            f"({m['fps_render']} fps, {m['repetidos']} repetidos) — {m['size_mb']} MB")
        log(f"    tiras: {tiras} | cano {cfg.get('width')}x{m['altura_cano']} "
            f"em vez de {cfg.get('width')}x{cfg.get('height')}")
        log(f"  Overlay pronto em {time.time()-t0:.1f}s SEM Chrome")
        return Path(out_path)
    except Exception as e:
        log(f"  MotionCore overlay WARN: {e} — caindo pro motor de navegador")
        try:
            p = Path(out_path)
            if p.exists():
                p.unlink()
        except Exception:
            pass
        return None


def _pasta_de_saida(cfg) -> Path:
    """Onde o render sai por padrao: DENTRO da pasta do projeto.

    Era um `output/` global, sem dono — render de projeto nenhum e de todos ao
    mesmo tempo. Duas consequencias que apareceram juntas: ninguem sabia de quem
    era cada arquivo, e como ninguem olha uma pasta sem dono, 16,9 GB se
    acumularam ali sem que se notasse. Era tambem a segunda arvore do mesmo
    projeto, ao lado de `public/projects/<slug>/`.

    Junto do projeto resolve os dois: apagar o projeto leva os renders junto, e
    como fica sob `public/`, o servidor serve o arquivo — da pra assistir o
    render no navegador sem sair do editor.

    Caminho absoluto em `--out` continua mandando: quem escolhe a pasta no modal
    manda nela.
    """
    src = str(cfg.get("videoSrc") or "").replace("\\", "/")
    m = re.search(r"projects/([^/]+)/", src)
    if m:
        d = ROOT / "public" / "projects" / m.group(1) / "renders"
        d.mkdir(parents=True, exist_ok=True)
        return d
    # sem slug identificavel no videoSrc, cai no antigo em vez de adivinhar
    return OUTPUT


def _camada_titulos_vazia(cfg, args) -> bool:
    """A camada de titulos nao tem NADA pra desenhar?

    Ela carrega tres coisas: titulos, shapes e legendas. Se as tres estao fora,
    O motor de navegador gera um MOV inteiro de transparencia — no video da Dra. Eli foram
    900s pra 1,2 GB de nada, contra 21s do composite inteiro. Nao e otimizacao
    de margem, e a diferenca entre 16,8 min e menos de um minuto.
    """
    if (cfg.get("titles") or []) or (cfg.get("shapes") or []):
        return False
    legendas = cfg.get("captions") or []
    if legendas and cfg.get("showCaptions") is not False and not args.no_captions:
        return False
    return True


def ensure_titles_overlay(cfg, force=False, force_no_captions=False):
    """Garante que titles alpha MOV existe pra esse hash do cfg.
    Brolls NAO precisam do motor de navegador — sao aplicados como overlay direto pelo ffmpeg.
    Retorna titles_mov.

    force_no_captions: vindo de --no-captions CLI. Invalida cache (hash diferente).
    """
    h = cfg_hash(cfg, force_no_captions=force_no_captions)
    cache_dir = CACHE_BASE / h
    cache_dir.mkdir(exist_ok=True)
    titles = cache_dir / "titles.mov"

    # Cada render com config diferente cria uma pasta com hash novo, e a antiga
    # ficava pra sempre. Achei 2,48 GB de overlay morto de 3 renders anteriores
    # contra 0,12 GB de cache util — limpa o que nao e mais deste projeto.
    if MC_DISPONIVEL:
        try:
            from motioncore.merge_titles import limpar_cache_morto
            limpar_cache_morto(CACHE_BASE, {h}, log=log)
        except Exception as e:
            log(f"  Cache: limpeza falhou ({e})")

    if not force and titles.exists() and titles.stat().st_size > 1_000_000:
        log(f"Cache HIT [{h}] — titles={titles.stat().st_size//1024//1024}MB")
        return titles

    # ── MotionCore: legenda + barra sem motor de navegador ───────────────────────────
    # Esse overlay e o de VIDEO INTEIRO — a etapa mais cara do render (929s num
    # video de 18min). Se o conteudo dele couber no que o MotionCore ja sabe
    # desenhar, o Chrome nem entra em cena.
    if MC_DISPONIVEL:
        mc = try_overlay_motioncore(cfg, titles, force_no_captions=force_no_captions)
        if mc is not None:
            return mc

    # Aqui era o caminhO motor de navegador: TitlesOverlay em pedacos paralelos, com
    # concat depois. Saiu junto com O motor de navegador. Se o MotionCore nao deu conta
    # do overlay, nao ha segundo motor — e dizer isso na hora e melhor que
    # tentar um `node o batch de titulos por navegador` que vai morrer no require.
    raise RuntimeError(
        "o MotionCore nao conseguiu montar o overlay deste projeto. "
        "Antes havia queda para O motor de navegador, que saiu do Klipe. "
        "Rode `python -m motioncore.overlay <config> <saida.mov>` para ver o motivo exato."
    )

    t0 = time.time()

    elapsed = time.time() - t0
    log(f"TitlesOverlay pronto em {elapsed:.1f}s | {titles.stat().st_size//1024//1024}MB")

    # OTIMIZACAO 2.0: monolitico (captions/shapes no video INTEIRO) em ProRes 4444
    # vira dezenas de GB. Transcodar pra QTRLE — mesmo alpha, fração do tamanho.
    tq = titles.with_name("titles_q.mov")
    t1 = time.time()
    r = subprocess.run([FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(titles), "-c:v", "qtrle", str(tq)],
                       capture_output=True, text=True)
    if r.returncode == 0 and tq.exists() and tq.stat().st_size > 1_000_000:
        old_gb = titles.stat().st_size / 1e9
        titles.unlink()
        tq.rename(titles)
        log(f"  QTRLE: {old_gb:.1f}GB -> {titles.stat().st_size/1e9:.1f}GB em {time.time()-t1:.0f}s")
    else:
        try: tq.unlink()
        except: pass
        log(f"  QTRLE transcode falhou (mantendo ProRes): {r.stderr[-200:] if r.stderr else '?'}")
    return titles


# ── Per-title cache (Phase 2) ─────────────────────────────────────────────────
# Em vez de renderizar TitlesOverlay monolitico (1 MOV com TODOS titles e duracao
# total do video), renderiza CADA title individualmente em paralelo. Cache por
# hash do title. Editar 1 title invalida so esse, nao os 13 outros.
import concurrent.futures
import threading

# ── Transformacoes de titulo: BAKE vs COMPOSICAO ─────────────────────────
# Estes cinco campos NAO entram no bake do MOV nem no hash: sao aplicados na
# hora do composite (scale/rotate/colorchannelmixer/overlay), igual ao b-roll.
# Motivo: assados no clipe, cada ajuste re-renderizava o titulo inteiro no
# servidor — mover o X fazia o titulo SUMIR da tela por segundos, e o cache
# per-title era invalidado por um tweak de posicao. Na composicao o ajuste e
# de graca e o preview (WebGL) faz a MESMA conta, entao nada diverge.
TRANSFORMS_COMPOSICAO = ("posX", "posY", "scale", "rotation", "opacity")


def _transform_de(t):
    """So o que NAO e neutro — dict vazio significa 'caminho rapido de antes'."""
    tf = {}
    if float(t.get("posX", 0) or 0):
        tf["posX"] = float(t["posX"])
    if float(t.get("posY", 0) or 0):
        tf["posY"] = float(t["posY"])
    esc = t.get("scale", 1)
    if esc is not None and float(esc) != 1:
        tf["scale"] = float(esc)
    if float(t.get("rotation", 0) or 0):
        tf["rotation"] = float(t["rotation"])
    op = t.get("opacity", None)
    if op is not None and float(op) != 1:
        tf["opacity"] = float(op)
    return tf


def _fonte_tem_audio(caminho):
    """A fonte tem trilha de audio? ffprobe direto — extensao nao prova nada."""
    _ff = Path(FFMPEG_EXTERNAL)
    ffprobe = str(_ff.with_name(_ff.name.replace("ffmpeg", "ffprobe")))
    try:
        r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "a",
                            "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                            str(caminho)], capture_output=True, text=True, timeout=15)
        return r.returncode == 0 and "audio" in r.stdout
    except Exception:
        return True   # na duvida, assume que tem — o erro antigo era melhor
                      # que silenciar um video COM audio por engano


def title_hash(title, w, h, fps, video_dur=None):
    """Hash POSICAO-INDEPENDENTE do title: conteudo visual + DURACAO, nada mais.

    Igual template de editor (CapCut/DaVinci): o estilo "ja ta feito" — mover o
    title na timeline, recortar o video ou mudar a duracao total NAO invalida o
    cache. So re-renderiza quando muda texto/estilo/fonte/posY/duracao do title.
    (Antes o hash incluia startSec + videoDuration: qualquer corte re-renderizava
    TODOS os titles do zero.)
    """
    t_norm = {k: v for k, v in title.items() if k not in ("startSec", "endSec", "id")}
    t_norm["_dur"] = round(float(title["endSec"]) - float(title["startSec"]), 2)
    payload = {"t": t_norm, "w": w, "h": h, "fps": fps}
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


# ── MotionCore: render de titulo em Skia, sem Chrome ──────────────────────────
try:
    from motioncore.render import suporta as mc_suporta
    MC_DISPONIVEL = True
except Exception as _e:
    MC_DISPONIVEL = False
    def mc_suporta(style): return False


def render_via_motioncore(tasks, w, h, fps, max_workers=8):
    """
    Renderiza os titles de estilo ja portado direto em Skia -> QTRLE.

    Sai do caminho Chrome -> PNG por frame -> ProRes em disco -> transcode.
    Aqui o frame vai da memoria pro stdin do ffmpeg e ja sai QTRLE — mesmo
    formato que o cache per-title usa hoje, entao o composite nao muda.

    Retorna o conjunto de Paths que ficaram prontos. O que falhar volta pro
    motor de navegador: o MotionCore acelera, nunca derruba o render.
    """
    payload = json.dumps({"width": int(w), "height": int(h), "fps": fps, "tasks": tasks})
    prontos = set()
    try:
        t0 = time.time()
        proc = subprocess.run([sys.executable, "-m", "motioncore.render",
                               "--tasks", "-", "--workers", str(max_workers)],
                              cwd=ROOT, input=payload, capture_output=True,
                              text=True, encoding="utf-8", timeout=1800)
        for line in (proc.stderr or "").splitlines():
            if line.startswith("[MC]"):
                log("    " + line[5:])
        saida = json.loads((proc.stdout or "").strip().splitlines()[-1])
        por_hash = {t["hash"]: Path(t["outPath"]) for t in tasks}
        for r in saida.get("results", []):
            if r.get("ok"):
                p = por_hash.get(r["hash"])
                if p and p.exists() and p.stat().st_size > 1000:
                    prontos.add(p)
        log(f"  MotionCore: {len(prontos)}/{len(tasks)} titles em {time.time()-t0:.1f}s (sem Chrome)")
    except Exception as e:
        log(f"  MotionCore WARN: {e} — esses titles voltam pro motor de navegador")
    return prontos


def ensure_individual_titles(cfg, force=False, max_workers=4):
    """Renderiza/cacheia cada title individualmente via motor de navegador Node API.

    Estrategia: bundle UMA VEZ + renderMedia N vezes (vs N invocacoes de
    `npx motor de navegador render` que recompilam o projeto cada vez).
    Ganho esperado: ~10x sobre o approach CLI antigo.

    - Cache: .forge_cache/titles_indiv/<hash>.mov
    - Paralelo: ate max_workers titles simultaneos compartilhando 1 bundle
    - Skip vazios e duracao <= 0
    """
    titles = cfg.get("titles", [])
    if not titles:
        return []

    cache_dir = CACHE_BASE / "titles_indiv"
    cache_dir.mkdir(exist_ok=True)

    fps = cfg.get("fps", 30)
    w = cfg.get("width", 1920)
    h = cfg.get("height", 1080)
    vd = cfg.get("videoDuration", 0)

    # So o NOME do executavel muda — trocar "ffmpeg" no caminho inteiro
    # transformava C:\ffmpeg\bin\ffprobe.exe em C:\ffprobe\bin\ffprobe.exe, que
    # nao existe. Com isso _mov_ok() falhava sempre e o cache per-title NUNCA
    # dava hit: todo render refazia todos os titles do zero.
    _ff = Path(FFMPEG_EXTERNAL)
    ffprobe = str(_ff.with_name(_ff.name.replace("ffmpeg", "ffprobe")))

    def _mov_ok(p):
        """Valida integridade do MOV cacheado (render morto no meio da escrita
        deixa arquivo sem moov atom que so explode la no composite)."""
        try:
            r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=15)
            return r.returncode == 0 and r.stdout.strip() != ""
        except Exception:
            return False

    results = []  # (path, startSec, endSec)
    todo = []
    vistos = set()   # hashes ja enfileirados
    pendentes = []   # (title, hash, path) — titles cujo MOV ainda vai ser gerado
    for t in titles:
        # o hash ignora as transformacoes de composicao: mover/escalar um
        # titulo NAO pode invalidar o MOV assado — era isso que fazia um
        # ajuste de 1px custar um re-render
        t_bake = {k: v for k, v in t.items() if k not in TRANSFORMS_COMPOSICAO}
        h_str = title_hash(t_bake, w, h, fps, vd)
        out = cache_dir / f"{h_str}.mov"
        if not force and out.exists() and out.stat().st_size > 1000 and _mov_ok(out):
            results.append((out, float(t["startSec"]), float(t["endSec"]), _transform_de(t)))
            continue
        # DEDUPE POR HASH: com hash independente de posicao, titles identicos
        # (ex: 4 cutMask de 0.33s) apontam pro MESMO arquivo. Sem dedupe, 4
        # renders paralelos escreviam no mesmo .mov e corrompiam (WinError 32
        # + moov atom not found). Renderiza 1 vez e reaproveita nos 4.
        pendentes.append((t, h_str, out))
        if h_str in vistos:
            continue
        vistos.add(h_str)
        if out.exists():
            try: out.unlink()
            except Exception: pass
        todo.append((t, h_str, out))

    if todo:
        log(f"  Per-title CACHE MISS: rendering {len(todo)}/{len(titles)} "
            f"(MotionCore + motor de navegador, concurrency={max_workers})...")
        t0 = time.time()

        # Build payload pra o batch de titulos por navegador
        # Clamp ao max frame valido da Composition (durationInFrames - 1)
        # pra evitar erro "frame range X-Y is not inbetween 0-Z" quando endSec
        # ultrapassa videoDuration por floating-point/rounding.
        # NORMALIZACAO 2.0: cada title renderiza ancorado em t=0 com SUA duracao
        # (o MOV resultante independe da posicao na timeline — cache reusavel
        # entre cortes/movidas, igual template de editor).
        tasks = []
        vd = float(cfg["videoDuration"])
        for t, h_str, out in todo:
            dur = min(float(t["endSec"]) - float(t["startSec"]), vd)
            dur_frames = round(dur * fps)
            if dur_frames <= 0:
                continue
            t_norm = {k: v for k, v in t.items() if k not in TRANSFORMS_COMPOSICAO}
            t_norm["startSec"] = 0.0
            t_norm["endSec"] = round(dur, 3)
            tasks.append({
                "hash": h_str,
                "outPath": str(out).replace("\\", "/"),
                "title": t_norm,
                "startFrame": 0,
                "endFrame": dur_frames - 1,
            })

        if not tasks:
            return results

        # ── MotionCore primeiro: estilo portado nao precisa de Chrome ───────
        # O que ele entregar sai da fila do motor de navegador. O que falhar continua na
        # fila — o motor novo acelera, mas nunca derruba o render.
        mc_outs = set()
        if MC_DISPONIVEL:
            tasks_mc = [tk for tk in tasks if mc_suporta(tk["title"].get("style"))]
            if tasks_mc:
                mc_outs = render_via_motioncore(tasks_mc, w, h, fps, max_workers)
                tasks = [tk for tk in tasks if Path(tk["outPath"]) not in mc_outs]

        # Aqui os titulos em estilo nao portado iam para O motor de navegador. Sem ele,
        # a lista precisa APARECER em vez de sumir dentro de um spawn que
        # falha: um titulo que nao desenha e um titulo que o cliente vai
        # procurar no video pronto.
        if tasks:
            nao_portados = sorted({(tk.get('title') or {}).get('style') or '?' for tk in tasks})
            log(f"  {len(tasks)} titulo(s) sem motor (estilo nao portado): "
                f"{', '.join(nao_portados)}")
            log("    (o seletor da interface nao oferece mais esses estilos; "
                "se apareceram, vieram de um projeto antigo)")


        # OTIMIZACAO 2.0: ProRes 4444 (380-560 Mbps) -> QTRLE (RLE com alpha).
        # Texto/graficos em fundo transparente comprimem 10-30x e o decode no
        # composite fica muito mais leve (era o maior custo de CPU/RAM do render).
        # NUNCA deixar essa otimizacao derrubar o render: no Windows o handle do
        # arquivo pode ficar preso (antivirus/indexador) e o unlink joga WinError 32.
        # Qualquer falha aqui = mantem o ProRes original e segue o baile.
        def _to_qtrle(path):
            tmp = path.with_name(path.stem + "_q.mov")
            try:
                r = subprocess.run([FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "error",
                                    "-i", str(path), "-c:v", "qtrle", str(tmp)],
                                   capture_output=True, text=True, timeout=600)
                if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size <= 1000:
                    raise RuntimeError("transcode falhou")
                old_mb = path.stat().st_size / 1e6
                # retry no unlink: handle costuma liberar em <1s
                for tentativa in range(5):
                    try:
                        path.unlink()
                        break
                    except PermissionError:
                        if tentativa == 4:
                            raise
                        time.sleep(0.4 * (tentativa + 1))
                tmp.rename(path)
                return old_mb - path.stat().st_size / 1e6
            except Exception:
                try:
                    if tmp.exists():
                        tmp.unlink()
                except Exception:
                    pass
                return 0.0
        t_q = time.time()
        saved_mb = 0.0
        # O MotionCore ja grava QTRLE direto — so o que veio do motor de navegador
        # (ProRes 4444) precisa do transcode.
        new_paths = [out for _, _, out in todo
                     if out.exists() and out.stat().st_size > 1000 and out not in mc_outs]
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                for s_mb in ex.map(_to_qtrle, new_paths):
                    saved_mb += s_mb
        except Exception as e:
            log(f"  QTRLE WARN: {e} — seguindo com os MOVs como estao")
        if new_paths:
            log(f"  QTRLE transcode: {len(new_paths)} titles, -{saved_mb/1000:.1f} GB em {time.time()-t_q:.0f}s")

        # Coletar: percorre TODOS os pendentes (nao so os renderizados), pra que
        # os titles que compartilham hash tambem recebam o MOV.
        for t, h_str, out in pendentes:
            if out.exists() and out.stat().st_size > 1000:
                results.append((out, float(t["startSec"]), float(t["endSec"]), _transform_de(t)))

        elapsed = time.time() - t0
        log(f"  Per-title render: {elapsed:.1f}s ({len(results)}/{len(todo)} OK)")

    results.sort(key=lambda x: x[1])
    log(f"  Total individual titles: {len(results)}/{len(titles)}")
    return results


# ── Native titles drawtext (OPT — bypass motor de navegador) ────────────────────────────
try:
    from forge_titles_native import (
        can_render_native, native_styles_only,
        build_native_titles_chain, NATIVE_STYLES,
    )
except ImportError:
    NATIVE_STYLES = set()
    def can_render_native(titles): return False
    def native_styles_only(titles): return False
    def build_native_titles_chain(titles, w, h): return ""


# ── Audio stems pre-mix (OPT) ─────────────────────────────────────────────────
def stems_hash(cfg):
    """Hash baseado em SFX + music config. Cache invalida quando muda."""
    payload = {
        # Invalida stems antigos quando a matematica do mixer muda. Sem essa
        # versao, corrigir volume/fade no codigo continuava reutilizando o WAV
        # produzido pela implementacao anterior.
        "mixVersion": 2,
        "sfx": cfg.get("sfx", []),
        "music": cfg.get("musicTracks", []),
        "duration": cfg.get("videoDuration"),
        "regions": cfg.get("audioRegions", []),
        "clipfx": [{k: v.get(k) for k in ("startSec", "endSec", "treble", "mid", "bass", "denoise", "highpass", "loudnorm")}
                   for v in cfg.get("videoClips", [])],
    }
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def ensure_audio_stems(cfg, project_dir):
    """Gera audio_voice/sfx/music.wav se nao existem ou hash mudou.

    Voice: extract from source video.mp4 (PCM 48kHz stereo).
    SFX: mix de todos sfx[] com volume + atrim.
    Music: mix de musicTracks[] com loop pra tracks curtas + fades.

    Cache: stems_<hash>.txt no project_dir indica versao atual.
    """
    voice = project_dir / "audio_voice.wav"
    sfx_out = project_dir / "audio_sfx.wav"
    music_out = project_dir / "audio_music.wav"
    hash_marker = project_dir / "audio_stems.hash"
    cur_hash = stems_hash(cfg)

    # Cache hit: stems exist + hash matches
    if all(p.exists() for p in [voice, sfx_out, music_out]) and hash_marker.exists():
        if hash_marker.read_text(encoding="utf-8").strip() == cur_hash:
            log(f"  Audio stems CACHE HIT [{cur_hash}]")
            return voice, sfx_out, music_out

    log(f"  Audio stems CACHE MISS [{cur_hash}] - gerando stems...")
    SR = 48000
    total_dur = cfg["videoDuration"]
    video_src = PUBLIC / cfg["videoSrc"]

    t0 = time.time()
    # Voice: extract from source — SEMPRE que o hash muda (o video_cut.mp4 pode
    # ter sido recortado com o mesmo nome; reusar voice.wav velho dessincroniza tudo)
    log(f"    voice: extracting...")
    # REGIOES DE AUDIO: correcao de tom por trecho (ex: parte gravada no celular
    # fica mais brilhante). Cada regiao aplica ganho/graves/agudos SO na sua janela.
    # Cada CLIP de video carrega seu proprio tratamento (igual a qualquer NLE:
    # corta o trecho, seleciona, ajusta). Aplicado so na janela daquele clip.
    regioes = list(cfg.get("audioRegions") or [])
    for vc in cfg.get("videoClips", []):
        if any(float(vc.get(k, 0) or 0) for k in ("treble", "mid", "bass", "denoise", "highpass")) or vc.get("loudnorm"):
            regioes.append({
                "startSec": float(vc.get("startSec", 0)), "endSec": float(vc.get("endSec", 0)),
                "treble": vc.get("treble", 0), "mid": vc.get("mid", 0), "bass": vc.get("bass", 0),
                "gain": 0, "denoise": vc.get("denoise", 0),
                "highpass": vc.get("highpass", 0), "loudnorm": vc.get("loudnorm", 0),
            })
    af = []
    for rg in regioes:
        ini, fim = float(rg.get("startSec", 0)), float(rg.get("endSec", 0))
        if fim <= ini:
            continue
        janela = f"between(t\,{ini}\,{fim})"
        g = float(rg.get("gain", 0) or 0)
        tr = float(rg.get("treble", 0) or 0)
        md = float(rg.get("mid", 0) or 0)
        bs = float(rg.get("bass", 0) or 0)
        dn = float(rg.get("denoise", 0) or 0)
        hp = float(rg.get("highpass", 0) or 0)
        if tr:
            af.append(f"treble=g={tr}:f=3000:enable='{janela}'")
        if md:
            af.append(f"equalizer=f=1200:t=q:w=1.2:g={md}:enable='{janela}'")
        if bs:
            af.append(f"bass=g={bs}:f=200:enable='{janela}'")
        if hp:
            af.append(f"highpass=f={hp}:enable='{janela}'")
        if dn:
            af.append(f"afftdn=nr={dn}:nf=-25:enable='{janela}'")
        if g:
            af.append(f"volume={g}dB:enable='{janela}'")
        if rg.get("loudnorm"):
            af.append("loudnorm=I=-16:TP=-1.5:LRA=11")   # global (nao aceita enable)
    cmd_voice = [FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "error",
                 "-i", str(video_src), "-vn"]
    if af:
        cmd_voice += ["-af", ",".join(af)]
        log(f"    voice: {len(regioes)} regiao(oes) de correcao aplicada(s)")
    cmd_voice += ["-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(voice)]
    subprocess.run(cmd_voice, check=True)

    # SFX mix
    sfx_list = cfg.get("sfx", [])
    log(f"    sfx: mixing {len(sfx_list)} entries...")
    if sfx_list:
        inputs = []
        filters = []
        ff_idx = 0  # FIX: track real ffmpeg input index separately from SFX list index
        skipped = []
        for s in sfx_list:
            src = (PUBLIC / s["src"]).resolve()
            if not src.exists():
                skipped.append(s["src"])
                continue
            inputs += ["-i", str(src)]
            delay_ms = int(s["startSec"] * 1000)
            # TETO 1.0, nao 2.0. O mesmo volume dava tres resultados: o preview
            # satura em 1.0 (limite do <audio> do navegador), este caminho
            # permitia +6 dB e o caminho individual nao tinha teto nenhum.
            # 1.0 e o unico valor que os tres conseguem honrar — quem precisa
            # de mais normaliza o arquivo de origem, onde o ganho e real.
            vol = max(0.0, min(float(s.get("volume", 1.0) or 0), 1.0))
            # BUG ATE 2026-07-31: o SFX entrava INTEIRO no mix, ignorando o corte
            # feito na timeline (user: "as sfx que tem corte nao estao cortando").
            # Agora respeita srcStart + duracao do clip; fades continuam sendo
            # uma decisao explicita da timeline.
            span = max(0.02, float(s["endSec"]) - float(s["startSec"]))
            src_start = float(s.get("srcStart", 0) or 0)
            fi = min(span, max(0.0, float(s.get("fadeIn", 0) or 0)))
            fo = min(span, max(0.0, float(s.get("fadeOut", 0) or 0)))
            ch = (f"[{ff_idx}:a]atrim=start={src_start:.3f}:end={src_start + span:.3f},"
                  f"asetpts=PTS-STARTPTS,volume={vol}")
            # Paridade com o preview: fade zero significa audio intacto. O
            # caminho de stems aplicava 5 ms/20 ms escondidos em todo clipe,
            # apagando o ataque de clicks, markers e impactos curtos. So entra
            # rampa quando ela foi configurada na timeline.
            if fi > 0:
                ch += f",afade=t=in:st=0:d={fi:.3f}"
            if fo > 0:
                ch += f",afade=t=out:st={max(0.0, span - fo):.3f}:d={fo:.3f}"
            # BUG ATE 2026-08-07: aqui vinha um `atrim=end={total_dur}` POR RAMO,
            # e ele fazia UM dos SFX sumir do mix — sempre o ultimo da lista,
            # calado, sem aviso nenhum. Medido: com 12 SFX o stem saia com 11.
            # O amix nao lida bem com ramos deslocados por PTS que terminam em
            # instantes diferentes por atrim. A trava de duracao continua
            # existindo, mas DEPOIS do amix (ver o atrim no fim do filtro), que
            # e onde ela devia estar desde o comeco: o que nao pode passar do
            # fim do video e a MISTURA, nao cada som isolado.
            ch += f",adelay={delay_ms}|{delay_ms}[s{ff_idx}]"
            filters.append(ch)
            ff_idx += 1
        if skipped:
            log(f"    WARN: {len(skipped)} SFX files NOT FOUND, skipping:")
            for p in skipped[:10]:
                log(f"      - {p}")
        if filters:
            mix_inputs = "".join(f"[s{i}]" for i in range(len(filters)))
            # `apad` estica ate o fim do video e `atrim` corta o que passar —
            # nesta ordem, e sobre a MISTURA. Cortar ramo a ramo derrubava um
            # dos SFX (ver a nota acima).
            sfx_filter = ";".join(filters) + f";{mix_inputs}amix=inputs={len(filters)}:duration=longest:dropout_transition=0:normalize=0,apad=whole_dur={total_dur},atrim=end={total_dur}[mix]"
            fc_file = project_dir / ".sfx_filter.txt"
            fc_file.write_text(sfx_filter, encoding="utf-8")
            subprocess.run([FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "error",
                *inputs, "-filter_complex_script", str(fc_file), "-map", "[mix]",
                "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(sfx_out)], check=True)
            fc_file.unlink(missing_ok=True)
        else:
            # Empty SFX track
            subprocess.run([FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={SR}",
                "-t", str(total_dur), "-c:a", "pcm_s16le", str(sfx_out)], check=True)
    else:
        subprocess.run([FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={SR}",
            "-t", str(total_dur), "-c:a", "pcm_s16le", str(sfx_out)], check=True)

    # Music mix (with loop pra tracks curtas, BOOST 5x sobre vol Klipe pra audibilidade)
    music_list = cfg.get("musicTracks", [])
    log(f"    music: mixing {len(music_list)} tracks...")
    if music_list:
        snippets = []
        for i, m in enumerate(music_list):
            src = (PUBLIC / m["src"]).resolve()
            if not src.exists(): continue
            start = m.get("startSec", 0)
            end = m.get("endSec", total_dur)
            dur = end - start
            srcStart = m.get("srcStart", 0)
            # PARIDADE COM PREVIEW: volume aplicado como esta no config, SEM boost.
            # O boost 5x antigo fazia -30dB virar -16dB no render ("musica nao
            # baixou") — user ajusta o volume no Klipe e o render tem que obedecer.
            vol = min(m.get("volume", 0.07), 1.0)
            fadeIn = m.get("fadeIn", 0)
            fadeOut = m.get("fadeOut", 0)
            tmp = project_dir / f".m{i}.wav"
            chain = [f"[0:a]atrim=start={srcStart},asetpts=PTS-STARTPTS,volume={vol}"]
            if fadeIn > 0:
                chain.append(f"afade=t=in:st=0:d={fadeIn:.3f}")
            if fadeOut > 0:
                chain.append(f"afade=t=out:st={max(0,dur-fadeOut):.3f}:d={fadeOut:.3f}")
            # FIX BUG 2026-05-06: aloop=loop=-1 gerava arquivos de 190GB+ porque
            # ffmpeg materializa o loop infinito antes do atrim cortar. Substituido
            # por apad=whole_dur que padda com silencio ate a duracao alvo (sem loop).
            # Limita arquivo de saida em SR*4 bytes/s × dur (~1MB/s estereo 16bit)
            # garantindo size proporcional a dur.
            chain.append(f"apad=whole_dur={dur},atrim=end={dur},adelay={int(start*1000)}|{int(start*1000)}")
            chain_str = ",".join(chain)
            # Hard limit -t no ffmpeg pra garantir que NUNCA escreva alem do esperado
            subprocess.run([FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(src), "-filter_complex", chain_str,
                "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
                "-t", str(start + dur),  # SAFETY: hard cap no output duration
                str(tmp)], check=True, timeout=120)  # SAFETY: timeout 2min
            snippets.append(str(tmp))
        if snippets:
            inputs = []
            for s in snippets: inputs += ["-i", s]
            mix_filter = f"amix=inputs={len(snippets)}:duration=longest:dropout_transition=0:normalize=0,apad=whole_dur={total_dur}"
            subprocess.run([FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "error",
                *inputs, "-filter_complex", mix_filter,
                "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", "-t", str(total_dur),
                str(music_out)], check=True)
            for s in snippets:
                try: Path(s).unlink()
                except: pass
        else:
            subprocess.run([FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={SR}",
                "-t", str(total_dur), "-c:a", "pcm_s16le", str(music_out)], check=True)
    else:
        subprocess.run([FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={SR}",
            "-t", str(total_dur), "-c:a", "pcm_s16le", str(music_out)], check=True)

    hash_marker.write_text(cur_hash, encoding="utf-8")
    elapsed = time.time() - t0
    log(f"  Audio stems gerados em {elapsed:.1f}s")
    return voice, sfx_out, music_out


# ── Audio mix ─────────────────────────────────────────────────────────────────
def build_audio_filter_graph(cfg, audio_inputs, src_audio="0:a"):
    """Constroi filter_complex pra mix audio:
       - source voice (input 0:a)
       - N SFX (volume + delay)
       - M music tracks (volume + fadein/fadeout + delay)
       Retorna (filter_str, output_label).

       audio_inputs eh lista [(input_idx, type, params), ...]"""
    duration_ms = int(cfg["videoDuration"] * 1000)
    parts = []
    mix_labels = []

    # Source voice = input 0
    # O botao de mute e o volume do video principal valiam SO no preview: o
    # render mixava a voz sempre em 1.0 e o arquivo saia com som que a tela
    # dizia nao existir. (--audio-from-source continua ignorando isto de
    # proposito: e uma flag explicita de CLI pedindo o audio da fonte.)
    vol_fonte = 0.0 if cfg.get("videoMuted") else float(cfg.get("videoVolume", 1) or 0)
    parts.append(f"[{src_audio}]volume={vol_fonte:.4f}[v0]")
    mix_labels.append("[v0]")

    for input_idx, kind, params in audio_inputs:
        start_ms = int(params["startSec"] * 1000)
        vol = params.get("volume", 1.0)
        fade_in = params.get("fadeIn", 0)
        fade_out = params.get("fadeOut", 0)
        end_ms = int(params["endSec"] * 1000)
        clip_dur_ms = end_ms - start_ms
        src_offset = params.get("srcStart", 0)

        # Build chain: atrim (skip srcStart) -> volume -> afade in/out -> adelay
        chain = [f"[{input_idx}:a]"]
        if src_offset > 0:
            chain.append(f"atrim=start={src_offset},asetpts=PTS-STARTPTS")
        # mesmo teto do preview e do caminho de stems (ver nota acima)
        chain.append(f"volume={min(float(vol), 1.0):.4f}")
        clip_dur_s = clip_dur_ms / 1000
        # Helper pra formatar floats sem notacao cientifica (ffmpeg nao parseia 2.26e-14)
        def _f(v):
            v = round(max(0, v), 6)
            return f"{v:.6f}"
        if fade_in > 0:
            fi = min(fade_in, clip_dur_s)
            if fi > 0.001:
                chain.append(f"afade=t=in:st=0:d={_f(fi)}")
        if fade_out > 0:
            fo = min(fade_out, clip_dur_s)
            fo_st = max(0, clip_dur_s - fo)
            if fo > 0.001:
                chain.append(f"afade=t=out:st={_f(fo_st)}:d={_f(fo)}")
        # Trim to clip duration
        chain.append(f"atrim=duration={_f(clip_dur_s)}")
        # Delay to align na timeline
        if start_ms > 0:
            chain.append(f"adelay={start_ms}|{start_ms}")

        label = f"[a{input_idx}]"
        chain_str = ",".join(chain[1:])  # skip the [N:a] prefix
        parts.append(f"[{input_idx}:a]{chain_str}{label}")
        mix_labels.append(label)

    # Mix everything
    mix = f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0:normalize=0[aout]"
    parts.append(mix)
    return ";".join(parts), "[aout]"


# ── Zoom math (replica logica motor de navegador) ───────────────────────────────────────
def build_zoom_expression(cfg):
    """Constroi expressao ffmpeg pra scale factor dinamico baseado em zooms.

    Retorna tupla (zoom_factor_expr, origin_y_expr) ou (None, None) se sem zooms.

    Cada zoom em cfg["zooms"]:
      - direction: "in" (1.0->intensity), "out" (intensity->1.0),
                   "hardIn" (constante intensity), "hardOut" (constante intensity)
      - intensity: ex 1.1, 1.2, 1.3
      - easing: "smooth"/"easeInOut", "easeOut", "easeIn", "linear"
      - originY: opcional, % do centro Y (default 50)

    Math:
      zoom_factor(t) = 1.0 + sum(zoom_contribution(z, t) for z in zooms)
      onde contribution = 0 fora da janela, e dentro depende de direction+easing
    """
    zooms = [z for z in cfg.get("zooms", []) if z["endSec"] > z["startSec"]]
    if not zooms:
        return None, None

    # SEMANTICA KLIPE (o template antigo ~6323): o PRIMEIRO zoom ativo na ordem do
    # array vence (break) — zooms simultaneos NUNCA somam. A versao antiga somava
    # contribuicoes e um overlap de 3 zooms virava fator 1.77 constante ("zoom
    # absurdo" no render com preview normal). Resolvemos o vencedor AQUI em Python:
    # particionamos a timeline em janelas disjuntas, cada uma com o zoom vencedor,
    # e a expressao vira uma soma de janelas que nunca se sobrepoem.
    bounds = sorted({round(b, 4) for z in zooms for b in (z["startSec"], z["endSec"])})
    segs = []  # (a, b, zoom_vencedor)
    for a, b in zip(bounds, bounds[1:]):
        mid = (a + b) / 2
        win = next((z for z in zooms if z["startSec"] <= mid <= z["endSec"]), None)
        if win is None:
            continue
        if segs and segs[-1][2] is win and abs(segs[-1][1] - a) < 1e-6:
            segs[-1] = (segs[-1][0], b, win)  # merge janelas contiguas do mesmo vencedor
        else:
            segs.append((a, b, win))

    def ease_expr(easing, prog):
        # Identico ao applyEasing do template antigo (default LINEAR, como no Klipe)
        if easing == "easeInOut":
            return f"if(lt({prog}\\,0.5)\\,2*{prog}*{prog}\\,1-pow(-2*{prog}+2\\,2)/2)"
        if easing == "easeIn":
            return f"pow({prog}\\,3)"
        if easing == "easeOut":
            return f"(1-pow(1-{prog}\\,3))"
        if easing == "smooth":  # Hermite smoothstep t*t*(3-2*t)
            return f"({prog}*{prog}*(3-2*{prog}))"
        return prog  # linear

    contribs = []
    oy_terms = []
    for a, b, z in segs:
        s, e = z["startSec"], z["endSec"]
        intensity = z["intensity"]
        direction = z["direction"]
        # progress relativo a janela ORIGINAL do zoom vencedor, clampado 0..1
        prog = f"clip((t-{s})/{e - s}\\,0\\,1)"
        if direction == "slowIn":
            # chega devagar: acelera so no fim (p^1.7)
            val = f"{intensity - 1.0}*pow({prog}\,1.7)"
        elif direction == "breathe":
            # vai e volta: sobe ate a metade da janela e retorna
            val = f"{intensity - 1.0}*sin(3.14159265*{prog})"
        elif direction == "hardIn":
            val = f"{intensity - 1.0}"
        elif direction == "hardOut":
            val = "0"  # Klipe: hardOut = scale 1.0 constante
        elif direction == "in":
            val = f"{intensity - 1.0}*{ease_expr(z.get('easing', 'linear'), prog)}"
        elif direction == "out":
            val = f"{intensity - 1.0}*(1-{ease_expr(z.get('easing', 'linear'), prog)})"
        else:
            val = "0"
        # janelas semi-abertas (b-0.001) pra bordas adjacentes nao contarem 2x
        contribs.append(f"between(t\\,{a}\\,{b - 0.001})*({val})")
        oy = z.get("originY", 40)  # default 40 como no Klipe (nao 50)
        oy_terms.append(f"between(t\\,{a}\\,{b - 0.001})*{oy - 50}")

    if not contribs:
        return None, None
    zoom_factor_expr = "1.0+" + "+".join(contribs)
    # originY efetivo: 50 + deltas por janela (fora de zoom o termo (z-1) zera o crop_y)
    origin_y_expr = "50+" + "+".join(oy_terms)

    return zoom_factor_expr, origin_y_expr


def apply_zoom_to_source(zoom_factor_expr, origin_y_expr, use_cuda=False, w=1920, h=1080):
    """Constroi filter chain pra aplicar zoom dinamico no source.

    Modo CPU (default): scale eval=frame + crop centralizado
    Modo CUDA: scale_cuda (GPU) + hwdownload + crop CPU
      (crop_cuda nao existe nesse ffmpeg)

    Output WxH respeita o aspect ratio configurado (16:9, 9:16, 1:1, 4:5).
    """
    crop_x = f"{w}*(({zoom_factor_expr})-1)/2"
    crop_y = f"{h}*(({zoom_factor_expr})-1)*(({origin_y_expr})/100)"

    if use_cuda:
        # GPU scale via scale_cuda, depois hwdownload pra crop CPU
        return (
            f"scale_cuda="
            f"w='{w}*({zoom_factor_expr})':"
            f"h='{h}*({zoom_factor_expr})':"
            f"format=yuv420p:"
            f"interp_algo=lanczos,"
            f"hwdownload,format=yuv420p,"
            f"crop={w}:{h}:"
            f"x='{crop_x}':"
            f"y='{crop_y}':"
            f"exact=1"
        )
    else:
        return (
            f"scale="
            f"w='{w}*({zoom_factor_expr})':"
            f"h='{h}*({zoom_factor_expr})':"
            f"eval=frame:"
            f"flags=bilinear,"
            f"crop={w}:{h}:"
            f"x='{crop_x}':"
            f"y='{crop_y}':"
            f"exact=1"
        )


# ── Composite final (NVENC) ───────────────────────────────────────────────────
def build_color_correction_chain(cfg):
    """Constroi chain ffmpeg pra color correction baseada em campos do edit_config.

    Klipe armazena em cfg.colorCorrection (objeto) ou em chaves top-level legacy.
    Mapeia params pra filtros ffmpeg:
      brightness  (-100..100, default 0)  -> eq=brightness=N/100
      contrast    (-100..100, default 0)  -> eq=contrast=1+N/100
      saturation  (-100..100, default 0)  -> eq=saturation=1+N/100 (-100=BW, 0=normal)
      temperature (-100..100, default 0)  -> tonal shift (azul/laranja)
      hue         (-180..180 graus)       -> hue=h=N
      vignette    (0..100)                -> vignette=PI/4+(N/100)*PI/4
      grain       (0..100)                -> noise=alls=N:allf=t (light noise)
    """
    cc = cfg.get("colorCorrection", {}) or {}
    chain = []
    # Le do colorCorrection objeto OU top-level (fallback)
    brightness = cc.get("brightness", cfg.get("brightness", 0))
    contrast = cc.get("contrast", cfg.get("contrast", 0))
    saturation = cc.get("saturation", cfg.get("saturation", 0))
    temperature = cc.get("temperature", cfg.get("temperature", 0))
    hue = cc.get("hue", cfg.get("hue", 0))
    # BUG: vinheta e grao eram lidos SO do topo do config, nunca do objeto
    # colorCorrection — que e onde o painel escreve. Os dois sliders nao
    # faziam nada no render.
    vignette = cc.get("vignette", cfg.get("vignette", 0))
    grain = cc.get("grain", cfg.get("grain", 0))
    # Realce e sombra: o preview (shader) os aplica e o render nao tinha nada
    # equivalente — e como quase todo preset os usa, TODO preset divergia.
    highlight = cc.get("highlight", cfg.get("highlight", 0))
    shadow = cc.get("shadow", cfg.get("shadow", 0))

    # `filterIntensity` do painel: o preview multiplica o efeito inteiro por
    # ele (mix(org, cor, forca) no shader) e o render ignorava — o slider
    # movia a imagem na tela e nao movia nada no arquivo. Escalar os valores
    # AQUI reproduz o mesmo resultado, porque todos os efeitos abaixo sao
    # lineares no parametro.
    forca = cfg.get("filterIntensity", cc.get("filterIntensity", 100))
    try:
        forca = max(0.0, min(1.0, float(forca) / 100.0))
    except (TypeError, ValueError):
        forca = 1.0
    if forca != 1.0:
        brightness *= forca
        contrast *= forca
        saturation *= forca
        temperature *= forca
        hue *= forca
        highlight *= forca
        shadow *= forca

    # eq filter — combina brightness/contrast/saturation
    if brightness != 0 or contrast != 0 or saturation != 0:
        eq_parts = []
        if brightness != 0:
            eq_parts.append(f"brightness={brightness/100:.3f}")
        if contrast != 0:
            eq_parts.append(f"contrast={1 + contrast/100:.3f}")
        if saturation != 0:
            eq_parts.append(f"saturation={1 + saturation/100:.3f}")
        chain.append("eq=" + ":".join(eq_parts))

    # Realce/sombra via `curves`. O shader soma um offset pesado pelas PONTAS
    # da curva de luminancia (smoothstep), o que permite levantar sombra sem
    # estourar o branco. `curves` faz o equivalente movendo os pontos de
    # controle: o de 0.75 pro realce, o de 0.25 pra sombra. Nao e a mesma
    # formula ao decimal, mas e o mesmo GESTO e para no mesmo lugar nos
    # extremos — muito mais perto que a divergencia total de antes.
    if highlight != 0 or shadow != 0:
        alto = max(0.0, min(1.0, 0.75 + (highlight / 100.0) * 0.25))
        baixo = max(0.0, min(1.0, 0.25 + (shadow / 100.0) * 0.25))
        chain.append(f"curves=all='0/0 0.25/{baixo:.4f} 0.75/{alto:.4f} 1/1'")

    # Temperature: shift quente/frio via colorbalance
    if temperature != 0:
        rs = temperature / 200  # +0.5 max
        bs = -temperature / 200
        chain.append(f"colorbalance=rs={rs:.3f}:bs={bs:.3f}")

    # hue rotation
    if hue != 0:
        chain.append(f"hue=h={hue}")

    # vignette (intensidade do escurecimento nos cantos)
    if vignette > 0:
        # angle PI/4 + intensity * PI/4 (0 = no vignette, max = pretty dark)
        ang = 0.7854 + (vignette / 100) * 0.7854
        chain.append(f"vignette=angle={ang:.3f}")

    # grain (noise filter)
    if grain > 0:
        chain.append(f"noise=alls={grain}:allf=t")

    return ",".join(chain) if chain else None


def build_video_filter_graph(cfg, n_brolls_inputs, titles_input_idx,
                              gpu_pipeline=False, skip_titles=False,
                              titles_indiv=None):
    """Constroi filter_complex pra video.

    Pipeline:
      [0:v] aspect crop -> color correction -> zoom -> overlay brolls -> overlay titles -> NVENC

    skip_titles=True: pula o overlay do titles.mov (composite final fica sem texto).
                     Cache do titles.mov continua valido.
    """
    W = int(cfg.get("width", 1920))
    H = int(cfg.get("height", 1080))
    parts = []

    # 0. Aspect crop: source pode ser 1920x1080, output W x H. Scale cover + crop centro.
    aspect_chain = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"

    # 1. Color correction (eq, hue, vignette, grain) aplicado ao source
    color_chain = build_color_correction_chain(cfg)

    # 2. Zoom dinamico
    zoom_expr, origin_y_expr = build_zoom_expression(cfg)

    # Combina aspect + color + zoom em uma chain
    src_chain_parts = [aspect_chain]
    if color_chain:
        src_chain_parts.append(color_chain)
    if zoom_expr:
        src_chain_parts.append(apply_zoom_to_source(zoom_expr, origin_y_expr, use_cuda=False, w=W, h=H))

    parts.append(f"[0:v]{','.join(src_chain_parts)}[src_processed]")
    source_label = "src_processed"

    # 2. Brolls com tpad pra delay
    broll_intervals = []
    broll_pos = []          # canto onde cada camada entra (posX/posY + escala)
    brolls_cfg = cfg.get("brolls", [])
    for i in range(n_brolls_inputs):
        b = brolls_cfg[i]
        start = b["startSec"]
        end = b["endSec"]
        clip_dur = end - start
        broll_intervals.append((start, end))

        # Brolls em CPU (mesmo no modo GPU): tpad com alpha + overlay
        # NVDEC pode ser usado via -hwaccel no input mas precisamos hwdownload
        # pra fazer tpad alpha que nao tem versao CUDA.
        prefix = ""
        if gpu_pipeline:
            # Source do broll vem como cuda format se -hwaccel cuda foi setado no input
            prefix = "hwdownload,format=yuv420p,"
        # Fades de alpha (paridade com preview: brolls entram/saem suaves, nao pop)
        fade_in = float(b.get("fadeIn", 0) or 0)
        fade_out = float(b.get("fadeOut", 0) or 0)
        fade_chain = ""
        if fade_in > 0:
            fade_chain += f",fade=t=in:st={start}:d={fade_in}:alpha=1"
        if fade_out > 0:
            fade_chain += f",fade=t=out:st={max(start, end - fade_out)}:d={fade_out}:alpha=1"
        # ── PARIDADE COM O PREVIEW ────────────────────────────────────────
        # O preview le `alpha`, `opacity`, `posX/posY` e `scale` de cada broll;
        # aqui nada disso era lido, entao o arquivo final saia diferente do que
        # a tela mostrava. Pior: `alpha` (cor|alpha lado a lado) nem existia no
        # render — o crop centralizado pegava metade da cor com metade do
        # alpha e o overlay entrava opaco por cima dela.
        esc = float(b.get("scale", 1) or 1)
        lw = max(2, int(round(W * esc)))
        lh = max(2, int(round(H * esc)))
        # o preview escala em torno do CENTRO (p * escala no vertex shader);
        # `overlay` posiciona pelo canto, entao a diferenca entra no offset
        pos_x = int(round(float(b.get("posX", 0) or 0) + (W - lw) / 2.0))
        pos_y = int(round(float(b.get("posY", 0) or 0) + (H - lh) / 2.0))
        broll_pos.append((pos_x, pos_y))

        op = b.get("opacity", 1)
        op = 1.0 if op is None else float(op)
        op_chain = "" if abs(op - 1.0) < 1e-3 else f",colorchannelmixer=aa={op:.4f}"

        # Velocidade: reescala o tempo DENTRO do clipe e reancora em `start`.
        # `(PTS-STARTPTS)/vel` acelera a partir do primeiro frame; `+start/TB`
        # devolve o clipe pro lugar dele na timeline (o `-itsoffset` ja o pos
        # la, e dividir o PTS cru arrastaria tudo pra origem).
        vel = float(b.get("speed", 1) or 1)
        vel = min(10.0, max(0.1, vel))
        spd_chain = "" if abs(vel - 1.0) < 1e-3 else \
            f"setpts=(PTS-STARTPTS)/{vel:.4f}+{start}/TB,"

        # Splits gerados pela nossa pipeline ja saem em WxH exatos — pular o
        # swscale por frame (no-op caro em 14 branches simultaneas)
        is_our_split = "/splits/" in str(b.get("src", "")) and esc == 1
        scale_chain = "" if is_our_split else (
            f"scale={lw}:{lh}:force_original_aspect_ratio=increase,crop={lw}:{lh},")

        if b.get("alpha"):
            # Camada cor|alpha: metade esquerda e a cor, direita e o alpha em
            # tons de cinza. `split` e obrigatorio — um pad de filtro so pode ser
            # consumido UMA vez, entao referenciar [i:v] duas vezes nao compila.
            parts.append(
                f"[{i+1}:v]{prefix}split=2[bsa{i}][bsb{i}]")
            parts.append(
                f"[bsa{i}]crop=iw/2:ih:0:0,scale={lw}:{lh}[bc{i}]")
            parts.append(
                f"[bsb{i}]crop=iw/2:ih:iw/2:0,scale={lw}:{lh},format=gray[ba{i}]")
            parts.append(
                f"[bc{i}][ba{i}]alphamerge,"
                f"{spd_chain}"
                f"trim=start={start}:end={end},format=yuva420p"
                f"{op_chain}{fade_chain}[b{i}]"
            )
            continue
        # `-itsoffset` no input em vez de `tpad`.
        #
        # O `tpad=start_duration={start}` FABRICAVA um frame transparente pra
        # cada frame desde o segundo zero ate o broll comecar — e depois jogava
        # fora. Neste projeto sao 86.262 frames vazios pra entregar 3.679 uteis,
        # 23 pra 1. Um broll aos 667s sozinho gerava 20 mil frames.
        #
        # `-itsoffset` so desloca o timestamp: nao gera frame nenhum. E o mesmo
        # caminho que os titulos por arquivo ja usavam.
        parts.append(
            f"[{i+1}:v]{prefix}"
            f"{scale_chain}"
            f"{spd_chain}"
            f"trim=start={start}:end={end},"
            f"format=yuva420p"
            f"{op_chain}"
            f"{fade_chain}"
            f"[b{i}]"
        )

    # 3. Sequential overlays brolls (CPU)
    cur_label = source_label
    for i, (start, end) in enumerate(broll_intervals):
        next_label = f"v_after_b{i}" if i < len(broll_intervals) - 1 else "v_with_brolls"
        ox, oy = broll_pos[i] if i < len(broll_pos) else (0, 0)
        parts.append(
            f"[{cur_label}][b{i}]overlay={ox}:{oy}:enable='between(t,{start},{end})':"
            f"format=auto[{next_label}]"
        )
        cur_label = next_label

    if n_brolls_inputs == 0:
        parts.append(f"[{source_label}]copy[v_with_brolls]")

    # 4. Titles overlay — 3 modos
    if skip_titles:
        parts.append(f"[v_with_brolls]copy[vout]")
    elif titles_indiv:
        # PER-TITLE: cada title eh input separado com -itsoffset, sequential overlay
        # com enable=between(t,startSec,endSec) — fora desse range, alpha do MOV ja eh 0
        # mas enable acelera (skip frames inteiros).
        cur = "v_with_brolls"
        for k, item in enumerate(titles_indiv):
            in_idx, s_sec, e_sec = item[0], item[1], item[2]
            tf = item[3] if len(item) > 3 else {}
            nxt = f"v_t{k}" if k < len(titles_indiv) - 1 else "vout"
            if tf:
                # MESMA ordem do preview e do motor: escala sobre o centro,
                # rotacao sobre o centro, e ai o deslocamento. Divergir de
                # ordem aqui e o tipo de bug que so aparece com rot+scale
                # juntos — e ai o arquivo sai diferente da tela.
                esc = float(tf.get("scale", 1) or 1)
                rot = float(tf.get("rotation", 0) or 0)
                op = float(tf.get("opacity", 1) if tf.get("opacity") is not None else 1)
                px = float(tf.get("posX", 0) or 0)
                py = float(tf.get("posY", 0) or 0)
                cadeia = f"[{in_idx}:v]format=rgba"
                if esc != 1:
                    cadeia += f",scale=iw*{esc:.6g}:ih*{esc:.6g}"
                if rot:
                    rad = rot * math.pi / 180.0
                    # positivo gira em sentido horario, igual ao skia (y desce);
                    # ow/oh=rotw/roth pra nao cortar os cantos girados
                    cadeia += (f",rotate={rad:.6f}:ow=rotw({rad:.6f})"
                               f":oh=roth({rad:.6f}):c=black@0")
                if op < 1:
                    cadeia += f",colorchannelmixer=aa={op:.4f}"
                parts.append(cadeia + f"[tt{k}]")
                # posY positivo SOBE (convencao do painel), overlay y desce
                parts.append(
                    f"[{cur}][tt{k}]overlay=x=(W-w)/2{px:+g}:y=(H-h)/2{-py:+g}"
                    f":enable='between(t,{s_sec},{e_sec})':format=auto[{nxt}]"
                )
            else:
                parts.append(
                    f"[{cur}][{in_idx}:v]overlay=0:0:enable='between(t,{s_sec},{e_sec})':format=auto[{nxt}]"
                )
            cur = nxt
    elif titles_input_idx is None:
        # NATIVE drawtext: chain de drawtext direto na video output
        titles_chain = build_native_titles_chain(cfg.get("titles", []), W, H)
        if titles_chain:
            parts.append(f"[v_with_brolls]{titles_chain}[vout]")
        else:
            parts.append(f"[v_with_brolls]copy[vout]")
    else:
        parts.append(
            f"[v_with_brolls][{titles_input_idx}:v]overlay=0:0:format=auto[vout]"
        )

    return ";".join(parts)


_NVENC_CACHE = {}


def _tem_nvenc(codec_nvenc):
    """A placa aguenta esse encoder? Encoda um quadro preto e ve se volta 0.

    `ffmpeg -encoders` nao serve: ele lista o que foi COMPILADO, e o binario
    padrao traz nvenc, qsv e amf sempre — inclusive numa maquina sem GPU
    nenhuma. So a chamada de verdade responde.
    """
    if codec_nvenc in _NVENC_CACHE:
        return _NVENC_CACHE[codec_nvenc]
    try:
        r = subprocess.run(
            [FFMPEG_EXTERNAL, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "color=c=black:s=320x240:d=0.1",
             "-c:v", codec_nvenc, "-f", "null", "-"],
            capture_output=True, text=True, timeout=30)
        ok = r.returncode == 0
    except Exception:
        ok = False
    _NVENC_CACHE[codec_nvenc] = ok
    return ok


def render_composite(cfg, titles_mov, out_path, ass_path=None,
                     audio_from_source_only=False, video_bitrate="12M",
                     gpu_pipeline=False, force_bw=False, skip_titles=False,
                     codec="h264", test_duration=None, encoder="auto"):
    """Composite final: source + brolls + titles_alpha + audio mix + NVENC.

    Modes:
      gpu_pipeline=False: decode CPU + filtros CPU + NVENC encode (atual)
      gpu_pipeline=True:  NVDEC decode source/brolls + scale_cuda zoom + NVENC encode
                          (titles fica em CPU - ProRes 4444 alpha nao tem CUDA path)

    Inputs do ffmpeg:
      0: source video (com voice)
      1..N_brolls: cada broll mp4
      N_brolls+1: titles alpha MOV
      ...N_audio: SFX + music (se audio_from_source_only=False)
    """
    source = PUBLIC / cfg["videoSrc"]
    if not source.exists():
        log(f"FAIL: source nao encontrado: {source}")
        sys.exit(1)

    # Inputs com hwaccel cuda quando gpu_pipeline=True
    # Cada input precisa do flag -hwaccel/-hwaccel_output_format ANTES do -i
    # Source: gpu_pipeline -> NVDEC
    # Brolls: gpu_pipeline -> NVDEC
    # Titles: SEMPRE CPU (ProRes 4444 alpha nao tem CUDA decode)
    # Audios: nao precisa
    inputs_with_flags = []  # list[(extra_flags, path)]

    inputs_with_flags.append(
        (["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"] if gpu_pipeline else [], str(source))
    )

    brolls_added = []
    # Empilhamento por Z da track: Z maior entra POR CIMA. Ordenar AQUI, antes
    # dos inputs, e' o que mantem os indices do grafo alinhados com os inputs —
    # `brolls_added` alimenta os dois. `sorted` do Python e' estavel, entao
    # dentro do mesmo Z vale a ordem da timeline, igualzinho ao preview.
    for b in sorted(cfg.get("brolls", []), key=lambda x: float(x.get("z", 0) or 0)):
        bsrc = PUBLIC / b["src"]
        if not bsrc.exists():
            log(f"WARN: broll nao encontrado: {bsrc}, skip")
            continue
        # `-itsoffset` alinha o broll com a timeline sem fabricar frame vazio
        # antes dele (ver a nota no filtro, onde o `tpad` foi removido).
        flags = ["-itsoffset", str(b["startSec"])]
        # `srcStart` = ponto de entrada NA FONTE (o corte de entrada do clipe).
        # Como `-ss` de INPUT ele custa zero — o decoder pula direto pro ponto,
        # em vez de decodificar e jogar fora. Junto com o `-itsoffset`: o frame
        # do segundo `srcStart` do arquivo cai no segundo `startSec` da timeline.
        # Sem isto o render tocava todo broll aparado desde o comeco, enquanto o
        # preview ja respeitava o corte — o arquivo saia diferente da tela.
        src_start = float(b.get("srcStart", 0) or 0)
        if src_start > 0:
            flags = ["-ss", f"{src_start:.3f}"] + flags
        if gpu_pipeline:
            flags += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
        inputs_with_flags.append((flags, str(bsrc)))
        brolls_added.append(b)
    n_brolls = len(brolls_added)

    # Titles input: 3 modos
    #  1. titles_mov = None: drawtext nativo (sem input adicional)
    #  2. titles_mov = Path/str: monolithic MOV (1 input) — comportamento legado
    #  3. titles_mov = list[(path, startSec, endSec)]: per-title cache (N inputs com -itsoffset)
    titles_idx = None
    titles_indiv = None  # list of (input_idx, startSec, endSec) for per-title overlay
    if isinstance(titles_mov, list):
        titles_indiv = []
        for item in titles_mov:
            # 3 elementos = caminho antigo (fita, overlay monolitico); o 4o e a
            # transformacao de composicao do titulo (posX/posY/scale/rot/op)
            path, start_sec, end_sec = item[0], item[1], item[2]
            tf = item[3] if len(item) > 3 else {}
            # -itsoffset desloca o input pra alinhar com timeline
            inputs_with_flags.append(([f"-itsoffset", str(start_sec)], str(path)))
            titles_indiv.append((len(inputs_with_flags) - 1, start_sec, end_sec, tf))
    elif titles_mov is not None:
        # ProRes 4444 alpha = libprores CPU only (sem hwaccel)
        inputs_with_flags.append(([], str(titles_mov)))
        titles_idx = len(inputs_with_flags) - 1

    # ── OPT 1: Audio stems fast-path ──
    # Auto-gera stems (voice/sfx/music.wav) se nao existirem ou se sfx/music config mudou.
    # Composite usa apenas 3 audio inputs em vez de 100+ → filter graph trivial,
    # decode paralelo de 3 WAVs (SSD) >> decode sequencial de 100+ MP3 (CPU bound).
    audio_inputs = []
    use_stems = False
    stem_inputs = []  # input indices for voice/sfx/music
    if not audio_from_source_only:
        proj_dir = (PUBLIC / cfg["videoSrc"]).parent
        n_audio = len(cfg.get("sfx", [])) + len(cfg.get("musicTracks", []))
        # Use stems se ha 3+ audios (worth the pre-mix cost) OU stems ja existem
        already_have_stems = all((proj_dir / f"audio_{kind}.wav").exists() for kind in ["voice", "sfx", "music"])
        if n_audio >= 3 or already_have_stems:
            try:
                voice, sfx_path, music_path = ensure_audio_stems(cfg, proj_dir)
                use_stems = True
                for s in [voice, sfx_path, music_path]:
                    inputs_with_flags.append(([], str(s)))
                    stem_inputs.append(len(inputs_with_flags) - 1)
                log(f"  Audio: stems pre-mixed (3 inputs vs {n_audio} individuais)")
            except Exception as e:
                log(f"  Audio stems falhou ({e}) — fallback pra individual mix")

        if not use_stems:
            idx = len(inputs_with_flags)
            for sfx in cfg.get("sfx", []):
                sfx_path = PUBLIC / sfx["src"]
                if not sfx_path.exists():
                    continue
                inputs_with_flags.append(([], str(sfx_path)))
                audio_inputs.append((idx, "sfx", sfx))
                idx += 1
            for mus in cfg.get("musicTracks", []):
                mus_path = PUBLIC / mus["src"]
                if not mus_path.exists():
                    continue
                inputs_with_flags.append(([], str(mus_path)))
                audio_inputs.append((idx, "music", mus))
                idx += 1

    # Build filter graphs
    cfg_brolls_filtered = dict(cfg)
    cfg_brolls_filtered["brolls"] = brolls_added
    # Force B&W test: override colorCorrection.saturation = -100
    if force_bw:
        cc = dict(cfg_brolls_filtered.get("colorCorrection", {}) or {})
        cc["saturation"] = -100
        cfg_brolls_filtered["colorCorrection"] = cc
        log("MODO TESTE P&B: forcando saturation=-100 (saida deve ser preto e branco)")
    video_filter = build_video_filter_graph(cfg_brolls_filtered, n_brolls, titles_idx,
                                             gpu_pipeline=gpu_pipeline,
                                             skip_titles=skip_titles,
                                             titles_indiv=titles_indiv)
    if skip_titles:
        log("MODO --no-titles: pulando overlay do titles.mov no composite (cache continua valido)")

    # ── Fonte sem trilha de audio ────────────────────────────────────────
    # Um mp4 mudo derrubava o composite: o grafo de audio referencia [0:a],
    # que nao existe, e o ffmpeg morre com "Error binding filtergraph
    # inputs/outputs" — mensagem que nao diz nada a ninguem. Em vez de proibir
    # fonte muda, entra um anullsrc como trilha silenciosa. Adicionado por
    # ULTIMO nos inputs de proposito: no meio, deslocaria os indices de todos
    # os brolls e titulos ja mapeados no grafo.
    src_audio = "0:a"
    if not _fonte_tem_audio(source):
        inputs_with_flags.append(
            (["-f", "lavfi", "-t", str(cfg.get("videoDuration", 60))],
             "anullsrc=r=48000:cl=stereo"))
        src_audio = f"{len(inputs_with_flags) - 1}:a"
        log("  Fonte sem trilha de audio -> anullsrc silencioso no lugar dela")

    if audio_from_source_only:
        filter_complex = video_filter
        audio_map = ["-map", src_audio]
    elif use_stems:
        # Mix dos 3 stems (voice + sfx + music ja mixados em inputs separados)
        # voice em 1.0, sfx em 1.0, music em 1.0 (volumes ja embutidos nos stems)
        stems_filter = (
            f"[{stem_inputs[0]}:a]volume={0.0 if cfg.get('videoMuted') else float(cfg.get('videoVolume', 1) or 0):.4f}[svoice];"
            f"[{stem_inputs[1]}:a]volume=1.0[ssfx];"
            f"[{stem_inputs[2]}:a]volume=1.0[smusic];"
            f"[svoice][ssfx][smusic]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0[aout]"
        )
        filter_complex = video_filter + ";" + stems_filter
        audio_map = ["-map", "[aout]"]
    else:
        audio_filter, audio_label = build_audio_filter_graph(cfg, audio_inputs, src_audio=src_audio)
        filter_complex = video_filter + ";" + audio_filter
        audio_map = ["-map", audio_label]

    pipeline_label = "GPU pipeline (NVDEC+scale_cuda+NVENC)" if gpu_pipeline else "NVENC encode-only"
    log(f"Composite [{pipeline_label}]: 1 source + {n_brolls} brolls + 1 titles + {len(audio_inputs)} audios -> {out_path.name}")
    log(f"  filter_complex: {len(filter_complex)} chars")

    # Build ffmpeg cmd
    cmd = [FFMPEG_EXTERNAL, "-y", "-hide_banner", "-loglevel", "warning"]
    for flags, inp in inputs_with_flags:
        cmd.extend(flags)
        cmd.extend(["-i", inp])
    # Write filter_complex to file pra evitar Windows cmdline limit (~32K)
    # com 100+ SFX inputs o filter graph fica muito grande pra inline arg
    filter_script = out_path.parent / f".forge_filter_{out_path.stem}.txt"
    filter_script.write_text(filter_complex, encoding="utf-8")
    cmd.extend(["-filter_complex_script", str(filter_script)])
    if ass_path:
        # o ass entra DEPOIS de tudo (fonte+brolls+titulos), como nos editores
        filter_complex += f";[vout]ass={ass_path}[vsub]"
        filter_script.write_text(filter_complex, encoding="utf-8")
    cmd.extend(["-map", "[vsub]" if ass_path else "[vout]"])
    cmd.extend(audio_map)
    # NVENC config: qualidade ALTA (visualmente proxima de x264 crf=18) 100% GPU.
    # preset=p7 = slowest NVENC (melhor compressao), cq adjustado por codec
    # multipass=fullres = 2-pass NVENC (melhor distribuicao de bits)
    # AQ (adaptive quantization) espacial + temporal = preserva detalhe em areas planas
    # rc-lookahead=32 = ve 32 frames a frente pra decidir quantizacao
    nvenc_codec_map = {
        "h264": ("h264_nvenc", "19"),    # universal, cq=19
        "h265": ("hevc_nvenc", "21"),    # -40% tamanho, cq~21 equivale visualmente a h264 cq=19
        "av1":  ("av1_nvenc",  "23"),    # ainda menor, RTX 40+/50 only
    }
    nvenc_codec, nvenc_cq = nvenc_codec_map.get(codec, nvenc_codec_map["h264"])

    # encoder: "auto" | "gpu" | "cpu". (Nao confundir com --gpu, que liga o
    # pipeline CUDA inteiro — decode e zoom na placa. Aqui e so o encode.)
    # Ate aqui NVENC era o unico caminho: numa maquina sem placa NVIDIA o
    # render nao ficava lento, ele MORRIA no fim, depois do trabalho todo
    # feito. "auto" pergunta antes e cai pra CPU em vez de perder tudo.
    usar_gpu = {"gpu": True, "cpu": False}.get(encoder, _tem_nvenc(nvenc_codec))
    if encoder == "auto" and not usar_gpu:
        log("  NVENC nao respondeu nesta maquina -> encodando na CPU")

    # FPS output forcado pra evitar VFR que causa A/V desync.
    # Source 24fps + titles_indiv 30fps + brolls fps variavel -> sem -r/fps_mode
    # ffmpeg pode gerar saida com timestamps inconsistentes -> drift audio↔video.
    out_fps = int(cfg.get("fps", 30))

    if usar_gpu:
        log(f"  Codec: {codec} -> {nvenc_codec} (GPU, cq={nvenc_cq})")
        cmd.extend([
            "-c:v", nvenc_codec,
            "-preset", "p7", "-tune", "hq",
            "-rc", "vbr", "-cq", nvenc_cq,
            "-b:v", "0",
            "-multipass", "fullres",
            "-rc-lookahead", "32",
            "-spatial-aq", "1", "-temporal-aq", "1",
            "-aq-strength", "8",
            "-bf", "3",
        ])
    else:
        # CRF equivalente ao cq do NVENC. x264/x265 sao mais eficientes por
        # bit, entao o mesmo numero ja sai melhor — e MUITO mais devagar.
        cpu_codec, cpu_crf = {
            "h264": ("libx264", "19"),
            "h265": ("libx265", "23"),
            "av1":  ("libsvtav1", "30"),
        }.get(codec, ("libx264", "19"))
        log(f"  Codec: {codec} -> {cpu_codec} (CPU, crf={cpu_crf}) — conte varios minutos a mais")
        cmd.extend(["-c:v", cpu_codec, "-preset", "slow" if cpu_codec != "libsvtav1" else "6",
                    "-crf", cpu_crf, "-pix_fmt", "yuv420p"])

    cmd.extend([
        # FIX desync: forca CFR no fps configurado SEM mexer no audio.
        # -async 1 estava REMOVENDO samples de pausas pra "alinhar" audio com video,
        # cortando silencios da fala. Solucao: video CFR + audio puro (sem resample).
        "-r", str(out_fps),
        "-fps_mode", "cfr",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        # Garante duracao = duracao do source (ou test_duration se setado)
        "-t", str(test_duration if test_duration else cfg["videoDuration"]),
        str(out_path),
    ])

    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t0

    if r.returncode != 0:
        log(f"FFMPEG FAIL ({elapsed:.1f}s):")
        print(r.stderr[-3000:])
        sys.exit(1)

    # Cleanup filter script
    try: filter_script.unlink()
    except: pass

    sz_mb = out_path.stat().st_size / 1024 / 1024
    log(f"Composite OK em {elapsed:.1f}s | {sz_mb:.1f} MB | {out_path}")
    return out_path, elapsed, sz_mb


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="Nome do MP4 de saida (default: forge_render_TIMESTAMP.mp4)")
    ap.add_argument("--no-cache", action="store_true", help="Forca re-render dos overlays (ignora cache)")
    ap.add_argument("--audio-from-source", action="store_true", help="Pula mix de SFX/music, usa so audio do source")
    ap.add_argument("--bitrate", default="12M", help="Video bitrate alvo (default 12M)")
    ap.add_argument("--gpu", action="store_true",
                    help="Modo GPU pipeline: NVDEC decode + scale_cuda zoom + NVENC encode (mais rapido, mas tem incompat com alguns setups)")
    ap.add_argument("--encoder", default="auto", choices=["auto", "gpu", "cpu"],
                    help="Onde ENCODAR o video final. auto testa a placa e cai pra CPU se ela nao responder (default). Diferente de --gpu, que muda o pipeline inteiro.")
    ap.add_argument("--bw", action="store_true",
                    help="Teste color correction: forca saturation=-100 (preto e branco)")
    ap.add_argument("--no-titles", action="store_true",
                    help="Skip overlay do titles.mov no composite final (cache continua valido)")
    ap.add_argument("--no-captions", action="store_true",
                    help="Forca showCaptions=False no overlay (invalida cache, re-render motor de navegador)")
    ap.add_argument("--codec", default="h264", choices=["h264", "h265", "av1"],
                    help="Codec NVENC: h264 (universal) | h265 (-40%% tamanho) | av1 (RTX 40+/50)")
    # PADRAO desde que o MotionCore passou a cobrir os estilos: este caminho
    # manda cada title pro Skia e so o que nao estiver portado vai pro Chrome.
    # Era opt-in, e ai a UI (que sempre manda a flag) e a linha de comando (que
    # nao mandava) tomavam ramos DIFERENTES do render — a linha de comando caia
    # no TitlesOverlay monolitico do motor de navegador. Mesmo config, mesmo script,
    # tempos de 17s e 17min. Divergencia entre os dois e justamente o que nao
    # pode existir aqui.
    ap.add_argument("--per-title", dest="per_title", action="store_true", default=True,
                    help="(PADRAO) Renderiza cada title separado, cache por hash, "
                         "MotionCore primeiro e o motor de navegador so pro que falta portar.")
    ap.add_argument("--monolitico", dest="per_title", action="store_false",
                    help="Caminho antigo: TitlesOverlay monolitico via motor de navegador. "
                         "So pra depurar — e ordens de magnitude mais lento.")
    ap.add_argument("--test-duration", type=float, default=None,
                    help="Renderiza apenas os primeiros N segundos (pra testar sync rapido sem render completo)")
    ap.add_argument("--per-title-workers", type=int, default=8,
                    help="Renders paralelos com --per-title (default 8; i9-14900F aguenta, RAM ~74%% em 1080p)")
    ap.add_argument("--config", default=None,
                    help="Caminho de um edit_config alternativo (default: public/edit_config.json). "
                         "Usado pra render de trecho: config com videoDuration curto = overlay curto.")
    args = ap.parse_args()

    global EDIT_CONFIG
    if args.config:
        EDIT_CONFIG = Path(args.config)

    if not EDIT_CONFIG.exists():
        log(f"FAIL: edit_config.json nao encontrado em {EDIT_CONFIG}")
        sys.exit(1)

    if not Path(FFMPEG_EXTERNAL).exists():
        log(f"FAIL: ffmpeg externo nao encontrado em {FFMPEG_EXTERNAL}")
        sys.exit(1)

    cfg = json.loads(EDIT_CONFIG.read_text(encoding="utf-8"))
    out_name = args.out or f"forge_render_{int(time.time())}.mp4"
    # `--out` aceita caminho completo (o usuario escolhe a pasta no modal, como
    # em qualquer editor) ou so o nome, que cai em output/ como antes.
    _o = Path(out_name)
    out_path = _o if _o.is_absolute() else _pasta_de_saida(cfg) / _o.name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    log(f"=== ForgeRender Lite started ===")
    log(f"Source: {cfg['videoSrc']} | duration={cfg['videoDuration']}s fps={cfg.get('fps', 30)}")
    log(f"Titles: {len(cfg.get('titles', []))} | Brolls: {len(cfg.get('brolls', []))} | SFX: {len(cfg.get('sfx', []))} | Music: {len(cfg.get('musicTracks', []))}")
    log(f"Output: {out_path}")

    t_total = time.time()

    # Step 1: ensure titles MOVs (cache or render)
    ass_rel = None
    if args.per_title:
        # Phase 2: per-title cache. Cada title eh um MOV separado.
        # Captions E SHAPES precisam de TitlesOverlay monolithic separado:
        # - per-title renderiza so individual titles, nao processa shapes nem captions
        # - shapes/captions vao num overlay monolithic adicional
        has_shapes = bool(cfg.get("shapes"))
        # showCaptions default True (matches build_overlay_props default)
        cfg_show_captions = cfg.get("showCaptions", True) and len(cfg.get("captions") or []) > 0
        wants_captions = cfg_show_captions and not args.no_captions
        # BARRA DE PROGRESSO: vive no overlay monolitico. Antes so era renderizada
        # quando havia legenda ou forma — desligar a legenda fazia a barra sumir
        # do render (user 2026-07-31: "tem que sair igual aos outros, so nao sai
        # se eu tirar"). Agora ela sozinha ja justifica o monolitico.
        wants_bar = bool(cfg.get("showProgressBar", True))
        # Legenda dinamica via libass: quando TODOS os estilos em uso cabem no
        # ASS, a legenda sai do overlay (que custava 267s no video de 12min) e
        # e queimada de graca dentro do composite que ja ia acontecer.
        ass_rel = None
        if wants_captions and MC_DISPONIVEL:
            try:
                from motioncore.caption_ass import expressa_em_ass, gerar
                if expressa_em_ass(cfg):
                    dest = CACHE_BASE / "captions.ass"
                    gerar(cfg, dest)
                    ass_rel = dest.relative_to(ROOT).as_posix()
                    wants_captions = False
                    log(f"  Legenda via libass ({ass_rel}) — overlay fica so com a barra")
            except Exception as e:
                log(f"  ASS WARN: {e} — legenda segue no overlay")
        if has_shapes or wants_captions or wants_bar:
            extras = []
            if has_shapes: extras.append("shapes")
            if wants_captions: extras.append("captions")
            if wants_bar: extras.append("barra")
            log(f"  Per-title + monolithic overlay ({'+'.join(extras)})...")
            # Render TitlesOverlay so com shapes+captions (titles vazios = nao duplica)
            cfg_extra = dict(cfg)
            cfg_extra["titles"] = []
            # Se nao quer captions, override
            extra_mov = ensure_titles_overlay(
                cfg_extra, force=args.no_cache,
                force_no_captions=(not wants_captions),
            )
            indiv_titles = ensure_individual_titles(cfg, force=args.no_cache, max_workers=args.per_title_workers)
            # O composite paga por ENTRADA, nao por operacao: 44 titulos viram
            # 44 decoders + uma corrente de 44 `overlay` (filter_complex de 20 mil
            # chars). Juntar numa fita so, sem re-encode, tira ~3 min do render.
            # A fita cola varios MOVs num so — titulo COM transformacao de
            # composicao nao pode entrar nela, senao a transformacao dele
            # seria aplicada (ou perdida) em bloco. Neutros vao pra fita,
            # transformados seguem como entradas proprias.
            neutros = [it for it in indiv_titles if not (len(it) > 3 and it[3])]
            transformados = [it for it in indiv_titles if len(it) > 3 and it[3]]
            if (MC_DISPONIVEL and len(neutros) > 1
                    and os.environ.get("KLIPE_MERGE_TITLES", "1") != "0"):
                try:
                    from motioncore.merge_titles import merge
                    fita = merge([(it[0], it[1], it[2]) for it in neutros],
                                 CACHE_BASE / "titles_fita.mov",
                                 int(cfg.get("width", 1920)), int(cfg.get("height", 1080)),
                                 float(cfg.get("fps", 30)), float(cfg["videoDuration"]),
                                 ffmpeg=FFMPEG_EXTERNAL, log=log)
                    if fita is not None:
                        indiv_titles = [(fita, 0, cfg["videoDuration"])] + transformados
                except Exception as e:
                    log(f"    merge WARN: {e} — seguindo com as entradas separadas")
            # Combina: shapes/captions monolithic + individual titles
            titles = [(extra_mov, 0, cfg["videoDuration"])] + indiv_titles
        else:
            titles = ensure_individual_titles(cfg, force=args.no_cache, max_workers=args.per_title_workers)
    elif args.no_titles:
        # --no-titles: nao renderizar o TitlesOverlay monolitico (18min de render por navegador)
        # so pra ignorar no composite — render_composite trata titles_mov=None.
        titles = None
    elif _camada_titulos_vazia(cfg, args):
        # NADA pra desenhar nessa camada: sem titulo, sem shape, e sem legenda
        # (ou legendas desligadas). Renderizar assim mesmo custou 900s de
        # motor de navegador + 84s de transcode pra produzir 1,2 GB de transparencia —
        # 15 dos 16,8 minutos de um render completo, pra sobrepor coisa nenhuma.
        log("Camada de titulos VAZIA (0 titulos, 0 shapes, 0 legendas) — pulando "
            "O motor de navegador. Use --no-cache se quiser forcar.")
        titles = None
    else:
        titles = ensure_titles_overlay(cfg, force=args.no_cache, force_no_captions=args.no_captions)

    # Step 2: composite (source + brolls via overlay enable + titles alpha + audio mix) + NVENC
    out_path, composite_elapsed, sz_mb = render_composite(
        cfg, titles, out_path,
        ass_path=ass_rel,
        audio_from_source_only=args.audio_from_source,
        video_bitrate=args.bitrate,
        gpu_pipeline=args.gpu,
        force_bw=args.bw,
        skip_titles=args.no_titles,
        codec=args.codec,
        test_duration=args.test_duration,
        encoder=args.encoder,
    )

    total = time.time() - t_total
    log(f"=== DONE em {total:.1f}s ({total/60:.1f}min) | {sz_mb:.1f} MB ===")
    log(f"Output: {out_path}")


if __name__ == "__main__":
    main()
