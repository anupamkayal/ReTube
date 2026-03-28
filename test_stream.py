"""
Extended stream diagnostic – tests web_creator and mediaconnect client specifically.
"""
import yt_dlp
import urllib.parse
import requests

TEST_VIDEO = 'dQw4w9WgXcQ'

def try_client(client_name):
    print(f"\n--- Testing client: {client_name} ---")
    opts = {
        'format': 'bestvideo+bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'youtube_include_dash_manifest': False,
        'extractor_args': {'youtube': {'player_client': [client_name]}},
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f'https://www.youtube.com/watch?v={TEST_VIDEO}', download=False)
        
        fmts = info.get('formats', [])
        video_fmts = [f for f in fmts if f.get('vcodec') != 'none' and f.get('height')]
        audio_fmts = [f for f in fmts if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        video_fmts.sort(key=lambda f: f.get('height', 0), reverse=True)
        audio_fmts.sort(key=lambda f: f.get('abr', 0) or 0, reverse=True)

        print(f"  Video formats: {len(video_fmts)}, Audio formats: {len(audio_fmts)}")
        if video_fmts:
            f = video_fmts[0]
            url = f.get('url','')
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            c = (qs.get('c') or ['?'])[0]
            spc = 'spc=' in url
            rqh = 'rqh=1' in url
            print(f"  Best video: {f.get('height')}p | c_param={c} | spc={spc} | rqh={rqh}")
            # Try fetching 64KB of it
            ua_map = {
                'ANDROID': 'com.google.android.youtube/21.05.46 (Linux; U; Android 14; en_US) gzip',
                'WEB': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
                'MWEB': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36',
                'IOS': 'com.google.ios.youtube/19.45.4 (iPhone16,2; U; CPU iOS 18_1_0 like Mac OS X)',
                'TVHTML5': 'Mozilla/5.0 (PlayStation; PlayStation 4/8.03) AppleWebKit/605.1.15',
            }
            ua = ua_map.get(c, ua_map['WEB'])
            try:
                r = requests.get(url, headers={'User-Agent': ua, 'Referer': 'https://www.youtube.com/', 'Range': 'bytes=0-65535'}, stream=True, timeout=8)
                print(f"  Proxy test: HTTP {r.status_code} | {len(r.content)} bytes")
            except Exception as e:
                print(f"  Proxy test: ERROR {e}")
        if audio_fmts:
            f = audio_fmts[0]
            print(f"  Best audio: {f.get('abr')}kbps ext={f.get('ext')}")
        return len(video_fmts) > 0
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


if __name__ == '__main__':
    # Test the clients most likely to work without PO token
    for c in ['web_creator', 'mediaconnect', 'mweb', 'android_vr', 'tv_embedded', 'web_embedded']:
        try_client(c)
    print("\nDone.")
