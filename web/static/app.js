/* Hassan AI Agent — frontend with auth */
'use strict';

// ─── State ─────────────────────────────────────────────────────────────────────
let messages   = [];
let sessions   = [];
let activeSession = null;
let isLoading  = false;
let currentUser = null;
let authToken   = localStorage.getItem('hassan_token') || '';
let settings    = loadSettings();

const FALLBACK_DEFAULTS = {
  provider: 'gemini',
  model: 'gemini-2.5-flash',
  base_url: 'https://generativelanguage.googleapis.com/v1beta/openai/',
};

// ─── DOM refs ──────────────────────────────────────────────────────────────────
const splash        = document.getElementById('splash');
const authScreen    = document.getElementById('auth-screen');
const dashboard     = document.getElementById('dashboard');
const welcomeScreen = document.getElementById('welcome-screen');
const chatMessages  = document.getElementById('chat-messages');
const userInput     = document.getElementById('user-input');
const sendBtn       = document.getElementById('send-btn');
const charCount     = document.getElementById('char-count');
const historyList   = document.getElementById('history-list');
const settingsModal = document.getElementById('settings-modal');
const settingsStatus= document.getElementById('settings-status');
const topbarTitle   = document.getElementById('topbar-title');

// ─── Boot ──────────────────────────────────────────────────────────────────────
(async function boot() {
  applySavedSettings();
  await applyUserDefaults(false);

  // Show splash for 2.8s then route
  setTimeout(async () => {
    splash.classList.add('fade-out');
    await sleep(480);
    splash.style.display = 'none';

    if (authToken) {
      const ok = await verifyToken();
      if (ok) { showDashboard(); return; }
    }
    showAuth('login');
  }, 2900);
})();

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ─── Auth routing ──────────────────────────────────────────────────────────────
function showAuth(mode) {
  authScreen.style.display = 'flex';
  dashboard.style.display  = 'none';
  showAuthMode(mode);
  bindAuthEvents();
}

function showAuthMode(mode) {
  document.getElementById('login-card').style.display  = mode === 'login'  ? 'block' : 'none';
  document.getElementById('signup-card').style.display = mode === 'signup' ? 'block' : 'none';
}

function showDashboard() {
  authScreen.style.display = 'none';
  dashboard.style.display  = 'grid';
  initDashboard();
}

// ─── Token verify ─────────────────────────────────────────────────────────────
async function verifyToken() {
  try {
    const r = await fetch('/api/auth/me', {
      headers: { 'x-token': authToken },
    });
    if (!r.ok) { authToken = ''; localStorage.removeItem('hassan_token'); return false; }
    const data = await r.json();
    currentUser = data;
    return true;
  } catch { return false; }
}

// ─── Auth events ──────────────────────────────────────────────────────────────
let authEventsBound = false;
function bindAuthEvents() {
  if (authEventsBound) return;
  authEventsBound = true;

  document.getElementById('go-signup').addEventListener('click', () => showAuthMode('signup'));
  document.getElementById('go-login').addEventListener('click', () => showAuthMode('login'));

  document.getElementById('login-btn').addEventListener('click', doLogin);
  document.getElementById('signup-btn').addEventListener('click', doSignup);

  document.getElementById('login-password').addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
  document.getElementById('signup-confirm').addEventListener('keydown', e => { if (e.key === 'Enter') doSignup(); });
}

async function readJsonResponse(r) {
  const text = await r.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return { detail: text.slice(0, 200) }; }
}

async function doLogin() {
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  const errEl    = document.getElementById('login-error');
  const btn      = document.getElementById('login-btn');
  const btnText  = document.getElementById('login-btn-text');
  const spinner  = document.getElementById('login-spinner');

  errEl.textContent = '';
  if (!username || !password) { errEl.textContent = 'Please fill in all fields.'; return; }

  btn.disabled = true;
  btnText.style.display = 'none';
  spinner.style.display = 'block';

  try {
    const r = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await readJsonResponse(r);
    if (!r.ok) {
      const msg = data.detail || 'Login failed.';
      errEl.textContent = r.status === 403 && msg.toLowerCase().includes('block')
        ? 'Your account has been blocked. Contact admin.'
        : msg;
      return;
    }
    authToken = data.token;
    currentUser = { username: data.username };
    localStorage.setItem('hassan_token', authToken);
    await applyUserDefaults(false);
    showDashboard();
  } catch (e) {
    errEl.textContent = e.message === 'Failed to fetch'
      ? 'Cannot reach server. Run run_web.bat and open http://127.0.0.1:8080'
      : (e.message || 'Network error. Try again.');
  } finally {
    btn.disabled = false;
    btnText.style.display = '';
    spinner.style.display = 'none';
  }
}

