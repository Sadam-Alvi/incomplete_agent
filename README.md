# Webby Chat

Webby Chat is a YouTube-aware AI assistant that lets a user ask questions about a video and receive grounded answers from the transcript. The project combines a FastAPI backend, a Chrome extension UI, and a lightweight Streamlit demo interface.

The system works by:

1. Accepting a YouTube URL from the client.
2. Fetching the video's transcript.
3. Splitting the transcript into chunks and storing embeddings in Pinecone.
4. Rewriting the user's question and retrieving relevant transcript segments.
5. Sending the retrieved context to Groq-hosted LLM for a concise answer.
6. Streaming the final answer back to the frontend.

This project is intentionally scoped to YouTube videos only. Non-video webpages are not supported in the current backend.

## Features

- YouTube transcript retrieval using a transcript API.
- Vector search over transcript chunks in Pinecone.
- Question rewriting for better retrieval.
- Context-grounded answers with Groq.
- Streaming responses to the client.
- Per-video chat history stored in Chrome local storage.
- Optional Streamlit interface for testing the API.
- Container support via Docker Compose.

## Project structure

```text
incomplete_agent/
├── README.md
├── requirements.txt
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   ├── function.py
│   ├── llm.py
│   ├── RewriteQuestion.py
│   ├── answer_question.py
│   ├── vector_database.py
│   ├── youtube_transcript.py
│   ├── .env.example (if present in your local checkout)
│   └── evaluation/
│       ├── evals.py
│       ├── ragas_results.csv
│       └── test.json
├── front-end/
│   ├── Dockerfile
│   ├── display.py
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.css
│   ├── popup.js
│   ├── marked.min.js
│   └── purify.min.js
└── .github/workflows/
    └── backend.yml
```

## Tech stack

- Python 3.10+
- FastAPI
- LangChain + Groq
- Pinecone vector database
- Chrome extension (Manifest V3)
- Streamlit (demo UI)
- Docker + Docker Compose

## How the app works

### Backend flow

The FastAPI app in `backend/main.py` exposes endpoints such as:

- `POST /analyze` — starts a background job to fetch and index a URL's transcript.
- `GET /progress/{task_id}` — polls progress for the analysis job.
- `POST /ask/stream` — streams a grounded answer from the transcript.
- `GET /health` — lightweight health endpoint.

The core answering pipeline is in `backend/answer_question.py`:

1. `rewrite_question()` rewrites the input to improve retrieval quality.
2. `retrieve_chunks()` searches Pinecone for the most relevant chunks.
3. The retrieved context is assembled into a prompt.
4. `answer_the_given_question_stream()` streams the model output back to the client.

### Front-end flow

The Chrome extension in `front-end/`:

- reads the active tab URL,
- calls the backend analysis endpoint,
- shows progress while transcript embeddings are created,
- opens a chat panel when ready,
- saves chat history per video in Chrome storage.

The Streamlit app in `front-end/display.py` is a simple demo UI that calls the same backend API.

## Requirements

Before running the project, make sure you have:

- Python 3.10 or newer
- Chrome or Chromium for the extension
- A Groq API key
- A Pinecone API key
- A transcript service API key for the YouTube transcript endpoint

## Environment setup

Create a `backend/.env` file (or export the same variables in your environment) with values like:

```env
GROQ_API_KEY=your_groq_api_key
PINECONE_API_KEY=your_pinecone_api_key
API_KEY=your_transcript_api_key
```

The application code currently expects the Pinecone index name `webby-chat` to exist in your Pinecone project. If the index does not exist, create it before running the app.

## Local development

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# or .\.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
```

### 2) Start the backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will run at:

- `http://localhost:8000`
- Health check: `http://localhost:8000/health`

### 3) Load the Chrome extension

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Click Load unpacked.
4. Select the `front-end` directory.

### 4) Optional: run the Streamlit demo

```bash
cd front-end
streamlit run display.py
```

The demo page is usually available at:

- `http://localhost:8501`

## Docker deployment

This repository also includes a Docker Compose setup for local containerized development.

```bash
docker compose up --build
```

Services defined in `docker-compose.yml`:

- `backend` on port `8000`
- `frontend` on port `8501`

The frontend service is a Streamlit app, while the Chrome extension remains a browser-side artifact and is not packaged directly by Docker.

## Usage

1. Open the extension or Streamlit UI.
2. Paste a YouTube video URL.
3. Wait for the transcript to be analyzed and indexed.
4. Ask a question about the video.
5. Read the streamed answer grounded in the retrieved transcript chunks.

## Important implementation notes

- The code supports YouTube URLs only. `youtube_transcript.py` rejects non-YouTube URLs.
- The backend uses a transcript API and Pinecone for retrieval. If either service is unavailable or misconfigured, question answering will fail.
- Chat history is stored in the browser local storage, not in a database.
- The evaluation script in `backend/evaluation/evals.py` expects an `/evaluate/answer` endpoint; that endpoint is currently commented out in `backend/main.py`.

## Evaluation

A sample RAGAS evaluation is included in `backend/evaluation/ragas_results.csv` with associated test cases in `backend/evaluation/test.json`.

Example results from the included run:

| Metric | Score |
| --- | ---: |
| Answer correctness | 84.3% |
| Faithfulness | 91.8% |
| Answer relevancy | 96.5% |
| Context precision | 84.1% |
| Context recall | 89.3% |

These numbers are only a small benchmark for a specific video and should not be treated as a general claim of model quality across all content.

## Troubleshooting

### Backend fails to start

- Check that the required environment variables are present.
- Verify that `requirements.txt` has been installed.
- Confirm that the Pinecone index named `webby-chat` exists.

### YouTube transcript is not retrieved

- Ensure the `API_KEY` is valid.
- Confirm the URL is a valid YouTube video URL.
- Check the transcript API response format and service status.

### Questions return poor answers

- Check whether the transcript was indexed successfully.
- Verify that the vector store contains data for the URL being queried.
- Ensure the question is specific enough to match transcript content.

### Extension cannot reach the backend

- Update the API URL in `front-end/popup.js` if you are not using the default remote deployment.
- Check your CORS and host configuration if running locally.

## Contribution notes

This repo is a prototype and some parts are intentionally simple. If you extend it, key areas to review are:

- transcript fetching and validation
- Pinecone indexing and retrieval logic
- prompt design and answer grounding
- frontend-to-backend API compatibility
- evaluation coverage and test quality

## License

No explicit license file is included in this repository, so source usage and distribution should be checked against the project owner’s requirements before public reuse.
