/* Hassan AI Agent — frontend with auth */
'use strict';

// ─── State ─────────────────────────────────────────────────────────────────────
let messages   = [];
let sessions   = [];
let activeSession = null;
let isLoading  = false;
let currentUser = null;
let authToken   = localStorage.getItem('hassan_token') || '';
let settings    = {};

const FALLBACK_DEFAULTS = {
  provider: 'gemini',
  model: 'gemini-3.1-flash-lite',
  base_url: 'https://generativelanguage.googleapis.com/v1beta/openai/',
};

const GEMINI_DEFAULT = 'gemini-3.1-flash-lite';
const GEMINI_LEGACY = new Set([
  '', 'gemini-2.5-flash', 'gemini-2.5-flash-lite',
  'gemini-2.0-flash', 'gemini-2.0-flash-lite',
]);

let modelsCatalog = null;

function providerDefaultModel(provider) {
  const cat = modelsCatalog?.[provider];
  if (cat?.default) return cat.default;
  if (provider === 'gemini') return GEMINI_DEFAULT;
  return FALLBACK_DEFAULTS.model;
}

function resolveModelForProvider(provider, savedModel) {
  const def = providerDefaultModel(provider);
  if (provider === 'gemini' && GEMINI_LEGACY.has(savedModel || '')) return def;
  if (!savedModel) return def;
  return savedModel;
}

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
const sidebar       = document.getElementById('sidebar');
const rightPanel    = document.getElementById('right-panel');
const layoutEl      = document.getElementById('dashboard');
const mobileBackdrop = document.getElementById('mobile-backdrop');
const SPLASH_MS = 4000;

// ─── Boot ──────────────────────────────────────────────────────────────────────
function clearSplashFallback() {
  if (window.__hideSplashFallback) {
    clearTimeout(window.__hideSplashFallback);
    window.__hideSplashFallback = null;
  }
}

async function finishBoot() {
  try {
    await loadModelsCatalog();
    if (splash) splash.classList.add('fade-out');
    await sleep(400);
    if (splash) splash.style.display = 'none';
    clearSplashFallback();

    if (authToken) {
      const ok = await verifyToken();
      if (ok) {
        await fetchUserSettings();
        if (!settings.provider) await applyUserDefaults(true);
        else applySavedSettings();
        showDashboard();
        return;
      }
    }
    showAuth('login');
  } catch (e) {
    console.error('Boot error:', e);
    if (splash) splash.style.display = 'none';
    clearSplashFallback();
    showAuth('login');
  }
}

function startBoot() {
  setTimeout(finishBoot, SPLASH_MS);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startBoot);
} else {
  startBoot();
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ─── Auth routing ──────────────────────────────────────────────────────────────
function showAuth(mode) {
  if (!authScreen) return;
  authScreen.style.display = 'flex';
  if (dashboard) dashboard.style.display = 'none';
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
    if (!r.ok) { errEl.textContent = data.detail || 'Login failed.'; return; }
    authToken = data.token;
    localStorage.setItem('hassan_token', authToken);
    resetChatState();
    await refreshCurrentUser();
    await fetchUserSettings();
    if (!settings.provider) await applyUserDefaults(true);
    else applySavedSettings();
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
    if (!r.ok) { errEl.textContent = data.detail || 'Signup failed.'; return; }
    authToken = data.token;
    localStorage.setItem('hassan_token', authToken);
    resetChatState();
    await refreshCurrentUser();
    await fetchUserSettings();
    await applyUserDefaults(true);
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
  sessions = [];
  if (!authToken) return;
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
    sessions = [];
  }
}
function persistSessions() {
  /* history lives on server per user — no shared localStorage */
}
async function newSession() {
  messages = [];
  activeSession = null;
  if (chatMessages) chatMessages.innerHTML = '';
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
      renderHistory();
      return sess;
    }
  } catch {}
  const id = Date.now().toString();
  const sess = { id, title: 'New Chat', messages: [] };
  sessions.unshift(sess);
  activeSession = sess;
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
  closeMobilePanels();
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
        message: text,
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

// ─── Mobile / panel toggles ────────────────────────────────────────────────────
function isMobileSidebar() {
  return window.matchMedia('(max-width: 768px)').matches;
}

