import json
import os

from openai import AsyncOpenAI

from app.services.settings_service import get_settings

_ls_enabled = None


def _langsmith_enabled() -> bool:
    global _ls_enabled
    if _ls_enabled is None:
        _ls_enabled = bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))
    return _ls_enabled


# Fallback schema used when app_settings.metadata_schema is empty
_DEFAULT_SCHEMA: list[dict] = [
    {"name": "doc_type", "type": "string", "description": "Document type", "allowed_values": ["contract", "report", "email", "memo", "technical", "article", "other"], "nullable": False},
    {"name": "language", "type": "string", "description": "ISO 639-1 language code", "nullable": False},
    {"name": "topics", "type": "array", "description": "Topics from controlled vocabulary", "nullable": False},
    {"name": "summary", "type": "string", "description": "1-2 sentence document summary", "nullable": False},
    {"name": "entities", "type": "array", "description": "Named people, organisations, places (max 10)", "nullable": False},
    {"name": "date", "type": "date", "description": "ISO 8601 document date if found", "nullable": True},
]

# Keep for backward-compat with settings.py import
_TOPIC_VOCABULARY = [
    "legal", "finance", "technology", "operations", "hr",
    "sales-marketing", "compliance", "strategy", "research", "communications",
]


def _build_default(schema: list[dict]) -> dict:
    type_defaults = {"array": [], "string": "", "date": None}
    return {f["name"]: type_defaults.get(f["type"], None) for f in schema}


def _build_system_prompt(schema: list[dict], vocabulary: list[str]) -> str:
    lines = []
    for f in schema:
        line = f'  "{f["name"]}": {f["type"]}'
        if f["name"] == "topics":
            vocab = vocabulary or f.get("allowed_values", [])
            line += f" — select ALL that apply from: {vocab} (do not invent new values)"
        elif f.get("allowed_values"):
            line += f" — one of: {f['allowed_values']}"
        if f.get("description"):
            line += f" — {f['description']}"
        if f.get("nullable"):
            line += " (or null if not found)"
        lines.append(line)
    return (
        "You are a document analysis assistant. Extract structured metadata from the provided document text. "
        "Return ONLY a valid JSON object with exactly these fields:\n"
        + "\n".join(lines)
        + "\nDo not include any other text outside the JSON object."
    )


def _validate(raw_dict: dict, schema: list[dict], vocabulary: list[str]) -> dict:
    """Coerce and validate a raw parsed dict against the schema. Returns a clean dict."""
    result = {}
    for f in schema:
        name = f["name"]
        ftype = f["type"]
        nullable = f.get("nullable", False)
        val = raw_dict.get(name)

        if ftype == "array":
            result[name] = val if isinstance(val, list) else []
            if name == "topics" and vocabulary:
                vocab_set = set(vocabulary)
                result[name] = [t for t in result[name] if t in vocab_set]
        elif ftype in ("string", "date"):
            if val is None and nullable:
                result[name] = None
            else:
                result[name] = str(val) if val is not None else ""
        else:
            result[name] = val
    return result


def _get_client(settings: dict) -> AsyncOpenAI:
    api_key = settings.get("llm_api_key") or os.getenv("OPENROUTER_API_KEY", "")
    base_url = settings.get("llm_base_url") or "https://openrouter.ai/api/v1"
    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=30.0)


async def extract_metadata(text: str) -> dict:
    """Extract structured metadata from document text using the configured LLM.

    Uses the first 2000 characters of the document to keep costs low.
    Returns a safe default dict on any failure.
    """
    sample = text[:2000].strip()

    try:
        settings = get_settings()
        schema = settings.get("metadata_schema") or _DEFAULT_SCHEMA
        vocabulary = settings.get("topic_vocabulary") or []
        default = _build_default(schema)

        if not sample:
            return default

        client = _get_client(settings)
        model = settings["chat_model"]
        system_prompt = _build_system_prompt(schema, vocabulary)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Document text:\n\n{sample}"},
        ]

        run = None
        if _langsmith_enabled():
            from langsmith.run_trees import RunTree
            run = RunTree(
                name="extract_metadata",
                run_type="llm",
                inputs={
                    "text_sample": sample,
                    "metadata_schema": schema,
                    "topic_vocabulary": vocabulary,
                    "model": model,
                },
                session_name=os.getenv("LANGCHAIN_PROJECT", "default"),
            )
            run.post()

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                extra_headers={"HTTP-Referer": os.getenv("APP_URL", "http://localhost:5173")},
            )

            raw = response.choices[0].message.content or "{}"
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            parsed = json.loads(raw)
            result = _validate(parsed, schema, vocabulary)

            if run:
                run.end(outputs={"metadata": result})
                run.patch()

            return result

        except Exception as e:
            if run:
                run.end(error=str(e))
                run.patch()
            raise

    except Exception:
        try:
            settings = get_settings()
            schema = settings.get("metadata_schema") or _DEFAULT_SCHEMA
            return _build_default(schema)
        except Exception:
            return _build_default(_DEFAULT_SCHEMA)
