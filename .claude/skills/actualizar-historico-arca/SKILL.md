---
name: actualizar-historico-arca
description: Descarga los periodos nuevos de importaciones publicados por ARCA y los agrega a Data/impo_historico.parquet. Usar cuando alguien pida actualizar, refrescar, sincronizar o traer los ultimos meses del historico de comercio exterior/importaciones de ARCA, o pregunte si el historico esta al dia.
---

# Actualizar el histórico de importaciones ARCA

Este repo mantiene un único archivo consolidado, `Data/impo_historico.parquet`,
con todas las importaciones mensuales de ARCA (una fila por declaración,
ítem y concepto de arancel). Esta skill automatiza traerlo al día. Antes de
tocar nada, leé `README.md` (sección "Descargar y convertir importaciones")
para el contexto completo: qué es cada archivo, por qué se usa DuckDB y
Parquet, y las limitaciones de la máquina donde esto corrió originalmente
(4 GB de RAM).

## Cuándo usar esto

- Piden "actualizar el histórico", "traer los últimos meses", "¿está al día
  el dataset de ARCA?", o algo equivalente.
- Antes de responder preguntas de análisis sobre datos recientes, si conviene
  confirmar que el histórico llega hasta el mes esperado.

## Pasos

1. **Verificar el entorno.** Confirmar que existe `.venv` en la raíz del repo
   con las dependencias de `requirements.txt` instaladas (`duckdb`, `pyarrow`,
   etc). Si no existe, crearlo:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Correr la actualización incremental.** Este es el comando central; NO
   uses `--force` acá (eso resortea todo el histórico desde cero, es carísimo
   y no hace falta para una actualización normal):
   ```powershell
   python Data\descargar_historico_impo.py --actualizar
   ```
   Qué hace: mira el último `PERIODO` que ya está en `impo_historico.parquet`,
   descubre en la página oficial de ARCA qué meses nuevos hay publicados,
   descarga y convierte solo esos, y los agrega al histórico sin resortear
   las filas ya existentes (ver README, sección "Por qué DuckDB y por qué
   Parquet", para el porqué de esto). Si `impo_historico.parquet` todavía no
   existe, hace la carga completa (puede tardar horas la primera vez).

3. **Leer la salida y confirmar.** El comando imprime, por cada período
   nuevo, si lo descargó/convirtió o si lo salteó (por ejemplo, meses que
   ARCA solo publica en formato "agregado", sin detalle por importador: eso
   es esperado, no un error). Al final imprime algo como:
   ```
   Histórico actualizado: 620,xxx,xxx filas, 89 meses, 201801 a 202601
   ```
   Confirmá que el "hasta" sea el mes que se esperaba. Si el comando termina
   con "no hay periodos nuevos publicados todavia", el histórico ya estaba al
   día: no es un error.

4. **No restaurar los `impo_YYYYMM.parquet` mensuales a mano.** Por diseño se
   borran solos apenas quedan incorporados al histórico (para no duplicar
   espacio en disco). Si hace falta inspeccionar un mes puntual por separado,
   usar `--mes YYYYMM --keep-mensuales` para traerlo de nuevo sin tocar el
   histórico.

5. **Si algo falla a mitad de camino:**
   - Puede quedar un `impo_historico.parquet.tmp` de 0 bytes y algunos
     `duckdb_temp_storage_*.tmp` en `Data/`: son basura segura de borrar (solo
     si no hay ningún proceso de Python corriendo sobre esta carpeta).
   - Volver a correr `python Data\descargar_historico_impo.py --actualizar`
     retoma solo lo que falte; no hace falta empezar de cero.
   - Si el error es de memoria durante la conversión de un mes puntual
     (`--convertir-uno` interno), reintentar con `--memoria-limite 300MB` o
     `--liviano` (más lento, memoria casi constante, ver `--help`).

6. **Si se agregó una fuente de exploración online** (ver
   `docs/EXPLORACION_ONLINE.md`): después de actualizar el histórico, subir el
   `impo_historico.parquet` nuevo al object storage configurado ahí, para que
   `explorer/index.html` sirva los datos al día. Ese paso no está automatizado
   todavía (depende de qué proveedor se haya elegido); si no hay nada
   configurado, omitir este paso.

## Qué NO hacer

- No correr `--force` como parte de una actualización rutinaria: resortea
  cientos de millones de filas existentes y puede usar decenas de GB de disco
  temporal (ver README, "Corrido en una máquina con 4 GB de RAM"). Reservado
  para reparar un histórico corrupto o incompleto.
- No editar `Data/impo_historico.parquet` a mano ni con herramientas que no
  preserven el orden `PERIODO, DESTINACION, NUM_ITEM, ARANCEL_CONCEPTO`
  (rompe la poda de row groups por fecha que depende de ese orden).
- No commitear nada de `Data/` a git: todo lo que termina en `.parquet`,
  `.lst`, `.zip` está ignorado a propósito (ver `.gitignore`).
