import os
from pathlib import Path

from langchain_openai import ChatOpenAI


def get_llm_client() -> ChatOpenAI:
    _load_env_file()

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    openrouter_model_name = os.getenv("OPENROUTER_MODEL_NAME")

    if openrouter_api_key and openrouter_model_name:
        return ChatOpenAI(
            api_key=openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            model=openrouter_model_name,
            temperature=0,
        )

    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    if openai_api_key:
        return ChatOpenAI(
            api_key=openai_api_key,
            model=openai_model,
            temperature=0,
        )

    raise ValueError(
        "LLM API key is required. Set OPENROUTER_API_KEY and "
        "OPENROUTER_MODEL_NAME, or set OPENAI_API_KEY."
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
