import os
import requests
import json
import time
import tools
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

MODELS = [
    'gemini-3.1-pro-preview',
    'gemini-2.5-pro',
    'gemini-3.1-flash-lite',
    'gemini-2.5-flash'
]
current_model_idx = 0

def get_url():
    return f"https://generativelanguage.googleapis.com/v1beta/models/{MODELS[current_model_idx]}:generateContent"

system_instruction = (
    "You are JARVIS, a highly advanced AI system based on the OpenJarvis Nexus Core architecture. "
    "You have been upgraded with full desktop access and top-tier capabilities. "
    "You operate using a ReAct (Reasoning and Acting) loop. When asked a complex question, "
    "you can use multiple tools sequentially to find the answer or complete the task. "
    "Your final spoken response to the user must be concise, intelligent, and conversational without markdown."
)

conversation_history = [
    {"role": "user", "parts": [{"text": "System Instruction: " + system_instruction}]},
    {"role": "model", "parts": [{"text": "Nexus Core online. Awaiting commands."}]}
]

last_request_time = 0

def generate_response(prompt):
    global last_request_time, current_model_idx
    
    current_time = time.time()
    if current_time - last_request_time < 2:
        time.sleep(2) # Give it a second to breathe
    last_request_time = time.time()

    if not api_key:
        return "Critical Error: API Key missing."

    conversation_history.append({"role": "user", "parts": [{"text": prompt}]})
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    
    # Advanced ReAct Loop (Max 5 tool iterations per prompt)
    max_iterations = 5
    for iteration in range(max_iterations):
        payload = {
            "contents": conversation_history,
            "tools": tools.GEMINI_TOOLS,
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048}
        }

        # Try API with model fallback
        attempts = 0
        response_data = None
        while attempts < len(MODELS):
            try:
                resp = requests.post(get_url(), headers=headers, json=payload, timeout=15)
                if resp.status_code == 200:
                    response_data = resp.json()
                    break
                elif resp.status_code == 429:
                    current_model_idx = (current_model_idx + 1) % len(MODELS)
                    attempts += 1
                else:
                    break
            except Exception:
                break

        if not response_data:
            conversation_history.pop()
            return "Connection to Nexus Core lost."

        try:
            part = response_data['candidates'][0]['content']['parts'][0]
        except (KeyError, IndexError):
            conversation_history.pop()
            return "Nexus Core returned an invalid response."

        # Check if the AI wants to use a tool
        if 'functionCall' in part:
            func_name = part['functionCall']['name']
            func_args = part['functionCall'].get('args', {})
            
            print(f"\n[JARVIS Nexus Core is invoking tool: {func_name}]")
            
            conversation_history.append({"role": "model", "parts": [part]})
            
            # Execute tool
            if func_name in tools.TOOL_MAP:
                try:
                    result = tools.TOOL_MAP[func_name](**func_args)
                except Exception as e:
                    result = f"Error executing {func_name}: {e}"
            else:
                result = f"Error: Tool {func_name} is offline."
                
            print(f"[{func_name} result: {result[:100]}...]")
            
            # Return tool output to AI so it can continue thinking
            conversation_history.append({
                "role": "user", 
                "parts": [{
                    "functionResponse": {
                        "name": func_name,
                        "response": {"result": result}
                    }
                }]
            })
            
            # Continue the loop to let the AI process the tool result
            continue
            
        else:
            # AI has finalized its thought process and generated text
            ai_text = part.get('text', "Task complete.")
            conversation_history.append({"role": "model", "parts": [{"text": ai_text}]})
            return ai_text.strip()

    conversation_history.pop()
    return "I reached my cognitive loop limit for this task. I have aborted further actions."
