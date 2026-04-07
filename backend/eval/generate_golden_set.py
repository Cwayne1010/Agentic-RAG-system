"""
Generate a golden set of 10 varied Q&A pairs from uploaded document chunks.

Usage:
    cd backend && source venv/bin/activate
    python -m eval.generate_golden_set --user-id <uuid>
"""
import asyncio
import argparse
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)

from openai import AsyncOpenAI
from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
openrouter = AsyncOpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")

_PROMPT = """\
You are a test-set generator for evaluating RAG systems.

Given the document chunks below, generate exactly 40 question-answer pairs that are varied in type:
- 8 factual recall (specific facts, dates, names)
- 8 definitional (what is X, what does X mean)
- 8 cause-and-effect or procedural (why/how)
- 8 comparative or analytical (differences, relationships)
- 8 summary or broad (covering multiple ideas)

Rules:
- Every question must be answerable from the provided chunks alone
- Answers should be concise but complete

Return a JSON array only, no other text:
[{{"question": "...", "answer": "..."}}, ...]

Chunks:
{chunks}
"""


async def main(user_id: str, output: str, model: str):
    result = (
        supabase.table("document_chunks")
        .select("id, document_id, chunk_index, content")
        .eq("user_id", user_id)
        .order("document_id")
        .limit(100)
        .execute()
    )
    chunks = result.data or []

    if not chunks:
        print("No chunks found. Upload and ingest a document first.")
        return

    combined = "\n\n---\n\n".join(
        f"[doc={c['document_id'][:8]} chunk={c['chunk_index']}]\n{c['content']}" for c in chunks
    )

    print(f"Generating 40 varied Q&A pairs from {len(chunks)} chunks using {model}...")

    resp = await openrouter.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": _PROMPT.format(chunks=combined)}],
        extra_headers={"HTTP-Referer": "http://localhost:5173"},
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    pairs = json.loads(raw)
    golden = [
        {
            "id": f"gs-{i:02d}",
            "question": p["question"],
            "ground_truth": p["answer"],
        }
        for i, p in enumerate(pairs)
    ]

    with open(output, "w") as f:
        json.dump(golden, f, indent=2)

    print(f"Saved {len(golden)} pairs → {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--output", default="eval/golden_set.json")
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    args = parser.parse_args()

    asyncio.run(main(args.user_id, args.output, args.model))
