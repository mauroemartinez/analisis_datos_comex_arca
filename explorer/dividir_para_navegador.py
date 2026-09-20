"""Parte impo_historico.parquet en un archivo por año para el explorador web.

Por qué hace falta: Chrome (y el resto de los navegadores basados en
Chromium) no puede volcar un archivo de más de ~2 GiB a un buffer en
memoria de una sola vez (falla con "Array buffer allocation failed"), así
que `explorer/index.html` no puede cargar `Data/impo_historico.parquet`
como archivo local una vez que supera ese tamaño (ya lo supera: ronda los
2.3 GiB). La solución es partirlo en archivos más chicos: el explorador ya
sabe leer varios Parquet juntos (`read_parquet([...])`), así que el usuario
simplemente selecciona los años que le interesan de una vez en el selector
de archivo.

Se parte por año calendario (no por tamaño fijo) porque es el corte que
tiene sentido para quien lo usa ("quiero ver 2023 y 2024"), y de paso cada
año pesa cómodo bajo el límite del navegador: medido sobre el histórico
real, 2018 pesa ~104 MiB y el año más pesado hasta ahora (2024) ~314 MiB.
Al ritmo de crecimiento actual, faltan décadas para que un solo año se
acerque a los ~2 GiB del límite; si eso llegara a pasar, este script avisa
en vez de escribir un archivo roto (ver `LIMITE_ADVERTENCIA_GIB` abajo).

Uso:
    python explorer\\dividir_para_navegador.py

Genera `explorer/data/impo_YYYY.parquet`, un archivo por año presente en el
histórico. Los archivos viejos se borran antes de escribir los nuevos, así
que es seguro correrlo de nuevo después de cada `--actualizar` del
histórico (conviene correrlo justo después, para que el explorador siempre
tenga los años al día).

Como cada año ya es un bloque contiguo del histórico (que está ordenado por
PERIODO), partir por año no resortea nada ni pierde la compresión que da
ese orden: es cortar el archivo ya ordenado en pedazos, no reorganizarlo.
"""

import argparse
import shutil
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA_DEFAULT = RAIZ / "Data" / "impo_historico.parquet"
SALIDA_DEFAULT = Path(__file__).resolve().parent / "data"
LIMITE_ADVERTENCIA_GIB = 1.5


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrada", type=Path, default=ENTRADA_DEFAULT)
    ap.add_argument("--salida-dir", type=Path, default=SALIDA_DEFAULT)
    args = ap.parse_args()

    if not args.entrada.exists():
        sys.exit(f"No existe {args.entrada}")

    con = duckdb.connect()
    anios = [
        r[0]
        for r in con.execute(
            f"SELECT DISTINCT substr(PERIODO, 1, 4) AS anio FROM read_parquet('{args.entrada.as_posix()}') ORDER BY anio"
        ).fetchall()
    ]
    print(f"Años encontrados: {', '.join(anios)}")

    if args.salida_dir.exists():
        shutil.rmtree(args.salida_dir)
    args.salida_dir.mkdir(parents=True)

    for anio in anios:
        destino = args.salida_dir / f"impo_{anio}.parquet"
        con.execute(
            f"COPY (SELECT * FROM read_parquet('{args.entrada.as_posix()}') WHERE substr(PERIODO, 1, 4) = '{anio}') "
            f"TO '{destino.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        tam_gib = destino.stat().st_size / 1024**3
        aviso = " <-- se acerca al límite del navegador, ver LIMITE_ADVERTENCIA_GIB" if tam_gib >= LIMITE_ADVERTENCIA_GIB else ""
        print(f"  {destino.name}: {tam_gib:.2f} GiB{aviso}")

    print(f"Listo. Un archivo por año en {args.salida_dir}")


if __name__ == "__main__":
    main()
