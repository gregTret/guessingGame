#!/usr/bin/env python3
"""
Test script to verify WSGI setup is working correctly.
"""

import sys
import os

# Add the flask_game directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Testing WSGI setup...")
    
    # Test importing the app
    print("1. Importing Flask app...")
    from app import app, socketio
    print("   ✓ Flask app imported successfully")
    
    # Test importing the WSGI application
    print("2. Importing WSGI application...")
    from wsgi import application
    print("   ✓ WSGI application imported successfully")
    
    # Test if application is callable
    print("3. Testing if application is callable...")
    if callable(application):
        print("   ✓ Application is callable")
    else:
        print("   ✗ Application is NOT callable")
        sys.exit(1)
    
    # Test basic app configuration
    print("4. Testing app configuration...")
    if app.config.get('SECRET_KEY'):
        print("   ✓ SECRET_KEY is configured")
    else:
        print("   ✗ SECRET_KEY is missing")
        sys.exit(1)
    
    print("\n✅ All tests passed! WSGI setup is working correctly.")
    print("\nTo start the application:")
    print("  Development: python wsgi.py")
    print("  Production:  gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 wsgi:application")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 