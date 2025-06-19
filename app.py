from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, join_room, emit, disconnect
import random
import string
from datetime import datetime
import ast # To safely evaluate string literals as Python tuples

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app, async_mode='threading')

# Global storage for lobbies.
# Each lobby holds:
#   - 'host': host nickname
#   - 'players': {socket_id: {'nickname': ..., 'alive': True, 'points': int}}
#   - 'state': 'lobby', 'game', 'waiting_for_next_round', or 'ended'
#   - 'current_word_pair': chosen word pair (tuple)
#   - 'assignments': {nickname: {'word': ..., 'role': 'spy' or 'normal'}}
#   - 'descriptions': {nickname: description}
#   - 'votes': {nickname: voted_nickname}
#   - 'settings': { 'show_role': bool, 'dead_vote': bool, 'animations': bool, 'sound': bool }
#   - 'description_order': list of nicknames in order for describing
#   - 'current_descr_index': index in description_order for whose turn it is
lobbies = {}

# List to store word pairs, loaded from words.txt
word_pairs = []

def load_word_pairs(filename="words.txt"):
    """Loads word pairs from a text file, ignoring comments and empty lines.
    Handles lines with or without a trailing comma after the tuple."""
    loaded_pairs = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comment lines
                if line and not line.startswith('#'):
                    try:
                        # Safely evaluate the string as a Python literal
                        evaluated_item = ast.literal_eval(line)
                        
                        # Case 1: Directly parsed as a (str, str) tuple, e.g., "('word1', 'word2')"
                        if isinstance(evaluated_item, tuple) and len(evaluated_item) == 2 and \
                           isinstance(evaluated_item[0], str) and isinstance(evaluated_item[1], str):
                            loaded_pairs.append(evaluated_item)
                        
                        # Case 2: Parsed as a single-element tuple containing the (str, str) tuple,
                        # due to a trailing comma in the file, e.g., "('word1', 'word2'),"
                        elif isinstance(evaluated_item, tuple) and len(evaluated_item) == 1 and \
                             isinstance(evaluated_item[0], tuple) and len(evaluated_item[0]) == 2 and \
                             isinstance(evaluated_item[0][0], str) and isinstance(evaluated_item[0][1], str):
                            loaded_pairs.append(evaluated_item[0])
                        else:
                            print(f"Warning: Skipping malformed or unexpected format in {filename}: {line}")
                    except (ValueError, SyntaxError) as e:
                        print(f"Error parsing line in {filename}: {line} - {e}")
    except FileNotFoundError:
        print(f"Error: {filename} not found. Please create it with word pairs.")
    return loaded_pairs

# Load word pairs when the application starts
word_pairs = load_word_pairs()
if not word_pairs:
    print("No word pairs loaded. The game might not function correctly.")


