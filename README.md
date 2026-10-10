# PagePal

PagePal is a Chrome extension and local FastAPI service that lets you ask questions about the webpage currently open in your browser. The backend extracts readable page content, splits and embeds it with ChromaDB, then uses a local Hugging Face language model to answer questions from the retrieved text.

## Features

- Automatically analyzes the active webpage when the extension popup opens.
- Shows analysis progress and errors in the popup.
- Stores page chunks and embeddings locally in ChromaDB.
- Answers questions using only the retrieved webpage content.
- Keeps a short, in-memory chat history for follow-up questions.

## Project structure

```text
backend/
  main.py       FastAPI routes
  function.py   Web extraction, embeddings, and vector search
  llm.py        Local Hugging Face LLM and chat chain
extension/
  manifest.json Chrome extension manifest
  popup.*       Popup interface and API client
```

## Prerequisites

- Python 3.10 or newer
- Google Chrome or another Chromium-based browser
- Sufficient disk space and RAM for the configured local model (`prism-ml/Ternary-Bonsai-2-27B-gguf`)

> The model is downloaded/initialized by the backend on first use. Its hardware requirements can be substantial.

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the backend dependencies:

```powershell
pip install -r requirements.txt
```

Start the API from the `backend` directory:

```powershell
cd backend
uvicorn main:app --reload
```

The API listens at `http://127.0.0.1:8000` by default.

## Load the extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked**.
4. Select this repository's `extension` folder.
5. Keep the backend running, open a normal `http` or `https` webpage, and click the PagePal extension icon.

PagePal analyzes the page automatically. Once processing reaches 100%, enter a question in the popup.

## API

### `POST /analyze`

Starts background analysis of a webpage.

```json
{ "url": "https://example.com" }
```

The response contains a `task_id`.

### `GET /progress/{task_id}`

Returns the current stage, percentage, and any error for an analysis task.

### `POST /ask`

Answers a question using chunks stored for the specified URL.

```json
{
  "url": "https://example.com",
  "question": "What is this page about?"
}
```

## Local data

ChromaDB persists its data in `backend/database` when the server is started from the `backend` directory. Delete that folder if you want to remove all indexed page data.

## Notes

- The extension is configured to contact `http://127.0.0.1:8000`. Update `API_BASE` in `extension/popup.js` if the backend uses a different address or port.
- CORS is currently open to all origins for local development. Restrict it before exposing the API outside your machine.
