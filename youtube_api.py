import yt_dlp
import requests
import innertube
from pytubefix import YouTube
import subprocess
bg_path = "/app/rustypipe-botguard"
# ---------------------------------------------------------------------------
# Patch innertube package config: remove stale API keys from Android/iOS clients.
# The package sends ?key=AIzaSy... to youtubei.googleapis.com, which YouTube now
# rejects with 400 "Precondition check failed" for these clients.
# Removing the key makes them work without auth — same approach yt-dlp uses.
# ---------------------------------------------------------------------------
try:
    from innertube import config as _it_cfg
    _NO_KEY_CLIENTS = {"ANDROID", "IOS", "MWEB", "ANDROID_MUSIC","WEB_EMBEDDED", "IOS_MUSIC"}
    # We iterate through the clients defined in the library's internal registry
    for _client in _it_cfg.clients:
        # Check if this specific client object is in our "No Key" list
        if hasattr(_client, 'client_name') and _client.client_name in _NO_KEY_CLIENTS:
            _client.api_key = None 
            print(f"[Innertube] Patched {_client.client_name}: Removed API Key")
            
except Exception as _e:
    print(f"[Innertube] Config patch failed: {str(_e)}")


def get_safe_session():
    session = requests.Session()
    session.headers.update({
        # Spoofing a 2026 Android Version
        'User-Agent': 'com.google.android.youtube/21.05.46 (Linux; U; Android 14; en_US) gzip',
        'X-Goog-Api-Format-Version': '2',
        'Origin': 'https://www.youtube.com',
        'Referer': 'https://www.youtube.com/'
    })
    return session


