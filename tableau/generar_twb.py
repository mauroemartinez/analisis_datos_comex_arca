"""Genera el libro de Tableau (tableau/importaciones_argentina.twb) desde código.

Un .twb es un XML: la conexión a los datos, los campos calculados, cada hoja (qué va en filas,
columnas y marcas, con su formato) y los dashboards que las acomodan. Escribirlo desde acá hace
el tablero reproducible: si cambian los datos o el diseño, se vuelve a generar en un segundo.

Cómo está armado:
- Cinco dashboards de 1280 x 720 (como páginas de Power BI), con botones para pasar de uno a otro.
- En cada uno, una imagen de fondo con el vidrio y los títulos de la marca (fondos.py) y, encima,
  las hojas de Tableau con fondo transparente. Las posiciones salen de diseno.py.
- Las hojas quedan ocultas: quien abre el libro ve solo las cinco páginas.

Antes: python tableau/preparar_datos.py   (datos)   y   python tableau/fondos.py   (fondos)
Uso:   python tableau/generar_twb.py, y abrir el .twb con Tableau Public Desktop.

Variables para revisar: TABLEAU_HOJA=<nombre> abre directo esa hoja o esa página.
"""

import os
import re
import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import escape
from xml.sax.saxutils import quoteattr as a

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import diseno as d  # noqa: E402
from referencias import COLUMNAS, GRUPOS_DE_ORIGEN  # noqa: E402

CSV = AQUI / "importaciones_argentina.csv"
HYPER = AQUI / "importaciones_argentina.hyper"
SALIDA = AQUI / "importaciones_argentina.twb"
DS = "federated.importaciones"
NL = chr(10)
# Las tipografías de la marca van en el fondo; para lo que escribe Tableau, las suyas (se ven igual en cualquier equipo)
F_TEXTO, F_MEDIA, F_FUERTE = "Tableau Book", "Tableau Medium", "Tableau Semibold"

TIPOS = {"date": ("date", "dimension", "ordinal"), "text": ("string", "dimension", "nominal"),
         "double": ("real", "measure", "quantitative"), "big_int": ("integer", "measure", "quantitative")}
U, P = "[FOB últimos 12 meses]", "[FOB 12 meses anteriores]"

# Campos calculados: nombre interno → (título, fórmula, tipo de dato, rol, clase, formato, es cálculo de tabla)
CALCULOS = {
    "c_fob_mm": ("FOB (miles de millones USD)", "[FOB USD] / 1000000000", "real", "measure", "quantitative", "n#,##0.0", False),
    "c_fob_m": ("FOB (millones USD)", "[FOB USD] / 1000000", "real", "measure", "quantitative", "n#,##0", False),
    "c_u12_mm": ("FOB de los últimos 12 meses (miles de millones USD)", f"{U} / 1000000000", "real", "measure", "quantitative",
                 "n#,##0.0", False),
    "c_mm12": ("Media móvil de 12 meses", "WINDOW_AVG(SUM([FOB USD]) / 1000000000, -11, 0)", "real", "measure", "quantitative",
               "n#,##0.0", True),
    "c_kpi_u12": ("Importado en los últimos 12 meses", f"SUM({U}) / 1000000000", "real", "measure", "quantitative",
                  'n"US$ "#,##0.0" mil M"', False),
    "c_var": ("Variación contra los 12 meses anteriores", f"SUM({U}) / SUM({P}) - 1", "real", "measure", "quantitative",
              'p"▲ "0.0%;"▼ "0.0%', False),
    "c_peso": ("Peso en los últimos 12 meses", f"SUM({U}) / MIN({{FIXED : SUM({U})}})", "real", "measure", "quantitative",
               "p0.0%", False),
    "c_peso_sel": ("Peso en el total o en el origen elegido",
                   f"IF COUNTD([País de origen]) = 1 THEN SUM({U}) / MIN({{FIXED [País de origen] : SUM({U})}}) "
                   f"ELSE SUM({U}) / MIN({{FIXED : SUM({U})}}) END", "real", "measure", "quantitative", "p0.0%", False),
    "c_peso_2019": ("Peso en 2019", "SUM([FOB 2019]) / MIN({FIXED : SUM([FOB 2019])})", "real", "measure", "quantitative",
                    "p0.0%", False),
    "c_cambio": ("Cambio de peso (puntos porcentuales)", "([c_peso] - [c_peso_2019]) * 100", "real", "measure", "quantitative",
                 "n+0.0;-0.0", False),
    "c_signo_peso": ("Ganó o perdió peso", "IF [c_cambio] >= 0 THEN 'Ganó peso' ELSE 'Perdió peso' END", "string", "measure",
                     "nominal", None, False),
    "c_signo": ("Subió o bajó", "IF [c_var] >= 0 THEN 'Subió' ELSE 'Bajó' END", "string", "measure", "nominal", None, False),
    "c_peso_anio": ("Peso en el año", "SUM([FOB USD]) / MIN({FIXED DATETRUNC('year', [Fecha]) : SUM([FOB USD])})", "real",
                    "measure", "quantitative", "p0%", False),
    "c_peso_anio_final": ("Peso en el último año", "IF MIN(YEAR([Fecha])) = MIN({FIXED : MAX(YEAR([Fecha]))}) THEN [c_peso_anio] END",
                          "real", "measure", "quantitative", "p0%", False),
    "c_peso_rubro": ("Peso dentro del rubro", f"SUM({U}) / MIN({{FIXED [Rubro] : SUM({U})}})", "real", "measure", "quantitative",
                     "p0%", False),
    "c_peso_region": ("Peso dentro de la región", f"SUM({U}) / MIN({{FIXED [Región] : SUM({U})}})", "real", "measure",
                      "quantitative", "p0%", False),
    "c_por_item": ("FOB medio por ítem (USD)", f"SUM({U}) / SUM(IF NOT ISNULL({U}) THEN [Ítems] END)", "real", "measure",
                   "quantitative", 'n"US$ "#,##0', False),
    "c_ubicable": ("Es un país", "NOT ISNULL([País (mapa)])", "boolean", "dimension", "nominal", None, False),
    "c_combustibles": ("Combustibles (miles de millones USD)", "(IF [Rubro] = 'Combustibles' THEN [FOB USD] END) / 1000000000",
                       "real", "measure", "quantitative", "n#,##0.0", False),
    "c_electrica": ("Energía eléctrica declarada (miles de millones USD)", "[FOB energía eléctrica] / 1000000000", "real",
                    "measure", "quantitative", "n#,##0.0", False),
    "c_electrica_arriba": ("Energía eléctrica declarada, donde supera a los combustibles",
                           "IF SUM([c_electrica]) > SUM([c_combustibles]) THEN SUM([c_electrica]) END", "real", "measure",
                           "quantitative", "n#,##0.0", False),
    "c_mes_texto": ("Mes", "DATENAME('month', [Fecha]) + ' de ' + STR(YEAR([Fecha]))", "string", "dimension", "nominal", None, False),
    "c_items_miles": ("Ítems de despacho (miles)", "[Ítems] / 1000", "real", "measure", "quantitative", "n#,##0", False),
    "c_origen_elegido": ("Origen elegido", "IF COUNTD([País de origen]) = 1 THEN MIN([País de origen]) ELSE 'Todos los orígenes' END",
                         "string", "measure", "nominal", None, False),
    "c_rubro_elegido": ("Rubro elegido", "IF COUNTD([Rubro]) = 1 THEN MIN([Rubro]) ELSE 'Todos los rubros' END", "string",
                        "measure", "nominal", None, False),
}
NOMBRES_DE_COLUMNA = {n for n, _ in COLUMNAS}

