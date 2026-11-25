"""Arma el conjunto de ejemplo del explorador: guantes (NCM 4015), solo empresas,
desde enero de dos años antes del último período disponible (con datos de 2026,
arranca en enero de 2024).

Los importadores que son personas fisicas no se publican: se conserva una fila
solo si el nombre tiene una forma societaria o es una entidad (asociacion,
cooperativa, fundacion...). Lo que queda afuera son, sobre todo, nombres de
personas y algunas empresas sin forma societaria en el nombre.

uso: python demo.py <impo_historico.parquet> <salida.parquet>
"""
import sys

import duckdb

src, dst = sys.argv[1], sys.argv[2]
EMPRESA = (
    r"(^|\s)(S\.?\s?A\.?(\s?U\.?)?|S\.?\s?R\.?\s?L\.?|S\.?\s?A\.?\s?S\.?|S\.?\s?C\.?\s?A\.?)$"
    r"|(^|\s)(SACI|SAIC|SACIF|SAICF|SACIFIA|SAICA|SAICYF|SRL|SA|SAU|SAS)\b"
    r"|SOCIEDAD|COOPERATIVA|ASOCIACION|FUNDACION|MUTUAL|LTDA|\bINC\.?$|\bLLC\b|\bCORP|\bLIMITED\b|\bGMBH\b"
)
c = duckdb.connect()
ultimo = c.sql(f"SELECT max(PERIODO) FROM read_parquet('{src}')").fetchone()[0]
desde_periodo = f"{int(ultimo[:4]) - 2}01"
c.execute(
    f"""
    COPY (
        SELECT * FROM read_parquet('{src}')
        WHERE POS_NCM LIKE '4015%'
          AND PERIODO >= '{desde_periodo}'
          AND regexp_matches(upper(trim(NOMBRE_IMPORTADOR)), '{EMPRESA}')
        ORDER BY PERIODO, DESTINACION, NUM_ITEM, ARANCEL_CONCEPTO
    ) TO '{dst}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 20000)
    """
)
filas, imp, desde, hasta = c.sql(
    f"SELECT count(*), count(DISTINCT NOMBRE_IMPORTADOR), min(PERIODO), max(PERIODO) FROM '{dst}'"
).fetchone()
print(f"filas={filas} importadores={imp} periodo={desde}-{hasta}")
excluidos = c.sql(
    f"""SELECT DISTINCT trim(NOMBRE_IMPORTADOR) FROM read_parquet('{src}')
        WHERE POS_NCM LIKE '4015%'
          AND NOT regexp_matches(upper(trim(NOMBRE_IMPORTADOR)), '{EMPRESA}')
        LIMIT 15"""
).fetchall()
print("ejemplos excluidos:", [e[0] for e in excluidos])
