#!/usr/bin/env python3
"""
Klipe Cleanup — Limpeza automatizada do storage do Klipe (motionforge/)
=============================================━━━━━━━━━━━━━━━━━━━━━━

Identifica e apaga arquivos descartaveis:
  1. output/.forge_cache/<hash>/  — mantem so o N mais recente
  2. output/forge_test_*.mp4      — MP4s de teste (>X dias)
  3. output/motionforge_davinci_*.{xml,fcpxml} — exports DaVinci antigos
  4. public/projects/<proj>/audio_*.wav        — stems gigantes do build_davinci
  5. public/projects/<proj>/overlays_clean/    — segments DaVinci pipeline
  6. public/projects/<proj>/brolls_overlay/    — segments DaVinci pipeline

Por padrao: --dry-run (so mostra). Use --apply pra apagar de verdade.

Uso:
  python cleanup.py                     # dry-run, todas as categorias
  python cleanup.py --apply             # apaga de verdade
  python cleanup.py --keep-cache 1      # mantem so 1 hash do cache (default)
  python cleanup.py --age-days 30       # apaga MP4s/exports > 30 dias
  python cleanup.py --only cache,exports
  python cleanup.py --skip stems
"""
import argparse
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
OUTPUT = ROOT / "output"
CACHE = OUTPUT / ".forge_cache"


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_size(bytes_):
    if bytes_ >= 1_000_000_000:
        return f"{bytes_/1_000_000_000:.2f} GB"
    if bytes_ >= 1_000_000:
        return f"{bytes_/1_000_000:.1f} MB"
    return f"{bytes_/1_000:.1f} KB"


def dir_size(path):
    if not path.exists():
        return 0
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except (OSError, FileNotFoundError):
                    pass
    except (OSError, FileNotFoundError):
        pass
    return total


def file_age_days(path):
    if not path.exists():
        return 0
    try:
        return (time.time() - path.stat().st_mtime) / 86400
    except (OSError, FileNotFoundError):
        return 0


def safe_rm(path, dry_run=True):
    """Remove file ou dir. Retorna bytes liberados."""
    if not path.exists():
        return 0
    size = dir_size(path) if path.is_dir() else path.stat().st_size
    if dry_run:
        return size
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return size
    except (OSError, FileNotFoundError, PermissionError) as e:
        print(f"  WARN failed to remove {path}: {e}")
        return 0


