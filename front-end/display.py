import streamlit as st
import requests
import time
import uuid

API_URL = "https://new-repo.fastapicloud.dev"

st.set_page_config(page_title="Video Chat")
st.title("Chat with a video")

# ---------------- SESSION STATE ----------------

if "analyzed_url" not in st.session_state:
    st.session_state.analyzed_url = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())


# ---------------- ANALYZE VIDEO ----------------

def analyze_video(url):

    response = requests.post(
        f"{API_URL}/analyze",
        json={"url": url},
        timeout=30
    )

    response.raise_for_status()

    task_id = response.json()["task_id"]

    # Poll analysis progress
    with st.status("Analyzing video...", expanded=True) as status:

        progress_bar = st.progress(0)
        message_placeholder = st.empty()

        while True:

            response = requests.get(
                f"{API_URL}/progress/{task_id}",
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

            progress = data.get("progress", 0)
            stage = data.get("stage", "")
            message = data.get("message", "Processing video...")

            progress_bar.progress(
                min(max(int(progress), 0), 100)
            )

            message_placeholder.write(message)

            # Handle errors
            if data.get("error"):
                status.update(
                    label="Video analysis failed",
                    state="error"
                )
                raise RuntimeError(message)

            # Analysis completed
            if stage in ("completed", "complete", "done") or progress >= 100:
                status.update(
                    label="Video analyzed successfully!",
                    state="complete"
                )
                break

            time.sleep(.5)


# ---------------- STREAM ANSWER ----------------

def answer_question(question, url):

    payload = {
        "url": url,
        "question": question,
        "session_id": st.session_state.session_id
    }

    with requests.post(
        f"{API_URL}/ask/stream",
        json=payload,
        stream=True,
        timeout=(10, 300)
    ) as response:

        response.raise_for_status()
        response.encoding = "utf-8"

        for chunk in response.iter_content(
            chunk_size=1024,
            decode_unicode=True
        ):
            if chunk:
                yield chunk


# ---------------- MAIN UI ----------------

if st.session_state.analyzed_url is None:

    with st.form("video_url_form"):

        url = st.text_input("Enter a YouTube video URL")

        submitted = st.form_submit_button("Analyze video")

    if submitted:

        if not url.strip():

            st.error("Enter a YouTube URL.")

        else:

            try:

                analyze_video(url.strip())

                st.session_state.analyzed_url = url.strip()

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": (
                        "I've analyzed the video. "
                        "You can now ask questions about it."
                    )
                })

                st.rerun()

            except requests.RequestException as e:

                st.error(f"API request failed: {e}")

            except Exception as e:

                st.error(f"Analysis failed: {e}")


# ---------------- CHAT INTERFACE ----------------

else:

    st.caption(
        f"Video: {st.session_state.analyzed_url}"
    )

    # Display chat history
    for message in st.session_state.messages:

        with st.chat_message(message["role"]):
            st.write(message["content"])

    question = st.chat_input(
        "Ask a question about the video"
    )

    if question:

        # Display user message
        st.session_state.messages.append({
            "role": "user",
            "content": question
        })

        with st.chat_message("user"):
            st.write(question)

        # Stream answer from FastAPI
        with st.chat_message("assistant"):

            try:

                answer = st.write_stream(
                    answer_question(
                        question,
                        st.session_state.analyzed_url
                    )
                )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer
                })

            except requests.RequestException as e:

                st.error(f"Question answering API failed: {e}")

            except Exception as e:

                st.error(f"Something went wrong: {e}")