async function doSignup() {
  const username = document.getElementById('signup-username').value.trim();
  const password = document.getElementById('signup-password').value;
  const confirm  = document.getElementById('signup-confirm').value;
  const errEl    = document.getElementById('signup-error');
  const btn      = document.getElementById('signup-btn');
  const btnText  = document.getElementById('signup-btn-text');
  const spinner  = document.getElementById('signup-spinner');

  errEl.textContent = '';
  if (!username || !password) { errEl.textContent = 'Please fill in all fields.'; return; }
  if (password !== confirm)   { errEl.textContent = 'Passwords do not match.'; return; }
  if (password.length < 6)   { errEl.textContent = 'Password must be at least 6 characters.'; return; }

  btn.disabled = true;
  btnText.style.display = 'none';
  spinner.style.display = 'block';

  try {
    const r = await fetch('/api/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await readJsonResponse(r);
    if (!r.ok) {
      const msg = data.detail || 'Signup failed.';
      errEl.textContent = r.status === 403 && msg.toLowerCase().includes('limit')
        ? 'Signup limit reached. Contact admin.'
        : msg;
      return;
    }
    authToken = data.token;
    currentUser = { username: data.username };
    localStorage.setItem('hassan_token', authToken);
    await applyUserDefaults(false);
    showDashboard();
  } catch (e) {
    errEl.textContent = e.message === 'Failed to fetch'
      ? 'Cannot reach server. Run run_web.bat and open http://127.0.0.1:8080'
      : (e.message || 'Network error. Try again.');
  } finally {
    btn.disabled = false;
    btnText.style.display = '';
    spinner.style.display = 'none';
  }
}

// ─── Dashboard init ────────────────────────────────────────────────────────────
function initDashboard() {
  loadSessions().then(() => {
    renderHistory();
    bindDashboardEvents();
    applySavedSettings();
    if (currentUser) {
      const name = currentUser.username;
      const el = document.getElementById('sidebar-username');
      if (el) el.textContent = name;
      const av = document.getElementById('user-avatar-initials');
      if (av) av.textContent = name.charAt(0).toUpperCase();
    }
    userInput.focus();
  });
}

// ─── Sessions (Supabase via API) ───────────────────────────────────────────────
async function loadSessions() {
  try {
    const r = await fetch('/api/conversations', { headers: { 'x-token': authToken } });
    if (!r.ok) throw new Error('api');
    const data = await r.json();
    sessions = (data.conversations || []).map(c => ({
      id: c.id,
      title: c.title || 'New Chat',
      preview: c.preview || '',
      messages: [],
    }));
  } catch {
    try { sessions = JSON.parse(localStorage.getItem('hassan_sessions') || '[]'); }
    catch { sessions = []; }
  }
}
function persistSessions() {
  localStorage.setItem('hassan_sessions', JSON.stringify(sessions.slice(0, 80)));
}
async function newSession() {
  try {
    const r = await fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-token': authToken },
      body: JSON.stringify({ title: 'New Chat' }),
    });
    if (r.ok) {
      const conv = await r.json();
      const sess = { id: conv.id, title: conv.title || 'New Chat', messages: [] };
      sessions.unshift(sess);
      activeSession = sess;
      messages = sess.messages;
      renderHistory();
      return sess;
    }
  } catch {}
  const id = Date.now().toString();
  const sess = { id, title: 'New Chat', messages: [] };
  sessions.unshift(sess);
  activeSession = sess;
  messages = sess.messages;
  persistSessions();
  return sess;
}
async function openSession(id) {
  const local = sessions.find(s => s.id === id);
  if (!local) return;
  activeSession = local;
  try {
    const r = await fetch(`/api/conversations/${encodeURIComponent(id)}`, {
      headers: { 'x-token': authToken },
    });
    if (r.ok) {
      const data = await r.json();
      messages = (data.messages || []).map(m => ({ role: m.role, content: m.content }));
      local.messages = messages;
      local.title = data.conversation?.title || local.title;
    } else {
      messages = local.messages || [];
    }
  } catch {
    messages = local.messages || [];
  }
  renderHistory();
  renderAllMessages();
  messages.length > 0 ? showChat() : showWelcomeView();
}
function updateSessionTitle(sess, firstMsg) {
  sess.title = firstMsg.length > 50 ? firstMsg.slice(0, 47) + '...' : firstMsg;
}

// ─── Render history ────────────────────────────────────────────────────────────
function renderHistory() {
  if (!historyList) return;
  if (sessions.length === 0) {
    historyList.innerHTML = `
      <div class="right-panel-empty">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        No chats yet
      </div>`;
    return;
  }
  historyList.innerHTML = sessions.map(s => `
    <div class="history-item ${activeSession && activeSession.id === s.id ? 'active' : ''}" data-id="${s.id}">
      <div class="history-check"></div>
      <div class="history-text">
        <div class="history-title">${esc(s.title)}</div>
        <div class="history-preview">${esc(s.preview || (s.messages.length + ' message' + (s.messages.length !== 1 ? 's' : '')))}</div>
      </div>
    </div>`).join('');
  historyList.querySelectorAll('.history-item').forEach(el => {
    el.addEventListener('click', () => openSession(el.dataset.id));
  });
}