# Colores fijos por categoría. Van en la fuente de datos, y cada campo necesita su instancia declarada ahí
PALETAS = {
    ("Grupo de origen", "None", "nominal"): d.COLOR_GRUPO,
    ("Vía (grupo)", "None", "nominal"): d.COLOR_VIA,
    ("c_signo_peso", "User", "nominal"): {"Ganó peso": d.CIAN, "Perdió peso": d.MAGENTA},
    ("c_signo", "User", "nominal"): {"Subió": d.CIAN, "Bajó": d.MAGENTA},
}


# ── Piezas ─────────────────────────────────────────────────────────────────────
def guid(nombre: str) -> str:
    """Identificador estable: el mismo nombre da siempre el mismo, así el archivo no cambia de más entre corridas."""
    return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, "globalaize/importaciones-argentina/" + nombre)).upper() + "}"


def ref(instancia: str) -> str:
    return f"[{DS}].[{instancia}]"


_PRE = {"None": "none", "Sum": "sum", "User": "usr", "Attribute": "attr", "Month-Trunc": "tmn", "Year": "yr", "Month": "mn"}
_SUF = {"nominal": "nk", "ordinal": "ok", "quantitative": "qk"}


def inst(campo: str, deriv: str = "None", clase: str = "nominal") -> tuple[str, str, str, str]:
    """Una instancia de campo: (campo, derivación, nombre de la instancia, clase)."""
    return (campo, deriv, f"{_PRE[deriv]}:{campo}:{_SUF[clase]}", clase)


def dim(campo):
    return inst(campo)


def suma(campo):
    return inst(campo, "Sum", "quantitative")


def calc(campo):
    return inst(campo, "User", "quantitative")


def calc_texto(campo):
    return inst(campo, "User", "nominal")


def attr(campo):
    return inst(campo, "Attribute", "nominal")


# En los ejes va la fecha exacta (los datos ya son mensuales): así el eje no muestra los botones +/- de la jerarquía de fechas
FECHA = inst("Fecha", "None", "quantitative")
# "marzo de 2020" para las descripciones emergentes. Una dimensión ahí tiene que ir como atributo: si no, la hoja queda en blanco
MES_TEXTO = inst("c_mes_texto", "Attribute", "nominal")
ANIO = inst("Fecha", "Year", "ordinal")
MES_DEL_ANIO = inst("Fecha", "Month", "ordinal")


def def_columna(nombre: str, sangria: str) -> str:
    if nombre in CALCULOS:
        titulo, formula, tipo, rol, clase, formato, de_tabla = CALCULOS[nombre]
        fmt = f" default-format={a(formato)}" if formato else ""
        tabla = "<table-calc ordering-type='Rows' />" if de_tabla else ""
        return (f"{sangria}<column caption={a(titulo)} datatype={a(tipo)}{fmt} name={a(f'[{nombre}]')} role={a(rol)} "
                f"type={a(clase)}><calculation class='tableau' formula={a(formula)}>{tabla}</calculation></column>")
    tipo, rol, clase = TIPOS[dict(COLUMNAS)[nombre]]
    geo = " semantic-role='[Country].[ISO3166_2]'" if nombre == "País (mapa)" else ""   # el rol País/Región
    return f"{sangria}<column datatype={a(tipo)} name={a(f'[{nombre}]')} role={a(rol)} type={a(clase)}{geo} />"


def def_instancia(i, sangria: str) -> str:
    campo, deriv, nombre, clase = i
    hijo = "<table-calc ordering-type='Rows' />" if campo in CALCULOS and CALCULOS[campo][6] else ""
    cierre = f">{hijo}</column-instance>" if hijo else " />"
    return (f"{sangria}<column-instance column={a(f'[{campo}]')} derivation={a(deriv)} name={a(f'[{nombre}]')} pivot='key' "
            f"type={a(clase)}{cierre}")


def dependencias(campos) -> list[str]:
    """Los campos pedidos y, si son cálculos, todo lo que usan sus fórmulas."""
    vistos: list[str] = []

    def visitar(c):
        if c in vistos or (c not in CALCULOS and c not in NOMBRES_DE_COLUMNA):
            return
        if c in CALCULOS:
            for usado in re.findall(r"\[([^\]]+)\]", CALCULOS[c][1]):
                visitar(usado)
        vistos.append(c)

    for c in campos:
        visitar(c)
    return vistos


def run(texto: str, color: str = d.SECUNDARIO, pt: float = 9, fuente: str = F_TEXTO, negrita: bool = False) -> str:
    extra = " bold='true'" if negrita else ""
    return f"<run{extra} fontcolor='{color.lower()}' fontname={a(fuente)} fontsize='{pt}'>{texto}</run>"


def valor(i) -> str:
    """El valor de un campo dentro de una etiqueta o una descripción emergente."""
    return escape(f"<{ref(i[2])}>")


