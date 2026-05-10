/**
 * Spy Game - Client-side JavaScript
 * Handles socket communication, UI updates, and game logic
 */

// Localization dictionary (loaded from words.json)
let i18n = {};
let currentLang = 'en';

// Game state
const state = {
  socket: null,
  playerId: null,
  gameCode: null,
  isHost: false,
  playerName: '',
  role: null,
  word: null,
  players: [],
  gameState: 'menu', // menu, lobby, reveal, discussion, voting, results
  hasVoted: false
};

// DOM Elements cache
const elements = {};

/**
 * Initialize the application
 */
function init() {
  cacheElements();
  loadLocalization();
  setupEventListeners();
  connectSocket();
}

/**
 * Cache DOM elements for performance
 */
function cacheElements() {
  elements.screens = {
    menu: document.getElementById('screen-menu'),
    lobby: document.getElementById('screen-lobby'),
    reveal: document.getElementById('screen-reveal'),
    discussion: document.getElementById('screen-discussion'),
    voting: document.getElementById('screen-voting'),
    results: document.getElementById('screen-results')
  };
  
  elements.menu = {
    createBtn: document.getElementById('btn-create-game'),
    joinBtn: document.getElementById('btn-join-game'),
    joinForm: document.getElementById('join-form'),
    joinCodeInput: document.getElementById('join-code'),
    confirmJoinBtn: document.getElementById('btn-confirm-join'),
    cancelJoinBtn: document.getElementById('btn-cancel-join')
  };
  
  elements.lobby = {
    code: document.getElementById('lobby-code'),
    copyBtn: document.getElementById('btn-copy-code'),
    playersList: document.getElementById('lobby-players'),
    message: document.getElementById('lobby-message'),
    startBtn: document.getElementById('btn-start-game'),
    leaveBtn: document.getElementById('btn-leave-lobby')
  };
  
  elements.reveal = {
    card: document.getElementById('role-card'),
    icon: document.getElementById('role-icon'),
    title: document.getElementById('role-title'),
    description: document.getElementById('role-description'),
    wordSection: document.getElementById('role-word'),
    secretWord: document.getElementById('secret-word'),
    continueBtn: document.getElementById('btn-continue-reveal')
  };
  
  elements.discussion = {
    timer: document.getElementById('timer'),
    chatContainer: document.getElementById('chat-container'),
    messages: document.getElementById('chat-messages'),
    input: document.getElementById('chat-input'),
    sendBtn: document.getElementById('btn-send-chat'),
    voteBtn: document.getElementById('btn-call-vote')
  };
  
  elements.voting = {
    playersGrid: document.getElementById('voting-players'),
    status: document.getElementById('vote-status')
  };
  
  elements.results = {
    title: document.getElementById('results-title'),
    message: document.getElementById('result-message'),
    details: document.getElementById('result-details'),
    location: document.getElementById('result-location'),
    finalWord: document.getElementById('final-word'),
    playAgainBtn: document.getElementById('btn-play-again'),
    backMenuBtn: document.getElementById('btn-back-menu')
  };
  
  elements.modal = {
    error: document.getElementById('modal-error'),
    message: document.getElementById('error-message'),
    closeBtn: document.getElementById('btn-close-error')
  };
}

/**
 * Load localization data
 */
async function loadLocalization() {
  try {
    const response = await fetch('words.json');
    i18n = await response.json();
    applyLocalization();
  } catch (error) {
    console.error('Failed to load localization:', error);
    // Use English as fallback
    currentLang = 'en';
  }
}

/**
 * Apply localization to all elements with data-i18n attribute
 */
function applyLocalization() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (i18n[currentLang] && i18n[currentLang][key]) {
      el.textContent = i18n[currentLang][key];
    }
  });
  
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (i18n[currentLang] && i18n[currentLang][key]) {
      el.placeholder = i18n[currentLang][key];
    }
  });
}

/**
 * Get localized text
 */
function t(key) {
  return i18n[currentLang]?.[key] || key;
}

/**
 * Connect to Socket.IO server
 */
