"""Diseño del tablero: marca, páginas, paneles y textos fijos.

Es la única fuente de verdad de las posiciones. De acá leen:
- fondos.py, que dibuja el fondo de vidrio de cada página con sus títulos (la marca en imagen);
- generar_twb.py, que pone cada hoja de Tableau, transparente, justo encima de su panel.

Todo está en píxeles de un lienzo de 1280 x 720, como una página de Power BI.
"""

import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ANCHO, ALTO = 1280, 720

# ── Marca GlobalAIze (versión oscura) ──────────────────────────────────────────
PAGINA = "#040F23"
TINTA, SECUNDARIO, TENUE = "#F0EEE9", "#BBC5D1", "#8D9AA8"
TARJETA = "#0D2C5F"            # una tarjeta dentro de un panel
GRILLA = "#16284A"             # líneas de referencia muy suaves sobre el vidrio
CIAN, VIOLETA, OLIVA, AZUL, ROJO, VERDE_AZULADO, MAGENTA, VERDE = (
    "#0DA4CF", "#795EC9", "#A69722", "#4170CB", "#C13234", "#3BAB8D", "#B33879", "#47AB4F")
GRIS_SERIE = "#5E6B7D"         # "resto" y "otros": no compite con las series
BUENO, MALO = "#62D286", "#EF6661"
ESCALA_CIAN = ["#0B2E55", "#0DA4CF", "#8FE3FA"]   # de menos a más, sobre fondo oscuro (mapa)
ESCALA_CON_TEXTO = ["#0B2E55", "#0DA4CF"]         # cuando lleva números blancos encima

# Un color sigue a su categoría, en el orden fijo de la marca
COLOR_GRUPO = {"Brasil": CIAN, "China": VIOLETA, "Unión Europea": OLIVA, "Estados Unidos": AZUL,
               "Áreas especiales": VERDE_AZULADO, "Resto del mundo": GRIS_SERIE}
COLOR_VIA = {"Marítima": CIAN, "Camión": VIOLETA, "Aérea": OLIVA, "Ductos": AZUL, "Otras y sin informar": GRIS_SERIE}
REFERENCIA = "#3D5480"         # líneas de referencia: se ven sobre el vidrio sin competir con los datos

# Cambios de reglas que se marcan en la evolución mensual: (mes, nombre corto, nombre largo para la página de método)
HITOS = [
    ("2020-03-01", "Cuarentena", "la cuarentena (marzo de 2020)"),
    ("2022-10-01", "SIRA", "el régimen SIRA (octubre de 2022)"),
    ("2023-12-01", "Devaluación", "la devaluación y el fin de SIRA (diciembre de 2023)"),
    ("2025-04-01", "Menos cepo", "la flexibilización del cepo (abril de 2025)"),
]

# ── Textos que dependen de los datos ───────────────────────────────────────────
try:
    CIFRAS = json.loads((AQUI / "datos_del_tablero.json").read_text(encoding="utf-8"))
except FileNotFoundError:   # todavía no se corrió preparar_datos.py
    CIFRAS = {}


def _corto(mes: str) -> str:
    """'septiembre de 2025' → 'sep 2025'."""
    nombre, _, anio = mes.partition(" de ")
    return f"{nombre[:3]} {anio}"


U12 = CIFRAS.get("ultimos_12_meses", {"desde": "septiembre de 2025", "hasta": "agosto de 2026"})
P12 = CIFRAS.get("doce_meses_anteriores", {"desde": "septiembre de 2024", "hasta": "agosto de 2025"})
VENTANA = f"{_corto(U12['desde'])} a {_corto(U12['hasta'])}"
VENTANA_ANTERIOR = f"{_corto(P12['desde'])} a {_corto(P12['hasta'])}"

TITULO = "Importaciones de Argentina"
SUBTITULO = "2019 a 2026, con los datos abiertos de ARCA"
PIE = ("Fuente: ARCA, despachos de importación (datos abiertos). Valores FOB en dólares. No incluye energía eléctrica: "
       "el motivo está en Método. Hecho por GlobalAIze.")

# ── Grilla ─────────────────────────────────────────────────────────────────────
M = 20                         # margen del lienzo
ENCABEZADO = (M, 12, ANCHO - 2 * M, 64)
ARRIBA, ABAJO = 88, 692        # donde empiezan y terminan los paneles
SEP = 12                       # separación entre paneles