def _innertube_get_stream(video_id, quality=None):
    """Use innertube package to fetch stream URLs. Returns stream dict or None."""
    safe_session = get_safe_session()
    requested_height = 0
    if quality:
        try:
            requested_height = int(''.join(filter(str.isdigit, quality)) or '0')
        except (ValueError, TypeError):
            pass

    # Prioritised client list:
    # ANDROID_TESTSUITE → test client, URLs usually have no spc/rqh protection
    # ANDROID_UNPLUGGED / ANDROID_LITE → YouTube TV / Go variants, usually no PO token
    # ANDROID/IOS (patched, no api_key) → direct unsigned HD URLs for most videos
    yt = YouTube(f'https://www.youtube.com/watch?v={video_id}', use_po_token=True)
    result = subprocess.run([bg_path, video_id], capture_output=True, text=True, check=True)
    
    # Print the result
    print("Generated PO Token Data:")
    generated_token = result.stdout.strip()
    PO_TOKEN = generated_token
    print(f"Successfully captured PoToken: {PO_TOKEN}")
    print(result.stdout.strip())
    print(f"PoToken: {yt.po_token}")
    print(f"VisitorData: {yt.visitor_data}")

    PO_TOKEN = "MnjGxQIIPDT8Wcb5Uuyi6bS0qfSaZpfO16DhnsZjywjOAqMD1ICiQC3De7k3eb35lx0ieiliAAXws6Ixc-HZ0cCAYFP-Rmr47BIpEvR2Pnhqo5G-0o8ql8sBVqVecg3m23I2IDALEWbppqYyGLFiAmx1my9fLLXw2e8="
    VISITOR_DATA = yt.visitor_data
    for client_name in ("ANDROID_TESTSUITE", "ANDROID_UNPLUGGED", "ANDROID_LITE", "ANDROID", "IOS"):
        try:
            client = innertube.InnerTube(client_name,client_version="21.05.46")
            # Use direct dispatch to add contentCheckOk/racyCheckOk for age-restricted videos
            data = client(
                "player",
                body={
                    "videoId": video_id,
                    "contentCheckOk": True,
                    "racyCheckOk": True,
                    "context": {
                        "client": {
                            "clientName": client_name,
                            "clientVersion": "21.05.46",
                            "visitorData": VISITOR_DATA, # CRITICAL FOR GUEST MODE
                        },
                         "serviceIntegrityDimensions": {
                            "poToken": PO_TOKEN,  # PO token passed here as required by YouTube
                        },
                        
                    }
                }
            )

            status = data.get("playabilityStatus", {}).get("status", "")
            if status not in ("OK", ""):
                reason = data.get("playabilityStatus", {}).get("reason", "unknown")
                print(f"[Innertube/{client_name}] Not playable: {status} - {reason}")
                continue

            streaming_data = data.get("streamingData", {})
            if not streaming_data:
                print(f"[Innertube/{client_name}] No streamingData")
                continue

            adaptive = streaming_data.get("adaptiveFormats", [])
            combined = streaming_data.get("formats", [])

            # Only use formats with a direct URL (not signatureCipher / encrypted)
            video_fmts = [f for f in adaptive if f.get("mimeType", "").startswith("video/") and "url" in f]
            audio_fmts = [f for f in adaptive if f.get("mimeType", "").startswith("audio/") and "url" in f]

            video_fmts.sort(key=lambda f: f.get("height", 0) or 0, reverse=True)

            if video_fmts:
                if requested_height > 0:
                    cands = [f for f in video_fmts if (f.get("height") or 0) <= requested_height]
                    chosen_video = cands[0] if cands else video_fmts[-1]
                else:
                    chosen_video = video_fmts[0]
                video_url = chosen_video.get("url", "")
                actual_height = chosen_video.get("height", 0) or 0
            elif combined:
                # Fallback to combined (video+audio) formats
                direct_combined = [f for f in combined if "url" in f]
                if not direct_combined:
                    print(f"[Innertube/{client_name}] Only cipher formats available")
                    continue
                direct_combined.sort(key=lambda f: f.get("height", 0) or 0, reverse=True)
                if requested_height > 0:
                    cands = [f for f in direct_combined if (f.get("height") or 0) <= requested_height]
                    chosen_video = cands[0] if cands else direct_combined[-1]
                else:
                    chosen_video = direct_combined[0]
                video_url = chosen_video.get("url", "")
                actual_height = chosen_video.get("height", 0) or 0
            else:
                print(f"[Innertube/{client_name}] No formats in streamingData")
                continue

            if not video_url:
                print(f"[Innertube/{client_name}] Empty video URL (likely cipher-only)")
                continue

            # Best audio stream
            audio_url = ""
            if audio_fmts:
                audio_fmts.sort(key=lambda f: f.get("bitrate", 0) or 0, reverse=True)
                audio_url = audio_fmts[0].get("url", "")

            vd = data.get("videoDetails", {})
            try:
                views_fmt = f"{int(vd.get('viewCount', 0) or 0):,}"
            except (ValueError, TypeError):
                views_fmt = "0"

            print(f"[Innertube/{client_name}] Got stream: {actual_height}p, audio={'yes' if audio_url else 'no'}")
            return {
                'id': video_id,
                'youtube_id': video_id,
                'title': vd.get('title', 'Unknown Title'),
                'stream_url': video_url,
                'audio_url': audio_url,
                'actual_quality': f'{actual_height}p' if actual_height else 'auto',
                'visitor_data': VISITOR_DATA or '',  # needed by proxy for rqh=1 URLs
                'thumbnail_url': (
                    vd.get('thumbnail', {}).get('thumbnails', [{}])[-1].get('url', '')
                    or f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'
                ),
                'uploader': {'username': vd.get('author', 'Unknown Channel')},
                'views': views_fmt,
                'like_count': 0,
                'description': vd.get('shortDescription', ''),
                'duration': int(vd.get('lengthSeconds', 0) or 0),
            }
        except Exception as e:
            print(f"[Innertube/{client_name}] Error: {e}")
            continue
    return None

# ---------------------------------------------------------------------------


