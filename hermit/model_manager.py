"""
Auto-download and manage local models for Hermit.
Downloads a small model on first run - no user setup needed.
"""

import os
import sys
from pathlib import Path

MODEL_DIR = Path.home() / ".hermit" / "models"
DEFAULT_MODEL = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
DEFAULT_MODEL_URL = "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
MODEL_SIZE_MB = 670  # Approximate size


def get_model_path() -> Path:
    """Get path to the local model, downloading if needed."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / DEFAULT_MODEL

    if not model_path.exists():
        download_model(model_path)

    return model_path


def download_model(path: Path):
    """Download the default model with progress bar."""
    import urllib.request

    print(f"\n First run - downloading model (~{MODEL_SIZE_MB}MB)...")
    print(f"   This only happens once.\n")

    def progress_hook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(100, downloaded * 100 // total_size)
        bar = "█" * (percent // 2) + "░" * (50 - percent // 2)
        sys.stdout.write(f"\r   [{bar}] {percent}%")
        sys.stdout.flush()

    try:
        urllib.request.urlretrieve(DEFAULT_MODEL_URL, path, progress_hook)
        print("\n   Model downloaded!\n")
    except Exception as e:
        print(f"\n   Download failed: {e}")
        print("   Try manually: pip install ollama && ollama pull llama3")
        sys.exit(1)


def create_local_client():
    """Create a client using the local model via llama-cpp-python."""
    try:
        from llama_cpp import Llama
    except ImportError:
        print("Installing llama-cpp-python (one-time setup)...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "llama-cpp-python", "-q"])
        from llama_cpp import Llama

    model_path = get_model_path()

    # Create a wrapper that mimics OpenAI's interface
    llm = Llama(
        model_path=str(model_path),
        n_ctx=2048,
        n_threads=4,
        verbose=False
    )

    return LocalLLMClient(llm)


class LocalLLMClient:
    """Wrapper to make llama-cpp-python look like OpenAI client."""

    def __init__(self, llm):
        self.llm = llm
        self.chat = self.Chat(llm)

    class Chat:
        def __init__(self, llm):
            self.llm = llm
            self.completions = self.Completions(llm)

        class Completions:
            def __init__(self, llm):
                self.llm = llm

            def create(self, model, messages, max_tokens=256, **kwargs):
                # Format messages for the model
                prompt = ""
                for msg in messages:
                    role = msg["role"]
                    content = msg["content"]
                    if role == "system":
                        prompt += f"<|system|>\n{content}</s>\n"
                    elif role == "user":
                        prompt += f"<|user|>\n{content}</s>\n"
                    elif role == "assistant":
                        prompt += f"<|assistant|>\n{content}</s>\n"
                prompt += "<|assistant|>\n"

                response = self.llm(
                    prompt,
                    max_tokens=max_tokens,
                    stop=["</s>", "<|user|>"],
                    echo=False
                )

                # Return in OpenAI format
                return type('Response', (), {
                    'choices': [type('Choice', (), {
                        'message': type('Message', (), {
                            'content': response['choices'][0]['text'].strip()
                        })()
                    })()]
                })()


if __name__ == "__main__":
    # Test
    print("Testing model manager...")
    client = create_local_client()
    response = client.chat.completions.create(
        model="local",
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Say hello in JSON: {\"greeting\": \"...\"}"}
        ]
    )
    print(f"Response: {response.choices[0].message.content}")
