#!/usr/bin/env python
"""
Fix V1 + zoom keyframes para projetos onde DaVinci consolidou slices.

Estrategia:
- Limpa V1 atual (27 slices consolidadas, fora de sync com zooms)
- Adiciona UM big clip de video.mp4 cobrindo o video todo
- Aplica TODOS os zoom keyframes globalmente nessa unica slice
- V2 (brolls) e V3 (overlays) e A1-A4 (audio) ficam intactos

USO:
    python fix_v1_zooms.py <project_slug> <davinci_project_name>
"""
import sys, os, json, time, struct, sqlite3, requests
from pathlib import Path
import zstandard

ROOT = Path(__file__).resolve().parent
RESOLVEFORGE = "http://localhost:8020"
RESOLVE_DB_BASE = Path(os.environ.get(
    "KLIPE_RESOLVE_DB_BASE",
    Path(os.environ.get("APPDATA", Path.home()))
    / "Blackmagic Design" / "DaVinci Resolve" / "Support"
    / "Resolve Project Library" / "Resolve Projects" / "Users" / "guest" / "Projects",
))
TL_FPS = 30
SRC_FPS = 30  # Forcamos video.mp4 a 30fps via SetClipProperty antes do append


def ease(t, e):
    if e in ("easeInOut", "easeOutCubic"):
        return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2
    elif e == "easeIn":
        return t ** 3
    elif e == "easeOut":
        return 1 - (1 - t) ** 3
    elif e == "smooth":
        return t * t * (3 - 2 * t)
    return t


def build_global_keyframes(zooms, total_frames):
    """Constroi lista de (frame, value) cobrindo todos os zooms na timeline.

    Entre zoom regions o valor fica 1.0. Snap zooms (hardIn/hardOut) sao
    representados como 2 keyframes consecutivos com valores diferentes.
    """
    SAMPLE_PTS = 8
    kfs = [(0, 1.0)]  # comeca em 1.0

    for z in sorted(zooms, key=lambda x: x["startSec"]):
        z_start = round(z["startSec"] * TL_FPS)
        z_end = round(z["endSec"] * TL_FPS)
        intensity = z.get("intensity", 1.3)
        direction = z["direction"]
        easing = z.get("easing", "linear")
        dur_frames = z_end - z_start

        # Antes do zoom: garante 1.0
        if kfs[-1][0] < z_start - 1:
            kfs.append((z_start - 1, 1.0))

        if direction == "hardIn":
            # Snap to intensity at start, hold, snap back at end
            kfs.append((z_start, intensity))
            kfs.append((z_end, intensity))
            kfs.append((z_end + 1, 1.0))
        elif direction == "hardOut":
            # Just hold at 1.0 (zoom anterior caia pra 1.0)
            kfs.append((z_start, 1.0))
            kfs.append((z_end, 1.0))
        elif direction == "in":
            from_z, to_z = 1.0, intensity
            for i in range(SAMPLE_PTS + 1):
                f = z_start + round(i / SAMPLE_PTS * dur_frames)
                p = i / SAMPLE_PTS
                kfs.append((f, from_z + (to_z - from_z) * ease(p, easing)))
            kfs.append((z_end + 1, 1.0))
        elif direction == "out":
            from_z, to_z = intensity if intensity > 1 else 1.0, 1.0
            # "out" with intensity=1 means just hold at 1.0
            if from_z == 1.0:
                kfs.append((z_start, 1.0))
                kfs.append((z_end, 1.0))
            else:
                for i in range(SAMPLE_PTS + 1):
                    f = z_start + round(i / SAMPLE_PTS * dur_frames)
                    p = i / SAMPLE_PTS
                    kfs.append((f, from_z + (to_z - from_z) * ease(p, easing)))

    # Ensure last keyframe at total_frames is 1.0
    if kfs[-1][0] < total_frames:
        kfs.append((total_frames, 1.0))

    # Dedupe by frame (keep last) and sort
    by_frame = {}
    for f, v in kfs:
        by_frame[f] = v
    return sorted(by_frame.items())


def varlen(n):
    if n < 128:
        return bytes([n])
    o = b""
    while n > 127:
        o += bytes([0x80 | (n & 0x7f)])
        n >>= 7
    return o + bytes([n])


def kf_bytes(frame, value):
    return struct.pack("<i", frame) + struct.pack("<I", 0x000C0000) + struct.pack("<d", value)


