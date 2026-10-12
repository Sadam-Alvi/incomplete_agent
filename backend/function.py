import trafilatura
from langchain_text_splitters import RecursiveCharacterTextSplitter
from context_compression import *
# from langchain_experimental.text_splitter import SemanticChunker
from sentence_transformers import SentenceTransformer
import chromadb
import uuid
from urllib.parse import urlparse
from threading import Lock
from llm import *
from youtube_transcript import *

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

client = chromadb.PersistentClient(path="./database")
collection = client.get_or_create_collection(
    name="page_data",
    metadata={"hnsw:space": "cosine"}
)

tasks = {}
tasks_lock = Lock()

def get_content_from_url(url: str) -> str:
    if not url or not url.strip():
        raise ValueError("URL cannot be empty.")

    url = url.strip()
    hostname = (urlparse(url).hostname or "").lower()

    

    # Detect YouTube URLs, including youtu.be links.
    is_youtube = (
        hostname == "youtu.be"
        or hostname.endswith("youtube.com")
        or hostname.endswith("youtube-nocookie.com")
    )

    if is_youtube:
        text = get_youtube_transcript(url)
        

    else:
        downloaded = trafilatura.fetch_url(url)

        if not downloaded:
            raise ValueError("Could not download webpage.")

        text = trafilatura.extract(downloaded)
        

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Could not extract readable content from the URL.")

    text = text.strip()
    return clean_text(text)





def preprocess_data(content: str, url: str) -> list:
    text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,        # Maximum number of characters per chunk
    chunk_overlap=40,      # Number of characters to overlap between chunks
    length_function=len,   # How to measure chunk size
    is_separator_regex=False,
)
    chunks = text_splitter.split_text(content)
    if not chunks:
        return []
    
    embeddings = model.encode(
        chunks,
        normalize_embeddings=True,
        convert_to_numpy=True
    ).tolist()



    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"url": url, "chunk_index": i} for i in range(len(chunks))]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,   # important for some chromadb versions
        metadatas=metadatas
    )
    return ids

def update_progress(task_id, stage, percent, message):
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id].update({
                "stage": stage,
                "progress": percent,
                "message": message,
                "error": False
            })

def process_page(task_id, url):
    try:
        update_progress(task_id, "reading", 10, "Reading webpage...")
        content = get_content_from_url(url)
        print(content)
        update_progress(task_id, "extracting", 35, "Extracting readable text...")
        if not content.strip():
            raise ValueError("No readable webpage content found.")

        update_progress(task_id, "embedding", 55, "Generating embeddings and saving...")
        ids = preprocess_data(content, url)

        if not ids:
            raise ValueError("No text chunks were extracted.")

        with tasks_lock:
            tasks[task_id].update({
                "stage": "complete",
                "progress": 100,
                "message": "Analysis complete!",
                "error": False,
                "result": {
                    "url": url,
                    "chunks_stored": len(ids),
                },
            })

    except Exception as error:
        with tasks_lock:
            if task_id in tasks:
                tasks[task_id].update({
                    "stage": "error",
                    "progress": 0,
                    "message": str(error),
                    "error": True,
                })

def answer_the_query(question: str, url: str) -> str:
    question = rewrite_question(question)
    embedded_query = model.encode(question,normalize_embeddings=True)
    results = collection.query(
        query_embeddings=[embedded_query],
        n_results=40,
        where={"url": url},
    )
    docs = results["documents"][0] if results["documents"] else []
    if not docs:
        answer = "I couldn't find any relevant information on this page for that question."
        context = ['not found']
        return answer,context
    
    context = "\n\n---\n\n".join(docs)
    compressed_context = compress_context(context,question)
    answer = answer_the_given_question(question,compressed_context)
    return answer,compressed_context


def clean_text(text: str) -> str:
    # Remove Wikipedia edit markers
    text = re.sub(r"\[edit\]", "", text, flags=re.IGNORECASE)

    # Remove common inline citation markers
    text = re.sub(r"\[(?:\d+(?:,\s*\d+)*|citation needed|update)\]", "", text, flags=re.IGNORECASE)

    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    # Normalize spacing around punctuation
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)

    return text.strip()
