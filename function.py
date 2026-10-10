import trafilatura
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb
import uuid
from threading import Lock
from llm import *

model = SentenceTransformer("BAAI/bge-small-en-v1.5")
client = chromadb.PersistentClient(path="./database")
collection = client.get_or_create_collection(
    name="page_data",
    metadata={"hnsw:space": "cosine"}
)

tasks = {}
tasks_lock = Lock()

def get_content_from_url(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError("Could not download webpage")
    text = trafilatura.extract(downloaded)
    if not text:
        raise ValueError("Could not extract webpage text")
    return text

def preprocess_data(content: str, url: str) -> list:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=60,
        length_function=len,
    )
    chunks = text_splitter.split_text(content)
    if not chunks:
        return []

    embeddings = model.encode(chunks, normalize_embeddings=True)
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"url": url, "chunk_index": i} for i in range(len(chunks))]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings.tolist(),   # important for some chromadb versions
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
    embedded_query = model.encode(question,normalize_embeddings=True)
    results = collection.query(
        query_embeddings=[embedded_query],
        n_results=70,
        where={"url": url},
    )
    docs = results["documents"][0] if results["documents"] else []
    if not docs:
        return "I couldn't find any relevant information on this page for that question."
    
    context = "\n\n---\n\n".join(docs)
    answer = answer_the_given_question(question,context)
    return answer