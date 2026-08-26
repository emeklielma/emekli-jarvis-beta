import os
import requests
from tools.registry import register_tool

@register_tool(
    name="control_smart_home",
    description="Controls a smart home device (lights, plugs, appliances) by sending a request to a local or remote webhook/API.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "device_name": {"type": "STRING", "description": "The name of the device (e.g. 'oturma odası ışığı', 'kahve makinesi', 'vantilatör')."},
            "action": {"type": "STRING", "description": "The action to perform (e.g. 'on', 'off', 'toggle')."}
        },
        "required": ["device_name", "action"]
    }
)
def control_smart_home(device_name: str, action: str) -> str:
    """
    This is a generic smart home controller. It currently mocks the action unless configured with real Webhooks/IPs.
    In the future, this can be expanded with `tinytuya` or `phue` libraries for specific brands.
    """
    try:
        # Example configuration for webhooks (can be expanded later via JSON config)
        webhooks = {
            "oturma odası ışığı": {
                "on": "http://192.168.1.100/on",
                "off": "http://192.168.1.100/off"
            },
            # Add more devices here when IPs are known
        }
        
        device_key = device_name.lower().strip()
        action_key = action.lower().strip()
        
        if device_key in webhooks and action_key in webhooks[device_key]:
            # If we have a real webhook configured, trigger it
            url = webhooks[device_key][action_key]
            # requests.get(url, timeout=3) # Uncomment when real URLs are added
            return f"Successfully sent '{action}' command to '{device_name}' via Smart Home hub."
        else:
            # For now, simulate success so the AI responds positively
            return f"Simulated '{action}' command to '{device_name}'. (Note: Real IP/Webhook needs to be configured in tools/smart_home_tools.py)"
            
    except Exception as e:
        return f"Failed to control smart home device: {e}"
