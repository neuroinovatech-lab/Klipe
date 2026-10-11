# Speech, References, and Review

## Build From Speech

Use the edited timeline as the timing authority. Existing captions may contain
manual corrections: prefer them over the original transcript. A source transcript
must be remapped through keepRanges; never attach removed words to a surviving
sentence. For multiple sources, verify the source/time map before using a transcript.

Describe a short beat list: interval, spoken point, intended visual, source of
supporting imagery. Keep factual wording faithful to the speaker. Choose emphasis
and SFX by meaning; do not interpret a keyword match as proof that a cut is good.
Check the audio around any proposed pause cut, including the final consonant,
breath, and start of the next phrase. Do not delete every breath.

Use the existing authorization: when the user requested a full edit, proceed.
When they requested a preview before rendering, deliver the editable preview first.
For a new style, verify a representative short section before repeating it across
the project; this need not become an extra approval step.

## Match a Moving Reference

Compare at least entrance, settled state, and exit at equivalent speech timestamps.
Record font file and weight, line breaks, line offsets, baseline distance, size,
entry travel distance, duration, easing, stagger, and any requested blink timing.
Do not substitute opacity animation for a requested upward translation.
Keep every title's editable text wired to the scene parameters. Inspect the
rendered glyphs; a declared font family is not evidence that the font loaded.

If two attempts fail in the same way, inspect the responsible preview/render or
font path before making another visual guess. A paused screenshot cannot prove
that an animation matches.

## Local Assistant

There is no in-editor assistant panel; use the local tools from the agent chat.
Save pending editor changes before analyzing the on-disk config.
`POST /api/assistant/analyze` takes
`{config, faces: false}` and the current project's `X-Projeto` header. It returns
a job id; poll `/api/assistant/job?id=...` for the result. Analysis is read-only.
Suggestions are rule-based, grounded in the current captions/transcript. Applying
them must preserve ordinary editable clips; Save remains manual.
An analysis is invalid once the project snapshot changes.

The vision worker is optional. Install with `python tools/setup_assistant_vision.py`.
Face detection samples frames; absence of a detection does not prove a face is
clear. Check actual composition, especially with zooms and split layouts.

Person segmentation creates an alpha side-by-side video in the project and a
B-roll proposal with `foreground: true`. This layer goes above titles and below
captions in both preview and render. It is a generated mask asset, not an editable
rotoscope path. Verify edges, timing, hands, and background leakage. Automatic
generation currently accepts up to 30 seconds without a source transform or zoom.
Later source/zoom changes require regenerating the mask.

## Delivery Evidence

Check missing media, invalid intervals, accidental overlaps, fast captions, mute
states, text clipping, safe areas, and voice versus music/SFX by listening. The
assistant's structural report does not measure intelligibility or guarantee
perfect person segmentation. Verify the actual exported affected range when
changing composition. Name only checks actually run and disclose outstanding ones.
