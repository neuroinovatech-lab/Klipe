#!/usr/bin/env python
"""
Pipeline limpa Klipe -> DaVinci.

Pega tudo que aprendemos:
- Render TitlesOverlay sem letterbox bars (limpo pra usar como overlay no DaVinci)
- Audio stems com loop pra músicas curtas (atrim correto)
- Brolls como MP4 opacos (alpha ProRes não funciona)
- 47 slices V1 com keyframes injetados via DB SQLite (per-slice = sem limite)
- Klipe-exact easings (smoothstep, easeOut, easeInOut)

USO:
    python build_davinci_from_klipe.py <project_name>

EXEMPLO:
    python build_davinci_from_klipe.py barreiras-academico

IMPORTANTE:
    DaVinci precisa estar FECHADO ao executar (DB injection).
    Script vai abrir o DaVinci no fim com tudo pronto.
"""
import sys, os, json, subprocess, sqlite3, struct, zstandard, time, shutil, requests, hashlib
from pathlib import Path

# ======================================================================
# CONFIG
# ======================================================================
ROOT = Path(__file__).resolve().parent  # motionforge/
RESOLVE_DB_BASE = Path(os.environ.get(
    "KLIPE_RESOLVE_DB_BASE",
    Path(os.environ.get("APPDATA", Path.home()))
    / "Blackmagic Design" / "DaVinci Resolve" / "Support"
    / "Resolve Project Library" / "Resolve Projects" / "Users" / "guest" / "Projects",
))
RESOLVEFORGE = "http://localhost:8020"
TL_FPS = 30
SRC_FPS = 60   # DaVinci interpreta video.mp4 como 60fps (dup-frames)

# Klipe-exact easings (mesmo do template antigo applyEasing)
def ease(t, e):
    if e == "easeInOut": return 2*t*t if t < 0.5 else 1 - (-2*t+2)**2 / 2
    elif e == "easeIn": return t**3
    elif e == "easeOut": return 1 - (1-t)**3
    elif e == "smooth": return t*t*(3-2*t)
    return t

# ======================================================================
# STEP 1: Pre-process audio stems
# ======================================================================
def build_audio_stems(project_dir, cfg):
    """Extract voice + mix sfx + mix music (with loop pra tracks curtos)."""
    print("\n=== STEP 1: Audio stems ===")
    voice_out = project_dir / "audio_voice.wav"
    sfx_out = project_dir / "audio_sfx.wav"
    music_out = project_dir / "audio_music.wav"

    video_src = ROOT / "public" / cfg["videoSrc"]
    SR = 48000
    total_dur = cfg["videoDuration"]

    # Voice: extract from main video
    print(f"  voice: extracting from {video_src.name}")
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
        "-i", str(video_src), "-vn", "-ar", str(SR), "-ac", "2",
        "-c:a", "pcm_s16le", str(voice_out)], check=True)

    # SFX: mix all sfx tracks with delays + volumes
    sfx = cfg.get("sfx", [])
    print(f"  sfx: mixing {len(sfx)} entries")
    sfx_inputs, sfx_filters = [], []
    for i, s in enumerate(sfx):
        src = (ROOT / "public" / s["src"]).resolve()
        if not src.exists(): continue
        sfx_inputs += ["-i", str(src)]
        delay_ms = int(s["startSec"] * 1000)
        vol = s.get("volume", 1.0)
        # Clamp volume to safe range (avoid distortion)
        vol = min(vol, 2.0)
        f = f"[{i}:a]volume={vol},adelay={delay_ms}|{delay_ms},atrim=end={total_dur}[s{i}]"
        sfx_filters.append(f)
    if sfx:
        mix_inputs = "".join(f"[s{i}]" for i in range(len(sfx)))
        sfx_filter = ";".join(sfx_filters) + f";{mix_inputs}amix=inputs={len(sfx)}:duration=longest:dropout_transition=0,apad=whole_dur={total_dur}[mix]"
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
            *sfx_inputs, "-filter_complex", sfx_filter, "-map", "[mix]",
            "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
            "-t", str(total_dur), str(sfx_out)], check=True)

    # Music: similar but with loop pra tracks where dur > src_dur
    music = cfg.get("musicTracks", [])
    print(f"  music: mixing {len(music)} tracks (com loop)")
    snippets = []
    for i, m in enumerate(music):
        src = (ROOT / "public" / m["src"]).resolve()
        if not src.exists(): continue
        start = m["startSec"]; end = m["endSec"]
        dur = end - start
        src_start = m.get("srcStart", 0)
        # Probe source duration
        probe = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1", str(src)], capture_output=True, text=True)
        src_dur = float(probe.stdout.strip()) if probe.stdout.strip() else dur
        need_loop = dur > (src_dur - src_start)
        fadeIn = m.get("fadeIn", 0); fadeOut = m.get("fadeOut", 0)
        vol = m.get("volume", 1.0)

        af = []
        if fadeIn > 0: af.append(f"afade=t=in:st=0:d={fadeIn}")
        if fadeOut > 0: af.append(f"afade=t=out:st={dur-fadeOut}:d={fadeOut}")
        af.append(f"volume={vol}")
        af.append(f"adelay={int(start*1000)}|{int(start*1000)}")
        af.append(f"atrim=end={start+dur}")  # CRITICAL: corta DEPOIS do adelay

        from tempfile import NamedTemporaryFile
        snippet = NamedTemporaryFile(suffix=".wav", delete=False).name
        cmd = ["ffmpeg","-y","-hide_banner","-loglevel","error"]
        if need_loop: cmd += ["-stream_loop","-1"]
        cmd += ["-ss", str(src_start), "-i", str(src),
                "-af", ",".join(af),
                "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", snippet]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0: snippets.append(snippet)

    if snippets:
        inputs = []
        for s in snippets: inputs += ["-i", s]
        fc = f"amix=inputs={len(snippets)}:duration=longest:dropout_transition=0,apad=whole_dur={total_dur}"
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
            *inputs, "-filter_complex", fc,
            "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
            "-t", str(total_dur), str(music_out)], check=True)
        for s in snippets:
            try: os.unlink(s)
            except: pass

    print(f"  OK {voice_out.name} | {sfx_out.name} | {music_out.name}")
    return voice_out, sfx_out, music_out

