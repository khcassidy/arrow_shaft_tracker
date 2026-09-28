# Shaft Tracker

Shaft Tracker is a local web tool for archers. It tracks each wooden
arrow shaft you buy, records its spine and weight, and groups shafts
into matched sets. A matched set is a group of shafts with closely
similar spine and weight, ready to fletch together.

Spine is a measure of how much a shaft bends under a fixed load. Archers
match spine and weight across a set of arrows so the arrows fly the
same way.

## What it does

- Records each batch of shafts you buy, and each shaft's spine and
  weight.
- Lets you build matched sets by hand, on the Sets tab.
- Finds matched sets for you, on the Analysis tab. A solver searches
  for the largest matched set, or the most complete dozens (full or
  partial 12-arrow sets), across a whole batch.

## Stack

- Backend: Python, FastAPI, SQLite.
- Frontend: static HTML and CSS, plain JavaScript. There is no build
  step and no frontend framework.
- Solver: Google OR-Tools' CP-SAT solver, a constraint-based
  optimization solver, for the analysis engine.

## Quick start

This is the setup for local development. It needs Python 3.11 or
later. For deployment to a server on an older Python, see
[deploy/README.md](deploy/README.md) — Python 3.9 or later works there.

Run these commands from the project root, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python run.py --reload
```

The last command starts the dev server. It prints a local network
address, so you can also open the app from a phone or tablet at the
workbench.

## Tests

Run the full test suite with this command:

```powershell
pytest
```

## Project layout

- `core/` — the calculation and solver logic. This part touches no
  database and no web framework, so its tests run without either.
- `app/` — the FastAPI backend: the API routes and the database layer.
- `static/` — the frontend: HTML, CSS, and JavaScript modules.
- `tests/` — the automated test suite.
- `scripts/` — command-line tools, such as the workbook importer and
  the database backup script.
- `deploy/` — a self-contained copy of the app for deployment to a
  server. See [deploy/README.md](deploy/README.md).
- `planning/` — the original spreadsheet and design documents this
  project replaces.

## Data

Shaft Tracker stores your data in a local SQLite file,
`shafttracker.db`. Git ignores this file, so it stays out of the
repository. Back it up first, with this command, before any risky
change:

```powershell
python scripts\backup.py
```
<img width="1628" height="1028" alt="image" src="https://github.com/user-attachments/assets/2e62b3b5-2e4b-4590-bf10-8327baab9a1c" />

<img width="1620" height="1180" alt="image" src="https://github.com/user-attachments/assets/e01ffc28-840a-40e9-bc9e-b0f65b7a0ef2" />

<img width="1630" height="1435" alt="image" src="https://github.com/user-attachments/assets/f88a40ce-bd16-4b51-81d0-bfe8380ffd3c" />

<img width="1631" height="1444" alt="image" src="https://github.com/user-attachments/assets/b9cd7b1a-0052-46fa-b5be-bc3a05d3d32a" />

<img width="1631" height="224" alt="image" src="https://github.com/user-attachments/assets/058ef4e4-67ac-4b3e-b70a-8f9612cc2686" />

<img width="1617" height="1359" alt="image" src="https://github.com/user-attachments/assets/5e3913f1-630b-40dd-adf4-6166e5ce029b" />

<img width="1626" height="1388" alt="image" src="https://github.com/user-attachments/assets/f98012aa-1529-4144-8aba-5fd89d4a1491" />

<img width="1619" height="1432" alt="image" src="https://github.com/user-attachments/assets/d7a6217e-5933-4f01-ad1a-45f3aa9c7c80" />





