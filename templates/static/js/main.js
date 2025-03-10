function showEliminationPopup(nickname, role) {
  // Create overlay container.
  const overlay = document.createElement('div');
  overlay.className = 'popup-overlay';
  
  // Create popup element.
  const popup = document.createElement('div');
  popup.className = 'popup';
  
  // Create close button.
  const closeBtn = document.createElement('button');
  closeBtn.className = 'popup-close';
  closeBtn.innerHTML = '&times;';
  closeBtn.onclick = () => document.body.removeChild(overlay);
  
  // Create header and body.
  const header = document.createElement('div');
  header.className = 'popup-header';
  header.innerText = 'Player Eliminated';
  
  const body = document.createElement('div');
  body.className = 'popup-body';
  body.innerText = nickname + (role === 'spy' ? ' was the Spy!' : ' was not the Spy!');
  
  // Append elements.
  popup.appendChild(closeBtn);
  popup.appendChild(header);
  popup.appendChild(body);
  overlay.appendChild(popup);
  
  // Append to body.
  document.body.appendChild(overlay);
}
