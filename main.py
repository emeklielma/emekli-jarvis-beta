import time
import speech_module as sm
import ai_module as am
import webbrowser
import os

WAKE_WORD = "jarvis"

def main():
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
