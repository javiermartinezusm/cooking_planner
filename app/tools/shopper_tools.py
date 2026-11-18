from pydantic import BaseModel, Field
from langchain_core.tools import tool

from functions.ingredients_functions import calculate_remaining_food, procesar_pdf_boleta


class ParseReceiptInput(BaseModel):
    receipt_path: str = Field(description="Ruta al PDF de la boleta")


@tool("parse_receipt_inventory", args_schema=ParseReceiptInput)
def parse_receipt_inventory(receipt_path: str) -> dict:
    """Lee una boleta PDF y devuelve inventario y subtotal."""
    products, subtotal = procesar_pdf_boleta(receipt_path)
    inventory = {item["producto"]: item["cantidad"] for item in products}
    return {
        "inventory": inventory,
        "subtotal": subtotal,
        "items_count": len(products),
    }


class RemainingFoodInput(BaseModel):
    food_list: dict[str, str, int] = Field(description="Inventario actual del hogar")
    food_used: dict[str, str, int] = Field(description="Cantidades usadas por receta o plan")


@tool("calculate_remaining_food", args_schema=RemainingFoodInput)
def calculate_remaining_food_tool(food_list: dict[str, int], food_used: dict[str, int]) -> dict:
    """Calcula inventario restante despues de usar ciertos ingredientes."""
    remaining = calculate_remaining_food(food_list, food_used)
    return {"remaining_food": remaining}


def get_shopper_tools() -> list:
    return [parse_receipt_inventory, calculate_remaining_food_tool]