def build_blob(kfs):
    if not kfs:
        return None
    kf_blob = b"\xff\xff\xff\xe0" + b"".join(kf_bytes(f, v) for f, v in kfs)
    prop_zoomx = b"\x08\x2a\x52" + varlen(len(kf_blob)) + kf_blob
    prop_zoomy = b"\x08\x2b\x52" + varlen(len(kf_blob)) + kf_blob
    properties = b"\x4a" + varlen(len(prop_zoomx)) + prop_zoomx + b"\x4a" + varlen(len(prop_zoomy)) + prop_zoomy
    for _ in range(10):
        properties += b"\x4a\x00"
    inner = b"\x08\x04" + properties
    payload = b"\x0a" + varlen(len(inner)) + inner
    if len(payload) > 100:
        comp = zstandard.ZstdCompressor().compress(payload)
        return b"\x00\x00\x00\x02" + struct.pack(">I", 1 + len(comp)) + b"\x81" + comp
    else:
        return b"\x00\x00\x00\x02" + struct.pack(">I", 1 + len(payload)) + b"\x80" + payload


def add_zoom_markers(davinci_project, zooms):
    """Adiciona markers coloridos na timeline pra cada zoom.

    Cores (do project_video_pipeline.md):
    - Red = hardIn
    - Cyan = hardOut
    - Blue = in
    - Green = out
    """
    print(f"\n=== Adding {len(zooms)} colored markers ===")
    color_map = {"hardIn": "Red", "hardOut": "Cyan", "in": "Blue", "out": "Green"}

    # Build marker entries Lua-side
    marker_entries = []
    for z in zooms:
        frame = round(z["startSec"] * TL_FPS)
        color = color_map.get(z["direction"], "White")
        name = f"{z['direction']} {z.get('intensity', 1.0)}"
        note = f"{z['id']} {z['startSec']}s-{z['endSec']}s easing={z.get('easing', 'linear')}"
        # Escape quotes for Lua
        name_l = name.replace('"', '\\"')
        note_l = note.replace('"', '\\"')
        marker_entries.append(f'{{frame={frame}, color="{color}", name="{name_l}", note="{note_l}"}}')

    markers_lua = ",\n  ".join(marker_entries)
    lua = f"""
local r = Resolve()
local pm = r:GetProjectManager()
local p = pm:GetCurrentProject()
local tl = p:GetCurrentTimeline()

local markers = {{
  {markers_lua}
}}

-- Clear existing markers first
local existing = tl:GetMarkers() or {{}}
for fr, _ in pairs(existing) do tl:DeleteMarkerAtFrame(fr) end

local added = 0
for _, m in ipairs(markers) do
  local ok = tl:AddMarker(m.frame, m.color, m.name, m.note, 1)
  if ok then added = added + 1 end
end
print("Markers added: " .. added .. "/" .. #markers)
p:SaveProject()
"""
    r = requests.post(f"{RESOLVEFORGE}/api/lua/run", json={"script": lua}, timeout=30)
    print("  " + r.json().get("output", r.text)[-300:])


def rebuild_v1_single_clip(davinci_project, total_dur_sec):
    """Limpa V1 e adiciona um unico big clip de video.mp4."""
    print(f"\n=== Rebuild V1 as single big clip ({total_dur_sec}s) ===")
    lua = f"""
local r = Resolve()
local pm = r:GetProjectManager()
local p = pm:GetCurrentProject()
if p:GetName() ~= "{davinci_project}" then
  if p then pm:CloseProject(p) end
  p = pm:LoadProject("{davinci_project}")
end
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

-- Clear ONLY V1
local items_v1 = tl:GetItemListInTrack("video", 1)
if items_v1 and #items_v1 > 0 then
  tl:DeleteClips(items_v1, false)
  print("Cleared V1: " .. #items_v1 .. " items")
end

local original = findClip(mp:GetRootFolder(), "video.mp4")
if not original then print("ERROR: video.mp4 not in pool") return end

-- CRITICAL: Force FPS=30 BEFORE append (DaVinci interpreta o source como 60fps por dup-frames)
local fps_ok = original:SetClipProperty("FPS", "30")
print("FPS forced: " .. tostring(fps_ok))

local TL_FPS = {TL_FPS}
local SRC_FPS = {SRC_FPS}
local DUR = {total_dur_sec}
local TOTAL_FRAMES = math.floor(DUR * TL_FPS + 0.5)

local clipInfo = {{{{
  mediaPoolItem = original,
  startFrame = 0,
  endFrame = TOTAL_FRAMES - 1,
  trackIndex = 1,
  recordFrame = 0,
  mediaType = 1,
}}}}
local res = mp:AppendToTimeline(clipInfo)
print("V1 big clip: " .. (res and #res or 0) .. " (Lua-side count) targetFrames=" .. TOTAL_FRAMES)

p:SaveProject()
print("Saved")
"""
    r = requests.post(f"{RESOLVEFORGE}/api/lua/run", json={"script": lua}, timeout=60)
    out = r.json().get("output", r.text)
    print("  " + out[-400:])
    time.sleep(1)


