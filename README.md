# Analisis Datos Comex ARCA

Herramientas en Python para descargar, convertir, consultar y filtrar datos publicos de comercio exterior argentino publicados por ARCA.

Fuente oficial: Informacion Agregada de Comercio Exterior de ARCA.

https://arca.gob.ar/operadoresComercioExterior/informacionAgregada/informacion-agregada.asp

Este repositorio esta preparado para publicarse: no incluye bases mensuales, salidas generadas, notebooks con resultados, ni listas comerciales reales de posiciones NCM.

## Para que sirve

- Convertir archivos mensuales de importacion de ARCA desde `.lst` a Parquet.
- Unir varios meses en un unico `Data/impo_historico.parquet`.
- Consultar importaciones por importador, NCM, resumen general o SQL libre.
- Generar una tabla final mensual con una fila por item.
- Filtrar posiciones NCM desde una lista local editable.

## Estructura

```text
.
|-- Data/
|   |-- consultar_impo.py
|   |-- descargar_historico_impo.py
|   |-- tabla_final.py
|   `-- datos mensuales locales no versionados
|-- codigos/
|   `-- codigos_arca.py
|-- filtrar_posiciones.py
|-- posiciones_interes.ejemplo.txt
|-- requirements.txt
`-- README.md
```

Los datos y salidas estan ignorados por Git: `.csv`, `.xlsx`, `.parquet`, `.lst`, `.zip`, bases locales y exports generados.

## Instalacion

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Descargar y convertir importaciones

Para descargar meses desde ARCA, convertirlos a Parquet mensual y generar un historico unido:

```powershell
python Data\descargar_historico_impo.py --desde 202601 --hasta 202608
```

El script genera archivos mensuales con este patron:

```text
Data/impo_YYYYMM.parquet
```

Y tambien puede consolidarlos en:

```text
Data/impo_historico.parquet
```

Para unir solamente los Parquet que ya esten descargados:

```powershell
python Data\descargar_historico_impo.py --sin-descarga --force
```

## Consultas rapidas

Resumen general del ultimo mes disponible:

```powershell
python Data\consultar_impo.py --resumen
```

Buscar por importador:

```powershell
python Data\consultar_impo.py "IMPORTADOR"
```

Buscar por importador y prefijo NCM:

```powershell
python Data\consultar_impo.py "IMPORTADOR" --ncm 8504
```

Ejecutar SQL libre sobre la vista `impo`:

```powershell
python Data\consultar_impo.py --sql "SELECT POS_NCM, count(*) filas FROM impo GROUP BY 1 ORDER BY filas DESC LIMIT 20"
```

## Tabla final mensual

```powershell
python Data\tabla_final.py
```

Salidas locales:

```text
Data/impo_YYYYMM_tabla_final.parquet
Data/impo_YYYYMM_tabla_final.xlsx
```

## Filtrar posiciones NCM

El repositorio incluye una lista publica de ejemplo:

```text
posiciones_interes.ejemplo.txt
```

Para trabajar con una lista propia, crear una copia local:

```powershell
Copy-Item posiciones_interes.ejemplo.txt posiciones_interes.txt
```

Luego editar `posiciones_interes.txt` y ejecutar:

```powershell
python filtrar_posiciones.py
```

Forzar salida Excel:

```powershell
python filtrar_posiciones.py --xlsx
```

Tambien se puede pasar otro archivo de posiciones:

```powershell
python filtrar_posiciones.py mi_lista_ncm.txt
```

## Validacion rapida

```powershell
python -B -m py_compile filtrar_posiciones.py Data\consultar_impo.py Data\tabla_final.py Data\descargar_historico_impo.py codigos\codigos_arca.py
python Data\descargar_historico_impo.py --sin-descarga --force
```

## Nota sobre datos

Los datos de ARCA son publicos, pero los recortes comerciales, analisis internos, notebooks con outputs y archivos generados no deben versionarse. Este repo esta pensado para publicar el codigo y mantener los datos propios en local.