# ======================================================================
# STEP 2: Render clean title overlays
# ======================================================================
def render_full_alpha_mov(composition, out_path, config_path=None):
    """Overlay da linha do tempo inteira, com alpha, pelo MotionCore.

    Era o render por navegador em ProRes 4444. O MotionCore
    desenha o mesmo overlay em Skia, sem subir Chrome, e o qtrle que ele
    entrega carrega alpha sem perda — o Resolve le os dois, e o qtrle nao
    depende de codec proprietario instalado na maquina de quem recebe.

    `composition` (TitlesOverlay / BrollsOverlay) nao e mais um nome de
    composicao React: o que entra no overlay ja vem decidido pelo config.
    Fica no parametro para nao quebrar quem chama, e so aparece no log.
    """
    cfg = config_path or (ROOT / "public" / "edit_config.json")
    cmd = [sys.executable, "-m", "motioncore.overlay", str(cfg), str(out_path)]
    print(f"  overlay ({composition}) via MotionCore: {' '.join(cmd[-2:])}")
    return subprocess.Popen(cmd, cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def render_overlays_and_brolls_parallel(project_dir, cfg):
    """Render TitlesOverlay + BrollsOverlay EM PARALELO (2 GPUs/CPU jobs simultaneos)."""
    print("\n=== STEP 2+3: Render TitlesOverlay + BrollsOverlay PARALELO ===")
    titles_mov = ROOT / "output" / "_titles_final.mov"
    brolls_mov = ROOT / "output" / "_brolls_final.mov"

    print(f"  Renderizando os 2 overlays em paralelo...")
    p1 = render_full_alpha_mov("TitlesOverlay", titles_mov)
    p2 = render_full_alpha_mov("BrollsOverlay", brolls_mov)

    # Wait for both
    r1_out, r1_err = p1.communicate()
    r2_out, r2_err = p2.communicate()

    if p1.returncode != 0:
        print(f"  TitlesOverlay FAIL: {r1_err.decode()[-300:]}")
    if p2.returncode != 0:
        print(f"  BrollsOverlay FAIL: {r2_err.decode()[-300:]}")
    print(f"  Titles: {titles_mov.stat().st_size//1024//1024}MB | Brolls: {brolls_mov.stat().st_size//1024//1024}MB")
    return titles_mov, brolls_mov

def render_overlays(project_dir, cfg, full_mov=None):
    """Split full TitlesOverlay MOV em segments (rapido — c copy)."""
    print("\n=== STEP 2: Splitting title overlays ===")
    overlay_dir = project_dir / "overlays_clean"
    overlay_dir.mkdir(exist_ok=True)
    if full_mov is None:
        full_mov = ROOT / "output" / "_titles_final.mov"

    titles = sorted(cfg["titles"], key=lambda t: t["startSec"])
    total_dur = cfg["videoDuration"]
    segments = []
    seg = {"start": titles[0]["startSec"] - 0.5, "end": titles[0]["endSec"] + 0.5}
    for t in titles[1:]:
        if t["startSec"] - seg["end"] < 2:
            seg["end"] = max(seg["end"], t["endSec"] + 0.5)
        else:
            segments.append(seg)
            seg = {"start": t["startSec"] - 0.5, "end": t["endSec"] + 0.5}
    segments.append(seg)

    overlay_paths = []
    for i, s in enumerate(segments):
        s["start"] = max(0, s["start"])
        s["end"] = min(total_dur, s["end"])
        out = overlay_dir / f"overlay_{i:03d}.mov"
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
            "-ss", str(s["start"]), "-to", str(s["end"]), "-i", str(full_mov),
            "-c", "copy", str(out)], check=True)
        overlay_paths.append((out, s["start"]))
    print(f"  {len(overlay_paths)} title segments split")
    return overlay_paths

