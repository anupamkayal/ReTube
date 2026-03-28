from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import Video, Like, Comment
from extensions import db
from youtube_api import get_video_stream, search_youtube
import os
import uuid
import subprocess
import requests as req_lib
import urllib.parse

video_bp = Blueprint('video', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'mp4', 'mkv', 'webm', 'mov'}

def generate_thumbnail(video_path, thumbnail_path):
    try:
        subprocess.run([
            'ffmpeg', '-y', '-i', video_path, '-vframes', '1', '-ss', '00:00:02', 
            '-s', '1280x720', thumbnail_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

@video_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'video' not in request.files:
            flash('No video file selected')
            return redirect(request.url)
            
        file = request.files['video']
        if file.filename == '':
            flash('No video file selected')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            title = request.form.get('title', 'Untitled Video')
            description = request.form.get('description', '')
            
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            video_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            
            file.save(video_path)
            
            thumbnail_file = request.files.get('thumbnail')
            thumbnail_filename = None
            if thumbnail_file and thumbnail_file.filename != '':
                thumb_ext = thumbnail_file.filename.rsplit('.', 1)[1].lower()
                if thumb_ext in {'png', 'jpg', 'jpeg'}:
                    thumbnail_filename = f"thumb_{uuid.uuid4().hex}.{thumb_ext}"
                    thumbnail_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], thumbnail_filename))
            else:
                gen_thumb_filename = f"thumb_{uuid.uuid4().hex}.jpg"
                if generate_thumbnail(video_path, os.path.join(current_app.config['UPLOAD_FOLDER'], gen_thumb_filename)):
                    thumbnail_filename = gen_thumb_filename
                    
            new_video = Video(
                title=title,
                description=description,
                filename=unique_filename,
                thumbnail_filename=thumbnail_filename,
                uploader_id=current_user.id
            )
            
            db.session.add(new_video)
            db.session.commit()
            
            flash('Video uploaded successfully!')
            return redirect(url_for('main.index'))
            
    return render_template('upload.html')

@video_bp.route('/play')
def play():
    video_id = request.args.get('v')
    if not video_id:
        return "Video not found", 404
        
    is_local = video_id.isdigit()
    
    if is_local:
        video = Video.query.get_or_404(int(video_id))
        video.views += 1
        db.session.commit()
        related_videos = Video.query.filter(Video.id != video.id).limit(10).all()
        # Ensure template gets what it needs:
        video.uploader_name = video.uploader.username
        video.views_formatted = str(video.views)
        video_db_id = video.id
        
        # Also let's append some viral videos to related
        yt_related = search_youtube('viral videos 2024')
        related_videos = list(related_videos) + yt_related[:6]
    else:
        # YouTube Video
        yt_video = get_video_stream(video_id)
        if not yt_video:
            return "Video not found or DRM protected", 404
            
        video = yt_video  # dictionary
        video_db_id = 0 # No local DB ID
        
        related_query = f"{video['uploader']['username']} videos"
        yt_related = search_youtube(related_query)
        related_videos = yt_related[:10]

    # Check if current user liked it (only supported for local videos for now, or we can use string IDs for youtube if we change model)
    # The Like model expects integer video_id. So we can't easily like youtube videos without DB schema changes.
    user_liked = False
    likes_count = 0
    comments = []
    
    if is_local:
        if current_user.is_authenticated:
            like = Like.query.filter_by(user_id=current_user.id, video_id=video_db_id, is_dislike=False).first()
            if like:
                user_liked = True
                
        likes_count = Like.query.filter_by(video_id=video_db_id, is_dislike=False).count()
        comments = Comment.query.filter_by(video_id=video_db_id).order_by(Comment.created_at.desc()).all()
    else:
        # Mock likes for YouTube videos based on extracted data
        if 'like_count' in video and video['like_count'] != 'Like':
            try:
                likes_count = video['like_count']
            except:
                likes_count = 42000
        else:
            likes_count = 1000  # fallback mock
            
    return render_template('player.html', video=video, is_local=is_local, related_videos=related_videos, 
                           likes_count=likes_count, user_liked=user_liked, comments=comments)

@video_bp.route('/stream/<int:video_id>')
def stream(video_id):
    video = Video.query.get_or_404(video_id)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], video.filename)

@video_bp.route('/api/stream_url')
def api_stream_url():
    video_id = request.args.get('v')
    quality = request.args.get('q', '720p')
    
    if not video_id:
        return jsonify({'error': 'Missing video ID'}), 400
        
    if video_id.isdigit():
        video = Video.query.get_or_404(int(video_id))
        # Local video: we don't have on-the-fly transcoding yet, so just stream original
        return jsonify({'url': url_for('video.stream', video_id=video.id)})
    else:
        yt_video = get_video_stream(video_id, quality=quality)
        if yt_video and 'stream_url' in yt_video:
            vd_encoded = urllib.parse.quote(yt_video.get('visitor_data', ''), safe='')
            def _proxy(raw):
                return (url_for('video.proxy_stream', _external=False)
                        + '?url=' + urllib.parse.quote(raw, safe='')
                        + ('&vd=' + vd_encoded if vd_encoded else ''))
            return jsonify({
                'url':           _proxy(yt_video['stream_url']),
                'audio_url':     _proxy(yt_video['audio_url']) if yt_video.get('audio_url') else '',
                'video_mime':    yt_video.get('video_mime', ''),
                'audio_mime':    yt_video.get('audio_mime', ''),
                'actual_quality': yt_video.get('actual_quality', quality)
            })
        return jsonify({'error': 'Stream not found'}), 404


