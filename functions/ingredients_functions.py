import json
import re

import pymupdf as fitz

def extraer_productos_boleta(texto_boleta: str) -> list[dict]:
    """
    Extrae los productos de un texto de boleta y calcula el subtotal.

    Args:
        texto_boleta (str): Texto completo de la boleta.
    Returns:
        tuple: Una tupla con la lista de productos y el subtotal.
    """
    productos = []
    cantidad_actual = 1
    subtotal = 0

    # Patrón 1: Detecta líneas de cantidad múltiple (ej: "2 X $1.350")
    patron_cantidad = re.compile(r"^\s*(\d+)\s+X\s+\$[\d.,]+\s*$", re.IGNORECASE)
    
    # Patrón 2: Detecta código de barras (8 a 14 dígitos) + nombre + precio final
    patron_producto = re.compile(r"^\s*(\d{8,14})\s+(.+?)\s+([\d.,]+)\s*$")

    for linea in texto_boleta.splitlines():
        # Ignoramos líneas de descuentos o promociones
        if "TMP OFERTA" in linea or "TMP DESCUENTO" in linea:
            continue

        # 1. Revisamos si la línea indica cantidad > 1 para el siguiente producto
        match_cant = patron_cantidad.match(linea)
        if match_cant:
            cantidad_actual = int(match_cant.group(1))
            continue

        # 2. Revisamos si es una línea de producto
        match_prod = patron_producto.match(linea)
        if match_prod:
            codigo = match_prod.group(1)
            nombre = match_prod.group(2).strip()
            precio_total = int(match_prod.group(3).replace(".", ""))

            productos.append({
                "codigo": codigo,
                "producto": nombre,
                "cantidad": cantidad_actual,
                "precio_bruto": precio_total
            })
            subtotal += precio_total

            # Reiniciamos la cantidad a 1 para el siguiente producto
            cantidad_actual = 1

    return productos, subtotal

def procesar_pdf_boleta(ruta_pdf: str):
    """
    Manda a procesar el PDF de la boleta y extrae los productos y subtotal.
    Args:
        ruta_pdf (str): Ruta al archivo PDF de la boleta.
    Returns:
        tuple: Una tupla con la lista de productos y el subtotal.
    """
    texto_completo = ""
    with fitz.open(ruta_pdf) as doc:
        for pagina in doc:
            texto_completo += pagina.get_text("text") + "\n"
    return extraer_productos_boleta(texto_completo)

def convertir_respuesta_shopper_a_lista(respuesta) -> list[dict]:
    """
    Convierte la respuesta del agente shopper a una lista de diccionarios normalizados.
    Acepta JSON puro, cadenas con texto extra, bloques markdown ```json ... ``` y dict/list ya parseados.
    """
    if respuesta is None:
        print("La respuesta del agente shopper es None. No se puede convertir a lista.")
        return []

    if isinstance(respuesta, list):
        datos = respuesta
    elif isinstance(respuesta, dict):
        datos = [respuesta]
    elif isinstance(respuesta, str):
        texto = respuesta.strip()
        if not texto:
            return []

        bloque = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", texto, flags=re.DOTALL | re.IGNORECASE)
        if bloque:
            texto = bloque.group(1)
        elif not (texto.startswith("[") or texto.startswith("{")):
            extraido = re.search(r"(\[.*\]|\{.*\})", texto, flags=re.DOTALL)
            if extraido:
                texto = extraido.group(1)

        try:
            datos = json.loads(texto)
        except json.JSONDecodeError:
            try:
                datos = json.loads(texto.replace("'", '"'))
            except json.JSONDecodeError:
                return []

        if isinstance(datos, dict):
            datos = [datos]
        elif not isinstance(datos, list):
            return []
    else:
        return []

    productos = []
    for item in datos:
        if not isinstance(item, dict):
            continue

        codigo = item.get("codigo")
        producto = item.get("producto") or item.get("nombre") or ""
        unidad = item.get("unidad_medida") or item.get("unidad") or "un"
        cantidad = item.get("cantidad_unidad", item.get("cantidad", 1))
        es_comida = item.get("es_comida", True)

        try:
            codigo = int(codigo)
        except (TypeError, ValueError):
            continue

        try:
            cantidad = float(cantidad)
        except (TypeError, ValueError):
            cantidad = 1.0

        productos.append({
            "codigo": codigo,
            "producto": str(producto).strip(),
            "unidad_medida": str(unidad).strip() or "un",
            "cantidad_unidad": cantidad,
            "es_comida": bool(es_comida),
        })

    return productos


def integrar_respuesta_shopper(food_list: list[dict], respuesta) -> list[dict]:
    """Agrega los productos parseados desde la respuesta del agente a la lista actual."""
    productos = convertir_respuesta_shopper_a_lista(respuesta)
    return food_list + productos


def calculate_remaining_food(food_list: dict, food_used: dict) -> dict:
    """
    Calculate the remaining amount of food after usage.

    Args:
        food_list (dict): A dictionary containing the initial amount of each food item.
        food_used (dict): A dictionary containing the amount of each food item that has been used.

    Returns:
        food_remaining (dict): A dictionary containing the remaining amount of each food item.
    """
    food_remaining = {}
    for name, quantity in food_used.items():
        initial_amount = food_list.get(name, 0)
        if initial_amount == 0:
            raise ValueError(f"{name} is not in the initial food list. Please check your input.")
        used_amount = quantity
        remaining_amount = initial_amount - used_amount
        if remaining_amount < 0:
            raise ValueError(f"Used amount for {name} exceeds initial amount. Try again or stop planning.")
        elif remaining_amount > 0:
            food_remaining[name] = remaining_amount
        else:
            continue 
    return food_remaining