# ======================================================================
# STEP 3: Render BrollsOverlay (Klipe-exact transitions baked) + split
# ======================================================================
def render_brolls(project_dir, cfg, full_mov=None):
    """Split full BrollsOverlay MOV em segments (rapido — c copy)."""
    print("\n=== STEP 3: Splitting broll segments ===")
    broll_dir = project_dir / "brolls_overlay"
    broll_dir.mkdir(exist_ok=True)
    if full_mov is None:
        full_mov = ROOT / "output" / "_brolls_final.mov"
    brolls_cfg = cfg.get("brolls", [])
    out_paths = []
    for i, b in enumerate(brolls_cfg):
        out = broll_dir / f"brollT_{i:02d}_{Path(b['src']).stem}.mov"
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
            "-ss", str(b["startSec"]), "-to", str(b["endSec"]),
            "-i", str(full_mov), "-c", "copy", str(out)], check=True)
        out_paths.append((out, b["startSec"]))
    print(f"  {len(out_paths)} broll segments split")
    return out_paths

# _OLD_render_brolls saiu: estava marcada DEPRECATED, ninguem chamava, e era
# o ultimo `npx motor de navegador render` deste arquivo.

def optimize_overlays(project_dir):
    """Re-encode overlay MOVs com qscale=14 — alpha preservado, ~80% menor.
    Skip se ja foi otimizado (marker file por pasta)."""
    print("\n=== STEP 3.5: Otimizando overlays (qscale=14) ===")
    total_before = total_after = 0
    skipped = 0
    for d in [project_dir / "overlays_clean", project_dir / "brolls_overlay"]:
        if not d.exists(): continue
        marker = d / ".optimized"
        files = sorted(d.glob("*.mov"))
        # Skip se marker existe E nenhum MOV foi modificado depois do marker
        if marker.exists() and files:
            marker_mtime = marker.stat().st_mtime
            if all(f.stat().st_mtime <= marker_mtime for f in files):
                skipped += len(files)
                continue
        for src in files:
            sz_before = src.stat().st_size
            total_before += sz_before
            tmp = src.with_suffix(".tmp.mov")
            cmd = ["ffmpeg","-y","-hide_banner","-loglevel","error",
                   "-i", str(src),
                   "-c:v", "prores_ks", "-profile:v", "4",
                   "-vendor", "ap10", "-pix_fmt", "yuva444p10le",
                   "-qscale:v", "14", "-an", str(tmp)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                if tmp.exists(): tmp.unlink()
                continue
            sz_after = tmp.stat().st_size
            total_after += sz_after
            src.unlink()
            tmp.rename(src)
        # Marca como otimizado pro proximo run pular
        marker.write_text(f"optimized at {time.time()}", encoding="utf-8")
    if skipped > 0:
        print(f"  CACHE HIT: {skipped} overlays ja otimizados (skip)")
    if total_before > 0:
        gb_saved = (total_before - total_after) / 1024 / 1024 / 1024
        pct = (1 - total_after/total_before) * 100
        print(f"  Otimizado: {gb_saved:.2f}GB liberados ({pct:.0f}% reducao)")

# ======================================================================
# STEP 4: Build DaVinci timeline via Lua
# ======================================================================
def create_new_project(name):
    """Cria projeto NOVO no DaVinci pra começar do zero."""
    print(f"\n=== Creating new DaVinci project: {name} ===")
    lua = f"""
local r = Resolve()
local pm = r:GetProjectManager()
-- Close current
local cur = pm:GetCurrentProject()
if cur then pm:CloseProject(cur) end
-- Create new
local p = pm:CreateProject("{name}")
if not p then
  print("ERROR: project may already exist, loading instead...")
  p = pm:LoadProject("{name}")
end
if not p then return end
-- Set timeline settings
-- 30fps fixo (TL_FPS=30 no Python). Settar ANTES de criar timeline pra ela herdar.
p:SetSetting("timelineFrameRate", "30")
p:SetSetting("timelinePlayrateLockedToTimecode", "0")  -- permite playback rate diff
p:SetSetting("timelinePlaybackFrameRate", "30")        -- API pode falhar; cobre via videoMonitorFormat
p:SetSetting("videoMonitorFormat", "HD 1080p 30")
p:SetSetting("timelineResolutionWidth", "1920")
p:SetSetting("timelineResolutionHeight", "1080")
-- Create empty timeline (deve herdar settings acima = 30fps)
local mp = p:GetMediaPool()
local tl = mp:CreateEmptyTimeline("MotionForge Export")
-- CRITICO: default start timecode eh 01:00:00:00 (1 hora). Clips em recordFrame=0
-- caem ANTES da timeline, ficam invisiveis no UI mesmo estando no DB.
tl:SetStartTimecode("00:00:00:00")
-- Force timeline FPS via SetSetting (em alguns DaVinci precisa setar no projeto + timeline)
p:SetSetting("timelineFrameRate", "30")
print("Created project + empty timeline (start=00:00:00:00 fps=30)")
"""
    r = requests.post(f"{RESOLVEFORGE}/api/lua/run", json={"script": lua}, timeout=30)
    print("  " + r.json().get("output", r.text)[-300:])
    time.sleep(2)

def build_davinci_timeline(project_name, video_src, overlays, brolls, voice, sfx, music, cfg):
    """Place all media na timeline atual."""
    print("\n=== STEP 4: DaVinci timeline ===")

    zooms = cfg.get("zooms", [])
    total = cfg["videoDuration"]

    # Build region list (zoom slices + gaps)
    regions = []
    cursor = 0
    for z in zooms:
        if z["startSec"] > cursor:
            regions.append((cursor, z["startSec"], None))
        regions.append((z["startSec"], z["endSec"], z))
        cursor = z["endSec"]
    if cursor < total:
        regions.append((cursor, total, None))

    # All media paths to import
    all_media = [str(video_src), str(voice), str(sfx), str(music)]
    for o, _ in overlays: all_media.append(str(o))
    for b, _ in brolls: all_media.append(str(b))
    all_media = [m.replace("\\", "/") for m in all_media]

    # Step A: import media via ResolveForge
    print(f"  Importing {len(all_media)} files...")
    r = requests.post(f"{RESOLVEFORGE}/api/media/import", json={"paths": all_media}, timeout=30)
    job_id = r.json()["job_id"]
    for _ in range(60):
        time.sleep(2)
        j = requests.get(f"{RESOLVEFORGE}/api/jobs/{job_id}", timeout=10).json()
        if j["status"] == "done":
            print(f"    imported {j['result']['count']}")
            break

    # Step B: set alpha on overlays AND brolls (both are alpha MOVs now)
    print(f"  Setting alpha=Straight on overlays + brolls...")
    for o, _ in overlays + brolls:
        requests.post(f"{RESOLVEFORGE}/api/media/set-alpha",
            json={"clip_name": o.name, "mode": "Straight"}, timeout=10)

    # Step C: Lua to build timeline
    print(f"  Building timeline via Lua...")
    print(f"  DEBUG overlays={len(overlays)} brolls={len(brolls)} regions={len(regions)}")
    if brolls:
        print(f"  DEBUG broll[0]: name={brolls[0][0].name} startSec={brolls[0][1]} exists={brolls[0][0].exists()} size={brolls[0][0].stat().st_size if brolls[0][0].exists() else 0}")
    region_data = json.dumps([(r[0], r[1]) for r in regions])
    overlay_data = json.dumps([(p.name, s) for p, s in overlays])
    broll_data = json.dumps([(p.name, s) for p, s in brolls])

    lua = f"""
local r = Resolve()
local pm = r:GetProjectManager()
local p = pm:GetCurrentProject()
local mp = p:GetMediaPool()
local tl = p:GetCurrentTimeline()

local function findClip(folder, name)
  for _, c in ipairs(folder:GetClipList() or {{}}) do
    if c:GetName() == name then return c end
  end
  for _, sub in ipairs(folder:GetSubFolderList() or {{}}) do
    local x = findClip(sub, name)
    if x then return x end
  end
  return nil
end

-- ENSURE 3 video tracks (V1, V2, V3) — default DaVinci tem so 1
while tl:GetTrackCount("video") < 3 do tl:AddTrack("video") end

-- Clean V1, V2, V3
for trk = 1, tl:GetTrackCount("video") do
  local items = tl:GetItemListInTrack("video", trk)
  if items and #items > 0 then tl:DeleteClips(items, false) end
end
for trk = 1, tl:GetTrackCount("audio") do
  local items = tl:GetItemListInTrack("audio", trk)
  if items and #items > 0 then tl:DeleteClips(items, false) end
end
print("Cleaned timeline (V tracks: " .. tl:GetTrackCount("video") .. ")")

local TL_FPS = {TL_FPS}
local SRC_FPS = {SRC_FPS}

-- V1: Place {len(regions)} slices of video.mp4 at zoom region boundaries
local original = findClip(mp:GetRootFolder(), "{video_src.name}")
if not original then print("ERROR: video.mp4 not in pool") return end

-- Force FPS=30 no clip (DaVinci as vezes le como 60fps por dup-frames)
original:SetClipProperty("FPS", "30")

local regions = {{
{",".join(f"{{{r[0]},{r[1]}}}" for r in [(reg[0], reg[1]) for reg in regions])}
}}
local v1_count = 0
for _, reg in ipairs(regions) do
  local clipInfo = {{{{
    mediaPoolItem = original,
    startFrame = math.floor(reg[1] * SRC_FPS + 0.5),
    endFrame = math.floor(reg[2] * SRC_FPS + 0.5) - 1,
    trackIndex = 1, recordFrame = math.floor(reg[1] * TL_FPS + 0.5), mediaType = 1,
  }}}}
  local res = mp:AppendToTimeline(clipInfo)
  if res and #res > 0 then v1_count = v1_count + 1 end
end
print("V1: " .. v1_count .. " slices")
print("V1: " .. v1_count .. " slices")

-- DEBUG: list pool clips
print("=== Pool clip names ===")
local function listAll(folder, depth)
  for _, c in ipairs(folder:GetClipList() or {{}}) do
    print(string.rep("  ", depth) .. "- " .. c:GetName())
  end
  for _, sub in ipairs(folder:GetSubFolderList() or {{}}) do
    print(string.rep("  ", depth) .. "[" .. sub:GetName() .. "]")
    listAll(sub, depth + 1)
  end
end
listAll(mp:GetRootFolder(), 0)
print("=== End pool ===")

-- V2: Brolls
local brolls = {{
{",".join(f'{{"{p.name}",{s}}}' for p, s in brolls)}
}}
local v2_count = 0
for _, b in ipairs(brolls) do
  local clip = findClip(mp:GetRootFolder(), b[1])
  if not clip then print("MISS broll: " .. b[1]) end
  if clip then
    local clipInfo = {{{{
      mediaPoolItem = clip,
      trackIndex = 2, recordFrame = math.floor(b[2] * TL_FPS + 0.5), mediaType = 1,
    }}}}
    local res = mp:AppendToTimeline(clipInfo)
    if res and #res > 0 then v2_count = v2_count + 1 end
  end
end
print("V2: " .. v2_count .. " brolls")

-- V3: Title overlays (Zoom=1.0 garantido)
local overlays = {{
{",".join(f'{{"{p.name}",{s}}}' for p, s in overlays)}
}}
local v3_count = 0
for _, o in ipairs(overlays) do
  local clip = findClip(mp:GetRootFolder(), o[1])
  if clip then
    local clipInfo = {{{{
      mediaPoolItem = clip,
      trackIndex = 3, recordFrame = math.floor(o[2] * TL_FPS + 0.5), mediaType = 1,
    }}}}
    local res = mp:AppendToTimeline(clipInfo)
    if res and #res > 0 then
      local item = res[1]
      item:SetProperty("ZoomX", 1.0)
      item:SetProperty("ZoomY", 1.0)
      v3_count = v3_count + 1
    end
  end
end
print("V3: " .. v3_count .. " overlays")

-- Audio: voice on A2, sfx on A3, music on A4 (A1 = video.mp4 linked, mute)
while tl:GetTrackCount("audio") < 4 do tl:AddTrack("audio", "stereo") end
tl:SetTrackName("audio", 2, "Voice")
tl:SetTrackName("audio", 3, "SFX")
tl:SetTrackName("audio", 4, "Music")

local function placeAudio(name, track)
  local clip = findClip(mp:GetRootFolder(), name)
  if clip then
    local res = mp:AppendToTimeline({{{{
      mediaPoolItem = clip, trackIndex = track,
      recordFrame = 0, mediaType = 2,
    }}}})
    if res and #res > 0 then return true end
  end
  return false
end
local av = placeAudio("{voice.name}", 2)
local as = placeAudio("{sfx.name}", 3)
local am = placeAudio("{music.name}", 4)
print("Audio: voice=" .. tostring(av) .. " sfx=" .. tostring(as) .. " music=" .. tostring(am))

p:SaveProject()
print("Saved")
"""
    r = requests.post(f"{RESOLVEFORGE}/api/lua/run", json={"script": lua}, timeout=120)
    print("    " + r.json().get("output", r.text)[-500:])

    return regions

# ======================================================================
# STEP 5: Inject zoom keyframes per slice via SQLite
# ======================================================================
def inject_keyframes(project_name, regions, video_src):
    """Per-slice keyframes via DB (DaVinci precisa estar fechado)."""
    print("\n=== STEP 5: Inject zoom keyframes ===")
    db_path = RESOLVE_DB_BASE / project_name / "Project.db"
    if not db_path.exists():
        print(f"  ERROR: DB not found at {db_path}")
        return

    # Close project via Lua first
    print("  Closing project for safe DB write...")
    requests.post(f"{RESOLVEFORGE}/api/lua/run",
        json={"script": "local r=Resolve();local pm=r:GetProjectManager();pm:CloseProject(pm:GetCurrentProject())"},
        timeout=30)
    time.sleep(2)

    SAMPLE_PTS = 8
    def kf(frame, value):
        return struct.pack('<i', frame) + struct.pack('<I', 0x000C0000) + struct.pack('<d', value)
    def varlen(n):
        if n < 128: return bytes([n])
        o = b''
        while n > 127: o += bytes([0x80 | (n & 0x7f)]); n >>= 7
        return o + bytes([n])
    def build_blob(kfs):
        if not kfs: return None
        kf_blob = b'\xff\xff\xff\xe0' + b''.join(kf(f, v) for f, v in kfs)
        prop_zoomx = b'\x08\x2a\x52' + varlen(len(kf_blob)) + kf_blob
        prop_zoomy = b'\x08\x2b\x52' + varlen(len(kf_blob)) + kf_blob
        properties = b'\x4a' + varlen(len(prop_zoomx)) + prop_zoomx + b'\x4a' + varlen(len(prop_zoomy)) + prop_zoomy
        for _ in range(10): properties += b'\x4a\x00'
        inner = b'\x08\x04' + properties
        payload = b'\x0a' + varlen(len(inner)) + inner
        if len(payload) > 100:
            comp = zstandard.ZstdCompressor().compress(payload)
            return b'\x00\x00\x00\x02' + struct.pack('>I', 1 + len(comp)) + b'\x81' + comp
        else:
            return b'\x00\x00\x00\x02' + struct.pack('>I', 1 + len(payload)) + b'\x80' + payload

    def keyframes_for_zoom(z):
        startSec, endSec = z["startSec"], z["endSec"]
        intensity = z.get("intensity", 1.3)
        easing = z.get("easing", "linear")
        dir_ = z["direction"]
        dur_frames = round((endSec - startSec) * TL_FPS)
        kfs = []
        if dir_ == "hardIn":
            kfs.append((0, intensity)); kfs.append((dur_frames, intensity))
        elif dir_ == "hardOut":
            kfs.append((0, 1.0)); kfs.append((dur_frames, 1.0))
        elif dir_ in ("in", "out"):
            fromZ = 1.0 if dir_ == "in" else intensity
            toZ = intensity if dir_ == "in" else 1.0
            for i in range(SAMPLE_PTS + 1):
                f = round(i / SAMPLE_PTS * dur_frames)
                p = i / SAMPLE_PTS
                kfs.append((f, fromZ + (toZ - fromZ) * ease(p, easing)))
        return kfs

    # NEW APPROACH: 1 big clip + keyframes globais (resolve consolidacao do DaVinci).
    # Constroi UMA lista de keyframes cobrindo todos os zooms na timeline e injeta
    # numa unica slice de video.mp4 (a maior, que cobre tudo).
    cfg_path = ROOT / "public" / "projects" / project_name.replace("MotionForge_Clean_", "").rstrip("0123456789_") / "edit_config.json"
    # Try absolute via regions: extrai todos zoom data
    zoom_list = [r[2] for r in regions if r[2] is not None]
    total_frames = round(regions[-1][1] * TL_FPS) if regions else 0

    # Build global keyframe sequence
    SAMPLE_PTS = 8
    all_kfs = [(0, 1.0)]
    for z in sorted(zoom_list, key=lambda x: x["startSec"]):
        z_start = round(z["startSec"] * TL_FPS)
        z_end = round(z["endSec"] * TL_FPS)
        intensity = z.get("intensity", 1.3)
        easing = z.get("easing", "linear")
        direction = z["direction"]
        dur_frames = z_end - z_start
        if all_kfs[-1][0] < z_start - 1:
            all_kfs.append((z_start - 1, 1.0))
        if direction == "hardIn":
            all_kfs.append((z_start, intensity))
            all_kfs.append((z_end, intensity))
            all_kfs.append((z_end + 1, 1.0))
        elif direction == "hardOut":
            all_kfs.append((z_start, 1.0))
            all_kfs.append((z_end, 1.0))
        elif direction == "in":
            for i in range(SAMPLE_PTS + 1):
                f = z_start + round(i / SAMPLE_PTS * dur_frames)
                p = i / SAMPLE_PTS
                all_kfs.append((f, 1.0 + (intensity - 1.0) * ease(p, easing)))
            all_kfs.append((z_end + 1, 1.0))
        elif direction == "out":
            from_z = intensity if intensity > 1 else 1.0
            if from_z == 1.0:
                all_kfs.append((z_start, 1.0))
                all_kfs.append((z_end, 1.0))
            else:
                for i in range(SAMPLE_PTS + 1):
                    f = z_start + round(i / SAMPLE_PTS * dur_frames)
                    p = i / SAMPLE_PTS
                    all_kfs.append((f, from_z + (1.0 - from_z) * ease(p, easing)))
    if all_kfs[-1][0] < total_frames:
        all_kfs.append((total_frames, 1.0))
    # Dedupe + sort
    by_frame = {f: v for f, v in all_kfs}
    kfs_global = sorted(by_frame.items())
    print(f"  Global keyframes: {len(kfs_global)} (covers {len(zoom_list)} zooms)")

    # Find biggest slice de video.mp4 (single big clip after our refactor)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT Sm2TiItem_id, Start, Duration FROM Sm2TiItem WHERE Name=? ORDER BY CAST(Duration AS INTEGER) DESC", (video_src.name,))
    slices = cur.fetchall()
    print(f"  V1 slices in DB: {len(slices)}")

    if not slices:
        print(f"  ERROR: nenhuma slice de {video_src.name}")
        conn.close()
        return

    # Inject blob na maior slice (a big clip), zerar demais
    blob = build_blob(kfs_global)
    target_id = slices[0][0]
    print(f"  Target slice: id={target_id[:8]} start={slices[0][1]} dur={slices[0][2]}")
    for s in slices[1:]:
        cur.execute("UPDATE Sm2TiItem SET EffectFiltersBA = NULL WHERE Sm2TiItem_id = ?", (s[0],))
    cur.execute("UPDATE Sm2TiItem SET EffectFiltersBA = ? WHERE Sm2TiItem_id = ?", (blob, target_id))
    conn.commit()
    conn.close()
    print(f"  OK keyframes globais injetados (1 big clip)")

# ======================================================================
# MAIN
# ======================================================================
def reuse_per_title_cache_as_overlays(cfg, project_dir):
    """OTIMIZACAO: Reusa MOVs individuais cacheadas em .forge_cache/titles_indiv/
    como overlays do DaVinci, em vez de renderizar TitlesOverlay full + splitar.

    Se algum title nao estiver cacheado, chama ensure_individual_titles que
    renderiza so os faltantes via Node API (bundle once).

    Retorna [(path_in_overlays_clean, startSec), ...] no formato esperado
    por build_davinci_timeline.
    """
    import shutil
    sys.path.insert(0, str(ROOT))
    from forge_render import ensure_individual_titles

    print("\n=== STEP 2 (otimizado): Reusing per-title cache ===")
    individual = ensure_individual_titles(cfg, force=False, max_workers=4)

    overlay_dir = project_dir / "overlays_clean"
    overlay_dir.mkdir(exist_ok=True)

    # Limpa overlays antigos pra evitar duplicidade
    for old in overlay_dir.glob("overlay_*.mov"):
        try: old.unlink()
        except: pass

    overlays = []
    for i, (cached_path, start_sec, end_sec) in enumerate(individual):
        target = overlay_dir / f"overlay_{i:03d}.mov"
        # Hard link se possivel (instantaneo, sem copia), fallback copy
        try:
            if target.exists(): target.unlink()
            os.link(str(cached_path), str(target))  # hard link
        except OSError:
            shutil.copy(str(cached_path), str(target))
        overlays.append((target, float(start_sec)))

    print(f"  Reused {len(overlays)} title overlays from per-title cache")
    return overlays


def main(project_name):
    project_dir = ROOT / "public" / "projects" / project_name
    cfg_path = project_dir / "edit_config.json"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} not found")
        sys.exit(1)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Use video.mp4 (master) as V1 source (no baked zoom — keyframes do it)
    video_src = project_dir / "video.mp4"
    if not video_src.exists():
        print(f"ERROR: video.mp4 not found in {project_dir}")
        sys.exit(1)

    print(f"=== Building DaVinci pipeline for {project_name} (OPTIMIZED) ===")
    print(f"Video: {video_src.name}  Duration: {cfg['videoDuration']}s")

    # PREREQ: DaVinci precisa estar aberto e conectado ao ResolveForge.
    # Se nao estiver, auto-spawn antes de prosseguir (evita pipeline silenciosa
    # falhar com 0 imports / DB nao criado).
    ensure_davinci_running()

    # OTIMIZACAO 1: audio stems via forge_render (cache por hash)
    sys.path.insert(0, str(ROOT))
    from forge_render import ensure_audio_stems
    voice, sfx, music = ensure_audio_stems(cfg, project_dir)

    # OTIMIZACAO 2: titles via per-title cache (reusa MOVs individuais)
    overlays = reuse_per_title_cache_as_overlays(cfg, project_dir)

    # OTIMIZACAO 3: Brolls — renderiza SO BrollsOverlay (titles ja vem do cache).
    # Cache por hash da config de brolls. Se nao mudou, pula.
    print("\n=== STEP 3 (otimizado): BrollsOverlay only ===")
    brolls_hash = hashlib.md5(json.dumps({
        "brolls": cfg.get("brolls", []),
        "duration": cfg.get("videoDuration"),
        "w": cfg.get("width"), "h": cfg.get("height"),
    }, sort_keys=True).encode()).hexdigest()[:12]
    brolls_cache_dir = ROOT / "output" / ".forge_cache" / "brolls_full"
    brolls_cache_dir.mkdir(parents=True, exist_ok=True)
    brolls_mov = brolls_cache_dir / f"{brolls_hash}.mov"
    if brolls_mov.exists() and brolls_mov.stat().st_size > 1_000_000:
        print(f"  Brolls CACHE HIT [{brolls_hash}] -> {brolls_mov.stat().st_size//1024//1024}MB")
    else:
        print(f"  Brolls CACHE MISS [{brolls_hash}] — renderizando...")
        t0 = time.time()
        # Sync Root.tsx antes (mesmo bug do per-title)
        try:
            pass   # era um POST /api/sync (removido); o endpoint saiu com O motor de navegador
        except: pass
        p = render_full_alpha_mov("BrollsOverlay", brolls_mov)
        out, err = p.communicate()
        if p.returncode != 0:
            print(f"  FAIL BrollsOverlay: {err.decode(errors='replace')[-500:]}")
            sys.exit(1)
        print(f"  Brolls rendered em {time.time()-t0:.1f}s")
    brolls = render_brolls(project_dir, cfg, brolls_mov)
    optimize_overlays(project_dir)

    # Reusa projeto fixo por slug. CreateProject retorna projeto existente se ja existe
    # (sem perder PlaybackFrameRate=30 que user configurou manualmente uma vez).
    # Build_davinci_timeline limpa V1/V2/V3 e rebuilda do zero — isolamento OK.
    safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
    new_name = f"MotionForge_{safe_slug}"
    create_new_project(new_name)

    regions = build_davinci_timeline(project_name, video_src, overlays, brolls, voice, sfx, music, cfg)

    # FIX persistencia: build_davinci_timeline faz SaveProject mas DaVinci serializa
    # AppendToTimeline async. Sem delay + segundo save, o estado em disco fica
    # incompleto (track-sequence link nao persiste, timeline reaberta vazia).
    print("\n  Forcing extra save pra garantir track-sequence persistencia...")
    time.sleep(5)
    requests.post(f"{RESOLVEFORGE}/api/lua/run",
        json={"script": "local r=Resolve();local p=r:GetProjectManager():GetCurrentProject();p:SaveProject();print('saved-2')"},
        timeout=30)
    time.sleep(3)
    requests.post(f"{RESOLVEFORGE}/api/lua/run",
        json={"script": "local r=Resolve();local p=r:GetProjectManager():GetCurrentProject();p:SaveProject();print('saved-3')"},
        timeout=30)
    time.sleep(3)

    # Use the new project we just created
    print(f"\n  Using DaVinci project: {new_name}")

    # Zoom keyframes: pulado na pipeline principal.
    # User pode rodar fix_v1_zooms.py separadamente APOS fechar e reabrir DaVinci
    # pra aplicar os 24 zooms globalmente.
    print("\n=== STEP 5 SKIPPED: zoom keyframes ===")
    print(f"  Pra aplicar zooms: 1) feche DaVinci, 2) execute:")
    print(f"     python fix_v1_zooms.py {project_name} {new_name}")
    print(f"  3) reabra DaVinci e o projeto")

    print("\nDONE DONE - DaVinci pronto pra editar")
    print(f"  Projeto: {new_name}")
    print()
    print("=" * 60)
    print("MANUAL 1x por projeto: Project Settings (gear icon canto inf direito)")
    print("  Master Settings -> Playback frame rate -> 30 -> Save")
    print("(Necessario porque API DaVinci nao permite setar via codigo)")
    print("=" * 60)


