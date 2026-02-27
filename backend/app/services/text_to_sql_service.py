import json
import os
import re
from openai import AsyncOpenAI
from supabase import create_client
from app.services.settings_service import get_settings

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

# Schema exposed to the LLM — only tables the user owns data in
_SCHEMA = """
Tables (all have a user_id column for data isolation):

documents
  id uuid, user_id uuid, filename text, file_size integer (bytes),
  mime_type text, status text ('pending'|'processing'|'completed'|'failed'),
  created_at timestamptz,
  metadata jsonb (keys: doc_type, topics, language, summary),
  chunk_count integer

document_chunks
  id uuid, document_id uuid, user_id uuid, chunk_index integer, content text

conversations
  id uuid, user_id uuid, title text, created_at timestamptz, updated_at timestamptz

messages
  id uuid, conversation_id uuid, user_id uuid,
  role text ('user'|'assistant'), content text, created_at timestamptz
"""


async def text_to_sql(question: str, user_id: str) -> dict:
    """
    Convert a natural language question to SQL, execute it, and return results.

    Returns:
        {"sql": str, "explanation": str, "results": list[dict], "row_count": int}

    Raises:
        ValueError: if generated SQL is not a SELECT statement or doesn't reference user_id
        RuntimeError: if Supabase execution fails
    """
    prompt = [
        {
            "role": "system",
            "content": (
                f"You are a SQL expert. Generate a PostgreSQL SELECT query to answer the user's question.\n\n"
                f"Schema:\n{_SCHEMA}\n\n"
                f"Rules:\n"
                f"1. Only generate SELECT statements — never INSERT, UPDATE, DELETE, DROP, etc.\n"
                f"2. ALWAYS include `user_id = '{user_id}'` in the WHERE clause for every table you query.\n"
                f"3. Use single quotes for the user_id literal.\n"
                f"4. Limit results to 50 rows maximum.\n"
                f"5. Return JSON with keys: sql (string), explanation (string)."
            ),
        },
        {"role": "user", "content": question},
    ]

    settings = get_settings()
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )
    response = await client.chat.completions.create(
        model=settings["chat_model"],
        messages=prompt,
        extra_headers={"HTTP-Referer": os.getenv("APP_URL", "http://localhost:5173")},
    )
    raw = response.choices[0].message.content or ""
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    try:
        structured = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned non-JSON response: {raw[:200]}") from e

    sql = structured.get("sql", "").strip().rstrip(";").strip()
    explanation = structured.get("explanation", "")

    # Validate SELECT-only
    if not sql.lower().startswith("select"):
        raise ValueError(f"Generated SQL is not a SELECT statement: {sql[:100]}")

    # Validate user_id is referenced
    if user_id not in sql:
        raise ValueError("Generated SQL does not reference the user_id — unsafe to execute")

    # Execute via safe RPC
    try:
        result = supabase.rpc(
            "execute_user_sql",
            {"sql_query": sql, "p_user_id": user_id},
        ).execute()
        rows = result.data or []
        if isinstance(rows, list) is False:
            rows = [rows] if rows else []
    except Exception as e:
        raise RuntimeError(f"SQL execution failed: {e}") from e

    return {
        "sql": sql,
        "explanation": explanation,
        "results": rows,
        "row_count": len(rows),
    }
