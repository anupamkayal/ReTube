# YouTube Vanced Clone Platform

A full-featured video streaming platform that visually and functionally resembles YouTube Vanced.

## Features Included

### Core Functionality
- **User Authentication:** Signup, login, logout, securely hashed passwords.
- **Video Discovery:** Search functionality with categorical filters (Music, Gaming, News, etc.).
- **Social Engagement:** Like (real-time updating), Comment, and Share (using Native Web Share API).
- **Channels/Profiles:** Dedicated channel pages with a grid of uploaded videos.
- **Recommendations:** Basic recommendation system fetching similar/latest content.

### Advanced "Vanced" Features
- **Ad-Free Playback:** All videos hosted natively bypass advertising networks.
- **Background Play:** Utilizing `MediaSession API` and `visibilitychange` listeners to keep play alive when the tab is switched.
- **Video Download:** Direct access link to download raw video.
- **SponsorBlock Mock:** Integrated logic to auto-skip predefined sponsor segments via `timeupdate` listening.
- **Force Quality Mock:** UI implemented. Complete the FFmpeg HLS tutorial below to make it live.
- **Playback Speed:** 0.25x – 2x controls natively affecting `<video>` playback rate.
- **Picture-in-Picture:** Built-in PiP mode.
- **Dark/Light Theme:** Fully responsive theme switching saved via `localStorage`.

---

## 1. Step-by-Step Setup and Run Instructions

1. **Install Python & Virtual Environment:**
   Ensure Python 3.10+ is installed.
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Dependencies:**
   ```bash
   pip install flask flask-sqlalchemy flask-login flask-bcrypt flask-cors werkzeug
   ```

3. **Install FFmpeg (Critical for Thumbnails & Future Transcoding):**
   - Windows: Download from `gyan.dev/ffmpeg/builds/` and add the `bin` folder to your System PATH.
   - Mac: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

4. **Run the Application:**
   ```bash
   python app.py
   ```
   The database tables and upload folders are automatically generated on first boot.

5. **Visit the Dashboard:**
   Open a browser to `http://localhost:5000`.

---

## 2. Explanation of Architecture

This platform uses a classical web MVC architecture optimized for solo deployment without the overhead of heavy SPA frameworks.

- **Frontend (View):** Jinja2 Templates ([base.html](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/templates/base.html), [player.html](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/templates/player.html), [index.html](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/templates/index.html)) using Vanilla HTML/CSS/JS. Responsive layout logic uses CSS Flexbox/Grid mapped to CSS custom properties (`var(--yt-*)`). It achieves SPA-like speeds without React payload sizes.
- **Backend (Controller):** Flask application factory dividing responsibility into isolated Blueprints (`main`, `auth`, [video](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/youtube_api.py#38-82)). 
- **Database (Model):** SQLite via Flask-SQLAlchemy handling [User](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/models.py#5-15), [Video](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/models.py#16-30), [Comment](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/models.py#31-38), [Like](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/models.py#39-44), and [SponsorBlock](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/models.py#45-51) models. ORM relationships map videos to channels and comments effortlessly.
- **Storage Layer:** Binary video objects are kept cleanly out of the SQLite file, stored on-disk in `static/uploads/`, served back using Flask's `send_from_directory()`.

---

## 3. Suggestions for Scaling

If this project grows beyond a home server, consider these architectural scaling paths:

### A. Database Upgrade (PostgreSQL)
SQLite locks entirely during writes. Change `DATABASE_URL` in your configuration to point to a PostgreSQL instance for concurrency.
```python
# config.py
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://user:pass@localhost:5432/vanced_db')
```

### B. Adaptive Bitrate Streaming (HLS) & Storage (S3)
Currently, MP4s are served directly. This halts on low-bandwidth networks.
**To upgrade (The Adaptive Quality Fix):**
1. When a user uploads a video, use a background worker (e.g., Celery) to run FFmpeg:
   ```bash
   ffmpeg -i input.mp4 \
     -vf scale=w=1920:h=1080 -c:v h264 -b:v 5M -hls_time 10 -hls_playlist_type vod 1080p.m3u8 \
     -vf scale=w=1280:h=720 -c:v h264 -b:v 3M -hls_time 10 -hls_playlist_type vod 720p.m3u8 \
     -master_pl_name master.m3u8
   ```
2. Upload the resulting `.ts` chunks and `.m3u8` playlists to an **AWS S3 Bucket**.
3. In [player.html](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/templates/player.html), import `hls.js` and point `<video>` source to `master.m3u8`. `hls.js` automatically shifts quality, fulfilling the Mock Quality menu's true potential.

### C. CDN & Caching (Load Balancing)
1. **CDN:** Place Cloudflare or AWS CloudFront in front of the application. Configure the CDN to aggressively cache `static/uploads/` and `static/thumbnails/`. This offloads 99% of bandwidth from your Flask server.
2. **Redis Caching:** Wrap popular endpoints (like the homepage video feed) in `Flask-Caching` backed by Redis so you don't query the database for every new visitor.
3. **Load Balancer:** Run `gunicorn -w 4 app:create_app()` to handle multiple requests, and sit it behind an Nginx reverse proxy.

### D. Railway Free Tier Deployment
You requested free server deployment options. I have fully equipped this codebase for **Railway.app**:
1. Push this folder to a new **GitHub Repository**.
2. Go to **Railway.app**, log in via GitHub, and click **New Project -> Deploy from Github rep**.
3. Railway will auto-detect the [Procfile](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/Procfile), [requirements.txt](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/requirements.txt), and [apt.txt](file:///c:/Users/DELL/Downloads/app%20upload/youtube_mod/apt.txt) (to install FFmpeg) and start building your web server.
4. **Important**: Because Railway wipes free-tier file systems whenever the server sleeps, you MUST go to your Railway Service Settings -> **Volumes**, and create a Volume mounted at `/data`.
5. Under your Service Variables, add `RAILWAY_VOLUME_MOUNT_PATH = /data`. The app will automatically route your SQLite database and video uploads directly into the persistent volume, preventing them from being erased!
