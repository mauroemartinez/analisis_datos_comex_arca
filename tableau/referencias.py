"""Tablas de referencia del tablero: países, capítulos, grandes rubros, vías y grupos de origen.

Los códigos de país y de vía son los de ARCA; los capítulos son los dos primeros dígitos de la
posición NCM (Sistema Armonizado), con nombres cortos. Los grandes rubros y los grupos de origen
son agrupaciones propias, pensadas para leer el tablero de un vistazo.
"""

AREAS = "Áreas especiales"

# Columnas de la extracción, en orden: (nombre, tipo de Hyper). Las leen preparar_datos.py y generar_twb.py
COLUMNAS = [
    ("Fecha", "date"), ("Rubro", "text"), ("Capítulo", "text"), ("N.º de capítulo", "text"),
    ("País de origen", "text"), ("País (mapa)", "text"), ("Región", "text"), ("Grupo de origen", "text"),
    ("Vía de transporte", "text"), ("Vía (grupo)", "text"),
    ("FOB USD", "double"), ("Ítems", "big_int"),
    ("FOB últimos 12 meses", "double"), ("FOB 12 meses anteriores", "double"), ("FOB 2019", "double"),
    ("FOB energía eléctrica", "double"),
]

# Código de país de ARCA: (nombre, ISO 3166 alfa-3, región)
PAIS = {
    "203": ("Brasil", "BRA", "Sudamérica"), "310": ("China", "CHN", "Asia"),
    "212": ("Estados Unidos", "USA", "Norteamérica"), "438": ("Alemania", "DEU", "Europa"),
    "225": ("Uruguay", "URY", "Sudamérica"), "417": ("Italia", "ITA", "Europa"),
    "218": ("México", "MEX", "Norteamérica"), "202": ("Bolivia", "BOL", "Sudamérica"),
    "315": ("India", "IND", "Asia"), "337": ("Vietnam", "VNM", "Asia"),
    "410": ("España", "ESP", "Europa"), "412": ("Francia", "FRA", "Europa"),
    "320": ("Japón", "JPN", "Asia"), "335": ("Tailandia", "THA", "Asia"),
    "208": ("Chile", "CHL", "Sudamérica"), "430": ("Suiza", "CHE", "Europa"),
    "423": ("Países Bajos", "NLD", "Europa"), "309": ("Corea del Sur", "KOR", "Asia"),
    "426": ("Reino Unido", "GBR", "Europa"), "313": ("Taiwán", "TWN", "Asia"),
    "204": ("Canadá", "CAN", "Norteamérica"), "127": ("Marruecos", "MAR", "África"),
    "406": ("Bélgica", "BEL", "Europa"), "415": ("Irlanda", "IRL", "Europa"),
    "316": ("Indonesia", "IDN", "Asia"), "205": ("Colombia", "COL", "Sudamérica"),
    "326": ("Malasia", "MYS", "Asia"), "210": ("Ecuador", "ECU", "Sudamérica"),
    "331": ("Emiratos Árabes Unidos", "ARE", "Medio Oriente"), "436": ("Turquía", "TUR", "Europa"),
    "302": ("Arabia Saudita", "SAU", "Medio Oriente"), "444": ("Rusia", "RUS", "Europa"),
    "429": ("Suecia", "SWE", "Europa"), "221": ("Paraguay", "PRY", "Sudamérica"),
    "113": ("Egipto", "EGY", "África"), "405": ("Austria", "AUT", "Europa"),
    "409": ("Dinamarca", "DNK", "Europa"), "414": ("Hungría", "HUN", "Europa"),
    "222": ("Perú", "PER", "Sudamérica"), "411": ("Finlandia", "FIN", "Europa"),
    "424": ("Polonia", "POL", "Europa"), "224": ("Trinidad y Tobago", "TTO", "Centroamérica y Caribe"),
    "319": ("Israel", "ISR", "Medio Oriente"), "501": ("Australia", "AUS", "Oceanía"),
    "451": ("República Checa", "CZE", "Europa"), "322": ("Qatar", "QAT", "Medio Oriente"),
    "333": ("Singapur", "SGP", "Asia"), "102": ("Argelia", "DZA", "África"),
    "425": ("Portugal", "PRT", "Europa"), "159": ("Sudáfrica", "ZAF", "África"),
    "131": ("Nigeria", "NGA", "África"), "328": ("Omán", "OMN", "Medio Oriente"),
    "427": ("Rumania", "ROU", "Europa"), "422": ("Noruega", "NOR", "Europa"),
    "442": ("Lituania", "LTU", "Europa"), "312": ("Filipinas", "PHL", "Asia"),
    "223": ("Puerto Rico", "PRI", "Centroamérica y Caribe"), "332": ("Pakistán", "PAK", "Asia"),
    "448": ("Eslovaquia", "SVK", "Europa"), "355": ("Turkmenistán", "TKM", "Asia"),
    "449": ("Eslovenia", "SVN", "Europa"), "306": ("Camboya", "KHM", "Asia"),
    "345": ("Bangladés", "BGD", "Asia"), "303": ("Baréin", "BHR", "Medio Oriente"),
    "119": ("Guinea Ecuatorial", "GNQ", "África"), "413": ("Grecia", "GRC", "Europa"),
    "206": ("Costa Rica", "CRI", "Centroamérica y Caribe"), "323": ("Kuwait", "KWT", "Medio Oriente"),
    "407": ("Bulgaria", "BGR", "Europa"), "504": ("Nueva Zelanda", "NZL", "Oceanía"),
    "141": ("Túnez", "TUN", "África"), "445": ("Ucrania", "UKR", "Europa"),
    "352": ("Kazajistán", "KAZ", "Asia"), "307": ("Sri Lanka", "LKA", "Asia"),
    "341": ("Hong Kong", "HKG", "Asia"), "419": ("Luxemburgo", "LUX", "Europa"),
    "108": ("Congo", "COG", "África"), "440": ("Estonia", "EST", "Europa"),
    "158": ("Namibia", "NAM", "África"), "447": ("Croacia", "HRV", "Europa"),
    "308": ("Corea del Norte", "PRK", "Asia"), "304": ("Myanmar", "MMR", "Asia"),
    "324": ("Laos", "LAO", "Asia"), "439": ("Bielorrusia", "BLR", "Europa"),
    "321": ("Jordania", "JOR", "Medio Oriente"), "420": ("Malta", "MLT", "Europa"),
    "217": ("Jamaica", "JAM", "Centroamérica y Caribe"), "226": ("Venezuela", "VEN", "Sudamérica"),
    "441": ("Letonia", "LVA", "Europa"), "209": ("República Dominicana", "DOM", "Centroamérica y Caribe"),
    "207": ("Cuba", "CUB", "Centroamérica y Caribe"), "213": ("Guatemala", "GTM", "Centroamérica y Caribe"),
    "140": ("Togo", "TGO", "África"), "446": ("Bosnia y Herzegovina", "BIH", "Europa"),
    "105": ("Camerún", "CMR", "África"), "110": ("Costa de Marfil", "CIV", "África"),
    "211": ("El Salvador", "SLV", "Centroamérica y Caribe"), "450": ("Macedonia del Norte", "MKD", "Europa"),
    "151": ("Mozambique", "MOZ", "África"), "216": ("Honduras", "HND", "Centroamérica y Caribe"),
    "318": ("Irán", "IRN", "Medio Oriente"), "124": ("Madagascar", "MDG", "África"),
    "346": ("Brunéi", "BRN", "Asia"), "416": ("Islandia", "ISL", "Europa"),
    "351": ("Georgia", "GEO", "Asia"), "117": ("Ghana", "GHA", "África"),
    "350": ("Azerbaiyán", "AZE", "Asia"), "220": ("Panamá", "PAN", "Centroamérica y Caribe"),
    "149": ("Angola", "AGO", "África"), "435": ("Chipre", "CYP", "Europa"),
    "418": ("Liechtenstein", "LIE", "Europa"), "120": ("Kenia", "KEN", "África"),
    "136": ("Somalia", "SOM", "África"), "240": ("Granada", "GRD", "Centroamérica y Caribe"),
    "401": ("Albania", "ALB", "Europa"), "123": ("Libia", "LBY", "África"),
    "134": ("Senegal", "SEN", "África"), "219": ("Nicaragua", "NIC", "Centroamérica y Caribe"),
    "128": ("Mauricio", "MUS", "África"), "428": ("San Marino", "SMR", "Europa"),
    "421": ("Mónaco", "MCO", "Europa"), "132": ("Zimbabue", "ZWE", "África"),
    "356": ("Uzbekistán", "UZB", "Asia"), "344": ("Macao", "MAC", "Asia"),
    "115": ("Gabón", "GAB", "África"), "443": ("Moldavia", "MDA", "Europa"),
    "239": ("Bahamas", "BHS", "Centroamérica y Caribe"), "317": ("Irak", "IRQ", "Medio Oriente"),
    "161": ("Etiopía", "ETH", "África"), "349": ("Armenia", "ARM", "Asia"),
    "325": ("Líbano", "LBN", "Medio Oriente"), "215": ("Haití", "HTI", "Centroamérica y Caribe"),
    "125": ("Malaui", "MWI", "África"), "238": ("San Cristóbal y Nieves", "KNA", "Centroamérica y Caribe"),
    "201": ("Barbados", "BRB", "Centroamérica y Caribe"), "139": ("Tanzania", "TZA", "África"),
    "144": ("Zambia", "ZMB", "África"), "236": ("Belice", "BLZ", "Centroamérica y Caribe"),
    "142": ("Uganda", "UGA", "África"), "237": ("Antigua y Barbuda", "ATG", "Centroamérica y Caribe"),
    "111": ("Chad", "TCD", "África"), "242": ("Aruba", "ABW", "Centroamérica y Caribe"),
    "153": ("Yibuti", "DJI", "África"), "126": ("Malí", "MLI", "África"),
    "116": ("Gambia", "GMB", "África"), "130": ("Níger", "NER", "África"),
    "301": ("Afganistán", "AFG", "Asia"), "118": ("Guinea", "GIN", "África"),
    "156": ("Guinea-Bisáu", "GNB", "África"), "404": ("Andorra", "AND", "Europa"),
    "109": ("República Democrática del Congo", "COD", "África"), "135": ("Sierra Leona", "SLE", "África"),
    "129": ("Mauritania", "MRT", "África"), "348": ("Yemen", "YEM", "Medio Oriente"),
    "107": ("República Centroafricana", "CAF", "África"), "305": ("Bután", "BTN", "Asia"),
    "103": ("Botsuana", "BWA", "África"), "354": ("Tayikistán", "TJK", "Asia"),
    "121": ("Lesoto", "LSO", "África"), "513": ("Papúa Nueva Guinea", "PNG", "Oceanía"),
    "330": ("Nepal", "NPL", "Asia"), "512": ("Fiyi", "FJI", "Oceanía"),
    "353": ("Kirguistán", "KGZ", "Asia"), "329": ("Mongolia", "MNG", "Asia"),
    "232": ("Surinam", "SUR", "Sudamérica"), "214": ("Guyana", "GUY", "Sudamérica"),
    "334": ("Siria", "SYR", "Medio Oriente"), "133": ("Ruanda", "RWA", "África"),
    "122": ("Liberia", "LBR", "África"), "112": ("Benín", "BEN", "África"),
    "101": ("Burkina Faso", "BFA", "África"), "104": ("Burundi", "BDI", "África"),
    "200": ("Argentina (reimportación)", "", AREAS),
}

