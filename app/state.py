from typing import TypedDict


class PlannerState(TypedDict):
    user_request: str
    ingredients_available: dict[str, list[int, str]]
    last_ingredients_used: dict[str, int]
    food_plan: dict[int, list[str, list[str], list[str]]]
    
