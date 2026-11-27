"""Dibuja el fondo de cada página del tablero: vidrio de la marca, logo, títulos y navegación.

Tableau solo pinta fondos lisos y no trae las tipografías de la marca, así que todo lo que es
fijo va en una imagen por página (como en los tableros de Power BI de GlobalAIze) y las hojas
de Tableau, transparentes, van encima. Las posiciones salen de diseno.py: si un panel se mueve,
se vuelve a correr esto y generar_twb.py.

Uso: python tableau/fondos.py   (deja tableau/fondos/<página>.png, al doble de resolución)
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / "marca"))
import diseno as d  # noqa: E402
import vidrio  # noqa: E402

K = vidrio.K
SALIDA = AQUI / "fondos"
FUENTES = AQUI / "marca" / "fuentes"
_cache: dict = {}


def fuente(familia: str, peso: int, px: float) -> ImageFont.FreeTypeFont:
    clave = (familia, peso, px)
    if clave not in _cache:
        _cache[clave] = ImageFont.truetype(str(FUENTES / f"{familia}-{peso}.ttf"), round(px * K))
    return _cache[clave]


def plex(peso: int, px: float):
    return fuente("ibm-plex-sans", peso, px)


def news(px: float):
    return fuente("newsreader", 500, px)


def ancho(texto: str, f, espaciado: float = 0) -> float:
    """Ancho del texto en píxeles del lienzo."""
    return (f.getlength(texto) + espaciado * K * max(len(texto) - 1, 0)) / K


def escribir(dib, x, y, texto, f, color, espaciado: float = 0, derecha: bool = False):
    """Escribe en (x, y) del lienzo; con derecha=True, x es el borde derecho."""
    if derecha:
        x -= ancho(texto, f, espaciado)
    if not espaciado:
        dib.text((x * K, y * K), texto, font=f, fill=color)
        return
    cx = x * K
    for letra in texto:   # Pillow no espacia letras: una por una
        dib.text((cx, y * K), letra, font=f, fill=color)
        cx += f.getlength(letra) + espaciado * K


def partir(texto: str, f, maximo: float) -> list[str]:
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if ancho(prueba, f) <= maximo or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    return lineas + [actual] if actual else lineas


def pegar(fondo, archivo: str, x: float, y: float, alto: float) -> float:
    """Pega un PNG de la marca con el alto pedido; devuelve el ancho que ocupó."""
    img = Image.open(AQUI / "marca" / archivo).convert("RGBA")
    img = img.crop(img.getbbox())
    w = img.width * alto / img.height
    img = img.resize((round(w * K), round(alto * K)), Image.LANCZOS)
    fondo.paste(img, (round(x * K), round(y * K)), img)
    return w


def pastilla(fondo, rect, color: str, opacidad: float, radio: float = 8):
    x, y, w, h = (round(v * K) for v in rect)
    capa = Image.new("RGBA", fondo.size, (0, 0, 0, 0))
    ImageDraw.Draw(capa).rounded_rectangle((x, y, x + w, y + h), radio * K, fill=color + f"{round(opacidad * 255):02X}")
    return Image.alpha_composite(fondo.convert("RGBA"), capa).convert("RGB")


def encabezado(fondo, activa: str):
    ex, ey, ew, eh = d.ENCABEZADO
    for i, rect in enumerate(d.NAV):   # la pastilla de la página activa va antes que los textos
        if d.NOMBRES_DE_PAGINA[i] == activa:
            fondo = pastilla(fondo, rect, d.TARJETA, 0.85)
    dib = ImageDraw.Draw(fondo)
    x = ex + 18
    x += pegar(fondo, "globalaize-mark-dark-1024.png", x, ey + 13, 38) + 10
    x += pegar(fondo, "globalaize-wordmark-dark-1024.png", x, ey + 24, 16) + 30
    escribir(dib, x, ey + 9, d.TITULO, news(22), d.TINTA)
    escribir(dib, x, ey + 40, d.SUBTITULO, plex(400, 11), d.TENUE)
    for i, (nx, ny, nw, nh) in enumerate(d.NAV):
        nombre = d.NOMBRES_DE_PAGINA[i]
        es_activa = nombre == activa
        f = plex(600 if es_activa else 500, 12)
        escribir(dib, nx + (nw - ancho(nombre, f)) / 2, ny + 7, nombre, f, d.TINTA if es_activa else d.SECUNDARIO)
    return fondo


def leyenda(dib, p):
    x, y, w, _ = p["rect"]
    f = plex(400, 10.5)
    total = sum(ancho(nombre, f) + 27 for _, nombre in p["leyenda"])
    pisa_el_titulo = x + w - 16 - total < x + 16 + ancho(p["titulo"], news(17)) + 20
    fila = y + (35 if pisa_el_titulo else 17)      # si no entra junto al título, va en el renglón del contexto
    cx = x + w - 16
    for color, nombre in reversed(p["leyenda"]):
        cx -= ancho(nombre, f)
        escribir(dib, cx, fila, nombre, f, d.SECUNDARIO)
        cx -= 13
        dib.ellipse((cx * K, (fila + 3) * K, (cx + 8) * K, (fila + 11) * K), fill=color)
        cx -= 14
    if pisa_el_titulo and cx < x + 16 + ancho(p["contexto"], plex(400, 11)) + 12:
        print(f"  ojo: la leyenda de «{p['titulo']}» pisa el contexto")


def titulos(dib, p):
    x, y, w, h = p["rect"]
    if p["tipo"] == "kpi":
        escribir(dib, x + 16, y + 13, p["rotulo"].upper(), plex(600, 9.5), d.SECUNDARIO, espaciado=0.9)
        escribir(dib, x + 16, y + h - 21, p["nota"], plex(400, 10.5), d.TENUE)
        return
    escribir(dib, x + 16, y + 11, p["titulo"], news(17), d.TINTA)
    if p["contexto"]:
        f = plex(400, 11)
        if ancho(p["contexto"], f) > w - 32:
            print(f"  ojo: no entra en una línea el contexto de «{p['titulo']}» ({ancho(p['contexto'], f):.0f} px de {w - 32})")
        escribir(dib, x + 16, y + 36, p["contexto"], f, d.TENUE)
    if p["leyenda"]:
        leyenda(dib, p)
    if p["tipo"] == "texto":
        cy = y + 50
        for rotulo, parrafo in d.texto_del_metodo():
            escribir(dib, x + 16, cy, rotulo.upper(), plex(600, 9.5), d.TINTA, espaciado=0.9)
            cy += 17
            for linea in partir(parrafo, plex(400, 12.5), w - 36):
                escribir(dib, x + 16, cy, linea, plex(400, 12.5), d.SECUNDARIO)
                cy += 18
            cy += 12
        if cy > y + h - 8:
            print(f"  ojo: el texto de método se pasa del panel por {cy - (y + h - 8):.0f} px")


def pagina(pag: dict) -> Image.Image:
    rects = [d.ENCABEZADO] + [p["rect"] for p in pag["paneles"]]
    fondo = vidrio.pagina(rects, d.ANCHO, d.ALTO)
    fondo = encabezado(fondo, pag["nombre"])
    dib = ImageDraw.Draw(fondo)
    for p in pag["paneles"]:
        titulos(dib, p)
    escribir(dib, d.M + 4, 699, d.PIE, plex(400, 10), d.TENUE)
    return fondo


def main() -> None:
    SALIDA.mkdir(exist_ok=True)
    for pag in d.PAGINAS:
        print(pag["nombre"])
        pagina(pag).save(SALIDA / f"{pag['id']}.png", optimize=True)
    print("listo:", SALIDA)


if __name__ == "__main__":
    main()
