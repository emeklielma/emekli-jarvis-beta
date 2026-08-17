import time
import speech_module as sm
import ai_module as am
import tools
import webbrowser
import os

WAKE_WORD = "jarvis"

# ANSI escape codes for colors! (main() içindeki yerel kopyalarla aynı,
# ama _cli_approval_sink modül seviyesinde çalıştığı için kendi kopyasına
# ihtiyaç duyuyor)
_YELLOW = '\033[93m'
_RESET = '\033[0m'


def _cli_approval_sink(payload):
    """tools.approval_request_sink'e bağlanır: server.py'deki WebSocket
    onay akışının CLI karşılığı. _await_approval bu fonksiyonu çağırıp
    pending_approvals[id]["event"] üzerinde beklemeye başlıyor; burada
    kullanıcıdan senkron olarak (input ile) yanıt alınıp aynı event
    tetiklenerek o bekleme sonlandırılıyor.
    """
    request_id = payload["id"]
    command = payload["command"]
    print(f"\n{_YELLOW}[ONAY GEREKLİ]{_RESET} {command}")
    answer = input(f"{_YELLOW}Onaylıyor musunuz? (e/h):{_RESET} ").strip().lower()
    approved = answer in ("e", "evet", "y", "yes")

    with tools.pending_approvals_lock:
        entry = tools.pending_approvals.get(request_id)
        if entry is not None:
            entry["approved"] = approved
            entry["event"].set()


def main():
    tools.approval_request_sink = _cli_approval_sink

    # ANSI escape codes for colors!
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

    print(f"{CYAN}======================================={RESET}")
    print(f"{CYAN} JARVIS AI CORE ONLINE - CONTINUOUS MODE{RESET}")
    print(f"{CYAN}======================================={RESET}")
    
    # Introduce itself on startup
    sm.speak("Online and ready. What would you like to talk about?")
    
    mic_failures = 0
    text_mode = False
    
    while True:
        if text_mode:
            text = input(f"\n{GREEN}You:{RESET} ").lower()
        else:
            text = sm.listen()
        
        if text is None:
            mic_failures += 1
            if mic_failures >= 2 and not text_mode:
                print(f"\n{YELLOW}*** Microphone not detected. Switching to Text Mode! ***{RESET}")
                text_mode = True
            time.sleep(1)
            continue
            
        # If we got actual text (not empty), process it!
        if text != "":
            # Check for shutdown commands
            if "goodbye" in text or "shut down" in text or "sleep" in text:
                print(f"\n{CYAN}Jarvis:{RESET} Powering down. Goodbye, sir.")
                sm.speak("Powering down. Goodbye.")
                break
                
            # Get intelligent response from AI (which can now execute tools!)
            response = am.generate_response(text)
            
            # Print with color and Speak response
            print(f"\n{CYAN}Jarvis:{RESET} {response}")
            sm.speak(response)
        
        # Small sleep to prevent high CPU usage
        time.sleep(0.1)

if __name__ == "__main__":
    main()
