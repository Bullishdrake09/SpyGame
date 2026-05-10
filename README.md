# Spy Game - Social Deduction Game

A complete responsive web app for the social deduction game "Spy" (Imposter). Players are assigned roles as either civilians (who know a secret location) or spies (who must blend in and guess the location).

## Recent Updates (v2.0)
- **Turn-Based System**: Strict turn order implemented. Player 1 describes first, then Player 2, etc. Only the active player can type and send messages.
- **Enhanced Voting**: After all players describe, vote to either continue with another round OR accuse someone immediately.
- **Chat Fixed**: Socket events properly namespaced; messages now broadcast correctly to game rooms.
- **Modern UI Overhaul**: Dark theme with purple/teal gradients, animated turn indicators, styled message bubbles, and professional card designs.
- **Visual Feedback**: Turn indicator banner shows whose turn it is, input disabled when not your turn, Pass Turn button visible only for active player.

## Features

- **Real-time multiplayer** using Socket.IO
- **Turn-based discussion** - players describe in order
- **Dual voting system** - continue describing or accuse
- **Responsive mobile-first design** with touch-friendly UI
- **No login required** - join with short game codes (5 characters)
- **Complete game flow**: lobby → role reveal → turn-based discussion → voting → results
- **Localization support** (English, Spanish, French)
- **Host management** with automatic transfer on disconnect
- **Configurable timer** (default 5 minutes)
- **Ephemeral rooms** stored in memory

## Project Structure

```
/workspace
├── server/
│   ├── index.js          # Node.js/Socket.IO server with turn logic
│   └── package.json      # Dependencies
├── public/
│   ├── index.html        # Main HTML UI with turn indicator
│   ├── style.css         # Modern responsive CSS with animations
│   ├── script.js         # Client-side JavaScript (turn handling)
│   └── words.json        # Localization dictionary
└── README.md             # This file
```

## Installation & Running

### Prerequisites
- Node.js 14+ installed
- npm or yarn package manager

### Setup

1. Navigate to the server directory:
   ```bash
   cd /workspace/server
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the server:
   ```bash
   npm start
   ```

4. Open your browser to:
   ```
   http://localhost:3000
   ```

### Testing

To test the game:

1. **Start the server** as shown above
2. **Open multiple browser windows/tabs** (or use incognito mode) to `http://localhost:3000`
3. **Create a game** in the first window:
   - Click "Create Game"
   - Enter a player name
   - Note the game code (e.g., ABC12)
4. **Join from other windows**:
   - Click "Join Game"
   - Enter the same game code
   - Enter different player names
5. **Start the game** (host only):
   - Wait for at least 3 players
   - Host clicks "Start Game"
6. **Play through the game**:
   - View your role (spy or civilian)
   - Chat during discussion phase
   - Vote for who you think is the spy
   - See results!

### Simulating Multiple Players

For quick testing, open these URLs in different browsers/incognito tabs:
- Tab 1: Create game → becomes host
- Tab 2-5: Join with code → additional players

## Game Rules

1. **Setup**: 3-12 players join a lobby
2. **Role Assignment**: 
   - 1 player randomly becomes the **Spy**
   - All others are **Civilians**
   - Civilians receive a secret location word
3. **Discussion Phase** (5 minutes):
   - Players chat to identify the spy
   - Spy tries to blend in and figure out the location
   - Any player can call for a vote
4. **Voting**:
   - Everyone votes for who they think is the spy
   - Player with most votes is eliminated
5. **Results**:
   - If spy is voted out → **Civilians win**
   - If civilian is voted out → **Spy wins**

## API Reference

### Server Events (Client → Server)

| Event | Payload | Description |
|-------|---------|-------------|
| `createGame` | `{ playerName: string }` | Create new game lobby |
| `joinGame` | `{ code: string, playerName: string }` | Join existing game |
| `startGame` | `{ code: string }` | Start game (host only) |
| `chatMessage` | `{ code: string, message: string }` | Send chat message |
| `callVote` | `{ code: string }` | Initiate voting |
| `vote` | `{ code: string, targetId: string }` | Submit vote |
| `spyGuess` | `{ code: string, guess: string }` | Spy guesses location |

