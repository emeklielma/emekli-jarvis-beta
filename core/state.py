import asyncio
from typing import Optional, Dict

class GlobalState:
    def __init__(self):
        # Tracking active tasks for barge-in cancellation
        self.active_tasks: Dict[str, asyncio.Task] = {}
        # Keep track if the microphone is active globally
        self.mic_active = True
        # Keep track of current system protocol
        self.protocol = "normal"
        # Keep track of the last time a clap was detected
        self.last_clap_time = 0.0
    
    def register_task(self, name: str, task: asyncio.Task):
        self.active_tasks[name] = task
        
    def cancel_task(self, name: str):
        if name in self.active_tasks:
            task = self.active_tasks[name]
            if not task.done():
                task.cancel()
            del self.active_tasks[name]
            
    def cancel_all_barge_in_tasks(self):
        """Cancels LLM generation and audio playback if user interrupts."""
        self.cancel_task("ai_stream_task")
        self.cancel_task("audio_playback_task")

# Global singleton
state = GlobalState()
