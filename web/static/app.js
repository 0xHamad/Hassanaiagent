/* Hassan AI Agent — frontend */

'use strict';

// ─── State ───────────────────────────────────────────────────────────────────
let messages = [];          // [{role, content}]
let sessions = [];          // [{id, title, messages}]
let activeSession = null;
let isLoading = false;
let settings = loadSettings();

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const welcomeScreen  = document.getElementById('welcome-screen');
const chatMessages   = document.getElementById('chat-messages');
const userInput      = document.getElementById('user-input');
const sendBtn        = document.getElementById('send-btn');
const charCount      = document.getElementById('char-count');
const historyList    = document.getElementById('history-list');
const settingsModal  = document.getElementById('settings-modal');
const settingsStatus = document.getElementById('settings-status');
const topbarTitle    = document.getElementById('topbar-title');

// ─── Boot ─────────────────────────────────────────────────────────────────────
(function init() {
  applySavedSettings();
  loadSessions();
  renderHistory();
  bindEvents();
  userInput.focus();
})();

// ─── Settings persistence ─────────────────────────────────────────────────────
function loadSettings() {
  try { return JSON.parse(localStorage.getItem('hassan_settings') || '{}'); }
  catch { return {}; }
}

function saveSettings(obj) {
  settings = { ...settings, ...obj };
  localStorage.setItem('hassan_settings', JSON.stringify(settings));
}

function applySavedSettings() {
  const el = (id) => document.getElementById(id);
  if (settings.provider) el('set-provider').value = settings.provider;
  if (settings.api_key)  el('set-api-key').value  = settings.api_key;
  if (settings.cursor_api_key) el('set-cursor-key').value = settings.cursor_api_key;
  if (settings.model)    el('set-model').value    = settings.model;
  if (settings.base_url) el('set-base-url').value = settings.base_url;
  if (settings.theme)    applyTheme(settings.theme);
  toggleCursorRow();
}

// ─── Session management ────────────────────────────────────────────────────────
function loadSessions() {
  try { sessions = JSON.parse(localStorage.getItem('hassan_sessions') || '[]'); }
  catch { sessions = []; }
}

function persistSessions() {
  localStorage.setItem('hassan_sessions', JSON.stringify(sessions.slice(0, 80)));
}

function newSession() {
  const id = Date.now().toString();
  const sess = { id, title: 'New Chat', messages: [] };
  sessions.unshift(sess);
  activeSession = sess;
  messages = sess.messages;
  persistSessions();
  return sess;
}

function openSession(id) {
  const sess = sessions.find(s => s.id === id);
  if (!sess) return;
  activeSession = sess;
  messages = sess.messages;
  renderHistory();
  renderAllMessages();
  if (messages.length > 0) showChat();
  else showWelcome();
}

function updateSessionTitle(sess, firstMsg) {
  sess.title = firstMsg.length > 50 ? firstMsg.slice(0, 47) + '...' : firstMsg;
}

// ─── Render history list ───────────────────────────────────────────────────────
function renderHistory() {
  if (sessions.length === 0) {
    historyList.innerHTML = `
      <div class="right-panel-empty">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        No chats yet
      </div>`;
    return;
  }
  historyList.innerHTML = sessions.map(s => `
    <div class="history-item ${activeSession && activeSession.id === s.id ? 'active' : ''}"
         data-id="${s.id}">
      <div class="history-check"></div>
      <div class="history-text">
        <div class="history-title">${escHtml(s.title)}</div>
        <div class="history-preview">${s.messages.length} message${s.messages.length !== 1 ? 's' : ''}</div>
      </div>
    </div>`).join('');

  historyList.querySelectorAll('.history-item').forEach(el => {
    el.addEventListener('click', () => openSession(el.dataset.id));
  });
}

// ─── Render messages ──────────────────────────────────────────────────────────
function renderAllMessages() {
  chatMessages.innerHTML = '';
  messages.forEach(m => appendMessage(m.role, m.content, false));
}