def search_youtube(query):
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'extract_flat': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios','twb', 'tv','android_embedded']}},
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'logtostderr': True,
        'quiet': False,
        'no_warnings': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',}} # This header helps bypass some player-client checks
    
    if not str(query).startswith('http') and not str(query).startswith('ytsearch'):
        # Reduce to 50 items to avoid excessive pagination requests during search
        query = f"ytsearch50:{query}"
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                results = []
                for entry in info['entries']:
                    view_count = entry.get('view_count') or 0
                    
                    # Duck-type to match the SQLAlchemy Video model used in Jinja
                    # Jinja allows accessing dict keys via dot notation (e.g., video.title)
                    results.append({
                        'id': entry.get('id', ''),
                        'youtube_id': entry.get('id', ''), # explicit marker
                        'title': entry.get('title', 'Unknown Title'),
                        'uploader': {'username': entry.get('uploader', 'Unknown Channel')},
                        'duration': entry.get('duration', 0),
                        'views': f"{view_count:,}",
                        'thumbnail_url': f"https://i.ytimg.com/vi/{entry.get('id', '')}/hqdefault.jpg"
                    })
                # Shuffle the results to provide a fresh grid every page load
                if len(results) > 100:
                    import random
                    results = random.sample(results, 100)
                return results
        except Exception as e:
            print(f"Error searching: {e}")
    return []

def _build_ydl_opts(format_str='bestvideo+bestaudio/best', extra=None):
    """Build yt-dlp opts.
    android_vr / tv_embedded / mediaconnect return 4K adaptive streams with
    audio that ARE proxy-compatible (HTTP 206 confirmed via testing).
    mweb/web_creator require sign-in. android/ios require GVS PO Token.
    """
    import os
    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    
    base = {
        'format': format_str,
        'noplaylist': True,
        'quiet': True,
        'youtube_include_dash_manifest': False,
        # android_vr / tv_embedded give 4K proxy-friendly URLs without needing PO tokens
        'extractor_args': {'youtube': {'player_client': ['android_vr', 'tv_embedded', 'mediaconnect']}},
    }
    if extra:
        base.update(extra)
    
    # Cookies enable highest quality if available
    if os.path.exists(cookies_file):
        print(f'[yt-dlp] Using cookies.txt: {cookies_file}')
        base['cookiefile'] = cookies_file
    else:
        print('[yt-dlp] No cookies.txt — using android_vr/tv_embedded client')
    
    return base

def _ydl_opts_no_cookies(format_str=None):
    """yt-dlp opts with no cookies at all — used as retry when cookie copy fails."""
    if format_str is None:
        # Default: combined stream (video+audio in one file) up to 720p.
        # No separate audio element → zero sync issues.
        format_str = (
            'best[ext=mp4][height<=720]'
            '/best[height<=720]'
            '/best[ext=mp4]'
            '/best'
        )
    return {
        'format': format_str,
        'noplaylist': True,
        'quiet': True,
        'youtube_include_dash_manifest': False,
        'extractor_args': {'youtube': {'player_client': ['android_vr', 'tv_embedded', 'mediaconnect']}},
    }

def _extract_ydl_info(video_url, ydl_opts):
    """Run yt-dlp extract_info; raises on failure."""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(video_url, download=False)