function connectSocket() {
  state.socket = io();
  
  state.socket.on('connect', () => {
    console.log('Connected to server');
  });
  
  state.socket.on('disconnect', () => {
    console.log('Disconnected from server');
  });
  
  // Game events
  state.socket.on('gameCreated', handleGameCreated);
  state.socket.on('gameJoined', handleGameJoined);
  state.socket.on('playerJoined', handlePlayerJoined);
  state.socket.on('playerLeft', handlePlayerLeft);
  state.socket.on('hostChanged', handleHostChanged);
  state.socket.on('gameStarted', handleGameStarted);
  state.socket.on('roleAssigned', handleRoleAssigned);
  
  // Timer events
  state.socket.on('timerStarted', handleTimerStarted);
  state.socket.on('timerUpdate', handleTimerUpdate);
  
  // Chat events
  state.socket.on('chatMessage', handleChatMessage);
  
  // Voting events
  state.socket.on('votingStarted', handleVotingStarted);
  state.socket.on('voteResult', handleVoteResult);
  
  // Game end
  state.socket.on('gameEnd', handleGameEnd);
  
  // Errors
  state.socket.on('error', handleError);
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
  // Menu buttons
  elements.menu.createBtn.addEventListener('click', showNamePrompt);
  elements.menu.joinBtn.addEventListener('click', showJoinForm);
  elements.menu.confirmJoinBtn.addEventListener('click', joinGame);
  elements.menu.cancelJoinBtn.addEventListener('click', hideJoinForm);
  elements.menu.joinCodeInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') joinGame();
  });
  
  // Lobby buttons
  elements.lobby.copyBtn.addEventListener('click', copyGameCode);
  elements.lobby.startBtn.addEventListener('click', startGame);
  elements.lobby.leaveBtn.addEventListener('click', leaveGame);
  
  // Reveal button
  elements.reveal.continueBtn.addEventListener('click', () => {
    showScreen('discussion');
  });
  
  // Discussion buttons
  elements.discussion.sendBtn.addEventListener('click', sendChatMessage);
  elements.discussion.input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendChatMessage();
  });
  elements.discussion.voteBtn.addEventListener('click', callVote);
  
  // Results buttons
  elements.results.playAgainBtn.addEventListener('click', playAgain);
  elements.results.backMenuBtn.addEventListener('click', backToMenu);
  
  // Error modal
  elements.modal.closeBtn.addEventListener('click', closeModal);
}

/**
 * Show screen by name
 */
function showScreen(screenName) {
  Object.values(elements.screens).forEach(screen => {
    screen.classList.remove('active');
  });
  
  if (elements.screens[screenName]) {
    elements.screens[screenName].classList.add('active');
  }
  
  state.gameState = screenName;
}

/**
 * Show name prompt and create game
 */
function showNamePrompt() {
  const name = prompt(t('enterName'), `Player${Math.floor(Math.random() * 1000)}`);
  if (name) {
    state.playerName = name.trim() || `Player${Math.floor(Math.random() * 1000)}`;
    state.socket.emit('createGame', { playerName: state.playerName });
  }
}

/**
 * Show join form
 */
function showJoinForm() {
  elements.menu.joinForm.classList.remove('hidden');
  elements.menu.joinCodeInput.focus();
}

/**
 * Hide join form
 */
function hideJoinForm() {
  elements.menu.joinForm.classList.add('hidden');
  elements.menu.joinCodeInput.value = '';
}

/**
 * Join existing game
 */
function joinGame() {
  const code = elements.menu.joinCodeInput.value.trim().toUpperCase();
  if (!code) {
    showError(t('gameNotFound'));
    return;
  }
  
  const name = prompt(t('enterName'), `Player${Math.floor(Math.random() * 1000)}`);
  if (name) {
    state.playerName = name.trim() || `Player${Math.floor(Math.random() * 1000)}`;
    state.socket.emit('joinGame', { code, playerName: state.playerName });
  }
}

/**
 * Handle game created
 */
function handleGameCreated(data) {
  state.playerId = data.playerId;
  state.gameCode = data.code;
  state.isHost = data.isHost;
  state.players = data.players;
  
  updateLobbyUI();
  showScreen('lobby');
}

/**
 * Handle game joined
 */
function handleGameJoined(data) {
  state.playerId = data.playerId;
  state.gameCode = data.code;
  state.isHost = data.isHost;
  state.players = data.players;
  
  updateLobbyUI();
  showScreen('lobby');
}

/**
 * Handle player joined
 */
function handlePlayerJoined(data) {
  state.players = data.players;
  updateLobbyUI();
  
  // Show notification
  addSystemMessage(`${data.player.name} ${t('playerJoined')}`);
}

