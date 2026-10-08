# Klipe Workflows

Use only the section matching the request. Shared constraints remain in
`SKILL.md`.

## Create A New Project

1. Probe every supplied source with FFprobe.
2. Create a unique slug under `public/projects/`.
3. Copy or import source media into that project; avoid absolute paths.
4. Transcribe when speech determines timing.
5. Divide the content into semantic beats and write a short visual intention for
   each beat before creating layers.
6. Build an editable `edit_config.json`: primary clips first, then B-roll,
   titles/scenes, zooms, transitions, SFX, and music.
7. Validate, open, play, and render. Keep a clean original source available.

## Edit An Existing Project

1. Read the current config and inspect the timeline around the requested time.
2. Identify the smallest affected objects by ID and track.
3. Patch those objects without reordering unrelated clips or replacing the
   entire file.
4. Preserve manual user changes, including timings and track visibility.
5. Verify a few seconds before and after the changed range.

## Match A Reference

1. Compare layout, font family and weight, size, line breaks, alignment,
   position, entry motion, hold, exit motion, blur/shadow, and timing.
2. Use equivalent timestamps. A frame from the beginning cannot be compared to
   a settled frame from the middle.
3. Reproduce the behavior with editable Klipe layers. A flattened reference may
   guide the look but must not replace the project's editable structure.
4. Iterate from screenshots or rendered stills, not memory.

## Repair Preview, Save, Or Render

1. Reproduce the failure in the smallest project/range that still fails.
2. Determine whether the source of truth is editor state, saved JSON, preview
   compositor, or final renderer.
3. Fix the owning layer rather than compensating in another stage.
4. Check `node --check editor-server.js` for server changes and compile affected
   Python modules.
5. Compare preview and rendered output at the same timestamp. Include audio when
   the bug concerns mute, gain, fades, or source offsets.

## Portable Client Handoff

1. Include the editable project folder and all referenced local media.
2. Include `AGENTS.md` and `skills/klipe-editor/` with the Klipe application.
3. Remove caches, renders, databases, credentials, and unrelated client media.
4. Run the validator from the destination-shaped folder.
5. Confirm that the project opens without relinking and that preview works before
   rendering.

## Benchmark Against Another Engine

1. Use the same dimensions, FPS, duration, fonts, text, timing, and codec target.
2. Match the composition visually before timing it.
3. Separate cold and warm/cache-ready runs.
4. Record wall time, peak worker memory, output size, and machine context.
5. Do not equate smaller output with better performance or quality by itself.
