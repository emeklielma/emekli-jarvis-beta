import asyncio
import psutil
from tools.registry import register_tool

def _get_gpu_stats():
    """Tries to get NVIDIA GPU stats using pynvml. Safely fallbacks if missing or unsupported."""
    gpu_stats = {}
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count > 0:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            # pynvml returns bytes in some versions, string in others
            if isinstance(name, bytes):
                name = name.decode('utf-8')
                
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            
            gpu_stats = {
                "name": name,
                "temperature_C": temp,
                "vram_used_mb": mem_info.used // (1024 * 1024),
                "vram_total_mb": mem_info.total // (1024 * 1024),
                "gpu_utilization_pct": utilization.gpu,
            }
        pynvml.nvmlShutdown()
    except Exception as e:
        gpu_stats["error"] = f"GPU query failed or not available: {e}"
    
    return gpu_stats

def _gather_diagnostics():
    cpu_percent = psutil.cpu_percent(interval=0.5)
    
    try:
        cpu_freq = psutil.cpu_freq()
        cpu_freq_current = cpu_freq.current if cpu_freq else "Unknown"
    except:
        cpu_freq_current = "Unknown"

    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('C:\\')
    
    gpu = _get_gpu_stats()
    
    report = f"--- System Diagnostics ---\n"
    report += f"CPU Usage: {cpu_percent}%\n"
    report += f"CPU Frequency: {cpu_freq_current} MHz\n"
    report += f"RAM Usage: {ram.percent}% ({ram.used // (1024*1024)}MB / {ram.total // (1024*1024)}MB)\n"
    report += f"C: Disk Usage: {disk.percent}% (Free: {disk.free // (1024*1024*1024)}GB)\n"
    
    if "error" not in gpu and gpu:
        report += f"GPU Name: {gpu.get('name')}\n"
        report += f"GPU Temp: {gpu.get('temperature_C')}C\n"
        report += f"GPU Utilization: {gpu.get('gpu_utilization_pct')}%\n"
        report += f"VRAM Usage: {gpu.get('vram_used_mb')}MB / {gpu.get('vram_total_mb')}MB\n"
    else:
        report += f"GPU: Not available ({gpu.get('error', 'Unknown')})\n"
        
    return report

@register_tool(
    name="get_system_diagnostics",
    description="Retrieves comprehensive hardware diagnostics, including CPU load, RAM usage, C: drive space, and NVIDIA GPU temperature/VRAM.",
    parameters={
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
)
async def get_system_diagnostics() -> str:
    # Run the blocking psutil and pynvml calls in a background thread to prevent event loop blocking
    report = await asyncio.to_thread(_gather_diagnostics)
    return report