# Capítulos del Sistema Armonizado, en corto
CAPITULO = {
    1: "Animales vivos", 2: "Carne", 3: "Pescados y mariscos", 4: "Lácteos, huevos y miel", 5: "Otros productos animales",
    6: "Plantas y flores", 7: "Hortalizas", 8: "Frutas", 9: "Café, té y especias", 10: "Cereales",
    11: "Harinas y almidones", 12: "Semillas y oleaginosas", 13: "Gomas y resinas vegetales", 14: "Otros vegetales",
    15: "Grasas y aceites", 16: "Preparaciones de carne y pescado", 17: "Azúcar y confitería", 18: "Cacao y chocolate",
    19: "Panadería y pastas", 20: "Conservas de frutas y hortalizas", 21: "Preparaciones alimenticias diversas",
    22: "Bebidas", 23: "Alimento para animales", 24: "Tabaco", 25: "Sal, piedras y cemento", 26: "Minerales metalíferos",
    27: "Combustibles", 28: "Química inorgánica", 29: "Química orgánica", 30: "Farmacéuticos",
    31: "Fertilizantes", 32: "Tintas, pinturas y colorantes", 33: "Perfumería y cosmética", 34: "Jabones y limpieza",
    35: "Colas y enzimas", 36: "Explosivos y pirotecnia", 37: "Productos fotográficos", 38: "Químicos diversos",
    39: "Plásticos", 40: "Caucho", 41: "Cueros", 42: "Marroquinería", 43: "Peletería", 44: "Madera",
    45: "Corcho", 46: "Cestería", 47: "Pasta de papel", 48: "Papel y cartón", 49: "Libros e impresos",
    50: "Seda", 51: "Lana", 52: "Algodón", 53: "Otras fibras vegetales", 54: "Filamentos sintéticos",
    55: "Fibras sintéticas", 56: "Guata y cordelería", 57: "Alfombras", 58: "Tejidos especiales",
    59: "Telas técnicas", 60: "Tejidos de punto", 61: "Ropa de punto", 62: "Ropa (no de punto)",
    63: "Otros textiles confeccionados", 64: "Calzado", 65: "Sombreros", 66: "Paraguas y bastones",
    67: "Plumas y flores artificiales", 68: "Manufacturas de piedra y yeso", 69: "Cerámica", 70: "Vidrio",
    71: "Piedras y metales preciosos", 72: "Hierro y acero", 73: "Manufacturas de hierro y acero", 74: "Cobre",
    75: "Níquel", 76: "Aluminio", 78: "Plomo", 79: "Zinc", 80: "Estaño", 81: "Otros metales comunes",
    82: "Herramientas", 83: "Manufacturas de metal diversas", 84: "Maquinaria",
    85: "Electrónica y equipos eléctricos", 86: "Ferrocarriles", 87: "Vehículos y autopartes", 88: "Aeronaves",
    89: "Barcos", 90: "Óptica, medicina y medición", 91: "Relojes", 92: "Instrumentos musicales",
    93: "Armas y municiones", 94: "Muebles, colchones e iluminación", 95: "Juguetes y deportes",
    96: "Manufacturas diversas", 97: "Obras de arte", 98: "Regímenes especiales", 99: "Regímenes especiales",
}

