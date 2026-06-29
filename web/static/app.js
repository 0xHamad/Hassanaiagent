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
let pendingAttachments = [];
let attachSupported = null;

const ATTACH_ICONS = {
  images: '📷', documents: '📄', code: '💻', config: '📦', spreadsheet: '📊', other: '📎',
};
const ATTACH_CLASS = {
  images: 'img', documents: 'doc', code: 'code', config: 'cfg', spreadsheet: 'sheet', other: 'doc',
};

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
const attachTray = document.getElementById('attach-tray');
const fileInput = document.getElementById('file-input');
const attachPopover = document.getElementById('attach-popover');
const inputDropZone = document.getElementById('input-drop-zone');
const platformsView = document.getElementById('platforms-view');
const platformsFeed = document.getElementById('platforms-feed');
const platformsUpdated = document.getElementById('platforms-updated');
const platformsRefresh = document.getElementById('platforms-refresh');
const inputBar = document.querySelector('.input-bar');
const newChatBtn = document.getElementById('new-chat-btn');
const SPLASH_MS = 4000;

let mainView = 'chat';
let platformsPollTimer = null;
let platformsLoading = false;

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
    checkChatStorage();
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

async function checkChatStorage() {
  try {
    const r = await fetch('/api/health');
    if (!r.ok) return;
    const h = await r.json();
    if (h.chat_storage !== 'supabase') {
      showToast(
        'Chat memory is NOT on Supabase. Fix /root/hassanaiagent/.env — paste full service_role JWT (one line).'
      );
    }
  } catch {}
}

async function newSession() {
  messages = [];
  activeSession = null;
  if (chatMessages) chatMessages.innerHTML = '';
  const r = await fetch('/api/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-token': authToken },
    body: JSON.stringify({ title: 'New Chat' }),
  });
  const data = await readJsonResponse(r);
  if (!r.ok) {
    const msg = data.detail || `Could not create chat (HTTP ${r.status})`;
    showToast(msg);
    throw new Error(msg);
  }
  const sess = { id: data.id, title: data.title || 'New Chat', messages: [] };
  sessions.unshift(sess);
  activeSession = sess;
  renderHistory();
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
  messages.forEach(m => appendMessage(m.role, m.content, false, m.attachments || []));
}

function renderAttachmentPills(items) {
  if (!items?.length) return '';
  return `<div class="msg-attachments">${items.map(a => {
    const cat = a.category || guessCategory(a.name);
    const thumb = a.preview
      ? `<img src="${a.preview}" alt="" />`
      : `<span>${ATTACH_ICONS[cat] || '📎'}</span>`;
    return `<span class="msg-attach-pill">${thumb} ${esc(a.name)}</span>`;
  }).join('')}</div>`;
}

