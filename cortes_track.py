# -*- coding: utf-8 -*-
"""TRACK DE CORTE — fluxo em 2 etapas (ideia do user, estilo paginas do DaVinci).

  python cortes_track.py detectar   -> PROPOE cortes em cfg["cutMarks"] (nao corta nada)
  python cortes_track.py aplicar    -> aplica os cutMarks, remapeia tudo, refaz legendas

Por que existe: cortar e remapear de uma vez so nao deixa margem pra revisao, e
os erros sao sempre de fracao de segundo (a cauda da palavra). Propondo primeiro,
o user ve as marcas vermelhas na timeline, arrasta a borda de cada uma, apaga o
que nao quer — e so entao manda aplicar.
"""
import json, math, os, re, subprocess, sys, wave, bisect, shutil, time
import numpy as np

FF = "C:/ffmpeg/bin/ffmpeg.exe"
FPS = 30
ROOT = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(ROOT, "public", "edit_config.json")


def proj_dir(cfg):
    src = cfg.get("videoSrc", "")
    d = os.path.join(ROOT, "public", os.path.dirname(src))
    return d if os.path.isdir(d) else os.path.join(ROOT, "public")


def carregar_audio(video, wav):
    subprocess.run([FF, "-y", "-v", "error", "-i", video, "-vn", "-ac", "1",
                    "-ar", "16000", "-c:a", "pcm_s16le", wav], check=True)
    wf = wave.open(wav, "rb")
    sr = wf.getframerate()
    a = np.abs(np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.int32))
    wf.close()
    return a, sr


def detectar():
    cfg = json.load(open(CFG, encoding="utf-8"))
    pd = proj_dir(cfg)
    video = os.path.join(ROOT, "public", cfg["videoSrc"])
    bkp = video.replace(".mp4", "_PRE_CORTES.mp4")
    if os.path.exists(bkp):
        video = bkp          # marcas sempre no tempo do ORIGINAL
    wav = os.path.join(pd, "_cortes_audio.wav")
    a, SR = carregar_audio(video, wav)
    import subprocess as _sp
    D0 = round(float(_sp.run(["C:/ffmpeg/bin/ffprobe.exe","-v","error","-show_entries",
        "format=duration","-of","csv=p=0", video], capture_output=True, text=True).stdout.strip()), 3)

    def pk(t0, d):
        i, j = max(0, int(t0 * SR)), min(len(a), int((t0 + d) * SR))
        return -90.0 if j <= i else 20 * math.log10(max(int(a[i:j].max()), 1) / 32768.0)

    from faster_whisper import WhisperModel
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    segs, _ = model.transcribe(wav, language="pt", word_timestamps=True, vad_filter=True,
                               vad_parameters={"min_silence_duration_ms": 300}, beam_size=5)
    words = [(w.start, w.end) for s in segs for w in (s.words or [])]

    # mesmas margens validadas em 2026-07-31 (ver feedback_cut_validation_audio)
    GAP_MIN, PAD_POS, PAD_ANTES, DB_CAUDA, DB_ONSET = 0.75, 0.32, 0.20, -28, -24
    marcas = []
    for i in range(len(words) - 1):
        gap = words[i + 1][0] - words[i][1]
        if gap < GAP_MIN:
            continue
        cs, ce = words[i][1] + PAD_POS, words[i + 1][0] - PAD_ANTES
        if ce - cs < 0.20 or cs < 0.5 or ce > D0 - 1.0:
            continue
        ok = False
        for _ in range(5):
            if pk(cs - 0.16, 0.16) <= DB_CAUDA:
                ok = True
                break
            cs += 0.06
        if not ok or ce - cs < 0.20:
            continue
        if pk(ce, 0.14) > DB_ONSET:
            ce = words[i + 1][0] - 0.30
            if ce - cs < 0.20:
                continue
        cs, ce = round(cs * FPS) / FPS, round(ce * FPS) / FPS
        if ce - cs < 0.20:
            continue
        if marcas and cs - marcas[-1]["endSec"] < 0.20:
            continue
        marcas.append({"id": f"cut{len(marcas):03d}", "startSec": round(cs, 3),
                       "endSec": round(ce, 3), "tipo": "pausa", "info": f"{gap:.2f}s"})

    cfg["cutMarks"] = marcas
    for p in (CFG, os.path.join(pd, "edit_config.json")):
        if os.path.isdir(os.path.dirname(p)):
            json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    total = sum(m["endSec"] - m["startSec"] for m in marcas)
    print(json.dumps({"ok": True, "cutMarks": marcas, "total": round(total, 2)}, ensure_ascii=False))


