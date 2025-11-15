"""Token counting utilities."""

from typing import Optional

import tiktoken

# Cache for tokenizer instances
_tokenizer_cache = {}


def count_tokens(text: str, model_id: str) -> int:
    """Count tokens for given text and model.

    Args:
        text: Input text
        model_id: Model identifier

    Returns:
        Token count (approximate)
    """
    if not text:
        return 0

    # Try to get exact tokenizer for OpenAI models
    if "gpt" in model_id.lower():
        try:
            encoding = get_openai_encoding(model_id)
            return len(encoding.encode(text))
        except Exception:
            pass

    # Fallback: approximate (1 token ~= 4 chars)
    return len(text) // 4


def get_openai_encoding(model_id: str):
    """Get tiktoken encoding for OpenAI model."""
    if model_id in _tokenizer_cache:
        return _tokenizer_cache[model_id]

    try:
        # Map model to encoding
        if "gpt-4" in model_id or "gpt-3.5" in model_id:
            encoding = tiktoken.encoding_for_model("gpt-4")
        else:
            encoding = tiktoken.get_encoding("cl100k_base")

        _tokenizer_cache[model_id] = encoding
        return encoding
    except Exception as e:
        print(f"⚠️  Failed to load tokenizer for {model_id}: {e}")
        raise
