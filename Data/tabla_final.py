# -*- coding: utf-8 -*-
"""
Tabla final mensual: 1 fila por ítem (DESTINACION+NUM_ITEM), todos los importadores.
Columnas: Importador, Despacho, Tipo de Destinación, Fecha, Medio,
          Unidad de medida, Cantidad, FOB unitario USD, País de origen, Aduana

Uso:
  python tabla_final.py                 -> ultimo periodo disponible
  python tabla_final.py --periodo 202508 -> un periodo puntual del historico
"""
import os, sys, duckdb, pandas as pd
from _fuente_impo import ubicar_fuente

HERE = os.path.dirname(os.path.abspath(__file__))
PARQUET, ES_HISTORICO = ubicar_fuente(HERE)
if PARQUET is None:
    sys.exit(
        "No encontré Data/impo_historico.parquet ni ningún impo_YYYYMM.parquet.\n"
        "Corré: python Data/descargar_historico_impo.py --actualizar"
    )

ROOT = os.path.abspath(os.path.join(HERE, "..", "codigos"))
sys.path.insert(0, ROOT)
from codigos_arca import ADUANAS, UNIDADES, PAISES, MEDIOS_TRANSPORTE

con = duckdb.connect()

periodo_arg = None
if "--periodo" in sys.argv:
    periodo_arg = sys.argv[sys.argv.index("--periodo") + 1]

if ES_HISTORICO:
    PERIODO = periodo_arg or con.execute(
        f"SELECT max(PERIODO) FROM read_parquet('{PARQUET}')"
    ).fetchone()[0]
    FILTRO_PERIODO = f"AND PERIODO = '{PERIODO}'"
else:
    if periodo_arg:
        sys.exit("--periodo solo aplica cuando la fuente es Data/impo_historico.parquet.")
    PERIODO = "mensual"
    FILTRO_PERIODO = ""

def _t(d, col):
    return pd.DataFrame(list(d.items()), columns=["cod", col])

con.register("t_aduana", _t(ADUANAS, "aduana"))
con.register("t_unidad", _t(UNIDADES, "unidad"))
con.register("t_pais", _t(PAISES, "pais"))
con.register("t_medio", _t(MEDIOS_TRANSPORTE, "medio"))

final = con.execute(f"""
    WITH items AS (
        SELECT
            ADU, DESTINACION,
            any_value(trim(NOMBRE_IMPORTADOR)) AS NOMBRE_IMPORTADOR,
            any_value(FECHA)             AS FECHA,
            any_value(MEDIO_TRANSPORTE)  AS MEDIO_TRANSPORTE,
            any_value(UNIDAD_MEDIDA)     AS UNIDAD_MEDIDA,
            any_value(CANT_UNIDAD_MEDIDA) AS CANT_UNIDAD_MEDIDA,
            any_value(FOB_UNITARIO_USD)  AS FOB_UNITARIO_USD,
            any_value(PAIS_ORIGEN)       AS PAIS_ORIGEN
        FROM read_parquet('{PARQUET}')
        WHERE regexp_matches(trim(FECHA), '^[0-9]{{6}}$')
        {FILTRO_PERIODO}
        GROUP BY ADU, DESTINACION, NUM_ITEM
    )
    SELECT
        i.NOMBRE_IMPORTADOR                                     AS "Importador",
        i.DESTINACION                                           AS "Despacho",
        substr(i.DESTINACION, 6, 4)                             AS "Tipo de Destinación",
        strptime(i.FECHA || '01', '%Y%m%d')::DATE                AS "Fecha",
        coalesce(m.medio, i.MEDIO_TRANSPORTE)                   AS "Medio",
        coalesce(u.unidad, i.UNIDAD_MEDIDA)                     AS "Unidad de medida",
        i.CANT_UNIDAD_MEDIDA                                    AS "Cantidad",
        i.FOB_UNITARIO_USD                                      AS "FOB unitario USD",
        coalesce(p.pais, i.PAIS_ORIGEN)                         AS "País de origen",
        coalesce(ad.aduana, i.ADU)                              AS "Aduana"
    FROM items i
    LEFT JOIN t_aduana ad ON ad.cod = i.ADU
    LEFT JOIN t_medio  m  ON m.cod  = trim(i.MEDIO_TRANSPORTE)
    LEFT JOIN t_unidad u  ON u.cod  = i.UNIDAD_MEDIDA
    LEFT JOIN t_pais   p  ON p.cod  = i.PAIS_ORIGEN
    ORDER BY "Despacho"
""").fetchdf()

print("filas:", len(final))
print(final.head(5).to_string(index=False))

out_parquet = os.path.join(HERE, f"impo_{PERIODO}_tabla_final.parquet")
out_xlsx = os.path.join(HERE, f"impo_{PERIODO}_tabla_final.xlsx")
final.to_parquet(out_parquet, compression="zstd", index=False)
final.to_excel(out_xlsx, index=False)
print("guardado:", out_parquet)
print("guardado:", out_xlsx)
