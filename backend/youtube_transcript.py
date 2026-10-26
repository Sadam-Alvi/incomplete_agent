
import os
import re
import requests
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs
import pandas as pd
from urllib.parse import urlparse
from langsmith import traceable
load_dotenv()
API_KEY = os.environ["API_KEY"]
API_URL = "https://transcriptapi.com/api/v2/youtube/transcript"




def get_youtube_id(video_url: str) -> str | None:
    parsed = urlparse(video_url)
    host = (parsed.hostname or "").lower()

    if host == "youtu.be":
        return parsed.path.strip("/").split("/")[0] or None

    if host in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]

        if parsed.path.startswith(("/embed/", "/v/", "/shorts/")):
            parts = parsed.path.strip("/").split("/")
            return parts[1] if len(parts) > 1 else None

    return None

@traceable(name="getting_transcript", run_type="retriever")
def get_youtube_transcript(video_url: str) -> str:
    

    video_id = get_youtube_id(video_url)
    if not video_id:
        raise ValueError(f"Invalid YouTube URL: {video_url}")

    # Check cache using the original URL
  

    try:
        response = requests.get(
            API_URL,
            params={"video_url": video_url, "format": "json"},
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        transcript = data.get("transcript", [])

        if not isinstance(transcript, list):
            raise ValueError("API returned an unexpected transcript format.")

        text_only = "\n".join(
            re.sub(r"\s+", " ", item.get("text", "")).strip()
            for item in transcript
            if isinstance(item, dict)
            and isinstance(item.get("text"), str)
            and item["text"].strip()
        )

        if not text_only:
            raise ValueError("The API returned an empty transcript.")

        # Update the in-memory cache
    

      

        return text_only

    except (requests.RequestException, ValueError, KeyError) as e:
        raise RuntimeError(f"Failed to retrieve transcript: {e}") from e





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
        return text
              
    
    else:   
        raise ValueError("Currently this extension is only for youtube video, please open  a youtube video, in future i'll add reading of other pages capability too")
    





