from sentence_transformers import SentenceTransformer
import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import json
from langchain_groq import ChatGroq
from pathlib import Path
import os
import time
import requests
from langchain_community.embeddings import HuggingFaceEmbeddings
load_dotenv()

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
POLL_INTERVAL = 1.5          # seconds between progress checks
MAX_WAIT_SECONDS = 180       # max time to wait for analysis

# Evaluation models (these do not replace your PagePal models)
evaluator_llm =ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.7
)


evaluator_embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)


test_cases_path = Path(__file__).parent / "test.json"

with open(test_cases_path, "r", encoding="utf-8") as file:
    test_cases = json.load(file)

# ------------------------------------------------------------------
# Helper functions that talk to the FastAPI endpoints
# ------------------------------------------------------------------
def start_analysis(url: str) -> str:
    """Call POST /analyze and return the task_id."""
    resp = requests.post(
        f"{API_BASE_URL}/analyze",
        json={"url": url},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["task_id"]


def wait_until_ready(task_id: str) -> dict:
    """
    Poll GET /progress/{task_id} until the analysis is finished
    or an error occurs / timeout is reached.
    """
    start = time.time()
    while True:
        resp = requests.get(f"{API_BASE_URL}/progress/{task_id}", timeout=15)
        resp.raise_for_status()
        status = resp.json()

        stage = status.get("stage", "")
        progress = status.get("progress", 0)
        message = status.get("message", "")
        error = status.get("error", False)

        print(f"  [{task_id[:8]}] stage={stage} progress={progress}% – {message}")

        if error:
            raise RuntimeError(f"Analysis failed: {message}")

        # Adjust the finished condition to whatever your process_page sets
        if stage in ("complete", "done", "ready") or progress >= 100:
            return status

        if time.time() - start > MAX_WAIT_SECONDS:
            raise TimeoutError(f"Analysis timed out after {MAX_WAIT_SECONDS}s")

        time.sleep(POLL_INTERVAL)


def ask_question(url: str, question: str) -> tuple[str, list]:
    """Call POST /ask and return (answer, contexts)."""
    resp = requests.post(
        f"{API_BASE_URL}/ask",
        json={"url": url, "question": question},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["answer"], data.get("context", [])


# ------------------------------------------------------------------
# Main evaluation loop
# ------------------------------------------------------------------
rows = []

for i, case in enumerate(test_cases, 1):
    url = case["url"]
    question = case["question"]
    ground_truth = case["ground_truth"]

    print(f"\n[{i}/{len(test_cases)}] Processing: {question[:80]}...")
    print(f"  URL: {url}")

    try:
        # 1. Start analysis
        task_id = start_analysis(url)
        print(f"  Started analysis → task_id={task_id}")

        # 2. Wait until the page is processed
        wait_until_ready(task_id)

        # 3. Ask the question
        answer, contexts = ask_question(url, question)

        # Ensure contexts is a list of strings (RAGAS expects list[str])
        if isinstance(contexts, str):
            contexts = [contexts]
        elif contexts is None:
            contexts = []

        rows.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": ground_truth,
        })
        print(f"  ✓ Answer received (length={len(answer)})")

    except Exception as e:
        print(f"  ✗ Failed: {e}")
        # Optionally still record a failed row so the dataset stays aligned
        rows.append({
            "question": question,
            "answer": f"ERROR: {str(e)}",
            "contexts": [],
            "ground_truth": ground_truth,
        })

# ------------------------------------------------------------------
# Run RAGAS evaluation
# ------------------------------------------------------------------
if not rows:
    raise RuntimeError("No successful test cases to evaluate.")

dataset = Dataset.from_list(rows)

results = evaluate(
    dataset=dataset,
    metrics=[
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ],
    llm=evaluator_llm,
    embeddings=evaluator_embeddings,
    raise_exceptions=False,   # continue even if some jobs fail
    batch_size=1,             # run one sample at a time (slower but stable)
)

# Display and save
print("\n" + "=" * 60)
print(results)

results_df = results.to_pandas()
results_df.to_csv("ragas_results.csv", index=False)

print("\nIndividual metric scores (mean):")
print(results_df.mean(numeric_only=True))

print("\nSaved results to ragas_results.csv")








