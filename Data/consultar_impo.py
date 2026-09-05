"""
Consultas rápidas sobre las importaciones.

Uso:
  python consultar_impo.py "ROCHE"                -> exporta impo_ROCHE.xlsx (filas del importador, todo el historico)
  python consultar_impo.py "ROCHE" --ncm 3004     -> filtra además por NCM que empiece con 3004
  python consultar_impo.py --sql "SELECT ..."     -> corre SQL libre e imprime el resultado
  python consultar_impo.py --resumen              -> resumen general (todo el historico, con desglose por período)

La tabla se llama impo. Sale de Data/impo_historico.parquet (todos los meses
consolidados) si existe, o si no del último impo_YYYYMM.parquet suelto que
encuentre (por ejemplo un mes recién descargado que todavía no se fusionó).
Columnas:
  PERIODO (solo si la fuente es el histórico) ADU DESTINACION NUM_ITEM FECHA
  NOMBRE_IMPORTADOR MEDIO_TRANSPORTE UNIDAD_MEDIDA CANT_UNIDAD_MEDIDA
  FOB_UNITARIO_USD FOB_TOTAL_USD DIVISA PAIS_ORIGEN PAIS_PROCEDENCIA POS_NCM
  ARANCEL_CONCEPTO ARANCEL_MONTO
Ojo: hay 1 fila por CONCEPTO de arancel; FOB_UNITARIO_USD es el FOB del ITEM (repetido en
cada línea de tributo); FOB_TOTAL_USD es el total de la DESTINACION (repetido en todo el item).
FECHA es un período YYYYMM en texto; para convertirlo a fecha real:
  strptime(FECHA || '01', '%Y%m%d')::DATE
"""
import sys, os, duckdb
from _fuente_impo import ubicar_fuente

HERE = os.path.dirname(os.path.abspath(__file__))

PARQUET, ES_HISTORICO = ubicar_fuente(HERE)
if PARQUET is None:
    sys.exit(
        "No encontré Data/impo_historico.parquet ni ningún impo_YYYYMM.parquet.\n"
        "Corré: python Data/descargar_historico_impo.py --actualizar"
    )

con = duckdb.connect()
con.execute(f"CREATE VIEW impo AS SELECT * FROM read_parquet('{PARQUET}')")

args = sys.argv[1:]

if not args or args[0] in ("-h", "--help"):
    print(__doc__); sys.exit(0)

if args[0] == "--resumen":
    if ES_HISTORICO:
        print(con.execute("""
          SELECT count(*) filas, count(DISTINCT PERIODO) meses,
                 min(PERIODO) desde, max(PERIODO) hasta,
                 count(DISTINCT NOMBRE_IMPORTADOR) importadores,
                 count(DISTINCT POS_NCM) ncm
          FROM impo""").fetchdf().to_string(index=False))
    else:
        print(con.execute("""
          SELECT count(*) filas, count(DISTINCT DESTINACION) destinaciones,
                 count(DISTINCT DESTINACION||'-'||NUM_ITEM) items,
                 count(DISTINCT NOMBRE_IMPORTADOR) importadores,
                 count(DISTINCT POS_NCM) ncm
          FROM impo""").fetchdf().to_string(index=False))
    print("\nTop 20 importadores por FOB de items (USD, todo el rango cargado):")
    print(con.execute("""
      WITH it AS (SELECT NOMBRE_IMPORTADOR, DESTINACION, NUM_ITEM,
                    any_value(FOB_UNITARIO_USD) fob FROM impo GROUP BY 1,2,3)
      SELECT NOMBRE_IMPORTADOR, round(sum(fob)) fob_usd, count(*) items
      FROM it GROUP BY 1 ORDER BY fob_usd DESC LIMIT 20""").fetchdf().to_string(index=False))
    sys.exit(0)

if args[0] == "--sql":
    print(con.execute(args[1]).fetchdf().to_string(index=False)); sys.exit(0)

# --- exportar por importador ---
name = args[0]
ncm = None
if "--ncm" in args:
    ncm = args[args.index("--ncm") + 1]

where = "upper(NOMBRE_IMPORTADOR) LIKE upper('%' || ? || '%')"
params = [name]
if ncm:
    where += " AND POS_NCM LIKE ? || '%'"
    params.append(ncm)

df = con.execute(f"SELECT * FROM impo WHERE {where} ORDER BY DESTINACION, NUM_ITEM, ARANCEL_CONCEPTO", params).fetchdf()
safe = "".join(c for c in name if c.isalnum() or c in " _-").strip().replace(" ", "_")
out = os.path.join(HERE, f"impo_{safe}{('_ncm'+ncm) if ncm else ''}.xlsx")
if len(df) > 1_048_575:
    print(f"{len(df):,} filas: no entra en una hoja de Excel. Guardo CSV en su lugar.")
    out = out.replace(".xlsx", ".csv"); df.to_csv(out, index=False)
else:
    df.to_excel(out, index=False)
print(f"{len(df):,} filas  ->  {out}")
if len(df):
    print("\nImportadores que matchearon:")
    print(con.execute(f"SELECT NOMBRE_IMPORTADOR, count(*) filas FROM impo WHERE {where} GROUP BY 1 ORDER BY 2 DESC", params).fetchdf().to_string(index=False))
