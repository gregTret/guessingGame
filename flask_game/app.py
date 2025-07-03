from flask import Flask, session, request, redirect, url_for, jsonify, render_template_string, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room
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

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

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
        
        # Check if there's a stored redirect URL
        next_url = session.pop('next_url', None)
        if next_url:
            return redirect(next_url)
        
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
        # Store the current URL to return here after name entry
        session['next_url'] = request.url
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
        # Store the current URL to return here after name entry
        session['next_url'] = request.url
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
        game_player = GamePlayer(game_id=game.id, player_id=player.id, status='waiting')
        db.session.add(game_player)
        
        # Create invite code
        invite = GameInvite(
            game_id=game.id,
            invite_code=GameInvite.generate_invite_code()
        )
        db.session.add(invite)
        db.session.commit()
        
        # Broadcast lobby update
        broadcast_lobby_update()
        
        return redirect(url_for('game_room', game_id=game.id))
    
    return render_template('create_game.html')

@app.route('/join/<invite_code>')
def join_by_invite(invite_code):
    player = get_current_player()
    if not player:
        # Store the current URL to return here after name entry
        session['next_url'] = request.url
        return redirect(url_for('enter_name'))
    
    invite = GameInvite.query.filter_by(invite_code=invite_code).first()
    if not invite or invite.expires_at:
        return redirect(url_for('lobby'))
    
    return redirect(url_for('join_game', game_id=invite.game_id))

@app.route('/join_game/<int:game_id>')
def join_game(game_id):
    player = get_current_player()
    if not player:
        # Store the current URL to return here after name entry
        session['next_url'] = request.url
        return redirect(url_for('enter_name'))
    
    game = Game.query.get_or_404(game_id)
    
    # Check if game is still waiting
    if game.status != 'waiting':
        return redirect(url_for('lobby'))
    
    # Check if player already in game
    existing = GamePlayer.query.filter_by(game_id=game_id, player_id=player.id).first()
    if existing:
        return redirect(url_for('game_room', game_id=game_id))
    
    # Check if game is full
    current_players = GamePlayer.query.filter_by(game_id=game_id).count()
    if current_players >= game.max_players:
        return redirect(url_for('lobby'))
    
    # Add player to game
    game_player = GamePlayer(game_id=game_id, player_id=player.id)
    db.session.add(game_player)
    
    # Update game activity
    game.update_activity()
    
    # Broadcast lobby update and room update
    broadcast_lobby_update()
    socketio.emit('player_list_updated', {
        'players': [{
            'id': gp.player.id,
            'name': gp.player.name,
            'total_wins': gp.player.total_wins,
            'total_losses': gp.player.total_losses,
            'is_host': gp.player.id == game.host_player_id
        } for gp in GamePlayer.query.filter_by(game_id=game_id).join(Player).all()],
        'player_count': GamePlayer.query.filter_by(game_id=game_id).count(),
        'max_players': game.max_players
    }, room=f"game_{game_id}")
    
    return redirect(url_for('game_room', game_id=game_id))

@app.route('/game/<int:game_id>')
def game_room(game_id):
    player = get_current_player()
    if not player:
        # Store the current URL to return here after name entry
        session['next_url'] = request.url
        return redirect(url_for('enter_name'))
    
    game = Game.query.get_or_404(game_id)
    game_player = GamePlayer.query.filter_by(game_id=game_id, player_id=player.id).first()
    
    if not game_player:
        return redirect(url_for('lobby'))
    
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
        return redirect(url_for('lobby'))
    
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
    
    # Broadcast lobby update (game no longer in waiting list)
    broadcast_lobby_update()
    
    return redirect(url_for('game_room', game_id=game_id))

