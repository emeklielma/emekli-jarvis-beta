import os
import datetime
import urllib.parse
import subprocess
import pyautogui
import time
import urllib.request
import xml.etree.ElementTree as ET

# Original Tools
def open_website(url):
    if not url.startswith("http"): url = "https://" + url
    os.startfile(url)
    return f"Successfully opened {url}."

def search_youtube(query):
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded_query}"
    os.startfile(url)
    return f"Successfully searched YouTube for: {query}."

def open_application(app_name):
    app_map = {"notepad": "notepad", "calculator": "calc", "calc": "calc", "chrome": "chrome", "spotify": "spotify", "edge": "msedge", "explorer": "explorer"}
    cmd = app_map.get(app_name.lower())
    if cmd:
        os.system(f"start {cmd}")
        return f"Successfully opened {app_name}."
    else:
        os.system(f"start {app_name}")
        return f"Attempted to open {app_name} via Windows Start."

def get_time_and_date():
    now = datetime.datetime.now()
    return now.strftime("The current date is %B %d, %Y, and the time is %I:%M %p.")

def run_terminal_command(command):
    try:
        result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True, timeout=15)
        if result.returncode == 0: return f"Command executed successfully: {result.stdout.strip()}"
        else: return f"Command failed: {result.stderr.strip()}"
    except Exception as e:
        return f"Error executing command: {e}"

def press_keys(keys):
    try:
        keys_list = keys.split('+')
        if len(keys_list) == 1: pyautogui.press(keys_list[0].strip())
        else: pyautogui.hotkey(*[k.strip() for k in keys_list])
        return f"Successfully pressed: {keys}"
    except Exception as e: return f"Error pressing keys: {e}"

def type_text(text):
    try:
        pyautogui.write(text, interval=0.05)
        return f"Successfully typed: {text}"
    except Exception as e: return f"Error typing text: {e}"

TOOL_MAP = {
    "open_website": open_website,
    "search_youtube": search_youtube,
    "open_application": open_application,
    "get_time_and_date": get_time_and_date,
    "run_terminal_command": run_terminal_command,
    "press_keys": press_keys,
    "type_text": type_text
}

GEMINI_TOOLS = [{
    "functionDeclarations": [
        {"name": "open_website", "description": "Opens a website URL.", "parameters": {"type": "OBJECT", "properties": {"url": {"type": "STRING"}}, "required": ["url"]}},
        {"name": "search_youtube", "description": "Searches YouTube.", "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]}},
        {"name": "open_application", "description": "Opens a local Windows application.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING"}}, "required": ["app_name"]}},
        {"name": "get_time_and_date", "description": "Gets current time.", "parameters": {"type": "OBJECT"}},
        {"name": "run_terminal_command", "description": "Runs a PowerShell command.", "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING"}}, "required": ["command"]}},
        {"name": "press_keys", "description": "Simulates keyboard presses (e.g. ctrl+c).", "parameters": {"type": "OBJECT", "properties": {"keys": {"type": "STRING"}}, "required": ["keys"]}},
        {"name": "type_text", "description": "Simulates typing.", "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}}, "required": ["text"]}}
    ]
}]
