#!/usr/bin/env python
"""
Aplica plano de edicao completo no projeto domingo-com-ritalina.

Pipeline:
  1. Concatena ranges do source via ffmpeg → video_edited.mp4
  2. Renomeia: video.mp4 → video_original.mp4, video_edited → video.mp4
  3. Regenera video_preview.mp4
  4. Re-transcreve (faster-whisper GPU)
  5. Gera edit_config.json com 9:16 + titulos por bloco + captions karaoke + musica
"""
import sys, os, json, subprocess, shutil, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJ = ROOT / "public" / "projects" / "domingo-com-ritalina"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

# (source_start_sec, source_end_sec, label) — cuts conforme plano de edicao
KEEPS = [
    (0.24, 5.72,    "hook+identity"),
    (8.26, 17.88,   "trauma_inicio"),
    (23.08, 27.40,  "primeira_festinha"),
    (29.96, 48.64,  "festa_quase_ninguem_vulnerabilidade"),
    (48.64, 65.72,  "gestacao_expectativa"),
    (65.72, 73.44,  "qualidade_presentes"),
    (73.44, 82.24,  "filho_merece_revoltada"),
    (83.10, 90.64,  "triste_criei_trauma"),
    (90.64, 100.36, "nunca_comemorei_rejeicao"),
    (105.38, 119.58, "terapia_rei_leao"),
    (124.62, 134.04, "barreiras_muros"),
    (137.20, 149.58, "fugir_problema"),
    (149.58, 156.34, "processo_terapeutico"),
    (167.76, 197.02, "dia27_vou_casar_renovacao"),
    (197.02, 204.06, "ansiedade_insonia"),
    (213.46, 222.10, "16_anos_juntos"),
    (225.64, 232.66, "nao_solucao_relato"),
    (233.06, 243.52, "desabafo_espelho_daniel"),
    (244.40, 254.48, "marido_estado_crise"),
    (259.92, 268.36, "dificuldade_falar"),
    (273.02, 281.82, "amor_preciso_conversar_escrever"),
    (283.90, 290.76, "nao_responda_so_leia"),
    (294.22, 305.52, "diferente_diario_chat"),
    (317.78, 325.16, "nao_precisa_aprovacao"),
    (330.18, 333.00, "comemorar_realizacao"),
    (341.50, 349.20, "festa_pra_gente"),
    (386.96, 396.72, "nao_se_sinta_so"),
    (405.98, 416.56, "consolada_outras_pessoas"),
    (417.88, 423.16, "nao_esta_sozinha"),
    (430.30, 437.62, "preste_atencao_agora"),
    (482.28, 493.30, "pequenas_coisas_vitoriosa"),
    (497.48, 498.06, "beijo"),
]

# Timeline mapping (start_in_cut, end_in_cut, label)
def build_timeline_map():
    timeline = []
    cursor = 0.0
    for src_start, src_end, label in KEEPS:
        dur = src_end - src_start
        timeline.append({
            "src_start": src_start,
            "src_end": src_end,
            "tl_start": cursor,
            "tl_end": cursor + dur,
            "label": label,
        })
        cursor += dur
    return timeline, cursor

def cut_video(timeline, total_dur, src_path, out_path):
    """Concatena ranges via ffmpeg filter_complex (single pass, sem temp files)."""
    print(f"[1/4] Cutting video → {out_path.name} ({total_dur:.1f}s expected)")
    if out_path.exists() and out_path.stat().st_size > 1_000_000:
        print(f"      Reusando existente ({out_path.stat().st_size//1024//1024}MB)")
        return

    # Build filter_complex pra concatenar com trim+setpts
    filters = []
    streams = []
    for i, t in enumerate(timeline):
        filters.append(f"[0:v]trim={t['src_start']:.3f}:{t['src_end']:.3f},setpts=PTS-STARTPTS[v{i}]")
        filters.append(f"[0:a]atrim={t['src_start']:.3f}:{t['src_end']:.3f},asetpts=PTS-STARTPTS[a{i}]")
        streams.extend([f"[v{i}]", f"[a{i}]"])
    concat = "".join(streams) + f"concat=n={len(timeline)}:v=1:a=1[vout][aout]"
    filter_complex = ";".join(filters) + ";" + concat

    # Write filter to file pra evitar Windows cmdline limit
    fc_file = out_path.parent / "_edit_filter.txt"
    fc_file.write_text(filter_complex, encoding="utf-8")

    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
        "-i", str(src_path),
        "-filter_complex_script", str(fc_file),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "h264_nvenc", "-preset", "p7", "-cq", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"FAIL ffmpeg cut: {r.stderr[-1000:]}")
        sys.exit(1)
    fc_file.unlink(missing_ok=True)
    print(f"      OK {out_path.stat().st_size//1024//1024}MB")

