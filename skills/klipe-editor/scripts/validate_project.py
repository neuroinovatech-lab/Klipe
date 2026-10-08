#!/usr/bin/env python3
"""Validate a Klipe edit_config without changing the project."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


MEDIA_TRACKS = ("videoClips", "brolls", "sfx", "musicTracks")
TIMED_TRACKS = (
    "videoClips", "brolls", "titles", "zooms", "shortsClips", "shapes",
    "sfx", "musicTracks", "captions", "audioRegions",
)


def positive_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def locate_roots(config_path: Path) -> tuple[Path, Path]:
    project_dir = config_path.parent
    if project_dir.parent.name == "projects" and project_dir.parent.parent.name == "public":
        return project_dir.parent.parent.parent, project_dir.parent.parent
    for parent in config_path.parents:
        if (parent / "editor-server.js").exists() and (parent / "public").is_dir():
            return parent, parent / "public"
    return project_dir, project_dir


def resolve_media(src: str, project_dir: Path, public_dir: Path) -> Path | None:
    raw = Path(src)
    candidates = [raw] if raw.is_absolute() else [public_dir / raw, project_dir / raw]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Klipe edit_config.json")
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config_path = args.config.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR config not found: {config_path}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
        return 1

    if not isinstance(config, dict):
        print("ERROR config root must be an object")
        return 1

    root, public_dir = locate_roots(config_path)
    project_dir = config_path.parent
    duration = config.get("videoDuration")
    if not positive_number(duration):
        errors.append("videoDuration must be a positive finite number")
        duration = None
    if not positive_number(config.get("fps")):
        errors.append("fps must be a positive finite number")
    if not positive_number(config.get("width")) or not positive_number(config.get("height")):
        warnings.append("width/height are missing or invalid; editor defaults may hide an aspect mismatch")

    for track in TIMED_TRACKS:
        items = config.get(track, [])
        if not isinstance(items, list):
            errors.append(f"{track} must be a list")
            continue
        seen: set[str] = set()
        for index, item in enumerate(items):
            label = f"{track}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object")
                continue
            item_id = item.get("id")
            if not item_id:
                warnings.append(f"{label} has no id")
            elif item_id in seen:
                errors.append(f"{label} duplicates id {item_id!r} in {track}")
            else:
                seen.add(str(item_id))
            start, end = item.get("startSec"), item.get("endSec")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                errors.append(f"{label} needs numeric startSec/endSec")
            elif not math.isfinite(start) or not math.isfinite(end) or end <= start:
                errors.append(f"{label} has invalid interval {start!r}..{end!r}")
            elif duration is not None and end > duration + 0.05:
                warnings.append(f"{label} ends after videoDuration ({end:.3f} > {duration:.3f})")

    media_entries = []
    if config.get("videoSrc"):
        media_entries.append(("videoSrc", config["videoSrc"]))
    for track in MEDIA_TRACKS:
        items = config.get(track, [])
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if isinstance(item, dict) and item.get("src"):
                media_entries.append((f"{track}[{index}].src", item["src"]))
    for label, src in media_entries:
        if not isinstance(src, str) or not src.strip():
            errors.append(f"{label} must be a non-empty string")
            continue
        if Path(src).is_absolute():
            warnings.append(f"{label} uses an absolute path and is not portable: {src}")
        if resolve_media(src, project_dir, public_dir) is None:
            errors.append(f"{label} does not exist: {src}")

    titles = config.get("titles", [])
    scene_titles = [item for item in titles if isinstance(item, dict) and item.get("style") == "cena"] if isinstance(titles, list) else []
    if scene_titles:
        sys.path.insert(0, str(root))
        try:
            from motioncore.cena import validar
        except Exception as exc:  # pragma: no cover - environment-specific
            warnings.append(f"could not import MotionCore scene validator: {exc}")
        else:
            for item in scene_titles:
                for problem in validar(item.get("cena") or {}, avisos=True):
                    target = errors if not problem.startswith("aviso:") else warnings
                    target.append(f"title {item.get('id', '<no id>')}: {problem}")

    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}")
    print(f"Checked {config_path}")
    counts = ", ".join(f"{name}={len(config.get(name, []))}" for name in TIMED_TRACKS if isinstance(config.get(name, []), list))
    print(f"Tracks: {counts}")
    if errors:
        print(f"FAILED with {len(errors)} error(s) and {len(warnings)} warning(s)")
        return 1
    print(f"OK with {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
