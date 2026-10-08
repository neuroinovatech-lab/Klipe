---
name: klipe-editor
description: Edit, create, repair, validate, and render Klipe video projects with timeline-safe changes and MotionCore preview/render parity. Use for work inside a Klipe repository or a public/projects/SLUG project; do not use for unrelated generic FFmpeg or Remotion tasks unless they are being compared with Klipe.
---

# Klipe Editor

Work on the real editable Klipe project, not only on a flattened MP4. Preserve
the user's timeline and make the smallest change that satisfies the request.

## Start Here

1. Locate the Klipe root by finding `editor-server.js`, `editor.html`, and
   `motioncore/` together. Do not assume the current directory is the app that
   is actually running.
2. Resolve the project slug from the URL or request and inspect
   `public/projects/<slug>/edit_config.json` before editing anything.
3. Inspect existing changes and media. Treat unknown work as user work; never
   regenerate the whole config to make a narrow correction.
4. Measure source media with FFprobe. Do not infer duration, frame rate,
   dimensions, or audio presence from filenames.
5. Choose the applicable mode in [references/workflows.md](references/workflows.md).

## Editing Decisions

- Let the subject and reference determine typography, palette, material, and
  motion language. Do not inherit the last video's look unless continuity was
  requested.
- Build around content beats rather than equal time slices. On-screen text must
  be anchored to what is said or deliberately identified as editorial copy.
- Use `videoClips` for the primary footage, `brolls` for supporting media,
  `titles` for native styles or MotionCore scenes, `zooms` for camera emphasis,
  and the audio tracks for music/SFX. Keep each concern editable.
- For vertical video, prefer top/bottom compositions over side-by-side panels
  unless the brief asks for another layout.
- In a motion-heavy edit, do not leave still images inert. Give them restrained
  pan, zoom, reveal, or parallax appropriate to the beat.
- Use transitions to express a beat change. Do not hide a bad cut with a random
  effect, and do not leave an accidental dry cut between designed sections.
- Keep captions and titles as editable text. Do not bake them into replacement
  footage merely to make preview look correct.

## MotionCore Scenes

For custom motion, read these files from the active Klipe root as needed:

- `motioncore/cena/PROMPT.md` for universal creative rules.
- `motioncore/cena/BRIEFING.md` for turning speech into beats.
- `motioncore/cena/DSL.md` for the exact scene schema and supported fields.

Use `style: "cena"` with a validated `cena` object. Prefer native DSL
primitives, including animated `numero`, before introducing a hardcoded style.
Never invent a field: run `motioncore.cena.validar()` and fix every error.

## Project Integrity

- A project is isolated by slug. Never write one project's config or media into
  another project.
- Store distributable media inside the project or an included public library.
  Avoid absolute paths and references to another client's project.
- Manual Save is authoritative in the editor. Direct file edits must not be
  presented as an editor Save test; verify both paths when save behavior matters.
- Preview and render must agree in composition, timing, visibility, opacity,
  audio mix, and titles.
- Do not include credentials, databases, caches, generated renders, or personal
  media in a public package.

## Required Verification

Run the bundled validator before opening the editor:

```bash
python skills/klipe-editor/scripts/validate_project.py public/projects/<slug>/edit_config.json
```

Then:

1. Open `/p/<slug>` and verify the expected tracks and total duration.
2. Play the affected beats at normal speed and inspect representative frames.
3. Test Save when the task touches persistence.
4. Render the affected range or full project and compare it with preview.
5. Report the project path, render path, checks run, and any remaining mismatch.

Do not claim a visual match from config inspection alone. For reference-driven
work, compare screenshots at equivalent timestamps.