// ─── Render messages ───────────────────────────────────────────────────────────
function renderAllMessages() {
  chatMessages.innerHTML = '';
  messages.forEach(m => appendMessage(m.role, m.content, false));
}

function appendMessage(role, content, animate = true) {
  const row = document.createElement('div');
  row.className = `msg-row ${role}`;
  if (!animate) row.style.animation = 'none';

  const avatarHtml = role === 'user'
    ? `<div class="msg-avatar">${currentUser ? currentUser.username.charAt(0).toUpperCase() : 'U'}</div>`
    : `<div class="msg-avatar"><img src="/static/logo.jpg" alt="H" /></div>`;

  row.innerHTML = `
    ${avatarHtml}
    <div class="msg-content">
      ${role === 'user'
        ? `<div class="msg-bubble">${esc(content)}</div>`
        : `<div class="kimi-ai-bubble">${renderMD(content)}</div>`}
    </div>`;
  chatMessages.appendChild(row);
  addCopyButtons(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderMD(text) {
  if (typeof marked === 'undefined') return esc(text).replace(/\n/g, '<br>');
  try { marked.setOptions({ breaks: true, gfm: true }); return marked.parse(text); }
  catch { return esc(text).replace(/\n/g, '<br>'); }
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
        btn.textContent = 'Copied!'; btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
      });
    });
    wrapper.appendChild(btn);
  });
}

// ─── View switching ────────────────────────────────────────────────────────────
function showChat() {
  welcomeScreen.style.display = 'none';
  chatMessages.style.display  = 'flex';
  if (topbarTitle) topbarTitle.textContent = activeSession?.title || 'AI Chat';
}
function showWelcomeView() {
  welcomeScreen.style.display = 'flex';
  chatMessages.style.display  = 'none';
  if (topbarTitle) topbarTitle.textContent = 'AI Chat';
}

// ─── Typing indicator ──────────────────────────────────────────────────────────
let typingRow = null;
function showTyping() {
  typingRow = document.createElement('div');
  typingRow.className = 'msg-row assistant';
  typingRow.innerHTML = `
    <div class="msg-avatar"><img src="/static/logo.jpg" alt="H" /></div>
    <div class="msg-content">
      <div class="typing-indicator">
        <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
      </div>
    </div>`;
  chatMessages.appendChild(typingRow);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}
function hideTyping() { if (typingRow) { typingRow.remove(); typingRow = null; } }

// ─── Send message ──────────────────────────────────────────────────────────────
async function sendMessage(text) {
  text = (text || userInput.value).trim();
  if (!text || isLoading) return;

  if (!activeSession) await newSession();
  if (messages.length === 0) updateSessionTitle(activeSession, text);

  messages.push({ role: 'user', content: text });
  showChat();
  appendMessage('user', text);
  userInput.value = '';
  userInput.style.height = 'auto';
  if (charCount) charCount.textContent = '0';
  updateSendBtn();
  renderHistory();

  isLoading = true;
  setLoading(true);
  showTyping();

  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-token': authToken },
      body: JSON.stringify({
        messages,
        conversation_id: activeSession?.id || '',
        provider: settings.provider || '',
        api_key: settings.api_key || '',
        cursor_api_key: settings.cursor_api_key || '',
        model: settings.model || '',
        base_url: settings.base_url || '',
      }),
    });
    const data = await r.json();
    hideTyping();
    if (r.status === 401) { showToast('Session expired — please sign in again.'); doLogout(); return; }
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    if (data.conversation_id && activeSession) activeSession.id = data.conversation_id;
    messages.push({ role: 'assistant', content: data.reply });
    appendMessage('assistant', data.reply);
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
function updateSendBtn() {
  sendBtn.classList.toggle('active', userInput.value.trim().length > 0);
}

// ─── Logout ────────────────────────────────────────────────────────────────────
async function doLogout() {
  try { await fetch('/api/auth/logout', { method: 'POST', headers: { 'x-token': authToken } }); } catch {}
  authToken = '';
  currentUser = null;
  localStorage.removeItem('hassan_token');
  dashboard.style.display = 'none';
  authEventsBound = false;
  showAuth('login');
}

