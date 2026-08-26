import os
import shutil
import time
from tools.registry import register_tool

@register_tool(
    name="organize_directory",
    description="Organizes a folder by grouping files into subfolders by their extension (e.g. Images, Documents, Videos).",
    parameters={
        "type": "OBJECT",
        "properties": {
            "directory_path": {"type": "STRING", "description": "The absolute path of the directory to organize."}
        },
        "required": ["directory_path"]
    }
)
def organize_directory(directory_path: str) -> str:
    try:
        if not os.path.exists(directory_path):
            return f"Directory {directory_path} does not exist."
            
        ext_map = {
            'Images': ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'],
            'Documents': ['.pdf', '.doc', '.docx', '.txt', '.xlsx', '.xls', '.ppt', '.pptx', '.csv'],
            'Videos': ['.mp4', '.avi', '.mkv', '.mov', '.wmv'],
            'Audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg'],
            'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
            'Executables': ['.exe', '.msi', '.bat', '.sh'],
            'Code': ['.py', '.js', '.html', '.css', '.cpp', '.c', '.java', '.json', '.xml']
        }
        
        moved_count = 0
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            if os.path.isfile(item_path):
                _, ext = os.path.splitext(item)
                ext = ext.lower()
                
                # Find category
                category = "Others"
                for cat, exts in ext_map.items():
                    if ext in exts:
                        category = cat
                        break
                        
                cat_path = os.path.join(directory_path, category)
                if not os.path.exists(cat_path):
                    os.makedirs(cat_path)
                    
                shutil.move(item_path, os.path.join(cat_path, item))
                moved_count += 1
                
        return f"Successfully organized {moved_count} files in {directory_path}."
    except Exception as e:
        return f"Failed to organize directory: {e}"

@register_tool(
    name="write_code_to_file",
    description="Writes raw code to a new or existing file. Jarvis can use this to generate code for the user.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "file_path": {"type": "STRING", "description": "The path to the file to create/modify."},
            "code": {"type": "STRING", "description": "The code to write into the file."}
        },
        "required": ["file_path", "code"]
    }
)
def write_code_to_file(file_path: str, code: str) -> str:
    try:
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        return f"Successfully wrote code to {file_path}."
    except Exception as e:
        return f"Failed to write code to file: {e}"
