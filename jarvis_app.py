import webview
import sys

def main():
    # Use the native Windows Edge WebView2 engine to render the React app seamlessly
    # This completely bypasses all Node.js and Electron security cache errors!
    webview.create_window(
        title='JARVIS - MARK XLIX', 
        url='http://localhost:5173',
        width=1200, 
        height=800, 
        background_color='#030612'
    )
    
    # Start the native window loop
    webview.start()

if __name__ == '__main__':
    main()
