import os
import time
from tools.registry import register_tool

@register_tool(
    name="read_clipboard",
    description="Reads the current text content from the user's clipboard.",
)
def read_clipboard() -> str:
    try:
        import pyperclip
        content = pyperclip.paste()
        if content:
            return f"Clipboard content:\n{content}"
        return "Clipboard is empty."
    except Exception as e:
        return f"Failed to read clipboard: {e}"

@register_tool(
    name="click_on_screen",
    description="Clicks at a specific coordinate or moves the mouse. Format for action: 'click x,y' or 'doubleclick x,y'.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "Action to perform, e.g. 'click 500,500'"}
        },
        "required": ["action"]
    }
)
def click_on_screen(action: str) -> str:
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        parts = action.lower().split()
        if len(parts) >= 2:
            cmd = parts[0]
            coords = parts[1].split(',')
            x, y = int(coords[0]), int(coords[1])
            if cmd == "click":
                pyautogui.click(x, y)
                return f"Clicked at {x}, {y}"
            elif cmd == "doubleclick":
                pyautogui.doubleClick(x, y)
                return f"Double clicked at {x}, {y}"
            elif cmd == "rightclick":
                pyautogui.rightClick(x, y)
                return f"Right clicked at {x}, {y}"
        return "Invalid command format. Use 'click x,y'"
    except Exception as e:
        return f"Failed to perform screen action: {e}"