// ─── Dashboard events ──────────────────────────────────────────────────────────
let dashEventsBound = false;
function bindDashboardEvents() {
  if (dashEventsBound) return;
  dashEventsBound = true;

  userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 160) + 'px';
    if (charCount) charCount.textContent = userInput.value.length.toLocaleString();
    updateSendBtn();
  });
  userInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
  sendBtn.addEventListener('click', () => sendMessage());

  document.querySelectorAll('.quick-card').forEach(btn => {
    btn.addEventListener('click', () => sendMessage(btn.dataset.prompt));
  });

  document.getElementById('new-chat-btn').addEventListener('click', async () => {
    await newSession(); showWelcomeView(); renderHistory(); userInput.focus();
  });

  document.getElementById('open-settings')?.addEventListener('click', openSettings);
  document.getElementById('open-settings-top')?.addEventListener('click', openSettings);
  document.getElementById('close-settings').addEventListener('click', closeSettings);
  settingsModal.addEventListener('click', e => { if (e.target === settingsModal) closeSettings(); });
  document.getElementById('save-settings').addEventListener('click', doSaveSettings);
  document.getElementById('set-provider').addEventListener('change', toggleCursorRow);

  document.getElementById('logout-btn').addEventListener('click', doLogout);

  document.getElementById('theme-light').addEventListener('click', () => applyTheme('light'));
  document.getElementById('theme-dark').addEventListener('click', () => applyTheme('dark'));

  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); document.getElementById('search-input')?.focus(); }
    if (e.key === 'Escape') closeSettings();
  });

  document.querySelectorAll('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      item.classList.add('active');
      if (topbarTitle) topbarTitle.textContent = item.querySelector('span').textContent.trim();
    });
  });
}

// ─── Settings ──────────────────────────────────────────────────────────────────
async function applyUserDefaults(force) {
  let defs = { ...FALLBACK_DEFAULTS };
  try {
    const r = await fetch('/api/default-settings');
    if (r.ok) {
      const d = await r.json();
      defs = {
        provider: d.provider || FALLBACK_DEFAULTS.provider,
        model: d.model || FALLBACK_DEFAULTS.model,
        base_url: d.base_url || FALLBACK_DEFAULTS.base_url,
      };
    }
  } catch {}
  const cur = loadSettings();
  if (force || !cur.provider) {
    saveSettings({ ...defs, api_key: cur.api_key || '', cursor_api_key: cur.cursor_api_key || '' });
    settings = loadSettings();
  }
}

function loadSettings() {
  try { return JSON.parse(localStorage.getItem('hassan_settings') || '{}'); }
  catch { return {}; }
}
function saveSettings(obj) {
  settings = { ...settings, ...obj };
  localStorage.setItem('hassan_settings', JSON.stringify(settings));
}
function applySavedSettings() {
  ensureDefaultSettings();
  const g = id => document.getElementById(id);
  if (g('set-provider')) g('set-provider').value = settings.provider || FALLBACK_DEFAULTS.provider;
  if (settings.api_key && g('set-api-key')) g('set-api-key').value = settings.api_key;
  if (settings.cursor_api_key && g('set-cursor-key')) g('set-cursor-key').value = settings.cursor_api_key;
  if (g('set-model')) g('set-model').value = settings.model || FALLBACK_DEFAULTS.model;
  if (g('set-base-url')) g('set-base-url').value = settings.base_url || FALLBACK_DEFAULTS.base_url;
  if (settings.theme) applyTheme(settings.theme);
  toggleCursorRow();
}

function ensureDefaultSettings() {
  if (!settings.provider) {
    saveSettings({ ...FALLBACK_DEFAULTS, ...settings });
    settings = loadSettings();
  }
}
function openSettings() { settingsModal.classList.add('open'); settingsStatus.textContent = ''; settingsStatus.className = 'settings-note'; }
function closeSettings() { settingsModal.classList.remove('open'); }
function toggleCursorRow() {
  const el = document.getElementById('set-provider');
  if (!el) return;
  const row = document.getElementById('cursor-key-row');
  if (row) row.style.display = el.value === 'cursor' ? 'flex' : 'none';
}
function doSaveSettings() {
  const g = id => document.getElementById(id)?.value?.trim() || '';
  saveSettings({ provider: g('set-provider'), api_key: g('set-api-key'), cursor_api_key: g('set-cursor-key'), model: g('set-model'), base_url: g('set-base-url') });
  settingsStatus.textContent = 'Settings saved!';
  settingsStatus.className = 'settings-note ok';
  setTimeout(closeSettings, 900);
}

// ─── Theme ─────────────────────────────────────────────────────────────────────
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.getElementById('theme-light')?.classList.toggle('active', theme === 'light');
  document.getElementById('theme-dark')?.classList.toggle('active', theme === 'dark');
  saveSettings({ theme });
}

// ─── Toast ─────────────────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg) {
  let t = document.querySelector('.toast');
  if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 4000);
}

// ─── Utils ─────────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