def render_game_play(game, player, game_player, spectate_mode=False):
    # Skip status checks if in spectate mode
    if not spectate_mode:
        # Check for 5-minute timeout (only for players who have made at least one guess)
        if game_player.last_guess_time and game_player.status == 'playing':
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
            # If game is completed, redirect to results  
            if game.status == 'completed':
                return render_game_results(game, player)
            
            # For hosts who finish but game isn't complete yet, show different options
            is_host = game.host_player_id == player.id
            
            return render_template_string('''
            {% extends "base.html" %}
            {% block content %}
            <div class="container">
                <div class="card text-center animate-fade-in">
                    <div class="text-6xl mb-4">🎉</div>
                    <h1>✅ Solved!</h1>
                    <p class="text-xl text-text-secondary mb-4">You cracked the pattern!</p>
                    <div class="text-3xl font-bold text-success mb-6">{{ game_player.guess_count }} guesses</div>
                    <p class="text-text-secondary mb-6">Other players can continue guessing until they solve it or forfeit</p>
                    <div class="flex gap-4 justify-center">
                        <a href="{{ url_for('view_guesses', game_id=game.id) }}" class="btn btn-secondary">View Guesses</a>
                        {% if is_host %}
                        <button onclick="if(confirm('End game for all players?')) window.location.href='{{ url_for('lobby') }}'" class="btn btn-warning">🏁 End Game</button>
                        {% else %}
                        <a href="{{ url_for('game_room', game_id=game.id) }}?spectate=true" class="btn btn-secondary">👀 Watch Game</a>
                        {% endif %}
                        <a href="{{ url_for('lobby') }}" class="btn btn-primary">Back to Lobby</a>
                    </div>
                </div>
            </div>
            {% endblock %}
            ''', game=game, game_player=game_player, is_host=is_host)
    
    # Get player's guesses
    guesses = Guess.query.filter_by(game_id=game.id, player_id=player.id).order_by(Guess.guess_number.desc()).all()
    
    # Calculate remaining time
    if game_player.last_guess_time:
        time_since_last = datetime.utcnow() - game_player.last_guess_time
        remaining_seconds = max(0, 300 - int(time_since_last.total_seconds()))
    else:
        remaining_seconds = 300  # Full 5 minutes for first guess
    
    remaining_time = f"{remaining_seconds // 60}:{remaining_seconds % 60:02d}"
    active_players = GamePlayer.query.filter_by(game_id=game.id).filter(GamePlayer.status.in_(['playing', 'waiting'])).count()
    
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
    
    if not game_player or game_player.status not in ['playing', 'waiting']:
        return "Cannot make guess", 403
    
    # Auto-transition from waiting to playing on first guess
    if game_player.status == 'waiting':
        game_player.status = 'playing'
    
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
    
    # Update game activity
    game.update_activity()
    
    db.session.commit()
    
    # Check if game is complete
    check_game_completion(game_id)
    
    # If player just solved and game is now completed, go directly to results
    game = Game.query.get(game_id)  # Refresh game state
    if correct_positions == 5 and game.status == 'completed':
        return redirect(url_for('game_room', game_id=game_id))  # This will show results since game is completed
    
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
        if gp.status in ['playing', 'waiting']:
            # Check if this player has timed out (only applies to players who have made a guess)
            if gp.last_guess_time and gp.status == 'playing':
                time_since = datetime.utcnow() - gp.last_guess_time
                if time_since.total_seconds() > 300:  # 5+ minutes - timeout
                    gp.status = 'forfeited'
                    player = Player.query.get(gp.player_id)
                    player.total_losses += 1
                else:
                    # Player is still actively playing
                    players_still_playing += 1
            else:
                # Player hasn't made a guess yet or is waiting - still playing
                players_still_playing += 1
    
            # Game is complete only when NO players are still actively playing
        if players_still_playing == 0:
            game.status = 'completed'
            game.completed_at = datetime.utcnow()
            
            # Determine winner: player who solved with fewest guesses
            solved_players = [gp for gp in all_players if gp.status == 'solved']
            if solved_players:
                # Find player with minimum guess count among those who solved
                winner_gp = min(solved_players, key=lambda gp: gp.guess_count)
                game.winner_id = winner_gp.player_id
                
                # Award win to the winner
                winner = Player.query.get(winner_gp.player_id)
                winner.total_wins += 1
                
                # Note: Players who forfeited already got losses when they forfeited
                # Players who solved but didn't win don't get losses
            
            db.session.commit()
            
            # Notify all players in the game that it has completed
            socketio.emit('game_completed', {
                'game_id': game_id,
                'winner_name': winner.name if solved_players else None
            }, room=f"game_{game_id}")