def make_preview(src, out):
    print(f"[2/4] Generating preview → {out.name}")
    if out.exists() and out.stat().st_size > 100_000:
        print(f"      Reusando existente")
        return
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(src), "-vf", "scale=1920:1080",
           "-c:v", "libx264", "-b:v", "1500k", "-preset", "fast",
           "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "128k", str(out)]
    subprocess.run(cmd, check=True)
    print(f"      OK {out.stat().st_size//1024//1024}MB")

def re_transcribe(src, out_json):
    print(f"[3/4] Re-transcribing → {out_json.name}")
    if out_json.exists() and out_json.stat().st_size > 1000:
        print(f"      Reusando existente")
        return
    from faster_whisper import WhisperModel
    try:
        model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    except Exception:
        model = WhisperModel("large-v3", device="cpu", compute_type="int8")
    segments_iter, info = model.transcribe(str(src), language="pt", beam_size=5, vad_filter=True)
    segments = [{"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()} for s in segments_iter]
    out_json.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      OK {len(segments)} segments")

# Block-level titles (synced with cut timeline_map)
BLOCK_TITLES = [
    # (label_match, title_text, style, posY)
    ("hook+identity",            "Eu tenho um trauma com festas.",       "hero",       None),
    ("trauma_inicio",            "Eu nunca fui chamada para festinhas.", "lower3rd",   None),
    ("festa_quase_ninguem_vulnerabilidade", "Quando eu fiz meu bebê chá, quase ninguém foi.", "ribbon", None),
    ("nunca_comemorei_rejeicao", "Eu parei de comemorar por medo de ninguém aparecer.", "ribbon", None),
    ("barreiras_muros",          "Barreiras|Muros|Distância",            "panel",      None),
    ("dia27_vou_casar_renovacao","A renovação de votos virou um gatilho.","ribbon",    None),
    ("ansiedade_insonia",        "Ansiedade · Insônia",                  "lower3rd",   None),
    ("nao_solucao_relato",       "Não é conselho. É desabafo.",          "ribbon",     None),
    ("dificuldade_falar",        "Às vezes eu só consigo falar escrevendo.", "lower3rd", None),
    ("nao_precisa_aprovacao",    "Você não precisa de aprovação de ninguém.", "hero",  None),
    ("festa_pra_gente",          "A festa não é para provar nada.|É para celebrar.", "hero", None),
    ("nao_esta_sozinha",         "Você não está sozinha.",               "hero",       None),
    ("preste_atencao_agora",     "Preste atenção no agora.",             "ribbon",     None),
    ("pequenas_coisas_vitoriosa","Você já venceu muita coisa.",          "hero",       None),
]

def find_block_time(timeline, label_match):
    """Encontra o startSec (timeline) do bloco pelo label."""
    for t in timeline:
        if t["label"] == label_match:
            return t["tl_start"], t["tl_end"]
    return None

def build_edit_config(timeline, total_dur, slug):
    print(f"[4/4] Building edit_config.json")

    titles = []
    for i, (label, text, style, posY) in enumerate(BLOCK_TITLES):
        block = find_block_time(timeline, label)
        if not block:
            print(f"      WARN: bloco '{label}' nao encontrado")
            continue
        t_start, t_end = block
        # Title aparece um pouco depois do inicio do bloco e dura ~3-4s
        t = {
            "id": f"t{i+1:02d}",
            "startSec": round(t_start + 0.5, 2),
            "endSec": round(min(t_start + 4.5, t_end - 0.2), 2),
            "text": text,
            "style": style,
        }
        if posY is not None:
            t["posY"] = posY
        titles.append(t)

    # Music tracks (low volume, emotional documentary)
    music_dir = ROOT / "public" / "music" / "documentary"
    music_files = []
    if music_dir.exists():
        music_files = sorted([f for f in music_dir.glob("*.mp3") if f.stat().st_size > 1000])

    music_tracks = []
    if music_files:
        # Single emotional bed throughout, low volume
        m = music_files[0]
        music_tracks.append({
            "id": "mus1",
            "src": f"music/documentary/{m.name}",
            "startSec": 0,
            "endSec": round(total_dur, 2),
            "volume": 0.07,
            "fadeIn": 2.0,
            "fadeOut": 4.0,
            "srcStart": 0,
        })

    # Subtle SFX on title appearances (whoosh light)
    sfx = []
    whoosh_path = ROOT / "public" / "sfx" / "whooshes" / "Slow Woosh - SoundConteúdo.mp3"
    if whoosh_path.exists():
        for i, t in enumerate(titles):
            sfx.append({
                "id": f"sfx_t{i:02d}",
                "src": "sfx/whooshes/Slow Woosh - SoundConteúdo.mp3",
                "startSec": round(t["startSec"] - 0.2, 2),
                "endSec": round(t["startSec"] + 1.0, 2),
                "volume": 0.35,
                "duration": 1.2,
            })

    # Subtle slow zooms in emotional moments (in only, intensity 1.08-1.12)
    zooms = []
    zoom_blocks = [
        ("hook+identity",                   1.10, "in",     "smooth"),
        ("nunca_comemorei_rejeicao",        1.12, "in",     "smooth"),
        ("dia27_vou_casar_renovacao",       1.10, "in",     "smooth"),
        ("ansiedade_insonia",               1.15, "hardIn", "easeOutCubic"),
        ("nao_precisa_aprovacao",           1.12, "hardIn", "easeOutCubic"),
        ("festa_pra_gente",                 1.10, "in",     "smooth"),
        ("nao_esta_sozinha",                1.15, "hardIn", "easeOutCubic"),
        ("pequenas_coisas_vitoriosa",       1.10, "in",     "smooth"),
    ]
    for i, (label, intensity, direction, easing) in enumerate(zoom_blocks):
        block = find_block_time(timeline, label)
        if not block: continue
        t_start, t_end = block
        zooms.append({
            "id": f"z{i+1:02d}",
            "startSec": round(t_start, 2),
            "endSec": round(t_end, 2),
            "direction": direction,
            "intensity": intensity,
            "easing": easing,
            "originY": 35,
        })

    cfg = {
        "videoDuration": round(total_dur, 3),
        "fps": 30,
        "videoSrc": f"projects/{slug}/video_preview.mp4",
        "width": 1080,
        "height": 1920,
        "aspectRatio": "9:16",
        "videoClips": [{
            "id": "v1",
            "startSec": 0,
            "endSec": round(total_dur, 3),
            "src": f"projects/{slug}/video_preview.mp4",
            "baseDurationSec": round(total_dur, 3),
        }],
        "titles": titles,
        "brolls": [],
        "zooms": zooms,
        "sfx": sfx,
        "musicTracks": music_tracks,
        # Captions karaoke conforme plano
        "showCaptions": True,
        "captionStyle": "words",
        "captionKaraoke": True,
        "captionFontSize": 110,
        "captionFont": "Montserrat",
        "captionColor": "#FFFFFF",
        "captionHighlightColor": "#FFD54F",  # amarelo suave conforme plano
        "captionMaxLines": 2,
        "captionBg": True,
        # Sem progress bar pra Reels
        "showProgressBar": False,
        # Color correction sutil
        "brightness": 0,
        "contrast": 4,
        "saturation": -2,
        "temperature": 0,
    }
    cfg_path = PROJ / "edit_config.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      OK {cfg_path}")
    print(f"      Titulos: {len(titles)} | Zooms: {len(zooms)} | SFX: {len(sfx)} | Music: {len(music_tracks)}")

def main():
    timeline, total_dur = build_timeline_map()
    print(f"Plano: {len(KEEPS)} keeps → {total_dur:.1f}s ({total_dur/60:.1f}min)")

    src_orig = PROJ / "video.mp4"
    src_orig_backup = PROJ / "video_uncut.mp4"
    src_edited = PROJ / "video_edited.mp4"

    # Backup original (only first time)
    if not src_orig_backup.exists() and src_orig.exists():
        # Check if current video.mp4 is the cut version (size mismatch means already cut)
        # If size > 35MB, it's still the original 8:18 version (37MB)
        if src_orig.stat().st_size > 30_000_000:
            shutil.move(str(src_orig), str(src_orig_backup))
            print(f"Backup: video.mp4 → video_uncut.mp4 ({src_orig_backup.stat().st_size//1024//1024}MB)")

    # Use the original as source for cuts
    cut_source = src_orig_backup if src_orig_backup.exists() else src_orig
    cut_video(timeline, total_dur, cut_source, src_edited)

    # Replace video.mp4 with edited
    if src_edited.exists():
        if src_orig.exists() and src_orig.stat().st_size > 30_000_000:
            src_orig.unlink()
        if not src_orig.exists():
            shutil.copy(str(src_edited), str(src_orig))
            print(f"video.mp4 ← video_edited.mp4 ({src_orig.stat().st_size//1024//1024}MB)")

    # Preview
    preview = PROJ / "video_preview.mp4"
    if preview.exists() and preview.stat().st_size > 50_000_000:
        # Old preview from before cut — remove
        preview.unlink()
    make_preview(src_orig, preview)

    # Re-transcribe (force re-do since video changed)
    trans = PROJ / "transcription.json"
    trans_old = PROJ / "transcription_uncut.json"
    if trans.exists() and not trans_old.exists():
        shutil.move(str(trans), str(trans_old))
    re_transcribe(src_orig, trans)

    # Build config
    build_edit_config(timeline, total_dur, "domingo-com-ritalina")

    print("\nDONE.")
    print("  Reload Klipe: http://localhost:3001/?project=domingo-com-ritalina")

if __name__ == "__main__":
    main()
