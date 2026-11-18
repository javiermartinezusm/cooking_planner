import json
from langgraph.prebuilt import create_react_agent

from app.llm import get_llm
from app.tools.shopper_tools import get_shopper_tools
from app.prompts.shopper_prompt import SHOPPER_SYSTEM_PROMPT

def build_shopper_agent(model_name: str):
    llm = get_llm(model_name)
    return create_react_agent(
        llm,
        tools=get_shopper_tools(),
        prompt=SHOPPER_SYSTEM_PROMPT,
    )

def invoke_shopper_agent(agent, user_message: str) -> str:
    """
    Invokes the shopper agent with a user message and returns the agent's response.
    Note: This function is a placeholder and should be implemented with the actual logic to invoke the agent.

    Args:
        agent: The shopper agent to invoke.
        user_message (str): The user message to send to the agent.

    Returns:
        str: The agent's response.
    """
    result = agent.invoke({"messages": [("user", user_message)]})
    return str(result["messages"][-1].content)

def shopper_agent_invoke(products_scrapped: list[dict], model_name) -> str:
    shopper_agent = build_shopper_agent(model_name)
    shopper_user_prompt = f"""
        Procesa la siguiente lista de productos ({len(products_scrapped)} productos) en formato JSON:
        {json.dumps(products_scrapped, ensure_ascii=False, indent=2)}
    """
    result = shopper_agent.invoke({"messages": [("user", shopper_user_prompt)]})
    
    last_message = result["messages"][-1]
    content = last_message.content

    # Si Gemini devuelve una lista de bloques (texto, thinking, etc.)
    if isinstance(content, list):
        text_parts = [
            block["text"] for block in content 
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(text_parts)

    # Si ya es un string simple
    return str(content)