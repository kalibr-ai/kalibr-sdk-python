"""Client-side redaction and hashing."""

import hashlib
import re
from typing import Optional

# PII patterns
PII_PATTERNS = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),
    (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "[CREDIT_CARD]"),
    (r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", "[IP_ADDRESS]"),
]

# Compiled patterns
COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), repl) for p, repl in PII_PATTERNS]


def redact_text(text: str) -> str:
    """Redact PII from text."""
    if not text:
        return text

    redacted = text
    for pattern, replacement in COMPILED_PATTERNS:
        redacted = pattern.sub(replacement, redacted)

    return redacted


def hash_text(text: str) -> str:
    """Create SHA256 hash of text."""
    if not text:
        return "0" * 64
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redact_and_hash(text: Optional[str]) -> str:
    """Redact PII and return hash."""
    if not text:
        return "0" * 64
    redacted = redact_text(text)
    return hash_text(redacted)
