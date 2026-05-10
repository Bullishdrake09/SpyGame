/**
 * Spy Game Server - Node.js with Express and Socket.IO
 * Handles game lobbies, role assignment, chat, voting, and game flow
 */

const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = new Server(server);

// Serve static files from public directory
app.use(express.static(path.join(__dirname, '../public')));

// In-memory game storage (use Redis for production scaling)
const games = {};

// Configuration
const GAME_CONFIG = {
  CODE_LENGTH: 5,
  DEFAULT_TIMER: 300, // 5 minutes in seconds
  MIN_PLAYERS: 3,
  MAX_PLAYERS: 12,
  SPY_COUNT: 1
};

// Generate random game code
function generateCode() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // No I, O, 0, 1 to avoid confusion
  let code = '';
  for (let i = 0; i < GAME_CONFIG.CODE_LENGTH; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return code;
}

// Get or create game room
function getOrCreateGame(code) {
  if (!games[code]) {
    games[code] = {
      code,
      players: [],
      hostId: null,
      word: null,
      spyIds: [],
      gameState: 'lobby', // lobby, reveal, discussion, voting, results
      timer: GAME_CONFIG.DEFAULT_TIMER,
      timerInterval: null,
      votes: {},
      started: false
    };
  }
  return games[code];
}

// Find player by socket ID
function findPlayer(game, socketId) {
  return game.players.find(p => p.id === socketId);
}

// Assign roles randomly
function assignRoles(game) {
  const playerIds = game.players.map(p => p.id);
  // Shuffle array
  for (let i = playerIds.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [playerIds[i], playerIds[j]] = [playerIds[j], playerIds[i]];
  }
  
  // Assign spy(s)
  game.spyIds = playerIds.slice(0, GAME_CONFIG.SPY_COUNT);
  
  // Select random word from word list
  const words = [
    'Beach', 'Hospital', 'Space Station', 'School', 'Restaurant',
    'Airplane', 'Cruise Ship', 'Zoo', 'Bank', 'Library',
    'Casino', 'Theater', 'Gym', 'Supermarket', 'Police Station',
    'Fire Station', 'Museum', 'Farm', 'Construction Site', 'Laboratory'
  ];
  game.word = words[Math.floor(Math.random() * words.length)];
}

// Start vote countdown timer
function startTimer(game, duration) {
  if (game.timerInterval) {
    clearInterval(game.timerInterval);
  }
  
  game.timer = duration;
  game.gameState = 'discussion';
  
  // Emit timer start to all players
  io.to(game.code).emit('timerStarted', { 
    duration, 
    remaining: game.timer 
  });
  
  game.timerInterval = setInterval(() => {
    game.timer--;
    
    // Emit timer update every second
    io.to(game.code).emit('timerUpdate', { remaining: game.timer });
    
    if (game.timer <= 0) {
      clearInterval(game.timerInterval);
      // Auto-start voting when timer ends
      startVoting(game);
    }
  }, 1000);
}

// Stop timer
function stopTimer(game) {
  if (game.timerInterval) {
    clearInterval(game.timerInterval);
    game.timerInterval = null;
  }
}

// Start voting phase
function startVoting(game) {
  stopTimer(game);
  game.gameState = 'voting';
  game.votes = {};
  
  io.to(game.code).emit('votingStarted', {
    players: game.players.map(p => ({ id: p.id, name: p.name }))
  });
}

// Tally votes and determine result
function tallyVotes(game) {
  const voteCounts = {};
  
  // Count votes
  Object.values(game.votes).forEach(vote => {
    if (vote) {
      voteCounts[vote] = (voteCounts[vote] || 0) + 1;
    }
  });
  
  // Find highest voted player(s)
  let maxVotes = 0;
  let candidates = [];
  
  Object.entries(voteCounts).forEach(([playerId, count]) => {
    if (count > maxVotes) {
      maxVotes = count;
      candidates = [playerId];
    } else if (count === maxVotes) {
      candidates.push(playerId);
    }
  });
  
  // Handle tie or no votes
  if (candidates.length === 0 || maxVotes === 0) {
    return { winner: null, isTie: false, noVotes: true };
  }
  
  if (candidates.length > 1) {
    // Random selection in case of tie
    const winner = candidates[Math.floor(Math.random() * candidates.length)];
    return { winner, isTie: true, noVotes: false };
  }
  
  return { winner: candidates[0], isTie: false, noVotes: false };
}

