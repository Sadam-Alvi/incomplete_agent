# Webby Chat

Webby Chat is a Chrome extension that analyzes the current webpage or YouTube video and answers questions from the content it extracts. The backend retrieves readable text, splits it into chunks, stores embeddings in ChromaDB, and uses Groq-hosted LLMs to answer grounded questions from the retrieved context.

## Features

- Analyzes the active tab when the extension opens.
- Handles both regular webpages and YouTube links.
- Extracts readable text using `trafilatura` and YouTube subtitle retrieval.
- Saves page/video chunks and embeddings in a local ChromaDB collection.
- Answers questions using only the indexed content for that URL.
- Keeps a short in-memory chat history for follow-up questions.
- Provides a FastAPI backend with progress tracking for long-running page analysis.

## Project structure

```text
backend/
  main.py                 FastAPI endpoints
  function.py            URL extraction, chunking, vector search, indexing
  llm.py                 Groq chat model + prompt + session history
  youtube_transcript.py  YouTube transcript extraction utilities
  evaluation/
    evals.py             Optional RAG evaluation script
    test.json            Evaluation cases
front-end/
  manifest.json          Chrome extension manifest
  popup.html             Popup UI
  popup.css             Popup styling
  popup.js              Front-end logic and API client
README.md
requirements.txt
```

## Prerequisites

- Python 3.10+
- Google Chrome or another Chromium-based browser
- A Groq API key

The app uses the Groq model configured in `backend/llm.py` (`openai/gpt-oss-20b`), so you must set your `GROQ_API_KEY` before running the backend.

## Setup

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install the dependencies:

```powershell
pip install -r requirements.txt
```

3. Create a `.env` file in the project root or `backend/` directory with your Groq key:

```env
GROQ_API_KEY=your_api_key_here
```

4. Start the backend:

```powershell
cd backend
uvicorn main:app --reload
```

The API will run at `http://127.0.0.1:8000`.

## Load the extension

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Click Load unpacked.
4. Select the `front-end` folder from this project.
5. Keep the FastAPI backend running, open a normal webpage or a YouTube video, and click the extension icon.

The extension automatically starts analysis for the active page. Once analysis finishes, you can ask questions in the popup.

## API routes

### POST /analyze

Starts background analysis for a URL.

Request body:

```json
{
  "url": "https://example.com"
}
```

Response:

```json
{
  "task_id": "<uuid>"
}
```

### GET /progress/{task_id}

Returns the status for a long-running analysis task.

Example response:

```json
{
  "stage": "complete",
  "progress": 100,
  "message": "Analysis complete!",
  "error": false
}
```

### POST /ask

Answers a question based on previously indexed content for a given URL.

Request body:

```json
{
  "url": "https://example.com",
  "question": "What is this page about?"
}
```

Response:

```json
{
  "question": "What is this page about?",
  "answer": "...",
  "context": "..."
}
```

## Local data

ChromaDB stores the indexed page data in the `backend/database` folder when the backend is started from the `backend` directory. Delete that folder if you want to clear all stored embeddings and page chunks.

## Notes

- The extension is configured to call `http://127.0.0.1:8000`. If you run the API on a different host or port, update `API_BASE` in `front-end/popup.js`.
- CORS is intentionally permissive for local development. Restrict it before exposing the API beyond your local machine.
- The evaluation script in `backend/evaluation/evals.py` is optional and helps benchmark the RAG pipeline against sample questions.
