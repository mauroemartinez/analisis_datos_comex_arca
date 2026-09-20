# Repository Guidelines

## Project Structure & Module Organization

This repository analyzes Argentine foreign trade data from ARCA/AFIP. The
pipeline's product is a single consolidated file, `Data/impo_historico.parquet`;
everything else under `Data/` (ZIP, LST, per-month Parquet) is a disposable
intermediate that gets deleted once it is folded into that file.

- `filtrar_posiciones.py`: filters import data by NCM positions listed in a local `posiciones_interes.txt`.
- `posiciones_interes.ejemplo.txt`: public-safe example list for testing the NCM filter.
- `Data/descargar_historico_impo.py`: downloads ARCA monthly ZIP files, converts import LST files to Parquet, and maintains the single `impo_historico.parquet`. `--actualizar` is the normal path (incremental, no full re-sort); `--desde/--hasta` for the initial full load; `--sin-descarga --force` to rebuild from whatever monthly Parquet files exist locally.
- `Data/_fuente_impo.py`: shared helper the query scripts use to resolve `impo_historico.parquet` (preferred) or a loose `impo_YYYYMM.parquet` (fallback).
- `Data/consultar_impo.py`: quick importer, NCM, summary, or SQL queries. Runs against the full historico when it exists.
- `Data/consultar_impo_polars.py`: same summary, written with polars instead of duckdb+pandas, kept as a side-by-side learning reference (see its docstring).
- `Data/tabla_final.py`: one-row-per-item table for one period (`--periodo YYYYMM`, defaults to the latest).
- `codigos/codigos_arca.py`: ARCA/AFIP lookup dictionaries for countries, customs offices, units, taxes, and transport modes.
- `Data/`: local data folder. Everything in it is ignored by Git.
- `notebooks/`: tutorial notebooks (basic to advanced) against `impo_historico.parquet`. Tracked in Git (exception to the general `*.ipynb` ignore) and must stay output-free; see "Notebooks" below.
- `explorer/index.html`: static, no-backend dashboard (filters, evolution/top-15 charts, period-over-period delta) that queries the Parquet directly in the browser via DuckDB-WASM — either a local file (no upload, works from a USB drive) or a remote URL (HTTP Range requests). See `docs/EXPLORACION_ONLINE.md`.
- `docs/EXPLORACION_ONLINE.md`: architecture decision for online/self-hosted exploration.
- `.claude/skills/actualizar-historico-arca/SKILL.md`: runbook for keeping the historico up to date; tracked in Git as the one exception to the general `.claude/` ignore.
- `exports/`: personal scratch/workspace folder for local files and exports. Fully gitignored except `exports/README.md`, which documents its purpose. Scripts never read or write here automatically.
- `assets/`: screenshots referenced from `README.md` (and other docs). Tracked in Git; keep it to illustrative images only, never real commercial data.

There is no formal `tests/` directory yet.

## Build, Test, and Development Commands

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run core workflows:

```powershell
python Data\consultar_impo.py --resumen
python filtrar_posiciones.py --xlsx
python Data\tabla_final.py
python Data\descargar_historico_impo.py --actualizar
```

Check Python syntax without writing bytecode:

```powershell
python -B -m py_compile filtrar_posiciones.py Data\consultar_impo.py Data\consultar_impo_polars.py Data\tabla_final.py Data\descargar_historico_impo.py Data\_fuente_impo.py codigos\codigos_arca.py
```

## Coding Style & Naming Conventions

Use Python 3, UTF-8, 4-space indentation, and clear Spanish domain names when they match Comercio Exterior terminology. Keep monthly data files named with the `YYYYMM` pattern, for example `impo_202607.parquet`. Prefer portable relative paths over machine-specific paths.

Do not use em dashes in documentation, comments, or notebooks.

## Notebooks

`notebooks/*.ipynb` are tutorials meant for publication, not scratch analysis:
keep them free of outputs, local paths, and real commercial data before
committing (`jupyter nbconvert --clear-output` or re-run and save clean).
Exploratory notebooks with real findings belong in `exports/` (gitignored),
never in `notebooks/`. Any new tutorial notebook must be validated end to end
(e.g. `nbclient`/`jupyter nbconvert --execute`) before committing.

## Testing Guidelines

Until a test suite exists, validate changes by running the core workflows above against `Data/impo_historico.parquet` (or a local `Data/impo_YYYYMM.parquet` if that is what is being tested). For query changes, include at least one summary or small filtered query and compare row counts or expected columns.

## Commit & Pull Request Guidelines

Use concise, imperative commit messages such as `Add historical downloader` or `Update Data path handling`.

Pull requests should describe the change, list commands run, note any data files required locally, and confirm that ignored formats such as `.csv`, `.xlsx`, `.parquet`, and `.lst` were not committed.

## Data & Security Notes

Source data comes from ARCA Información Agregada de Comercio Exterior. Keep raw data, generated exports, exploratory notebooks with outputs, and real commercial NCM lists out of Git. The `.gitignore` excludes common data formats, local exports, virtual environments, tool caches, and local `posiciones_interes.txt`, with narrow tracked exceptions for `notebooks/*.ipynb` and `.claude/skills/actualizar-historico-arca/`.
