from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, join_room, emit, disconnect
import random
import string
from datetime import datetime
import ast
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here_change_in_production'
app.config['SESSION_TYPE'] = 'filesystem'  # Use filesystem sessions
socketio = SocketIO(app, async_mode='threading', manage_session=True, cors_allowed_origins="*")

# Global storage for lobbies
lobbies = {}

# List to store word pairs, loaded from words.txt
word_pairs = []

def load_word_pairs(filename="words.txt"):
    """Loads word pairs from a text file with robust error handling."""
    loaded_pairs = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        evaluated_item = ast.literal_eval(line)
                        
                        if isinstance(evaluated_item, tuple) and len(evaluated_item) == 2 and \
                           isinstance(evaluated_item[0], str) and isinstance(evaluated_item[1], str):
                            loaded_pairs.append(evaluated_item)
                        elif isinstance(evaluated_item, tuple) and len(evaluated_item) == 1 and \
                             isinstance(evaluated_item[0], tuple) and len(evaluated_item[0]) == 2:
                            loaded_pairs.append(evaluated_item[0])
                        else:
                            logger.warning(f"Skipping malformed line {line_num} in {filename}")
                    except (ValueError, SyntaxError) as e:
                        logger.error(f"Error parsing line {line_num} in {filename}: {e}")
    except FileNotFoundError:
        logger.error(f"{filename} not found. Using fallback word pairs.")
        # Fallback word pairs
        loaded_pairs = [
            ('cat', 'dog'), ('apple', 'banana'), ('car', 'truck'),
            ('coffee', 'tea'), ('book', 'magazine'), ('ocean', 'sea')
        ]
    return loaded_pairs

# Load word pairs when the application starts
word_pairs = load_word_pairs()
if not word_pairs:
    logger.critical("No word pairs loaded. Game will not function correctly.")
else:
    logger.info(f"Loaded {len(word_pairs)} word pairs successfully")

