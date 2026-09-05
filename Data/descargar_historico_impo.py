# -*- coding: utf-8 -*-
"""
Descarga y consolida importaciones mensuales de ARCA en un unico Parquet
historico (Data/impo_historico.parquet).

Flujo:
  1. Descubre links mensuales desde la página oficial de ARCA.
  2. Descarga cada ZIP faltante.
  3. Extrae impo_YYYYMM.lst (salteando los meses que solo tienen reporte
     agregado, sin detalle por importador).
  4. Convierte el LST mensual a impo_YYYYMM.parquet.
  5. Une los impo_YYYYMM.parquet en impo_historico.parquet y borra los
     mensuales ya incorporados (--keep-mensuales para conservarlos).

Carga inicial completa (una sola vez; tarda y usa harto disco temporal):
  python Data/descargar_historico_impo.py --desde 201702 --hasta 202608

Actualizacion periodica (uso recomendado de ahi en adelante): descarga y
agrega solo los periodos nuevos, sin resortear todo el historico:
  python Data/descargar_historico_impo.py --actualizar

Para solo unir los Parquet ya existentes en Data/:
  python Data/descargar_historico_impo.py --sin-descarga --force
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


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

NUMERIC_COLUMNS = ("NUM_ITEM", "CANT_UNIDAD_MEDIDA", "FOB_UNITARIO_USD", "FOB_TOTAL_USD", "ARANCEL_MONTO")
PYARROW_TYPES = {"VARCHAR": pa.string(), "INTEGER": pa.int32(), "DOUBLE": pa.float64()}

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
            print("Aviso: estos periodos no están publicados en el HTML:", ", ".join(faltantes))
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
                raise RuntimeError("el archivo descargado no es un ZIP válido")
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
    # El nombre del archivo de importaciones varia segun el mes: algunos ZIP
    # traen "impo_YYYYMM.lst", otros "impo_YYYY_MM.lst". Se compara solo por
    # los digitos del nombre (ignorando separadores) para cubrir ambas
    # variantes, y se excluyen los "total_impo_..." y "expo_..." que tambien
    # contienen "impo". Los "impo_agregado_..." se excluyen aparte: son un
    # reporte agregado (sin detalle por declaracion/importador) con un
    # esquema de columnas totalmente distinto, incompatible con este pipeline.
    for nombre in zf.namelist():
        base = Path(nombre).name.lower()
        if not base.startswith("impo") or "agregado" in base:
            continue
        if not base.endswith((".lst", ".txt")):
            continue
        if "".join(re.findall(r"\d", base)) == periodo:
            return nombre
    return None


def solo_tiene_agregado(zf: zipfile.ZipFile) -> bool:
    # Los nombres de los "agregado" de estos meses vienen con typos del lado
    # de ARCA (mes sin cero a la izquierda, digitos de mas, etc.), asi que no
    # se valida el periodo dentro del nombre: alcanza con que el ZIP (que ya
    # es especifico de un periodo por la URL de descarga) tenga un archivo de
    # importaciones agregado y ninguno transaccional.
    return any(
        Path(nombre).name.lower().startswith("impo")
        and "agregado" in Path(nombre).name.lower()
        and Path(nombre).name.lower().endswith((".lst", ".txt"))
        for nombre in zf.namelist()
    )


def extraer_impo(zip_path: Path, periodo: str, lst_path: Path) -> bool:
    if lst_path.exists() and lst_path.stat().st_size > 0:
        print(f"  LST existente: {lst_path.name}")
        return False

    with zipfile.ZipFile(zip_path) as zf:
        miembro = buscar_miembro_impo(zf, periodo)
        if not miembro:
            if solo_tiene_agregado(zf):
                print(
                    f"  {periodo}: ARCA solo publico el reporte agregado (sin detalle "
                    "por importador/declaracion) para este mes. Se omite: esquema "
                    "incompatible con el historico transaccional."
                )
            else:
                print(f"  El ZIP no contiene impo_{periodo}.lst")
            return False
        print(f"  Extrayendo {Path(miembro).name}")
        with zf.open(miembro) as src, lst_path.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
    return True


def convertir_lst_a_parquet(lst_path: Path, parquet_path: Path, force: bool, memoria_limite: str = "500MB") -> bool:
    if parquet_path.exists() and parquet_path.stat().st_size > 0 and not force:
        print(f"  Parquet existente: {parquet_path.name}")
        return False

    tmp = parquet_path.with_suffix(".parquet.tmp")
    if tmp.exists():
        tmp.unlink()

    print(f"  Convirtiendo a {parquet_path.name}")
    con = duckdb.connect()
    try:
        con.execute("PRAGMA threads=1")
        con.execute(f"PRAGMA memory_limit='{memoria_limite}'")
        con.execute(f"PRAGMA temp_directory='{sql_path(DATA_DIR)}'")
        # Se lee todo como VARCHAR: algunos items no tienen tributo asociado y el
        # campo numerico queda relleno de espacios en vez de vacio, lo que rompe
        # la deteccion de tipo de DuckDB si se tipa directo en el read_csv.
        raw_columns = {col: "VARCHAR" for col in IMPO_COLUMNS}
        rel = con.read_csv(
            str(lst_path),
            delimiter="'",
            quotechar="",
            header=False,
            skiprows=2,
            columns=raw_columns,
            null_padding=True,
        )
        con.register("raw_impo", rel)
        select_cols = ", ".join(
            f'TRY_CAST(NULLIF(TRIM("{col}"), \'\') AS {tipo}) AS "{col}"'
            if col in NUMERIC_COLUMNS
            else f'"{col}"'
            for col, tipo in IMPO_COLUMNS.items()
        )
        # El .lst trae un pie de reporte (lineas en blanco y "N rows selected.")
        # despues de la ultima fila real; se descarta validando que FECHA tenga
        # formato de periodo YYYYMM.
        con.sql(
            f"""SELECT {select_cols} FROM raw_impo
            WHERE regexp_matches(TRIM("FECHA"), '^[0-9]{{6}}$')"""
        ).write_parquet(str(tmp), compression="zstd")
    finally:
        con.close()
    tmp.replace(parquet_path)
    return True


def convertir_lst_a_parquet_liviano(lst_path: Path, parquet_path: Path, force: bool, lote: int = 100_000) -> bool:
    """Igual que convertir_lst_a_parquet pero sin DuckDB: lee el .lst linea a
    linea con Python puro y escribe el Parquet por lotes chicos con pyarrow.
    No hay motor de consultas de por medio, asi que el pico de memoria queda
    acotado al tamano del lote sin importar cuanta RAM libre haya."""
    if parquet_path.exists() and parquet_path.stat().st_size > 0 and not force:
        print(f"  Parquet existente: {parquet_path.name}")
        return False

    tmp = parquet_path.with_suffix(".parquet.tmp")
    if tmp.exists():
        tmp.unlink()

    print(f"  Convirtiendo (modo liviano) a {parquet_path.name}")
    columnas = list(IMPO_COLUMNS)
    schema = pa.schema([(col, PYARROW_TYPES[tipo]) for col, tipo in IMPO_COLUMNS.items()])
    buffers = {col: [] for col in columnas}

    def vaciar(writer):
        if not buffers[columnas[0]]:
            return
        arrays = []
        for col, tipo in IMPO_COLUMNS.items():
            valores = buffers[col]
            if col in NUMERIC_COLUMNS:
                conv = int if tipo == "INTEGER" else float
                valores = [conv(v) if v is not None else None for v in valores]
            arrays.append(pa.array(valores, type=PYARROW_TYPES[tipo]))
        writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
        for col in columnas:
            buffers[col].clear()

    with lst_path.open("r", encoding="utf-8") as f, pq.ParquetWriter(str(tmp), schema, compression="zstd") as writer:
        f.readline()
        f.readline()
        for linea in f:
            partes = linea.rstrip("\n").split("'")
            if len(partes) != len(columnas):
                continue
            fecha = partes[3].strip()
            if not re.fullmatch(r"\d{6}", fecha):
                continue
            for col, valor in zip(columnas, partes):
                if col in NUMERIC_COLUMNS:
                    valor = valor.strip()
                    buffers[col].append(valor if valor else None)
                else:
                    buffers[col].append(valor)
            if len(buffers[columnas[0]]) >= lote:
                vaciar(writer)
        vaciar(writer)

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


def max_periodo_historico(salida: Path) -> str | None:
    if not salida.exists():
        return None
    con = duckdb.connect()
    try:
        row = con.execute(
            f"SELECT max(PERIODO) FROM read_parquet('{sql_path(salida)}')"
        ).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def ordenar_parquet_mensual(parquet_path: Path) -> None:
    """Reordena un Parquet mensual por (DESTINACION, NUM_ITEM, ARANCEL_CONCEPTO).
    Un solo mes entra comodo en memoria, asi que a diferencia del historico
    completo esto no necesita derramar a disco."""
    tmp = parquet_path.with_suffix(".sort.tmp")
    if tmp.exists():
        tmp.unlink()
    con = duckdb.connect()
    try:
        con.execute("PRAGMA threads=1")
        con.execute("PRAGMA memory_limit='500MB'")
        con.sql(
            f"""SELECT * FROM read_parquet('{sql_path(parquet_path)}')
            ORDER BY DESTINACION, NUM_ITEM, ARANCEL_CONCEPTO"""
        ).write_parquet(str(tmp), compression="zstd")
    finally:
        con.close()
    tmp.replace(parquet_path)


def agregar_al_historico(nuevos: list[Path], salida: Path) -> None:
    """Agrega meses nuevos al historico sin resortear las cientos de millones
    de filas ya existentes.

    Importante: esto NO usa un UNION ALL de DuckDB para pegar el historico
    viejo con los meses nuevos. Un intento anterior lo hizo asi (confiando en
    que sin ORDER BY, un UNION ALL de dos scans secuenciales con threads=1
    preserva el orden de lectura) y en la practica el resultado salio
    desordenado: DuckDB no garantiza el orden de un UNION ALL. En cambio, acá
    se copian los row groups de cada Parquet de entrada tal cual, uno por
    uno, con pyarrow: no hay motor de consultas de por medio que pueda
    reordenar nada, así que el orden de salida es exactamente "todo el
    historico viejo, despues cada mes nuevo" sin ambigüedad. Cada mes nuevo
    se ordena antes por separado (chico, entra en memoria); como PERIODO ya
    queda creciente entre archivos, el resultado global queda bien ordenado
    sin un ORDER BY completo sobre todo el dataset. Se valida al final que
    haya quedado ordenado, como red de seguridad."""
    if not nuevos:
        return

    for p in nuevos:
        ordenar_parquet_mensual(p)

    tmp = salida.with_suffix(".parquet.tmp")
    if tmp.exists():
        tmp.unlink()

    columnas_salida = ["PERIODO"] + list(IMPO_COLUMNS)
    schema_salida = pa.schema(
        [("PERIODO", pa.string())] + [(col, PYARROW_TYPES[tipo]) for col, tipo in IMPO_COLUMNS.items()]
    )

    print(f"Agregando {len(nuevos)} mes(es) nuevos a {salida.name} (sin resortear el historico completo)")

    # pyarrow no libera el handle del Parquet leido hasta que el objeto se
    # destruye. En Windows un rename/replace falla si el archivo destino
    # sigue abierto, asi que hay que soltar pf_viejo (y la conexion de
    # DuckDB de la validacion) explicitamente ANTES de tmp.replace(salida).
    writer = pq.ParquetWriter(str(tmp), schema_salida, compression="zstd")
    try:
        pf_viejo = pq.ParquetFile(str(salida))
        try:
            for i in range(pf_viejo.num_row_groups):
                tabla = pf_viejo.read_row_group(i, columns=columnas_salida)
                writer.write_table(tabla.select(columnas_salida))
        finally:
            del pf_viejo

        for p in nuevos:
            periodo = MONTHLY_RE.fullmatch(p.name).group(1)
            pf_nuevo = pq.ParquetFile(str(p))
            try:
                for i in range(pf_nuevo.num_row_groups):
                    tabla = pf_nuevo.read_row_group(i)
                    tabla = tabla.add_column(0, "PERIODO", pa.array([periodo] * tabla.num_rows, type=pa.string()))
                    writer.write_table(tabla.select(columnas_salida))
            finally:
                del pf_nuevo
    finally:
        writer.close()

    con = duckdb.connect()
    try:
        desorden = con.execute(
            f"""
            SELECT count(*) FROM (
                SELECT PERIODO, lag(PERIODO) OVER () AS anterior
                FROM read_parquet('{sql_path(tmp)}')
            ) WHERE anterior IS NOT NULL AND PERIODO < anterior
            """
        ).fetchone()[0]
    finally:
        con.close()

    if desorden:
        tmp.unlink()
        raise SystemExit(
            "El agregado incremental quedo desordenado (no deberia pasar; "
            "si ves esto es un bug en agregar_al_historico, no un problema "
            "de datos). Volve a correr con --sin-descarga --force para "
            "regenerar todo el historico desde cero mientras se investiga."
        )

    tmp.replace(salida)

    con = duckdb.connect()
    try:
        stats = con.execute(
            f"""
            SELECT count(*), count(DISTINCT PERIODO), min(PERIODO), max(PERIODO)
            FROM read_parquet('{sql_path(salida)}')
            """
        ).fetchone()
    finally:
        con.close()
    print(
        "Histórico actualizado: "
        f"{stats[0]:,} filas, {stats[1]} meses, {stats[2]} a {stats[3]}"
    )


def combinar_historico(parquets: list[Path], salida: Path, force: bool) -> bool:
    if not parquets:
        raise SystemExit("No hay impo_YYYYMM.parquet para unir.")
    if salida.exists() and not force:
        print(f"Histórico existente: {salida.name}. Uso --force para regenerarlo.")
        return False

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
    try:
        con.execute("PRAGMA threads=2")
        con.execute("PRAGMA memory_limit='1GB'")
        con.execute(f"PRAGMA temp_directory='{sql_path(DATA_DIR)}'")
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
    finally:
        con.close()
    print(
        "Histórico listo: "
        f"{stats[0]:,} filas, {stats[1]} meses, {stats[2]} a {stats[3]}"
    )
    return True


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
        help="Parquet histórico consolidado.",
    )
    parser.add_argument(
        "--sin-descarga",
        action="store_true",
        help="No descarga nada. Solo une los Parquet mensuales existentes.",
    )
    parser.add_argument(
        "--actualizar",
        action="store_true",
        help=(
            "Descarga y agrega solo los periodos posteriores al ultimo que "
            "ya esta en --salida, sin re-descargar ni re-ordenar todo el "
            "historico previo. Pensado para correr periodicamente. Si "
            "--salida todavia no existe, hace una carga completa."
        ),
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
        help="Conserva los LST extraídos.",
    )
    parser.add_argument(
        "--keep-mensuales",
        action="store_true",
        help=(
            "Conserva los impo_YYYYMM.parquet ya incorporados al historico. "
            "Por defecto se borran despues de un merge exitoso para dejar un "
            "unico archivo consolidado (se pueden regenerar en cualquier "
            "momento con --sin-descarga --force si el ZIP/LST original ya no "
            "esta, o re-descargando ese periodo puntual con --mes)."
        ),
    )
    parser.add_argument(
        "--solo-listar",
        action="store_true",
        help="Lista periodos detectados en ARCA y termina.",
    )
    parser.add_argument(
        "--memoria-limite",
        dest="memoria_limite",
        default="500MB",
        help="Limite de memoria para DuckDB al convertir cada mes (ignorado con --liviano).",
    )
    parser.add_argument(
        "--liviano",
        action="store_true",
        help=(
            "Convierte sin DuckDB, leyendo el .lst linea a linea y escribiendo "
            "el Parquet por lotes chicos. Mas lento pero con memoria casi "
            "constante; usalo si --memoria-limite no alcanza."
        ),
    )
    parser.add_argument("--convertir-uno", metavar="PERIODO", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.convertir_uno:
        periodo = args.convertir_uno
        lst_path = DATA_DIR / f"impo_{periodo}.lst"
        parquet_path = DATA_DIR / f"impo_{periodo}.parquet"
        if args.liviano:
            convertir_lst_a_parquet_liviano(lst_path, parquet_path, force=True)
        else:
            convertir_lst_a_parquet(lst_path, parquet_path, force=True, memoria_limite=args.memoria_limite)
        return 0

    salida = Path(args.salida)
    incremental = False
    if args.actualizar:
        if args.force:
            raise SystemExit("--actualizar y --force son incompatibles: --force resortea todo el historico.")
        ultimo = max_periodo_historico(salida)
        if ultimo is None:
            print("--actualizar: no hay historico previo en --salida, se hace una carga completa.")
        else:
            incremental = True
            siguiente = f"{int(ultimo) + 1:06d}"
            args.desde = max(args.desde, siguiente) if args.desde else siguiente
            print(f"--actualizar: historico existente llega a {ultimo}. Buscando periodos desde {args.desde}.")

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

    if incremental and not periodos:
        print("--actualizar: no hay periodos nuevos publicados todavia.")
        return 0

    procesados: list[Path] = []

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
                procesados.append(parquet_path)
                continue

            zip_creado = False
            lst_creado = False

            if not lst_path.exists():
                zip_creado = descargar_archivo(links[periodo], zip_path, args.force)
                if not zip_path.exists():
                    continue
                lst_creado = extraer_impo(zip_path, periodo, lst_path)

            if not lst_path.exists():
                print(f"  Salteo {periodo}: no hay LST de importación.")
                continue

            # Conversion en un subproceso aparte: cada mes puede pesar varios GB
            # en RAM incluso con memory_limit bajo, y correrlo en un proceso
            # nuevo asegura que el sistema operativo libere toda esa memoria al
            # terminar, en vez de confiar en que Python la libere entre meses.
            cmd = [sys.executable, str(Path(__file__).resolve()), "--convertir-uno", periodo]
            if args.liviano:
                cmd.append("--liviano")
            else:
                cmd += ["--memoria-limite", args.memoria_limite]
            subprocess.run(cmd, check=True)
            if parquet_path.exists() and parquet_path.stat().st_size > 0:
                procesados.append(parquet_path)

            if lst_creado and not args.keep_lst and lst_path.exists():
                lst_path.unlink()
                print(f"  Borrado LST temporal: {lst_path.name}")
            if zip_creado and not args.keep_zip and zip_path.exists():
                zip_path.unlink()
                print(f"  Borrado ZIP temporal: {zip_path.name}")

    if incremental:
        agregar_al_historico(procesados, salida)
        mergeados = procesados
    else:
        parquets = parquets_mensuales(DATA_DIR)
        se_actualizo = combinar_historico(parquets, salida, args.force)
        mergeados = parquets if se_actualizo else []

    if mergeados and not args.keep_mensuales:
        for p in mergeados:
            if p.exists():
                p.unlink()
        print(f"Borrados {len(mergeados)} impo_YYYYMM.parquet ya incorporados a {salida.name}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
