import os
import threading
import webbrowser
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from core import autostart

class JarvisSystemTray:
    def __init__(self):
        self.icon = None
        self.running = False

    def _create_default_icon(self):
        # Create a dynamic blue Arc Reactor style icon
        image = Image.new('RGB', (64, 64), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Outer ring
        draw.ellipse((8, 8, 56, 56), outline=(0, 150, 255), width=4)
        # Inner ring
        draw.ellipse((16, 16, 48, 48), outline=(0, 200, 255), width=2)
        # Core
        draw.ellipse((24, 24, 40, 40), fill=(0, 255, 255))
        
        return image

    def on_open_interface(self, icon, item):
        webbrowser.open("http://localhost:5173")

    def on_toggle_autostart(self, icon, item):
        autostart.toggle_autostart()

    def on_exit(self, icon, item):
        self.running = False
        icon.stop()
        os._exit(0)

    def _get_menu(self):
        return Menu(
            MenuItem("J.A.R.V.I.S. (Çalışıyor)", None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("Arayüzü Aç", self.on_open_interface, default=True),
            MenuItem(
                "Windows Başlangıcında Çalıştır", 
                self.on_toggle_autostart, 
                checked=lambda item: autostart.is_autostart_enabled()
            ),
            Menu.SEPARATOR,
            MenuItem("Çıkış", self.on_exit)
        )

    def _run_tray(self):
        self.running = True
        self.icon = Icon(
            "JarvisAI",
            icon=self._create_default_icon(),
            title="J.A.R.V.I.S.",
            menu=self._get_menu()
        )
        self.icon.run()

    def start(self):
        """Starts the tray icon in a background daemon thread."""
        if not self.running:
            threading.Thread(target=self._run_tray, daemon=True).start()

tray_manager = JarvisSystemTray()
