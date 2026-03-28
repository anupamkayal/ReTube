from flask import Blueprint, render_template, request
from models import Video, User
from extensions import db
from youtube_api import search_youtube

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    category = request.args.get('c', 'All')
    
    query = Video.query

    if category != 'All':
        # Simple logical filtering: search for category keyword in title or description
        query = query.filter(db.or_(
            Video.title.ilike(f'%{category}%'),
            Video.description.ilike(f'%{category}%')
        ))

    videos = query.order_by(Video.created_at.desc()).all()
    
    import random
    default_topics = ['viral videos 2026', 'trending videos this week', 'popular music videos', 'top gaming highlights', 'funny viral vlogs', 'tech reviews 2026']
    yt_query = category if category != 'All' else random.choice(default_topics)
    yt_videos = search_youtube(yt_query)
    
    results = list(videos) + yt_videos
    return render_template('index.html', results=results, active_category=category)

@main_bp.route('/search', methods=['GET', 'POST'])
def search():
    query_str = request.form.get('query') or request.args.get('query', '')
    if query_str:
        videos = Video.query.filter(db.or_(
            Video.title.ilike(f'%{query_str}%'),
            Video.description.ilike(f'%{query_str}%')
        )).order_by(Video.created_at.desc()).all()
    else:
        videos = Video.query.order_by(Video.created_at.desc()).all()
        
    import random
    default_topics = ['viral videos 2026', 'trending videos this week', 'popular music videos', 'top gaming highlights', 'funny viral vlogs', 'tech reviews 2026']
    yt_query = query_str if query_str else random.choice(default_topics)
    yt_videos = search_youtube(yt_query)
    
    results = list(videos) + yt_videos
    return render_template('index.html', results=results, active_category='All', query=query_str)

@main_bp.route('/channel/<username>')
def channel(username):
    user = User.query.filter_by(username=username).first_or_404()
    videos = Video.query.filter_by(uploader_id=user.id).order_by(Video.created_at.desc()).all()
    return render_template('index.html', results=videos, active_category='All', channel_user=user)