function isMobileHistory() {
  return window.matchMedia('(max-width: 1024px)').matches;
}

function updateMobileBackdrop() {
  const open = sidebar?.classList.contains('open') || rightPanel?.classList.contains('open');
  mobileBackdrop?.classList.toggle('show', !!open);
  document.body.classList.toggle('drawer-open', !!open);
}

function openSidebar() {
  if (!isMobileSidebar()) return;
  rightPanel?.classList.remove('open');
  sidebar?.classList.add('open');
  updateMobileBackdrop();
}

function closeSidebar() {
  sidebar?.classList.remove('open');
  updateMobileBackdrop();
}

function toggleSidebar() {
  if (isMobileSidebar()) {
    if (sidebar?.classList.contains('open')) closeSidebar();
    else openSidebar();
    return;
  }
  layoutEl?.classList.toggle('sidebar-collapsed');
}

function openHistoryPanel() {
  if (isMobileHistory()) {
    sidebar?.classList.remove('open');
    rightPanel?.classList.add('open');
    updateMobileBackdrop();
    return;
  }
  layoutEl?.classList.remove('history-collapsed');
}

function closeHistoryPanel() {
  rightPanel?.classList.remove('open');
  if (!isMobileHistory()) layoutEl?.classList.add('history-collapsed');
  updateMobileBackdrop();
}

function toggleHistoryPanel() {
  if (isMobileHistory()) {
    if (rightPanel?.classList.contains('open')) closeHistoryPanel();
    else openHistoryPanel();
    return;
  }
  layoutEl?.classList.toggle('history-collapsed');
}

function closeMobilePanels() {
  sidebar?.classList.remove('open');
  rightPanel?.classList.remove('open');
  updateMobileBackdrop();
}

function resetChatState() {
  messages = [];
  sessions = [];
  activeSession = null;
  if (chatMessages) chatMessages.innerHTML = '';
  localStorage.removeItem('hassan_sessions');
}

// ─── Logout ────────────────────────────────────────────────────────────────────
async function doLogout() {
  const uid = currentUser?.id;
  try { await fetch('/api/auth/logout', { method: 'POST', headers: { 'x-token': authToken } }); } catch {}
  authToken = '';
  currentUser = null;
  settings = {};
  resetChatState();
  localStorage.removeItem('hassan_token');
  if (uid) localStorage.removeItem(`hassan_settings_${uid}`);
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
    closeMobilePanels();
  });

  document.getElementById('toggle-sidebar')?.addEventListener('click', toggleSidebar);
  document.getElementById('mobile-menu-btn')?.addEventListener('click', openSidebar);
  document.getElementById('mobile-history-btn')?.addEventListener('click', openHistoryPanel);
  document.getElementById('close-history-panel')?.addEventListener('click', closeHistoryPanel);
  mobileBackdrop?.addEventListener('click', closeMobilePanels);

  document.getElementById('open-settings')?.addEventListener('click', () => {
    closeMobilePanels();
    openSettings();
  });
  document.getElementById('open-settings-top')?.addEventListener('click', openSettings);
  document.getElementById('close-settings').addEventListener('click', closeSettings);
  settingsModal.addEventListener('click', e => { if (e.target === settingsModal) closeSettings(); });
  document.getElementById('save-settings').addEventListener('click', doSaveSettings);
  document.getElementById('set-provider')?.addEventListener('change', () => {
    updateSettingsUI();
    const provider = document.getElementById('set-provider')?.value || FALLBACK_DEFAULTS.provider;
    populateModelSelect(provider, providerDefaultModel(provider));
  });
  document.getElementById('set-model')?.addEventListener('change', onModelSelectChange);

  document.getElementById('logout-btn')?.addEventListener('click', doLogout);

  document.getElementById('theme-light')?.addEventListener('click', () => applyTheme('light'));
  document.getElementById('theme-dark')?.addEventListener('click', () => applyTheme('dark'));

  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); document.getElementById('search-input')?.focus(); }
    if (e.key === 'Escape') {
      if (sidebar?.classList.contains('open') || rightPanel?.classList.contains('open')) {
        closeMobilePanels();
      } else {
        closeSettings();
      }
    }
  });

  window.addEventListener('resize', () => {
    if (!isMobileSidebar()) sidebar?.classList.remove('open');
    if (!isMobileHistory()) rightPanel?.classList.remove('open');
    updateMobileBackdrop();
  });

  document.querySelectorAll('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      item.classList.add('active');
      const view = item.dataset.view;
      if (topbarTitle) topbarTitle.textContent = item.querySelector('span').textContent.trim();
      if (view === 'history') {
        openHistoryPanel();
        closeSidebar();
      } else if (view === 'chat') {
        showWelcomeView();
        closeMobilePanels();
      } else {
        closeMobilePanels();
      }
    });
  });
}

