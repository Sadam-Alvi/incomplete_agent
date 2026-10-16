import numpy as np
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
load_dotenv()
model = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

def compress_context(context: list[str], question: str) -> list[str]:
    if not context:
        return []

    # Remove duplicate chunks while preserving order
    unique_chunks = list(dict.fromkeys(context))

    # Generate embeddings
    question_embedding = model.embed_query(question)
    chunk_embeddings = model.embed_documents(unique_chunks)

    # Convert lists to NumPy arrays
    question_embedding = np.asarray(question_embedding, dtype=np.float32)
    chunk_embeddings = np.asarray(chunk_embeddings, dtype=np.float32)

    # Normalize embeddings for cosine similarity
    question_embedding /= (
        np.linalg.norm(question_embedding) + 1e-12
    )
    chunk_embeddings /= (
        np.linalg.norm(chunk_embeddings, axis=1, keepdims=True) + 1e-12
    )

    # Calculate cosine similarities
    similarities = chunk_embeddings @ question_embedding

    # Select the top 5 most relevant chunks
    top_k = min(5, len(unique_chunks))
    top_indices = np.argsort(similarities)[-top_k:][::-1]

    compressed_context = [
        unique_chunks[i] for i in top_indices
    ]

    return compressed_context