// End game with result
function endGame(game, result) {
  stopTimer(game);
  game.gameState = 'results';
  
  const spyRevealed = game.spyIds.map(id => {
    const player = findPlayer(game, id);
    return { id, name: player ? player.name : 'Unknown' };
  });
  
  io.to(game.code).emit('gameEnd', {
    ...result,
    word: game.word,
    spies: spyRevealed,
    allPlayers: game.players.map(p => ({
      id: p.id,
      name: p.name,
      isSpy: game.spyIds.includes(p.id)
    }))
  });
}

// Transfer host to another player
function transferHost(game) {
  if (!game.hostId || !findPlayer(game, game.hostId)) {
    // Find first available player
    if (game.players.length > 0) {
      game.hostId = game.players[0].id;
      io.to(game.code).emit('hostChanged', { hostId: game.hostId });
    }
  }
}

// Socket.IO connection handling
io.on('connection', (socket) => {
  console.log(`Player connected: ${socket.id}`);
  
  // Create new game
  socket.on('createGame', (data) => {
    const { playerName } = data;
    let code;
    let game;
    
    // Generate unique code
    do {
      code = generateCode();
      game = getOrCreateGame(code);
    } while (game.players.length > 0);
    
    // Add player as host
    const player = { id: socket.id, name: playerName || `Player${Math.floor(Math.random()*1000)}` };
    game.players.push(player);
    game.hostId = socket.id;
    
    socket.join(code);
    
    socket.emit('gameCreated', {
      code,
      playerId: socket.id,
      isHost: true,
      players: game.players
    });
    
    console.log(`Game created: ${code} by ${player.name}`);
  });
  
  // Join existing game
  socket.on('joinGame', (data) => {
    const { code, playerName } = data;
    const game = games[code.toUpperCase()];
    
    if (!game) {
      socket.emit('error', { message: 'Game not found' });
      return;
    }
    
    if (game.started) {
      socket.emit('error', { message: 'Game already started' });
      return;
    }
    
    if (game.players.length >= GAME_CONFIG.MAX_PLAYERS) {
      socket.emit('error', { message: 'Game is full' });
      return;
    }
    
    const player = { 
      id: socket.id, 
      name: playerName || `Player${Math.floor(Math.random()*1000)}` 
    };
    game.players.push(player);
    
    socket.join(code);
    
    // Notify all players
    io.to(code).emit('playerJoined', {
      player,
      players: game.players,
      isHost: game.hostId === socket.id
    });
    
    socket.emit('gameJoined', {
      code: code.toUpperCase(),
      playerId: socket.id,
      isHost: game.hostId === socket.id,
      players: game.players
    });
    
    console.log(`${player.name} joined game ${code}`);
  });
  
  // Start game (host only)
  socket.on('startGame', (data) => {
    const { code } = data;
    const game = games[code];
    
    if (!game) return;
    if (game.hostId !== socket.id) {
      socket.emit('error', { message: 'Only host can start game' });
      return;
    }
    
    if (game.players.length < GAME_CONFIG.MIN_PLAYERS) {
      socket.emit('error', { message: `Need at least ${GAME_CONFIG.MIN_PLAYERS} players` });
      return;
    }
    
    // Assign roles
    assignRoles(game);
    game.started = true;
    
    // Send role to each player privately
    game.players.forEach(player => {
      const isSpy = game.spyIds.includes(player.id);
      io.to(player.id).emit('roleAssigned', {
        role: isSpy ? 'spy' : 'civilian',
        word: isSpy ? null : game.word
      });
    });
    
    game.gameState = 'reveal';
    
    // Notify all players game started
    io.to(code).emit('gameStarted', {
      playerCount: game.players.length,
      spyCount: GAME_CONFIG.SPY_COUNT
    });
    
    console.log(`Game ${code} started with ${game.players.length} players`);
  });
  
  // Chat message
  socket.on('chatMessage', (data) => {
    const { code, message } = data;
    const game = games[code];
    
    if (!game || game.gameState !== 'discussion') return;
    
    const player = findPlayer(game, socket.id);
    if (!player) return;
    
    io.to(code).emit('chatMessage', {
      playerId: socket.id,
      playerName: player.name,
      message,
      timestamp: Date.now()
    });
  });
  
  // Call vote
  socket.on('callVote', (data) => {
    const { code } = data;
    const game = games[code];
    
    if (!game || game.gameState !== 'discussion') return;
    
    startVoting(game);
  });
  
  // Submit vote
  socket.on('vote', (data) => {
    const { code, targetId } = data;
    const game = games[code];
    
    if (!game || game.gameState !== 'voting') return;
    
    game.votes[socket.id] = targetId;
    
    // Check if all players have voted
    const hasVoted = Object.keys(game.votes).length;
    if (hasVoted >= game.players.length) {
      // All votes in, tally immediately
      setTimeout(() => {
        const result = tallyVotes(game);
        
        if (result.noVotes) {
          // No votes cast, restart discussion
          io.to(code).emit('voteResult', {
            result: 'no_votes',
            message: 'No votes were cast. Discussion continues.'
          });
          startTimer(game, 60); // 1 minute additional discussion
        } else {
          // Determine win/loss
          const spyWasVotedOut = result.winner && game.spyIds.includes(result.winner);
          
          if (spyWasVotedOut) {
            endGame(game, {
              result: 'civilians_win',
              votedOut: findPlayer(game, result.winner)?.name,
              message: result.isTie ? 'Tie broken randomly - Spy caught!' : 'Spy identified!'
            });
          } else {
            // Spy wins or gets final guess opportunity
            endGame(game, {
              result: 'spy_win',
              votedOut: findPlayer(game, result.winner)?.name,
              message: result.isTie ? 'Tie broken randomly - Spy survives!' : 'Wrong suspect! Spy wins!'
            });
          }
        }
      }, 1000);
    }
  });
  
  // Spy guess (optional feature)
  socket.on('spyGuess', (data) => {
    const { code, guess } = data;
    const game = games[code];
    
    if (!game || !game.spyIds.includes(socket.id)) return;
    
    const isCorrect = guess.toLowerCase() === game.word.toLowerCase();
    
    io.to(code).emit('spyGuessResult', {
      guess,
      isCorrect,
      correctWord: game.word
    });
    
    if (isCorrect) {
      endGame(game, {
        result: 'spy_win_guess',
        message: 'Spy correctly guessed the location!'
      });
    }
  });
  
  // Disconnect handling
  socket.on('disconnect', () => {
    console.log(`Player disconnected: ${socket.id}`);
    
    // Find and remove player from all games
    Object.values(games).forEach(game => {
      const playerIndex = game.players.findIndex(p => p.id === socket.id);
      
      if (playerIndex !== -1) {
        const player = game.players[playerIndex];
        game.players.splice(playerIndex, 1);
        
        // Remove their vote if exists
        delete game.votes[socket.id];
        
        io.to(game.code).emit('playerLeft', {
          playerId: socket.id,
          playerName: player.name,
          players: game.players
        });
        
        // Transfer host if needed
        if (game.hostId === socket.id) {
          transferHost(game);
        }
        
        // Clean up empty games
        if (game.players.length === 0) {
          stopTimer(game);
          delete games[game.code];
          console.log(`Game ${game.code} deleted (empty)`);
        }
      }
    });
  });
});

// Start server
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Spy Game server running on port ${PORT}`);
  console.log(`Open http://localhost:${PORT} in your browser`);
});

module.exports = { app, server, io, games };
