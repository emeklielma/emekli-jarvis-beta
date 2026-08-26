import webview
import sys
import socket
import time

_window_ref = [None]

def wait_for_server(host='localhost', port=5173, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False

class JarvisAPI:
    def minimize(self):
        if _window_ref[0]:
            _window_ref[0].minimize()
            
    def toggle_fullscreen(self):
        if _window_ref[0]:
            _window_ref[0].toggle_fullscreen()

def main():
    api = JarvisAPI()
    
    print("Waiting for Vite dev server (localhost:5173)...")
    if not wait_for_server(port=5173, timeout=30):
        print("Error: Vite dev server did not start in time.")
        sys.exit(1)
        
    window = webview.create_window(
        title='JARVIS - MARK XLIX', 
        url='http://localhost:5173',
        width=1200, 
        height=800, 
        background_color='#030612',
        js_api=api
    )
    _window_ref[0] = window
    
    # Start the native window loop
    webview.start()

if __name__ == '__main__':
    main()