def render_game_results(game, player):
    players = GamePlayer.query.filter_by(game_id=game.id).join(Player).all()
    
    return render_template('results.html', game=game, players=players, player=player)

@app.route('/view_guesses/<int:game_id>')
def view_guesses(game_id):
    player = get_current_player()
    if not player:
        return redirect(url_for('enter_name'))
    
    guesses = Guess.query.filter_by(game_id=game_id, player_id=player.id).order_by(Guess.guess_number.desc()).all()
    
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

# SocketIO Events

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_waiting_room')
def handle_join_waiting_room(data):
    game_id = data.get('game_id')
    if not game_id:
        return
    
    room = f"game_{game_id}"
    join_room(room)
    
    # Get current game state
    game = Game.query.get(game_id)
    if game:
        players = GamePlayer.query.filter_by(game_id=game_id).join(Player).all()
        
        # Broadcast updated player list to room
        emit('player_list_updated', {
            'players': [{
                'id': gp.player.id,
                'name': gp.player.name,
                'total_wins': gp.player.total_wins,
                'total_losses': gp.player.total_losses,
                'is_host': gp.player.id == game.host_player_id
            } for gp in players],
            'player_count': len(players),
            'max_players': game.max_players
        }, room=room)

@socketio.on('leave_waiting_room')
def handle_leave_waiting_room(data):
    game_id = data.get('game_id')
    if game_id:
        leave_room(f"game_{game_id}")

@socketio.on('start_game_socket')
def handle_start_game_socket(data):
    game_id = data.get('game_id')
    player_name = session.get('player_name')
    
    if not game_id or not player_name:
        return
    
    player = get_current_player()
    if not player:
        return
    
    game = Game.query.get(game_id)
    if not game or game.host_player_id != player.id:
        return
    
    # Start the game
    game.status = 'active'
    game.started_at = datetime.utcnow()
    game.update_activity()
    db.session.commit()
    
    # Notify all players in waiting room
    emit('game_started', {
        'game_id': game_id
    }, room=f"game_{game_id}")

@socketio.on('join_game_room')
def handle_join_game_room(data):
    game_id = data.get('game_id')
    if not game_id:
        return
    
    room = f"game_{game_id}"
    join_room(room)
    
    # Send current game state to joining player
    game = Game.query.get(game_id)
    if game and game.status == 'active':
        active_players = GamePlayer.query.filter_by(game_id=game_id).filter(GamePlayer.status.in_(['playing', 'waiting'])).all()
        
        emit('game_state_updated', {
            'active_players': len(active_players),
            'game_status': game.status
        })

@socketio.on('guess_submitted_socket')
def handle_guess_submitted_socket(data):
    game_id = data.get('game_id')
    player_name = session.get('player_name')
    
    if not game_id or not player_name:
        return
    
    # Broadcast to all players in the game that someone made a guess
    active_players = GamePlayer.query.filter_by(game_id=game_id).filter(GamePlayer.status.in_(['playing', 'waiting'])).count()
    
    emit('player_made_guess', {
        'player_name': player_name,
        'active_players': active_players
    }, room=f"game_{game_id}")

@socketio.on('join_lobby')
def handle_join_lobby():
    join_room('lobby')
    
    # Send current lobby stats
    public_games = Game.query.filter_by(status='waiting', invite_only=False).all()
    total_players = GamePlayer.query.join(Game).filter(Game.status == 'waiting').count()
    
    emit('lobby_updated', {
        'public_games_count': len(public_games),
        'total_players': total_players
    })

def broadcast_lobby_update():
    """Broadcast lobby updates to all connected lobby clients"""
    public_games = Game.query.filter_by(status='waiting', invite_only=False).all()
    total_players = GamePlayer.query.join(Game).filter(Game.status == 'waiting').count()
    
    socketio.emit('lobby_updated', {
        'public_games_count': len(public_games),
        'total_players': total_players
    }, room='lobby')

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
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True) 