function appendMessage(role, content, animate = true) {
  const row = document.createElement('div');
  row.className = `msg-row ${role}`;
  if (!animate) row.style.animation = 'none';

  const initial = role === 'user' ? 'U' : 'H';
  const avatarBg = role === 'user' ? '' : '';

  row.innerHTML = `
    <div class="msg-avatar">${initial}</div>
    <div class="msg-content">
      ${role === 'user'
        ? `<div class="msg-bubble">${escHtml(content)}</div>`
        : `<div class="kimi-ai-bubble">${renderMarkdown(content)}</div>`}
    </div>`;

  chatMessages.appendChild(row);
  addCopyButtons(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderMarkdown(text) {
  if (typeof marked === 'undefined') return escHtml(text).replace(/\n/g, '<br>');
  try {
    marked.setOptions({ breaks: true, gfm: true });
    return marked.parse(text);
  } catch {
    return escHtml(text).replace(/\n/g, '<br>');
  }
}

function addCopyButtons(container) {
  container.querySelectorAll('pre').forEach(pre => {
    const code = pre.querySelector('code');
    if (!code) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'code-wrapper';
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.addEventListener('click', () => {
      navigator.clipboard.writeText(code.innerText).then(() => {
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
      });
    });
    wrapper.appendChild(btn);
  });
}

// ─── Show/hide views ──────────────────────────────────────────────────────────
function showChat() {
  welcomeScreen.style.display = 'none';
  chatMessages.style.display = 'flex';
  topbarTitle.textContent = activeSession?.title || 'AI Chat';
}
function showWelcome() {
  welcomeScreen.style.display = 'flex';
  chatMessages.style.display = 'none';
  topbarTitle.textContent = 'AI Chat';
}

// ─── Typing indicator ─────────────────────────────────────────────────────────
let typingRow = null;
function showTyping() {
  typingRow = document.createElement('div');
  typingRow.className = 'msg-row assistant';
  typingRow.innerHTML = `
    <div class="msg-avatar">H</div>
    <div class="msg-content">
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>`;
  chatMessages.appendChild(typingRow);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}
function hideTyping() {
  if (typingRow) { typingRow.remove(); typingRow = null; }
}

// ─── Send message ─────────────────────────────────────────────────────────────
async function sendMessage(text) {
  text = (text || userInput.value).trim();
  if (!text || isLoading) return;

  if (!activeSession) newSession();
  if (messages.length === 0) updateSessionTitle(activeSession, text);

  messages.push({ role: 'user', content: text });
  showChat();
  appendMessage('user', text);
  userInput.value = '';
  userInput.style.height = 'auto';
  charCount.textContent = '0';
  updateSendBtn();
  renderHistory();

  isLoading = true;
  setLoading(true);
  showTyping();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages,
        provider: settings.provider || '',
        api_key: settings.api_key || '',
        cursor_api_key: settings.cursor_api_key || '',
        model: settings.model || '',
        base_url: settings.base_url || '',
      }),
    });
    const data = await res.json();
    hideTyping();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    const reply = data.reply || '';
    messages.push({ role: 'assistant', content: reply });
    appendMessage('assistant', reply);
    persistSessions();
    renderHistory();
  } catch (e) {
    hideTyping();
    showToast('Error: ' + e.message);
  } finally {
    isLoading = false;
    setLoading(false);
  }
}

function setLoading(on) {
  sendBtn.classList.toggle('loading', on);
  userInput.disabled = on;
}

// ─── Input events ─────────────────────────────────────────────────────────────
function updateSendBtn() {
  sendBtn.classList.toggle('active', userInput.value.trim().length > 0);
}

function bindEvents() {
  userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 180) + 'px';
    charCount.textContent = userInput.value.length.toLocaleString();
    updateSendBtn();
  });

  userInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener('click', () => sendMessage());

  // Quick cards
  document.querySelectorAll('.quick-card').forEach(btn => {
    btn.addEventListener('click', () => sendMessage(btn.dataset.prompt));
  });

  // New chat
  document.getElementById('new-chat-btn').addEventListener('click', () => {
    newSession();
    showWelcome();
    renderHistory();
    userInput.focus();
  });

  // Settings modal
  document.getElementById('open-settings').addEventListener('click', openSettings);
  document.getElementById('close-settings').addEventListener('click', closeSettings);
  settingsModal.addEventListener('click', e => {
    if (e.target === settingsModal) closeSettings();
  });
  document.getElementById('save-settings').addEventListener('click', doSaveSettings);
  document.getElementById('set-provider').addEventListener('change', toggleCursorRow);

  // Theme
  document.getElementById('theme-light').addEventListener('click', () => applyTheme('light'));
  document.getElementById('theme-dark').addEventListener('click', () => applyTheme('dark'));

  // Keyboard shortcut ⌘K
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      document.getElementById('search-input').focus();
    }
    if (e.key === 'Escape') closeSettings();
  });

  // Nav items
  document.querySelectorAll('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      item.classList.add('active');
      topbarTitle.textContent = item.querySelector('span').textContent.trim();
    });
  });
}

// ─── Settings modal ───────────────────────────────────────────────────────────
function openSettings() {
  settingsModal.classList.add('open');
  settingsStatus.textContent = '';
  settingsStatus.className = 'settings-note';
}
function closeSettings() {
  settingsModal.classList.remove('open');
}

function toggleCursorRow() {
  const provider = document.getElementById('set-provider').value;
  document.getElementById('cursor-key-row').style.display =
    provider === 'cursor' ? 'flex' : 'none';
}

function doSaveSettings() {
  const get = id => document.getElementById(id).value.trim();
  const newSettings = {
    provider:       get('set-provider'),
    api_key:        get('set-api-key'),
    cursor_api_key: get('set-cursor-key'),
    model:          get('set-model'),
    base_url:       get('set-base-url'),
  };
  saveSettings(newSettings);
  settingsStatus.textContent = 'Settings saved!';
  settingsStatus.className = 'settings-note ok';
  setTimeout(closeSettings, 900);
}

// ─── Theme ────────────────────────────────────────────────────────────────────
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.getElementById('theme-light').classList.toggle('active', theme === 'light');
  document.getElementById('theme-dark').classList.toggle('active', theme === 'dark');
  saveSettings({ theme });
}

// ─── Toast ────────────────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg) {
  let t = document.querySelector('.toast');
  if (!t) {
    t = document.createElement('div');
    t.className = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 4000);
}

// ─── Utils ────────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
