import os
import datetime
import urllib.parse
import webbrowser
import time
import pyautogui
from AppOpener import open as open_app

# CRITICAL FIX: Disable failsafe so mouse resting in corner doesn't crash the tools!
pyautogui.FAILSAFE = False

def _minimize_jarvis():
    """Forces the Jarvis UI to minimize via WebSocket so the newly opened app gains absolute focus!"""
    try:
        import requests
        requests.get("http://localhost:8000/api/minimize", timeout=2)
        import time
        time.sleep(0.4) # Give UI time to minimize
    except:
        pass

def open_website(url):
    """Opens a specific URL directly."""
    if not url.startswith("http"):
        url = "https://" + url
    
    import webbrowser
    import time
    import pyautogui
    
    try:
        _minimize_jarvis() # Definitive focus fix
        pyautogui.press('alt') # Focus hack
        time.sleep(0.1)
        
        # webbrowser.open natively handles registry and brings to front better than 'start'
        success = webbrowser.open(url)
        
        if not success:
            import subprocess
            subprocess.Popen(f'start msedge "{url}"', shell=True)
            
        return f"Successfully opened {url}."
    except Exception as e:
        return "Failed to run terminal command."

def search_youtube(query):
    """Searches YouTube directly."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded_query}"
    
    import webbrowser
    import time
    import pyautogui
    
    try:
        _minimize_jarvis()
        pyautogui.press('alt')
        time.sleep(0.1)
        
        success = webbrowser.open(url)
        if not success:
            import subprocess
            subprocess.Popen(f'start msedge "{url}"', shell=True)
            
        return f"Successfully searched YouTube for: {query}"
    except Exception as e:
        return f"Failed to search YouTube: {e}"

def open_application(app_name):
    """Opens an application exactly like FatihMakes' Jarvis by visually typing in the start menu!"""
    try:
        import pyautogui
        import time
        # The true FatihMakes method: Visually open start menu and type it!
        pyautogui.hotkey('ctrl', 'esc') # 100% reliable way to open Start Menu
        time.sleep(1.0) # Wait for Start Menu to fully open and animate
        pyautogui.write(app_name, interval=0.08)
        time.sleep(0.8) # Wait for Windows Search to find it
        pyautogui.press('enter')
        
        # MINIMIZE AFTER LAUNCH: This forces Windows to give foreground focus to the newly launched app!
        time.sleep(1.5) 
        _minimize_jarvis()
        
        return f"Successfully executed visual start menu search for {app_name}."
    except Exception as e:
        return f"Failed to open {app_name}: {e}"

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

def get_system_status():
    """Checks the computer's CPU and RAM usage to report system health."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        return f"System Status: CPU Usage is {cpu}%, RAM Usage is {ram}%."
    except Exception as e:
        return "Failed to read system status."

import urllib.request
import xml.etree.ElementTree as ET

SEEN_NEWS = set()

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
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            if title not in SEEN_NEWS:
                headlines.append(f"- {title}")
                SEEN_NEWS.add(title)
            if len(headlines) >= 7: # Return top 7 unseen news
                break
            
        if not headlines:
            return f"No unread news found for {query}."
            
        return f"{topic_name}:\n" + "\n".join(headlines)
    except Exception as e:
        return f"Error fetching news: {e}"

import pyautogui
import time

def press_keys(keys):
    """Simulates pressing keyboard keys (e.g. 'ctrl+w', 'space', 'playpause')."""
    try:
        pyautogui.FAILSAFE = False
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
        pyautogui.FAILSAFE = False
        pyautogui.write(text, interval=0.05)
        return f"Successfully typed: {text}"
    except Exception as e:
        return f"Error typing text: {e}"

def take_screenshot():
    """Takes a screenshot of the screen so Jarvis can 'see' what the user is doing."""
    try:
        import pyautogui
        pyautogui.screenshot("screen.png")
        return "Screenshot taken successfully and attached to your visual sensors (I added it to the prompt)."
    except Exception as e:
        return f"Failed to take screenshot: {e}"

def search_web(query):
    """Searches the internet for information, such as finding Steam App IDs or general facts."""
    try:
        import urllib.request, urllib.parse, re
        encoded_query = urllib.parse.quote(query)
        req = urllib.request.Request(f"https://html.duckduckgo.com/html/?q={encoded_query}", headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
        # Extract snippets from DuckDuckGo Lite
        snippets = re.findall(r'class="result__snippet[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        clean_snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets]
        if clean_snippets:
            return f"Web Search Results for '{query}':\n- " + "\n- ".join(clean_snippets[:3])
        return "No internet results found."
    except Exception as e:
        return f"Web search error: {e}"

# ---------------------------------------------------------
# TOOL DISPATCHER MAP
# ---------------------------------------------------------
TOOL_MAP = {
    "open_website": open_website,
    "search_youtube": search_youtube,
    "open_application": open_application,
    "get_time_and_date": get_time_and_date,
    "run_terminal_command": run_terminal_command,
    "search_news": search_news,
    "press_keys": press_keys,
    "type_text": type_text,
    "get_system_status": get_system_status,
    "take_screenshot": take_screenshot,
    "search_web": search_web
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
                "description": "Opens ANY local Windows application, game, or software on the user's computer. Use this whenever the user asks you to open a program, game, or app. It has full OS access to open absolutely anything.",
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
            },
            {
                "name": "take_screenshot",
                "description": "Takes a screenshot of the user's computer screen and allows you to literally SEE what is on the screen right now. Use this whenever the user asks 'What is on my screen?', 'What am I looking at?', or asks for help with a real-life project on their computer.",
                "parameters": {
                    "type": "OBJECT"
                }
            },
            {
                "name": "search_web",
                "description": "Searches the live internet (DuckDuckGo) to find facts, news, or most importantly, Steam App IDs for installing games.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {
                            "type": "STRING",
                            "description": "The search query (e.g. 'Rainbow Six Siege steam app id' or 'Capital of France')"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    }
]
