from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi

def extract_video_id(url):
    """
    Extracts the video ID from various styles of YouTube links.
    """
    parsed_url = urlparse(url)
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
        if parsed_url.path.startswith(('/embed/', '/v/')):
            return parsed_url.path.split('/')[2]
    raise ValueError("Invalid YouTube URL")

def get_youtube_transcript(video_url):
    try:
        # Step 1: Extract the video ID from the link
        video_id = extract_video_id(video_url)
        
        # Step 2: Fetch the raw transcript data
        # This returns a list of dictionaries: [{'text': '...', 'start': 0.0, 'duration': 0.0}]
        raw_transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Step 3: Join the text snippets into a clean, single paragraph
        full_transcript = " ".join([entry['text'] for entry in raw_transcript])
        print(full_transcript)
        return full_transcript

    except Exception as e:
        return f"Error retrieving transcript: {str(e)}"

