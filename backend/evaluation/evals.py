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
from langchain_groq import ChatGroq
from light_embed import TextEmbedding
from langchain_core.embeddings import Embeddings


# ==========================================
# 1. CONFIGURATION
# ==========================================


# 1. Load your API key from the .env file
load_dotenv()

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.7)


API_URL = "http://localhost:8000"
TEST_FILE = Path(__file__).parent / "test.json"

POLL_INTERVAL = 1.5
MAX_WAIT_SECONDS = 180

# ==========================================
# 2. EVALUATION MODELS
# ==========================================
'''`Error, Embeddings has no attribute embed_documents` thats why using this class'''


class RagasEmbeddings(Embeddings):
    def __init__(self):
        self.model_name = "onnx-models/all-MiniLM-L6-v2-onnx"
        self.encoder = TextEmbedding(
            model_name_or_path=self.model_name
        )

        # Required by RAGAS usage tracking
        self.model = self.model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.encoder.encode(texts)
        return [
            v.tolist() if hasattr(v, "tolist") else list(v)
            for v in vectors
        ]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


# 1. Create your embedding object
embedding_object = RagasEmbeddings()

# 2. Wrap it for RAGAS
embeddings = LangchainEmbeddingsWrapper(embedding_object)




# ==========================================
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
        answer_correctness,
    ],
    llm=llm,
    embeddings=embeddings,
    raise_exceptions=True,
    batch_size=10,
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
