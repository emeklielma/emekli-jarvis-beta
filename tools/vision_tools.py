import os
import io
import mss
from PIL import Image
import google.generativeai as genai
from tools.registry import register_tool
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

def capture_screen_to_bytes() -> bytes:
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception as e:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        
    # Resize to save token/bandwidth
    img.thumbnail((1280, 720))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=80)
    return img_byte_arr.getvalue()

@register_tool(
    name="analyze_screen",
    description="Takes a screenshot of the user's screen and analyzes it to answer their question about what is currently visible.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "question": {"type": "STRING", "description": "What to look for or analyze on the screen (e.g. 'What error is on the screen?', 'Read this text')."}
        },
        "required": ["question"]
    }
)
def analyze_screen(question: str) -> str:
    try:
        image_bytes = capture_screen_to_bytes()
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Prepare the part for the image
        image_part = {
            "mime_type": "image/jpeg",
            "data": image_bytes
        }
        
        response = model.generate_content([image_part, question])
        return f"Vision Analysis Result: {response.text}"
    except Exception as e:
        return f"Failed to analyze screen: {e}"