def generate_lobby_code(length=4):
    """Generate a unique lobby code."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        if code not in lobbies:
            return code

def clean_lobby_state(lobby_code):
    """Clean up disconnected players and validate lobby state."""
    if lobby_code not in lobbies:
        return False
    
    lobby = lobbies[lobby_code]
    valid_nicknames = {player['nickname'] for player in lobby['players'].values()}
    
    # Clean up assignments, descriptions, and votes for disconnected players
    lobby['assignments'] = {k: v for k, v in lobby['assignments'].items() if k in valid_nicknames}
    lobby['descriptions'] = {k: v for k, v in lobby['descriptions'].items() if k in valid_nicknames}
    lobby['votes'] = {k: v for k, v in lobby['votes'].items() if k in valid_nicknames}
    
    # Update description order to remove disconnected players
    lobby['description_order'] = [nick for nick in lobby['description_order'] if nick in valid_nicknames]
    
    return True

# -----------------------
# ROUTES
# -----------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create', methods=['POST'])
def create():
    nickname = request.form.get('nickname', '').strip()
    if not nickname or len(nickname) > 20:
        return redirect(url_for('index'))
    
    lobby_code = generate_lobby_code()
    lobbies[lobby_code] = {
        'host': nickname,
        'players': {},
        'state': 'lobby',
        'current_word_pair': None,
        'assignments': {},
        'descriptions': {},
        'votes': {},
        'settings': {
            'show_role': False,
            'dead_vote': False,
            'animations': True,
            'sound': True
        },
        'description_order': [],
        'current_descr_index': 0
    }
    session['nickname'] = nickname
    session['lobby'] = lobby_code
    session['role'] = 'host'
    session.modified = True
    return redirect(url_for('lobby', code=lobby_code))

@app.route('/join', methods=['POST'])
def join():
    nickname = request.form.get('nickname', '').strip()
    lobby_code = request.form.get('lobby_code', '').upper().strip()
    
    if not nickname or len(nickname) > 20:
        return "Invalid nickname", 400
    if lobby_code not in lobbies:
        return "Lobby not found", 404
    
    # Check if nickname is already taken
    existing_nicknames = {p['nickname'] for p in lobbies[lobby_code]['players'].values()}
    if nickname in existing_nicknames or nickname == lobbies[lobby_code]['host']:
        return "Nickname already taken", 400
    
    session['nickname'] = nickname
    session['lobby'] = lobby_code
    session['role'] = 'player'
    session.modified = True
    return redirect(url_for('lobby', code=lobby_code))

@app.route('/lobby/<code>')
def lobby(code):
    if code not in lobbies:
        return "Lobby not found", 404
    is_host = (session.get('role') == 'host')
    return render_template('lobby.html', lobby_code=code, is_host=is_host, nickname=session.get('nickname'))

@app.route('/link/<code>')
def share_link(code):
    if code not in lobbies:
        return "Lobby not found", 404
    return render_template('share_link.html', code=code)

@app.route('/game')
def game():
    lobby_code = session.get('lobby')
    if not lobby_code or lobby_code not in lobbies:
        return render_template('game_not_found.html')
    nickname = session.get('nickname')
    is_host = (session.get('role') == 'host')
    return render_template('game.html', lobby_code=lobby_code, nickname=nickname, is_host=is_host)

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# -----------------------
# SOCKET.IO EVENTS
# -----------------------

@socketio.on('send_chat')
def handle_send_chat(data):
    lobby_code = session.get('lobby')
    nickname = session.get('nickname')
    message = data.get('message', '').strip()

    if not lobby_code or not nickname or not message or len(message) > 500:
        return

    emit('receive_chat', {
        'message': message,
        'nickname': nickname,
        'timestamp': datetime.now().strftime("%H:%M")
    }, room=lobby_code)

@socketio.on('join_lobby')
def handle_join_lobby():
    lobby_code = session.get('lobby')
    nickname = session.get('nickname')
    sid = request.sid
    
    if not lobby_code or not nickname or lobby_code not in lobbies:
        emit('error', {'message': 'Invalid lobby or nickname'}, room=sid)
        return
    
    try:
        join_room(lobby_code)
        lobbies[lobby_code]['players'][sid] = {
            'nickname': nickname,
            'alive': True,
            'points': 0
        }
        
        players_list = [
            {
                'nickname': player['nickname'],
                'sid': s,
                'points': player.get('points', 0),
                'alive': player.get('alive', True)
            }
            for s, player in lobbies[lobby_code]['players'].items()
        ]
        emit('update_players', {'players': players_list}, room=lobby_code)
        emit('settings_updated', {'settings': lobbies[lobby_code]['settings']}, room=sid)
        
        # If rejoining during game, send assignment
        if lobbies[lobby_code]['state'] in ['game', 'waiting_for_next_round'] and \
           nickname in lobbies[lobby_code]['assignments']:
            assignment = lobbies[lobby_code]['assignments'][nickname]
            emit('word_assignment', assignment, room=sid)
            
    except Exception as e:
        logger.error(f"Error in join_lobby: {e}")
        emit('error', {'message': 'Failed to join lobby'}, room=sid)

@socketio.on('disconnect')
def handle_disconnect():
    lobby_code = session.get('lobby')
    if lobby_code and lobby_code in lobbies:
        sid = request.sid
        if sid in lobbies[lobby_code]['players']:
            nickname = lobbies[lobby_code]['players'][sid]['nickname']
            logger.info(f"Player {nickname} disconnected from lobby {lobby_code}")
            
            del lobbies[lobby_code]['players'][sid]
            clean_lobby_state(lobby_code)
            
            # If no players left, clean up lobby
            if not lobbies[lobby_code]['players']:
                logger.info(f"Lobby {lobby_code} is empty, cleaning up")
                del lobbies[lobby_code]
            else:
                players_list = [
                    {
                        'nickname': player['nickname'],
                        'sid': s,
                        'points': player.get('points', 0),
                        'alive': player.get('alive', True)
                    }
                    for s, player in lobbies[lobby_code]['players'].items()
                ]
                emit('update_players', {'players': players_list}, room=lobby_code)

@socketio.on('kick_player')
def handle_kick_player(data):
    lobby_code = session.get('lobby')
    if session.get('role') != 'host':
        emit('error', {'message': 'Only host can kick players.'}, room=request.sid)
        return
    
    target_sid = data.get('sid')
    lobby = lobbies.get(lobby_code)
    if not lobby or target_sid not in lobby['players']:
        return
    
    try:
        target_nick = lobby['players'][target_sid]['nickname']
        del lobby['players'][target_sid]
        clean_lobby_state(lobby_code)
        
        emit('kicked', {'message': 'You have been kicked from the lobby.'}, room=target_sid)
        
        players_list = [
            {
                'nickname': player['nickname'],
                'sid': s,
                'points': player.get('points', 0),
                'alive': player.get('alive', True)
            }
            for s, player in lobby['players'].items()
        ]
        emit('update_players', {'players': players_list}, room=lobby_code)
    except Exception as e:
        logger.error(f"Error kicking player: {e}")

@socketio.on('start_game')
def handle_start_game():
    lobby_code = session.get('lobby')
    if lobby_code not in lobbies or session.get('role') != 'host':
        return
    
    lobby = lobbies[lobby_code]
    players = list(lobby['players'].keys())
    
    if len(players) < 3:
        emit('error', {'message': 'Need at least 3 players to start the game.'}, room=request.sid)
        return
    
    if not word_pairs:
        emit('error', {'message': 'Word list is empty. Cannot start game.'}, room=request.sid)
        return

    try:
        lobby['state'] = 'game'
        pair = random.choice(word_pairs)
        lobby['current_word_pair'] = pair
        logger.info(f"Game started in lobby {lobby_code} with word pair: {pair}")
        
        spy_sid = random.choice(players)
        spy_nickname = lobby['players'][spy_sid]['nickname']
        
        lobby['assignments'] = {}
        for sid, player in lobby['players'].items():
            nick = player['nickname']
            player['alive'] = True  # Reset alive status
            if nick == spy_nickname:
                lobby['assignments'][nick] = {'word': pair[1], 'role': 'spy'}
            else:
                lobby['assignments'][nick] = {'word': pair[0], 'role': 'normal'}
        
        for sid, player in lobby['players'].items():
            nick = player['nickname']
            emit('word_assignment', lobby['assignments'][nick], room=sid)
        
        alive_players = [player['nickname'] for player in lobby['players'].values() if player['alive']]
        random.shuffle(alive_players)
        lobby['description_order'] = alive_players
        lobby['current_descr_index'] = 0
        lobby['descriptions'] = {}
        lobby['votes'] = {}
        
        emit('next_describer', {'describer': alive_players[0]}, room=lobby_code)
        emit('game_started', {'message': 'Game has started!'}, room=lobby_code)
        
        players_list = [
            {
                'nickname': p['nickname'],
                'sid': s,
                'points': p.get('points', 0),
                'alive': p['alive']
            }
            for s, p in lobby['players'].items()
        ]
        emit('update_players', {'players': players_list}, room=lobby_code)
        
    except Exception as e:
        logger.error(f"Error starting game: {e}")
        emit('error', {'message': 'Failed to start game'}, room=request.sid)

@socketio.on('submit_description')
def handle_submit_description(data):
    lobby_code = session.get('lobby')
    nickname = session.get('nickname')
    description = data.get('description', '').strip()
    
    lobby = lobbies.get(lobby_code)
    if not lobby or lobby['state'] != 'game' or not description or len(description) > 500:
        return
    
    # Validate it's this player's turn
    if not lobby['description_order'] or \
       lobby['current_descr_index'] >= len(lobby['description_order']) or \
       lobby['description_order'][lobby['current_descr_index']] != nickname:
        return
    
    try:
        lobby['descriptions'][nickname] = description
        emit('description_submitted', {
            'nickname': nickname,
            'description': description
        }, room=lobby_code)
        
        lobby['current_descr_index'] += 1
        
        if lobby['current_descr_index'] < len(lobby['description_order']):
            next_describer = lobby['description_order'][lobby['current_descr_index']]
            emit('next_describer', {'describer': next_describer}, room=lobby_code)
        else:
            # All descriptions submitted, move to voting
            descriptions_list = [
                {'nickname': nick, 'description': desc}
                for nick, desc in lobby['descriptions'].items()
            ]
            random.shuffle(descriptions_list)
            
            votable_players_list = [
                {'nickname': player['nickname']}
                for player in lobby['players'].values()
                if player['alive']
            ]
            random.shuffle(votable_players_list)
            
            emit('all_descriptions', {
                'descriptions': descriptions_list,
                'votable_players': votable_players_list
            }, room=lobby_code)
            
    except Exception as e:
        logger.error(f"Error submitting description: {e}")

@socketio.on('submit_vote')
def handle_submit_vote(data):
    lobby_code = session.get('lobby')
    nickname = session.get('nickname')
    vote_target = data.get('vote')
    
    lobby = lobbies.get(lobby_code)
    if not lobby or lobby['state'] != 'game' or not vote_target:
        return
    
    try:
        lobby['votes'][nickname] = vote_target
        
        # Auto-vote for dead players if setting enabled
        if lobby['settings'].get('dead_vote'):
            for p in lobby['players'].values():
                if not p['alive'] and p['nickname'] not in lobby['votes']:
                    lobby['votes'][p['nickname']] = "none"
        
        # Calculate required votes
        if lobby['settings'].get('dead_vote'):
            required_votes = len(lobby['players'])
        else:
            required_votes = sum(1 for p in lobby['players'].values() if p['alive'])
        
        if len(lobby['votes']) < required_votes:
            return
        
        # All votes submitted, process results
        vote_count = {}
        for voter, target in lobby['votes'].items():
            vote_count[target] = vote_count.get(target, 0) + 1
        
        max_votes = max(vote_count.values())
        candidates = [name for name, count in vote_count.items() if count == max_votes]
        eliminated_name = random.choice(candidates)
        eliminated_role = lobby['assignments'][eliminated_name]['role']
        
        actual_spy_nickname = next(
            (nick for nick, assign in lobby['assignments'].items() if assign['role'] == 'spy'),
            'Unknown'
        )
        
        emit('player_eliminated', {
            'nickname': eliminated_name,
            'role': eliminated_role
        }, room=lobby_code)
        
        # Update eliminated player's status
        for sid, player in lobby['players'].items():
            if player['nickname'] == eliminated_name:
                player['alive'] = False
                break
        
        alive_assignments = [
            lobby['assignments'][player['nickname']]
            for player in lobby['players'].values()
            if player['alive']
        ]
        spies = sum(1 for assign in alive_assignments if assign['role'] == 'spy')
        normals = sum(1 for assign in alive_assignments if assign['role'] == 'normal')
        pair = lobby['current_word_pair']
        
        outcome_data = {
            'eliminated_name': eliminated_name,
            'eliminated_role': eliminated_role,
            'spy_word': pair[1],
            'normal_word': pair[0],
            'actual_spy_nickname': actual_spy_nickname
        }
        
        if eliminated_role == 'spy':
            # Normal team wins
            for player in lobby['players'].values():
                nick = player['nickname']
                if lobby['assignments'].get(nick, {}).get('role') == 'normal':
                    player['points'] = player.get('points', 0) + 3
            emit('round_over', outcome_data, room=lobby_code)
            lobby['state'] = 'waiting_for_next_round'
            
        elif spies >= normals:
            # Spy wins
            for player in lobby['players'].values():
                nick = player['nickname']
                if lobby['assignments'].get(nick, {}).get('role') == 'spy':
                    player['points'] = player.get('points', 0) + len(lobby['players'])
            emit('round_over', outcome_data, room=lobby_code)
            lobby['state'] = 'waiting_for_next_round'
            
        else:
            # Game continues
            alive_players_nicks = [
                player['nickname']
                for player in lobby['players'].values()
                if player['alive']
            ]
            
            if len(alive_players_nicks) < 2:
                # Not enough players to continue
                emit('round_over', outcome_data, room=lobby_code)
                lobby['state'] = 'waiting_for_next_round'
            else:
                random.shuffle(alive_players_nicks)
                lobby['description_order'] = alive_players_nicks
                lobby['current_descr_index'] = 0
                lobby['descriptions'] = {}
                lobby['votes'] = {}
                
                emit('vote_failed', outcome_data, room=lobby_code)
                emit('next_describer', {'describer': alive_players_nicks[0]}, room=lobby_code)
        
        players_list = [
            {
                'nickname': p['nickname'],
                'sid': s,
                'points': p.get('points', 0),
                'alive': p['alive']
            }
            for s, p in lobby['players'].items()
        ]
        emit('update_players', {'players': players_list}, room=lobby_code)
        
    except Exception as e:
        logger.error(f"Error processing vote: {e}")

@socketio.on('next_round')
def handle_next_round():
    lobby_code = session.get('lobby')
    if not lobby_code or lobby_code not in lobbies or session.get('role') != 'host':
        return
    
    lobby = lobbies[lobby_code]
    
    if lobby.get('state') != 'waiting_for_next_round':
        return
    
    if not word_pairs:
        emit('error', {'message': 'Word list is empty.'}, room=request.sid)
        return
    
    try:
        # Reset all players
        for player in lobby['players'].values():
            player['alive'] = True
        
        lobby['descriptions'] = {}
        lobby['votes'] = {}
        lobby['assignments'] = {}
        
        pair = random.choice(word_pairs)
        lobby['current_word_pair'] = pair
        logger.info(f"Next round started with word pair: {pair}")
        
        players_sids = list(lobby['players'].keys())
        if not players_sids:
            emit('error', {'message': 'No players left.'}, room=request.sid)
            lobby['state'] = 'lobby'
            return
        
        spy_sid = random.choice(players_sids)
        spy_nickname = lobby['players'][spy_sid]['nickname']
        
        for sid, player in lobby['players'].items():
            nick = player['nickname']
            if nick == spy_nickname:
                lobby['assignments'][nick] = {'word': pair[1], 'role': 'spy'}
            else:
                lobby['assignments'][nick] = {'word': pair[0], 'role': 'normal'}
            emit('word_assignment', lobby['assignments'][nick], room=sid)
        
        alive_players = [player['nickname'] for player in lobby['players'].values()]
        random.shuffle(alive_players)
        lobby['description_order'] = alive_players
        lobby['current_descr_index'] = 0
        lobby['state'] = 'game'
        
        emit('game_started', {'message': 'New round has started!'}, room=lobby_code)
        emit('next_describer', {'describer': alive_players[0]}, room=lobby_code)
        
        players_list = [
            {
                'nickname': player['nickname'],
                'sid': s,
                'points': player.get('points', 0),
                'alive': player.get('alive', True)
            }
            for s, player in lobby['players'].items()
        ]
        emit('update_players', {'players': players_list}, room=lobby_code)
        
    except Exception as e:
        logger.error(f"Error starting next round: {e}")
        emit('error', {'message': 'Failed to start next round'}, room=request.sid)

@socketio.on('update_settings')
def handle_update_settings(data):
    lobby_code = session.get('lobby')
    if not lobby_code or lobby_code not in lobbies or session.get('role') != 'host':
        return
    
    lobby = lobbies[lobby_code]
    for key, value in data.items():
        if key in lobby['settings'] and isinstance(value, bool):
            lobby['settings'][key] = value
    
    emit('settings_updated', {'settings': lobby['settings']}, room=lobby_code)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
