import json
from tools.registry import register_tool
from core import memory

@register_tool(
    name="remember_info",
    description="Saves important information about the user or system to persistent memory so you can recall it later (e.g. 'My name is John', 'I use VS Code').",
    parameters={
        "type": "OBJECT",
        "properties": {
            "key": {"type": "STRING", "description": "A short, unique key summarizing the information (e.g. 'user_name', 'favorite_editor')."},
            "value": {"type": "STRING", "description": "The actual detailed information to remember."},
            "category": {"type": "STRING", "description": "Optional category, e.g. 'general', 'preference', 'fact'."}
        },
        "required": ["key", "value"]
    }
)
def remember_info(key: str, value: str, category: str = "general") -> str:
    success = memory.save_memory(key, value, category)
    if success:
        return f"I have successfully remembered: {key} = {value}"
    return "Failed to save memory."

@register_tool(
    name="recall_info",
    description="Searches persistent memory for a specific topic, keyword, or fact.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "The search term to look for in memory."}
        },
        "required": ["query"]
    }
)
def recall_info(query: str) -> str:
    results = memory.search_memory(query)
    if results:
        formatted = "\n".join([f"- {r['key']}: {r['value']}" for r in results])
        return f"Found in memory:\n{formatted}"
    return "No memory found matching the query."
