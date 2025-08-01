# GuessingGame - Multiplayer Pattern Challenge

![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-v2.0+-green.svg)
![SQLite](https://img.shields.io/badge/sqlite-v3-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

A real-time multiplayer guessing game where players compete to crack secret color patterns. Features mobile-optimized interface, WebSocket support, and production-ready WSGI deployment.

## Quick Start

### Prerequisites
- Python 3.8+
- PDM (Python Dependency Manager) or pip
- Modern web browser with JavaScript enabled

### Installation with PDM (Recommended)

1. **Install PDM**
   ```bash
   # macOS/Linux
   curl -sSL https://pdm-project.org/install-pdm.py | python3 -
   
   # Windows PowerShell
   (Invoke-WebRequest -Uri https://pdm-project.org/install-pdm.py -UseBasicParsing).Content | python -
   
   # Or with pip
   pip install --user pdm
   ```

2. **Clone and setup**
   ```bash
   git clone https://github.com/yourusername/guessingGame.git
   cd guessingGame/flask_game
   pdm install
   ```

3. **Generate secret key**
   ```bash
   pdm run python generate_key.py
   ```

4. **Run the application**
   ```bash
   pdm run python app.py
   ```

### Installation with pip

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/guessingGame.git
   cd guessingGame/flask_game
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Generate secret key**
   ```bash
   python generate_key.py
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

### Access the Game
Open your browser and navigate to `http://localhost:5000`

## How to Play

1. **Enter your name** - Remembered for future sessions
2. **Join or create a game** - Public lobby or private invite codes
3. **Wait for players** - Host can start with any number of participants
4. **Crack the pattern** - 7 colors: Black, White, Yellow, Red, Green, Blue, Pink
5. **Use the feedback** - ✓ for correct position, ○ for correct color/wrong position
6. **Win by speed** - First to solve wins, others can keep playing
7. **Track your progress** - Wins and losses saved automatically

## Mobile Features

- **Responsive design** optimized for iPhone 12 (390px) and similar devices
- **4-column color grid** on mobile for easy touch interaction
- **Touch-friendly buttons** with minimum 44px height
- **Reorganized layout** with colors above game area on mobile
- **Confirmation dialogs** for critical actions like forfeit

## Production Deployment

### WSGI Support
The application includes production-ready WSGI deployment:

```bash
# Test WSGI setup
python flask_game/test_wsgi.py

# Deploy with Gunicorn
cd flask_game
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 wsgi:application

# Or use the provided script
chmod +x start_wsgi.sh
./start_wsgi.sh
```

### Environment Variables
- `PORT`: Server port (default: 5000)
- `DEBUG`: Enable debug mode (default: false for production)
- `SECRET_KEY`: Flask session encryption (generated by 
generate_key.py)
- `scpIP`: IP and directory to throw this into with the deploy script
## Tech Stack

- **Backend**: Flask with SocketIO for real-time features
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: Vanilla JavaScript with modern CSS Grid/Flexbox
- **Design**: Custom glassmorphism theme with CSS variables
- **Architecture**: Session-based authentication, RESTful routes
- **Real-time**: WebSocket support for live game updates
- **Deployment**: WSGI-compatible with Gunicorn + eventlet

## Project Structure

```
guessingGame/
├── flask_game/
│   ├── app.py              # Main Flask application
│   ├── wsgi.py             # WSGI entry point for production
│   ├── models.py           # Database models (Player, Game, Guess, etc.)
│   ├── templates/          # HTML templates with mobile-responsive design
│   │   ├── base.html       # Base template with CSS framework
│   │   ├── lobby.html      # Game browser and stats
│   │   ├── game.html       # Main game interface (mobile-optimized)
│   │   ├── waiting_room.html # Game lobby with real-time updates
│   │   └── results.html    # Game results and leaderboard
│   ├── instance/
│   │   └── game.db         # SQLite database (auto-created)
│   ├── requirements.txt    # Python dependencies
│   ├── requirements-wsgi.txt # Production WSGI dependencies
│   ├── generate_key.py     # Secret key generator
│   ├── start_wsgi.sh       # Production startup script
│   └── test_wsgi.py        # WSGI configuration test
├── deploy.py               # Deployment script
└── README.md
```

## Configuration

### Environment Variables
- `SECRET_KEY`: Flask session encryption (generated by generate_key.py)
- `PORT`: Server port (default: 5000)
- `DEBUG`: Enable debug mode (default: true for development)
- `FLASK_ENV`: Environment mode (development/production)

### Game Settings
- **Max Players**: 15 (configurable in models.py)
- **Guess Timeout**: 5 minutes per turn
- **Game Cleanup**: Inactive games removed after 15 minutes
- **Session Duration**: Player names remembered for 30 days
- **Pattern Colors**: 7 colors (Black, White, Yellow, Red, Green, Blue, Pink)

## Development

### Running in Development Mode
```bash
# With PDM
pdm run python app.py

# With pip/venv
source .venv/bin/activate
python app.py
```

### Testing WSGI Setup
```bash
python test_wsgi.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on both desktop and mobile
5. Submit a pull request

## License

MIT License - see LICENSE file for details
