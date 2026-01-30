"""
LLM abstraction layer for Hermit.
Supports both OpenAI and local Ollama.
"""

import json
import urllib.request
from hermit.config import ensure_setup

def get_completion(system_prompt: str, user_input: str) -> str:
    """Get completion from configured LLM backend."""
    config = ensure_setup()
    
    if config["llm_backend"] == "ollama":
        return _ollama_completion(system_prompt, user_input, config)
    else:
        return _openai_completion(system_prompt, user_input, config)

def _ollama_completion(system_prompt: str, user_input: str, config: dict) -> str:
    """Get completion from local Ollama."""
    payload = {
        "model": config["ollama_model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        "stream": False,
    }
    
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",  # Use chat endpoint, not generate
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # Longer timeout for local
            result = json.loads(resp.read().decode())
            return result["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        print(f"     Ollama error: {e}")
        print(f"   Trying simpler request...")
        return _ollama_completion_simple(user_input, config)
    
def _ollama_completion_simple(user_input: str, config: dict) -> str:
    """Fallback: simpler prompt for weaker models."""
    simple_prompt = f"""Convert this to a JSON action. Reply with ONLY JSON.

Actions: list_files, read_file, create_file, delete_files, move_file, create_directory, find_files, organize_by_type, run_command

User request: {user_input}

Examples:
"show files" → {{"action": "list_files", "path": ".", "all": true}}
"organize by type" → {{"action": "organize_by_type", "path": "/workspace/downloads"}}
"delete logs" → {{"action": "delete_files", "path": ".", "pattern": "*.log"}}

JSON:"""

    payload = {
        "model": config["ollama_model"],
        "prompt": simple_prompt,
        "stream": False,
    }
    
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode())
        return result["response"].strip()
    
def _openai_completion(system_prompt: str, user_input: str, config: dict) -> str:
    """Get completion from OpenAI API."""
    from openai import OpenAI
    
    client = OpenAI(api_key=config["openai_key"])
    
    response = client.chat.completions.create(
        model=config["openai_model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        max_tokens=256
    )
    
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    # Test
    result = get_completion(
        "You are a helpful assistant. Reply briefly.",
        "What is 2 + 2?"
    )
    print(f"Response: {result}")