SALTO = "<run>Æ&#10;</run>"


def etiqueta(*runs: str) -> str:
    return "<customized-label><formatted-text>" + "".join(runs) + "</formatted-text></customized-label>"


def emergente(*runs: str) -> str:
    """Descripción emergente. Tableau la dibuja siempre sobre blanco: los textos van con los tonos oscuros de la marca."""
    texto = "".join(runs).replace(f"fontcolor='{d.TINTA.lower()}'", "fontcolor='#051e45'")
    texto = texto.replace(f"fontcolor='{d.SECUNDARIO.lower()}'", "fontcolor='#3e4e66'")
    return "<customized-tooltip><formatted-text>" + texto + "</formatted-text></customized-tooltip>"


def pane(marca: str, codifica=(), *, etiqueta_xml: str = "", emergente_xml: str = "", estilo_marca: str = "", atributos: str = "",
         lineas_xml: str = "") -> str:
    """Un panel de marcas. codifica: pares (tipo, instancia) con tipo en color, size, text, lod, tooltip, geometry."""
    enc = "".join(f"<{tipo} column={a(i if isinstance(i, str) else ref(i[2]))} />" for tipo, i in codifica)
    return (f"          <pane{atributos} selection-relaxation-option='selection-relaxation-allow'><view><breakdown value='auto' /></view>"
            f"<mark class={a(marca)} />" + (f"<encodings>{enc}</encodings>" if enc else "") + lineas_xml + emergente_xml + etiqueta_xml +
            f"<style><style-rule element='mark'>{estilo_marca}</style-rule></style></pane>")


COLOR = "<format attr='mark-color' value='{}' />".format
ETIQUETAS = "<format attr='mark-labels-show' value='true' /><format attr='mark-labels-cull' value='false' />"


def escala(i, colores=d.ESCALA_CON_TEXTO) -> str:
    """Escala continua de un solo tono, de la marca."""
    return (f"<style-rule element='mark'><encoding attr='color' field={a(ref(i[2]))} type='custom-interpolated'>"
            f"<color-palette custom='true' name='' type='ordered-sequential'>" + "".join(f"<color>{c}</color>" for c in colores) +
            "</color-palette></encoding></style-rule>")


def sin_eje(i, donde: str) -> str:
    return f"<style-rule element='axis'><format attr='display' field={a(ref(i[2]))} scope={a(donde)} value='false' /></style-rule>"


def sin_titulo_de_eje(i, donde: str) -> str:
    return f"<style-rule element='axis'><format attr='title' class='0' field={a(ref(i[2]))} scope={a(donde)} value='' /></style-rule>"


def desde_piso(i, donde: str, piso: float) -> str:
    """El eje arranca en un piso fijo en vez de en cero (el techo sigue a los datos): para líneas, no para barras."""
    return (f"<style-rule element='axis'><encoding attr='space' class='0' field={a(ref(i[2]))} field-type='quantitative' "
            f"min='{piso}' range-type='fixedmin' scope={a(donde)} type='space' /></style-rule>")


def lineas_de_hitos(eje) -> tuple[str, str]:
    """Una línea vertical por hito, con su nombre: (líneas para el panel de marcas, formato para la hoja)."""
    lineas, formato = [], []
    for n, (fecha, nombre, _) in enumerate(d.HITOS):
        lineas.append(
            f"<reference-line axis-column={a(ref(eje[2]))} enable-instant-analytics='true' formula='constant' id='refline{n}' "
            f"label={a(nombre)} label-type='custom' scope='per-table' value='#{fecha} 00:00:00#' value-column={a(ref(eje[2]))} "
            f"z-order='{n + 1}' />")
        formato.append(
            f"<format attr='stroke-color' id='refline{n}' value='{d.REFERENCIA}' /><format attr='stroke-size' id='refline{n}' value='1' />"
            f"<format attr='line-pattern-only' id='refline{n}' value='dashed' />"
            f"<format attr='text-align' id='refline{n}' value='right' /><format attr='vertical-align' id='refline{n}' value='top' />"
            f"<format attr='font-size' id='refline{n}' value='8' /><format attr='color' id='refline{n}' value='{d.SECUNDARIO}' />"
            f"<format attr='background-color' id='refline{n}' value='#00000000' />")
    return "".join(lineas), "<style-rule element='refline'>" + "".join(formato) + "</style-rule>"


def orden(i, por, sentido: str = "DESC") -> str:
    return f"          <sort class='computed' column={a(ref(i[2]))} direction={a(sentido)} using={a(ref(por[2]))} />"


def orden_fijo(i, valores) -> str:
    cubos = "".join(f"<bucket>&quot;{escape(v)}&quot;</bucket>" for v in valores)
    return f"          <sort class='manual' column={a(ref(i[2]))} direction='ASC'><dictionary>{cubos}</dictionary></sort>"


def primeros(i, n: int, expresion: str) -> str:
    return (f"          <filter class='categorical' column={a(ref(i[2]))}><groupfilter count='{n}' end='top' function='end' "
            f"units='records' user:ui-marker='end' user:ui-top-by-field='true'><groupfilter direction='DESC' "
            f"expression={a(expresion)} function='order' user:ui-marker='order'><groupfilter function='level-members' "
            f"level={a(f'[{i[2]}]')} user:ui-enumeration='all' user:ui-marker='enumerate' /></groupfilter></groupfilter></filter>")


def solo(i, miembro: str) -> str:
    return (f"          <filter class='categorical' column={a(ref(i[2]))}><groupfilter function='member' level={a(f'[{i[2]}]')} "
            f"member={a(miembro)} user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' /></filter>")


def sin(i, *miembros: str) -> str:
    fuera = "".join(f"<groupfilter function='member' level={a(f'[{i[2]}]')} member={a(chr(34) + m + chr(34))} />" for m in miembros)
    if len(miembros) > 1:   # 'except' resta un solo conjunto: varios valores van juntos en una unión
        fuera = f"<groupfilter function='union'>{fuera}</groupfilter>"
    return (f"          <filter class='categorical' column={a(ref(i[2]))}><groupfilter function='except' user:ui-domain='database' "
            f"user:ui-enumeration='exclusive' user:ui-marker='enumerate'><groupfilter function='level-members' "
            f"level={a(f'[{i[2]}]')} />{fuera}</groupfilter></filter>")


