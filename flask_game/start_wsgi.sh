#!/bin/bash
# Start the Flask Guessing Game using Gunicorn WSGI server

# Set environment variables
export FLASK_ENV=production
export DEBUG=false
export PORT=5000

# Install requirements if needed
# pip install -r requirements-wsgi.txt

# Activate the virtual environment
source .venv/bin/activate

# Start the app with Gunicorn
echo "Starting Flask Guessing Game on port $PORT..."
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 wsgi:application

# Alternative startup options:
# 
# For development with more workers:
# gunicorn --worker-class eventlet -w 4 --bind 0.0.0.0:$PORT wsgi:application
#
# For production with logging:
# gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --access-logfile - --error-logfile - wsgi:application
#
# Run directly with Python (for testing):
# python wsgi.py 