function appendMessage(role, content, animate = true, attachments = []) {
  const row = document.createElement('div');
  row.className = `msg-row ${role}`;
  if (!animate) row.style.animation = 'none';

  const avatarHtml = role === 'user'
    ? `<div class="msg-avatar">${currentUser ? currentUser.username.charAt(0).toUpperCase() : 'U'}</div>`
    : `<div class="msg-avatar"><img src="/static/logo.jpg" alt="H" /></div>`;

  const userBody = role === 'user'
    ? `<div class="msg-bubble">${content ? esc(content).replace(/\n/g, '<br>') : ''}${renderAttachmentPills(attachments)}</div>`
    : `<div class="kimi-ai-bubble">${renderMD(content)}</div>`;

  row.innerHTML = `
    ${avatarHtml}
    <div class="msg-content">${userBody}</div>`;
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
function escHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function stopPlatformsPoll() {
  if (platformsPollTimer) {
    clearInterval(platformsPollTimer);
    platformsPollTimer = null;
  }
}

function startPlatformsPoll() {
  stopPlatformsPoll();
  platformsPollTimer = setInterval(() => fetchPlatformsLive(false), 5000);
}

function renderPlatformsFeed(data) {
  if (platformsUpdated) {
    platformsUpdated.textContent = data?.updated_at
      ? `Updated ${data.updated_at}${data.count != null ? ` · ${data.count} SMS` : ''}`
      : '—';
  }
  if (!platformsFeed) return;

  const rows = data?.messages || [];
  if (!rows.length) {
    platformsFeed.innerHTML = '<div class="platforms-empty">No live SMS right now — checking again shortly…</div>';
    return;
  }

  platformsFeed.innerHTML = rows.map(row => {
    const code = row.code
      ? `<span class="sms-code" title="OTP">${escHtml(row.code)}</span>`
      : '';
    const sms = escHtml(row.text || '');
    return `<div class="platforms-row">
      <div class="pf-cli">${escHtml(row.cli || '—')}</div>
      <div class="pf-sms">${sms}${code ? ` ${code}` : ''}</div>
      <div class="pf-time">${escHtml(row.time || '—')}</div>
    </div>`;
  }).join('');
}

async function fetchPlatformsLive(force = false) {
  if (!authToken || mainView !== 'platforms') return;
  if (platformsLoading) return;
  platformsLoading = true;
  if (platformsRefresh) platformsRefresh.disabled = true;
  try {
    const url = force ? '/api/platforms/live?force=true' : '/api/platforms/live';
    const r = await fetch(url, { headers: { 'x-token': authToken } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    renderPlatformsFeed(await r.json());
  } catch (e) {
    if (platformsFeed) {
      platformsFeed.innerHTML = `<div class="platforms-empty platforms-error">Could not load live SMS. ${escHtml(e.message)}</div>`;
    }
  } finally {
    platformsLoading = false;
    if (platformsRefresh) platformsRefresh.disabled = false;
  }
}

function setMainView(view) {
  mainView = view;
  const isPlatforms = view === 'platforms';

  platformsView?.classList.toggle('hidden', !isPlatforms);
  inputBar?.classList.toggle('hidden', isPlatforms);
  if (newChatBtn) newChatBtn.style.display = isPlatforms ? 'none' : '';

  if (isPlatforms) {
    welcomeScreen.style.display = 'none';
    chatMessages.style.display = 'none';
    if (platformsFeed && !platformsFeed.querySelector('.platforms-row')) {
      platformsFeed.innerHTML = '<div class="platforms-empty">Loading live SMS…</div>';
    }
    startPlatformsPoll();
    fetchPlatformsLive(false);
    return;
  }

  stopPlatformsPoll();
}

function showChat() {
  if (mainView !== 'chat') return;
  welcomeScreen.style.display = 'none';
  chatMessages.style.display  = 'flex';
  if (topbarTitle) topbarTitle.textContent = activeSession?.title || 'AI Chat';
}
function showWelcomeView() {
  if (mainView !== 'chat') return;
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

// ─── File attachments ─────────────────────────────────────────────────────────
function fmtFileSize(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function guessCategory(name) {
  const low = (name || '').toLowerCase();
  const dot = low.lastIndexOf('.');
  const ext = dot >= 0 ? low.slice(dot) : low;
  const cats = attachSupported?.categories || {};
  for (const [cat, exts] of Object.entries(cats)) {
    if (exts.includes(ext) || exts.includes(low.split('/').pop())) return cat;
  }
  if (['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.heic', '.heif'].includes(ext)) return 'images';
  return 'other';
}

function isFileAllowed(name) {
  const low = (name || '').toLowerCase();
  const base = low.split(/[/\\]/).pop();
  const specials = new Set([
    'docker-compose.yml', 'dockerfile', 'package.json', 'package-lock.json',
    'requirements.txt', 'pyproject.toml', 'cargo.toml', 'go.mod', 'composer.json',
    '.env', '.env.example',
  ]);
  if (specials.has(base)) return true;
  const dot = base.lastIndexOf('.');
  const ext = dot >= 0 ? base.slice(dot) : '';
  const all = new Set();
  Object.values(attachSupported?.categories || {}).forEach(arr => arr.forEach(e => all.add(e)));
  return all.has(ext);
}

async function loadAttachSupported() {
  try {
    const r = await fetch('/api/attachments/supported');
    if (r.ok) attachSupported = await r.json();
  } catch {}
  if (!attachSupported) {
    attachSupported = {
      max_files: 8, max_file_mb: 5,
      accept: '.jpg,.jpeg,.png,.webp,.pdf,.txt,.md,.py,.js,.json,.csv,.env',
      categories: {
        images: ['.jpg', '.jpeg', '.png', '.webp', '.gif'],
        documents: ['.pdf', '.txt', '.md', '.json', '.csv'],
        code: ['.py', '.js', '.ts', '.html', '.css'],
        config: ['.env', 'package.json', 'requirements.txt'],
        spreadsheet: ['.csv', '.xlsx'],
      },
    };
  }
  if (fileInput && attachSupported.accept) fileInput.accept = attachSupported.accept;
  renderAttachCategories();
}

function renderAttachCategories() {
  const box = document.getElementById('attach-categories');
  if (!box || !attachSupported?.categories) return;
  const labels = {
    images: 'Images',
    documents: 'Documents',
    code: 'Code Files',
    config: 'Config Files',
    spreadsheet: 'Spreadsheet',
  };
  box.innerHTML = Object.entries(attachSupported.categories).map(([key, exts]) => `
    <div class="attach-cat">
      <div class="attach-cat-title">${ATTACH_ICONS[key] || '📎'} ${labels[key] || key}</div>
      <div class="attach-cat-exts">${exts.join(' · ')}</div>
    </div>`).join('');
}

function toggleAttachPopover(force) {
  if (!attachPopover) return;
  const open = force !== undefined ? force : attachPopover.classList.contains('hidden');
  attachPopover.classList.toggle('hidden', !open);
}

function clearPendingAttachments() {
  pendingAttachments = [];
  renderAttachTray();
  updateSendBtn();
}

function renderAttachTray() {
  if (!attachTray) return;
  if (!pendingAttachments.length) {
    attachTray.classList.add('hidden');
    attachTray.innerHTML = '';
    return;
  }
  attachTray.classList.remove('hidden');
  attachTray.innerHTML = pendingAttachments.map((a, i) => {
    const cat = a.category || guessCategory(a.name);
    return `
    <div class="attach-chip" data-idx="${i}">
      <div class="attach-chip-icon ${ATTACH_CLASS[cat] || 'doc'}">${ATTACH_ICONS[cat] || '📎'}</div>
      <div class="attach-chip-meta">
        <span class="attach-chip-name" title="${esc(a.name)}">${esc(a.name)}</span>
        <span class="attach-chip-size">${fmtFileSize(a.size)}</span>
      </div>
      <button type="button" class="attach-chip-remove" data-remove="${i}" aria-label="Remove">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>`;
  }).join('');
  attachTray.querySelectorAll('[data-remove]').forEach(btn => {
    btn.onclick = () => {
      pendingAttachments.splice(Number(btn.dataset.remove), 1);
      renderAttachTray();
      updateSendBtn();
    };
  });
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
    reader.readAsDataURL(file);
  });
}

async function addFilesFromList(fileList) {
  const maxFiles = attachSupported?.max_files || 8;
  const maxBytes = (attachSupported?.max_file_mb || 5) * 1024 * 1024;
  const files = Array.from(fileList || []);
  if (!files.length) return;

  for (const file of files) {
    if (pendingAttachments.length >= maxFiles) {
      showToast(`Maximum ${maxFiles} files per message`);
      break;
    }
    if (!isFileAllowed(file.name)) {
      showToast(`Unsupported file: ${file.name}`);
      continue;
    }
    if (file.size > maxBytes) {
      showToast(`${file.name} exceeds ${attachSupported?.max_file_mb || 5}MB`);
      continue;
    }
    if (pendingAttachments.some(a => a.name === file.name && a.size === file.size)) continue;
    try {
      const dataUrl = await readFileAsDataUrl(file);
      const cat = guessCategory(file.name);
      const item = {
        name: file.name,
        size: file.size,
        category: cat,
        data: dataUrl,
        preview: cat === 'images' ? dataUrl : '',
      };
      pendingAttachments.push(item);
    } catch (e) {
      showToast(e.message);
    }
  }
  renderAttachTray();
  updateSendBtn();
  toggleAttachPopover(false);
}

function initAttachments() {
  loadAttachSupported();

  document.getElementById('attach-btn')?.addEventListener('click', () => toggleAttachPopover());
  document.getElementById('attach-tool-btn')?.addEventListener('click', () => toggleAttachPopover());
  document.getElementById('close-attach-popover')?.addEventListener('click', () => toggleAttachPopover(false));
  document.getElementById('pick-files-btn')?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', () => {
    addFilesFromList(fileInput.files);
    fileInput.value = '';
  });

  if (inputDropZone) {
    ['dragenter', 'dragover'].forEach(ev => {
      inputDropZone.addEventListener(ev, e => {
        e.preventDefault();
        inputDropZone.classList.add('drag-over');
      });
    });
    ['dragleave', 'drop'].forEach(ev => {
      inputDropZone.addEventListener(ev, e => {
        e.preventDefault();
        if (ev === 'dragleave') inputDropZone.classList.remove('drag-over');
      });
    });
    inputDropZone.addEventListener('drop', e => {
      inputDropZone.classList.remove('drag-over');
      addFilesFromList(e.dataTransfer?.files);
    });
  }

  document.addEventListener('click', e => {
    if (!attachPopover || attachPopover.classList.contains('hidden')) return;
    if (e.target.closest('#attach-popover') || e.target.closest('#attach-btn') || e.target.closest('#attach-tool-btn')) return;
    toggleAttachPopover(false);
  });
}

// ─── Send message ──────────────────────────────────────────────────────────────
async function sendMessage(text) {
  text = (text || userInput.value).trim();
  const files = pendingAttachments.slice();
  if ((!text && !files.length) || isLoading) return;

  if (!activeSession) await newSession();
  if (messages.length === 0) updateSessionTitle(activeSession, text || files[0]?.name || 'Attachment');

  const sentAttachments = files.map(f => ({
    name: f.name, size: f.size, category: f.category, preview: f.preview || '',
  }));
  messages.push({ role: 'user', content: text, attachments: sentAttachments });
  showChat();
  appendMessage('user', text, true, sentAttachments);
  userInput.value = '';
  userInput.style.height = 'auto';
  if (charCount) charCount.textContent = '0';
  clearPendingAttachments();
  updateSendBtn();
  renderHistory();

  isLoading = true;
  setLoading(true);
  showTyping();

  const payload = {
    message: text,
    conversation_id: activeSession?.id || '',
    attachments: files.map(f => ({ name: f.name, data: f.data, size: f.size })),
    provider: settings.provider || '',
    api_key: settings.api_key || '',
    cursor_api_key: settings.cursor_api_key || '',
    model: settings.model || '',
    base_url: settings.base_url || '',
  };

  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-token': authToken },
      body: JSON.stringify(payload),
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
  document.getElementById('attach-btn')?.toggleAttribute('disabled', on);
}
function updateSendBtn() {
  const ready = userInput.value.trim().length > 0 || pendingAttachments.length > 0;
  sendBtn.classList.toggle('active', ready);
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
  clearPendingAttachments();
  if (chatMessages) chatMessages.innerHTML = '';
  localStorage.removeItem('hassan_sessions');
}

// ─── Logout ────────────────────────────────────────────────────────────────────
async function doLogout() {
  const uid = currentUser?.id;
  stopPlatformsPoll();
  setMainView('chat');
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

  initAttachments();

  document.querySelectorAll('.quick-card').forEach(btn => {
    btn.addEventListener('click', () => sendMessage(btn.dataset.prompt));
  });

  platformsRefresh?.addEventListener('click', () => fetchPlatformsLive(true));

  document.getElementById('new-chat-btn').addEventListener('click', async () => {
    try {
      await newSession();
      showWelcomeView();
      renderHistory();
      userInput.focus();
      closeMobilePanels();
    } catch {}
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
        setMainView('chat');
        openHistoryPanel();
        closeSidebar();
      } else if (view === 'chat') {
        setMainView('chat');
        showWelcomeView();
        closeMobilePanels();
      } else if (view === 'platforms') {
        setMainView('platforms');
        closeMobilePanels();
      } else {
        setMainView('chat');
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