def desde(i, minimo: float) -> str:
    return f"          <filter class='quantitative' column={a(ref(i[2]))} included-values='in-range'><min>{minimo}</min></filter>"


ESTILO_BASE = f"""
          <style-rule element='table'><format attr='background-color' value='#051e4501' /></style-rule>
          <style-rule element='worksheet'>
            <format attr='display-field-labels' scope='rows' value='false' />
            <format attr='display-field-labels' scope='cols' value='false' />
            <format attr='font-family' value='{F_TEXTO}' />
            <format attr='color' value='{d.SECUNDARIO}' />
          </style-rule>
          <style-rule element='axis'>
            <format attr='font-size' value='8' /><format attr='color' value='{d.TENUE}' />
            <format attr='stroke-color' value='{d.GRILLA}' /><format attr='tick-color' value='{d.GRILLA}' />
          </style-rule>
          <style-rule element='label'><format attr='font-size' value='9' /><format attr='color' value='{d.TINTA}' /></style-rule>
          <style-rule element='gridline'>
            <format attr='line-visibility' scope='rows' value='on' />
            <format attr='stroke-color' scope='rows' value='{d.GRILLA}' />
            <format attr='line-visibility' scope='cols' value='off' />
          </style-rule>
          <style-rule element='zeroline'><format attr='line-visibility' value='off' /></style-rule>
          <style-rule element='table-div'><format attr='line-visibility' value='off' /></style-rule>"""


def hoja(nombre: str, instancias, *, filas: str = "", cols: str = "", panes, vista: str = "", estilo: str = "", mapa: bool = False) -> str:
    campos = dependencias([i[0] for i in instancias])
    deps = [def_columna(c, "            ") for c in campos] + [def_instancia(i, "            ") for i in instancias]
    fuente_de_mapas = "          <mapsources><mapsource name='Tableau' /></mapsources>" if mapa else ""
    return f"""    <worksheet name={a(nombre)}>
      <table>
        <view>
          <datasources><datasource caption='Importaciones ARCA' name='{DS}' /></datasources>
{fuente_de_mapas}
          <datasource-dependencies datasource='{DS}'>
{NL.join(deps)}
          </datasource-dependencies>
{vista}
          <aggregation value='true' />
        </view>
        <style>{ESTILO_BASE}
          {estilo}
        </style>
        <panes>
{NL.join(panes if isinstance(panes, list) else [panes])}
        </panes>
        <rows>{filas}</rows>
        <cols>{cols}</cols>
      </table>
      <simple-id uuid='{guid("hoja/" + nombre)}' />
    </worksheet>"""


# ── Hojas ──────────────────────────────────────────────────────────────────────
CELDA_DE_TARJETA = ("<style-rule element='cell'><format attr='width' value='272' /><format attr='height' value='48' />"
                    "<format attr='text-align' value='left' /></style-rule>")


def cifra(nombre: str, i) -> str:
    """Una tarjeta: el número grande. El rótulo y la nota van en el fondo."""
    return hoja(nombre, [i], estilo=CELDA_DE_TARJETA,
                panes=pane("Text", [("text", i)], etiqueta_xml=etiqueta(run(valor(i), d.TINTA, 20, F_MEDIA)), estilo_marca=ETIQUETAS))


def primero(nombre: str, campo: str, peso_de: str = "c_peso") -> str:
    """Una tarjeta con el primero del ranking y su peso."""
    k, peso, base = dim(campo), calc(peso_de), suma("FOB últimos 12 meses")
    return hoja(nombre, [k, peso, base], vista=primeros(k, 1, f"SUM({U})"), estilo=CELDA_DE_TARJETA,
                panes=pane("Text", [("text", k), ("text", peso)], estilo_marca=ETIQUETAS,
                           etiqueta_xml=etiqueta(run(valor(k), d.TINTA, 15, F_MEDIA), SALTO, run(valor(peso), d.SECUNDARIO, 11))))


def ancho_de_nombres(i, px_: int) -> str:
    return f"<style-rule element='header'><format attr='width' field={a(ref(i[2]))} value='{px_}' /></style-rule>"


def ranking(nombre: str, campo: str, *, n: int | None = None, color=None, color_por=None, nombres: int = 150,
            peso_de: str = "c_peso", de: str = " del total") -> str:
    """Barras horizontales por FOB de los últimos 12 meses, con el valor y el peso al lado."""
    k, fob, peso = dim(campo), suma("c_u12_mm"), calc(peso_de)
    instancias = [k, fob, peso] + ([color_por] if color_por and color_por != k else [])
    codifica = [("text", fob), ("text", peso)] + ([("color", color_por)] if color_por else [])
    vista = (primeros(k, n, f"SUM({U})") + NL if n else "") + orden(k, fob)
    return hoja(nombre, instancias, filas=ref(k[2]), cols=ref(fob[2]), vista=vista,
                estilo=sin_eje(fob, "cols") + ancho_de_nombres(k, nombres),
                panes=pane("Bar", codifica, estilo_marca=(COLOR(color) if color else "") + ETIQUETAS,
                           etiqueta_xml=etiqueta(run(valor(fob), d.TINTA, 9, F_MEDIA), run("   " + valor(peso), d.TENUE, 9)),
                           emergente_xml=emergente(run(valor(k), d.TINTA, 10, F_FUERTE), SALTO,
                                                   run("US$ " + valor(fob) + " mil millones, " + valor(peso) + de, pt=9))))


def evolucion(nombre: str) -> str:
    """Área mensual del FOB, en millones. La usan las páginas de orígenes y productos, filtrada por un clic."""
    fob = suma("c_fob_m")
    return hoja(nombre, [FECHA, MES_TEXTO, fob], filas=ref(fob[2]), cols=ref(FECHA[2]),
                panes=pane("Area", [("tooltip", MES_TEXTO)], estilo_marca=COLOR(d.CIAN),
                           emergente_xml=emergente(run(valor(MES_TEXTO), d.TINTA, 10, F_FUERTE), SALTO,
                                                   run("US$ " + valor(fob) + " millones en el mes", pt=9))),
                estilo=sin_titulo_de_eje(FECHA, "cols") + sin_titulo_de_eje(fob, "rows"))


