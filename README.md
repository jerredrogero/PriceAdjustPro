# PriceAdjustPro

A web application for managing and analyzing Costco receipts. Upload your receipts, track your spending, and get insights into your Costco purchases.

## Features

- PDF receipt upload and parsing
- Detailed receipt view with line items
- Modern, responsive UI with Costco branding
- Secure user authentication
- Automatic total and tax calculation

## Tech Stack

- **Backend**: Django (Python)
- **Frontend**: React with TypeScript
- **UI Framework**: Material-UI (MUI)
- **Database**: SQLite (development)
- **Authentication**: Django built-in auth

## Setup

### Backend Setup

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Run migrations:
```bash
python manage.py migrate
```

4. Create a superuser:
```bash
python manage.py createsuperuser
```

5. Start the Django development server:
```bash
python manage.py runserver
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd price_adjust_pro/frontend
```

2. Install Node dependencies:
```bash
npm install
```

3. Start the React development server:
```bash
npm start
```

## Development

- Backend server runs on http://localhost:8000
- Frontend development server runs on http://localhost:3000
- API endpoints are proxied from the frontend to the backend

## Email configuration

Verification and password reset emails require SMTP credentials. Set the
`EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` environment variables (along with
optional overrides such as `EMAIL_HOST`, `EMAIL_PORT`, and `DEFAULT_FROM_EMAIL`)
before deploying to production. Without these values, the app falls back to the
console email backend in development and refuses to start in production so you
don't accidentally ship without working email.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request 