// ─── Settings ──────────────────────────────────────────────────────────────────
async function loadModelsCatalog() {
  if (modelsCatalog) return modelsCatalog;
  try {
    const r = await fetch('/api/models');
    if (r.ok) {
      const data = await r.json();
      modelsCatalog = data.providers || data;
    }
  } catch {}
  return modelsCatalog;
}

function populateModelSelect(provider, selectedModel) {
  const sel = document.getElementById('set-model');
  const custom = document.getElementById('set-model-custom');
  if (!sel) return;

  const cat = modelsCatalog?.[provider];
  sel.innerHTML = '';

  if (!cat?.categories?.length) {
    const want = resolveModelForProvider(provider, selectedModel);
    const opt = document.createElement('option');
    opt.value = want;
    opt.textContent = want;
    sel.appendChild(opt);
    if (custom) custom.style.display = 'none';
    return;
  }

  const allIds = [];
  for (const group of cat.categories) {
    const og = document.createElement('optgroup');
    og.label = group.label || 'Models';
    for (const m of group.models || []) {
      allIds.push(m.id);
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.badge ? `${m.name} — ${m.badge}` : m.name;
      if (m.id === cat.default) opt.dataset.recommended = '1';
      og.appendChild(opt);
    }
    sel.appendChild(og);
  }

  const customOpt = document.createElement('option');
  customOpt.value = '__custom__';
  customOpt.textContent = 'Custom model ID…';
  sel.appendChild(customOpt);

  const want = resolveModelForProvider(provider, selectedModel);
  if (allIds.includes(want)) {
    sel.value = want;
    if (custom) { custom.style.display = 'none'; custom.value = ''; }
  } else if (want && want !== providerDefaultModel(provider)) {
    sel.value = '__custom__';
    if (custom) { custom.style.display = 'block'; custom.value = want; }
  } else {
    sel.value = cat.default || providerDefaultModel(provider);
    if (custom) custom.style.display = 'none';
  }
}

function onModelSelectChange() {
  const sel = document.getElementById('set-model');
  const custom = document.getElementById('set-model-custom');
  if (!sel || !custom) return;
  const isCustom = sel.value === '__custom__';
  custom.style.display = isCustom ? 'block' : 'none';
  if (isCustom && !custom.value) custom.focus();
}

function getSelectedModel() {
  const sel = document.getElementById('set-model');
  const custom = document.getElementById('set-model-custom');
  const provider = document.getElementById('set-provider')?.value || settings.provider || 'gemini';
  if (!sel) return providerDefaultModel(provider);
  if (sel.value === '__custom__') return custom?.value?.trim() || providerDefaultModel(provider);
  return sel.value?.trim() || providerDefaultModel(provider);
}

function settingsKey() {
  return currentUser?.id ? `hassan_settings_${currentUser.id}` : 'hassan_settings_guest';
}

async function refreshCurrentUser() {
  if (!authToken) return;
  try {
    const r = await fetch('/api/auth/me', { headers: { 'x-token': authToken } });
    if (r.ok) currentUser = await r.json();
  } catch {}
}

async function fetchUserSettings() {
  if (!authToken) return;
  try {
    const r = await fetch('/api/user/settings', { headers: { 'x-token': authToken } });
    if (r.ok) {
      settings = await r.json();
      await loadModelsCatalog();
      const provider = settings.provider || FALLBACK_DEFAULTS.provider;
      const resolved = resolveModelForProvider(provider, settings.model);
      if (resolved !== settings.model) {
        settings.model = resolved;
        saveSettings({ model: resolved }, !!authToken);
      }
      if (currentUser?.id) {
        localStorage.setItem(settingsKey(), JSON.stringify(settings));
      }
    }
  } catch {}
}

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
  const legacyGemini = [...GEMINI_LEGACY];
  const needsDefault = force
    || !settings.provider
    || (settings.provider === 'gemini' && legacyGemini.includes(settings.model || ''));
  if (needsDefault) {
    saveSettings({
      ...defs,
      model: defs.model || GEMINI_DEFAULT,
      api_key: settings.api_key || '',
      cursor_api_key: settings.cursor_api_key || '',
    }, !!authToken);
    applySavedSettings();
  }
}