@video_bp.route('/proxy/stream')
def proxy_stream():
    """Server-side proxy for YouTube adaptive streams.
    Bypasses browser CORS restrictions by piping the YouTube URL through Flask.
    Supports HTTP Range requests so seeking works correctly.
    """
    raw_url = request.args.get('url', '')
    if not raw_url:
        return 'Missing url', 400

    # Basic safety check — only proxy googlevideo / youtube domains
    parsed = urllib.parse.urlparse(raw_url)
    allowed_hosts = ('googlevideo.com', 'youtube.com', 'ytimg.com', 'googleusercontent.com')
    if not any(parsed.netloc.endswith(h) for h in allowed_hosts):
        return 'Forbidden host', 403

    # Detect which YouTube client signed this URL (c=ANDROID / IOS / WEB / etc.)
    # YouTube rejects requests whose User-Agent doesn't match the signing client.
    qs_params = urllib.parse.parse_qs(parsed.query)
    client_name = (qs_params.get('c') or ['ANDROID'])[0].upper()

    CLIENT_UA = {
        'ANDROID': 'com.google.android.youtube/21.05.46 (Linux; U; Android 14; en_US) gzip',
        'ANDROID_VR': 'com.google.android.apps.youtube.vr.oculus/1.62.27 (Linux; U; Android 12L; eureka-user Build/SQ3A.220605.009.A1) gzip',
        'IOS': 'com.google.ios.youtube/19.45.4 (iPhone16,2; U; CPU iOS 18_1_0 like Mac OS X)',
        'MWEB': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36',
        'ANDROID_MUSIC': 'com.google.android.apps.youtube.music/7.16.51 (Linux; U; Android 14; en_US) gzip',
        'ANDROID_UNPLUGGED': 'com.google.android.apps.youtube.unplugged/8.13.0 (Linux; U; Android 14; en_US) gzip',
        'ANDROID_TESTSUITE': 'com.google.android.youtube/1.9 (Linux; U; Android 14; en_US) gzip',
        'ANDROID_LITE': 'com.google.android.apps.youtube.mango/3.31.5 (Linux; U; Android 14; en_US) gzip',
        'WEB': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
        'TVHTML5': 'Mozilla/5.0 (PlayStation; PlayStation 4/8.03) AppleWebKit/605.1.15 Safari/605.1.15',
    }
    user_agent = CLIENT_UA.get(client_name, CLIENT_UA['ANDROID_VR'])

    # Forward Range header from the browser so seeking / partial content works
    headers = {
        'User-Agent': user_agent,
        'Referer': 'https://www.youtube.com/',
    }

    # If YouTube signed this URL with rqh=1 (Required Query Headers),
    # we must send X-Goog-Visitor-Id alongside the request.
    visitor_data = request.args.get('vd', '')
    if visitor_data:
        headers['X-Goog-Visitor-Id'] = visitor_data

    range_header = request.headers.get('Range')
    if range_header:
        headers['Range'] = range_header

    try:
        upstream = req_lib.get(raw_url, headers=headers, stream=True, timeout=15)
    except Exception as e:
        return f'Upstream error: {e}', 502

    # Log for debugging
    print(f'[Proxy] client={client_name} status={upstream.status_code} url={raw_url[:80]}...')

    # Pass through the important response headers
    resp_headers = {}
    for h in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges'):
        val = upstream.headers.get(h)
        if val:
            resp_headers[h] = val

    # Default accept-ranges so the browser knows it can seek
    resp_headers.setdefault('Accept-Ranges', 'bytes')
    # Allow same-origin embed
    resp_headers['Access-Control-Allow-Origin'] = '*'

    status_code = upstream.status_code  # 200 or 206 (partial)

    def generate():
        for chunk in upstream.iter_content(chunk_size=65536):
            if chunk:
                yield chunk

    return Response(
        stream_with_context(generate()),
        status=status_code,
        headers=resp_headers
    )

@video_bp.route('/thumbnail/<int:video_id>')
def thumbnail(video_id):
    video = Video.query.get_or_404(video_id)
    if video.thumbnail_filename:
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], video.thumbnail_filename)
    else:
        from flask import abort
        abort(404)

@video_bp.route('/like/<int:video_id>', methods=['POST'])
@login_required
def toggle_like(video_id):
    video = Video.query.get_or_404(video_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, video_id=video.id).first()
    
    if existing_like:
        if existing_like.is_dislike:
            existing_like.is_dislike = False
            msg = 'liked'
        else:
            db.session.delete(existing_like)
            msg = 'unliked'
    else:
        new_like = Like(user_id=current_user.id, video_id=video.id, is_dislike=False)
        db.session.add(new_like)
        msg = 'liked'
        
    db.session.commit()
    likes_count = Like.query.filter_by(video_id=video.id, is_dislike=False).count()
    
    return jsonify({'status': 'success', 'message': msg, 'likes': likes_count})

@video_bp.route('/comment/<int:video_id>', methods=['POST'])
@login_required
def add_comment(video_id):
    video = Video.query.get_or_404(video_id)
    text = request.form.get('text')
    
    if text and text.strip():
        new_comment = Comment(text=text.strip(), user_id=current_user.id, video_id=video.id)
        db.session.add(new_comment)
        db.session.commit()
        
    return redirect(url_for('video.play', v=video.id))