def _mapa(cortes, dur_origem):
    """Devolve (para_cortado, para_origem, nova_duracao) pra uma lista de cortes."""
    cs = [c[0] for c in cortes]; ce = [c[1] for c in cortes]
    off, acc = [], 0.0
    for a, b in cortes:
        acc += b - a; off.append(acc)
    nd = round(dur_origem - acc, 3)

    def para_cortado(t):
        i = bisect.bisect_right(cs, t) - 1
        if i >= 0 and t < ce[i]:
            t = ce[i]
        i = bisect.bisect_right(ce, t) - 1
        return max(0.0, min(nd, t - (off[i] if i >= 0 else 0)))

    def para_origem(t):
        # inverso: soma de volta tudo que foi removido antes desse ponto
        acc2 = 0.0
        for (a, b) in cortes:
            if a - acc2 <= t + 1e-6:
                acc2 += b - a
            else:
                break
        return t + acc2

    return para_cortado, para_origem, nd


def regerar_splits(cfg, pd):
    """Remonta os split-screen (feather blend) nas posicoes NOVAS.

    O split nao e um b-roll comum: ele ja tem o video principal embutido. Depois
    de qualquer corte, o arquivo antigo mostra o trecho errado — a voz vem do
    video novo e a imagem do velho. Por isso todo apply tem que reconstruir.
    """
    video = os.path.join(pd, "video_cut.mp4")
    mask = os.path.join(pd, "assets", "feather_mask_1020.png")
    mapa_path = os.path.join(pd, "splits_map.json")
    if not (os.path.exists(video) and os.path.exists(mask)):
        return 0
    # mapa split -> broll de origem (persistido; sem ele nao da pra remontar)
    try:
        MAPA = json.load(open(mapa_path, encoding="utf-8"))
    except Exception:
        return 0

    ok = 0
    for b in cfg.get("brolls", []):
        nome = os.path.basename(b.get("src", ""))
        src = MAPA.get(nome)
        if not src:
            continue
        fonte = os.path.join(pd, "brolls", src)
        if not os.path.exists(fonte):
            continue
        t0 = float(b["startSec"]); dur = round(float(b["endSec"]) - t0, 3)
        r = subprocess.run([
            FF, "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", video,
            "-stream_loop", "-1", "-i", fonte, "-i", mask, "-filter_complex",
            "[0:v]setpts=PTS-STARTPTS[t];"
            "[1:v]scale=1080:-1:force_original_aspect_ratio=increase,crop=1080:1020,setpts=PTS-STARTPTS[b];"
            "[2:v]format=gray[m];[b][m]alphamerge[ba];[t][ba]overlay=0:900[v]",
            "-map", "[v]", "-an", "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "22",
            "-pix_fmt", "yuv420p", "-t", f"{dur:.3f}",
            os.path.join(pd, "splits", nome)], capture_output=True, text=True)
        if r.returncode == 0:
            ok += 1
    return ok


