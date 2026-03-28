import yt_dlp

VIDEO_ID = 'aqz-KE-bpKQ'

# Use same opts as the real app - no format filter, just get all formats
opts = {
    'format': 'bestvideo+bestaudio/best',
    'quiet': False,
    'noplaylist': True,
    'youtube_include_dash_manifest': False,
    'extractor_args': {'youtube': {'player_client': ['tv', 'web']}}
}

with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info(f'https://www.youtube.com/watch?v={VIDEO_ID}', download=False)
    all_formats = info.get('formats', [])
    
    # Video-only formats sorted by height
    video_fmts = sorted(
        [f for f in all_formats if f.get('vcodec','none') != 'none' and f.get('height')],
        key=lambda f: f.get('height', 0), reverse=True
    )
    
    print(f"\nAvailable video heights: {[f.get('height') for f in video_fmts]}")
    print(f"\nTop 5 video formats:")
    for f in video_fmts[:5]:
        print(f"  id={f.get('format_id')} height={f.get('height')} ext={f.get('ext')} vcodec={f.get('vcodec','')[:10]} url={f.get('url','')[:60]}")