def _ydl_get_stream(video_id, quality=None):
    """
    Quality-aware stream extraction:
      <720p   → combined format (video+audio in one file)
      >=720p  → adaptive format (separate streams) + MIME types for MSE playback
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    # Parse requested height
    requested_height = 0
    if quality:
        try:
            requested_height = int(''.join(filter(str.isdigit, quality)) or '0')
        except (ValueError, TypeError):
            pass

    # YouTube itag 22 (720p combined) is rare now; adaptive is much more reliable.
    # So we use adaptive (MSE) for 720p and above.
    adaptive_mode = requested_height >= 720

    if adaptive_mode:
        # Force H.264 (avc1) + AAC (mp4a) only — VP9/WebM is NOT supported in
        # the MSE mp4 container the browser expects. Using vcodec:avc1 ensures
        # MediaSource.isTypeSupported('video/mp4; codecs="avc1..."') returns true.
        fmt_str = (
            f'bestvideo[height<={requested_height}][vcodec^=avc1][ext=mp4]+bestaudio[acodec^=mp4a][ext=m4a]'
            f'/bestvideo[height<={requested_height}][ext=mp4]+bestaudio[ext=m4a]'
            f'/bestvideo[height<={requested_height}][ext=mp4]+bestaudio'
            f'/bestvideo[height<={requested_height}]+bestaudio'
            f'/best[height<={requested_height}]'
        )
    else:
        h = requested_height if requested_height > 0 else 360
        fmt_str = (
            f'best[ext=mp4][height<={h}]'
            f'/best[height<={h}]'
            f'/best[ext=mp4]'
            f'/best'
        )

    ydl_opts = _build_ydl_opts(format_str=fmt_str)
    info = None
    try:
        info = _extract_ydl_info(video_url, ydl_opts)
    except Exception as e:
        err = str(e)
        _cookie_db_error = ('Could not copy' in err or 'cookie database' in err.lower() or 'cookiejar' in err.lower())
        if _cookie_db_error:
            print(f"[yt-dlp] Cookie DB error, retrying without cookies...")
            try:
                info = _extract_ydl_info(video_url, _ydl_opts_no_cookies(format_str=fmt_str))
            except Exception as e2:
                print(f"[yt-dlp] Retry without cookies also failed: {e2}")
        else:
            print(f"[yt-dlp] Extraction failed: {e}")

    if info is None:
        return None

    try:
        view_count = info.get('view_count', 0)
        video_stream_url = ''
        audio_stream_url = ''
        video_mime = ''
        audio_mime = ''
        actual_height = 0

        if adaptive_mode:
            # yt-dlp gives us requested_formats[] when format is "A+B"
            requested = info.get('requested_formats', [])
            vfmt = next((f for f in requested
                         if f.get('vcodec') not in (None, 'none', '') and f.get('url')), None)
            afmt = next((f for f in requested
                         if (f.get('vcodec') in (None, 'none', '') or not f.get('vcodec'))
                         and f.get('acodec') not in (None, 'none', '') and f.get('url')), None)

            if vfmt and afmt:
                video_stream_url = vfmt['url']
                audio_stream_url = afmt['url']
                actual_height = vfmt.get('height', 0) or 0
                
                # MIME types for MSE: always use video/mp4 and audio/mp4.
                # If the codec is VP9 (vp09) or AV1 (av01), those don't work in
                # an mp4 container for MSE — force avc1/mp4a fallback strings.
                v_full = vfmt.get('vcodec', 'avc1.4d401e')
                a_full = afmt.get('acodec', 'mp4a.40.2')

                # Normalise: if vp9/av1 slipped through, replace with safe defaults
                if v_full.startswith('vp09') or v_full.startswith('av01') or v_full.startswith('vp8'):
                    print(f"[yt-dlp] Unsafe video codec {v_full}, replacing with avc1.4d401e")
                    v_full = 'avc1.4d401e'
                if a_full.startswith('opus') or a_full.startswith('vorbis'):
                    print(f"[yt-dlp] Unsafe audio codec {a_full}, replacing with mp4a.40.2")
                    a_full = 'mp4a.40.2'

                video_mime = f'video/mp4; codecs="{v_full}"'
                audio_mime = f'audio/mp4; codecs="{a_full}"'
                
                print(f"[yt-dlp] adaptive {actual_height}p | vmime={video_mime} | amime={audio_mime}")
            else:
                # Fallback: adaptive requested but only combined available
                print("[yt-dlp] adaptive requested but only combined available — falling back")
                adaptive_mode = False

        if not adaptive_mode:
            # Combined: yt-dlp resolves the best format to info['url']
            video_stream_url = info.get('url', '')
            actual_height    = info.get('height', 0) or 0
            audio_stream_url = ''

            if not video_stream_url:
                all_formats = info.get('formats', [])
                combined = [f for f in all_formats
                            if f.get('vcodec') not in (None, 'none', '')
                            and f.get('acodec') not in (None, 'none', '')
                            and f.get('url')]
                combined.sort(key=lambda f: f.get('height', 0) or 0, reverse=True)
                if combined:
                    video_stream_url = combined[0].get('url', '')
                    actual_height    = combined[0].get('height', 0) or 0
            print(f"[yt-dlp] combined {actual_height}p")

        if not video_stream_url:
            print("[yt-dlp] No usable URL found")
            return None

        return {
            'id': info.get('id', ''),
            'youtube_id': info.get('id', ''),
            'title': info.get('title', 'Unknown Title'),
            'stream_url': video_stream_url,
            'audio_url':  audio_stream_url,
            'video_mime': video_mime,   # e.g. 'video/mp4; codecs="avc1.640028"'
            'audio_mime': audio_mime,   # e.g. 'audio/mp4; codecs="mp4a.40.2"'
            'actual_quality': f'{actual_height}p' if actual_height else 'auto',
            'visitor_data': '',
            'thumbnail_url': info.get('thumbnail', ''),
            'uploader': {'username': info.get('uploader', 'Unknown Channel')},
            'views': f"{view_count:,}",
            'like_count': info.get('like_count', 'Like'),
            'description': info.get('description', ''),
            'duration': info.get('duration', 0)
        }
    except Exception as e:
        print(f"[yt-dlp] Failed to parse info: {e}")
        return None


def _piped_get_stream(video_id, quality=None):
    """Last-resort fallback via Piped API instances."""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    requested_height = 0
    if quality:
        try:
            requested_height = int(''.join(filter(str.isdigit, quality)) or '0')
        except (ValueError, TypeError):
            pass

    piped_instances = [
        "https://pipedapi.kavin.rocks",
        "https://pipedapi-libre.kavin.rocks",
        "https://pipedapi.leptons.xyz",
        "https://pipedapi.smnz.de",
        "https://pipedapi.tokhmi.xyz"
    ]
    for uri in piped_instances:
        try:
            r = requests.get(f"{uri}/streams/{video_id}?proxy=true", timeout=5, verify=False)
            if r.status_code == 200:
                data = r.json()
                streams = data.get('videoStreams', [])
                if streams:
                    # Sort by height, pick closest to requested quality
                    streams.sort(key=lambda s: s.get('height', 0) or 0, reverse=True)
                    if requested_height > 0:
                        cands = [s for s in streams if (s.get('height') or 0) <= requested_height]
                        chosen = cands[0] if cands else streams[-1]
                    else:
                        chosen = streams[0]
                    audio_url = ""
                    if data.get('audioStreams'):
                        audio_url = data['audioStreams'][0].get('url', '')
                    print(f"[Piped] Got stream from {uri}: {chosen.get('quality','?')}")
                    return {
                        'id': video_id,
                        'youtube_id': video_id,
                        'title': data.get('title', 'Unknown Title'),
                        'stream_url': chosen.get('url', ''),
                        'audio_url': audio_url,
                        'actual_quality': chosen.get('quality', 'auto'),
                        'thumbnail_url': data.get('thumbnailUrl', ''),
                        'uploader': {'username': data.get('uploader', 'Unknown Channel')},
                        'views': f"{data.get('views', 0):,}",
                        'like_count': data.get('likes', 0),
                        'description': data.get('description', ''),
                        'duration': data.get('duration', 0)
                    }
        except Exception as ex:
            print(f"[Piped] {uri} failed: {ex}")
            continue
    return None

def get_video_stream(video_id, quality=None):
    """
    Priority order:
      1. yt-dlp (mweb/web_creator)  — returns spc-free URLs, works with server-side proxy
      2. Innertube                   — fast but ANDROID URLs have spc protection (403 on proxy)
      3. Piped API                   — last resort proxy fallback
    """
    # 1. Try yt-dlp first — mweb/web_creator client URLs are proxy-friendly
    print(f"[Stream] Trying yt-dlp for {video_id} quality={quality}")
    result = _ydl_get_stream(video_id, quality)
    if result:
        return result

    # 2. yt-dlp failed — try Innertube (may still work for some videos)
    print(f"[Stream] yt-dlp failed, trying Innertube for {video_id}")
    result = _innertube_get_stream(video_id, quality)
    if result:
        return result

    # 3. Both failed — try Piped
    print(f"[Stream] Innertube also failed, trying Piped API for {video_id}")
    return _piped_get_stream(video_id, quality)
