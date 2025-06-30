from flask import Flask, session, request, redirect, url_for, jsonify, render_template_string, render_template
from datetime import timedelta, datetime
import os
from dotenv import load_dotenv
from models import db, Player, Game, GamePlayer, Guess, GameInvite, evaluate_guess

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///game.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

def get_current_player():
    """Get current player from session, create if doesn't exist"""
    if 'player_name' not in session:
        return None
    
    player = Player.query.filter_by(name=session['player_name']).first()
    if not player:
        player = Player(name=session['player_name'])
        db.session.add(player)
        db.session.commit()
    return player

@app.route('/')
def index():
    if 'player_name' not in session:
        return redirect(url_for('enter_name'))
    
    return redirect(url_for('lobby'))

@app.route('/enter_name', methods=['GET', 'POST'])
def enter_name():
    if request.method == 'POST':
        session['player_name'] = request.form['name']
        session.permanent = True  # Makes the session permanent
        return redirect(url_for('lobby'))
    return render_template('enter_name.html')

@app.route('/game')
def game():
    player_name = session.get('player_name', 'Anonymous')
    return f"Playing as: {player_name}"

@app.route('/reset')
def reset_name():
    session.pop('player_name', None)
    return redirect(url_for('enter_name'))

@app.route('/lobby')
def lobby():
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    # Clean up inactive games
    Game.cleanup_inactive_games()
    
    # Get public waiting games
    public_games = Game.query.filter_by(status='waiting', invite_only=False).all()
    
    # Count total players in lobby
    total_players = GamePlayer.query.join(Game).filter(Game.status == 'waiting').count()
    
    return render_template('lobby.html', 
                         player=player, 
                         public_games=public_games, 
                         total_players=total_players)

@app.route('/create_game', methods=['GET', 'POST'])
def create_game():
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    # Clean up inactive games
    Game.cleanup_inactive_games()
    
    if request.method == 'POST':
        invite_only = 'invite_only' in request.form
        
        # Create new game
        secret_pattern = Game.generate_pattern()
        game = Game(
            host_player_id=player.id,
            secret_pattern=secret_pattern,
            invite_only=invite_only
        )
        db.session.add(game)
        db.session.flush()  # Get the game.id
        
        # Console log for testing
        print(f"🎯 GAME #{game.id} CREATED - Secret Pattern: {secret_pattern}")
        print(f"   Host: {player.name}")
        print(f"   Colors: {secret_pattern.replace(',', ' → ')}")
        print("-" * 50)
        
        # Add host as first player
        game_player = GamePlayer(game_id=game.id, player_id=player.id)
        db.session.add(game_player)
        
        # Create invite code
        invite = GameInvite(
            game_id=game.id,
            invite_code=GameInvite.generate_invite_code()
        )
        db.session.add(invite)
        db.session.commit()
        
        return redirect(url_for('game_room', game_id=game.id))
    
    return render_template('create_game.html')

@app.route('/join/<invite_code>')
def join_by_invite(invite_code):
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    invite = GameInvite.query.filter_by(invite_code=invite_code).first()
    if not invite or invite.expires_at:
        return "Invalid or expired invite code", 404
    
    return redirect(url_for('join_game', game_id=invite.game_id))

@app.route('/join_game/<int:game_id>')
def join_game(game_id):
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    game = Game.query.get_or_404(game_id)
    
    # Check if game is still waiting
    if game.status != 'waiting':
        return "Game has already started or ended", 400
    
    # Check if player already in game
    existing = GamePlayer.query.filter_by(game_id=game_id, player_id=player.id).first()
    if existing:
        return redirect(url_for('game_room', game_id=game_id))
    
    # Check if game is full
    current_players = GamePlayer.query.filter_by(game_id=game_id).count()
    if current_players >= game.max_players:
        return "Game is full", 400
    
    # Add player to game
    game_player = GamePlayer(game_id=game_id, player_id=player.id)
    db.session.add(game_player)
    
    # Update game activity
    game.update_activity()
    
    return redirect(url_for('game_room', game_id=game_id))

@app.route('/game/<int:game_id>')
def game_room(game_id):
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    game = Game.query.get_or_404(game_id)
    game_player = GamePlayer.query.filter_by(game_id=game_id, player_id=player.id).first()
    
    if not game_player:
        return "You are not in this game", 403
    
    if game.status == 'waiting':
        return render_waiting_room(game, player)
    elif game.status == 'active':
        # Check if player wants to spectate (finished players watching others)
        spectate_mode = request.args.get('spectate') == 'true'
        if spectate_mode or game_player.status in ['solved', 'forfeited']:
            # Show the main game interface but indicate spectator mode
            return render_game_play(game, player, game_player, spectate_mode=True)
        else:
            return render_game_play(game, player, game_player)
    else:
        return render_game_results(game, player)