# ── Categorias de cleanup ─────────────────────────────────────────────────────
def clean_cache(keep_n=1, dry_run=True):
    """Mantem so N hashes mais recentes do .forge_cache/. Apaga os outros."""
    print(f"\n=== [1] forge_cache (mantem {keep_n} hash mais recente) ===")
    if not CACHE.exists():
        print("  Cache vazio")
        return 0
    hashes = sorted(
        [d for d in CACHE.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True
    )
    if len(hashes) <= keep_n:
        print(f"  Apenas {len(hashes)} hashes — nada pra apagar")
        return 0

    keep = hashes[:keep_n]
    drop = hashes[keep_n:]
    print(f"  Mantem ({len(keep)}):")
    for h in keep:
        size = dir_size(h)
        age = file_age_days(h)
        print(f"    {h.name}  {fmt_size(size)}  ({age:.1f}d atras)")
    print(f"  APAGA ({len(drop)}):")
    freed = 0
    for h in drop:
        size = dir_size(h)
        age = file_age_days(h)
        print(f"    {h.name}  {fmt_size(size)}  ({age:.1f}d atras)")
        freed += safe_rm(h, dry_run=dry_run)
    return freed


def clean_test_mp4s(age_days=7, dry_run=True):
    """Apaga MP4s de teste (forge_test_*, render_output_*, *_test_*) com mais de N dias."""
    print(f"\n=== [2] output MP4s de teste (>{age_days} dias) ===")
    patterns = ["forge_test_*.mp4", "*_test_*.mp4", "render_output*.mp4",
                "barreiras_klipe_*.mp4", "barreiras_nvenc_*.mp4", "composite_nvenc_*.mp4"]
    candidates = set()
    for p in patterns:
        for f in OUTPUT.glob(p):
            if f.is_file():
                candidates.add(f)
    if not candidates:
        print("  Nenhum MP4 de teste encontrado")
        return 0
    freed = 0
    for f in sorted(candidates, key=lambda x: x.stat().st_mtime):
        age = file_age_days(f)
        size = f.stat().st_size
        if age >= age_days:
            print(f"  APAGA {f.name}  {fmt_size(size)}  ({age:.1f}d)")
            freed += safe_rm(f, dry_run=dry_run)
        else:
            print(f"  manter {f.name}  {fmt_size(size)}  ({age:.1f}d)")
    return freed


def clean_davinci_exports(age_days=14, dry_run=True):
    """Apaga exports DaVinci antigos (.xml, .fcpxml) com mais de N dias."""
    print(f"\n=== [3] output DaVinci exports (>{age_days} dias) ===")
    candidates = list(OUTPUT.glob("motionforge_davinci_*.xml")) + \
                 list(OUTPUT.glob("motionforge_davinci_*.fcpxml")) + \
                 list(OUTPUT.glob("test_*.fcpxml"))
    if not candidates:
        print("  Nenhum export antigo")
        return 0
    freed = 0
    kept = 0
    for f in sorted(candidates, key=lambda x: x.stat().st_mtime):
        age = file_age_days(f)
        size = f.stat().st_size
        if age >= age_days:
            freed += safe_rm(f, dry_run=dry_run)
        else:
            kept += 1
    n_drop = len(candidates) - kept
    if n_drop > 0:
        print(f"  APAGA {n_drop} arquivos antigos = {fmt_size(freed)}")
    if kept > 0:
        print(f"  Manter {kept} recentes (<{age_days}d)")
    return freed


def clean_audio_stems(age_days=14, dry_run=True):
    """Apaga audio stems gigantes (audio_voice/sfx/music.wav) por projeto, se nao usados ha X dias.
    Stems sao usados pelo build_davinci_from_klipe.py — se nao vai mais pro DaVinci, da pra apagar."""
    print(f"\n=== [4] public/projects/<proj>/audio_*.wav (>{age_days} dias sem usar) ===")
    proj_root = PUBLIC / "projects"
    if not proj_root.exists():
        return 0
    freed = 0
    for proj in proj_root.iterdir():
        if not proj.is_dir():
            continue
        for stem_name in ["audio_voice.wav", "audio_sfx.wav", "audio_music.wav"]:
            f = proj / stem_name
            if not f.exists():
                continue
            age = file_age_days(f)
            size = f.stat().st_size
            if age >= age_days:
                print(f"  APAGA {proj.name}/{stem_name}  {fmt_size(size)}  ({age:.1f}d)")
                freed += safe_rm(f, dry_run=dry_run)
            else:
                print(f"  manter {proj.name}/{stem_name}  {fmt_size(size)}  ({age:.1f}d)")
    return freed


def clean_davinci_segments(age_days=14, dry_run=True):
    """Apaga overlays_clean/ e brolls_overlay/ por projeto (segments split pro DaVinci).
    Reusados se voltar a renderizar DaVinci. Pequeno overhead pra recriar."""
    print(f"\n=== [5] public/projects/<proj>/{{overlays_clean,brolls_overlay}}/ (>{age_days} dias) ===")
    proj_root = PUBLIC / "projects"
    if not proj_root.exists():
        return 0
    freed = 0
    for proj in proj_root.iterdir():
        if not proj.is_dir():
            continue
        for sub_name in ["overlays_clean", "brolls_overlay"]:
            d = proj / sub_name
            if not d.exists():
                continue
            age = file_age_days(d)
            size = dir_size(d)
            if age >= age_days:
                n_files = sum(1 for _ in d.rglob("*") if _.is_file())
                print(f"  APAGA {proj.name}/{sub_name}/  {fmt_size(size)}  ({n_files} files, {age:.1f}d)")
                freed += safe_rm(d, dry_run=dry_run)
            else:
                print(f"  manter {proj.name}/{sub_name}/  {fmt_size(size)}  ({age:.1f}d)")
    return freed


def clean_master_videos(age_days=30, dry_run=True):
    """Apaga video.mp4 (master 4K original) se ja temos video_preview.mp4 (1080p).
    Mantem se for unico video do projeto."""
    print(f"\n=== [6] public/projects/<proj>/video.mp4 (master 4K, se ja tem video_preview) ===")
    proj_root = PUBLIC / "projects"
    if not proj_root.exists():
        return 0
    freed = 0
    for proj in proj_root.iterdir():
        if not proj.is_dir():
            continue
        master = proj / "video.mp4"
        preview = proj / "video_preview.mp4"
        if master.exists() and preview.exists():
            age = file_age_days(master)
            size = master.stat().st_size
            if age >= age_days:
                print(f"  APAGA {proj.name}/video.mp4 (master)  {fmt_size(size)}  ({age:.1f}d)  — preview existe")
                freed += safe_rm(master, dry_run=dry_run)
            else:
                print(f"  manter {proj.name}/video.mp4  {fmt_size(size)}  ({age:.1f}d)")
        elif master.exists():
            print(f"  manter {proj.name}/video.mp4 (sem preview, fonte unica)")
    return freed


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Klipe storage cleanup")
    ap.add_argument("--apply", action="store_true",
                    help="Apaga de verdade (default eh dry-run)")
    ap.add_argument("--keep-cache", type=int, default=1,
                    help="Quantos hashes do .forge_cache/ manter (default 1)")
    ap.add_argument("--age-days", type=int, default=7,
                    help="Dias minimos pra apagar MP4s de teste (default 7)")
    ap.add_argument("--exports-age", type=int, default=14,
                    help="Dias pra apagar exports DaVinci (default 14)")
    ap.add_argument("--stems-age", type=int, default=14,
                    help="Dias pra apagar audio stems (default 14)")
    ap.add_argument("--segments-age", type=int, default=14,
                    help="Dias pra apagar overlays_clean/brolls_overlay (default 14)")
    ap.add_argument("--master-age", type=int, default=30,
                    help="Dias pra apagar video.mp4 master (default 30)")
    ap.add_argument("--only", type=str, default=None,
                    help="Categorias separadas por virgula: cache,test_mp4s,exports,stems,segments,masters")
    ap.add_argument("--skip", type=str, default=None,
                    help="Categorias pra pular")
    args = ap.parse_args()

    dry_run = not args.apply
    mode = "DRY-RUN (nao apaga)" if dry_run else "APPLY (vai apagar)"
    print(f"=============================================")
    print(f"  KLIPE CLEANUP — {mode}")
    print(f"=============================================")

    cats = {
        "cache": (clean_cache, {"keep_n": args.keep_cache, "dry_run": dry_run}),
        "test_mp4s": (clean_test_mp4s, {"age_days": args.age_days, "dry_run": dry_run}),
        "exports": (clean_davinci_exports, {"age_days": args.exports_age, "dry_run": dry_run}),
        "stems": (clean_audio_stems, {"age_days": args.stems_age, "dry_run": dry_run}),
        "segments": (clean_davinci_segments, {"age_days": args.segments_age, "dry_run": dry_run}),
        "masters": (clean_master_videos, {"age_days": args.master_age, "dry_run": dry_run}),
    }

    selected = set(cats.keys())
    if args.only:
        selected = set(c.strip() for c in args.only.split(","))
    if args.skip:
        selected -= set(c.strip() for c in args.skip.split(","))

    total_freed = 0
    for name in ["cache", "test_mp4s", "exports", "stems", "segments", "masters"]:
        if name not in selected:
            continue
        fn, kwargs = cats[name]
        total_freed += fn(**kwargs)

    print(f"\n=============================================")
    if dry_run:
        print(f"  TOTAL liberavel: {fmt_size(total_freed)}")
        print(f"  Pra apagar de verdade, rode: python cleanup.py --apply")
    else:
        print(f"  TOTAL liberado: {fmt_size(total_freed)}")
    print(f"=============================================")


if __name__ == "__main__":
    main()
