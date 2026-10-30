# ANP-CLIPPER R&D v3 — Dynamic Template Handling

## Changes
- Template PNGs are optional at runtime: if a template's configured image is missing, that template is excluded from `GET /api/templates` without repeated warning logs. Other valid templates remain available.
- The frontend refreshes the template list every 15 seconds and when the browser tab regains focus.
- If the selected template disappears, the UI selects `default` if available, otherwise the first available template. If no valid templates remain, it clears the selection and disables Generate Clip until a valid template is added.
- README documents the dynamic template behavior.
- Retains the ANP-CLIPPER branding and R&D performance settings from v2.

## Validation
- Python source compile check passed.
- A temporary-directory test verified that a template with a missing PNG is excluded while a valid template remains available.
- Frontend production build was not completed in this environment because `npm ci` timed out; Docker should build frontend dependencies during `docker compose up --build`.

## Apply
Extract this ZIP to a new folder, then run:

```powershell
docker compose down
docker compose up --build -d
docker compose logs -f
```

The project uses bind mounts for `assets` and `config`, so changes made to template PNG/JSON files are reflected without rebuilding the backend image. The frontend is rebuilt as part of `docker compose up --build`.
