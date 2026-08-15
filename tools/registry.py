from typing import Callable, Dict, Any, List

TOOL_MAP: Dict[str, Callable] = {}
GEMINI_TOOLS: List[Dict[str, Any]] = [{"functionDeclarations": []}]

def register_tool(name: str, description: str, parameters: Dict[str, Any] = None):
    """
    Decorator to easily register a function as a tool for the LLM.
    """
    def decorator(func: Callable):
        TOOL_MAP[name] = func
        
        tool_schema = {
            "name": name,
            "description": description,
        }
        
        if parameters:
            tool_schema["parameters"] = parameters
        else:
            tool_schema["parameters"] = {"type": "OBJECT"}
            
        GEMINI_TOOLS[0]["functionDeclarations"].append(tool_schema)
        
        return func
    return decorator

def get_tool_map():
    return TOOL_MAP

def get_gemini_tools():
    return GEMINI_TOOLS