/**
 * Handle player left
 */
function handlePlayerLeft(data) {
  state.players = data.players;
  updateLobbyUI();
  
  // Show notification
  addSystemMessage(`${data.playerName} ${t('playerLeft')}`);
}

/**
 * Handle host changed
 */
function handleHostChanged(data) {
  state.isHost = data.hostId === state.playerId;
  updateLobbyUI();
  
  if (state.isHost) {
    addSystemMessage(t('hostLeft'));
  }
}

/**
 * Update lobby UI
 */
function updateLobbyUI() {
  elements.lobby.code.textContent = state.gameCode;
  
  // Update players list
  elements.lobby.playersList.innerHTML = state.players.map(player => {
    const isHost = player.id === state.players.find(p => p.id === state.gameCode)?.id;
    const isCurrentPlayer = player.id === state.playerId;
    return `
      <li>
        <span class="player-indicator ${isHost ? 'host-indicator' : ''}"></span>
        ${player.name} ${isCurrentPlayer ? '(You)' : ''} ${isHost ? '👑' : ''}
      </li>
    `.trim();
  }).join('');
  
  // Show/hide start button
  if (state.isHost) {
    elements.lobby.startBtn.classList.remove('hidden');
    if (state.players.length >= 3) {
      elements.lobby.message.textContent = t('startGame');
    } else {
      elements.lobby.message.textContent = `${t('minPlayers')} (${state.players.length}/3)`;
    }
  } else {
    elements.lobby.startBtn.classList.add('hidden');
    elements.lobby.message.textContent = t('waitingForPlayers');
  }
}

/**
 * Copy game code to clipboard
 */
async function copyGameCode() {
  try {
    await navigator.clipboard.writeText(state.gameCode);
    const originalText = elements.lobby.copyBtn.textContent;
    elements.lobby.copyBtn.textContent = t('codeCopied');
    setTimeout(() => {
      elements.lobby.copyBtn.textContent = originalText;
    }, 2000);
  } catch (err) {
    // Fallback for older browsers
    const textArea = document.createElement('textarea');
    textArea.value = state.gameCode;
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);
  }
}

/**
 * Start game (host only)
 */
function startGame() {
  state.socket.emit('startGame', { code: state.gameCode });
}

/**
 * Handle game started
 */
function handleGameStarted(data) {
  console.log('Game started:', data);
}

/**
 * Handle role assigned
 */
function handleRoleAssigned(data) {
  state.role = data.role;
  state.word = data.word;
  
  // Update role card
  elements.reveal.card.className = `role-card ${data.role}`;
  elements.reveal.title.textContent = t(data.role);
  elements.reveal.description.textContent = data.role === 'spy' 
    ? t('blendIn') 
    : t('findTheSpy');
  
  if (data.role === 'civilian' && data.word) {
    elements.reveal.wordSection.classList.remove('hidden');
    elements.reveal.secretWord.textContent = data.word;
  } else {
    elements.reveal.wordSection.classList.add('hidden');
  }
  
  showScreen('reveal');
}

/**
 * Handle timer started
 */
function handleTimerStarted(data) {
  updateTimerDisplay(data.remaining);
}

/**
 * Handle timer update
 */
function handleTimerUpdate(data) {
  updateTimerDisplay(data.remaining);
  
  if (data.remaining === 0) {
    addSystemMessage(t('timerExpired'));
  }
}

/**
 * Update timer display
 */
