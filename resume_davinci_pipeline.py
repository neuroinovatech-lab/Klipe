#!/usr/bin/env python
"""
Retoma pipeline Klipe -> DaVinci na metade.

Pula STEPS 1-3 (audio stems, title overlays, broll overlays) que ja existem em disco
e roda apenas STEP 4 (timeline build) + STEP 5 (zoom keyframes injection).

USO:
    python resume_davinci_pipeline.py <project_slug> <davinci_project_name>

EXEMPLO:
    python resume_davinci_pipeline.py abuso-mulheres-autistas AbusoMulheres_1777691872
"""
import sys, json, time, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Reuse logic from main script
sys.path.insert(0, str(ROOT))
from build_davinci_from_klipe import (
    build_davinci_timeline,
    inject_keyframes,
    RESOLVEFORGE,
)


def reconstruct_overlay_paths(project_dir, cfg):
    """Reconstroi a lista (path, startSec) dos title overlays a partir dos arquivos em disco.

    Replica a logica de render_overlays() pra calcular startSec de cada segment.
    """
    overlay_dir = project_dir / "overlays_clean"
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
        s_start = max(0, s["start"])
        out = overlay_dir / f"overlay_{i:03d}.mov"
        if not out.exists():
            print(f"  WARN: missing {out.name} -- skipping")
            continue
        overlay_paths.append((out, s_start))
    print(f"  {len(overlay_paths)} title overlays found on disk")
    return overlay_paths


def reconstruct_broll_paths(project_dir, cfg):
    """Reconstroi (path, startSec) dos broll overlays a partir dos arquivos em disco."""
    broll_dir = project_dir / "brolls_overlay"
    brolls_cfg = cfg.get("brolls", [])
    out_paths = []
    for i, b in enumerate(brolls_cfg):
        stem = Path(b["src"]).stem
        out = broll_dir / f"brollT_{i:02d}_{stem}.mov"
        if not out.exists():
            print(f"  WARN: missing {out.name} -- skipping")
            continue
        out_paths.append((out, b["startSec"]))
    print(f"  {len(out_paths)} broll overlays found on disk")
    return out_paths


def ensure_project_loaded(davinci_project):
    """Garante que o projeto certo esta aberto no DaVinci."""
    print(f"\n=== Loading DaVinci project: {davinci_project} ===")
    lua = f"""
local r = Resolve()
local pm = r:GetProjectManager()
local cur = pm:GetCurrentProject()
if cur and cur:GetName() == "{davinci_project}" then
  print("Already loaded: " .. cur:GetName())
else
  if cur then pm:CloseProject(cur) end
  local p = pm:LoadProject("{davinci_project}")
  if not p then
    print("ERROR: failed to load " .. "{davinci_project}")
    return
  end
  print("Loaded: " .. p:GetName())
end
-- Ensure 3 video tracks (V1, V2, V3)
local p = pm:GetCurrentProject()
local tl = p:GetCurrentTimeline()
if not tl then
  -- Create empty timeline if none
  local mp = p:GetMediaPool()
  tl = mp:CreateEmptyTimeline("MotionForge Export")
  print("Created empty timeline")
end
while tl:GetTrackCount("video") < 3 do tl:AddTrack("video") end
while tl:GetTrackCount("audio") < 4 do tl:AddTrack("audio", "stereo") end
-- Set timecode start to 00:00:00:00 (default is 01:00:00:00)
tl:SetStartTimecode("00:00:00:00")
print("Tracks: V=" .. tl:GetTrackCount("video") .. " A=" .. tl:GetTrackCount("audio"))
"""
    r = requests.post(f"{RESOLVEFORGE}/api/lua/run", json={"script": lua}, timeout=30)
    out = r.json().get("output", r.text)
    print("  " + out[-400:])
    time.sleep(1)


def force_video_fps(video_name):
    """Forca FPS=30 no clip do video.mp4 (DaVinci as vezes le como 60)."""
    print(f"\n=== Forcing FPS=30 on {video_name} ===")
    lua = f"""
local r = Resolve()
local pm = r:GetProjectManager()
local p = pm:GetCurrentProject()
local mp = p:GetMediaPool()

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

local clip = findClip(mp:GetRootFolder(), "{video_name}")
if clip then
  local ok = clip:SetClipProperty("FPS", "30")
  print("FPS set: " .. tostring(ok))
else
  print("WARN: video.mp4 not in pool")
end
"""
    r = requests.post(f"{RESOLVEFORGE}/api/lua/run", json={"script": lua}, timeout=30)
    print("  " + r.json().get("output", r.text)[-200:])


def main(project_slug, davinci_project):
    project_dir = ROOT / "public" / "projects" / project_slug
    cfg_path = project_dir / "edit_config.json"
    if not cfg_path.exists():
        print(f"ERROR: {cfg_path} not found")
        sys.exit(1)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    video_src = project_dir / "video.mp4"
    voice = project_dir / "audio_voice.wav"
    sfx = project_dir / "audio_sfx.wav"
    music = project_dir / "audio_music.wav"

    # Validate everything exists
    missing = []
    for p in [video_src, voice, sfx, music]:
        if not p.exists():
            missing.append(p.name)
    if missing:
        print(f"ERROR: missing files: {missing}")
        print("       Run full build_davinci_from_klipe.py first")
        sys.exit(1)

    print(f"=== Resuming pipeline for {project_slug} ===")
    print(f"DaVinci project: {davinci_project}")
    print(f"Video: {video_src.name} | Duration: {cfg['videoDuration']}s")

    # Reconstruct overlay/broll path lists from disk
    print("\n=== Reconstructing asset lists from disk ===")
    overlays = reconstruct_overlay_paths(project_dir, cfg)
    brolls = reconstruct_broll_paths(project_dir, cfg)

    if not overlays:
        print("ERROR: no title overlays found in overlays_clean/")
        sys.exit(1)
    if not brolls:
        print("ERROR: no broll overlays found in brolls_overlay/")
        sys.exit(1)

    # Ensure correct project is loaded with V1-V3 tracks
    ensure_project_loaded(davinci_project)
    force_video_fps(video_src.name)

    # STEP 4: build timeline (this is destructive — clears V1/V2/V3 first)
    regions = build_davinci_timeline(
        project_slug, video_src, overlays, brolls, voice, sfx, music, cfg
    )

    # STEP 5: inject zoom keyframes via SQLite (closes project first)
    inject_keyframes(davinci_project, regions, video_src)

    # Reopen project so user can see result
    print("\n=== Reopening project ===")
    requests.post(
        f"{RESOLVEFORGE}/api/lua/run",
        json={"script": f"local r=Resolve();r:GetProjectManager():LoadProject('{davinci_project}');print('loaded')"},
        timeout=30,
    )

    print("\nDONE — DaVinci timeline built + zooms injected")
    print("MANUAL STEP: Project Settings -> Master Settings -> Playback frame rate -> 30")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
