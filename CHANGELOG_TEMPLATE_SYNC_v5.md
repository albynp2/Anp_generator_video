# ANP Video Generator — Template Sync v5

## Changes
- Landscape Auto Template now places the video viewport across 100% of the canvas width, at approximately y=21.5% and height=45.8%, matching the user's red guide region.
- Portrait Auto Template video viewport expanded from 84% to 92% width.
- Auto text and title areas use wider centered bounds while remaining above/below the video viewport.
- Added `GET /api/templates/{name}/preview`, which composes the saved background image, video viewport, sample text, and title using the exact saved template config and Pillow text renderer.
- Dashboard Preview now requests the composed template preview instead of showing a plain PNG with a generic message overlay.
- Backend compileall and direct template preview smoke test passed (HTTP response object / valid PNG dimensions).

## Notes
- Saved templates are still the source of truth: `config/templates/<name>.json` and `assets/templates/<name>.png`.
- Existing templates keep their saved area coordinates. The new full-width geometry applies when a new template is created or re-saved in Auto Template mode. To update an existing template, open it in Template Builder, select/re-select Auto Template, then save with overwrite.
- Frontend production build was not run because `node_modules` is not present in this environment; run the Docker build on the target machine.
