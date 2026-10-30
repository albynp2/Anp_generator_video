# ANP Video Generator v4.2 — Full Screen Layout

## New dashboard layout selection
- Added `Template Background`: video remains inside the saved template video area.
- Added `Full Screen Video`: video is composited over the entire output canvas, with text/title layers on top.
- Full Screen defaults to `Contain` blur-fill, preserving the complete source content while a blurred, darkened duplicate fills the portrait canvas.
- `Cover` remains available for crop-to-fill when the user prefers a close-up.

## Embedded letterbox handling
- Full Screen + Contain runs FFmpeg cropdetect on up to five seconds of the selected clip.
- Stable black borders are detected and removed from both the blurred background and foreground copy.
- If detection is unavailable or not meaningful, the renderer safely falls back to the original full frame.

## Output resolution wiring
- Added output_width/output_height to the API request schema.
- Dashboard now sends the selected output dimensions to backend.
- Existing presets (portrait, landscape, square, custom) now reach the render pipeline rather than silently using backend defaults.

## Validation
- Python compileall: PASS.
- Backend module import and Pydantic schema: PASS.
- FFmpeg Full Screen + Contain blur-fill on user-provided MP4: PASS, 1080x1920 at 30 FPS.
- FFmpeg Template Background path: PASS.
- Frontend JSX transpile/syntax check (Home.jsx, TemplateBuilder.jsx, api.js): PASS.
- Full Vite production build: BLOCKED because npm dependencies could not be fetched in this environment (offline npm cache miss); no claim of production build success.
