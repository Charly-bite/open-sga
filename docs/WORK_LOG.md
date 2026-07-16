# Work Log

Use this file to record every meaningful change made to the SGA dev workspace.
The goal is to avoid repeating the same work twice and to keep the recovery
and restructuring history easy to audit.

## How to use

- Add one entry per change set.
- Keep each entry short, factual, and date-stamped.
- Include the files changed and the reason for the change.
- If a change affects runtime behavior, document the new expected behavior.

## Entry format

```md
### YYYY-MM-DD - Short title
- Files: `path/to/file.py`, `path/to/file.html`
- Change: What was changed.
- Reason: Why it was changed.
- Result: What should now happen.
```

## Current Entries

### 2026-04-01 - Server execution ownership policy
- Files: `.github/copilot-instructions.md`, `.github/copilot-instructions.development.md`, `.github/skills/sga-development-workflow/SKILL.md`
- Change: Added explicit rules that AI agents must not auto-start/keep servers running unless requested, and must close verification terminals immediately after checks.
- Reason: User requires absolute manual control over server runtime and terminal state.
- Result: Future agent behavior should no longer leave hidden/background server terminals open.

### 2026-04-01 - Batch number hydration
- Files: `sga_web/routes/control_interno.py`, `sga_web/core/tara_weight_manager.py`
- Change: Batch numbers now hydrate from stored data, recent label queue history, and live SAP batch stock; empty SQL product classification tables now fall back to the JSON cache.
- Reason: The Control Interno batch column was still blank because the stored classification table had no batch data.
- Result: The batch column should now display real lot values whenever they exist in the queue or SAP.

### 2026-04-01 - Populate main workspace tabs
- Files: `sga_web/routes/orders.py`, `sga_web/routes/control_interno.py`, `sga_web/templates/control_interno/index.html`, `label_templates/*.json`
- Change: Bootstrap recent orders from SAP when the local order store is empty, expose batch display data in Control Interno, and restore the original label template JSON files.
- Reason: The Estado de Pedidos, Visor de Estado de Pedidos, Plantillas de Etiquetas, and Control Interno tabs were showing empty states.
- Result: The order tabs now have a bootstrap path, the control grid shows batch/lote data, and the templates tab can list real templates again.

### 2026-04-01 - Work log initialized
- Files: `docs/WORK_LOG.md`, `.env`
- Change: Added a persistent work log for future changes and stored `DEV_HOST` / `DEV_PORT` in the environment file.
- Reason: Keep implementation notes in one place and prevent duplicate work across sessions.
- Result: Future edits can be documented immediately and the dev server bind is explicit.

### 2026-04-01 - Dedicated development bind
- Files: `sga_web/run_development.py`, `.env`
- Change: The development server now binds to `127.0.0.2:5001` by default, with `DEV_HOST` and `DEV_PORT` overrides.
- Reason: Prevent collisions with the pre-production server and avoid confusion on shared network interfaces.
- Result: Development and pre-production can run independently on this machine.

### 2026-04-01 - Connection status cleanup
- Files: `sga_web/app.py`, `sga_web/routes/main.py`
- Change: Dashboard database and SAP status now use live connection checks.
- Reason: The UI was showing stale fallback/disconnected states.
- Result: The dashboard should reflect the actual runtime connection state.