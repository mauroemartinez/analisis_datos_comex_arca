# -*- coding: utf-8 -*-
"""
Filtra las importaciones por las posiciones NCM de `posiciones_interes.txt`
y exporta para Google Sheets.

  python filtrar_posiciones.py                # usa posiciones_interes.txt
  python filtrar_posiciones.py otras.txt      # usa otro archivo de posiciones
  python filtrar_posiciones.py --xlsx         # fuerza xlsx (por defecto elige solo)

Genera, en la carpeta del script:
  impo_posiciones_detalle.(csv|xlsx)     -> 1 fila por ítem (deduplicado), con nombres
  impo_posiciones_resumen_ncm.csv        -> agregado por NCM 6 dígitos
El match es por prefijo de 6 dígitos: 392410 toma 3924.10.00, 3924.10.90, ...

Fuente: Data/impo_historico.parquet (todo el histórico) si existe, o si no el
último impo_YYYYMM.parquet suelto en Data/ o en la raíz del proyecto.
"""
import sys, os, duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "Data")
sys.path.insert(0, DATA_DIR)
from _fuente_impo import ubicar_fuente

PARQUET, ES_HISTORICO = ubicar_fuente(DATA_DIR)
if PARQUET is None:
    PARQUET, ES_HISTORICO = ubicar_fuente(HERE)
if PARQUET is None:
    sys.exit(
        "No encontré Data/impo_historico.parquet ni ningún impo_YYYYMM.parquet.\n"
        "Corré: python Data/descargar_historico_impo.py --actualizar"
    )
PERIODO = "todo el histórico" if ES_HISTORICO else "el período cargado"

args = [a for a in sys.argv[1:]]
force_xlsx = "--xlsx" in args
args = [a for a in args if not a.startswith("-")]
if args:
    pos_file = os.path.join(HERE, args[0])
else:
    pos_file = os.path.join(HERE, "posiciones_interes.txt")
    if not os.path.exists(pos_file):
        pos_file = os.path.join(HERE, "posiciones_interes.ejemplo.txt")
        print("Aviso: no encontré posiciones_interes.txt, uso posiciones_interes.ejemplo.txt")

# --- leer posiciones ---
codes = []
with open(pos_file, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"(\d{2,8})", line)
        if m:
            codes.append(m.group(1)[:6].ljust(6, "0") if len(m.group(1)) >= 6 else m.group(1))
codes = sorted(set(codes))
print(f"{len(codes)} posiciones leídas de {os.path.basename(pos_file)}")
if not codes:
    sys.exit("No hay posiciones válidas en el archivo.")

con = duckdb.connect()
con.execute("PRAGMA threads=4")
con.execute(f"CREATE VIEW impo AS SELECT * FROM read_parquet('{PARQUET}')")
con.execute("CREATE TABLE pos(cod6 VARCHAR)")
con.executemany("INSERT INTO pos VALUES (?)", [(c,) for c in codes])

# clave NCM sin puntos y a 6 dígitos
NCM6 = "substr(replace(POS_NCM, '.', ''), 1, 6)"

try:
    sys.path.insert(0, os.path.join(HERE, "codigos"))
    from codigos_arca import PAISES, ADUANAS, UNIDADES
    import pandas as pd
    con.register("t_pais",   pd.DataFrame(list(PAISES.items()),   columns=["cod", "pais"]))
    con.register("t_aduana", pd.DataFrame(list(ADUANAS.items()),  columns=["cod", "aduana"]))
    con.register("t_unidad", pd.DataFrame(list(UNIDADES.items()), columns=["cod", "unidad"]))
    HAVE_CODES = True
except Exception as e:
    print("  (sin codigos_arca.py, se exportan los códigos crudos)", e)
    HAVE_CODES = False