def elegido(nombre: str, campo: str) -> str:
    i = calc_texto(campo)
    celda = ("<style-rule element='cell'><format attr='width' value='214' /><format attr='height' value='22' />"
             "<format attr='text-align' value='right' /></style-rule>")
    return hoja(nombre, [i], estilo=celda, panes=pane("Text", [("text", i)], estilo_marca=ETIQUETAS,
                                                      etiqueta_xml=etiqueta(run(valor(i), d.TINTA, 10, F_MEDIA))))


def matriz(nombre: str, fila: str, columna: str, medida: str, orden_columnas, vista: str = "", nombres: int = 150) -> str:
    """Tabla de calor: el peso de cada columna dentro de cada fila."""
    f, c, m, fob = dim(fila), dim(columna), calc(medida), suma("c_u12_mm")
    return hoja(nombre, [f, c, m, fob], filas=ref(f[2]), cols=ref(c[2]), estilo=(escala(m) + ancho_de_nombres(f, nombres) +
                        f"<style-rule element='label'><format attr='font-size' field={a(ref(c[2]))} value='8' /></style-rule>"),
                vista=(vista + NL if vista else "") + orden(f, fob) + NL + orden_fijo(c, orden_columnas),
                panes=pane("Square", [("color", m), ("text", m)], estilo_marca=ETIQUETAS,
                           etiqueta_xml=etiqueta(run(valor(m), d.TINTA, 9, F_MEDIA)),
                           emergente_xml=emergente(run(valor(f) + ", " + valor(c), d.TINTA, 10, F_FUERTE), SALTO,
                                                   run(valor(m) + " de lo que se importa en esa fila", pt=9))))


