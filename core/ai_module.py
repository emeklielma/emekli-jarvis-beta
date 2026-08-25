import os
import json
import asyncio
import aiohttp
from typing import AsyncGenerator, Dict, Any, List
from dotenv import load_dotenv
from tools.registry import get_gemini_tools, get_tool_map

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

MODELS = [
    'gemini-3.5-flash',
    'gemini-flash-latest',
    'gemini-3.1-flash-lite',
    'gemini-2.5-pro'
]
current_model_idx = 0

def get_url():
    # Use SSE streaming endpoint
    return f"https://generativelanguage.googleapis.com/v1beta/models/{MODELS[current_model_idx]}:streamGenerateContent?alt=sse"

def get_system_instruction() -> str:
    base_instruction = (
        "You are an ultra-fast, minimal, and direct action-taking local desktop AI assistant (J.A.R.V.I.S.). "
        "[CORE PRINCIPLES] "
        "1. NEVER use unnecessary introductory phrases (e.g., 'Of course', 'Opening now', 'I am handling it'). "
        "2. When the user requests an action (e.g., opening an app, muting volume, searching files, web search), ALWAYS CALL the relevant function/tool first. "
        "3. When responding, use a maximum of 1-2 short, clear sentences. Speed is everything. "
        "4. If a command is ambiguous, do not guess repeatedly; execute the most likely command directly. "
        "[APPLICATION AND SYSTEM EXECUTION RULES] "
        "- When an application name is mentioned, make a tool call to search the system PATH or standard directories (C:\\Program Files, %AppData%, Start Menu). "
        "- When launching a process directly in a Windows/Linux environment, separate parameters correctly. "
        "- If the user is just chatting, respond instantly in a friendly, intelligent, and concise tone. "
        "- If an operation fails, state the reason in a single line without rambling."
    )
    # Load core memories
    try:
        if os.path.exists("core_memory.json"):
            with open("core_memory.json", "r", encoding="utf-8") as f:
                memories = json.load(f)
                if memories:
                    base_instruction += "\nCore Memories:\n- " + "\n- ".join(memories)
    except:
        pass
        
    try:
        from core import memory
        db_memories = memory.get_all_memories()
        if db_memories:
            formatted_db = "\n".join([f"- [{m['category']}] {m['key']}: {m['value']}" for m in db_memories])
            base_instruction += "\n[KALICI BELLEK (PERSISTENT MEMORY)]:\n" + formatted_db
    except Exception as e:
        print(f"Failed to load persistent memory: {e}")
        
    return base_instruction

# Sliding Context Window
# We keep System Instruction + Last 8 messages max
MAX_HISTORY = 8
conversation_history = []

def manage_history(new_message: Dict[str, Any]):
    global conversation_history
    conversation_history.append(new_message)
    # Keep only the last MAX_HISTORY messages
    if len(conversation_history) > MAX_HISTORY:
        conversation_history = conversation_history[-MAX_HISTORY:]

async def generate_response_stream(prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Yields chunks of text or tool execution events.
    Format: {"type": "token", "content": "..."} or {"type": "tool_call", "name": "...", "args": ...}
    """
    global current_model_idx
    
    # 1. Update history with user prompt
    manage_history({"role": "user", "parts": [{"text": prompt}]})
    
    if not API_KEY or API_KEY.strip() == "":
        yield {"type": "error", "content": "GEMINI_API_KEY bulunamadı. Lütfen .env dosyasını kontrol edin."}
        return
    
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY
    }
    
    # Always prepend the system instruction dynamically
    sys_msg = {"role": "user", "parts": [{"text": "System Instruction: " + get_system_instruction()}]}
    payload_history = [sys_msg, {"role": "model", "parts": [{"text": "Understood, Sir."}]}] + conversation_history
    
    payload = {
        "contents": payload_history,
        "tools": get_gemini_tools(),
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 500
        }
    }
    
    attempts = 0
    while attempts < len(MODELS):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(get_url(), headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=45)) as response:
                    if response.status == 200:
                        full_text = ""
                        async for line in response.content:
                            line = line.decode('utf-8').strip()
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break
                                
                                try:
                                    data = json.loads(data_str)
                                    candidates = data.get('candidates', [])
                                    if candidates:
                                        content = candidates[0].get('content', {})
                                        parts = content.get('parts', [])
                                        if parts:
                                            part = parts[0]
                                            # Check for text chunk
                                            if 'text' in part:
                                                chunk = part['text']
                                                full_text += chunk
                                                yield {"type": "token", "content": chunk}
                                                
                                            # Check for tool call
                                            if 'functionCall' in part:
                                                func_name = part['functionCall']['name']
                                                func_args = part['functionCall'].get('args', {})
                                                yield {"type": "tool_call", "name": func_name, "args": func_args}
                                                
                                                # Execute tool
                                                tool_map = get_tool_map()
                                                result_text = ""
                                                if func_name in tool_map:
                                                    try:
                                                        # Run tool in background thread if it's blocking
                                                        func = tool_map[func_name]
                                                        result_text = await asyncio.to_thread(func, **func_args)
                                                    except Exception as e:
                                                        result_text = f"Tool Error: {e}"
                                                else:
                                                    result_text = "Tool not found."
                                                    
                                                yield {"type": "tool_result", "name": func_name, "result": result_text}
                                                
                                                # In a real scenario we'd send the tool result back to Gemini for a second pass,
                                                # but for ultra-fast Jarvis, we often just read the result out loud or finish.
                                                if func_name not in ["take_screenshot", "search_web", "search_youtube", "search_news"]:
                                                    # For simple commands like opening apps, just say done.
                                                    done_text = f"Task complete. {result_text}"
                                                    yield {"type": "token", "content": done_text}
                                                    full_text += done_text
                                                    
                                except json.JSONDecodeError:
                                    pass
                        
                        if full_text:
                            manage_history({"role": "model", "parts": [{"text": full_text}]})
                        return # Success, exit generator
                        
                    elif response.status in (429, 404, 503, 500, 502):
                        current_model_idx = (current_model_idx + 1) % len(MODELS)
                        attempts += 1
                        continue
                    else:
                        yield {"type": "error", "content": f"API Error {response.status}"}
                        return
                        
            except asyncio.CancelledError:
                raise
            except Exception as e:
                yield {"type": "error", "content": str(e)}
                return
    
    yield {"type": "error", "content": "All models failed or rate limited."}
