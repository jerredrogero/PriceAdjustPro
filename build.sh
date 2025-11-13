#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Build React frontend
cd frontend
export NODE_OPTIONS="--max-old-space-size=4096"

# Clear old build and cache
rm -rf build
rm -rf node_modules/.cache

npm install
mkdir -p build/static  # Ensure build directory exists
CI=false GENERATE_SOURCEMAP=false npm run build:production

# Create a symlink for main.js to handle the hashed filename
cd build/static/js
MAIN_JS=$(ls main.*.js)
ln -sf "$MAIN_JS" main.js
cd ../../..

# Copy the build to the Django static directory
mkdir -p ../price_adjust_pro/staticfiles/
cp -r build/* ../price_adjust_pro/staticfiles/

# Also copy the static directory to ensure it's available at both paths
mkdir -p ../price_adjust_pro/staticfiles/static/
cp -r build/static/* ../price_adjust_pro/staticfiles/static/

# Copy asset-manifest.json to the root
cp build/asset-manifest.json ../price_adjust_pro/staticfiles/

cd ..

# Collect static files
cd price_adjust_pro
python manage.py collectstatic --noinput --clear

# Run migrations
python manage.py migrate 