def render_waiting_room(game, player):
    players = GamePlayer.query.filter_by(game_id=game.id).join(Player).all()
    is_host = game.host_player_id == player.id
    
    # Get invite link if exists
    invite = GameInvite.query.filter_by(game_id=game.id).first()
    invite_link = url_for('join_by_invite', invite_code=invite.invite_code, _external=True) if invite else None
    
    return render_template('waiting_room.html', 
                         game=game, 
                         players=players, 
                         is_host=is_host, 
                         player=player, 
                         invite_link=invite_link,
                         invite=invite)

@app.route('/kick_player/<int:game_id>/<int:player_id>')
def kick_player(game_id, player_id):
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    game = Game.query.get_or_404(game_id)
    if game.host_player_id != player.id:
        return "Only host can kick players", 403
    
    if game.status != 'waiting':
        return "Cannot kick players after game started", 400
    
    # Remove player from game
    game_player = GamePlayer.query.filter_by(game_id=game_id, player_id=player_id).first()
    if game_player:
        db.session.delete(game_player)
        
        # Update game activity
        game.update_activity()
    
    return redirect(url_for('game_room', game_id=game_id))

@app.route('/forfeit_game/<int:game_id>')
def forfeit_game(game_id):
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    game = Game.query.get_or_404(game_id)
    game_player = GamePlayer.query.filter_by(game_id=game_id, player_id=player.id).first()
    
    if not game_player:
        return "You are not in this game", 403
    
    if game.status == 'active' and game_player.status == 'playing':
        # Mark as forfeited and add loss
        game_player.status = 'forfeited'
        player.total_losses += 1
        db.session.commit()
        
        # Check if game should be completed
        check_game_completion(game_id)
    
    return redirect(url_for('lobby'))

@app.route('/start_game/<int:game_id>')
def start_game(game_id):
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    game = Game.query.get_or_404(game_id)
    if game.host_player_id != player.id:
        return "Only host can start the game", 403
    
    if game.status != 'waiting':
        return "Game already started", 400
    
    # Start the game
    game.status = 'active'
    game.started_at = datetime.utcnow()
    
    # Update all players to playing status
    GamePlayer.query.filter_by(game_id=game_id).update({'status': 'playing'})
    
    # Expire invite links
    GameInvite.query.filter_by(game_id=game_id).update({'expires_at': datetime.utcnow()})
    
    # Update game activity
    game.update_activity()
    
    db.session.commit()
    
    return redirect(url_for('game_room', game_id=game_id))

def render_game_play(game, player, game_player, spectate_mode=False):
    # Skip status checks if in spectate mode
    if not spectate_mode:
        # Check for 5-minute timeout
        if game_player.last_guess_time:
            time_since_last = datetime.utcnow() - game_player.last_guess_time
            if time_since_last.total_seconds() > 300:  # 5 minutes
                game_player.status = 'forfeited'
                # Add loss for timeout forfeit
                player.total_losses += 1
                db.session.commit()
        
        if game_player.status == 'forfeited':
            return render_template_string('''
            {% extends "base.html" %}
            {% block content %}
            <div class="container">
                <div class="card text-center animate-fade-in">
                    <div class="text-6xl mb-4">⏰</div>
                    <h1>Game Forfeited</h1>
                    <p class="text-text-secondary mb-6">You took too long to make a guess (5+ minutes)</p>
                    <div class="flex gap-4 justify-center">
                        <a href="{{ url_for('game_room', game_id=game.id) }}?spectate=true" class="btn btn-secondary">👀 Watch Game</a>
                        <a href="{{ url_for('lobby') }}" class="btn btn-primary">Back to Lobby</a>
                    </div>
                </div>
            </div>
            {% endblock %}
            ''', game=game)
        
        if game_player.status == 'solved':
            # Check if this player won (was first to solve)
            is_winner = game.winner_id == player.id
            winner_text = "🏆 You Won!" if is_winner else "✅ Solved!"
            description = "You were the first to crack the pattern!" if is_winner else "You solved the pattern!"
            
            return render_template_string('''
            {% extends "base.html" %}
            {% block content %}
            <div class="container">
                <div class="card text-center animate-fade-in">
                    <div class="text-6xl mb-4">🎉</div>
                    <h1>{{ winner_text }}</h1>
                    <p class="text-xl text-text-secondary mb-4">{{ description }}</p>
                    <div class="text-3xl font-bold text-success mb-6">{{ game_player.guess_count }} guesses</div>
                    <p class="text-text-secondary mb-6">Other players can continue guessing until they solve it or forfeit</p>
                    <div class="flex gap-4 justify-center">
                        <a href="{{ url_for('view_guesses', game_id=game.id) }}" class="btn btn-secondary">View Guesses</a>
                        <a href="{{ url_for('game_room', game_id=game.id) }}?spectate=true" class="btn btn-secondary">👀 Watch Game</a>
                        <a href="{{ url_for('lobby') }}" class="btn btn-primary">Back to Lobby</a>
                    </div>
                </div>
            </div>
            {% endblock %}
            ''', game=game, game_player=game_player, winner_text=winner_text, description=description)
    
    # Get player's guesses
    guesses = Guess.query.filter_by(game_id=game.id, player_id=player.id).order_by(Guess.guess_number).all()
    
    # Calculate remaining time
    if game_player.last_guess_time:
        time_since_last = datetime.utcnow() - game_player.last_guess_time
        remaining_seconds = max(0, 300 - int(time_since_last.total_seconds()))
    else:
        remaining_seconds = 300  # Full 5 minutes for first guess
    
    remaining_time = f"{remaining_seconds // 60}:{remaining_seconds % 60:02d}"
    active_players = GamePlayer.query.filter_by(game_id=game.id, status='playing').count()
    
    return render_template('game.html', 
                         game=game, 
                         game_player=game_player, 
                         guesses=guesses,
                         remaining_time=remaining_time,
                         remaining_seconds=remaining_seconds,
                         active_players=active_players,
                         spectate_mode=spectate_mode)

