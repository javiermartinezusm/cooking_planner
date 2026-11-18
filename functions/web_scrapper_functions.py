"""Búsqueda de productos en Jumbo.cl y extracción del GTIN desde la página de cada producto."""
import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.jumbo.cl"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CL,es;q=0.9",
}

# Nombres de campo bajo los que puede venir el código en JSON-LD / JSON embebido / meta tags.
CLAVES_GTIN = {"gtin", "gtin", "gtin8", "gtin12", "gtin13", "gtin14", "ean", "ean13", "barcode"}

_RE_CODIGO = re.compile(r"^\d{8,14}$")
# Clave de JSON (también escapada, como en los payloads de Next.js: \"gtin\":\"123...\")
_RE_JSON_CLAVE = re.compile(
    r"""\\?["'](gtin|gtin\d{0,2}|ean\d{0,2}|barcode)\\?["']\s*:\s*\\?["']?(\d{8,14})""",
    re.IGNORECASE,
)
# Etiqueta visible en la ficha: "GTIN 7801234567890" / "GTIN: 7801234567890"
_RE_TEXTO = re.compile(r"\b(?:GTIN|GTIN|EAN)\b\s*[:\-]?\s*(\d{8,14})\b", re.IGNORECASE)
_RE_SKU = re.compile(r"C[oó]digo:\s*(\d+)")


def _crear_sesion() -> requests.Session:
    sesion = requests.Session()
    sesion.headers.update(HEADERS)
    reintentos = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    sesion.mount("https://", HTTPAdapter(max_retries=reintentos))
    return sesion


def _descargar(sesion: requests.Session, url: str) -> str | None:
    try:
        respuesta = sesion.get(url, timeout=20)
        if respuesta.status_code != 200:
            return None
        return respuesta.text
    except requests.RequestException:
        return None


def _es_url_producto(url: str) -> bool:
    """Las páginas de producto de Jumbo terminan en '/p' (ej: /lavalozas-teza-1927149/p)."""
    partes = urlparse(url)
    if not partes.netloc.endswith("jumbo.cl"):
        return False
    ruta = partes.path.rstrip("/")
    return ruta.endswith("/p") and len(ruta) > 2


def _urls_de_productos(html: str, maximo: int, ignore: int) -> list[str]:
    """Extrae URLs únicas de productos desde el HTML de la página de resultados."""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for enlace in soup.find_all("a", href=True):
        absoluta = urljoin(BASE_URL, enlace["href"])
        partes = urlparse(absoluta)
        limpia = urlunparse((partes.scheme, partes.netloc, partes.path, "", "", ""))
        if _es_url_producto(limpia) and limpia not in urls:
            urls.append(limpia)
            if len(urls) >= maximo+ignore:
                break
    return urls[ignore:ignore + maximo]


def _normalizar_codigo(valor) -> str | None:
    texto = str(valor).strip()
    return texto if _RE_CODIGO.match(texto) else None


def _normalizar_gtin(valor) -> str | None:
    """Normaliza un GTIN a un valor numérico limpio y usable para comparación."""
    if valor is None:
        return None
    texto = re.sub(r"\D", "", str(valor).strip())
    if len(texto) in {8, 12, 13, 14}:
        return texto
    return None


def _buscar_en_json(nodo) -> str | None:
    """Recorre un JSON (dict/list) buscando una clave tipo gtin/gtin/ean con un código válido."""
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave.lower() in CLAVES_GTIN:
                codigo = _normalizar_codigo(valor)
                if codigo:
                    return codigo
        for valor in nodo.values():
            codigo = _buscar_en_json(valor)
            if codigo:
                return codigo
    elif isinstance(nodo, list):
        for item in nodo:
            codigo = _buscar_en_json(item)
            if codigo:
                return codigo
    return None


