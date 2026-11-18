from functions.ingredients_functions import convertir_respuesta_shopper_a_lista, integrar_respuesta_shopper, procesar_pdf_boleta
from functions.gcp_functions import get_food_from_bigquery, update_products_in_bigquery
from functions.web_scrapper_functions import get_products_info
from app.agents.shopper_agent import shopper_agent_invoke
from app.state import PlannerState


def create_ingredients_list_node(state: PlannerState) -> PlannerState:
    # Procesar el PDF de la boleta para obtener la lista de ingredientes y el subtotal
    shopping_list, subtotal = procesar_pdf_boleta(state["receipt_path"])
    product_cantities = {int(item["codigo"]): item["cantidad"] for item in shopping_list}
    code_list = [item["codigo"] for item in shopping_list]

    # Obetener los productos desde la BBDD (evitar webscrapping para no sobrecargar el sitio web)
    food_list = get_food_from_bigquery(code_list)
    print(f"Productos obtenidos desde la BBDD: {len(food_list)}.")
    
    #Obtener los productos que no se encontraron en la BBDD desde la web
    if len(food_list) < len(code_list):
        codes_from_bbdd = [item["codigo"] for item in food_list]
        codes_not_used = [code for code in code_list if int(code) not in codes_from_bbdd]
        products_to_scrap = [{item["codigo"]: item["producto"]} for item in shopping_list if item["codigo"] in codes_not_used]    
        products_found, products_not_found = get_products_info(products_to_scrap, max_results=10)
        if len(products_found) > 0:
            # Agregar los productos obtenidos desde la web a la BBDD
            # Clasificar con LLM los productos obtenidos desde la web y agregarlos a la lista de ingredientes
            shopper_agent_response = shopper_agent_invoke(products_found, state["model_name"])
            products_analyzed = convertir_respuesta_shopper_a_lista(shopper_agent_response)
            if(update_products_in_bigquery(products_analyzed)):
                print("Productos agregados a la BBDD correctamente")
                integrar_respuesta_shopper(food_list, products_analyzed)
            else:
                print("Error al agregar productos a la BBDD")
            print(f"Productos obtenidos desde la web: {len(products_found)}.")
            print(f"Productos no obtenidos desde la web: {len(products_not_found)}.")

    # Fijar el estado con los ingredientes disponibles y sus cantidades, códigos y unidades de medida.
    state["ingredients_available"] = {item["producto"]: [item["cantidad_unidad"]*product_cantities[item["codigo"]],item["unidad_medida"]] for item in food_list if item["es_comida"]==True}
    return state