def inject_global_keyframes(davinci_project, kfs):
    """Injeta keyframes na unica slice de V1 (Track 1)."""
    print(f"\n=== Inject {len(kfs)} keyframes via SQLite ===")

    # Close project
    print("  Closing project for safe DB write...")
    requests.post(f"{RESOLVEFORGE}/api/lua/run",
        json={"script": "local r=Resolve();local pm=r:GetProjectManager();local p=pm:GetCurrentProject();if p then p:SaveProject();pm:CloseProject(p) end"},
        timeout=30)
    time.sleep(3)

    db_path = RESOLVE_DB_BASE / davinci_project / "Project.db"
    if not db_path.exists():
        print(f"  ERROR: DB not found at {db_path}")
        return

    blob = build_blob(kfs)
    print(f"  Blob size: {len(blob)} bytes ({len(kfs)} keyframes)")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Find video.mp4 slice on V1 (which now should be just one)
    cur.execute("SELECT Sm2TiItem_id, Start, Duration FROM Sm2TiItem WHERE Name=? ORDER BY CAST(Duration AS INTEGER) DESC", ("video.mp4",))
    slices = cur.fetchall()
    print(f"  V1 candidate slices: {len(slices)}")
    for s in slices[:5]:
        print(f"    id={s[0][:8]} start={s[1]} dur={s[2]}")

    if not slices:
        print("  ERROR: no video.mp4 slice found")
        conn.close()
        return

    # Pick the largest one (the big clip)
    target_id, target_start, target_dur = slices[0]
    print(f"  Target slice: id={target_id[:8]} start={target_start} dur={target_dur}")

    # Clear keyframes on all OTHER video.mp4 slices, set on the big one
    for s in slices[1:]:
        cur.execute("UPDATE Sm2TiItem SET EffectFiltersBA = NULL WHERE Sm2TiItem_id = ?", (s[0],))
    cur.execute("UPDATE Sm2TiItem SET EffectFiltersBA = ? WHERE Sm2TiItem_id = ?", (blob, target_id))

    conn.commit()
    conn.close()
    print(f"  OK: keyframes injected into target slice")


def main(project_slug, davinci_project):
    project_dir = ROOT / "public" / "projects" / project_slug
    cfg = json.load(open(project_dir / "edit_config.json", "r", encoding="utf-8"))
    total_dur = cfg["videoDuration"]
    zooms = cfg.get("zooms", [])
    total_frames = round(total_dur * TL_FPS)

    print(f"=== Fix V1 zooms for {project_slug} ===")
    print(f"DaVinci project: {davinci_project}")
    print(f"Duration: {total_dur}s ({total_frames} frames)")
    print(f"Zooms: {len(zooms)}")

    # Step 1: Rebuild V1 as single clip
    rebuild_v1_single_clip(davinci_project, total_dur)

    # Step 2: Add colored markers per zoom (Red=hardIn, Cyan=hardOut, Blue=in, Green=out)
    add_zoom_markers(davinci_project, zooms)

    # Step 3: Build global keyframes
    kfs = build_global_keyframes(zooms, total_frames)
    print(f"\nKeyframes built: {len(kfs)}")
    print("First 5:", kfs[:5])
    print("Last 5: ", kfs[-5:])

    # Step 4: Inject zoom keyframes (closes project, modifies DB)
    inject_global_keyframes(davinci_project, kfs)

    # NOTE: Nao reabrir aqui — DaVinci pode pegar estado em cache.
    # User precisa fechar o DaVinci app e abrir manualmente pra ver os zooms.
    print("\n========================================================")
    print("DONE — Timeline + markers + zooms aplicados no DB.")
    print()
    print("IMPORTANTE: Feche o DaVinci totalmente (File > Close)")
    print("e reabra o projeto pra os zooms aparecerem no Inspector.")
    print()
    print("Ou: feche o app inteiro e relance pra garantir.")
    print("========================================================")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