def panel(rect, titulo="", contexto="", hoja=None, *, tipo="grafico", leyenda=None, extra=None, rotulo="", nota=""):
    """Un panel de vidrio. tipo: 'grafico' (título y contexto arriba), 'kpi' (rótulo, cifra y nota) o 'texto'."""
    return {"rect": rect, "titulo": titulo, "contexto": contexto, "hoja": hoja, "tipo": tipo, "leyenda": leyenda or [],
            "extra": extra or [], "rotulo": rotulo, "nota": nota}


def zona_de(p: dict) -> tuple[int, int, int, int]:
    """Rectángulo, dentro del panel, donde va la hoja de Tableau."""
    x, y, w, h = p["rect"]
    if p["tipo"] == "kpi":
        return (x + 12, y + 21, w - 24, 52)   # transparente: puede pisar el rótulo y la nota sin taparlos
    arriba = 56 if p["contexto"] else 40
    return (x + 12, y + arriba, w - 24, h - arriba - 10)


_KPI_W = (ANCHO - 2 * M - 3 * SEP) // 4            # 301
_kx = [M + i * (_KPI_W + SEP) for i in range(4)]

PAGINAS = [
    {
        "id": "panorama", "nombre": "Panorama",
        "paneles": [
            panel((_kx[0], ARRIBA, _KPI_W, 92), tipo="kpi", hoja="KPI importado", rotulo="Importado en los últimos 12 meses",
                  nota=VENTANA),
            panel((_kx[1], ARRIBA, _KPI_W, 92), tipo="kpi", hoja="KPI variación", rotulo="Contra los 12 meses anteriores",
                  nota=VENTANA_ANTERIOR),
            panel((_kx[2], ARRIBA, _KPI_W, 92), tipo="kpi", hoja="KPI origen", rotulo="Principal origen", nota="de lo importado en los últimos 12 meses"),
            panel((_kx[3], ARRIBA, _KPI_W, 92), tipo="kpi", hoja="KPI rubro", rotulo="Principal rubro", nota="de lo importado en los últimos 12 meses"),
            panel((M, 192, 820, 252), "Importaciones por mes", "Miles de millones de dólares FOB", "Evolución mensual",
                  leyenda=[(CIAN, "Mes"), (TINTA, "Media móvil de 12 meses")]),
            panel((852, 192, 408, 500), "De dónde viene", "Últimos 12 meses. Un clic en un origen filtra la página.",
                  "Principales orígenes", leyenda=[(OLIVA, "Unión Europea"), (GRIS_SERIE, "Resto del mundo")]),
            panel((M, 456, 404, 236), "Qué se compra", "Los 7 rubros principales, en el total o en el origen elegido", "Principales rubros"),
            panel((436, 456, 404, 236), "Cómo llega", "Vía de transporte, por FOB de los últimos 12 meses", "Vías de transporte"),
        ],
    },
    {
        "id": "origenes", "nombre": "Orígenes",
        "paneles": [
            panel((M, ARRIBA, 760, 360), "El mapa de los proveedores",
                  f"FOB por país de origen, {VENTANA}. Un clic en un país muestra abajo su evolución.", "Mapa de orígenes"),
            panel((792, ARRIBA, 468, 360), "Quién ganó y quién perdió peso",
                  "Cambio del peso de cada origen, en puntos: últimos 12 meses contra 2019", "Ganadores y perdedores"),
            panel((M, 460, 612, 232), "El peso de los socios principales", "Parte del FOB anual", "Peso de los grupos",
                  leyenda=[(c, n) for n, c in COLOR_GRUPO.items() if n not in ("Áreas especiales", "Resto del mundo")]),
            panel((644, 460, 616, 232), "Evolución del origen elegido", "FOB por mes, en millones de dólares", "Evolución del origen",
                  extra=["Origen elegido"]),
        ],
    },
    {
        "id": "productos", "nombre": "Productos",
        "paneles": [
            panel((M, ARRIBA, 612, 360), "Qué importa Argentina", f"Rubros y capítulos por FOB, {VENTANA}. Un clic muestra abajo su evolución.",
                  "Mapa de productos"),
            panel((644, ARRIBA, 616, 360), "A quién se le compra cada cosa",
                  "Peso de cada grupo de origen dentro de cada rubro, últimos 12 meses", "Rubro por origen"),
            panel((M, 460, 612, 232), "Qué creció y qué cayó", f"Capítulos de más de USD 1.000 M: {VENTANA} contra los 12 meses anteriores",
                  "Subas y bajas"),
            panel((644, 460, 616, 232), "Evolución del rubro elegido", "FOB por mes, en millones de dólares", "Evolución del rubro",
                  extra=["Rubro elegido"]),
        ],
    },
    {
        "id": "logistica", "nombre": "Logística",
        "paneles": [
            panel((M, ARRIBA, 612, 296), "Cómo llega la mercadería", "Peso de cada vía en el FOB de cada año", "Vías por año",
                  leyenda=list((c, n) for n, c in COLOR_VIA.items())),
            panel((644, ARRIBA, 616, 296), "Cada región, por su vía", "Peso de cada vía en lo que llega de cada región, últimos 12 meses",
                  "Región por vía"),
            panel((M, 396, 820, 296), "Estacionalidad", "FOB de cada mes, en miles de millones de dólares", "Calendario"),
            panel((852, 396, 408, 296), "Cuánto vale cada ítem", "FOB medio por ítem, últimos 12 meses. Sin ductos: USD 2 M por ítem",
                  "Valor por ítem"),
        ],
    },
    {
        "id": "metodo", "nombre": "Método",
        "paneles": [
            panel((M, ARRIBA, 612, 604), "Cómo se armó este tablero", tipo="texto"),
            panel((644, ARRIBA, 616, 296), "Por qué no está la energía eléctrica",
                  "Miles de millones de dólares por año",
                  "Energía eléctrica", leyenda=[(CIAN, "Combustibles, en el tablero"), (MAGENTA, "Energía eléctrica declarada, excluida")]),
            panel((644, 396, 616, 296), "Cobertura de la base", "Ítems de despacho por mes, en miles", "Cobertura"),
        ],
    },
]
NOMBRES_DE_PAGINA = [p["nombre"] for p in PAGINAS]

# Navegación: una pastilla por página, a la derecha del encabezado
NAV_ANCHO, NAV_ALTO, NAV_SEP = 86, 30, 4
_nav_x0 = ENCABEZADO[0] + ENCABEZADO[2] - 16 - len(PAGINAS) * NAV_ANCHO - (len(PAGINAS) - 1) * NAV_SEP
NAV = [(_nav_x0 + i * (NAV_ANCHO + NAV_SEP), ENCABEZADO[1] + (ENCABEZADO[3] - NAV_ALTO) // 2, NAV_ANCHO, NAV_ALTO)
       for i in range(len(PAGINAS))]


def _miles(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def texto_del_metodo() -> list[tuple[str, str]]:
    """Bloques (rótulo, párrafo) de la página de método, con las cifras del proceso."""
    c = CIFRAS
    if not c:
        return [("Falta correr preparar_datos.py", "")]
    e = c["energia_electrica_excluida"]
    return [
        ("La fuente", "Los despachos de importación que publica ARCA como datos abiertos, mes a mes. Cada despacho trae sus "
                      "ítems y, por cada ítem, una fila por concepto de arancel."),
        ("El proceso", f"De {_miles(c['filas_de_la_fuente'] / 1e6)} millones de filas a {_miles(c['items_de_despacho'] / 1e6)} "
                       f"millones de ítems (el FOB se repite en cada concepto: se cuenta una vez por ítem), y de ahí a un resumen "
                       f"de {_miles(c['filas_del_resumen'])} filas por mes, capítulo, origen y vía. Todo con DuckDB, en menos de dos "
                       f"minutos. El tablero se genera desde código: datos, hojas y diseño."),
        ("Qué mide", f"Valor FOB en dólares, de {c['desde']} a {c['hasta']}. No es la estadística oficial de comercio exterior: "
                     "el INDEC mide a valor CIF y con otra cobertura, así que los totales no coinciden."),
        ("Qué quedó afuera", f"2018 (le faltan meses en la fuente) y la energía eléctrica: {_miles(e['items'])} ítems declaran "
                             f"USD {_miles(e['fob_declarado_musd'] / 1e3)} mil millones, con ítems repetidos por más de lo que la "
                             "interconexión puede transportar. Dejarlos adentro duplicaba el peso de los combustibles."),
        ("Cómo leerlo", "Capítulo es el par de dígitos inicial de la posición NCM; los rubros los agrupan. Tierra del Fuego y las "
                        "zonas francas figuran como origen porque así vienen en la base: son áreas aduaneras especiales, no países, "
                        "y por eso no están en el mapa. \"Últimos 12 meses\" es siempre el último año móvil con datos."),
        ("Los hitos", "En la evolución mensual se marcan cuatro cambios de reglas: " + ", ".join(h[2] for h in HITOS[:-1]) +
                      " y " + HITOS[-1][2] + "."),
    ]
