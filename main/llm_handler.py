# EMO Assistant - LLM (Ollama)
# Wraps ChatOllama for EMO's replies.

from langchain_ollama import ChatOllama

# Default model for Raspberry Pi
DEFAULT_MODEL = "tinyllama"
DEFAULT_TEMPERATURE = 0.0


def create_llm(model=DEFAULT_MODEL, temperature=DEFAULT_TEMPERATURE):
    """Create ChatOllama instance."""
    return ChatOllama(model=model, temperature=temperature)


def get_reply(llm, user_text, system_prompt=None):
    """
    Get a short reply from the LLM.
    system_prompt: optional system/context (e.g. "You are EMO, a friendly desktop pet.").
    """
    if system_prompt is None:
        system_prompt = "You are EMO, a friendly desktop pet. Reply in 1-2 short sentences."
    prompt = f"{system_prompt}\nUser: {user_text}"
    response = llm.invoke(prompt)
    return (response.content or "").strip()