### Client Events (Server → Client)

| Event | Payload | Description |
|-------|---------|-------------|
| `gameCreated` | Game data | Game created successfully |
| `gameJoined` | Game data | Joined game successfully |
| `playerJoined` | Player info | New player joined |
| `playerLeft` | Player info | Player left game |
| `hostChanged` | `{ hostId: string }` | New host assigned |
| `roleAssigned` | `{ role, word? }` | Private role assignment |
| `timerStarted` | Timer data | Discussion timer started |
| `timerUpdate` | `{ remaining: number }` | Timer countdown update |
| `chatMessage` | Message data | New chat message |
| `votingStarted` | Players list | Voting phase began |
| `voteResult` | Vote tally | Voting results |
| `gameEnd` | Game results | Game finished |
| `error` | `{ message: string }` | Error occurred |

## Data Structures

### Game Object (server-side)

```javascript
{
  code: 'ABC12',           // Game code
  players: [               // Array of players
    { id: 'socketId', name: 'PlayerName' }
  ],
  hostId: 'socketId',      // Current host's socket ID
  word: 'Beach',           // Secret location
  spyIds: ['socketId'],    // Array of spy socket IDs
  gameState: 'lobby',      // lobby, reveal, discussion, voting, results
  timer: 300,              // Seconds remaining
  timerInterval: null,     // setInterval reference
  votes: {},               // { voterId: targetId }
  started: false           // Whether game has started
}
```

## Configuration

Edit `GAME_CONFIG` in `server/index.js`:

```javascript
const GAME_CONFIG = {
  CODE_LENGTH: 5,          // Game code length
  DEFAULT_TIMER: 300,      // Discussion time (seconds)
  MIN_PLAYERS: 3,          // Minimum players to start
  MAX_PLAYERS: 12,         // Maximum players per game
  SPY_COUNT: 1             // Number of spies
};
```

## Customization

### Adding Languages

Add new language to `public/words.json`:

```json
{
  "de": {
    "gameTitle": "Spion Spiel",
    "createGame": "Spiel erstellen",
    // ... more translations
  }
}
```

### Adding Locations

Edit the `words` array in `server/index.js` (assignRoles function):

```javascript
const words = [
  'Beach', 'Hospital', 'Space Station',
  // Add your custom locations here
];
```

## Deployment

### Environment Variables

- `PORT`: Server port (default: 3000)

### Production Build

1. Set NODE_ENV to production:
   ```bash
   NODE_ENV=production npm start
   ```

2. For Heroku, create a Procfile:
   ```
   web: node server/index.js
   ```

3. For Docker, create a Dockerfile:
   ```dockerfile
   FROM node:18-alpine
   WORKDIR /app
   COPY server/package*.json ./
   RUN npm install --production
   COPY . .
   EXPOSE 3000
   CMD ["node", "server/index.js"]
   ```

### Scaling with Redis

For production with multiple server instances, replace in-memory storage with Redis:

```javascript
// Replace games object with Redis client
const redis = require('redis');
const client = redis.createClient();

// Store/retrieve games using Redis commands
await client.set(`game:${code}`, JSON.stringify(gameData));
const game = JSON.parse(await client.get(`game:${code}`));
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Accessibility

- Reduced motion support (`prefers-reduced-motion`)
- High contrast mode support (`prefers-contrast`)
- Keyboard navigation
- Touch-friendly large buttons
- Screen reader compatible

## License

MIT License - Feel free to use and modify for your projects!

## Troubleshooting

**Server won't start:**
- Ensure port 3000 is not in use
- Check Node.js version (14+)
- Run `npm install` again

**Can't connect multiple players:**
- Make sure all browsers access the same URL
- Check firewall settings
- Try incognito/private browsing mode

**Game code not working:**
- Codes are case-insensitive
- Ensure code is entered correctly (no spaces)
- Game may have already started or been deleted

**Chat not working:**
- Ensure game is in discussion phase
- Check browser console for errors
- Verify WebSocket connection is active
