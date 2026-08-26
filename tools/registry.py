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
            tool_schema["parameters"] = {"type": "OBJECT", "properties": {}}
            
        GEMINI_TOOLS[0]["functionDeclarations"].append(tool_schema)
        
        return func
    return decorator

def get_tool_map():
    return TOOL_MAP

def get_gemini_tools():
    return GEMINI_TOOLS

def _fix_schema_types(schema):
    if isinstance(schema, dict):
        if "type" in schema and isinstance(schema["type"], str):
            schema["type"] = schema["type"].lower()
        for k, v in schema.items():
            _fix_schema_types(v)
    elif isinstance(schema, list):
        for item in schema:
            _fix_schema_types(item)
    return schema

def get_openai_tools():
    import copy
    openai_tools = []
    for tool in GEMINI_TOOLS[0]["functionDeclarations"]:
        params = copy.deepcopy(tool.get("parameters", {"type": "object", "properties": {}}))
        _fix_schema_types(params)
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": params
            }
        })
    return openai_tools
