import os
import datetime
import urllib.parse
import webbrowser
import time
import pyautogui
import app_launcher

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
    """Opens any Windows application, game, or software using the advanced app_launcher engine."""
    try:
        return app_launcher.open_app(app_name)
    except Exception as e:
        return f"Failed to open {app_name}: {e}"

def close_application(app_name):
    """Closes or terminates a running Windows application or game."""
    try:
        return app_launcher.close_app(app_name)
    except Exception as e:
        return f"Failed to close {app_name}: {e}"

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
    """Takes a screenshot of the user's computer screen and allows you to literally SEE what is on the screen right now."""
    try:
        import pyautogui
        try:
            pyautogui.screenshot("screen.png")
        except Exception as e:
            print(f"PyAutoGUI failed ({e}), falling back to mss...")
            import mss
            with mss.mss() as sct:
                sct.shot(output="screen.png")
                
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

def control_media(action):
    """Controls media playback and volume."""
    try:
        import pyautogui
        valid_actions = ['playpause', 'nexttrack', 'prevtrack', 'volumemute', 'volumeup', 'volumedown']
        if action in valid_actions:
            if action in ['volumeup', 'volumedown']:
                pyautogui.press([action]*5)
            else:
                pyautogui.press(action)
            return f"Executed media control: {action}"
        else:
            return f"Invalid action: {action}. Must be one of {valid_actions}"
    except Exception as e:
        return f"Failed to execute media control: {e}"

def get_weather():
    """Gets the current local weather using IP geolocation."""
    try:
        import requests
        r = requests.get('https://wttr.in/?format=j1', timeout=10).json()
        temp = r['current_condition'][0]['temp_C']
        desc = r['current_condition'][0]['weatherDesc'][0]['value']
        location = r['nearest_area'][0]['areaName'][0]['value']
        return f"The weather in {location} is currently {temp}°C and {desc}."
    except Exception as e:
        return f"Failed to get weather: {e}"

def send_notification(title, message):
    """Sends a native Windows popup notification."""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=5, threaded=True)
        return "Notification sent successfully."
    except Exception as e:
        return f"Failed to send notification: {e}"

def trigger_protocol(protocol_name):
    """Triggers a special Jarvis UI protocol."""
    try:
        import requests
        requests.get(f"http://localhost:8000/api/protocol/{protocol_name}", timeout=2)
        return f"Protocol '{protocol_name}' activated."
    except Exception as e:
        return f"Failed to activate protocol: {e}"

import json

def remember_fact(fact):
    """Saves a permanent core memory/fact about the user."""
    try:
        memory_file = "core_memory.json"
        memories = []
        if os.path.exists(memory_file):
            with open(memory_file, 'r', encoding='utf-8') as f:
                memories = json.load(f)
        
        if fact not in memories:
            memories.append(fact)
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memories, f, indent=4, ensure_ascii=False)
            return f"Successfully committed to core memory: {fact}"
        return f"I already know this fact: {fact}"
    except Exception as e:
        return f"Error saving memory: {e}"

def delete_fact(fact):
    """Deletes a fact from core memory."""
    try:
        memory_file = "core_memory.json"
        if os.path.exists(memory_file):
            with open(memory_file, 'r', encoding='utf-8') as f:
                memories = json.load(f)
            
            if fact in memories:
                memories.remove(fact)
                with open(memory_file, 'w', encoding='utf-8') as f:
                    json.dump(memories, f, indent=4, ensure_ascii=False)
                return f"Successfully deleted from core memory: {fact}"
        return f"Fact not found in core memory."
    except Exception as e:
        return f"Error deleting memory: {e}"

# ---------------------------------------------------------
# TOOL DISPATCHER MAP
# ---------------------------------------------------------
TOOL_MAP = {
    "open_website": open_website,
    "search_youtube": search_youtube,
    "open_application": open_application,
    "close_application": close_application,
    "get_time_and_date": get_time_and_date,
    "run_terminal_command": run_terminal_command,
    "search_news": search_news,
    "press_keys": press_keys,
    "type_text": type_text,
    "get_system_status": get_system_status,
    "take_screenshot": take_screenshot,
    "search_web": search_web,
    "control_media": control_media,
    "get_weather": get_weather,
    "send_notification": send_notification,
    "trigger_protocol": trigger_protocol,
    "remember_fact": remember_fact,
    "delete_fact": delete_fact
}

# The JSON schema passed to Gemini to teach it about our tools
GEMINI_TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": "control_media",
                "description": "Controls Windows media playback and volume. Use this whenever the user asks to change the volume or control music.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "action": {
                            "type": "STRING",
                            "description": "The action to perform. Valid options are: 'playpause', 'nexttrack', 'prevtrack', 'volumemute', 'volumeup', 'volumedown'"
                        }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "get_weather",
                "description": "Gets the current local weather and temperature based on the user's location.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            },
            {
                "name": "send_notification",
                "description": "Sends a native Windows desktop toast notification to the user. Use this to alert the user of finished background tasks or important warnings.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {
                            "type": "STRING",
                            "description": "The title of the notification."
                        },
                        "message": {
                            "type": "STRING",
                            "description": "The message body of the notification."
                        }
                    },
                    "required": ["title", "message"]
                }
            },
            {
                "name": "trigger_protocol",
                "description": "Triggers a special visual protocol on the Jarvis UI. Use this when the user asks for 'lockdown' or 'house party' mode.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "protocol_name": {
                            "type": "STRING",
                            "description": "The protocol to trigger. Valid options: 'lockdown', 'party', 'normal', 'decryption', 'destruct', 'satellite'"
                        }
                    },
                    "required": ["protocol_name"]
                }
            },
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
                "description": "Opens ANY local Windows application, game, system tool, or software on the user's computer. Fully supports Turkish and English names (e.g. 'hesap makinesi', 'calculator', 'not defteri', 'notepad', 'ayarlar', 'settings', 'görev yöneticisi', 'task manager', 'spotify', 'chrome', 'discord', 'steam', 'valorant', 'tlauncher', 'roblox', 'terminal', 'paint'). It has full OS access to open absolutely anything.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "app_name": {
                            "type": "STRING",
                            "description": "The name or query for the app to open (in Turkish or English, e.g. 'hesap makinesi', 'chrome', 'spotify', 'settings')."
                        }
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "close_application",
                "description": "Closes or terminates a running Windows application or game (e.g. 'spotify', 'chrome', 'hesap makinesi', 'notepad').",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "app_name": {
                            "type": "STRING",
                            "description": "The name of the app to close."
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
            },
            {
                "name": "remember_fact",
                "description": "Saves a permanent fact about the user or the environment to your core memory database. Use this WHENEVER the user tells you a preference, their name, or something you should remember for the future.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "fact": {
                            "type": "STRING",
                            "description": "The concise fact to remember (e.g. 'The user likes the color red', 'The user's name is John')"
                        }
                    },
                    "required": ["fact"]
                }
            },
            {
                "name": "delete_fact",
                "description": "Deletes a fact from your core memory database if it is no longer true.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "fact": {
                            "type": "STRING",
                            "description": "The exact fact string to delete."
                        }
                    },
                    "required": ["fact"]
                }
            }
        ]
    }
]