def ensure_davinci_running(resolve_exe=r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"):
    """Garante que DaVinci Resolve esta aberto e conectado ao ResolveForge.

    Se nao estiver, spawn Resolve.exe e poll ate ResolveForge confirmar conexao.
    Sem isso, pipeline falha silenciosamente (0 imports, DB nao criado).
    """
    print("\n=== Verificando DaVinci ===")
    # Quick check
    try:
        r = requests.get(f"{RESOLVEFORGE}/api/info", timeout=3)
        if r.status_code == 200 and r.json().get("connected"):
            print("  DaVinci ja esta conectado")
            return True
    except Exception:
        pass

    # Nao conectado — spawn
    if not os.path.exists(resolve_exe):
        print(f"  ERROR: Resolve.exe nao encontrado em {resolve_exe}")
        sys.exit(1)
    print(f"  DaVinci nao detectado, abrindo Resolve.exe...")
    try:
        subprocess.Popen([resolve_exe], shell=False)
    except Exception as e:
        print(f"  spawn falhou: {e}")
        sys.exit(1)

    # Poll ate ResolveForge confirmar conexao (Resolve carrega ~15-30s)
    t0 = time.time()
    for _ in range(60):
        time.sleep(2)
        try:
            r = requests.get(f"{RESOLVEFORGE}/api/info", timeout=3)
            if r.status_code == 200 and r.json().get("connected"):
                print(f"  DaVinci pronto em {time.time()-t0:.0f}s")
                time.sleep(3)  # Margem extra pra Lua aceitar comandos
                return True
        except Exception:
            pass
    print(f"  TIMEOUT esperando DaVinci ficar pronto ({time.time()-t0:.0f}s)")
    sys.exit(1)


def restart_davinci_and_open(project_name, resolve_exe=r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"):
    """Mata Resolve.exe + reabre + carrega projeto. Resolve o cache em memoria.

    ResolveForge subprocess fica vivo (nao precisa restart, ele reconecta).
    """
    # Kill se rodando
    try:
        subprocess.run(["taskkill", "/F", "/IM", "Resolve.exe"],
                       capture_output=True, timeout=10)
        print("  Resolve.exe killed")
        time.sleep(2)
    except Exception as e:
        print(f"  taskkill: {e}")

    # Start Resolve novamente
    if not os.path.exists(resolve_exe):
        print(f"  WARN: Resolve.exe nao encontrado em {resolve_exe} — abra manualmente")
        return
    try:
        subprocess.Popen([resolve_exe], shell=False)
        print(f"  Resolve.exe iniciado, aguardando ficar pronto...")
    except Exception as e:
        print(f"  spawn falhou: {e}")
        return

    # Poll ResolveForge /api/info ate Resolve estar conectado
    # Resolve demora ~10-20s pra carregar
    t0 = time.time()
    ready = False
    for _ in range(45):
        time.sleep(2)
        try:
            r = requests.get(f"{RESOLVEFORGE}/api/info", timeout=3)
            if r.status_code == 200 and r.json().get("connected"):
                ready = True
                break
        except Exception:
            pass
    if not ready:
        print(f"  WARN: timeout esperando Resolve conectar ({time.time()-t0:.0f}s)")
        return
    print(f"  Resolve pronto em {time.time()-t0:.0f}s, carregando projeto {project_name}...")

    # Open the project
    time.sleep(2)  # extra margem pra DaVinci aceitar Lua
    r = requests.post(f"{RESOLVEFORGE}/api/lua/run",
        json={"script": f"local r=Resolve();local p=r:GetProjectManager():LoadProject('{project_name}');print('loaded: ' .. (p and p:GetName() or 'FAIL'))"},
        timeout=30)
    print(f"  {r.json().get('output', r.text)[-200:]}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
