import yaml
from pathlib import Path

def load_prompt(name: str) -> str:
    """
    Loads a system prompt from the YAML files in the prompts directory.
    
    Args:
        name: The base name of the prompt file (without extension).
        
    Returns:
        str: The extracted system prompt content.
    """
    prompt_path = Path(__file__).parent / "prompts" / f"{name}.yaml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["system_prompt"]
