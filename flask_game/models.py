from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timedelta
import random
import string

db = SQLAlchemy()

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    total_wins = db.Column(db.Integer, default=0)
    total_losses = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    host_player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    secret_pattern = db.Column(db.String(25), nullable=False)  # "Black,White,Yellow,Red,Green"
    status = db.Column(db.String(20), default='waiting')  # waiting/active/completed
    winner_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=True)
    max_players = db.Column(db.Integer, default=15)
    invite_only = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    host = db.relationship('Player', foreign_keys=[host_player_id], backref='hosted_games')
    winner = db.relationship('Player', foreign_keys=[winner_id])
    
    @staticmethod
    def generate_pattern():
        """Generate a random 5-color pattern with no repetitions"""
        colors = ['Black', 'White', 'Yellow', 'Red', 'Green', 'Blue', 'Pink']
        pattern = random.sample(colors, 5)
        return ','.join(pattern)
    
    def update_activity(self):
        """Update the last activity timestamp"""
        try:
            self.last_activity = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            # Handle missing column gracefully
            if "no such column" in str(e).lower():
                db.session.rollback()
                return
            raise
    
    @staticmethod
    def cleanup_inactive_games():
        """Remove games that have been inactive for 15+ minutes"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=15)
            inactive_games = Game.query.filter(
                Game.last_activity < cutoff_time,
                Game.status.in_(['waiting', 'active'])
            ).all()
            
            for game in inactive_games:
                # Clean up related data
                GamePlayer.query.filter_by(game_id=game.id).delete()
                Guess.query.filter_by(game_id=game.id).delete()
                GameInvite.query.filter_by(game_id=game.id).delete()
                db.session.delete(game)
            
            if inactive_games:
                db.session.commit()
                
            return len(inactive_games)
        except Exception as e:
            # Handle missing column gracefully
            if "no such column" in str(e).lower():
                # Column doesn't exist yet, add it
                try:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE game ADD COLUMN last_activity DATETIME DEFAULT CURRENT_TIMESTAMP'))
                        conn.commit()
                    db.session.commit()
                    return 0
                except:
                    pass
            return 0

class GamePlayer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    status = db.Column(db.String(20), default='waiting')  # waiting/playing/solved/forfeited
    guess_count = db.Column(db.Integer, default=0)
    join_time = db.Column(db.DateTime, default=datetime.utcnow)
    finish_time = db.Column(db.DateTime, nullable=True)
    last_guess_time = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    game = db.relationship('Game', backref='game_players')
    player = db.relationship('Player', backref='game_participations')

class Guess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    guess_pattern = db.Column(db.String(25), nullable=False)  # "Black,Black,Black,Black,Black"
    correct_positions = db.Column(db.Integer, nullable=False)
    correct_colors = db.Column(db.Integer, nullable=False)
    guess_number = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    game = db.relationship('Game', backref='guesses')
    player = db.relationship('Player', backref='guesses')

class GameInvite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    invite_code = db.Column(db.String(10), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # Will be set when game starts
    
    # Relationships
    game = db.relationship('Game', backref='invites')
    
    @staticmethod
    def generate_invite_code():
        """Generate a unique 6-character invite code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def evaluate_guess(secret_pattern, guess_pattern):
    """
    Evaluate a guess against the secret pattern
    Returns (correct_positions, correct_colors)
    """
    secret = secret_pattern.split(',')
    guess = guess_pattern.split(',')
    
    correct_positions = 0
    correct_colors = 0
    
    # Count exact matches (correct position and color)
    secret_remaining = []
    guess_remaining = []
    
    for i in range(5):
        if secret[i] == guess[i]:
            correct_positions += 1
        else:
            secret_remaining.append(secret[i])
            guess_remaining.append(guess[i])
    
    # Count correct colors in wrong positions
    for color in guess_remaining:
        if color in secret_remaining:
            correct_colors += 1
            secret_remaining.remove(color)
    
    return correct_positions, correct_colors 