function loadSettings() {
  if (currentUser?.id) {
    try { return JSON.parse(localStorage.getItem(settingsKey()) || '{}'); }
    catch { return {}; }
  }
  return {};
}

function saveSettings(obj, syncServer = true) {
  settings = { ...settings, ...obj };
  const provider = settings.provider || FALLBACK_DEFAULTS.provider;
  if (!settings.model || (provider === 'gemini' && GEMINI_LEGACY.has(settings.model))) {
    settings.model = resolveModelForProvider(provider, settings.model);
  }
  if (currentUser?.id) {
    localStorage.setItem(settingsKey(), JSON.stringify(settings));
  }
  if (syncServer && authToken) {
    const payload = {
      provider: settings.provider || FALLBACK_DEFAULTS.provider,
      api_key: settings.api_key || '',
      cursor_api_key: settings.cursor_api_key || '',
      model: settings.model || providerDefaultModel(provider),
      base_url: settings.base_url || '',
      theme: settings.theme || 'light',
    };
    fetch('/api/user/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'x-token': authToken },
      body: JSON.stringify(payload),
    }).catch(() => {});
  }
}

function applySavedSettings() {
  ensureDefaultSettings();
  const g = id => document.getElementById(id);
  const provider = settings.provider || FALLBACK_DEFAULTS.provider;
  const model = resolveModelForProvider(provider, settings.model);
  if (g('set-provider')) g('set-provider').value = provider;
  if (g('set-api-key')) g('set-api-key').value = settings.api_key || '';
  if (g('set-cursor-key')) g('set-cursor-key').value = settings.cursor_api_key || '';
  populateModelSelect(provider, model);
  if (g('set-base-url')) g('set-base-url').value = settings.base_url || FALLBACK_DEFAULTS.base_url;
  if (settings.theme) applyTheme(settings.theme);
  updateSettingsUI();
}

function ensureDefaultSettings() {
  if (!settings.provider) {
    settings = { ...FALLBACK_DEFAULTS, ...settings, api_key: settings.api_key || '', cursor_api_key: settings.cursor_api_key || '' };
  }
  if (settings.provider === 'gemini') {
    settings.model = resolveModelForProvider('gemini', settings.model);
  }
}

function openSettings() {
  settingsModal.classList.add('open');
  settingsStatus.textContent = '';
  settingsStatus.className = 'settings-note';
  loadModelsCatalog().then(() => {
    const provider = document.getElementById('set-provider')?.value || settings.provider || FALLBACK_DEFAULTS.provider;
    populateModelSelect(provider, resolveModelForProvider(provider, settings.model));
    updateSettingsUI();
  });
}

function closeSettings() { settingsModal.classList.remove('open'); }

function updateSettingsUI() {
  const el = document.getElementById('set-provider');
  if (!el) return;
  const row = document.getElementById('cursor-key-row');
  if (row) row.style.display = el.value === 'cursor' ? 'flex' : 'none';
  const guide = document.getElementById('gemini-guide');
  if (guide) guide.classList.toggle('open', el.value === 'gemini');
}

async function doSaveSettings() {
  const g = id => document.getElementById(id)?.value?.trim() || '';
  saveSettings({
    provider: g('set-provider'),
    api_key: g('set-api-key'),
    cursor_api_key: g('set-cursor-key'),
    model: getSelectedModel(),
    base_url: g('set-base-url'),
  }, true);
  settingsStatus.textContent = 'Settings saved for your account!';
  settingsStatus.className = 'settings-note ok';
  setTimeout(closeSettings, 900);
}

// ─── Theme ─────────────────────────────────────────────────────────────────────
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.getElementById('theme-light')?.classList.toggle('active', theme === 'light');
  document.getElementById('theme-dark')?.classList.toggle('active', theme === 'dark');
  saveSettings({ theme }, !!authToken);
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
