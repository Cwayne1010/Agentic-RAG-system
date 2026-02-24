"""
SQL Template Architecture — pre-built for Module 7 text-to-SQL tool.

The LLM never writes SQL. It picks a template from the allowlist and fills in
parameters only. execute_query() validates, binds safely, and calls the
corresponding Supabase RPC (one RPC per template, all read-only + timeouts).

Usage in Module 7 chat.py tool handler:
    call = TemplateCall(**json.loads(tc["arguments"]))
    result = await execute_query(call.template_name, call.params, str(user.id))
    tool_content = json.dumps({"rows": result.rows, "row_count": result.row_count})

Supabase setup required before wiring in — see supabase/migrations/ for the
per-template RPC functions (rpc_count_documents, rpc_list_documents, etc.).
"""
import os
from pydantic import BaseModel
from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


# ── Pydantic Models ──────────────────────────────────────────────────────────

class TemplateCall(BaseModel):
    """Structured output the LLM returns when it selects a SQL template."""
    template_name: str
    params: dict
    reasoning: str  # LLM explains its choice — useful for debugging


class QueryResult(BaseModel):
    template_name: str
    params: dict
    rows: list[dict]
    row_count: int


# ── Template Registry ────────────────────────────────────────────────────────
#
# Each entry maps a template_name to:
#   description : shown to the LLM in SQL_QUERY_TOOL schema
#   params      : list of param names the LLM must provide
#   rpc         : Supabase RPC function name to call
#   rpc_params  : function that builds the RPC kwargs from (params, user_id)

TEMPLATES: dict[str, dict] = {

    "count_documents": {
        "description": "Count how many documents the user has uploaded.",
        "params": [],
        "rpc": "rpc_count_documents",
        "rpc_params": lambda p, uid: {"p_user_id": uid},
    },

    "list_documents": {
        "description": "List all uploaded documents with their status and chunk count.",
        "params": [],
        "rpc": "rpc_list_documents",
        "rpc_params": lambda p, uid: {"p_user_id": uid},
    },

    "count_chunks_by_document": {
        "description": "Count how many chunks each document was split into.",
        "params": [],
        "rpc": "rpc_count_chunks_by_document",
        "rpc_params": lambda p, uid: {"p_user_id": uid},
    },

    "find_documents_by_status": {
        "description": (
            "Find documents with a specific ingestion status. "
            "Valid statuses: pending, processing, completed, failed."
        ),
        "params": ["status"],
        "rpc": "rpc_find_documents_by_status",
        "rpc_params": lambda p, uid: {"p_user_id": uid, "p_status": p["status"]},
    },

    "search_chunks_by_keyword": {
        "description": "Full-text keyword search across document chunks (case-insensitive).",
        "params": ["keyword"],
        "rpc": "rpc_search_chunks_by_keyword",
        "rpc_params": lambda p, uid: {"p_user_id": uid, "p_keyword": p["keyword"]},
    },

    "get_recent_conversations": {
        "description": "List the user's most recent conversations.",
        "params": [],
        "rpc": "rpc_get_recent_conversations",
        "rpc_params": lambda p, uid: {"p_user_id": uid},
    },

    "count_messages_in_conversation": {
        "description": "Count messages in a conversation identified by a partial title match.",
        "params": ["title_fragment"],
        "rpc": "rpc_count_messages_in_conversation",
        "rpc_params": lambda p, uid: {"p_user_id": uid, "p_title_fragment": p["title_fragment"]},
    },

    "storage_summary": {
        "description": "Show total storage used by completed documents (count, total bytes, average size).",
        "params": [],
        "rpc": "rpc_storage_summary",
        "rpc_params": lambda p, uid: {"p_user_id": uid},
    },
}

ALLOWED_TEMPLATES = set(TEMPLATES.keys())


# ── OpenRouter Tool Definition ───────────────────────────────────────────────
# Add this to openrouter_service.py alongside RETRIEVAL_TOOL when wiring in Module 7.

SQL_QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "query_database",
        "description": (
            "Query the user's data using safe predefined templates. "
            "Use this for questions about the user's documents, conversations, "
            "storage usage, or ingestion status. "
            "Do NOT use for reading document content — use retrieve_documents for that."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "enum": sorted(ALLOWED_TEMPLATES),
                    "description": (
                        "The query template to run. Available templates:\n"
                        + "\n".join(
                            f"  {name}: {t['description']} "
                            f"(params: {t['params'] if t['params'] else 'none'})"
                            for name, t in sorted(TEMPLATES.items())
                        )
                    ),
                },
                "params": {
                    "type": "object",
                    "description": "Parameters required by the chosen template.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of why this template was chosen.",
                },
            },
            "required": ["template_name", "params", "reasoning"],
        },
    },
}


# ── Execution ────────────────────────────────────────────────────────────────

async def execute_query(template_name: str, params: dict, user_id: str) -> QueryResult:
    """
    Validate the template, bind params safely, and call the Supabase RPC.

    user_id is always injected server-side — never accepted from the LLM.
    Raises ValueError for unknown templates or missing required params.
    """
    if template_name not in ALLOWED_TEMPLATES:
        raise ValueError(
            f"Unknown template '{template_name}'. "
            f"Allowed: {sorted(ALLOWED_TEMPLATES)}"
        )

    template = TEMPLATES[template_name]

    # Validate required params are present
    for required in template["params"]:
        if required not in params:
            raise ValueError(
                f"Template '{template_name}' requires param '{required}' "
                f"but it was not provided. LLM params received: {list(params.keys())}"
            )

    # Build RPC kwargs — user_id is always injected here, never from LLM
    rpc_kwargs = template["rpc_params"](params, user_id)

    result = supabase.rpc(template["rpc"], rpc_kwargs).execute()
    rows = result.data or []

    return QueryResult(
        template_name=template_name,
        params=params,
        rows=rows,
        row_count=len(rows),
    )
