#!/usr/bin/env python3
"""
WSGI entry point for the Flask Guessing Game application.
This file is used by WSGI servers like Gunicorn, uWSGI, or mod_wsgi.
"""

import sys
import os

# Add the flask_game directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app and SocketIO
from app import app, socketio, init_app

# Initialize the application for WSGI deployment
init_app()

# The WSGI application object
# For Flask-SocketIO apps, we need to use the underlying Flask app
# The SocketIO functionality will be handled by the eventlet worker
application = app

if __name__ == "__main__":
    # This allows running the WSGI file directly for testing
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting WSGI app on port {port}")
    socketio.run(app, debug=False, host='0.0.0.0', port=port) 