pais_o = "coalesce(po.pais, i.PAIS_ORIGEN)"       if HAVE_CODES else "i.PAIS_ORIGEN"
pais_p = "coalesce(pp.pais, i.PAIS_PROCEDENCIA)"  if HAVE_CODES else "i.PAIS_PROCEDENCIA"
aduana = "coalesce(ad.aduana, i.ADU)"             if HAVE_CODES else "i.ADU"
unidad = "coalesce(un.unidad, i.UNIDAD_MEDIDA)"   if HAVE_CODES else "i.UNIDAD_MEDIDA"
joins = ("""
  LEFT JOIN t_pais   po ON po.cod = i.PAIS_ORIGEN
  LEFT JOIN t_pais   pp ON pp.cod = i.PAIS_PROCEDENCIA
  LEFT JOIN t_aduana ad ON ad.cod = i.ADU
  LEFT JOIN t_unidad un ON un.cod = i.UNIDAD_MEDIDA
""" if HAVE_CODES else "")

# --- detalle: 1 fila por ítem ---
detalle = con.execute(f"""
WITH f AS (
  SELECT * FROM impo WHERE {NCM6} IN (SELECT cod6 FROM pos)
)
SELECT
  {NCM6.replace('POS_NCM','i.POS_NCM')}      AS NCM6,
  i.POS_NCM,
  i.ADU                                       AS ADUANA_COD,
  {aduana}                                    AS ADUANA,
  i.DESTINACION,
  i.NUM_ITEM,
  i.FECHA,
  i.NOMBRE_IMPORTADOR,
  {unidad}                                    AS UNIDAD,
  any_value(i.CANT_UNIDAD_MEDIDA)             AS CANT,
  any_value(i.FOB_UNITARIO_USD)              AS FOB_ITEM_USD,
  any_value(i.FOB_TOTAL_USD)                 AS FOB_DESTINACION_USD,
  any_value(i.DIVISA)                        AS DIVISA,
  i.PAIS_ORIGEN                               AS PAIS_ORIGEN_COD,
  {pais_o}                                    AS PAIS_ORIGEN,
  i.PAIS_PROCEDENCIA                          AS PAIS_PROCEDENCIA_COD,
  {pais_p}                                    AS PAIS_PROCEDENCIA,
  sum(i.ARANCEL_MONTO)                        AS ARANCEL_TOTAL_USD
FROM f i {joins}
GROUP BY 1,2,3,4,5,6,7,8,9,14,15,16,17
ORDER BY FOB_ITEM_USD DESC
""").df()

# --- resumen por NCM6 ---
resumen = con.execute(f"""
WITH it AS (
  SELECT {NCM6} AS NCM6, DESTINACION, NUM_ITEM,
         any_value(FOB_UNITARIO_USD) fob, any_value(NOMBRE_IMPORTADOR) imp
  FROM impo WHERE {NCM6} IN (SELECT cod6 FROM pos)
  GROUP BY 1,2,3
)
SELECT NCM6,
       count(*)                    AS items,
       count(DISTINCT imp)         AS importadores,
       round(sum(fob), 2)          AS fob_usd
FROM it GROUP BY 1 ORDER BY fob_usd DESC
""").df()

# posiciones sin movimiento (para que sepas cuáles no trajeron nada)
con_movi = set(resumen["NCM6"])
sin_movi = [c for c in codes if c not in con_movi]

print(f"\nDetalle : {len(detalle):,} ítems")
print(f"Resumen : {len(resumen)} posiciones con movimiento  ({len(sin_movi)} sin movimiento)")
print(f"FOB total del recorte: USD {detalle['FOB_ITEM_USD'].sum():,.0f}")

# --- exportar ---
use_xlsx = force_xlsx or len(detalle) <= 200_000
ext = "xlsx" if use_xlsx else "csv"
det_path = os.path.join(HERE, f"impo_posiciones_detalle.{ext}")
if use_xlsx:
    detalle.to_excel(det_path, index=False)
else:
    detalle.to_csv(det_path, index=False, encoding="utf-8-sig")
resumen.to_csv(os.path.join(HERE, "impo_posiciones_resumen_ncm.csv"), index=False, encoding="utf-8-sig")

print(f"\n-> {det_path}")
print(f"-> {os.path.join(HERE, 'impo_posiciones_resumen_ncm.csv')}")
if sin_movi:
    print(f"\nSin movimiento en {PERIODO}: {', '.join(sin_movi)}")
