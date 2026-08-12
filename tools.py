import webbrowser
import os
import datetime
import urllib.parse

def open_website(url):
    """Opens a specific URL in the default web browser."""
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Successfully opened {url}."

def search_youtube(query):
    """Searches YouTube for a specific query."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded_query}"
    webbrowser.open(url)
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

# This maps the tool names from Gemini to the actual Python functions
TOOL_MAP = {
    "open_website": open_website,
    "search_youtube": search_youtube,
    "open_application": open_application,
    "get_time_and_date": get_time_and_date
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
            }
        ]
    }
]
