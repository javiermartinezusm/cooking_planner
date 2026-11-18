# cooking_planner
Recomendación de recetas y planificación de comidas mensuales con las boletas/listas de supermercados

## Inicio rapido con LangGraph

1. Instala dependencias:

```bash
pip install langgraph langchain langchain-google-genai python-dotenv
```

2. Asegurate de tener en tu `.env`:

```env
GEMINI_API_KEY=tu_api_key
MODEL_NAME=gemini-3.5-flash-lite
RECEIPT_PATH=boleta_jumbo.pdf
DRAW_GRAPH=0
```

3. Ejecuta:

```bash
python main.py
```

El flujo actual hace tres pasos:
- Lee la boleta PDF y arma inventario.
- Genera una receta simple priorizando inventario.
- Genera la lista de compra faltante.

Arquitectura modular:
- app/config.py: carga de variables de entorno.
- app/state.py: estado tipado del grafo.
- app/llm.py: fabrica de modelo.
- app/nodes/: nodos del flujo.
- app/graph.py: definicion del flujo LangGraph.
- main.py: punto de entrada.

## Tools para agente LLM

Se agregaron tools basadas en funciones de negocio:
- app/tools/food_tools.py
	- parse_receipt_inventory(receipt_path)
	- calculate_remaining_food(food_list, food_used)

Y un agente listo para tool-calling:
- app/agents/food_agent.py

Ejemplo rapido:

```python
from app.agents.food_agent import build_food_agent, invoke_food_agent
from app.config import load_settings

settings = load_settings()
agent = build_food_agent(settings["model_name"])

answer = invoke_food_agent(
		agent,
		"Lee la boleta en boleta_jumbo.pdf y dime el inventario total con subtotal.",
)
print(answer)
```
