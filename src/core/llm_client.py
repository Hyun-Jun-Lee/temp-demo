import os
from pathlib import Path

from langchain_openai import ChatOpenAI


def get_llm_client() -> ChatOpenAI:
    _load_env_file()

    api_key = os.getenv("OPENROUTER_API_KEY")
    model_name = os.getenv("OPENROUTER_MODEL_NAME")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is required.")

    if not model_name:
        raise ValueError("OPENROUTER_MODEL_NAME environment variable is required.")

    return ChatOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        model=model_name,
        temperature=0,
    )


def _load_env_file() -> None:
    env_path = Path(".env")

    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        os.environ.setdefault(key, value)