def aplicar():
    """Reconstroi SEMPRE a partir do video ORIGINAL usando os cutMarks atuais.

    Isso e o que deixa o fluxo CUT <-> EDIT reversivel: mexer numa marca e
    aplicar de novo nao acumula perda, porque o corte nunca e feito em cima de
    um video ja cortado. Os elementos do config sao levados do tempo CORTADO
    atual -> tempo do ORIGINAL -> tempo do corte NOVO.
    """
    cfg = json.load(open(CFG, encoding="utf-8"))
    pd = proj_dir(cfg)
    marcas = sorted(cfg.get("cutMarks", []), key=lambda m: m["startSec"])
    if not marcas:
        print(json.dumps({"error": "sem cutMarks"}))
        return

    video = os.path.join(ROOT, "public", cfg["videoSrc"])
    bkp = video.replace(".mp4", "_PRE_CORTES.mp4")
    if not os.path.exists(bkp):
        shutil.copy(video, bkp)          # 1a vez: o atual VIRA o original

    # duracao real do ORIGINAL (fonte de verdade das marcas)
    pr = subprocess.run(["C:/ffmpeg/bin/ffprobe.exe", "-v", "error", "-show_entries",
                         "format=duration", "-of", "csv=p=0", bkp],
                        capture_output=True, text=True)
    D_ORIG = round(float(pr.stdout.strip()), 3)

    CORTES = [(round(float(m["startSec"]) * FPS) / FPS, round(float(m["endSec"]) * FPS) / FPS)
              for m in marcas]
    CORTES = [(a, b) for a, b in CORTES if b - a >= 0.10]
    novo_para_cortado, _, ND = _mapa(CORTES, D_ORIG)

    # marcas JA aplicadas no video atual (pra converter cortado -> original)
    aplicadas = [(float(m["startSec"]), float(m["endSec"]))
                 for m in sorted(cfg.get("appliedCutMarks", []), key=lambda m: m["startSec"])]
    _, atual_para_origem, _ = _mapa(aplicadas, D_ORIG) if aplicadas else (None, (lambda t: t), None)

    D0 = D_ORIG
    keeps, pos = [], 0.0
    for a, b in CORTES:
        if a > pos:
            keeps.append((pos, a))
        pos = b
    if pos < D0:
        keeps.append((pos, D0))

    fc = []
    for i, (a, b) in enumerate(keeps):
        fc.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}];")
        fc.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{i}];")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(len(keeps))) +
              f"concat=n={len(keeps)}:v=1:a=1[v][a]")
    script = os.path.join(pd, "_cortes_fc.txt")
    open(script, "w").write("".join(fc))
    tmp = os.path.join(pd, "_cortes_tmp.mp4")
    r = subprocess.run([FF, "-y", "-v", "error", "-i", bkp, "-filter_complex_script", script,
                        "-map", "[v]", "-map", "[a]", "-c:v", "h264_nvenc", "-preset", "p5",
                        "-cq", "19", "-pix_fmt", "yuv420p", "-g", "30",
                        "-c:a", "aac", "-b:a", "192k", tmp], capture_output=True, text=True)
    if r.returncode != 0:
        print(json.dumps({"error": r.stderr[-400:]}))
        return
    for _ in range(10):                      # Windows costuma segurar o handle
        try:
            os.remove(video); break
        except PermissionError:
            time.sleep(1.0)
    os.rename(tmp, video)

    # cortado-atual -> original -> cortado-novo
    def m(t):
        return novo_para_cortado(atual_para_origem(t))

    def dentro_de_corte(t_origem):
        """True se esse instante do ORIGINAL cai num trecho que sai."""
        for a, b in CORTES:
            if a - 1e-6 <= t_origem < b + 1e-6:
                return True
        return False

    def remap(arr, md):
        out = []
        for o in arr:
            # elemento inteiramente dentro de um trecho removido: descarta
            if dentro_de_corte(atual_para_origem(float(o["startSec"]))) and                dentro_de_corte(atual_para_origem(float(o["endSec"]))):
                continue
            s, e = m(float(o["startSec"])), m(float(o["endSec"]))
            if e - s < md or s >= ND - 0.05:
                continue
            o["startSec"], o["endSec"] = round(s, 3), round(e, 3)
            out.append(o)
        return out

    cfg["titles"] = remap(cfg.get("titles", []), 0.15)
    cfg["zooms"] = remap(cfg.get("zooms", []), 0.30)
    cfg["brolls"] = remap(cfg.get("brolls", []), 0.80)
    cfg["musicTracks"] = remap(cfg.get("musicTracks", []), 1.00)
    # SFX que cai DENTRO de um trecho removido tem que ser DESCARTADO, nao
    # empurrado pro ponto da emenda — senao varios colapsam no mesmo instante e
    # tocam empilhados (user 2026-07-31: "um monte de sfx sobreposta").
    sfx, empilhados = [], 0
    ocupado = []
    for o in sorted(cfg.get("sfx", []), key=lambda x: float(x["startSec"])):
        span = float(o["endSec"]) - float(o["startSec"])
        t_org = atual_para_origem(float(o["startSec"]))
        if dentro_de_corte(t_org):
            empilhados += 1
            continue
        s = novo_para_cortado(t_org)
        if s >= ND - 0.05:
            continue
        # rede de seguranca: 2 SFX no MESMO ponto = fica o de maior volume
        if ocupado and abs(ocupado[-1][0] - s) < 0.02:
            if (o.get("volume", 1) or 1) <= ocupado[-1][1]:
                empilhados += 1
                continue
            sfx.pop(); ocupado.pop()
        o["startSec"] = round(s, 3)
        o["endSec"] = round(min(s + span, ND), 3)   # SFX preserva a duracao do clip
        sfx.append(o)
        ocupado.append((s, o.get("volume", 1) or 1))
    cfg["sfx"] = sfx
    if empilhados:
        print(f"[cortes] {empilhados} SFX descartados (caiam em trecho cortado)", file=sys.stderr)
    cfg["videoDuration"] = ND
    for vc in cfg.get("videoClips", []):
        # startSec tambem precisa voltar pra 0: o clip do video passa a cobrir
        # o arquivo NOVO (que ja nasce so com o trecho mantido) do comeco ao
        # fim. Ficou faltando aqui — so aparecia quando o trecho mantido nao
        # comecava em 0 (ex.: importar so um pedaco do meio de um video longo),
        # porque no caso comum (tirar pausa dentro de um video que ja comeca
        # em 0) startSec ja era 0 e o bug nao tinha como aparecer.
        vc["startSec"] = 0; vc["endSec"] = ND; vc["baseDurationSec"] = ND
    # cutMarks PERMANECEM (sao a fonte de verdade da pagina CUT) e viram tambem
    # o registro do que esta baked no video atual — e isso que permite voltar
    # pro CUT, puxar uma borda e reaplicar sem perder fala.
    cfg["appliedCutMarks"] = [{"startSec": a, "endSec": b} for a, b in CORTES]
    cfg["captions"] = []          # refeitas do audio novo
    for p in (CFG, os.path.join(pd, "edit_config.json")):
        if os.path.isdir(os.path.dirname(p)):
            json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # SPLITS: sao pre-montados com o video principal EMBUTIDO (feather blend).
    # Se nao regerar, cada split continua mostrando o momento ANTIGO do video
    # enquanto a voz vem do novo — imagem e audio deixam de bater no b-roll.
    n_split = regerar_splits(cfg, pd)

    # legendas do AUDIO FINAL (sem remap = sem erro acumulado)
    rc = os.path.join(pd, "_rebuild_captions.py")
    if os.path.exists(rc):
        subprocess.run([sys.executable, rc], cwd=pd, capture_output=True, text=True)
    print(json.dumps({"ok": True, "duracao": ND, "cortes": len(CORTES), "splits": n_split}))


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "detectar"
    (detectar if acao == "detectar" else aplicar)()
