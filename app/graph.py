from langgraph.graph import END, START, StateGraph

from app.nodes.inventory import create_food_list_node
from app.nodes.recipe import create_recipe_node
from app.nodes.planner import create_shopping_list_node
from app.state import PlannerState

def route_after_judge(state: PlannerState) -> str:
    if state.get("approved") or state.get("iterations", 0) >= state.get("max_iterations", 3):
        return "end"
    return "retry"

def build_graph(model_name: str):
    workflow = StateGraph(PlannerState)

    workflow.add_node("get_ingredients", create_food_list_node)
    workflow.add_node("create_recipe", lambda state: create_recipe_node(state, model_name))
    workflow.add_node("planner_judge", lambda state: create_shopping_list_node(state, model_name))
    
    workflow.add_edge(START, "get_ingredients")
    workflow.add_edge("get_ingredients", "planner_judge")
    workflow.add_conditional_edge(
        "planner_judge",
        route_after_judge,
        {
            "retry": "create_recipe",
            "end": END,
        },)

    return workflow.compile()
