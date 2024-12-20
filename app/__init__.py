from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    # Get DATABASE_URL from environment, fallback to localhost for local development
    database_url = os.getenv('DATABASE_URL', 'postgresql://walkingbus:password@localhost:5432/walkingbus')
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    return app