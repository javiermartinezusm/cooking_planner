from app.config import ensure_environment, load_settings
from app.graph import build_graph


def main() -> None:
    settings = load_settings()

    try:
        ensure_environment(settings)
    except RuntimeError as error:
        print(f"ERROR: {error}")
        return

    app = build_graph(settings["model_name"])
    if settings["draw_graph"] == "1":
        app.get_graph().draw_mermaid_png(output_file_path="mi_grafo.png")

    request = input("Que quieres cocinar hoy? ").strip() or "una cena saludable para 2 personas"
    result = app.invoke(
        {
            "user_request": request,
            "receipt_path": settings["default_receipt_path"],
            "food_list": {},
            "subtotal": 0,
            "recipe_idea": "",
            "shopping_list": "",
        }
    )

    print("\n=== Receta ===")
    print(result["recipe_idea"])
    print("\n=== Lista de Compra ===")
    print(result["shopping_list"])


if __name__ == "__main__":
    main()