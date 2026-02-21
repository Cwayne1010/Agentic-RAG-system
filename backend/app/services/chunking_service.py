def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Simple sliding window chunker on character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks
