# Flask Guessing Game

Simple Flask app for session-based name tracking.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Generate secret key:**
   ```bash
   python generate_key.py
   ```

3. **Create .env file:**
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` and paste your generated SECRET_KEY.

4. **Run the app:**
   ```bash
   python app.py
   ```

Visit `http://localhost:5000` to start the game.

## Key Length
- **32 bytes (64 hex characters)** is recommended for production
- Never commit your actual `.env` file to git
- Use `.env.example` for sharing the template 