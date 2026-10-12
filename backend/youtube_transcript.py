import re
from urllib.parse import urlparse, parse_qs
from yt_dlp import YoutubeDL
from youtube_transcript_api import  YouTubeTranscriptApi
import pandas as pd
import json
import urllib.request
import os
def load_or_create_df(path) -> pd.DataFrame:
    
    if os.path.exists(path):
        df = pd.read_csv(path)
        # ensure expected columns exist
        if not set(["url", "content"]).issubset(df.columns):
            df = pd.DataFrame(columns=["url", "content"])
    else:
        df = pd.DataFrame(columns=["url", "content"])
    return df

# Load once at module/script level
df = load_or_create_df(r"C:\Users\Alvi\Desktop\agentic\incomplete_agent\content.csv"  )

 # Load the CSV file into a DataFrame
def extract_video_id(url):
    """
    Robust extraction of YouTube video ID from various URL formats.
    Returns a clean string.
    """
    parsed_url = urlparse(url)
    
    # Handle shortened youtu.be links
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
        
    # Handle standard watch links
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            query_params = parse_qs(parsed_url.query)
            if 'v' in query_params and query_params['v']:
                # FIX: parse_qs returns a list; extract the first element as a string
                return query_params['v'][0]
        # Handle shorts, embed, or live URLs
        if parsed_url.path.startswith(('/embed/', '/v/', '/shorts/', '/live/')):
            return parsed_url.path.split('/')[2]
            
    # Fallback regex for tricky string cases
    regex = r'(?:v=|\/shorts\/|\/embed\/|\/v\/|\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(regex, url)
    if match:
        return match.group(1)
        
    raise ValueError("Could not parse YouTube Video ID from URL")

def get_youtube_transcript(video_url):
    if video_url in df['url'].values:
        return df[df['url'] == video_url]['content'].values[0]
    else:
        try:
            video_id = extract_video_id(video_url)
            clean_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Configure yt-dlp to only fetch the subtitle tracks without downloading the video
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsubtitles': True,
                'skip_download': True,
                'quiet': True,
                'no_warnings': True
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(clean_url, download=False)
                
                # Check for manually uploaded subtitles first, fallback to auto-generated
                subtitles = info_dict.get('subtitles', {}) or info_dict.get('automatic_captions', {})
                
                # Check for English track variants
                en_track = None
                for lang in ['en', 'en-US', 'en-GB']:
                    if lang in subtitles:
                        en_track = subtitles[lang]
                        break
                
                if not en_track:
                    # Fallback to the first available language track if English isn't present
                    if subtitles:
                        en_track = list(subtitles.values())[0]
                    else:
                        return "Error: No transcripts or captions available for this video."
                
                # Find the JSON format url inside the subtitle track configurations
                json_url = next((item['url'] for item in en_track if item.get('ext') == 'json'), None)
                
                if not json_url:
                    # If no json format structure is directly exposed, try picking the first format index
                    json_url = en_track[0]['url']
                    
                # Fetch and clean the text content using yt-dlp's internal downloader instance
               
                
                response = urllib.request.urlopen(json_url)
                data = json.loads(response.read().decode('utf-8'))
                
                # Parse out the clean text segments depending on YouTube subtitle JSON structure formats
                text_segments = []
                if 'events' in data:
                    for event in data['events']:
                        if 'segs' in event:
                            for seg in event['segs']:
                                text_segments.append(seg['utf8'])
                
                full_transcript = "".join(text_segments).strip()
                df.loc[len(df)] = [video_url, full_transcript]  # Append new transcript to DataFrame
                df.to_csv('content.csv', index=False)  # Save the updated DataFrame
                return full_transcript if full_transcript else "Error: Transcript data could not be parsed."

        except Exception as e:
            return f"Error retrieving transcript: {str(e)}"