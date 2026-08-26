import os
import time
import urllib.parse
import webbrowser
import subprocess
from tools.registry import register_tool

@register_tool(
    name="send_whatsapp_message",
    description="Sends a WhatsApp message to a specific contact. Opens WhatsApp, searches for the person, and sends the text.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "contact_name": {"type": "STRING", "description": "The exact name of the person in the user's contacts."},
            "message": {"type": "STRING", "description": "The message to send."}
        },
        "required": ["contact_name", "message"]
    }
)
def send_whatsapp_message(contact_name: str, message: str) -> str:
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        
        # Open WhatsApp (Windows App or Web depending on what's installed)
        # Using the start protocol for WhatsApp Windows app
        subprocess.Popen('start whatsapp:', shell=True)
        time.sleep(4) # Wait for WhatsApp to open
        
        # Shortcut to search in WhatsApp: Ctrl + F
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(1)
        
        # Type the contact name
        pyautogui.write(contact_name, interval=0.05)
        time.sleep(1.5)
        
        # Hit enter to select the top contact
        pyautogui.press('enter')
        time.sleep(1)
        
        # Type the message
        pyautogui.write(message, interval=0.02)
        time.sleep(0.5)
        
        # Hit enter to send
        pyautogui.press('enter')
        
        return f"Successfully sent WhatsApp message to {contact_name}."
    except Exception as e:
        return f"Failed to send WhatsApp message: {e}"

@register_tool(
    name="send_discord_message",
    description="Sends a message to Discord using desktop automation.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "channel_or_user": {"type": "STRING", "description": "Who to send it to."},
            "message": {"type": "STRING", "description": "The message."}
        },
        "required": ["channel_or_user", "message"]
    }
)
def send_discord_message(channel_or_user: str, message: str) -> str:
    # Desktop automation fallback
    try:
        import pyautogui
        # Bring Discord to front
        subprocess.Popen(f'C:\\Users\\{os.getlogin()}\\AppData\\Local\\Discord\\Update.exe --processStart Discord.exe', shell=True)
        time.sleep(3)
        
        # Ctrl+K to search channels/users in Discord
        pyautogui.hotkey('ctrl', 'k')
        time.sleep(1)
        pyautogui.write(channel_or_user, interval=0.05)
        time.sleep(1.5)
        pyautogui.press('enter')
        time.sleep(1)
        pyautogui.write(message, interval=0.02)
        pyautogui.press('enter')
        return f"Sent Discord message to {channel_or_user}."
    except Exception as e:
        return f"Failed to send Discord message: {e}"

@register_tool(
    name="spotify_search_and_play",
    description="Searches for a song/artist on Spotify desktop app and plays it.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "Song or artist to play."}
        },
        "required": ["query"]
    }
)
def spotify_search_and_play(query: str) -> str:
    try:
        import pyautogui
        # Open Spotify Desktop
        subprocess.Popen(f'C:\\Users\\{os.getlogin()}\\AppData\\Roaming\\Spotify\\Spotify.exe', shell=True)
        time.sleep(4)
        
        # Ctrl+L to focus search bar
        pyautogui.hotkey('ctrl', 'l')
        time.sleep(0.5)
        
        # Clear search bar (Ctrl+A then Delete)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')
        
        pyautogui.write(query, interval=0.05)
        time.sleep(2.5) # wait for search results to load
        
        # Tab down to the first result and hit Enter to play
        pyautogui.press('tab')
        time.sleep(0.1)
        pyautogui.press('tab')
        time.sleep(0.1)
        pyautogui.press('enter')
        return f"Now playing {query} on Spotify."
    except Exception as e:
        return f"Failed to play on Spotify: {e}"
