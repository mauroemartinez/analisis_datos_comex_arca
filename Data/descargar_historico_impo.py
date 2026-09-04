# -*- coding: utf-8 -*-
"""
Descarga y consolida importaciones mensuales de ARCA.

Flujo:
  1. Descubre links mensuales desde la pagina oficial de ARCA.
  2. Descarga cada ZIP faltante.
  3. Extrae impo_YYYYMM.lst.
  4. Convierte el LST mensual a impo_YYYYMM.parquet.
  5. Une todos los impo_YYYYMM.parquet en impo_historico.parquet.

Uso recomendado:
  python Data/descargar_historico_impo.py --desde 201702 --hasta 202608

Para solo unir los Parquet ya existentes:
  python Data/descargar_historico_impo.py --sin-descarga
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import duckdb


DATA_DIR = Path(__file__).resolve().parent
ARCA_PAGE = (
    "https://arca.gob.ar/operadoresComercioExterior/"
    "informacionAgregada/informacion-agregada.asp"
)
ARCA_BASE = "https://arca.gob.ar"
HISTORICO_DEFAULT = DATA_DIR / "impo_historico.parquet"

IMPO_COLUMNS = {
    "ADU": "VARCHAR",
    "DESTINACION": "VARCHAR",
    "NUM_ITEM": "INTEGER",
    "FECHA": "VARCHAR",
    "NOMBRE_IMPORTADOR": "VARCHAR",
    "MEDIO_TRANSPORTE": "VARCHAR",
    "UNIDAD_MEDIDA": "VARCHAR",
    "CANT_UNIDAD_MEDIDA": "DOUBLE",
    "FOB_UNITARIO_USD": "DOUBLE",
    "FOB_TOTAL_USD": "DOUBLE",
    "DIVISA": "VARCHAR",
    "PAIS_ORIGEN": "VARCHAR",
    "PAIS_PROCEDENCIA": "VARCHAR",
    "POS_NCM": "VARCHAR",
    "ARANCEL_CONCEPTO": "VARCHAR",
    "ARANCEL_MONTO": "DOUBLE",
}

MONTHLY_RE = re.compile(r"^impo_(\d{6})\.parquet$")
DOWNLOAD_RE = re.compile(
    r"""href=["']([^"']*download\.aspx\?filename=(\d{6})\.zip)["']""",
    re.I,
)


def periodo_valido(value: str) -> str:
    if not re.fullmatch(r"\d{6}", value or ""):
        raise argparse.ArgumentTypeError("El periodo debe tener formato YYYYMM")
    month = int(value[4:6])
    if month < 1 or month > 12:
        raise argparse.ArgumentTypeError("El mes debe estar entre 01 y 12")
    return value


def request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 ARCA-data-downloader"
            )
        },
    )


def descubrir_descargas() -> dict[str, str]:
    with urllib.request.urlopen(request(ARCA_PAGE), timeout=60) as response:
        html = response.read().decode("utf-8", errors="ignore")

    links: dict[str, str] = {}
    for match in DOWNLOAD_RE.finditer(html):
        href = match.group(1)
        periodo = match.group(2)
        links[periodo] = urllib.parse.urljoin(ARCA_BASE, href)
    return dict(sorted(links.items()))


def filtrar_periodos(
    links: dict[str, str],
    desde: str | None,
    hasta: str | None,
    meses: list[str] | None,
) -> list[str]:
    periodos = sorted(links)
    if meses:
        faltantes = sorted(set(meses) - set(links))
        if faltantes:
            print("Aviso: estos periodos no estan publicados en el HTML:", ", ".join(faltantes))
        periodos = [p for p in meses if p in links]
    if desde:
        periodos = [p for p in periodos if p >= desde]
    if hasta:
        periodos = [p for p in periodos if p <= hasta]
    return periodos


def descargar_archivo(url: str, destino: Path, force: bool, retries: int = 3) -> bool:
    if destino.exists() and destino.stat().st_size > 0 and not force:
        print(f"  ZIP existente: {destino.name}")
        return False

    tmp = destino.with_suffix(destino.suffix + ".part")
    if tmp.exists():
        tmp.unlink()

    for intento in range(1, retries + 1):
        try:
            print(f"  Descargando {destino.name}")
            with urllib.request.urlopen(request(url), timeout=120) as response:
                total = int(response.headers.get("Content-Length") or 0)
                content_type = response.headers.get("Content-Type", "")
                if "text/html" in content_type.lower():
                    raise RuntimeError(f"respuesta HTML, no ZIP ({content_type})")

                recibido = 0
                ultimo_aviso = 0
                with tmp.open("wb") as out:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                        recibido += len(chunk)
                        if total:
                            pct = int(recibido * 100 / total)
                            if pct >= ultimo_aviso + 10:
                                print(f"    {pct:>3}% ({recibido / 1024**2:,.0f} MB)")
                                ultimo_aviso = pct
                        elif recibido - ultimo_aviso >= 250 * 1024**2:
                            print(f"    {recibido / 1024**2:,.0f} MB")
                            ultimo_aviso = recibido

            if tmp.stat().st_size < 1024:
                raise RuntimeError("archivo descargado demasiado chico")
            if not zipfile.is_zipfile(tmp):
                raise RuntimeError("el archivo descargado no es un ZIP valido")
            tmp.replace(destino)
            return True
        except (urllib.error.URLError, TimeoutError, RuntimeError, zipfile.BadZipFile) as exc:
            if tmp.exists():
                tmp.unlink()
            if intento == retries:
                print(f"  No se pudo descargar {destino.name}: {exc}")
                return False
            espera = 5 * intento
            print(f"  Reintento {intento}/{retries} en {espera}s: {exc}")
            time.sleep(espera)
    return False


def buscar_miembro_impo(zf: zipfile.ZipFile, periodo: str) -> str | None:
    esperado = f"impo_{periodo}.lst"
    nombres = zf.namelist()
    for nombre in nombres:
        if Path(nombre).name.lower() == esperado:
            return nombre

    patron = re.compile(rf"impo.*{periodo}.*\.(lst|txt)$", re.I)
    for nombre in nombres:
        if patron.search(Path(nombre).name):
            return nombre
    return None


def extraer_impo(zip_path: Path, periodo: str, lst_path: Path) -> bool:
    if lst_path.exists() and lst_path.stat().st_size > 0:
        print(f"  LST existente: {lst_path.name}")
        return False

    with zipfile.ZipFile(zip_path) as zf:
        miembro = buscar_miembro_impo(zf, periodo)
        if not miembro:
            print(f"  El ZIP no contiene impo_{periodo}.lst")
            return False
        print(f"  Extrayendo {Path(miembro).name}")
        with zf.open(miembro) as src, lst_path.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
    return True


def convertir_lst_a_parquet(lst_path: Path, parquet_path: Path, force: bool) -> bool:
    if parquet_path.exists() and parquet_path.stat().st_size > 0 and not force:
        print(f"  Parquet existente: {parquet_path.name}")
        return False

    tmp = parquet_path.with_suffix(".parquet.tmp")
    if tmp.exists():
        tmp.unlink()

    print(f"  Convirtiendo a {parquet_path.name}")
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    rel = con.read_csv(
        str(lst_path),
        delimiter="'",
        header=False,
        skiprows=2,
        columns=IMPO_COLUMNS,
    )
    rel.write_parquet(str(tmp), compression="zstd")
    tmp.replace(parquet_path)
    return True


def parquets_mensuales(data_dir: Path) -> list[Path]:
    archivos = []
    for path in data_dir.glob("impo_*.parquet"):
        match = MONTHLY_RE.fullmatch(path.name)
        if match:
            archivos.append(path)
    return sorted(archivos, key=lambda p: p.name)


def sql_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def combinar_historico(parquets: list[Path], salida: Path, force: bool) -> None:
    if not parquets:
        raise SystemExit("No hay impo_YYYYMM.parquet para unir.")
    if salida.exists() and not force:
        print(f"Historico existente: {salida.name}. Uso --force para regenerarlo.")
        return

    tmp = salida.with_suffix(".parquet.tmp")
    if tmp.exists():
        tmp.unlink()

    lista = ", ".join(f"'{sql_path(p)}'" for p in parquets)
    columnas = ",\n        ".join(IMPO_COLUMNS)
    sql = f"""
