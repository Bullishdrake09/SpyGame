from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, join_room, emit, disconnect
import random
import string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app, async_mode='threading')

# Global storage for lobbies.
# Each lobby holds:
#   - 'host': host nickname
#   - 'players': {socket_id: {'nickname': ..., 'alive': True, 'points': int}}
#   - 'state': 'lobby', 'game', 'waiting_for_next_round', or 'ended'
#   - 'current_word_pair': chosen word pair (tuple)
#   - 'assignments': {nickname: {'word': ..., 'role': 'spy' or 'normal'}}
#   - 'descriptions': {nickname: description}
#   - 'votes': {nickname: voted_nickname}
#   - 'settings': { 'show_role': bool, 'dead_vote': bool, 'animations': bool, 'sound': bool }
#   - 'description_order': list of nicknames in order for describing
#   - 'current_descr_index': index in description_order for whose turn it is
lobbies = {}

# Hardcoded word pairs (first word for normal players, second for spy).
word_pairs = [# Same-Category Pairs (160 lines):

# Vehicles (15)
('motorcycle', 'bicycle'),
('bus', 'tram'),
('taxi', 'van'),
('truck', 'pickup'),
('helicopter', 'jet'),
('scooter', 'minivan'),
('boat', 'ferry'),
('submarine', 'sailboat'),
('convertible', 'coupe'),
('roadster', 'limousine'),
('SUV', 'tractor'),
('blimp', 'airship'),
('dune buggy', 'racer'),
('segway', 'go-kart'),
('rickshaw', 'tricycle'),

# Beverages (15)
('espresso', 'cappuccino'),
('latte', 'mocha'),
('smoothie', 'milkshake'),
('lemonade', 'iced tea'),
('beer', 'wine'),
('soda', 'juice'),
('water', 'sparkling water'),
('cocktail', 'margarita'),
('whiskey', 'vodka'),
('iced coffee', 'affogato'),
('frappuccino', 'macchiato'),
('hot chocolate', 'chai'),
('kombucha', 'ginger beer'),
('cider', 'mead'),
('matcha', 'oolong'),

# Fruits (15)
('banana', 'apple'),
('mango', 'papaya'),
('strawberry', 'blueberry'),
('pear', 'peach'),
('grape', 'cherry'),
('watermelon', 'cantaloupe'),
('kiwi', 'lime'),
('pineapple', 'coconut'),
('apricot', 'plum'),
('raspberry', 'blackberry'),
('pomegranate', 'cranberry'),
('mandarin', 'tangerine'),
('fig', 'date'),
('guava', 'lychee'),
('dragonfruit', 'passionfruit'),

# Colors (15)
('red', 'blue'),
('green', 'yellow'),
('purple', 'pink'),
('black', 'white'),
('brown', 'beige'),
('gray', 'silver'),
('violet', 'indigo'),
('magenta', 'cyan'),
('turquoise', 'teal'),
('maroon', 'burgundy'),
('olive', 'lime'),
('navy', 'sky blue'),
('scarlet', 'crimson'),
('amber', 'gold'),
('emerald', 'jade'),

# Animals (15)
('cat', 'dog'),
('lion', 'tiger'),
('elephant', 'rhinoceros'),
('giraffe', 'zebra'),
('bear', 'wolf'),
('fox', 'coyote'),
('rabbit', 'squirrel'),
('horse', 'donkey'),
('monkey', 'ape'),
('panda', 'koala'),
('kangaroo', 'wallaby'),
('dolphin', 'whale'),
('shark', 'stingray'),
('penguin', 'seal'),
('crocodile', 'alligator'),

# Countries (10)
('USA', 'Canada'),
('UK', 'France'),
('Germany', 'Italy'),
('Spain', 'Portugal'),
('China', 'Japan'),
('Brazil', 'Argentina'),
('India', 'Pakistan'),
('Russia', 'Ukraine'),
('Australia', 'New Zealand'),
('Egypt', 'South Africa'),

# Sports (10)
('soccer', 'basketball'),
('tennis', 'badminton'),
('baseball', 'football'),
('cricket', 'rugby'),
('golf', 'cycling'),
('hockey', 'volleyball'),
('swimming', 'diving'),
('boxing', 'wrestling'),
('skiing', 'snowboarding'),
('skating', 'rollerblading'),

# Musical Instruments (10)
('guitar', 'bass'),
('piano', 'organ'),
('drums', 'cymbals'),
('violin', 'cello'),
('flute', 'clarinet'),
('saxophone', 'trumpet'),
('harp', 'mandolin'),
('banjo', 'ukulele'),
('harmonica', 'accordion'),
('synthesizer', 'keyboard'),

# Clothing (10)
('shirt', 'pants'),
('jacket', 'coat'),
('dress', 'skirt'),
('hat', 'scarf'),
('gloves', 'socks'),
('shoes', 'boots'),
('tie', 'belt'),
('sweater', 'hoodie'),
('shorts', 'leggings'),
('suit', 'blazer'),

# Professions (10)
('doctor', 'nurse'),
('teacher', 'professor'),
('engineer', 'architect'),
('lawyer', 'judge'),
('chef', 'baker'),
('pilot', 'flight attendant'),
('artist', 'designer'),
('writer', 'poet'),
('musician', 'composer'),
('scientist', 'researcher'),

# Technology (10)
('computer', 'laptop'),
('smartphone', 'tablet'),
('printer', 'scanner'),
('router', 'modem'),
('keyboard', 'mouse'),
('monitor', 'television'),
('camera', 'drone'),
('headphones', 'speaker'),
('smartwatch', 'fitness tracker'),
('microphone', 'amplifier'),

# Flowers (10)
('rose', 'lily'),
('daisy', 'tulip'),
('orchid', 'sunflower'),
('daffodil', 'marigold'),
('violet', 'peony'),
('carnation', 'gerbera'),
('hyacinth', 'iris'),
('poppy', 'anemone'),
('zinnia', 'cosmos'),
('chrysanthemum', 'freesia'),

# Trees (10)
('oak', 'maple'),
('pine', 'cedar'),
('birch', 'spruce'),
('willow', 'poplar'),
('sequoia', 'redwood'),
('cherry', 'apple tree'),
('ash', 'elm'),
('fir', 'larch'),
('sycamore', 'baobab'),
('cypress', 'magnolia'),

# Foods (5)
('bread', 'butter'),
('cheese', 'yogurt'),
('pasta', 'rice'),
('soup', 'salad'),
('steak', 'egg'),

# Completely Mismatching Pairs (20 lines):
('cat', 'laptop'),
('apple', 'hammer'),
('soccer', 'piano'),
('tree', 'phone'),
('shirt', 'giraffe'),
('river', 'clock'),
('coffee', 'engineer'),
('sunflower', 'airplane'),
('ocean', 'keyboard'),
('mountain', 'burger'),
('rain', 'suitcase'),
('ice', 'violin'),
('candle', 'soccer'),
('jacket', 'rocket'),
('island', 'toothbrush'),
('desert', 'microphone'),
('butterfly', 'printer'),
('coffee', 'telescope'),
('lizard', 'sandwich'),
('bicycle', 'novel'),

# Not-So-Close Related Pairs (20 lines):
('coffee', 'morning'),
('book', 'lamp'),
('rain', 'window'),
('music', 'memory'),
('shadow', 'time'),
('smile', 'sunset'),
('fire', 'desire'),
('ocean', 'echo'),
('forest', 'whisper'),
('mountain', 'silence'),
('river', 'journey'),
('storm', 'canvas'),
('breeze', 'secret'),
('mirror', 'dream'),
('desert', 'mystery'),
('clock', 'memory'),
('flame', 'passion'),
('window', 'perspective'),
('pen', 'thought'),
('silence', 'harmony'),
]

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

