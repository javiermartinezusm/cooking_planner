import os

from dotenv import load_dotenv


def load_settings() -> dict[str, str]:
    load_dotenv()
    return {
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "model_name": os.getenv("MODEL_NAME", "gemini-3.5-flash-lite"),
        "default_receipt_path": os.getenv("RECEIPT_PATH", "boleta_jumbo.pdf"),
        "draw_graph": os.getenv("DRAW_GRAPH", "0"),
    }


def ensure_environment(settings: dict[str, str]) -> None:
    if not settings["api_key"]:
        raise RuntimeError("No se encontro GEMINI_API_KEY en el entorno.")
