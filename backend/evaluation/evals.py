import os
import json
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
    answer_correctness
)
# from langchain_groq import ChatGroq
from langchain_openrouter import ChatOpenRouter
from light_embed import TextEmbedding
from langchain_core.embeddings import Embeddings
from ragas.llms import LangchainLLMWrapper

# ==========================================
# 1. CONFIGURATION
# ==========================================

load_dotenv()

model = ChatOpenRouter(
    model="nvidia/nemotron-3-ultra-550b-a55b:free",
    temperature=0.8,
)
llm = LangchainLLMWrapper(model)
API_URL = "http://localhost:8000"
TEST_FILE = Path(__file__).parent / "test.json"

POLL_INTERVAL = 1.5
MAX_WAIT_SECONDS = 180

# ==========================================
# 2. EVALUATION MODELS
# ==========================================
'''`light_embed has no attribute embed documents` thats why using this class'''
class RagasEmbeddings(Embeddings):
    def __init__(self):
        self.model_name = "onnx-models/all-MiniLM-L6-v2-onnx"
        self.encoder = TextEmbedding(
            model_name_or_path=self.model_name
        )
        # Required by Ragas usage tracking/metadata
        self.model = self.model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.encoder.encode(texts)
        return [
            v.tolist() if hasattr(v, "tolist") else list(v)
            for v in vectors
        ]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


# Initialize and wrap for RAGAS
embedding_object = RagasEmbeddings()
# Wrapping it with with ragas wrapper so that it can be used with ragas
embeddings = LangchainEmbeddingsWrapper(embedding_object)


# ==========================================
# 3. LOAD TEST CASES
# ==========================================

with open(TEST_FILE, "r", encoding="utf-8") as file:
    test_cases = json.load(file)


# ==========================================
# 4. API HELPER FUNCTIONS
# ==========================================

def ask_question(url, question):
    response = requests.post(
        f"{API_URL}/evaluate/answer",
        json={
            "url": url,
            "question": question,
            'session_id': '1234'
        },
        timeout=60
    )
    response.raise_for_status()

    data = response.json()
    answer = data["answer"]
    contexts = data.get("context", [])

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
        answer, contexts = ask_question(url, question)
       
        rows.append({
            "user_input": question,       # Ragas v0.2+ uses user_input instead of question
            "response": answer,           # Ragas v0.2+ uses response instead of answer
            "retrieved_contexts": contexts,# Ragas v0.2+ uses retrieved_contexts instead of contexts
            "reference": ground_truth     # Ragas v0.2+ uses reference instead of ground_truth
        })

        print("Answer received successfully")

    except Exception as error:
        print(f"Test failed: {error}")
        rows.append({
            "user_input": question,
            "response": "",
            "retrieved_contexts": [],
            "reference": ground_truth
        })

# ==========================================
# 6. RUN RAGAS EVALUATION
# ==========================================

if not rows:
    raise RuntimeError("No test cases were processed")

# Exclude failed API calls from metric calculations.
valid_rows = [
    row for row in rows
    if row["response"] and row["retrieved_contexts"]
]

if not valid_rows:
    raise RuntimeError(
        "No successful test cases with answers and contexts"
    )

dataset = Dataset.from_list(valid_rows)

# Define metrics array
metrics = [
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_correctness,
]

# Correct Ragas 0.2+ syntax: Init metrics with LLM and Embeddings first
for metric in metrics:
    metric.llm = llm
    metric.embeddings = embeddings

results = evaluate(
    dataset=dataset,
    batch_size=1,
    metrics=metrics,
    # llm and embeddings are removed from top-level arguments here
)

# ==========================================
# 7. SAVE RESULTS
# ==========================================
results_df = results.to_pandas().round(2)
results_df.to_csv("ragas_results.csv", index=False)

print("\n========== RAGAS RESULTS ==========")
print(results_df)

print("\n========== AVERAGE SCORES ==========")
print(results_df.mean(numeric_only=True))

print("\nResults saved to ragas_results.csv")
