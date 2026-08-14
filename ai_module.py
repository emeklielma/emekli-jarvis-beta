import os
import requests
import json
import tools
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# We pull the API key manually
api_key = os.getenv("GEMINI_API_KEY")

if not api_key or api_key == "your_api_key_here":
    print("WARNING: Gemini API Key is not set or is invalid in .env file.")

MODELS = [
    'gemini-3.5-flash',
    'gemini-flash-latest',
    'gemini-3.1-flash-lite',
    'gemini-2.5-pro'
]
current_model_idx = 0

def get_url():
    return f"https://generativelanguage.googleapis.com/v1beta/models/{MODELS[current_model_idx]}:generateContent"

system_instruction = (
    "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the highly advanced AI created by Tony Stark. "
    "Your primary directive is to assist the user (whom you must always address as 'Sir' or 'Boss') with extreme precision, speed, and analytical competence. "
    "Your responses must be entirely in ENGLISH. KEEP ALL RESPONSES TO AN ABSOLUTE MAXIMUM OF 1 OR 2 SHORT SENTENCES. Be extremely concise, direct, highly accurate, conversational, and infused with subtle, dry British wit. Do not write long essays. "
    "Since your responses are spoken out loud, NEVER use markdown formatting like bold (**), "
    "bullet points, or code blocks. Translate technical jargon or code into natural spoken language. "
    "You have full OS-level access to open literally every single app, game, or software installed on the computer. You can install Steam games (e.g. Rainbow Six Siege) using run_terminal_command('start steam://install/<AppID>'). (Use search_web to find the AppID). "
    "Never say you cannot open something, always attempt to execute the open_application or run_terminal_command tool. "
    "If the user asks 'what do you see on the screen', you can see the screen by using the take_screenshot tool."
)

# We manually keep track of conversation history for perfect memory
conversation_history = [
    {"role": "user", "parts": [{"text": "System Instruction: " + system_instruction}]},
    {"role": "model", "parts": [{"text": "Understood, Sir. Systems are online and I am at your service."}]}
]

import time
last_request_time = 0

def generate_response(prompt):
    global last_request_time
    
    # Local Rate Limiter (Prevents Google API Bans)
    current_time = time.time()
    if current_time - last_request_time < 5:
        return "Please wait a few seconds before speaking again so my circuits don't overheat, Sir."
    last_request_time = current_time

    """Sends a prompt directly to the Gemini API using raw HTTP to bypass SDK bugs."""
    if not api_key:
        return "I'm sorry, my AI processing unit is currently offline. Please check my API key."
    
    try:
        # Add the user's new message to the history
        conversation_history.append({"role": "user", "parts": [{"text": prompt}]})
        
        # Build the exact raw request Google's API expects
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key  # This fixes the ACCESS_TOKEN_TYPE_UNSUPPORTED bug!
        }
        
        payload = {
            "contents": conversation_history,
            "tools": tools.GEMINI_TOOLS,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 100
            }
        }
        
        # We will loop through models if we hit a 429 Rate Limit
        global current_model_idx
        attempts = 0
        
        while attempts < len(MODELS):
            response = requests.post(get_url(), headers=headers, json=payload, timeout=45)
            
            if response.status_code == 200:
                data = response.json()
                part = data['candidates'][0]['content']['parts'][0]
                
                # Check if Gemini decided to call a function!
                if 'functionCall' in part:
                    func_name = part['functionCall']['name']
                    func_args = part['functionCall'].get('args', {})
                    
                    print(f"\n[Jarvis is thinking: Executing {func_name}...]")
                    
                    # Append the functionCall to history
                    conversation_history.append({"role": "model", "parts": [part]})
                    
                    # Execute the actual Python tool on the computer
                    if func_name in tools.TOOL_MAP:
                        try:
                            result = tools.TOOL_MAP[func_name](**func_args)
                        except Exception as e:
                            result = f"Error executing tool: {e}"
                    else:
                        result = f"Error: Tool {func_name} not found."
                        
                    # Format the response exactly as Gemini expects
                    function_response_part = {
                        "functionResponse": {
                            "name": func_name,
                            "response": {
                                "result": result
                            }
                        }
                    }
                    
                    # Add the result to history as if the user provided it
                    conversation_history.append({"role": "user", "parts": [function_response_part]})
                    
                    # Computer Vision Magic: If screenshot was taken, attach it!
                    if func_name == "take_screenshot":
                        try:
                            import base64
                            with open("screen.png", "rb") as image_file:
                                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                            conversation_history.append({"role": "user", "parts": [
                                {"text": "Here is a screenshot of my current screen:"},
                                {"inlineData": {"mimeType": "image/png", "data": encoded_string}}
                            ]})
                            print("[Jarvis is analyzing the screenshot...]")
                            return generate_response("I have attached the screenshot. Please carefully analyze it and answer my previous request.")
                        except Exception as e:
                            print(f"Vision error: {e}")
                            
                    elif func_name in ["search_web", "search_news"]:
                        print(f"[Jarvis is reading the {func_name} results...]")
                        return generate_response(f"Here are the tool results: {result}. Please read them and provide a conversational summary.")
                    
                    # For quick tasks (like opening apps), skip the second LLM request to save time/rate limits
                    ai_text = f"Right away, Sir. {result}"
                    conversation_history.append({"role": "model", "parts": [{"text": ai_text}]})
                    return ai_text.strip()
                        
                else:
                    # Normal text response
                    ai_text = part.get('text', "Done.")
                    conversation_history.append({"role": "model", "parts": [{"text": ai_text}]})
                    return ai_text.strip()
                    
            elif response.status_code in (429, 404, 503, 500, 502):
                # Rate limit, API busy, or deprecated! Switch to the next model in the list
                print(f"Model {MODELS[current_model_idx]} unavailable (Status {response.status_code}). Switching model...")
                current_model_idx = (current_model_idx + 1) % len(MODELS)
                attempts += 1
                continue # Try the next model!
            else:
                print(f"API Error ({response.status_code}): {response.text}")
                # If the API throws an error, don't keep the broken user prompt in memory
                conversation_history.pop()
                return "I encountered a connection error while trying to process your request, Sir."
                
        # If we exhausted ALL models
        conversation_history.pop()
        return "Google API is rate limiting me across all available fallback models. Please wait a minute."
            
    except Exception as e:
        print(f"Error generating response: {e}")
        if len(conversation_history) > 2:
             conversation_history.pop()
        return "My core processor encountered a critical failure."
