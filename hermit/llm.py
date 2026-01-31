"""
LLM layer for Hermit - OpenAI with conversation history.
"""

from openai import OpenAI
from hermit.config import load_config

# Conversation history for context
conversation_history = []

# Max history turns to keep (to avoid token limits)
MAX_HISTORY_TURNS = 10


def clear_history():
    """Clear conversation history."""
    global conversation_history
    conversation_history = []

def get_completion(system_prompt: str, user_input: str) -> str:
    """Get completion from OpenAI with conversation history."""
    global conversation_history
    config = load_config()

    client = OpenAI(api_key=config["openai_key"])

    # Build messages with history
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model=config.get("openai_model", "gpt-4o-mini"),
        messages=messages,
        max_tokens=256
    )

    reply = response.choices[0].message.content.strip()

    conversation_history.append({"role": "user", "content": user_input})
    conversation_history.append({"role": "assistant", "content": reply})

    if len(conversation_history) > MAX_HISTORY_TURNS * 2:
        conversation_history = conversation_history[-(MAX_HISTORY_TURNS * 2):]

    return reply
