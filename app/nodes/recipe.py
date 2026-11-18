from app.llm import get_llm
from app.state import PlannerState


def create_recipe_node(state: PlannerState, model_name: str) -> PlannerState:
    llm = get_llm(model_name)
    inventory_hint = ", ".join(state["food_list"].keys()) if state["food_list"] else "sin inventario detectado"
    prompt = (
        "Eres un asistente de cocina. Crea una receta simple en espanol para esta solicitud: "
        f"{state['user_request']}. "
        f"Prioriza usar estos ingredientes del hogar: {inventory_hint}. "
        "Incluye nombre del plato e instrucciones cortas."
    )
    recipe = llm.invoke(prompt).content
    state["recipe_idea"] = str(recipe)
    return state