def _producto_json_ld(soup: BeautifulSoup) -> dict | None:
    """Devuelve el nodo schema.org 'Product' del JSON-LD (que puede venir como lista de nodos)."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            datos = json.loads(tag.string or tag.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        nodos = datos if isinstance(datos, list) else datos.get("@graph", [datos])
        for nodo in nodos:
            if not isinstance(nodo, dict):
                continue
            tipo = nodo.get("@type")
            if tipo == "Product" or (isinstance(tipo, list) and "Product" in tipo):
                return nodo
    return None


def _extraer_gtin(html: str, sku: str | None = None) -> tuple[str | None, str | None]:
    """Busca el GTIN en la metadata/HTML de la página. Devuelve (gtin, fuente donde se encontró)."""
    soup = BeautifulSoup(html, "html.parser")

    # 1) JSON-LD (schema.org Product: gtin, gtin13, etc.)
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            datos = json.loads(tag.string or tag.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        codigo = _buscar_en_json(datos)
        if codigo:
            return codigo, "json-ld"

    # 2) Meta tags / microdatos (itemprop="gtin13", <meta name="gtin" content="...">)
    for tag in soup.find_all(["meta", "span", "div", "td", "li"], attrs={"itemprop": True}):
        if any(k in tag["itemprop"].lower() for k in ("gtin", "gtin", "ean")):
            codigo = _normalizar_codigo(tag.get("content") or tag.get_text(strip=True))
            if codigo:
                return codigo, "microdatos"
    for tag in soup.find_all("meta"):
        clave = (tag.get("name") or tag.get("property") or "").lower()
        if any(k in clave for k in ("gtin", "gtin", "ean")):
            codigo = _normalizar_codigo(tag.get("content", ""))
            if codigo:
                return codigo, "meta"

    # 3) Texto visible (ficha "Características": etiqueta GTIN y su valor)
    for sucio in soup(["script", "style", "noscript"]):
        sucio.extract()
    texto = soup.get_text("\n", strip=True)
    coincidencia = _RE_TEXTO.search(texto)
    if coincidencia:
        return coincidencia.group(1), "texto-visible"

    # 4) JSON embebido en scripts (__NEXT_DATA__ o payload RSC de Next.js).
    #    Estos payloads pueden incluir también productos relacionados, así que si hay
    #    varios candidatos se prefiere el más cercano al código (SKU) del producto.
    candidatos = [(m.start(), m.group(2)) for m in _RE_JSON_CLAVE.finditer(html)]
    if candidatos:
        if sku and len({c for _, c in candidatos}) > 1:
            posiciones_sku = [m.start() for m in re.finditer(re.escape(sku), html)]
            if posiciones_sku:
                _, codigo = min(
                    candidatos,
                    key=lambda c: min(abs(c[0] - p) for p in posiciones_sku),
                )
                return codigo, "json-embebido (cercano al SKU)"
        return candidatos[0][1], "json-embebido"

    return None, None


def _normalizar_additional_property(adicional):
    """Normaliza additionalProperty para devolver solo una lista de dicts con nombre/valor."""
    if not isinstance(adicional, list):
        return []

    resultado = []
    for item in adicional:
        if isinstance(item, dict):
            nombre = item.get("name")
            valor = item.get("value")
            if nombre or valor:
                resultado.append({
                    "name": nombre,
                    "value": valor,
                })
    return resultado


def obtener_datos_producto(
    sesion: requests.Session, url: str, dir_debug: str | None = None
) -> dict:
    """Abre la página de un producto y devuelve solo los campos relevantes para el agente."""
    html = _descargar(sesion, url)
    if html is None:
        return {
            "titulo": "",
            "gtin": None,
            "descripcion": None,
            "additionalProperty": [],
        }

    soup = BeautifulSoup(html, "html.parser")
    producto_ld = _producto_json_ld(soup) or {}

    og_titulo = soup.find("meta", property="og:title")
    if producto_ld.get("name"):
        titulo = producto_ld["name"].strip()
    elif og_titulo and og_titulo.get("content"):
        titulo = og_titulo["content"].replace("| Jumbo.cl", "").strip()
    else:
        h1 = soup.find("h1")
        titulo = h1.get_text(" ", strip=True) if h1 else ""

    descripcion = producto_ld.get("description")
    if not descripcion:
        descripcion_tag = soup.find("meta", attrs={"name": "description"})
        descripcion = descripcion_tag.get("content") if descripcion_tag else None

    gtin, _ = _extraer_gtin(html)

    if gtin is None and dir_debug:
        carpeta = Path(dir_debug)
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / f"{re.sub(r'[^a-zA-Z0-9_-]','_', titulo)[:80] or 'producto'}.html").write_text(html, encoding="utf-8")

    additional_property = producto_ld.get("additionalProperty")
    additional_property = _normalizar_additional_property(additional_property)

    return {
        "titulo": titulo,
        "gtin": gtin,
        "descripcion": descripcion,
        "additionalProperty": additional_property,
    }


def buscar_producto_por_nombre(
    nombre_producto: str,
    max_resultados: int = 5,
    pausa_segundos: float = 0.5,
    dir_debug: str | None = None,
    gtin: str | None = None,
    max_paginas: int = 3,
) -> list[dict]:
    """Busca un productoen Jumbo.cl y, si se indica un GTIN, sigue recorriendo resultados hasta encontrarlo."""
    nombre_limpio = (nombre_producto or "").strip()
    gtin_limpio = _normalizar_gtin(gtin)

    if not nombre_limpio and not gtin_limpio:
        raise ValueError("Debes indicar un nombre de producto o un GTIN.")

    sesion = _crear_sesion()
    resultados: list[dict] = []
    urls_vistas: set[str] = set()

    max_paginas = max(1, int(max_paginas))
    max_resultados = max(1, int(max_resultados))

    for pagina in range(1, max_paginas + 1):
        query = quote_plus(nombre_limpio or gtin_limpio or "")
        url_busqueda = f"{BASE_URL}/busqueda?ft={query}"
        if pagina > 1:
            url_busqueda = f"{url_busqueda}&PageNumber={pagina}"

        html_busqueda = _descargar(sesion, url_busqueda)
        if html_busqueda is None:
            break

        ignore = len(urls_vistas) if gtin_limpio else 0
        urls = _urls_de_productos(html_busqueda, max_resultados+ignore, ignore=ignore)
        if not urls:
            break

        for url in urls:
            if url in urls_vistas:
                continue
            urls_vistas.add(url)

            producto = obtener_datos_producto(sesion, url, dir_debug)
            resultados.append(producto)

            if gtin_limpio and producto.get("gtin") == gtin_limpio:
                return [producto]

            time.sleep(pausa_segundos)

        if gtin_limpio and len(resultados) >= max_resultados:
            # Si ya revisamos varios candidatos y no aparecio el GTIN, seguimos
            # para no cortar demasiado pronto en búsquedas con muchos resultados.
            continue

    return resultados



def buscar_producto_por_gtin(gtin_producto: str, nombre_producto: str, max_resultados: int = 5, max_paginas: int = 10) -> dict | None:
    found = 0
    resultados = buscar_producto_por_nombre(nombre_producto,
                                            gtin=gtin_producto,
                                            max_resultados=max_resultados,
                                            max_paginas=max_paginas
                                            )
    for producto in resultados:
        if producto["gtin"] == gtin_producto:
            print(producto)
            found += 1
            return producto
    if found == 0:
        print(f"No se encontró el producto con GTIN {gtin_producto}.\nEn los {max_resultados*max_paginas} resultados obtenidos.")
    return {}

def get_products_info(products_to_scrap: list[dict], max_results: int = 5, max_pages: int = 10) -> tuple[list[dict], list[tuple]]:
    """
    Funcion que toma una lista de diccionarios con productos (cada diccionario contiene 'codigo' y 'producto') y busca información de cada producto en Jumbo.cl.
    Args:
        products_to_scrap (list[dict]): Lista de diccionarios con productos a buscar
        max_results (int): Número máximo de resultados a obtener por producto
        max_pages (int): Número máximo de páginas a recorrer por producto
    Returns:
        list[dict]: Lista de diccionarios con la información de los productos encontrados
        list[tuple]: Lista de tuplas con los productos que no se encontraron
    
    """
    products_found = []
    products_not_found = []
    for product in products_to_scrap:
        for code, name in product.items():
            product_info = buscar_producto_por_gtin(code, name, max_resultados=max_results, max_paginas=max_pages)
            if product_info:
                products_found.append(product_info)
            else:
                products_not_found.append((code, name))
                print(f"No se encontró información para el producto con código {code} y nombre {name}. Revisar boleta o agregar manualmente.")

    return products_found, products_not_found