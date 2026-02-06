from abc import ABC, abstractmethod

class LLMBackend(ABC):
    """Base class that both backends implement."""
    
    @abstractmethod
    def get_completion(self, system_prompt: str, user_input: str) -> str:
        """Send prompt to LLM, return response."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is properly configured."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Human-readable name for display."""
        pass
    
    @abstractmethod
    def clear_history(self):
        """Clear conversation history."""
        pass

class OpenAIBackend(LLMBackend):
    """Online backend using OpenAI API."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self._client = None  # Lazy load
        self.conversation_history = []
        self.max_history_turns = 10
    
    def _get_client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client
    
    def get_completion(self, system_prompt: str, user_input: str) -> str:
        client = self._get_client()
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_input})
        
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=2048
        )
        
        reply = response.choices[0].message.content.strip()
        
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": reply})
        
        if len(self.conversation_history) > self.max_history_turns * 2:
            self.conversation_history = self.conversation_history[-(self.max_history_turns * 2):]
        
        return reply
    
    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("sk-"))
    
    def get_name(self) -> str:
        return f"OpenAI ({self.model})"
    
    def clear_history(self):
        self.conversation_history = []

class LlamaCPPBackend(LLMBackend):
    
    def __init__(self, model_path: str, n_ctx: int = 4096, n_gpu_layers: int = -1):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self._llm = None
        self.conversation_history = []
        self.max_history_turns = 10

    def _get_llm(self):
        """Lazy-load the model. First call takes a few seconds."""
        if not self._llm:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                verbose=False  # Suppress llama.cpp logs
            )
        return self._llm

    def get_completion(self, system_prompt: str, user_input: str) -> str:
        """Send prompt to LLM, return response."""
        llama = self._get_llm()

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_input})
        
        response = llama.create_chat_completion(
            messages=messages,
            max_tokens=2048,
            temperature=0.1,
            response_format={
                "type": "json_object"  # Forces valid JSON
            }
        )
        reply = response['choices'][0]['message']['content'].strip()

        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": reply})

        if len(self.conversation_history) > self.max_history_turns * 2:
            self.conversation_history = self.conversation_history[-(self.max_history_turns * 2):]

        return reply
    
    def is_available(self) -> bool:
        """Check if backend is properly configured."""
        import os
        return bool(self.model_path and os.path.exists(self.model_path))
    
    def get_name(self) -> str:
        """Human-readable name for display."""
        import os
        if self.model_path:
            return f"llama.cpp ({os.path.basename(self.model_path)})"
        return "llama.cpp (not configured)"
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []

def create_backend(config: dict) -> LLMBackend:
    """Factory: create the right backend based on config."""
    backend_type = config.get("llm_backend", "openai")

    if backend_type == "openai":
        return OpenAIBackend(
            api_key=config.get("openai_key", ""),
            model=config.get("openai_model", "gpt-4o-mini")
        )
    elif backend_type == "llamacpp":
        return LlamaCPPBackend(
            model_path=config.get("llamacpp_model_path", ""),
            n_ctx=config.get("llamacpp_n_ctx", 4096),
            n_gpu_layers=config.get("llamacpp_n_gpu_layers", -1)
        )
    else:
        raise ValueError(f"Unknown backend: {backend_type}")