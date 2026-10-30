# ANP Video Generator — R&D Change Log v4

## Template Builder
- Added `POST /api/templates/preview` to render previews through the same Pillow text renderer used by final video jobs.
- Preview includes the configured video viewport placeholder and both text layers.
- Font theme, text style, text size, outline, shadow/glow, and text background changes refresh the preview with a short debounce.
- Auto Template hides manual area controls and resets the text style to the requested preset.
- Manual Template exposes Video Area, Text Area, and Title Area controls and draws editing guides.
- Auto preset defaults: 20 px main text, 20 px title, Shadow style, white text, #333333 background at 10% opacity, 0 padding, and 0 radius.
- Removed the orange video-area border from the server preview because it is not part of the final rendered frame.

## Render quality
- Default H.264 CRF changed from 17 to 14 for higher visual quality.
- Kept `medium` preset to balance encoding time on laptop CPUs.
- Documented that a small template video viewport still downsizes the source and cannot preserve details beyond its pixel dimensions.

## Validation
- Python backend compileall passed.
- `POST /api/templates/preview` smoke test returned HTTP 200 and a valid PNG.
- Full frontend Vite build could not be completed in this environment because npm dependency installation timed out; dependencies are not bundled in the project ZIP.