@app.route('/game')
def game():
    lobby_code = session.get('lobby')
    if not lobby_code or lobby_code not in lobbies:
        return render_template('game_not_found.html')
    return render_template('game.html', lobby_code=lobby_code, 
                           nickname=session.get('nickname'), 
                           is_host=(session.get('role')=='host'))

# Custom 404 error page.
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# -----------------------
# SOCKET.IO EVENTS
# -----------------------

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
    players_list = [{'nickname': player['nickname'], 'sid': s, 'points': player.get('points', 0)}
                    for s, player in lobbies[lobby_code]['players'].items()]
    emit('update_players', {'players': players_list}, room=lobby_code)
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
            players_list = [{'nickname': player['nickname'], 'sid': s, 'points': player.get('points', 0)}
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
        players_list = [{'nickname': player['nickname'], 'sid': s, 'points': player.get('points', 0)}
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
    if lobby['description_order'][lobby['current_descr_index']] != nickname:
        return  # Ignore submissions out of turn.
    lobby['descriptions'][nickname] = description
    emit('description_submitted', {'nickname': nickname, 'description': description}, room=lobby_code)
    lobby['current_descr_index'] += 1
    if lobby['current_descr_index'] < len(lobby['description_order']):
        next_describer = lobby['description_order'][lobby['current_descr_index']]
        emit('next_describer', {'describer': next_describer}, room=lobby_code)
    else:
        descriptions_list = [{'nickname': nick, 'description': desc} for nick, desc in lobby['descriptions'].items()]
        random.shuffle(descriptions_list)
        emit('all_descriptions', {'descriptions': descriptions_list}, room=lobby_code)

@socketio.on('submit_vote')
def handle_submit_vote(data):
    lobby_code = session.get('lobby')
    nickname = session.get('nickname')
    vote_target = data.get('vote')
    lobby = lobbies.get(lobby_code)
    if not lobby or lobby['state'] != 'game':
        return
    lobby['votes'][nickname] = vote_target
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
        for sid, player in lobby['players'].items():
            if player['nickname'] == eliminated_name:
                lobby['players'][sid]['alive'] = False
                break
        eliminated_role = lobby['assignments'][eliminated_name]['role']
        emit('player_eliminated', {'nickname': eliminated_name, 'role': eliminated_role}, room=lobby_code)
        
        alive_assignments = [lobby['assignments'][player['nickname']]
                             for sid, player in lobby['players'].items() if player['alive']]
        spies = sum(1 for assign in alive_assignments if assign['role'] == 'spy')
        normals = sum(1 for assign in alive_assignments if assign['role'] == 'normal')
        pair = lobby['current_word_pair']
        
        # Points system: if the spy is discovered, normal players get 3 points;
        # if the spy wins, the spy gets 1 point per player.
        if eliminated_role == 'spy':
            for sid, player in lobby['players'].items():
                nick = player['nickname']
                if lobby['assignments'].get(nick, {}).get('role') == 'normal':
                    player['points'] = player.get('points', 0) + 3
            outcome_message = (f"{eliminated_name} was the spy! Round over: Normal team wins. "
                               f"Spy word was '{pair[1]}' and Normal word was '{pair[0]}'. "
                               "Press Next Round to continue.")
            emit('round_over', {'message': outcome_message}, room=lobby_code)
            lobby['state'] = 'waiting_for_next_round'
        elif spies >= normals:
            for sid, player in lobby['players'].items():
                nick = player['nickname']
                if lobby['assignments'].get(nick, {}).get('role') == 'spy':
                    player['points'] = player.get('points', 0) + len(lobby['players'])
            outcome_message = (f"{eliminated_name} was not the spy! Round over: Spy wins. "
                               f"Spy word was '{pair[1]}' and Normal word was '{pair[0]}'. "
                               "Press Next Round to continue.")
            emit('round_over', {'message': outcome_message}, room=lobby_code)
            lobby['state'] = 'waiting_for_next_round'
        else:
            outcome_message = f"{eliminated_name} was not the spy. Continue the round."
            emit('vote_failed', {'message': outcome_message}, room=lobby_code)
            lobby['descriptions'] = {}
            lobby['votes'] = {}

@socketio.on('next_round')
def handle_next_round():
    lobby_code = session.get('lobby')
    if not lobby_code or lobby_code not in lobbies:
         return
    if session.get('role') != 'host':
         return
    lobby = lobbies[lobby_code]
    if lobby.get('state') != 'waiting_for_next_round':
         return
    for sid, player in lobby['players'].items():
         player['alive'] = True
    lobby['descriptions'] = {}
    lobby['votes'] = {}
    alive_players = [player['nickname'] for sid, player in lobby['players'].items()]
    random.shuffle(word_pairs)
    pair = word_pairs[0]
    lobby['current_word_pair'] = pair
    new_spy_nick = random.choice(alive_players)
    for sid, player in lobby['players'].items():
         nick = player['nickname']
         if nick == new_spy_nick:
              lobby['assignments'][nick] = {'word': pair[1], 'role': 'spy'}
         else:
              lobby['assignments'][nick] = {'word': pair[0], 'role': 'normal'}
    lobby['state'] = 'game'
    for sid, player in lobby['players'].items():
         nick = player['nickname']
         emit('word_assignment', lobby['assignments'][nick], room=sid)
    alive_players = [player['nickname'] for sid, player in lobby['players'].items() if player['alive']]
    random.shuffle(alive_players)
    lobby['description_order'] = alive_players
    lobby['current_descr_index'] = 0
    emit('next_describer', {'describer': alive_players[0]}, room=lobby_code)
    emit('new_round', {'message': 'New round started with new assignments.'}, room=lobby_code)
    players_list = [{'nickname': player['nickname'], 'sid': s, 'points': player.get('points', 0)}
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
    for key in ['show_role', 'dead_vote', 'animations', 'sound']:
         if key in data:
              lobby['settings'][key] = data[key]
    emit('settings_updated', {'settings': lobby['settings']}, room=lobby_code)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=False, allow_unsafe_werkzeug=True)

