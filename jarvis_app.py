import webview
import sys

_window_ref = [None]

class JarvisAPI:
    def minimize(self):
        if _window_ref[0]:
            _window_ref[0].minimize()
            
    def toggle_fullscreen(self):
        if _window_ref[0]:
            _window_ref[0].toggle_fullscreen()

def main():
    api = JarvisAPI()
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
