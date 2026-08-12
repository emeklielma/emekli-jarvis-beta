import os
import datetime
import urllib.parse

def open_website(url):
    """Opens a specific URL in the default web browser."""
    if not url.startswith("http"):
        url = "https://" + url
    os.startfile(url)
    return f"Successfully opened {url}."

def search_youtube(query):
    """Searches YouTube for a specific query."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded_query}"
    os.startfile(url)
    return f"Successfully searched YouTube for: {query}."

def open_application(app_name):
    """Opens a local Windows application."""
    app_map = {
        "notepad": "notepad",
        "calculator": "calc",
        "calc": "calc",
        "chrome": "chrome",
        "spotify": "spotify",
        "edge": "msedge",
        "explorer": "explorer"
    }
    
    cmd = app_map.get(app_name.lower())
    if cmd:
        os.system(f"start {cmd}")
        return f"Successfully opened {app_name}."
    else:
        # Fallback to general start command
        os.system(f"start {app_name}")
        return f"Attempted to open {app_name} via Windows Start."

def get_time_and_date():
    """Returns the current date and time."""
    now = datetime.datetime.now()
    return now.strftime("The current date is %B %d, %Y, and the time is %I:%M %p.")

import subprocess

def run_terminal_command(command):
    """Runs a powershell command on the computer."""
    try:
        result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return f"Command executed successfully: {result.stdout.strip()}"
        else:
            return f"Command failed: {result.stderr.strip()}"
    except Exception as e:
        return f"Error executing command: {e}"

import urllib.request
import xml.etree.ElementTree as ET

def search_news(query="gündem"):
    """Searches Google News for a specific topic or gets general top news."""
    # Build the URL based on whether there's a specific search query
    import urllib.parse
    
    if query.lower() in ["gündem", "genel", "top", "latest"]:
        url = "https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr"
        topic_name = "Türkiye ve Dünya Gündemi"
    else:
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=tr&gl=TR&ceid=TR:tr"
        topic_name = f"'{query}' Hakkındaki Son Haberler"
        
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        headlines = []
        for item in root.findall('./channel/item')[:10]: # Increased to 10 news items
            title = item.find('title').text
            headlines.append(f"- {title}")
            
        if not headlines:
            return f"{query} hakkında yeni bir haber bulunamadı."
            
        return f"{topic_name}:\n" + "\n".join(headlines)
    except Exception as e:
        return f"Haberler alınırken bir hata oluştu: {e}"

import pyautogui
import time

def press_keys(keys):
    """Simulates pressing keyboard keys (e.g. 'ctrl+w', 'space', 'playpause')."""
    try:
        keys_list = keys.split('+')
        if len(keys_list) == 1:
            pyautogui.press(keys_list[0].strip())
        else:
            pyautogui.hotkey(*[k.strip() for k in keys_list])
        return f"Successfully pressed: {keys}"
    except Exception as e:
        return f"Error pressing keys: {e}"

def type_text(text):
    """Types out text simulating a keyboard."""
    try:
        pyautogui.write(text, interval=0.05)
        return f"Successfully typed: {text}"
    except Exception as e:
        return f"Error typing text: {e}"

# This maps the tool names from Gemini to the actual Python functions
TOOL_MAP = {
    "open_website": open_website,
    "search_youtube": search_youtube,
    "open_application": open_application,
    "get_time_and_date": get_time_and_date,
    "run_terminal_command": run_terminal_command,
    "search_news": search_news,
    "press_keys": press_keys,
    "type_text": type_text
}

# The JSON schema passed to Gemini to teach it about our tools
GEMINI_TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": "open_website",
                "description": "Opens a specific website URL in the user's default browser.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "url": {
                            "type": "STRING",
                            "description": "The URL to open, e.g. 'google.com', 'wikipedia.org'"
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "search_youtube",
                "description": "Opens YouTube and searches for a specific video query. Use this whenever the user asks to play a video, watch something on YouTube, or search YouTube.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {
                            "type": "STRING",
                            "description": "The exact search term to look for on YouTube."
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "open_application",
                "description": "Opens a local Windows application on the user's computer (e.g. calculator, notepad, spotify).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "app_name": {
                            "type": "STRING",
                            "description": "The simple name of the app to open (e.g. 'notepad', 'calculator')."
                        }
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "get_time_and_date",
                "description": "Retrieves the current real-world time and date for the user.",
                "parameters": {
                    "type": "OBJECT"
                }
            },
            {
                "name": "run_terminal_command",
                "description": "Runs a PowerShell terminal command on the user's computer. Use this to fully control the computer (e.g. adjust volume, shutdown, open files, run scripts, create folders, check system stats).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "command": {
                            "type": "STRING",
                            "description": "The exact PowerShell command to run."
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "search_news",
                "description": "Searches for the latest news on a specific topic (e.g. 'teknoloji', 'amerika', 'spor', 'dünya') or general news (query='gündem'). Use this to fetch real-world current events.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {
                            "type": "STRING",
                            "description": "The topic to search for, or 'gündem' for general world/country news."
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "press_keys",
                "description": "Simulates keyboard shortcut presses. Extremely useful for controlling tabs (ctrl+w, ctrl+t), media (playpause, nexttrack, prevtrack, volumeup, volumedown, volumemute), scrolling (pagedown, pageup) or hitting 'enter'. For combinations, use '+', e.g. 'ctrl+t'.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "keys": {
                            "type": "STRING",
                            "description": "The key or key combination to press. Examples: 'space', 'playpause', 'ctrl+w', 'ctrl+t', 'enter', 'f'"
                        }
                    },
                    "required": ["keys"]
                }
            },
            {
                "name": "type_text",
                "description": "Simulates typing text on the keyboard. Useful after opening a new tab or clicking on a search bar.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "text": {
                            "type": "STRING",
                            "description": "The text to type out."
                        }
                    },
                    "required": ["text"]
                }
            }
        ]
    }
]