def generate_lobby_code(length=4):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# -----------------------
# ROUTES
# -----------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create', methods=['POST'])
def create():
    nickname = request.form.get('nickname')
    if not nickname:
        return redirect(url_for('index'))
    lobby_code = generate_lobby_code()
    lobbies[lobby_code] = {
        'host': nickname,
        'players': {},            # players will be added with a 'points' key
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
    return redirect(url_for('lobby', code=lobby_code))

@app.route('/join', methods=['POST'])
def join():
    nickname = request.form.get('nickname')
    lobby_code = request.form.get('lobby_code').upper()  # Ensure uppercase.
    if lobby_code not in lobbies:
        return "Lobby not found", 404
    session['nickname'] = nickname
    session['lobby'] = lobby_code
    session['role'] = 'player'
    return redirect(url_for('lobby', code=lobby_code))

@app.route('/lobby/<code>')
def lobby(code):
    if code not in lobbies:
        return "Lobby not found", 404
    is_host = (session.get('role') == 'host')
    return render_template('lobby.html', lobby_code=code, is_host=is_host, nickname=session.get('nickname'))

@app.route('/link/<code>')
def share_link(code):
    # Render the nickname input page
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
    message = data.get('message')

    if not lobby_code or not nickname or not message:
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
    if lobby_code not in lobbies:
        return
    join_room(lobby_code)
    # When adding a new player, set initial points to 0.
    lobbies[lobby_code]['players'][sid] = {'nickname': nickname, 'alive': True, 'points': 0}
    # Include 'alive' status when building players_list
    players_list = [{'nickname': player['nickname'], 'sid': s, 'points': player.get('points', 0), 'alive': player.get('alive', True)}
                    for s, player in lobbies[lobby_code]['players'].items()]
    emit('update_players', {'players': players_list}, room=lobby_code)
    # Also send settings to newly joined player
    emit('settings_updated', {'settings': lobbies[lobby_code]['settings']}, room=sid)
    if lobbies[lobby_code]['state'] in ['game', 'waiting_for_next_round'] and nickname in lobbies[lobby_code]['assignments']:
        assignment = lobbies[lobby_code]['assignments'][nickname]
        emit('word_assignment', assignment, room=sid)

@socketio.on('disconnect')
def handle_disconnect():
    lobby_code = session.get('lobby')
    if lobby_code and lobby_code in lobbies:
        sid = request.sid
        if sid in lobbies[lobby_code]['players']:
            print(f"Disconnecting player: {lobbies[lobby_code]['players'][sid]['nickname']}")
            del lobbies[lobby_code]['players'][sid]
            players_list = [{'nickname': player['nickname'], 'sid': s, 'points': player.get('points', 0), 'alive': player.get('alive', True)}
                            for s, player in lobbies[lobby_code]['players'].items()]
            emit('update_players', {'players': players_list}, room=lobby_code)

@socketio.on('kick_player')
def handle_kick_player(data):
    lobby_code = session.get('lobby')
    if session.get('role') != 'host':
        emit('error', {'message': 'Only host can kick players.'}, room=request.sid)
        return
    target_sid = data.get('sid')
    lobby = lobbies.get(lobby_code)
    if not lobby:
        return
    if target_sid in lobby['players']:
        target_nick = lobby['players'][target_sid]['nickname']
        del lobby['players'][target_sid]
        lobby['assignments'].pop(target_nick, None)
        lobby['descriptions'].pop(target_nick, None)
        lobby['votes'].pop(target_nick, None)
        emit('kicked', {'message': 'You have been kicked from the lobby.'}, room=target_sid)
        players_list = [{'nickname': player['nickname'], 'sid': s, 'points': player.get('points', 0), 'alive': player.get('alive', True)}
                        for s, player in lobby['players'].items()]
        emit('update_players', {'players': players_list}, room=lobby_code)

@socketio.on('start_game')
def handle_start_game():
    lobby_code = session.get('lobby')
    if lobby_code not in lobbies:
        return
    if session.get('role') != 'host':
        return
    lobby = lobbies[lobby_code]
    players = list(lobby['players'].keys())
    if len(players) < 3:
        emit('error', {'message': 'Need at least 3 players to start the game.'}, room=request.sid)
        return
    
    # Ensure word_pairs is loaded and not empty
    if not word_pairs:
        emit('error', {'message': 'Word list is empty. Cannot start game.'}, room=request.sid)
        return

    lobby['state'] = 'game'
    random.shuffle(word_pairs)
    pair = word_pairs[0]
    lobby['current_word_pair'] = pair
    print("Chosen word pair for game start:", pair)
    spy_sid = random.choice(players)
    spy_nickname = lobby['players'][spy_sid]['nickname']
    lobby['assignments'] = {}
    for sid, player in lobby['players'].items():
        nick = player['nickname']
        if nick == spy_nickname:
            lobby['assignments'][nick] = {'word': pair[1], 'role': 'spy'}
        else:
            lobby['assignments'][nick] = {'word': pair[0], 'role': 'normal'}
    for sid, player in lobby['players'].items():
        nick = player['nickname']
        emit('word_assignment', lobby['assignments'][nick], room=sid)
    # Set up turn-based description order.
    alive_players = [player['nickname'] for sid, player in lobby['players'].items() if player['alive']]
    random.shuffle(alive_players)
    lobby['description_order'] = alive_players
    lobby['current_descr_index'] = 0
    lobby['descriptions'] = {}
    emit('next_describer', {'describer': alive_players[0]}, room=lobby_code)
    emit('game_started', {'message': 'Game has started!'}, room=lobby_code)

@socketio.on('submit_description')
def handle_submit_description(data):
    lobby_code = session.get('lobby')
    nickname = session.get('nickname')
    description = data.get('description')
    lobby = lobbies.get(lobby_code)
    if not lobby or lobby['state'] != 'game':
        return
    # Only accept description if it's this player's turn.
    if lobby['description_order'][lobby['current_descr_index']] != nickname:
        return
    lobby['descriptions'][nickname] = description
    emit('description_submitted', {'nickname': nickname, 'description': description}, room=lobby_code)
    lobby['current_descr_index'] += 1
    if lobby['current_descr_index'] < len(lobby['description_order']):
        next_describer = lobby['description_order'][lobby['current_descr_index']]
        emit('next_describer', {'describer': next_describer}, room=lobby_code)
    else:
        descriptions_list = [{'nickname': nick, 'description': desc} for nick, desc in lobby['descriptions'].items()]
        random.shuffle(descriptions_list)
        
        # Prepare votable players list directly on the server
        votable_players_list = []
        for sid, player_data in lobby['players'].items():
            if player_data['alive']:
                votable_players_list.append({'nickname': player_data['nickname']})
        random.shuffle(votable_players_list) # Randomize vote button order
        
        emit('all_descriptions', {'descriptions': descriptions_list, 'votable_players': votable_players_list}, room=lobby_code)

@socketio.on('submit_vote')
def handle_submit_vote(data):
    lobby_code = session.get('lobby')
    nickname = session.get('nickname')
    vote_target = data.get('vote')  # Target player's nickname.
    lobby = lobbies.get(lobby_code)
    if not lobby or lobby['state'] != 'game':
        return
    lobby['votes'][nickname] = vote_target
    # If dead_vote is enabled, force default vote for any dead player that hasn't voted.
    if lobby['settings'].get('dead_vote'):
        for p in lobby['players'].values():
            if not p['alive'] and p['nickname'] not in lobby['votes']:
                lobby['votes'][p['nickname']] = "none"
    if lobby['settings'].get('dead_vote'):
        required_votes = len(lobby['players'])
    else:
        required_votes = sum(1 for p in lobby['players'].values() if p['alive'])
    if len(lobby['votes']) == required_votes:
        vote_count = {}
        for voter, target in lobby['votes'].items():
            vote_count[target] = vote_count.get(target, 0) + 1
        max_votes = max(vote_count.values())
        candidates = [name for name, count in vote_count.items() if count == max_votes]
        eliminated_name = random.choice(candidates)
        
        eliminated_role = lobby['assignments'][eliminated_name]['role']
        
        # Find the actual spy's nickname for the reveal message
        actual_spy_nickname = next((nick for nick, assign in lobby['assignments'].items() if assign['role'] == 'spy'), 'Unknown')
        
        emit('player_eliminated', {'nickname': eliminated_name, 'role': eliminated_role}, room=lobby_code) # Emit this first for animation
        
        alive_assignments = [lobby['assignments'][player['nickname']]
                             for sid, player in lobby['players'].items() if player['alive']]
        spies = sum(1 for assign in alive_assignments if assign['role'] == 'spy')
        normals = sum(1 for assign in alive_assignments if assign['role'] == 'normal')
        pair = lobby['current_word_pair']
        
        # Data to send to client for outcome message
        outcome_data = {
            'eliminated_name': eliminated_name,
            'eliminated_role': eliminated_role,
            'spy_word': pair[1],
            'normal_word': pair[0],
            'actual_spy_nickname': actual_spy_nickname # Always send actual spy for full reveal if game ends
        }

        if eliminated_role == 'spy':
            for sid, player in lobby['players'].items():
                nick = player['nickname']
                if lobby['assignments'].get(nick, {}).get('role') == 'normal':
                    player['points'] = player.get('points', 0) + 3
            emit('round_over', outcome_data, room=lobby_code) # Send structured data
            lobby['state'] = 'waiting_for_next_round'
        elif spies >= normals: # Spy wins
            for sid, player in lobby['players'].items():
                nick = player['nickname']
                if lobby['assignments'].get(nick, {}).get('role') == 'spy':
                    player['points'] = player.get('points', 0) + len(lobby['players'])
            emit('round_over', outcome_data, room=lobby_code) # Send structured data
            lobby['state'] = 'waiting_for_next_round'
        else: # Game continues
            # Update eliminated player's alive status in lobby state
            for sid, player in lobby['players'].items():
                if player['nickname'] == eliminated_name:
                    lobby['players'][sid]['alive'] = False
                    break

            # Reset description phase for all *alive* players.
            alive_players_nicks = [player['nickname'] for sid, player in lobby['players'].items() if player['alive']]
            random.shuffle(alive_players_nicks)
            lobby['description_order'] = alive_players_nicks
            lobby['current_descr_index'] = 0
            lobby['descriptions'] = {} # Clear descriptions for new round phase
            lobby['votes'] = {} # Clear votes for new voting phase

            emit('vote_failed', outcome_data, room=lobby_code) # Send structured data for "Search further!"
            # Only emit next_describer if there are alive players left
            if alive_players_nicks:
                emit('next_describer', {'describer': alive_players_nicks[0]}, room=lobby_code)

        # Always update player list after a vote, to show points/eliminated status
        players_list = [{'nickname': p['nickname'], 'sid': s, 'points': p.get('points', 0), 'alive': p['alive']}
                        for s, p in lobby['players'].items()]
        emit('update_players', {'players': players_list}, room=lobby_code)


@socketio.on('next_round')
def handle_next_round():
    lobby_code = session.get('lobby')
    if not lobby_code or lobby_code not in lobbies:
        return
    if session.get('role') != 'host':
        return
    
    lobby = lobbies[lobby_code]

    # Check if the lobby is in the 'waiting_for_next_round' state before proceeding.
    if lobby.get('state') != 'waiting_for_next_round':
        return
    
    # Ensure word_pairs is loaded and not empty
    if not word_pairs:
        emit('error', {'message': 'Word list is empty. Cannot start next round.'}, room=request.sid)
        return

    # Reset player alive status and game data for the new round
    for sid in lobby['players']:
        lobby['players'][sid]['alive'] = True
    lobby['descriptions'] = {}
    lobby['votes'] = {}
    lobby['assignments'] = {} # Clear previous assignments

    # Choose a new random word pair
    random.shuffle(word_pairs)
    pair = word_pairs[0]
    lobby['current_word_pair'] = pair
    print("Chosen word pair for next round:", pair)

    # Re-assign roles and words to all players
    players_sids = list(lobby['players'].keys())
    if not players_sids:
        emit('error', {'message': 'No players left to start a new round. Returning to lobby.'}, room=request.sid)
        lobby['state'] = 'lobby'
        emit('game_ended_return_to_lobby', {}, room=lobby_code) # Custom event for client to handle
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

    # Set up turn-based description order for the new round
    alive_players = [player['nickname'] for sid, player in lobby['players'].items() if player['alive']]
    random.shuffle(alive_players)
    lobby['description_order'] = alive_players
    lobby['current_descr_index'] = 0

    # Transition lobby state to 'game'
    lobby['state'] = 'game'

    # Notify clients about the new round and initial describer
    emit('game_started', {'message': 'New round has started!'}, room=lobby_code) # Re-use game_started for new round
    # Only emit next_describer if there are alive players left
    if alive_players:
        emit('next_describer', {'describer': alive_players[0]}, room=lobby_code)

    # Update players list to reflect 'alive' status and points
    players_list = [{'nickname': player['nickname'], 'sid': s, 'points': player.get('points', 0), 'alive': player.get('alive', True)}
                    for s, player in lobby['players'].items()]
    emit('update_players', {'players': players_list}, room=lobby_code)


@socketio.on('update_settings')
def handle_update_settings(data):
    lobby_code = session.get('lobby')
    if not lobby_code or lobby_code not in lobbies:
        return
    lobby = lobbies[lobby_code]
    if session.get('role') != 'host':
        return
    # Iterate through the provided data and update only existing settings keys
    for key, value in data.items():
        if key in lobby['settings']: # Ensure only predefined settings can be updated
            lobby['settings'][key] = value
    emit('settings_updated', {'settings': lobby['settings']}, room=lobby_code)

# Removed the handle_request_current_players event as it's no longer needed.
# The votable players list is now sent directly with 'all_descriptions'.

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=False, allow_unsafe_werkzeug=True)
