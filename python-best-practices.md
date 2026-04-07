# Python Best Practices — Senior Developer Patterns

This document explains the patterns and conventions used throughout this project.
Written for a near-beginner Python developer building toward freelance RAG/NLQ work.
Each section explains not just *what* to do but *why* seniors do it that way.

---

## 1. Type Hints — Label Everything

Type hints are annotations that tell you (and tools) what kind of data a function expects
and returns. They don't change how Python runs — they're documentation that tools can check.

```python
# ❌ Junior — you have to read the whole function to know what it takes
def retrieve(query, k):
    ...

# ✅ Senior — the signature tells you everything before you read a line
def retrieve(query: str, k: int = 5) -> list[str]:
    ...
```

**Why seniors do this:**
- A linter (like `ruff`) will warn you if you pass the wrong type
- You can read a function signature and understand it without reading the body
- Critical when writing RAG pipelines — a dict passed where a str is expected
  causes silent bugs, not crashes

**Common types you'll see in this project:**

```python
str          # text — queries, document content, collection names
int          # whole numbers — chunk size, top_k, token counts
float        # decimals — similarity scores (0.0 to 1.0)
bool         # True/False — flags like include_metadata=True
list[str]    # a list of strings — e.g. a list of retrieved chunks
dict[str, any]  # a dict with string keys — e.g. ChromaDB metadata
Optional[str]   # either a string OR None — use when a value might be absent
```

---

## 2. Dataclasses — Group Related Data Together

When a function needs to pass around several related values, don't use a plain dict.
Use a dataclass — it's like a lightweight struct that labels each field.

```python
# ❌ Junior — a dict works but has no labels, no type hints, no IDE help
doc = {"id": "001", "content": "...", "score": 0.87}

# ✅ Senior — a dataclass makes the shape of the data explicit
from dataclasses import dataclass

@dataclass
class RetrievedChunk:
    doc_id: str
    content: str
    score: float        # cosine similarity, 0.0 (unrelated) to 1.0 (identical)
    source_file: str
```

**Why seniors do this:**
- `chunk.score` is clearer than `chunk["score"]` — no typo risk
- Your IDE autocompletes fields
- If you add a new field later, Python will tell you every place that breaks

---

## 3. Early Returns — Avoid Deep Nesting

Nested `if` statements make code hard to follow. Exit early when something is wrong
so the "happy path" stays at the left margin.

```python
# ❌ Junior — the actual logic is buried 3 levels deep
def process_document(path):
    if path:
        if os.path.exists(path):
            if path.endswith(".pdf"):
                # actual logic here, deeply indented
                return extract_text(path)

# ✅ Senior — validate first, run logic last
def process_document(path: str) -> str:
    if not path:
        raise ValueError("path cannot be empty")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no file at: {path}")
    if not path.endswith(".pdf"):
        raise ValueError("only PDF files are supported")

    # happy path — no nesting
    return extract_text(path)
```

---

## 4. Constants at the Top — No Magic Numbers

A "magic number" is a literal value buried in code with no explanation.
Move all configuration values to named constants at the top of the file.

```python
# ❌ Junior — what does 1000 mean? what does 5 mean?
chunks = split_text(content, 1000, 100)
results = collection.query(embedding, 5)

# ✅ Senior — the name explains the intent
CHUNK_SIZE = 1000       # characters per chunk — tune up for dense legal docs
CHUNK_OVERLAP = 100     # characters shared between adjacent chunks
TOP_K = 5               # number of chunks to retrieve per query

chunks = split_text(content, CHUNK_SIZE, CHUNK_OVERLAP)
results = collection.query(embedding, TOP_K)
```

**Why seniors do this:**
- When a client's docs need different chunk sizes, you change one line, not ten
- The name documents the intent — `TOP_K = 5` is self-explanatory

---

## 5. f-strings — The Modern Way to Build Strings

Always use f-strings for string formatting. Avoid `+` concatenation and old `%` formatting.

```python
# ❌ Old style — hard to read, easy to miss a space
message = "Retrieved " + str(count) + " chunks for query: " + query

# ❌ Also old — % formatting, rarely used in new code
message = "Retrieved %d chunks for query: %s" % (count, query)

# ✅ Senior — f-strings are readable and fast
message = f"Retrieved {count} chunks for query: {query}"

# f-strings can run expressions inline
message = f"Top score: {results[0].score:.2f}"  # :.2f formats to 2 decimal places
```

---

## 6. Context Managers — Always Use `with` for Files

When opening files, always use `with`. It automatically closes the file even if
something goes wrong, preventing data corruption and resource leaks.

```python
# ❌ Junior — if an error happens, the file stays open
f = open("document.txt", "r")
content = f.read()
f.close()

# ✅ Senior — file closes automatically when the block exits, even on error
with open("document.txt", "r", encoding="utf-8") as f:
    content = f.read()
```

