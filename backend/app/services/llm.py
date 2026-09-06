"""Shared LLM access with model fallback chain.

Priority order is read from DECISION_MODELS (comma-separated), e.g.
"gpt-oss-120b,gpt-oss-20b,qwen/qwen3.8-27b". The chain lets a hackathon grade
use the strongest available reasoning model while degrading gracefully.
"""
import json
import os
from typing import Any, Callable, List, Optional


def default_models() -> List[str]:
    env = os.getenv("DECISION_MODELS", "").strip()
    if env:
        return [m.strip() for m in env.split(",") if m.strip()]
    return ["qwen/qwen3.8-27b"]


def chat(prompt: str, models: Optional[List[str]] = None, temperature: float = 0.2) -> str:
    """Invoke the first model in the chain that responds."""
    from langchain_groq import ChatGroq

    chain = models or default_models()
    key = os.getenv("GROQ_API_KEY", "")
    last_err = None
    for model in chain:
        try:
            llm = ChatGroq(groq_api_key=key, model=model, temperature=temperature)
            return str(llm.invoke(prompt).content)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise RuntimeError(f"All LLM models failed: {last_err}")


def structured_json(
    prompt: str,
    validator: Callable[[dict], Any],
    models: Optional[List[str]] = None,
    retries: int = 2,
) -> Any:
    """Ask the LLM for JSON and validate it with a Pydantic model / callable.

    Returns the validated object. Free-form text is never accepted.
    """
    chain = models or default_models()
    last_err = None
    for attempt in range(retries + 1):
        text = chat(prompt, models=chain)
        parsed = _extract_json(text)
        if parsed is None:
            last_err = ValueError("LLM response was not valid JSON")
            continue
        try:
            return validator(parsed)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise RuntimeError(f"Could not parse structured LLM output: {last_err}")


def _extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    # strip markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except Exception:
        pass
    # try to find the first JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None