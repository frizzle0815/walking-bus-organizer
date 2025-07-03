# Walking Bus Organizer - Agent Guidelines

## Commands
- **Run**: `flask run` or `python migrate_and_run.py`
- **Docker**: `docker-compose up`  
- **Database**: `flask db upgrade` (migrations)
- **No dedicated test suite found** - mainly manual testing through web interface

## Architecture
- **Flask web app** with PostgreSQL database, Redis cache, and scheduler service
- **Main components**: `app/` (Flask app), `migrations/` (DB schema), `data/` (runtime data)
- **Key modules**: `models.py` (SQLAlchemy ORM), `routes.py` (API endpoints), `services/` (business logic)
- **Real-time features**: Server-Sent Events (SSE), Redis pub/sub, push notifications
- **PWA support**: Service worker, offline capability, mobile-first design

## Code Style
- **Python**: Snake_case for variables/functions, PascalCase for classes
- **Database**: SQLAlchemy ORM with relationship mapping
- **Frontend**: Vanilla JS with Bootstrap 5, Axios for API calls
- **Error handling**: Try/catch blocks with proper logging
- **Imports**: Flask imports grouped, then local imports with relative paths
- **German language** used in UI/comments (this is a German school project)

## Key Features
- Multi-tenant walking bus management with authentication
- Real-time dashboard with participant status updates
- Calendar-based participation planning with overrides
- Weather integration and holiday detection
- Push notifications for mobile devices