def hojas() -> dict[str, str]:
    h: dict[str, str] = {}
    fob_mm, u12, peso = suma("c_fob_mm"), suma("c_u12_mm"), calc("c_peso")
    pais, grupo, rubro, capitulo, via, region = (dim(c) for c in ("País de origen", "Grupo de origen", "Rubro", "Capítulo",
                                                                    "Vía (grupo)", "Región"))

    # Panorama
    h["KPI importado"] = cifra("KPI importado", calc("c_kpi_u12"))
    h["KPI variación"] = cifra("KPI variación", calc("c_var"))
    h["KPI origen"] = primero("KPI origen", "País de origen")
    h["KPI rubro"] = primero("KPI rubro", "Rubro")
    media = calc("c_mm12")
    hitos, formato_de_hitos = lineas_de_hitos(FECHA)
    h["Evolución mensual"] = hoja(
        "Evolución mensual", [FECHA, MES_TEXTO, fob_mm, media], filas=f"({ref(fob_mm[2])} + {ref(media[2])})", cols=ref(FECHA[2]),
        panes=[pane("Automatic", lineas_xml=hitos),
               pane("Area", [("tooltip", MES_TEXTO)], atributos=f" id='1' y-axis-name={a(ref(fob_mm[2]))}", estilo_marca=COLOR(d.CIAN),
                    emergente_xml=emergente(run(valor(MES_TEXTO), d.TINTA, 10, F_FUERTE), SALTO,
                                            run("US$ " + valor(fob_mm) + " mil millones en el mes", pt=9))),
               pane("Line", [("tooltip", MES_TEXTO)], atributos=f" id='2' y-axis-name={a(ref(media[2]))}", estilo_marca=COLOR(d.TINTA),
                    emergente_xml=emergente(run(valor(MES_TEXTO), d.TINTA, 10, F_FUERTE), SALTO,
                                            run("US$ " + valor(media) + " mil millones por mes, media de los últimos 12", pt=9)))],
        estilo=(f"<style-rule element='axis'><encoding attr='space' class='0' field={a(ref(media[2]))} field-type='quantitative' "
                f"fold='true' scope='rows' synchronized='true' type='space' /></style-rule>" + sin_eje(media, "rows") +
                sin_titulo_de_eje(FECHA, "cols") + sin_titulo_de_eje(fob_mm, "rows") + formato_de_hitos))
    h["Principales orígenes"] = ranking("Principales orígenes", "País de origen", n=12, color_por=grupo)
    sel = dict(peso_de="c_peso_sel", de=" de lo importado (o del origen elegido)")
    h["Principales rubros"] = ranking("Principales rubros", "Rubro", n=7, color=d.CIAN, nombres=196, **sel)
    h["Vías de transporte"] = ranking("Vías de transporte", "Vía (grupo)", color_por=via, nombres=130, **sel)

    # Orígenes
    mapa, nombre_pais, es_pais = dim("País (mapa)"), attr("País de origen"), dim("c_ubicable")
    capas = "".join(f"<format attr='enabled' id='{c}' value='false' />" for c in (
        "tab_base", "um_lcp_enabled", "tab_coastline", "pp2_adminlabels", "pp2_statebounds", "pp2_statelabels",
        "countrybounds_ln", "countrylabels_ln"))
    h["Mapa de orígenes"] = hoja(
        "Mapa de orígenes", [mapa, nombre_pais, u12, peso, es_pais], mapa=True,
        filas=f"[{DS}].[Latitude (generated)]", cols=f"[{DS}].[Longitude (generated)]",
        vista=solo(es_pais, "true"),   # Tierra del Fuego y las zonas francas no son países: quedan fuera del mapa
        panes=pane("Multipolygon", [("lod", mapa), ("color", u12), ("geometry", f"[{DS}].[Geometry (generated)]"),
                                    ("tooltip", nombre_pais), ("tooltip", peso)],
                   emergente_xml=emergente(run(valor(nombre_pais), d.TINTA, 10, F_FUERTE), SALTO,
                                           run("US$ " + valor(u12) + " mil millones, " + valor(peso) + " del total", pt=9))),
        estilo=(escala(u12, d.ESCALA_CIAN) + f"<style-rule element='map-layer'>{capas}</style-rule>"
                              "<style-rule element='map'><format attr='washout' value='0.0' /></style-rule>"))
    cambio, signo = calc("c_cambio"), calc_texto("c_signo_peso")
    h["Ganadores y perdedores"] = hoja(
        "Ganadores y perdedores", [pais, cambio, signo, peso], filas=ref(pais[2]), cols=ref(cambio[2]),
        vista=primeros(pais, 14, "ABS([c_cambio])") + NL + orden(pais, cambio),
        estilo=sin_eje(cambio, "cols") + ancho_de_nombres(pais, 196),
        panes=pane("Bar", [("color", signo), ("text", cambio), ("tooltip", peso)], estilo_marca=ETIQUETAS,
                   etiqueta_xml=etiqueta(run(valor(cambio), d.TINTA, 9, F_MEDIA)),
                   emergente_xml=emergente(run(valor(pais), d.TINTA, 10, F_FUERTE), SALTO,
                                           run(valor(cambio) + " puntos de peso desde 2019. Hoy pesa " + valor(peso), pt=9))))
    peso_anio = calc("c_peso_anio")
    final = calc("c_peso_anio_final")
    h["Peso de los grupos"] = hoja(
        "Peso de los grupos", [ANIO, grupo, peso_anio, final], filas=ref(peso_anio[2]), cols=ref(ANIO[2]),
        vista=sin(grupo, "Áreas especiales", "Resto del mundo"), estilo=sin_titulo_de_eje(peso_anio, "rows") + desde_piso(peso_anio, "rows", 0.05),
        panes=pane("Line", [("color", grupo), ("text", final), ("tooltip", peso_anio)], estilo_marca=ETIQUETAS,
                   etiqueta_xml=etiqueta(run(valor(final), d.TINTA, 8, F_MEDIA)),
                   emergente_xml=emergente(run(valor(grupo) + ", " + valor(ANIO), d.TINTA, 10, F_FUERTE), SALTO,
                                           run(valor(peso_anio) + " del FOB de ese año", pt=9))))
    h["Evolución del origen"] = evolucion("Evolución del origen")
    h["Origen elegido"] = elegido("Origen elegido", "c_origen_elegido")

    # Productos
    h["Mapa de productos"] = hoja(
        "Mapa de productos", [rubro, capitulo, u12, peso], estilo=escala(u12),
        panes=pane("Square", [("size", u12), ("color", u12), ("lod", rubro), ("text", capitulo), ("text", peso)],
                   estilo_marca=ETIQUETAS + f"<format attr='has-stroke' value='true' /><format attr='stroke-color' value='{d.PAGINA}' />",
                   etiqueta_xml=etiqueta(run(valor(capitulo), d.TINTA, 9, F_MEDIA), SALTO, run(valor(peso), d.TINTA, 8)),
                   emergente_xml=emergente(run(valor(capitulo), d.TINTA, 10, F_FUERTE), run("  (" + valor(rubro) + ")", pt=9), SALTO,
                                           run("US$ " + valor(u12) + " mil millones, " + valor(peso) + " del total", pt=9))))
    h["Rubro por origen"] = matriz("Rubro por origen", "Rubro", "Grupo de origen", "c_peso_rubro", GRUPOS_DE_ORIGEN,
                                   vista=primeros(rubro, 10, f"SUM({U})"), nombres=226)
    var, sube, base = calc("c_var"), calc_texto("c_signo"), suma("FOB últimos 12 meses")
    h["Subas y bajas"] = hoja(
        "Subas y bajas", [capitulo, var, sube, base], filas=ref(capitulo[2]), cols=ref(var[2]),
        vista=desde(base, 1_000_000_000) + NL + orden(capitulo, var), estilo=sin_eje(var, "cols") + ancho_de_nombres(capitulo, 196),
        panes=pane("Bar", [("color", sube), ("text", var)], estilo_marca=ETIQUETAS,
                   etiqueta_xml=etiqueta(run(valor(var), d.TINTA, 9, F_MEDIA))))
    h["Evolución del rubro"] = evolucion("Evolución del rubro")
    h["Rubro elegido"] = elegido("Rubro elegido", "c_rubro_elegido")

    # Logística
    h["Vías por año"] = hoja(
        "Vías por año", [ANIO, via, peso_anio], filas=ref(peso_anio[2]), cols=ref(ANIO[2]),
        vista=orden_fijo(via, list(d.COLOR_VIA)), estilo=sin_eje(peso_anio, "rows"),
        panes=pane("Bar", [("color", via), ("text", peso_anio)], estilo_marca=ETIQUETAS,
                   etiqueta_xml=etiqueta(run(valor(peso_anio), d.TINTA, 8, F_MEDIA))))
    h["Región por vía"] = matriz("Región por vía", "Región", "Vía (grupo)", "c_peso_region", list(d.COLOR_VIA),
                                 vista=sin(region, "Otros"))
    h["Calendario"] = hoja(
        "Calendario", [ANIO, MES_DEL_ANIO, fob_mm], filas=ref(ANIO[2]), cols=ref(MES_DEL_ANIO[2]),
        estilo=(escala(fob_mm) + ancho_de_nombres(ANIO, 46) +   # los meses, un punto más chicos: así entra "septiembre"
                f"<style-rule element='label'><format attr='font-size' field={a(ref(MES_DEL_ANIO[2]))} value='8' /></style-rule>"),
        panes=pane("Square", [("color", fob_mm), ("text", fob_mm)], estilo_marca=ETIQUETAS,
                   etiqueta_xml=etiqueta(run(valor(fob_mm), d.TINTA, 9, F_MEDIA))))
    por_item = calc("c_por_item")
    h["Valor por ítem"] = hoja(
        "Valor por ítem", [via, por_item], filas=ref(via[2]), cols=ref(por_item[2]),
        vista=sin(via, "Ductos") + NL + orden(via, por_item), estilo=sin_eje(por_item, "cols"),
        panes=pane("Bar", [("color", via), ("text", por_item)], estilo_marca=ETIQUETAS,
                   etiqueta_xml=etiqueta(run(valor(por_item), d.TINTA, 9, F_MEDIA))))

    # Método
    comb, elec, arriba = suma("c_combustibles"), suma("c_electrica"), calc("c_electrica_arriba")
    h["Energía eléctrica"] = hoja(
        "Energía eléctrica", [ANIO, comb, elec, arriba], filas=f"({ref(comb[2])} + {ref(elec[2])})", cols=ref(ANIO[2]),
        panes=[pane("Automatic"),
               pane("Bar", [("text", comb)], atributos=f" id='1' y-axis-name={a(ref(comb[2]))}", estilo_marca=COLOR(d.CIAN) + ETIQUETAS,
                    etiqueta_xml=etiqueta(run(valor(comb), d.TINTA, 8, F_MEDIA)),
                    emergente_xml=emergente(run(valor(ANIO), d.TINTA, 10, F_FUERTE), SALTO,
                                            run("Combustibles: US$ " + valor(comb) + " mil millones", pt=9))),
               pane("Line", [("text", arriba)], atributos=f" id='2' y-axis-name={a(ref(elec[2]))}",
                    estilo_marca=COLOR(d.MAGENTA) + ETIQUETAS, etiqueta_xml=etiqueta(run(valor(arriba), d.MAGENTA, 8, F_MEDIA)),
                    emergente_xml=emergente(run(valor(ANIO), d.TINTA, 10, F_FUERTE), SALTO,
                                            run("Energía eléctrica declarada: US$ " + valor(elec) + " mil millones", pt=9)))],
        estilo=(f"<style-rule element='axis'><encoding attr='space' class='0' field={a(ref(elec[2]))} field-type='quantitative' "
                f"fold='true' scope='rows' synchronized='true' type='space' /></style-rule>" + sin_eje(elec, "rows") +
                sin_eje(comb, "rows")))
    items = suma("c_items_miles")
    h["Cobertura"] = hoja("Cobertura", [FECHA, MES_TEXTO, items], filas=ref(items[2]), cols=ref(FECHA[2]),
                          panes=pane("Area", [("tooltip", MES_TEXTO)], estilo_marca=COLOR(d.VERDE_AZULADO),
                                     emergente_xml=emergente(run(valor(MES_TEXTO), d.TINTA, 10, F_FUERTE), SALTO,
                                                             run(valor(items) + " mil ítems de despacho", pt=9))),
                          estilo=sin_titulo_de_eje(FECHA, "cols") + sin_titulo_de_eje(items, "rows"))
    return h


