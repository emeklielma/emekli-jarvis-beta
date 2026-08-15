import os
import time
import subprocess
import json
import datetime
from tools.registry import register_tool
from core import app_launcher

@register_tool(
    name="open_application",
    description="Opens ANY local Windows application, game, system tool, or software on the user's computer. Fully supports Turkish and English names.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "app_name": {"type": "STRING", "description": "The name or query for the app to open (e.g. 'hesap makinesi', 'chrome', 'spotify')."}
        },
        "required": ["app_name"]
    }
)
def open_application(app_name: str) -> str:
    return app_launcher.open_app(app_name)

@register_tool(
    name="close_application",
    description="Closes or terminates a running Windows application or game.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "app_name": {"type": "STRING", "description": "The name of the app to close."}
        },
        "required": ["app_name"]
    }
)
def close_application(app_name: str) -> str:
    return app_launcher.close_app(app_name)

@register_tool(
    name="run_terminal_command",
    description="Runs a PowerShell terminal command on the user's computer.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "command": {"type": "STRING", "description": "The exact PowerShell command to run."}
        },
        "required": ["command"]
    }
)
def run_terminal_command(command: str) -> str:
    try:
        result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return f"Command executed successfully: {result.stdout.strip()}"
        return f"Command failed: {result.stderr.strip()}"
    except Exception as e:
        return f"Error executing command: {e}"

@register_tool(
    name="take_screenshot",
    description="Takes a screenshot of the user's computer screen to SEE what is on the screen right now."
)
def take_screenshot() -> str:
    try:
        import pyautogui
        try:
            pyautogui.screenshot("screen.png")
        except Exception:
            import mss
            with mss.mss() as sct:
                sct.shot(output="screen.png")
        return "Screenshot taken successfully and attached to your visual sensors."
    except Exception as e:
        return f"Failed to take screenshot: {e}"

@register_tool(
    name="control_media",
    description="Controls Windows media playback and volume.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "The action to perform: 'playpause', 'nexttrack', 'prevtrack', 'volumemute', 'volumeup', 'volumedown'"}
        },
        "required": ["action"]
    }
)
def control_media(action: str) -> str:
    try:
        import pyautogui
        valid_actions = ['playpause', 'nexttrack', 'prevtrack', 'volumemute', 'volumeup', 'volumedown']
        if action in valid_actions:
            if action in ['volumeup', 'volumedown']:
                pyautogui.press([action]*5)
            else:
                pyautogui.press(action)
            return f"Executed media control: {action}"
        return f"Invalid action: {action}"
    except Exception as e:
        return f"Failed to execute media control: {e}"

@register_tool(
    name="get_time_and_date",
    description="Retrieves the current real-world time and date for the user."
)
def get_time_and_date() -> str:
    now = datetime.datetime.now()
    return now.strftime("The current date is %B %d, %Y, and the time is %I:%M %p.")

@register_tool(
    name="press_keys",
    description="Simulates keyboard shortcut presses. For combinations, use '+', e.g. 'ctrl+t'.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "keys": {"type": "STRING", "description": "The key or key combination to press."}
        },
        "required": ["keys"]
    }
)
def press_keys(keys: str) -> str:
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        keys_list = keys.split('+')
        if len(keys_list) == 1:
            pyautogui.press(keys_list[0].strip())
        else:
            pyautogui.hotkey(*[k.strip() for k in keys_list])
        return f"Successfully pressed: {keys}"
    except Exception as e:
        return f"Error pressing keys: {e}"

@register_tool(
    name="type_text",
    description="Simulates typing text on the keyboard.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "text": {"type": "STRING", "description": "The text to type out."}
        },
        "required": ["text"]
    }
)
def type_text(text: str) -> str:
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.write(text, interval=0.05)
        return f"Successfully typed: {text}"
    except Exception as e:
        return f"Error typing text: {e}"
