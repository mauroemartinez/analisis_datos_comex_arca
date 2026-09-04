# -*- coding: utf-8 -*-
"""
Tabla final mensual: 1 fila por item (DESTINACION+NUM_ITEM), todos los importadores.
Columnas: Importador, Despacho, Tipo de Destinacion, Fecha, Medio,
          Unidad de medida, Cantidad, FOB unitario USD, Pais de origen, Aduana
"""
import os, sys, re, glob, duckdb, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
_CANDIDATOS = glob.glob(os.path.join(HERE, "impo_*.parquet"))
_CANDIDATOS = [
    p for p in _CANDIDATOS
    if re.fullmatch(r"impo_\d{6}\.parquet", os.path.basename(p))
]
PARQUET = sorted(_CANDIDATOS, key=lambda p: os.path.basename(p))[-1] if _CANDIDATOS else None
if PARQUET is None:
    sys.exit("No encontre impo_YYYYMM.parquet. Descargalo desde ARCA y ubicalo en Data/.")
PERIODO = re.search(r"impo_(\d{6})\.parquet$", os.path.basename(PARQUET))
PERIODO = PERIODO.group(1) if PERIODO else "mensual"
PARQUET = PARQUET.replace("\\", "/")
ROOT = os.path.abspath(os.path.join(HERE, "..", "codigos"))
sys.path.insert(0, ROOT)
from codigos_arca import ADUANAS, UNIDADES, PAISES, MEDIOS_TRANSPORTE

con = duckdb.connect()

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
        GROUP BY ADU, DESTINACION, NUM_ITEM
    )
    SELECT
        i.NOMBRE_IMPORTADOR                                     AS "Importador",
        i.DESTINACION                                           AS "Despacho",
        substr(i.DESTINACION, 6, 4)                             AS "Tipo de Destinacion",
        strptime(i.FECHA || '01', '%Y%m%d')::DATE                AS "Fecha",
        coalesce(m.medio, i.MEDIO_TRANSPORTE)                   AS "Medio",
        coalesce(u.unidad, i.UNIDAD_MEDIDA)                     AS "Unidad de medida",
        i.CANT_UNIDAD_MEDIDA                                    AS "Cantidad",
        i.FOB_UNITARIO_USD                                      AS "FOB unitario USD",
        coalesce(p.pais, i.PAIS_ORIGEN)                         AS "Pais de origen",
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