MAPAS = {"Mapa de orígenes"}
SIN_AJUSTE = {"KPI importado", "KPI variación", "KPI origen", "KPI rubro", "Origen elegido", "Rubro elegido", "Mapa de orígenes"}
# Un clic en estas hojas filtra las que muestran la evolución, en la misma página
ACCIONES = [
    ("Elegir un origen en el panorama", "Panorama", "Principales orígenes",
     ["KPI importado", "KPI variación", "Evolución mensual", "Principales rubros", "Vías de transporte"]),
    ("Elegir un origen en el mapa", "Orígenes", "Mapa de orígenes", ["Evolución del origen", "Origen elegido"]),
    ("Elegir un origen en el ranking", "Orígenes", "Ganadores y perdedores", ["Evolución del origen", "Origen elegido"]),
    ("Elegir un rubro en el mapa de productos", "Productos", "Mapa de productos", ["Evolución del rubro", "Rubro elegido"]),
    ("Elegir un rubro en la matriz", "Productos", "Rubro por origen", ["Evolución del rubro", "Rubro elegido"]),
]


# ── Fuente de datos ────────────────────────────────────────────────────────────
def fuente_de_datos() -> str:
    cols = NL.join(f"            <column datatype={a(TIPOS[t][0])} name={a(n)} ordinal='{i}' />" for i, (n, t) in enumerate(COLUMNAS))
    campos = [def_columna(n, "      ") for n, _ in COLUMNAS] + [def_columna(c, "      ") for c in CALCULOS]
    instancias = [def_instancia(inst(*k), "      ") for k in PALETAS]
    paletas = NL.join(
        f"          <encoding attr='color' field={a('[' + inst(*k)[2] + ']')} type='palette'>" +
        "".join(f"<map to='{c.lower()}'><bucket>&quot;{escape(v)}&quot;</bucket></map>" for v, c in colores.items()) + "</encoding>"
        for k, colores in PALETAS.items())
    return f"""  <datasources>
    <datasource caption='Importaciones ARCA' inline='true' name='{DS}' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption='importaciones_argentina' name='textscan.importaciones'>
            <connection class='textscan' directory='.' filename={a(CSV.name)} password='' server='' />
          </named-connection>
        </named-connections>
        <relation connection='textscan.importaciones' name='importaciones_argentina.csv' table='[importaciones_argentina#csv]' type='table'>
          <columns character-set='UTF-8' header='yes' locale='es_AR' separator=','>
{cols}
          </columns>
        </relation>
      </connection>
      <aliases enabled='yes' />
{NL.join(campos)}
{NL.join(instancias)}
      <extract count='-1' enabled='true' units='records'>
        <connection access_mode='readonly' authentication='auth-none' author-locale='es_AR' class='hyper' dbname={a(HYPER.name)} default-settings='hyper' schema='Extract' sslmode='' tablename='Extract' update-time='11/27/2026 01:00:00 AM' username='tableau-internal-user'>
          <relation name='Extract' table='[Extract].[Extract]' type='table' />
          <refresh incremental-updates='false' />
        </connection>
      </extract>
      <style>
        <style-rule element='mark'>
{paletas}
        </style-rule>
      </style>
    </datasource>
  </datasources>"""


# ── Dashboards ─────────────────────────────────────────────────────────────────
def px(rect) -> str:
    """Posición en la grilla de 100.000 x 100.000 que usa Tableau, desde píxeles del lienzo."""
    x, y, w, h = rect
    return (f"h='{round(h * 100000 / d.ALTO)}' w='{round(w * 100000 / d.ANCHO)}' "
            f"x='{round(x * 100000 / d.ANCHO)}' y='{round(y * 100000 / d.ALTO)}'")


SIN_BORDE = ("<zone-style><format attr='border-style' value='none' /><format attr='margin' value='0' />"
             "<format attr='padding' value='0' /><format attr='background-color' value='#00000000' /></zone-style>")


