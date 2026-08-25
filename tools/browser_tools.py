import urllib.parse
import webbrowser
import subprocess
import re
from tools.registry import register_tool

@register_tool(
    name="open_website",
    description="Opens a specific website URL in the user's default browser.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "url": {"type": "STRING", "description": "The URL to open, e.g. 'google.com'"}
        },
        "required": ["url"]
    }
)
def open_website(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    try:
        success = webbrowser.open(url)
        if not success:
            subprocess.Popen(f'start "" "{url}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Successfully opened {url}."
    except Exception as e:
        return f"Failed to open website: {e}"

@register_tool(
    name="search_youtube",
    description="Opens YouTube and searches for a specific video query.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "The exact search term to look for on YouTube."}
        },
        "required": ["query"]
    }
)
def search_youtube(query: str) -> str:
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded_query}"
    try:
        success = webbrowser.open(url)
        if not success:
            subprocess.Popen(f'start "" "{url}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Successfully searched YouTube for: {query}"
    except Exception as e:
        return f"Failed to search YouTube: {e}"

@register_tool(
    name="search_web",
    description="Searches the live internet (DuckDuckGo) to find facts or news.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "The search query"}
        },
        "required": ["query"]
    }
)
def search_web(query: str) -> str:
    try:
        import urllib.request
        encoded_query = urllib.parse.quote(query)
        req = urllib.request.Request(f"https://html.duckduckgo.com/html/?q={encoded_query}", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
        snippets = re.findall(r'class="result__snippet[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        clean_snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets]
        if clean_snippets:
            return f"Web Search Results for '{query}':\n- " + "\n- ".join(clean_snippets[:3])
        return "No internet results found."
    except Exception as e:
        return f"Web search error: {e}"
