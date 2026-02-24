import re
import tiktoken

_enc: tiktoken.Encoding | None = None

# Separators tried in order: paragraphs → lines → sentence endings → words
_SEPARATORS = ["\n\n", "\n", r"(?<=[.!?])\s+"]


def _get_enc() -> tiktoken.Encoding:
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


def _token_len(text: str) -> int:
    return len(_get_enc().encode(text))


def _split_recursive(text: str, separators: list[str], chunk_size: int) -> list[str]:
    """Split text using the first separator; recurse on pieces still over chunk_size."""
    sep, rest = separators[0], separators[1:]
    parts = [p.strip() for p in re.split(sep, text) if p.strip()]

    result = []
    for part in parts:
        if _token_len(part) <= chunk_size or not rest:
            result.append(part)
        else:
            result.extend(_split_recursive(part, rest, chunk_size))
    return result


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """
    Recursive token-aware chunker.
    Splits on paragraphs → lines → sentence boundaries, then merges small pieces
    into chunks of up to chunk_size tokens with overlap tokens of context carry-over.
    """
    enc = _get_enc()
    pieces = _split_recursive(text, _SEPARATORS, chunk_size)

    chunks: list[str] = []
    current: list[int] = []

    for piece in pieces:
        piece_tokens = enc.encode(piece)

        if len(current) + len(piece_tokens) > chunk_size and current:
            chunks.append(enc.decode(current))
            current = current[-overlap:] if overlap else []

        current.extend(piece_tokens)

    if current:
        chunks.append(enc.decode(current))

    return chunks
