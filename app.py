from flask import Flask
from config import Config
from extensions import db, login_manager
from models import User
import os
from flask import send_from_directory
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize Extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.video import video_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(video_bp)

    # Make upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    with app.app_context():
        # Create database tables
        db.create_all()

    @app.route('/sw.js')
    def serve_sw():
        return send_from_directory('static', 'sw.js', mimetype='application/javascript')

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
