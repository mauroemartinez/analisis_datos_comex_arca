"""
Mismo resumen que 'consultar_impo.py --resumen', pero escrito con polars en vez
de duckdb+pandas. Pensado como referencia rapida mientras se aprende la lib,
comparando ambos archivos lado a lado.

Equivalencias usadas aca:
  con.execute("SELECT ... FROM impo")  ->  pl.scan_parquet(...)          (LazyFrame, no carga todo a RAM)
  GROUP BY x agg(...)                  ->  .group_by(x).agg(...)
  count(DISTINCT col)                  ->  pl.col(col).n_unique()
  any_value(col)                       ->  pl.col(col).first()           (idem valor repetido por grupo)
  ORDER BY ... LIMIT n                 ->  .sort(...).head(n)
  .fetchdf() / .df()                   ->  .collect()                    (ejecuta el plan lazy)

Uso:
  python Data/consultar_impo_polars.py

Fuente: Data/impo_historico.parquet (todos los meses) si existe, o si no el
último impo_YYYYMM.parquet suelto que encuentre en Data/.
"""
import os
import sys

import polars as pl

from _fuente_impo import ubicar_fuente

HERE = os.path.dirname(os.path.abspath(__file__))

PARQUET, ES_HISTORICO = ubicar_fuente(HERE)
if PARQUET is None:
    sys.exit(
        "No encontré Data/impo_historico.parquet ni ningún impo_YYYYMM.parquet.\n"
        "Corré: python Data/descargar_historico_impo.py --actualizar"
    )

impo = pl.scan_parquet(PARQUET)

resumen = impo.select(
    pl.len().alias("filas"),
    pl.col("DESTINACION").n_unique().alias("destinaciones"),
    pl.concat_str(["DESTINACION", pl.col("NUM_ITEM").cast(pl.Utf8)], separator="-").n_unique().alias("items"),
    pl.col("NOMBRE_IMPORTADOR").n_unique().alias("importadores"),
    pl.col("POS_NCM").n_unique().alias("ncm"),
).collect()
print(resumen)

print("\nTop 20 importadores por FOB de items (USD):")
top20 = (
    impo.group_by(["NOMBRE_IMPORTADOR", "DESTINACION", "NUM_ITEM"])
    .agg(pl.col("FOB_UNITARIO_USD").first().alias("fob"))
    .group_by("NOMBRE_IMPORTADOR")
    .agg(
        pl.col("fob").sum().round(0).alias("fob_usd"),
        pl.len().alias("items"),
    )
    .sort("fob_usd", descending=True)
    .head(20)
    .collect()
)
print(top20)
