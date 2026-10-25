import os
import json
import time
import requests
from ragas.embeddings import LangchainEmbeddingsWrapper
from pathlib import Path
from dotenv import load_dotenv
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from langchain_groq import ChatGroq
from light_embed import TextEmbedding
from langchain_core.embeddings import Embeddings
from langsmith import Client
from uuid import uuid4
from datetime import datetime, timezone
# ==========================================
# 1. CONFIGURATION
# ==========================================

load_dotenv()

API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_FILE = Path(__file__).parent / "test.json"

POLL_INTERVAL = 1.5
MAX_WAIT_SECONDS = 180

# ==========================================
# 2. EVALUATION MODELS
# ==========================================

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    timeout=60,
    max_retries=2)


class RagasEmbeddings(Embeddings):
    def __init__(self):
        self.model = TextEmbedding(
            model_name_or_path="onnx-models/all-MiniLM-L6-v2-onnx"
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = list(self.model.encode(texts))
        return [vector.tolist() if hasattr(vector, "tolist") else list(vector)
                for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


embeddings = RagasEmbeddings()

# ==========================================
# 3. LOAD TEST CASES
# ==========================================

with open(TEST_FILE, "r", encoding="utf-8") as file:
    test_cases = json.load(file)

# ==========================================
# 4. API HELPER FUNCTIONS
# ==========================================

def start_analysis(url):
    response = requests.post(
        f"{API_URL}/analyze",
        json={"url": url},
        timeout=30
    )
    response.raise_for_status()
    return response.json()["task_id"]


def wait_for_analysis(task_id):
    start_time = time.time()

    while time.time() - start_time < MAX_WAIT_SECONDS:
        response = requests.get(
            f"{API_URL}/progress/{task_id}",
            timeout=15
        )
        response.raise_for_status()

        status = response.json()

        print(
            f"Analysis: {status.get('stage')} | "
            f"{status.get('progress', 0)}%"
        )

        if status.get("error") or status.get("stage") == "failed":
            raise RuntimeError(
                status.get("message", "Analysis failed")
            )

        if (
            status.get("stage") in ("complete", "done", "ready")
            or status.get("progress", 0) >= 100
        ):
            return

        time.sleep(POLL_INTERVAL)

    raise TimeoutError("Page analysis took too long")


def ask_question(url, question):
    response = requests.post(
        f"{API_URL}/ask",
        json={
            "url": url,
            "question": question,
            'session_id':'1234'
        },
        timeout=60
    )
    response.raise_for_status()

    data = response.json()

    answer = data["answer"]
    contexts = data.get("context", [])

    # RAGAS expects a list of context strings.
    if isinstance(contexts, str):
        contexts = [contexts]
    elif contexts is None:
        contexts = []

    return answer, contexts


# ==========================================
# 5. RUN TEST CASES
# ==========================================

rows = []

for number, case in enumerate(test_cases, start=1):
    url = case["url"]
    question = case["question"]
    ground_truth = case["ground_truth"]

    print(f"\nTest {number}/{len(test_cases)}: {question}")

    try:
        # Analyze the webpage or video.
        task_id = start_analysis(url)

        # Wait until processing is finished.
        wait_for_analysis(task_id)

        # Get the answer and retrieved context.
        answer, contexts = ask_question(url, question)

        rows.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": ground_truth
        })

        print("Answer received successfully")

    except Exception as error:
        print(f"Test failed: {error}")

        # Keep the failure visible instead of scoring it as a valid answer.
        rows.append({
            "question": question,
            "answer": "",
            "contexts": [],
            "ground_truth": ground_truth
        })

# ==========================================
# 6. RUN RAGAS EVALUATION
# ==========================================

if not rows:
    raise RuntimeError("No test cases were processed")

# Exclude failed API calls from metric calculations.
valid_rows = [
    row for row in rows
    if row["answer"] and row["contexts"]
]

if not valid_rows:
    raise RuntimeError(
        "No successful test cases with answers and contexts"
    )

dataset = Dataset.from_list(valid_rows)

results = evaluate(
    dataset=dataset,
    metrics=[
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ],
    llm=llm,
    embeddings=embeddings,
    raise_exceptions=False,
    batch_size=1
)

# ==========================================
# 7. SAVE RESULTS
# ==========================================

results_df = results.to_pandas()

results_df.to_csv("ragas_results.csv", index=False)

print("\n========== RAGAS RESULTS ==========")
print(results_df)

print("\n========== AVERAGE SCORES ==========")
print(results_df.mean(numeric_only=True))

print("\nResults saved to ragas_results.csv")
