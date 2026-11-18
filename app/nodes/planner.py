from app.llm import get_llm
from app.state import PlannerState


def create_planner_node(state: PlannerState, model_name: str) -> PlannerState:
    llm = get_llm(model_name)
    prompt = (
        "Con esta receta, crea solo una lista de compra corta y clara en espanol. "
        "Si un ingrediente ya esta en el inventario, no lo repitas:\n\n"
        f"Inventario: {state['food_list']}\n\n"
        f"Receta: {state['recipe_idea']}"
    )
    shopping_list = llm.invoke(prompt).content
    state["shopping_list"] = str(shopping_list)
    return state
