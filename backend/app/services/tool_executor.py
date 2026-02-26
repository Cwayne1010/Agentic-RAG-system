import json
import os
from supabase import create_client
from app.services import retrieval_service, web_search_service, text_to_sql_service

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


async def execute_tool(tool_name: str, arguments: str, user_id: str) -> dict:
    """
    Execute a tool by name. Returns a result dict that includes:
      - tool_name: str
      - tool_message: str   (the string to pass back to the LLM as the tool result)
      - sse_event: dict     (extra info to stream to the frontend)

    Handles errors gracefully — returns error info rather than raising.
    """
    try:
        args = json.loads(arguments)
    except json.JSONDecodeError:
        args = {}

    if tool_name == "retrieve_documents":
        query = args.get("query", "")
        doc_type = args.get("doc_type_filter")
        chunks = await retrieval_service.search(query, doc_type_filter=doc_type, user_id=user_id)
        sources = list({c["doc_filename"] for c in chunks}) if chunks else []

        if chunks:
            context = "\n\n".join(
                "[Source: {fn} | Chunk {idx} | score {sim:.2f}]: {content}".format(
                    fn=c["doc_filename"],
                    idx=c["chunk_index"],
                    sim=c["similarity"],
                    content=c["content"],
                )
                for c in chunks
            )
        else:
            # No chunks found for this query — list available documents so the LLM
            # can make a more targeted follow-up query.
            docs_result = supabase.table("documents").select("filename").eq(
                "status", "completed"
            ).eq("user_id", user_id).execute()
            doc_names = [d["filename"] for d in (docs_result.data or [])]
            if doc_names:
                context = (
                    f"No chunks matched the query '{query}' with sufficient similarity. "
                    f"Available documents: {', '.join(doc_names)}. "
                    f"Try a more specific query about a topic or section in one of these documents."
                )
            else:
                context = "No documents have been indexed yet."

        return {
            "tool_name": tool_name,
            "tool_message": context,
            "sse_event": {
                "type": "tool_result",
                "tool_name": tool_name,
                "chunk_count": len(chunks),
                "sources": sources,
            },
        }

    elif tool_name == "query_database":
        question = args.get("question", "")
        try:
            result = await text_to_sql_service.text_to_sql(question, user_id)
            rows_text = json.dumps(result["results"], indent=2) if result["results"] else "No results."
            message = f"SQL: {result['sql']}\n\nResults ({result['row_count']} rows):\n{rows_text}"
            return {
                "tool_name": tool_name,
                "tool_message": message,
                "sse_event": {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "row_count": result["row_count"],
                    "sql": result["sql"],
                },
            }
        except Exception as e:
            import traceback; traceback.print_exc()
            return {
                "tool_name": tool_name,
                "tool_message": f"Database query failed: {e}",
                "sse_event": {"type": "tool_result", "tool_name": tool_name, "error": str(e)},
            }

    elif tool_name == "web_search":
        query = args.get("query", "")
        try:
            results = await web_search_service.web_search(query)
            context = "\n\n".join(
                f"[{r['title']}]({r['url']})\n{r['body']}"
                for r in results
            ) if results else "No web results found."
            return {
                "tool_name": tool_name,
                "tool_message": context,
                "sse_event": {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "result_count": len(results),
                    "results": [{"title": r["title"], "url": r["url"]} for r in results],
                },
            }
        except Exception as e:
            return {
                "tool_name": tool_name,
                "tool_message": f"Web search failed: {e}",
                "sse_event": {"type": "tool_result", "tool_name": tool_name, "error": str(e)},
            }

    else:
        return {
            "tool_name": tool_name,
            "tool_message": f"Unknown tool: {tool_name}",
            "sse_event": {"type": "tool_result", "tool_name": tool_name, "error": "unknown tool"},
        }
