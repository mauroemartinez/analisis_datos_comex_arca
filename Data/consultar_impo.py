"""
Consultas rapidas sobre el Parquet mensual de importaciones.

Uso:
  python consultar_impo.py "ROCHE"                -> exporta impo_ROCHE.xlsx (filas del importador)
  python consultar_impo.py "ROCHE" --ncm 3004     -> filtra ademas por NCM que empiece con 3004
  python consultar_impo.py --sql "SELECT ..."     -> corre SQL libre e imprime el resultado
  python consultar_impo.py --resumen              -> resumen general del mes

La tabla se llama impo y sale del ultimo archivo impo_YYYYMM.parquet disponible.
Columnas:
  ADU DESTINACION NUM_ITEM FECHA NOMBRE_IMPORTADOR MEDIO_TRANSPORTE UNIDAD_MEDIDA
  CANT_UNIDAD_MEDIDA FOB_UNITARIO_USD FOB_TOTAL_USD DIVISA PAIS_ORIGEN PAIS_PROCEDENCIA
  POS_NCM ARANCEL_CONCEPTO ARANCEL_MONTO
Ojo: hay 1 fila por CONCEPTO de arancel; FOB_UNITARIO_USD es el FOB del ITEM (repetido en
cada linea de tributo); FOB_TOTAL_USD es el total de la DESTINACION (repetido en todo el item).
"""
import sys, os, re, glob, duckdb

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
PERIODO = PERIODO.group(1) if PERIODO else "periodo"

con = duckdb.connect()
con.execute(f"CREATE VIEW impo AS SELECT * FROM read_parquet('{PARQUET.replace(chr(92), '/')}')")

args = sys.argv[1:]

if not args or args[0] in ("-h", "--help"):
    print(__doc__); sys.exit(0)

if args[0] == "--resumen":
    print(con.execute("""
      SELECT count(*) filas, count(DISTINCT DESTINACION) destinaciones,
             count(DISTINCT DESTINACION||'-'||NUM_ITEM) items,
             count(DISTINCT NOMBRE_IMPORTADOR) importadores,
             count(DISTINCT POS_NCM) ncm
      FROM impo""").fetchdf().to_string(index=False))
    print("\nTop 20 importadores por FOB de items (USD):")
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