@app.route('/make_guess/<int:game_id>', methods=['POST'])
def make_guess(game_id):
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    game = Game.query.get_or_404(game_id)
    game_player = GamePlayer.query.filter_by(game_id=game_id, player_id=player.id).first()
    
    if not game_player or game_player.status != 'playing':
        return "Cannot make guess", 403
    
    # Build guess pattern
    guess_colors = []
    for i in range(5):
        color = request.form.get(f'color_{i}')
        if not color:
            return "All 5 colors must be selected", 400
        guess_colors.append(color)
    
    guess_pattern = ','.join(guess_colors)
    
    # Evaluate guess
    correct_positions, correct_colors = evaluate_guess(game.secret_pattern, guess_pattern)
    
    # Save guess
    game_player.guess_count += 1
    game_player.last_guess_time = datetime.utcnow()
    
    guess = Guess(
        game_id=game_id,
        player_id=player.id,
        guess_pattern=guess_pattern,
        correct_positions=correct_positions,
        correct_colors=correct_colors,
        guess_number=game_player.guess_count
    )
    db.session.add(guess)
    
    # Check if solved
    if correct_positions == 5:
        game_player.status = 'solved'
        game_player.finish_time = datetime.utcnow()
        
        # Check if this is the first to solve (winner)
        if not game.winner_id:
            game.winner_id = player.id
    
    # Update game activity
    game.update_activity()
    
    db.session.commit()
    
    # Check if game is complete
    check_game_completion(game_id)
    
    return redirect(url_for('game_room', game_id=game_id))

def check_game_completion(game_id):
    """Check if all players are done and complete the game"""
    game = Game.query.get(game_id)
    if game.status != 'active':
        return
    
    # Get all players in the game
    all_players = GamePlayer.query.filter_by(game_id=game_id).all()
    
    # Check each player's status and handle timeouts
    players_still_playing = 0
    
    for gp in all_players:
        if gp.status == 'playing':
            # Check if this player has timed out
            if gp.last_guess_time:
                time_since = datetime.utcnow() - gp.last_guess_time
                if time_since.total_seconds() > 300:  # 5+ minutes - timeout
                    gp.status = 'forfeited'
                    player = Player.query.get(gp.player_id)
                    player.total_losses += 1
                else:
                    # Player is still actively playing
                    players_still_playing += 1
            else:
                # First guess - player is still playing
                players_still_playing += 1
    
    # Game is complete only when NO players are still actively playing
    if players_still_playing == 0:
        game.status = 'completed'
        game.completed_at = datetime.utcnow()
        
        # Award stats: winner gets a win, forfeited players already got losses
        if game.winner_id:
            winner = Player.query.get(game.winner_id)
            winner.total_wins += 1
            
            # Note: Players who solved but didn't win first don't get losses
            # Players who forfeited already got losses when they forfeited
        
        db.session.commit()

def render_game_results(game, player):
    players = GamePlayer.query.filter_by(game_id=game.id).join(Player).all()
    
    return render_template('results.html', game=game, players=players, player=player)

@app.route('/view_guesses/<int:game_id>')
def view_guesses(game_id):
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    guesses = Guess.query.filter_by(game_id=game_id, player_id=player.id).order_by(Guess.guess_number).all()
    
    return render_template_string('''
    <h1>Your Guesses for Game #{{ game_id }}</h1>
    <table border="1">
        <tr><th>#</th><th>Guess</th><th>Correct Position</th><th>Correct Color</th><th>Time</th></tr>
        {% for guess in guesses %}
        <tr>
            <td>{{ guess.guess_number }}</td>
            <td>{{ guess.guess_pattern.replace(',', ' - ') }}</td>
            <td>{{ guess.correct_positions }}</td>
            <td>{{ guess.correct_colors }}</td>
            <td>{{ guess.timestamp.strftime('%H:%M:%S') }}</td>
        </tr>
        {% endfor %}
    </table>
    <a href="{{ url_for('game_room', game_id=game_id) }}">Back to Game</a>
    ''', guesses=guesses, game_id=game_id)

if __name__ == '__main__':
    # Check if SECRET_KEY is set
    if not app.config['SECRET_KEY']:
        print("Error: SECRET_KEY environment variable not set!")
        print("Please check your .env file")
        exit(1)
    
    # Create database tables
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")
    
    app.run(debug=True, host='0.0.0.0', port=5000) 