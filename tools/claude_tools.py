from tools.registry import register_tool
from core import claude_launcher


@register_tool(
    name="open_claude",
    description=(
        "Opens Claude (Claude Code in the project folder, or the Claude app) so the user can build software with it. "
        "Call this when the user says they want to build/make a new app, website or game ('uygulama yapacağım'), "
        "or wants to continue working on a project ('<name> projesine devam edelim')."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "mode": {"type": "STRING", "description": "'new' to start a new app/project, 'continue' to continue an existing project."},
            "project_name": {"type": "STRING", "description": "Optional project name as spoken by the user (e.g. 'emekli jarvis')."}
        },
        "required": ["mode"]
    }
)
def open_claude(mode: str = "new", project_name: str = None) -> str:
    return claude_launcher.open_claude(mode, project_name)
