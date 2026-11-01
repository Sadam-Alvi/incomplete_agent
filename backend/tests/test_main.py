import os
import sys
from pathlib import Path
''' Using the mocking technique in these tests to test api calls without actually making real API calls. This is done to ensure that the tests are fast, reliable, and do not depend on external services. The tests use the `monkeypatch` fixture from pytest to replace the actual API call functions with fake implementations that simulate the expected behavior. This allows us to test the logic of our application without relying on the availability or behavior of external APIs.
Mocking is a common practice in unit testing to isolate the code being tested and to control the environment in which the tests run.'''


# Add repository root to Python path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

# Test environment variables
os.environ["GROQ_API_KEY"] = "test-groq-key"
os.environ["PINECONE_API_KEY"] = "test-pinecone-key"
os.environ["API_KEY"] = "test-transcript-key"
os.environ["LANGSMITH_API_KEY"] = "test-langsmith-key"
os.environ["HF_TOKEN"] = "test-hf-token"

import pytest
from fastapi.testclient import TestClient
from backend import main

client = TestClient(main.app)

# this decorator is used to define a fixture that will be automatically applied to all test functions in the module. The fixture is responsible for clearing the tasks dictionary before and after each test, ensuring that tests do not interfere with each other by sharing state.
@pytest.fixture(autouse=True)
def clear_tasks():
    # Keep tests independent of each other
    with main.tasks_lock:
        main.tasks.clear()

    yield

    with main.tasks_lock:
        main.tasks.clear()


# 1. Test health endpoint
def test_health():
    response = client.get("/health")
    # using assert insteasd of if statements to check the response status code and JSON content. If the assertions fail, pytest will report the failure and provide information about what went wrong.
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# 2. Test analyze endpoint
def test_analyze(monkeypatch):
    called = {}

    def fake_process_page(task_id, url):
        called["task_id"] = task_id
        called["url"] = url

    monkeypatch.setattr(main, "process_page", fake_process_page)

    response = client.post(
        "/analyze",
        json={"url": "https://www.youtube.com/watch?v=test123"}
    )

    assert response.status_code == 200

    task_id = response.json()["task_id"]

    assert task_id == called["task_id"]
    assert called["url"] == "https://www.youtube.com/watch?v=test123"

    assert task_id in main.tasks


# 3. Test progress endpoint
def test_get_progress():
    task_id = "test-task-123"

    with main.tasks_lock:
        main.tasks[task_id] = {
            "stage": "completed",
            "progress": 100,
            "message": "Analysis completed",
            "error": False
        }

    response = client.get(f"/progress/{task_id}")

    assert response.status_code == 200
    assert response.json()["progress"] == 100
    assert response.json()["stage"] == "completed"


# 4. Test progress for unknown task
def test_unknown_progress():
    response = client.get("/progress/unknown-task")

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis task not found."


# 5. Test streaming endpoint
def test_ask_stream(monkeypatch):
    called = {}

    def fake_answer(question, url, session_id):
        called["question"] = question
        called["url"] = url
        called["session_id"] = session_id

        return iter(["Hello ", "this is a test answer."])

    monkeypatch.setattr(
        main,
        "answer_the_query_stream",
        fake_answer
    )

    response = client.post(
        "/ask/stream",
        json={
            "url": "https://www.youtube.com/watch?v=test123",
            "question": "What is this video about?",
            "session_id": "session123"
        }
    )

    assert response.status_code == 200
    assert response.text == "Hello this is a test answer."
    assert response.headers["content-type"].startswith("text/plain")

    assert called["question"] == "What is this video about?"
    assert called["session_id"] == "session123"


# 6. Test invalid analyze request
def test_analyze_missing_url():
    response = client.post("/analyze", json={})

    assert response.status_code == 422


# 7. Test invalid ask request
def test_ask_missing_fields():
    response = client.post(
        "/ask/stream",
        json={"question": "Explain this video"}
    )

    assert response.status_code == 422
