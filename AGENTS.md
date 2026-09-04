# Repository Guidelines

## Project Structure & Module Organization

This repository analyzes Argentine foreign trade data from ARCA/AFIP.

- `filtrar_posiciones.py`: filters monthly import data by NCM positions listed in a local `posiciones_interes.txt`.
- `posiciones_interes.ejemplo.txt`: public-safe example list for testing the NCM filter.
- `Data/descargar_historico_impo.py`: downloads ARCA monthly ZIP files, converts import LST files to Parquet, and builds a consolidated historical Parquet.
- `Data/consultar_impo.py`: runs quick importer, NCM, summary, or SQL queries against the monthly import Parquet.
- `Data/tabla_final.py`: generates a clean one-row-per-item import table.
- `codigos/codigos_arca.py`: ARCA/AFIP lookup dictionaries for countries, customs offices, units, taxes, and transport modes.
- `Data/`: local monthly data folder. Data files are ignored by Git.

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
python Data\descargar_historico_impo.py --sin-descarga
```

Check Python syntax without writing bytecode:

```powershell
python -B -m py_compile filtrar_posiciones.py Data\consultar_impo.py Data\tabla_final.py Data\descargar_historico_impo.py codigos\codigos_arca.py
```

## Coding Style & Naming Conventions

Use Python 3, UTF-8, 4-space indentation, and clear Spanish domain names when they match Comercio Exterior terminology. Keep monthly data files named with the `YYYYMM` pattern, for example `impo_202607.parquet`. Prefer portable relative paths over machine-specific paths.

Do not use em dashes in documentation, comments, or notebooks.

## Testing Guidelines

Until a test suite exists, validate changes by running the core workflows above against a local file matching `Data/impo_YYYYMM.parquet`. For query changes, include at least one summary or small filtered query and compare row counts or expected columns.

## Commit & Pull Request Guidelines

Use concise, imperative commit messages such as `Add historical downloader` or `Update Data path handling`.

Pull requests should describe the change, list commands run, note any data files required locally, and confirm that ignored formats such as `.csv`, `.xlsx`, `.parquet`, and `.lst` were not committed.

## Data & Security Notes

Source data comes from ARCA Informacion Agregada de Comercio Exterior. Keep raw data, generated exports, notebooks with outputs, and real commercial NCM lists out of Git. The `.gitignore` excludes common data formats, local exports, virtual environments, notebooks, tool caches, and local `posiciones_interes.txt`.