**Always specify `encoding="utf-8"`** — without it, behavior differs between
Mac, Windows, and Linux. This matters when your client is on Windows.

---

## 7. List Comprehensions — Concise Loops

When building a new list by transforming or filtering another list, use a
list comprehension instead of a for loop with `.append()`.

```python
# ❌ Junior — works, but verbose
chunks = []
for doc in documents:
    if len(doc.content) > 50:      # skip very short fragments
        chunks.append(doc.content.strip())

# ✅ Senior — one line, same result
chunks = [doc.content.strip() for doc in documents if len(doc.content) > 50]
```

**Rule of thumb:** if the comprehension doesn't fit on one readable line, use a loop.
Cleverness that sacrifices clarity is not a best practice.

---

## 8. Environment Variables — Never Hardcode Secrets

API keys, database URLs, and passwords must never appear in source code.
Load them from `.env` using `python-dotenv`.

```python
# ❌ NEVER do this — key gets committed to git and leaked
client = anthropic.Anthropic(api_key="sk-ant-...")

# ✅ Senior — load from environment, crash loudly if missing
import os
from dotenv import load_dotenv

load_dotenv()   # reads .env file into os.environ

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise EnvironmentError("ANTHROPIC_API_KEY not set — check your .env file")

client = anthropic.Anthropic(api_key=api_key)
```

---

## 9. Logging Over Print

Use Python's `logging` module instead of `print()` for anything beyond a
quick script. It gives you timestamps, severity levels, and the ability to
silence debug output in production without changing code.

```python
# ❌ Junior — print is fine for quick tests, not for production code
print("Ingesting document:", path)
print("ERROR: file not found")

# ✅ Senior — structured logging with severity levels
import logging

# configure once at the top of your entry-point script
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)  # __name__ = the current module's name

logger.info(f"Ingesting document: {path}")
logger.error(f"File not found: {path}")
logger.debug(f"Embedding shape: {embedding.shape}")  # only shown if level=DEBUG
```

**Levels in order of severity:** `DEBUG` → `INFO` → `WARNING` → `ERROR` → `CRITICAL`

---

## 10. Fail Loudly With Meaningful Errors

Don't silently swallow errors or return `None` when something goes wrong.
Raise a specific exception with a message that tells you *exactly* what failed.

```python
# ❌ Junior — returns None silently, caller has no idea why
def load_document(path: str):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return None

# ✅ Senior — fail loudly with context
def load_document(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Document not found: {path}\n"
            f"Check that the file exists and the path is correct."
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
```

---

## 11. One Responsibility Per Function

Each function should do exactly one thing. If you find yourself writing "and" when
describing what a function does, split it.

```python
# ❌ Junior — this function loads, chunks, embeds, AND stores
def ingest_document(path):
    text = open(path).read()
    chunks = split_into_chunks(text, 1000)
    embeddings = model.encode(chunks)
    collection.add(embeddings=embeddings, documents=chunks)

# ✅ Senior — each step is its own function, composable and testable
def load_text(path: str) -> str:
    ...

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    ...

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    ...

def store_chunks(chunks: list[str], embeddings: list[list[float]]) -> None:
    ...

# The orchestrator just composes the steps — easy to read, easy to test
def ingest_document(path: str) -> None:
    text = load_text(path)
    chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    embeddings = embed_chunks(chunks)
    store_chunks(chunks, embeddings)
```

---

## 12. Dependency Injection — Pass Dependencies In

Don't create shared objects (like a ChromaDB client or an Anthropic client) inside
utility functions. Create them once and pass them in. This makes functions testable
and avoids hidden global state.

```python
# ❌ Junior — creates a new client on every call (slow, wasteful)
def retrieve(query: str) -> list[str]:
    client = chromadb.PersistentClient(path="./chroma_store")
    collection = client.get_collection("rag_docs")
    ...

# ✅ Senior — accept the collection as a parameter, create it once at startup
def retrieve(query: str, collection: chromadb.Collection, k: int = TOP_K) -> list[str]:
    ...
```

---

## Quick Reference Checklist

Before committing any Python file, ask:

- [ ] Do all functions have type hints on parameters and return values?
- [ ] Are magic numbers replaced with named constants?
- [ ] Are secrets loaded from `.env`, never hardcoded?
- [ ] Does each function do one thing?
- [ ] Are files opened with `with` and `encoding="utf-8"`?
- [ ] Do errors raise specific exceptions with helpful messages?
- [ ] Are non-obvious lines explained with inline comments?

---

## Further Reading

- [PEP 8 — Official Python Style Guide](https://peps.python.org/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Real Python — Best Practices](https://realpython.com/tutorials/best-practices/)
- [Effective Python — Brett Slatkin](https://effectivepython.com/) *(book — worth buying)*