# Grandes rubros: (capítulo desde, capítulo hasta, nombre)
RUBROS = [
    (1, 24, "Agro y alimentos"), (25, 26, "Minerales"), (27, 27, "Combustibles"), (28, 38, "Químicos y farmacéuticos"),
    (39, 40, "Plásticos y caucho"), (41, 49, "Cuero, madera y papel"), (50, 67, "Textiles y calzado"),
    (68, 71, "Piedra, vidrio y metales preciosos"), (72, 83, "Metales y sus manufacturas"), (84, 84, "Maquinaria"),
    (85, 85, "Electrónica y equipos eléctricos"), (86, 89, "Vehículos y transporte"),
    (90, 97, "Instrumentos y manufacturas diversas"),
]

# Vía de transporte de ARCA: (nombre, grupo)
OTRAS_VIAS = "Otras y sin informar"
VIAS = {
    "8": ("Marítima", "Marítima"), "4": ("Camión", "Camión"), "2": ("Aérea", "Aérea"),
    "7": ("Ductos (gas y petróleo)", "Ductos"), "3": ("Ferrocarril", OTRAS_VIAS), "9": ("Conductor eléctrico", OTRAS_VIAS),
    "1": ("Propios medios", OTRAS_VIAS), "A": ("Postal", OTRAS_VIAS), "5": ("Arreo", OTRAS_VIAS), "6": ("Jangada", OTRAS_VIAS),
}
VIA_SIN_DATO = ("Sin informar", OTRAS_VIAS)

# Grupos de origen: los tres socios principales, la Unión Europea como bloque y el resto
UNION_EUROPEA = {"AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "IRL", "ITA", "LVA",
                 "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE"}
GRUPOS_DE_ORIGEN = ["Brasil", "China", "Unión Europea", "Estados Unidos", "Resto del mundo", AREAS]


def rubro(capitulo: int | None) -> str:
    if capitulo is None:
        return "Otros"
    for desde, hasta, nombre in RUBROS:
        if desde <= capitulo <= hasta:
            return nombre
    return "Otros"


def grupo_de_origen(nombre: str, iso3: str, region: str) -> str:
    if region == AREAS:
        return AREAS
    if nombre in ("Brasil", "China", "Estados Unidos"):
        return nombre
    if iso3 in UNION_EUROPEA:
        return "Unión Europea"
    return "Resto del mundo"
