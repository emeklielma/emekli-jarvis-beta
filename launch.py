import subprocess
import time
import os
import sys

def print_cyan(text):
    print(f"\033[96m{text}\033[0m")

def main():
    print_cyan("=======================================")
    print_cyan(" JARVIS NEXUS CORE - SYSTEM STARTUP    ")
    print_cyan("=======================================")

    root_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(root_dir, "frontend")

    print_cyan("[1/3] Starting Python Intelligence Core (server.py)...")
    # Start the FastAPI server
    backend_process = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=root_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2) # Give backend time to spin up

    print_cyan("[2/3] Starting Frontend Matrix (Vite)...")
    # Start Vite dev server. We use shell=True for npm on Windows
    vite_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(3) # Give Vite time to compile and start

    print_cyan("[3/3] Launching Desktop Application (Electron)...")
    # Start Electron
    electron_process = subprocess.Popen(
        ["npm", "run", "electron"],
        cwd=frontend_dir,
        shell=True
    )

    print_cyan("\nJARVIS is now fully operational in Desktop Mode.")
    print_cyan("Close the desktop window to shut down the entire system.")

    try:
        # Wait for Electron app to be closed by the user
        electron_process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        print_cyan("\nInitiating System Shutdown...")
        
        # Kill the child processes gracefully
        try:
            backend_process.terminate()
            backend_process.wait(timeout=2)
        except Exception:
            backend_process.kill()

        try:
            # npm run dev might spawn child node processes, taskkill is safer on Windows
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(vite_process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        print_cyan("System Offline. Goodbye, sir.")

if __name__ == "__main__":
    main()
