"""
Comprehensive Unit & Integration Test Suite for J.A.R.V.I.S. App Launcher Engine
"""

import os
import sys
import unittest
import app_launcher
import tools

class TestAppLauncher(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app_launcher.initialize_index()

    def test_text_normalization(self):
        """Test Turkish character mappings and noise removals."""
        test_cases = [
            ("Hesap Makinesini Aç", ["hesap"]),
            ("Spotify'ı Aç Lütfen", ["spotify"]),
            ("Google Chrome'u Başlat", ["google", "chrome"]),
            ("Not Defterini Aç", ["not"]),
            ("Visual Studio Code'u Aç", ["visual", "studio", "code"]),
            ("VS Code Aç", ["vs", "code"]),
            ("Ayarları Aç", ["ayar"]),
            ("Görev Yöneticisini Göster", ["gorev"]),
            ("Dosya Gezginini Aç", ["dosya", "gezgin"]),
            ("Denetim Masasını Aç", ["denetim"]),
            ("Valorant'ı Başlat", ["valorant"]),
            ("Discord'u Aç", ["discord"]),
            ("Steam'i Aç", ["steam"]),
            ("Minecraft'ı Aç", ["minecraft"]),
            ("TLauncher'ı Aç", ["tlauncher"]),
            ("Roblox'u Aç", ["roblox"]),
            ("The Forest Oyununu Başlat", ["the", "forest"]),
            ("Rainbow Six Siege'i Aç", ["rainbow", "six", "siege"]),
            ("Kamerayı Aç", ["kamera"]),
            ("Ses Kaydediciyi Başlat", ["ses", "kaydedici"]),
            ("Saat ve Alarmı Aç", ["saat"]),
            ("Ekran Alıntısını Aç", ["ekran", "alinti"]),
            ("Terminali Aç", ["terminal"]),
            ("CMD Çalıştır", ["cmd"]),
            ("PowerShell Başlat", ["powershell"]),
            ("Open Calculator Please", ["calculator"]),
            ("Launch Notepad", ["notepad"]),
            ("Open Settings", ["settings"]),
            ("Task Manager", ["task", "manager"]),
            ("File Explorer", ["file", "explorer"]),
        ]

        for raw_input, expected_words in test_cases:
            normalized = app_launcher.normalize_text(raw_input)
            for w in expected_words:
                self.assertIn(
                    w, normalized,
                    f"Word '{w}' missing in normalized output for '{raw_input}': got '{normalized}'"
                )

    def test_resolution_queries(self):
        """Test resolving 50+ real-world user queries to valid targets."""
        queries = [
            # System Tools
            "hesap makinesi", "hesap makinesini aç", "calculator", "calc",
            "not defteri", "not defterini aç", "notepad",
            "ayarlar", "ayarları aç", "settings",
            "görev yöneticisi", "görev yöneticisini aç", "task manager", "taskmgr",
            "dosya gezgini", "dosya gezginini aç", "file explorer", "explorer", "bu bilgisayar",
            "denetim masası", "control panel",
            "paint", "boya", "mspaint",
            "terminal", "windows terminal", "komut istemi", "cmd", "powershell",
            "kamera", "camera", "saat", "alarm", "clock",
            "ses kaydedici", "voice recorder",
            "ekran alıntısı", "snipping tool",

            # Popular Apps
            "chrome", "google chrome", "google chrome'u aç", "tarayıcı", "browser",
            "edge", "microsoft edge",
            "vscode", "vs code", "visual studio code", "visual studio",
            "discord", "discord'u aç",
            "whatsapp", "whatsapp'ı aç",
            "spotify", "spotify'ı aç", "müzik aç",
            "vlc", "vlc media player",
            "capcut", "voicemod", "speedtest", "winrar", "chatgpt", "bluestacks",

            # Games
            "steam", "steam'i aç",
            "valorant", "valorant'ı aç",
            "minecraft", "tlauncher",
            "roblox", "roblox player", "roblox studio",
            "the forest", "rainbow six siege", "r6", "wallpaper engine", "backrooms", "redmatch 2"
        ]

        resolved_count = 0
        for q in queries:
            target_info = app_launcher.resolve_app_target(q)
            self.assertIsNotNone(target_info, f"Query '{q}' failed to resolve to any target.")
            self.assertTrue("target" in target_info and target_info["target"], f"Target empty for query '{q}'")
            resolved_count += 1

        print(f"\n[Test Suite] Successfully resolved {resolved_count}/{len(queries)} diverse queries.")

    def test_tools_dispatch(self):
        """Test tools.py open_application and close_application integration."""
        self.assertIn("open_application", tools.TOOL_MAP)
        self.assertIn("close_application", tools.TOOL_MAP)

        # Test resolving through tools wrapper
        res = tools.open_application("hesap makinesi")
        self.assertIn("Successfully", res)

        # Clean up by closing test app
        close_res = tools.close_application("hesap makinesi")
        print(f"[Test Suite] Open result: {res} | Close result: {close_res}")

if __name__ == "__main__":
    unittest.main()
