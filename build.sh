#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Build React frontend
cd frontend
npm install
npm run build
cd ..

# Collect static files
cd price_adjust_pro
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate 