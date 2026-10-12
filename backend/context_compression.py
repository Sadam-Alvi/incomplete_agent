
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-small-en-v1.5")
def compress_context(context: str, question: str) -> str:
    chunks = context.split("\n\n---\n\n")

    if not chunks:
        return ""

    # Remove empty chunks and duplicates
    unique_chunks = []
    seen = set()

    for chunk in chunks:
        chunk = chunk.strip()
        normalized = " ".join(chunk.lower().split())

        if chunk and normalized not in seen:
            seen.add(normalized)
            unique_chunks.append(chunk)

    if not unique_chunks:
        return ""

    # Generate normalized embeddings
    question_embedding = model.encode(
        question,
        normalize_embeddings=True
    )

    chunk_embeddings = model.encode(
        unique_chunks,
        normalize_embeddings=True
    )

    # Calculate cosine similarity
    similarities = chunk_embeddings @ question_embedding

    # Keep relevant chunks
    threshold = 0.50
    relevant_chunks = [
        (chunk, float(score))
        for chunk, score in zip(unique_chunks, similarities)
        if score >= threshold
    ]

    # Rank by relevance
    relevant_chunks.sort(
        key=lambda item: item[1],
        reverse=True
    )

    return "\n\n---\n\n".join(
        chunk for chunk, _ in relevant_chunks
    )
