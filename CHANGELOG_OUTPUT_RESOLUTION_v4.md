# ANP Video Generator v4 — Output Resolution

## Added
- Dashboard output-resolution selector: 1080x1920 (default), 720x1280, 1920x1080, 1280x720, 1080x1080, and Custom.
- Selected output width/height are sent to the backend for every normal video render.
- Preview panel aspect ratio follows the selected output dimensions.
- Custom output dimensions are validated server-side (256–4096 px per side, even values required for H.264).

## Rendering behavior
- Template artwork is scaled proportionally into the selected output canvas.
- Template video/text/title areas and text styling are scaled by the same factor, keeping layout proportional.
- When the template and output aspect ratios differ, the design is centered on a dark letterbox canvas rather than stretched or distorted.
- For best edge-to-edge results, create templates at the same aspect ratio as the selected output preset.

## Validation
- Python backend compileall passed.
- Backend schema and video processor imports passed.
- Frontend production build was not verified: `vite` is not installed in the available `node_modules` directory; `npm ci` could not complete before timeout.


## Hotfix v4.1 — Template area bounds
- Fixed Auto Template coordinate generation to calculate areas from the final even-sized canvas, not the original odd-sized image dimensions.
- Fixed Manual Template drag rectangles so their right/bottom edges cannot exceed the even canvas.
- Backend area parsing now safely trims right/bottom overflow to the canvas boundary while still rejecting invalid origins and unusably small areas.
- Template save now writes normalized area coordinates back into JSON, preventing the same overflow from recurring on later reads.
- Added API preview regression coverage using a 1919×1079 source image and a 1918×1078 H.264 canvas.
- Output-resolution mapping now clamps mapped video/text/title rectangles to the final output canvas after scaling, preventing rounding overflow across portrait, landscape, square, and custom presets.