function updateTimerDisplay(seconds) {
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  elements.discussion.timer.textContent = `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Send chat message
 */
function sendChatMessage() {
  const message = elements.discussion.input.value.trim();
  if (!message || !state.gameCode) return;
  
  state.socket.emit('chatMessage', {
    code: state.gameCode,
    message
  });
  
  elements.discussion.input.value = '';
}

/**
 * Handle chat message
 */
function handleChatMessage(data) {
  const messageEl = document.createElement('div');
  messageEl.className = `chat-message ${data.playerId === state.playerId ? 'own' : ''}`;
  messageEl.innerHTML = `
    <div class="player-name">${data.playerName}</div>
    <div class="message-text">${escapeHtml(data.message)}</div>
  `;
  
  elements.discussion.messages.appendChild(messageEl);
  elements.discussion.messages.scrollTop = elements.discussion.messages.scrollHeight;
}

/**
 * Add system message to chat
 */
function addSystemMessage(text) {
  const messageEl = document.createElement('div');
  messageEl.className = 'chat-message';
  messageEl.style.fontStyle = 'italic';
  messageEl.style.color = '#666';
  messageEl.textContent = text;
  
  elements.discussion.messages.appendChild(messageEl);
  elements.discussion.messages.scrollTop = elements.discussion.messages.scrollHeight;
}

/**
 * Call vote
 */
function callVote() {
  if (confirm('Are you sure you want to start voting?')) {
    state.socket.emit('callVote', { code: state.gameCode });
  }
}

/**
 * Handle voting started
 */
function handleVotingStarted(data) {
  state.hasVoted = false;
  
  // Create vote buttons for each player
  elements.voting.playersGrid.innerHTML = data.players
    .filter(p => p.id !== state.playerId) // Can't vote for yourself
    .map(player => `
      <button class="vote-btn" data-player-id="${player.id}">
        ${player.name}
      </button>
    `).join('');
  
  // Add click handlers
  document.querySelectorAll('.vote-btn').forEach(btn => {
    btn.addEventListener('click', () => submitVote(btn.dataset.playerId));
  });
  
  elements.voting.status.textContent = t('voteFor');
  showScreen('voting');
}

/**
 * Submit vote
 */
function submitVote(targetId) {
  if (state.hasVoted) return;
  
  state.socket.emit('vote', {
    code: state.gameCode,
    targetId
  });
  
  state.hasVoted = true;
  
  // Update UI
  document.querySelectorAll('.vote-btn').forEach(btn => {
    btn.classList.toggle('voted', btn.dataset.playerId === targetId);
    btn.disabled = true;
  });
  
  elements.voting.status.textContent = t('waitingForVotes');
}

/**
 * Handle vote result
 */
function handleVoteResult(data) {
  if (data.result === 'no_votes') {
    addSystemMessage(t('noVotesCast'));
    // Return to discussion after brief delay
    setTimeout(() => {
      showScreen('discussion');
    }, 2000);
  }
}

/**
 * Handle game end
 */
function handleGameEnd(data) {
  let resultClass, resultText;
  
  if (data.result === 'civilians_win') {
    resultClass = 'civilians-win';
    resultText = t('civiliansWin');
  } else if (data.result === 'spy_win_guess') {
    resultClass = 'spy-win';
    resultText = t('spyGuessedCorrectly');
  } else {
    resultClass = 'spy-win';
    resultText = t('spyWins');
  }
  
  elements.results.message.textContent = resultText;
  elements.results.message.className = `result-message ${resultClass}`;
  
  // Show details
  elements.results.details.innerHTML = `
    <p>${data.message || ''}</p>
    ${data.votedOut ? `<p>${t('votedOut')}: <strong>${data.votedOut}</strong></p>` : ''}
    <p><strong>${t('spies')}:</strong> ${data.spies.map(s => s.name).join(', ')}</p>
  `;
  
  // Show location
  if (data.word) {
    elements.results.location.classList.remove('hidden');
    elements.results.finalWord.textContent = data.word;
  } else {
    elements.results.location.classList.add('hidden');
  }
  
  showScreen('results');
}

/**
 * Play again (creates new game)
 */
function playAgain() {
  // Reset state
  state.playerId = null;
  state.gameCode = null;
  state.isHost = false;
  state.role = null;
  state.word = null;
  state.players = [];
  state.hasVoted = false;
  
  // Clear chat
  elements.discussion.messages.innerHTML = '';
  
  // Create new game
  showNamePrompt();
}

/**
 * Back to menu
 */
function backToMenu() {
  // Reset state
  state.playerId = null;
  state.gameCode = null;
  state.isHost = false;
  state.role = null;
  state.word = null;
  state.players = [];
  state.hasVoted = false;
  
  // Clear chat
  elements.discussion.messages.innerHTML = '';
  
  showScreen('menu');
}

/**
 * Leave game
 */
function leaveGame() {
  if (confirm('Are you sure you want to leave the game?')) {
    backToMenu();
    // Reload page to disconnect properly
    window.location.reload();
  }
}

/**
 * Show error modal
 */
function showError(message) {
  elements.modal.message.textContent = message;
  elements.modal.error.classList.remove('hidden');
}

/**
 * Close error modal
 */
function closeModal() {
  elements.modal.error.classList.add('hidden');
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', init);