def dashboard(pag: dict) -> str:
    # Todo flota dentro del contenedor raíz: así las hojas transparentes dejan ver la imagen de abajo
    zonas, n = [], 3
    zonas.append(f"          <zone floating='true' id='{n}' is-centered='0' is-scaled='1' param='fondos/{pag['id']}.png' "
                 f"type-v2='bitmap' {px((0, 0, d.ANCHO, d.ALTO))} />")
    for p in pag["paneles"]:
        if p["hoja"]:
            n += 1
            zonas.append(f"          <zone floating='true' id='{n}' name={a(p['hoja'])} show-title='false' {px(d.zona_de(p))}>{SIN_BORDE}</zone>")
        for extra in p["extra"]:   # el nombre de lo elegido, arriba a la derecha del panel
            n += 1
            x, y, w, _ = p["rect"]
            zonas.append(f"          <zone floating='true' id='{n}' name={a(extra)} show-title='false' {px((x + w - 236, y + 9, 220, 26))}>{SIN_BORDE}</zone>")
    for destino, rect in zip(d.NOMBRES_DE_PAGINA, d.NAV):
        if destino == pag["nombre"]:
            continue
        n += 1
        # Botón sin texto ni fondo, justo arriba del nombre de la página que ya está dibujado en la imagen
        zonas.append(f"          <zone floating='true' id='{n}' type-v2='dashboard-object' {px(rect)}>"
                     f"<button action='tabdoc:goto-sheet window-id=&quot;{guid('ventana/' + destino)}&quot;' button-type='text'>"
                     f"<button-visual-state><caption>&#160;</caption><tooltip-text>Ir a {escape(destino)}</tooltip-text>"
                     f"<button-caption-font-style fontcolor='#00000000' fontname={a(F_TEXTO)} fontsize='8' /></button-visual-state>"
                     f"</button>{SIN_BORDE}</zone>")
    return f"""    <dashboard name={a(pag["nombre"])}>
      <style><style-rule element='table'><format attr='background-color' value='{d.PAGINA}' /></style-rule></style>
      <size maxheight='{d.ALTO}' maxwidth='{d.ANCHO}' minheight='{d.ALTO}' minwidth='{d.ANCHO}' sizing-mode='fixed' />
      <zones>
        <zone h='100000' id='2' type-v2='layout-basic' w='100000' x='0' y='0'>
{NL.join(zonas)}
        </zone>
      </zones>
      <simple-id uuid='{guid("dashboard/" + pag["nombre"])}' />
    </dashboard>"""


def acciones() -> str:
    bloques = []
    for i, (titulo, pagina, origen, destinos) in enumerate(ACCIONES, start=1):
        todas = [p["hoja"] for pag in d.PAGINAS if pag["nombre"] == pagina for p in pag["paneles"] if p["hoja"]]
        todas += [e for pag in d.PAGINAS if pag["nombre"] == pagina for p in pag["paneles"] for e in p["extra"]]
        fuera = ",".join(h for h in todas if h not in destinos)
        bloques.append(f"""    <action caption={a(titulo)} name='[Action{i}]'>
      <activation auto-clear='true' type='on-select' />
      <source dashboard={a(pagina)} type='sheet' worksheet={a(origen)} />
      <command command='tsc:tsl-filter'>
        <param name='exclude' value={a(fuera)} />
        <param name='special-fields' value='all' />
        <param name='target' value={a(pagina)} />
      </command>
    </action>""")
    return "  <actions>" + NL + NL.join(bloques) + NL + "  </actions>"


def ventanas(nombres_de_hojas) -> str:
    previa = os.environ.get("TABLEAU_HOJA") or d.NOMBRES_DE_PAGINA[0]
    filas = []
    for n in nombres_de_hojas:
        maxi = " maximized='true'" if n == previa else " hidden='true'"
        filas.append(f"    <window class='worksheet'{maxi} name={a(n)}><cards><edge name='left'><strip size='160'><card type='pages' />"
                     f"<card type='filters' /><card type='marks' /></strip></edge><edge name='top'><strip size='2147483647'>"
                     f"<card type='columns' /></strip><strip size='2147483647'><card type='rows' /></strip></edge></cards>"
                     f"<simple-id uuid='{guid('ventana/' + n)}' /></window>")
    for pag in d.PAGINAS:
        en_pagina = [p["hoja"] for p in pag["paneles"] if p["hoja"]]
        vistas = "".join(f"<viewpoint name={a(n)}><zoom type='entire-view' /></viewpoint>" for n in en_pagina if n not in SIN_AJUSTE)
        # El mapa queda fijo: sin barra de herramientas, sin buscador y sin zoom, para que no se desarme la composición
        vistas += "".join(f"<viewpoint name={a(n)}><floating-toolbar-visibility value='2' /><geo-search-visibility value='0' />"
                          f"<map-navigation value='0' /></viewpoint>" for n in en_pagina if n in MAPAS)
        maxi = " maximized='true'" if pag["nombre"] == previa else ""
        filas.append(f"    <window class='dashboard'{maxi} name={a(pag['nombre'])}><viewpoints>{vistas}</viewpoints><active id='-1' />"
                     f"<simple-id uuid='{guid('ventana/' + pag['nombre'])}' /></window>")
    return "  <windows source-height='30'>" + NL + NL.join(filas) + NL + "  </windows>"


def main() -> None:
    h = hojas()
    usadas = [p["hoja"] for pag in d.PAGINAS for p in pag["paneles"] if p["hoja"]] + \
             [e for pag in d.PAGINAS for p in pag["paneles"] for e in p["extra"]]
    faltan = [n for n in usadas if n not in h]
    if faltan:
        sys.exit(f"El diseño pide hojas que no existen: {faltan}")
    xml = f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook original-version='18.1' source-build='2026.3.0 (20263.25.1027.1305)' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest>
    <BasicButtonObject />
    <BasicButtonObjectTextSupport />
    <SheetIdentifierTracking />
    <WindowsPersistSimpleIdentifiers />
  </document-format-change-manifest>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
{fuente_de_datos()}
{acciones()}
  <worksheets>
{NL.join(h.values())}
  </worksheets>
  <dashboards>
{NL.join(dashboard(pag) for pag in d.PAGINAS)}
  </dashboards>
{ventanas(list(h))}
</workbook>
"""
    SALIDA.write_text(xml, encoding="utf-8")
    print(f"Listo: {SALIDA} ({len(h)} hojas, {len(d.PAGINAS)} páginas)")


if __name__ == "__main__":
    main()
