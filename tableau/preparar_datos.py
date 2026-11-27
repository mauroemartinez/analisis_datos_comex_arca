"""Resumen de las importaciones de ARCA para el tablero de Tableau Public.

Lee Data/impo_historico.parquet (cientos de millones de filas, una por concepto de arancel)
con DuckDB y deja, en esta carpeta:

- importaciones_argentina.csv y .hyper: una fila por mes, capítulo NCM, país de origen y vía de
  transporte, con el FOB en dólares y la cantidad de ítems. Entra holgado en el límite de
  Tableau Public (1 millón de filas) y no publica despachos ni importadores.
- datos_del_tablero.json: las cifras del proceso (filas leídas, ítems, período, lo que se
  excluyó), que el generador del tablero escribe en la página de método.

Decisiones que cambian los números:

- Una fila por ítem antes de sumar (ADU + DESTINACION + NUM_ITEM): el FOB se repite en cada
  concepto de arancel. El FOB del ítem está en FOB_UNITARIO_USD (el nombre engaña);
  FOB_TOTAL_USD es el total del despacho, repetido en cada ítem.
- Desde enero de 2019: 2018 viene con meses faltantes en el origen.
- Sin energía eléctrica (NCM 2716). Sus despachos no reflejan lo comerciado: unos pocos
  cientos de ítems suman decenas de miles de millones de dólares, con ítems repetidos por más
  de lo que la interconexión puede transportar en un mes. Quedan en una columna aparte, para
  mostrar en la página de método qué se sacó y cuánto pesaba.

Uso: python tableau/preparar_datos.py
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pycountry

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
FUENTE = RAIZ / "Data" / "impo_historico.parquet"
SALIDA = AQUI / "importaciones_argentina.csv"
EXTRACCION = SALIDA.with_suffix(".hyper")  # Tableau Public solo publica libros con extracción
CIFRAS = AQUI / "datos_del_tablero.json"
DESDE = "201901"
NCM_EXCLUIDO = "2716"  # energía eléctrica

sys.path.insert(0, str(RAIZ / "codigos"))
sys.path.insert(0, str(AQUI))
from codigos_arca import PAISES  # noqa: E402
from referencias import AREAS, CAPITULO, COLUMNAS, PAIS, VIA_SIN_DATO, VIAS, grupo_de_origen, rubro  # noqa: E402

DIMENSIONES = [n for n, t in COLUMNAS if t in ("date", "text")]
MEDIDAS = [n for n, t in COLUMNAS if t not in ("date", "text")]


def en_ingles(iso3: str) -> str:
    """Nombre del país en inglés: es lo que Tableau ubica en el mapa sin dudar."""
    if not iso3:
        return ""
    encontrado = pycountry.countries.get(alpha_3=iso3)
    return getattr(encontrado, "common_name", None) or encontrado.name if encontrado else ""


def pais(codigo: str) -> tuple[str, str, str]:
    """(nombre, ISO alfa-3, región) de un código de país de ARCA."""
    if codigo in PAIS:
        return PAIS[codigo]
    nombre = (PAISES.get(codigo) or "Sin dato").strip()
    if nombre.startswith(("ZF", "Z.F", "TIERRA DEL FUEGO")):
        return ("Tierra del Fuego y zonas francas", "", AREAS)
    return (nombre.title(), "", "Otros")


def extraccion(csv: Path, hyper: Path) -> None:
    """Pasa el CSV a una extracción de Tableau (.hyper), con la tabla Extract.Extract que espera el libro."""
    from tableauhyperapi import (Connection, CreateMode, HyperProcess, SchemaName, SqlType, TableDefinition, TableName,
                                 Telemetry, escape_string_literal)

    tipos = {"date": SqlType.date, "text": SqlType.text, "double": SqlType.double, "big_int": SqlType.big_int}
    tabla = TableDefinition(TableName("Extract", "Extract"), [TableDefinition.Column(n, tipos[t]()) for n, t in COLUMNAS])
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as proceso:
        with Connection(proceso.endpoint, hyper, CreateMode.CREATE_AND_REPLACE) as con:
            con.catalog.create_schema(SchemaName("Extract"))
            con.catalog.create_table(tabla)
            filas = con.execute_command(
                f"COPY {tabla.table_name} FROM {escape_string_literal(str(csv))} WITH (format csv, header, NULL '')")
    print(f"Extracción: {hyper.name} ({filas:,} filas)")


def main() -> int:
    if not FUENTE.exists():
        print(f"No está {FUENTE}: corré antes Data/descargar_historico_impo.py", file=sys.stderr)
        return 1
    inicio = time.time()
    con = duckdb.connect()
    con.sql("SET enable_progress_bar = false")
    origen = f"read_parquet('{FUENTE.as_posix()}')"
    filas_fuente = con.sql(f"SELECT count(*) FROM {origen} WHERE PERIODO >= '{DESDE}'").fetchone()[0]
    resumen = con.sql(f"""
        WITH items AS (
            SELECT ADU, DESTINACION, NUM_ITEM,
                   any_value(PERIODO)                         AS periodo,
                   any_value(substr(POS_NCM, 1, 2))           AS capitulo,
                   any_value(POS_NCM LIKE '{NCM_EXCLUIDO}%')  AS excluido,
                   any_value(trim(PAIS_ORIGEN))               AS pais,
                   any_value(trim(MEDIO_TRANSPORTE))          AS via,
                   any_value(FOB_UNITARIO_USD)                AS fob
            FROM {origen}
            WHERE PERIODO >= '{DESDE}'
            GROUP BY ADU, DESTINACION, NUM_ITEM
        )
        SELECT periodo, capitulo, excluido, pais, via, sum(fob) AS fob, count(*) AS items
        FROM items
        WHERE fob IS NOT NULL AND regexp_matches(periodo, '^[0-9]{{6}}$')
        GROUP BY ALL
    """).df()

    fecha = pd.to_datetime(resumen["periodo"] + "01", format="%Y%m%d")
    ultimo = fecha.max()
    u12_desde, p12_desde, p12_hasta = (ultimo - pd.DateOffset(months=m) for m in (11, 23, 12))
    paises = {c: pais(c) for c in resumen["pais"].unique()}
    numero = pd.to_numeric(resumen["capitulo"], errors="coerce")
    vias = resumen["via"].map(lambda v: VIAS.get(v, VIA_SIN_DATO))
    cuenta = ~resumen["excluido"].fillna(False).astype(bool)   # lo que entra en el tablero
    fob = resumen["fob"].where(cuenta)

    salida = pd.DataFrame({
        "Fecha": fecha.dt.date,
        "Rubro": numero.map(lambda c: rubro(int(c)) if pd.notna(c) else "Otros"),
        "Capítulo": numero.map(lambda c: CAPITULO.get(int(c), "Otros") if pd.notna(c) else "Sin dato"),
        "N.º de capítulo": resumen["capitulo"].fillna(""),
        "País de origen": resumen["pais"].map(lambda c: paises[c][0]),
        "País (mapa)": resumen["pais"].map(lambda c: en_ingles(paises[c][1])),
        "Región": resumen["pais"].map(lambda c: paises[c][2]),
        "Grupo de origen": resumen["pais"].map(lambda c: grupo_de_origen(*paises[c])),
        "Vía de transporte": vias.map(lambda v: v[0]),
        "Vía (grupo)": vias.map(lambda v: v[1]),
        "FOB USD": fob,
        "Ítems": resumen["items"].where(cuenta),
        "FOB últimos 12 meses": fob.where(fecha >= u12_desde),
        "FOB 12 meses anteriores": fob.where((fecha >= p12_desde) & (fecha <= p12_hasta)),
        "FOB 2019": fob.where(fecha.dt.year == 2019),
        "FOB energía eléctrica": resumen["fob"].where(~cuenta),
    })
    # Una fila por combinación de dimensiones; una medida queda vacía si todas sus partes lo están
    salida = salida.groupby(DIMENSIONES, as_index=False, dropna=False)[MEDIDAS].sum(min_count=1)
    for medida in MEDIDAS:
        salida[medida] = salida[medida].round(2)
    salida["Ítems"] = salida["Ítems"].astype("Int64")
    salida = salida[[n for n, _ in COLUMNAS]].sort_values(DIMENSIONES)
    salida.to_csv(SALIDA, index=False, encoding="utf-8")
    extraccion(SALIDA, EXTRACCION)

    anio = pd.to_datetime(salida["Fecha"]).dt.year
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
             "diciembre"]

    def mes(f) -> str:
        return f"{meses[f.month - 1]} de {f.year}"

    excluido = resumen[~cuenta]
    cifras = {
        "generado": date.today().isoformat(),
        "desde": mes(fecha.min()), "hasta": mes(ultimo),
        "ultimos_12_meses": {"desde": mes(u12_desde), "hasta": mes(ultimo)},
        "doce_meses_anteriores": {"desde": mes(p12_desde), "hasta": mes(p12_hasta)},
        "filas_de_la_fuente": int(filas_fuente),
        "items_de_despacho": int(resumen["items"].sum()),
        "filas_del_resumen": int(len(salida)),
        "fob_total_musd": round(float(salida["FOB USD"].sum()) / 1e6, 1),
        "fob_por_anio_musd": {int(a): round(float(v) / 1e6, 1) for a, v in salida.groupby(anio)["FOB USD"].sum().items()},
        "energia_electrica_excluida": {
            "ncm": NCM_EXCLUIDO, "items": int(excluido["items"].sum()), "fob_declarado_musd": round(float(excluido["fob"].sum()) / 1e6, 1),
            "por_anio_musd": {int(a): round(float(v) / 1e6, 1)
                              for a, v in salida.groupby(anio)["FOB energía eléctrica"].sum().items()},
        },
        "paises_en_el_mapa": int(salida.loc[salida["País (mapa)"] != "", "País (mapa)"].nunique()),
        "capitulos": int(salida["Capítulo"].nunique()),
    }
    CIFRAS.write_text(json.dumps(cifras, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sin_mapa = salida[(salida["País (mapa)"] == "") & (salida["Región"] != AREAS)]
    print(f"{len(salida):,} filas en {time.time() - inicio:.0f} s: {SALIDA.name}")
    print(f"FOB total: USD {salida['FOB USD'].sum() / 1e9:,.1f} mil millones; excluido (energía eléctrica): "
          f"USD {excluido['fob'].sum() / 1e9:,.1f} mil millones en {int(excluido['items'].sum()):,} ítems; "
          f"sin país para el mapa: {sin_mapa['FOB USD'].sum() / salida['FOB USD'].sum():.2%} del FOB")
    print(salida.groupby(anio)["FOB USD"].sum().div(1e9).round(1).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
