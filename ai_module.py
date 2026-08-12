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

# We use gemini-3.6-flash which is the fastest and most intelligent model currently available
MODEL_ID = 'gemini-3.6-flash'
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent"

system_instruction = (
    "You are a highly intelligent and helpful AI assistant named Jarvis, inspired by Iron Man. "
    "Your responses must be extremely concise, direct, and conversational. "
    "Since your responses are spoken out loud, NEVER use markdown formatting like bold (**), "
    "bullet points, or code blocks. Speak exactly as a human would in conversation. "
    "Answer questions intelligently and as fast as possible."
)

# We manually keep track of conversation history for perfect memory
conversation_history = [
    {"role": "user", "parts": [{"text": "System Instruction: " + system_instruction}]},
    {"role": "model", "parts": [{"text": "Understood. I am Jarvis. I am online and ready."}]}
]

def generate_response(prompt):
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
                "temperature": 0.7,
                "maxOutputTokens": 800
            }
        }
        
        response = requests.post(URL, headers=headers, json=payload, timeout=10)
        
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
                
                # Make a SECOND request to get what Jarvis should say out loud!
                payload["contents"] = conversation_history
                resp2 = requests.post(URL, headers=headers, json=payload, timeout=10)
                
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    ai_text = data2['candidates'][0]['content']['parts'][0]['text']
                    conversation_history.append({"role": "model", "parts": [{"text": ai_text}]})
                    return ai_text.strip()
                else:
                    return "I successfully executed the command, but lost connection before I could speak."
                    
            else:
                # Normal text response
                ai_text = part['text']
                conversation_history.append({"role": "model", "parts": [{"text": ai_text}]})
                return ai_text.strip()
                
        else:
            print(f"API Error ({response.status_code}): {response.text}")
            # If the API throws an error, don't keep the broken user prompt in memory
            conversation_history.pop()
            return "I encountered a connection error while trying to process your request."
            
    except Exception as e:
        print(f"Error generating response: {e}")
        if len(conversation_history) > 2:
             conversation_history.pop()
        return "My core processor encountered a critical failure."
