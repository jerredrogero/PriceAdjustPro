# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend (Django)
```bash
# Development server
python manage.py runserver

# Database operations
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser

# Custom management commands
python manage.py process_promotions --all-unprocessed
python manage.py update_sales_status

# Static files
python manage.py collectstatic
```

### Frontend (React)
```bash
cd frontend
npm start                    # Development server (localhost:3000)
npm run build               # Production build (no source maps)
npm run build:production    # Optimized production build
npm test                    # Run tests
npm run analyze            # Bundle analysis
```

### Full Development Setup
```bash
# Backend setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver &

# Frontend setup (separate terminal)
cd frontend
npm install
npm start
```

## Architecture Overview

### Core Application
PriceAdjustPro is a Django + React application that helps Costco shoppers track receipts and identify price adjustment opportunities. The system processes PDF/image receipts using Google Gemini AI and compares prices against official promotions.

### Key Components

**Django Backend (`receipt_parser/`):**
- `models.py`: Core data models (Receipt, LineItem, CostcoItem, PriceAdjustmentAlert, Official Promotions)
- `views.py`: Both web views and API endpoints for frontend
- `utils.py`: Business logic for receipt processing and price comparisons
- `serializers.py`: DRF serializers for API responses
- `management/commands/`: Custom Django commands for processing promotions

**React Frontend (`frontend/src/`):**
- `components/`: Reusable UI components (authentication, receipt components)
- `pages/`: Page-level components (Dashboard, Analytics, PriceAdjustments)
- `contexts/`: Global state management (AuthContext, ThemeContext)
- `api/`: Axios configuration for API communication

### Database Models
- **Receipt**: Main transaction entity with user association and file uploads
- **LineItem**: Individual items from receipts with price tracking
- **CostcoItem**: Master catalog of items with current pricing
- **PriceAdjustmentAlert**: Core business logic for price adjustment opportunities
- **Official Promotion Models**: CostcoPromotion, CostcoPromotionPage, OfficialSaleItem

### Tech Stack
- **Backend**: Django 5.0.6, Django REST Framework, PostgreSQL/SQLite, Redis
- **Frontend**: React 18, TypeScript, Material-UI, Recharts, Axios
- **AI Integration**: Google Gemini API for receipt parsing
- **Deployment**: Gunicorn, WhiteNoise, AWS S3, Sentry monitoring

## File Structure

```
/PriceAdjustPro/           # Project root
├── CLAUDE.md              # This file - Claude Code instructions
├── manage.py              # Django management script
├── price_adjust_pro/      # Django project configuration
├── receipt_parser/        # Main Django app
│   ├── models.py          # Database models
│   ├── views.py           # Web and API views
│   ├── utils.py           # Business logic utilities
│   ├── serializers.py     # DRF serializers
│   └── management/commands/ # Custom Django commands
├── frontend/              # React frontend
│   ├── src/components/    # Reusable components
│   ├── src/pages/        # Page components
│   ├── src/contexts/     # React contexts
│   └── src/api/          # API layer
├── media/                # User uploads
│   ├── receipts/         # Receipt files (organized by user)
│   └── promo_booklets/   # Official Costco promotions
└── static/staticfiles/   # Static file serving
```

## Key Features

### Receipt Processing
- Supports PDF and image receipt uploads
- AI-powered OCR using Google Gemini API
- Automatic line item extraction and price parsing
- User review and manual editing capabilities

### Price Adjustment Intelligence
- Compares user receipts against official Costco promotions
- Tracks 30-day price adjustment eligibility
- Multi-source data validation (user edits vs. official promotions)
- Automated alert generation and expiration

### Security Considerations
- Custom authentication middleware
- CSRF protection for API endpoints
- Secure file upload handling
- Environment-based configuration for sensitive data

## Development Notes

### Frontend-Backend Communication
- Frontend runs on localhost:3000 (development)
- Backend API on localhost:8000
- Proxy configuration in package.json routes API calls
- Token-based authentication with automatic header injection

### Database Migrations
Always run migrations after model changes:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Static Files
Production builds copy React build to Django staticfiles:
```bash
npm run build:production
python manage.py collectstatic
```

### Testing
- Backend: Django test framework in `tests.py`
- Frontend: Jest + React Testing Library

## Production Deployment
The application is configured for production deployment with:
- PostgreSQL database (via DATABASE_URL)
- Redis for caching
- AWS S3 for file storage
- Gunicorn WSGI server
- WhiteNoise for static file serving
- Sentry for error monitoring