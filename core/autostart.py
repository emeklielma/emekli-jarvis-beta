import os
import sys
import winreg

APP_NAME = "JarvisAI"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

def get_server_start_command():
    # Use pythonw.exe to run without a console window
    python_exe = sys.executable.replace("python.exe", "pythonw.exe")
    server_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server.py")
    return f'"{python_exe}" "{server_script}"'

def is_autostart_enabled() -> bool:
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        value, regtype = winreg.QueryValueEx(registry_key, APP_NAME)
        winreg.CloseKey(registry_key)
        return value == get_server_start_command()
    except WindowsError:
        return False

def toggle_autostart() -> bool:
    """Toggles autostart on or off. Returns the new state (True if enabled, False if disabled)."""
    is_enabled = is_autostart_enabled()
    
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        
        if is_enabled:
            winreg.DeleteValue(registry_key, APP_NAME)
            new_state = False
        else:
            winreg.SetValueEx(registry_key, APP_NAME, 0, winreg.REG_SZ, get_server_start_command())
            new_state = True
            
        winreg.CloseKey(registry_key)
        return new_state
    except WindowsError as e:
        print(f"Failed to toggle autostart: {e}")
        return is_enabled
