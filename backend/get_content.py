import requests
import trafilatura

def get_content_from_url(url: str) -> str:
    if url in df['url'].values:
        return df[df['url'] == url]['content'].values[0]
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
        headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
        response = requests.get(
        url,
        headers=headers,
        timeout=20,
        allow_redirects=True,
    )   
        response.raise_for_status()
        downloaded = trafilatura.extract(response.text)

        if not downloaded:
            raise ValueError("Could not download webpage.")

        text = trafilatura.extract(downloaded)
        

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Could not extract readable content from the URL.")

    text = text.strip()
    df.loc[len(df)] = [url, clean_text(text)]  # Append new content to DataFrame
    df.to_csv('content.csv', index=False)  # Save the updated DataFrame
    return clean_text(text)



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


    


    

