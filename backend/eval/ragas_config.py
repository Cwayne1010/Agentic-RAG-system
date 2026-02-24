"""
RAGAS evaluation configuration.

Wires OpenRouter as the judge LLM so no separate API key is needed.
The judge model should be a capable model (gpt-4o-mini is a good default).
"""
import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

_judge_llm = ChatOpenAI(
    model=os.getenv("RAGAS_JUDGE_MODEL", "openai/gpt-4o-mini"),
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base="https://openrouter.ai/api/v1",
    default_headers={"HTTP-Referer": "http://localhost:5173"},
)

_embeddings = OpenAIEmbeddings(
    model=os.getenv("RAGAS_EMBEDDING_MODEL", "text-embedding-3-small"),
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

ragas_llm = LangchainLLMWrapper(_judge_llm)
ragas_embeddings = LangchainEmbeddingsWrapper(_embeddings)
