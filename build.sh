#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Build React frontend
cd frontend
export NODE_OPTIONS="--max-old-space-size=4096"
npm install
mkdir -p build/static  # Ensure build directory exists
CI=false GENERATE_SOURCEMAP=false npm run build:production

# Copy the build to the Django static directory
mkdir -p ../price_adjust_pro/staticfiles/
cp -r build/* ../price_adjust_pro/staticfiles/
cd ..

# Collect static files
cd price_adjust_pro
python manage.py collectstatic --noinput --clear

# Run migrations
python manage.py migrate 