"""
Run RAGAS evaluation against the live pipeline.

Calls retrieval + LLM directly (bypasses HTTP auth) so you need a valid user_id.
Scores Faithfulness, Answer Relevancy, and Context Precision against the golden set.

Usage:
    cd backend && source venv/bin/activate
    python -m eval.run_eval \\
        --user-id <your-user-uuid> \\
        --golden-set eval/golden_set.json \\
        --output eval/results.json

To filter by tag:
    python -m eval.run_eval --user-id <uuid> --tags technical factual
"""
import asyncio
import argparse
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(override=True)

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

from app.services import retrieval_service
from app.services.openrouter_service import stream_chat, SYSTEM_PROMPT
from eval.ragas_config import ragas_llm, ragas_embeddings


async def run_pipeline(question: str, user_id: str) -> tuple[str, list[str]]:
    """Run one question through the live retrieval + LLM pipeline.
    Returns (answer, list_of_retrieved_chunk_texts).
    """
    chunks = await retrieval_service.search(question, user_id=user_id)

    context_block = ""
    if chunks:
        context_lines = "\n\n".join(
            f"[Chunk {c['chunk_index']} | similarity {c['similarity']:.2f}]: {c['content']}"
            for c in chunks
        )
        context_block = f"\n\n<retrieved_context>\n{context_lines}\n</retrieved_context>"

    # Use a minimal system prompt for eval — the full SYSTEM_PROMPT includes
    # tool-calling instructions that cause the model to emit tool-call XML
    # even with use_tools=False, which tanks faithfulness and relevancy scores.
    eval_system = (
        "You are a helpful assistant. Answer the user's question using only "
        "the provided context. If the context does not contain the answer, "
        "say you don't know."
    )
    messages = [
        {"role": "system", "content": eval_system + context_block},
        {"role": "user", "content": question},
    ]

    answer_parts = []
    async for event in stream_chat(messages, use_tools=False):
        if event["type"] == "delta":
            answer_parts.append(event["content"])

    answer = "".join(answer_parts)
    retrieved_texts = [c["content"] for c in chunks] if chunks else [""]
    return answer, retrieved_texts


_ALL_METRICS = {
    "faithfulness": faithfulness,
    "answer_relevancy": answer_relevancy,
    "context_precision": context_precision,
    "context_recall": context_recall,
}


async def gather_pipeline_results(golden_set: list[dict], user_id: str):
    questions, answers, contexts, ground_truths = [], [], [], []
    for i, item in enumerate(golden_set):
        print(f"  [{i + 1}/{len(golden_set)}] {item['question'][:70]}...")
        answer, retrieved = await run_pipeline(item["question"], user_id)
        questions.append(item["question"])
        answers.append(answer)
        contexts.append(retrieved)
        ground_truths.append(item["ground_truth"])
    return questions, answers, contexts, ground_truths


def main(user_id: str, golden_set_path: str, output_path: str, tags_filter: list[str], limit: int = 0, metric_names: list[str] = None):
    with open(golden_set_path) as f:
        golden_set = json.load(f)

    golden_set = [q for q in golden_set if not q["id"].startswith("gs-example")]

    if tags_filter:
        golden_set = [q for q in golden_set if any(t in q.get("tags", []) for t in tags_filter)]

    if not golden_set:
        print("No questions to evaluate. Generate a golden set first with generate_golden_set.py")
        return

    if limit and limit < len(golden_set):
        step = len(golden_set) / limit
        golden_set = [golden_set[int(i * step)] for i in range(limit)]

    print(f"Evaluating {len(golden_set)} questions...")

    # Gather pipeline results in async context, then exit it cleanly before RAGAS
    questions, answers, contexts, ground_truths = asyncio.run(
        gather_pipeline_results(golden_set, user_id)
    )

    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    active_metrics = [_ALL_METRICS[m] for m in (metric_names or list(_ALL_METRICS))]
    needs_embeddings = any(m in active_metrics for m in [answer_relevancy, context_recall])

    print(f"\nRunning RAGAS scoring with metrics: {metric_names or list(_ALL_METRICS)}")
    result = evaluate(
        dataset,
        metrics=active_metrics,
        llm=ragas_llm,
        embeddings=ragas_embeddings if needs_embeddings else None,
    )

    df = result.to_pandas()
    metric_scores = {col: float(df[col].mean()) for col in df.columns if col in _ALL_METRICS}
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "n_questions": len(golden_set),
        "metrics": metric_scores,
        "per_question": df.to_dict(orient="records"),
    }

    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults:")
    for name, score in summary["metrics"].items():
        print(f"  {name}: {score:.3f}")
    print(f"\nFull results → {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation against the live pipeline")
    parser.add_argument("--user-id", required=True, help="Supabase user UUID")
    parser.add_argument("--golden-set", default="eval/golden_set.json")
    parser.add_argument("--output", default="eval/results.json")
    parser.add_argument("--tags", nargs="*", default=[], help="Filter questions by tag")
    parser.add_argument("--limit", type=int, default=0, help="Sample N questions evenly from the golden set (0 = all)")
    parser.add_argument("--metrics", nargs="*", default=None, choices=list(_ALL_METRICS), help="Metrics to run (default: all)")
    args = parser.parse_args()

    main(args.user_id, args.golden_set, args.output, args.tags, args.limit, args.metrics)