COPY (
    SELECT
        regexp_extract(filename, 'impo_([0-9]{{6}})\\.parquet', 1) AS PERIODO,
        {columnas}
    FROM read_parquet([{lista}], filename=true, union_by_name=true)
    ORDER BY PERIODO, DESTINACION, NUM_ITEM, ARANCEL_CONCEPTO
) TO '{sql_path(tmp)}' (FORMAT PARQUET, COMPRESSION ZSTD)
"""

    print(f"Uniendo {len(parquets)} meses en {salida.name}")
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute(sql)
    tmp.replace(salida)

    stats = con.execute(
        f"""
        SELECT
            count(*) AS filas,
            count(DISTINCT PERIODO) AS meses,
            min(PERIODO) AS desde,
            max(PERIODO) AS hasta
        FROM read_parquet('{sql_path(salida)}')
        """
    ).fetchone()
    print(
        "Historico listo: "
        f"{stats[0]:,} filas, {stats[1]} meses, {stats[2]} a {stats[3]}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", type=periodo_valido, help="Periodo inicial YYYYMM")
    parser.add_argument("--hasta", type=periodo_valido, help="Periodo final YYYYMM")
    parser.add_argument(
        "--mes",
        dest="meses",
        action="append",
        type=periodo_valido,
        help="Periodo puntual YYYYMM. Se puede repetir.",
    )
    parser.add_argument(
        "--salida",
        default=str(HISTORICO_DEFAULT),
        help="Parquet historico consolidado.",
    )
    parser.add_argument(
        "--sin-descarga",
        action="store_true",
        help="No descarga nada. Solo une los Parquet mensuales existentes.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reconvierte y regenera aunque existan archivos previos.",
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Conserva los ZIP descargados.",
    )
    parser.add_argument(
        "--keep-lst",
        action="store_true",
        help="Conserva los LST extraidos.",
    )
    parser.add_argument(
        "--solo-listar",
        action="store_true",
        help="Lista periodos detectados en ARCA y termina.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.sin_descarga:
        periodos = []
        links = {}
    else:
        links = descubrir_descargas()
        periodos = filtrar_periodos(links, args.desde, args.hasta, args.meses)

    if args.solo_listar:
        print(", ".join(periodos))
        print(f"{len(periodos)} periodos")
        return 0

    if not args.sin_descarga:
        if not periodos:
            raise SystemExit("No hay periodos para descargar con esos filtros.")

        print(f"Periodos a procesar: {len(periodos)}")
        print(f"Desde {periodos[0]} hasta {periodos[-1]}")

        for idx, periodo in enumerate(periodos, start=1):
            print(f"\n[{idx}/{len(periodos)}] {periodo}")
            parquet_path = DATA_DIR / f"impo_{periodo}.parquet"
            lst_path = DATA_DIR / f"impo_{periodo}.lst"
            zip_path = DATA_DIR / f"{periodo}.zip"

            if parquet_path.exists() and parquet_path.stat().st_size > 0 and not args.force:
                print(f"  Parquet existente: {parquet_path.name}")
                continue

            zip_creado = False
            lst_creado = False

            if not lst_path.exists():
                zip_creado = descargar_archivo(links[periodo], zip_path, args.force)
                if not zip_path.exists():
                    continue
                lst_creado = extraer_impo(zip_path, periodo, lst_path)

            if not lst_path.exists():
                print(f"  Salteo {periodo}: no hay LST de importacion.")
                continue

            convertir_lst_a_parquet(lst_path, parquet_path, args.force)

            if lst_creado and not args.keep_lst and lst_path.exists():
                lst_path.unlink()
                print(f"  Borrado LST temporal: {lst_path.name}")
            if zip_creado and not args.keep_zip and zip_path.exists():
                zip_path.unlink()
                print(f"  Borrado ZIP temporal: {zip_path.name}")

    parquets = parquets_mensuales(DATA_DIR)
    combinar_historico(parquets, Path(args.salida), args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
