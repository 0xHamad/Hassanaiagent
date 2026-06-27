'use strict';

let adminToken = sessionStorage.getItem('hassan_admin_token') || '';
let overviewData = null;

const $ = (s) => document.querySelector(s);

function headers() {
  return adminToken ? { 'x-admin-token': adminToken } : {};
}

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { 'Content-Type': 'application/json', ...headers(), ...(opts.headers || {}) } });
  const text = await r.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text.slice(0, 200) }; }
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}

function showLogin() {
  $('#admin-login').classList.remove('hidden');
  $('#admin-app').classList.add('hidden');
}

function showApp() {
  $('#admin-login').classList.add('hidden');
  $('#admin-app').classList.remove('hidden');
}

function fmtDate(s) {
  if (!s) return '—';
  try { return new Date(s).toLocaleString(); } catch { return s; }
}

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function loadOverview() {
  overviewData = await api('/api/admin/overview');
  $('#stat-users').textContent = overviewData.user_count ?? 0;
  $('#stat-sessions').textContent = overviewData.session_count ?? 0;
  $('#stat-chats').textContent = overviewData.conversation_count ?? 0;
  $('#stat-msgs').textContent = overviewData.message_count ?? 0;
  renderUsersTable();
  renderSessionsTable();
  renderChatsTable();
}

function renderUsersTable() {
  const tbody = $('#users-table');
  const users = overviewData?.users || [];
  tbody.innerHTML = users.map(u => `
    <tr>
      <td><strong>${esc(u.username)}</strong></td>
      <td><code>${esc(u.id)}</code></td>
      <td>${fmtDate(u.created_at)}</td>
      <td><button type="button" class="link-btn" data-user="${esc(u.id)}">View chats</button></td>
    </tr>`).join('');
  tbody.querySelectorAll('[data-user]').forEach(btn => {
    btn.onclick = () => openUserDetail(btn.dataset.user);
  });
}

function renderSessionsTable() {
  const tbody = $('#sessions-table');
  const sessions = overviewData?.sessions || [];
  tbody.innerHTML = sessions.map(s => `
    <tr>
      <td><code>${esc(s.user_id)}</code></td>
      <td>${fmtDate(s.created_at)}</td>
      <td>${fmtDate(s.expires_at)}</td>
    </tr>`).join('') || '<tr><td colspan="3">No sessions</td></tr>';
}

function renderChatsTable() {
  const tbody = $('#chats-table');
  const convs = overviewData?.conversations || [];
  tbody.innerHTML = convs.map(c => `
    <tr>
      <td>${esc(c.title)}</td>
      <td><code>${esc(c.user_id)}</code></td>
      <td>${fmtDate(c.updated_at || c.created_at)}</td>
      <td><button type="button" class="link-btn" data-user="${esc(c.user_id)}">User</button></td>
    </tr>`).join('') || '<tr><td colspan="4">No conversations yet</td></tr>';
  tbody.querySelectorAll('[data-user]').forEach(btn => {
    btn.onclick = () => openUserDetail(btn.dataset.user);
  });
}

async function openUserDetail(userId) {
  const data = await api(`/api/admin/users/${encodeURIComponent(userId)}`);
  document.querySelectorAll('.view-panel').forEach(p => p.classList.add('hidden'));
  $('#user-detail').classList.remove('hidden');
  $('#view-title').textContent = 'User detail';
  $('#detail-username').textContent = data.user.username;
  $('#detail-meta').textContent = `ID: ${data.user.id} · Joined ${fmtDate(data.user.created_at)} · ${data.sessions.length} session(s) · ${data.conversations.length} chat(s)`;
  const box = $('#detail-chats');
  box.innerHTML = (data.conversations || []).map(conv => `
    <div class="chat-block">
      <h4>${esc(conv.title)} <span class="muted">· ${fmtDate(conv.updated_at || conv.created_at)}</span></h4>
      ${(conv.messages || []).map(m => `
        <div class="msg-line"><span class="role">${esc(m.role)}</span>${esc(m.content).slice(0, 800)}</div>
      `).join('') || '<p class="muted">No messages</p>'}
    </div>`).join('') || '<p class="muted">No chats for this user.</p>';
}

function switchView(name) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === name));
  document.querySelectorAll('.view-panel').forEach(p => p.classList.add('hidden'));
  $('#user-detail').classList.add('hidden');
  const titles = { overview: 'Overview', users: 'All Users', sessions: 'Login Sessions', chats: 'Chat History' };
  $('#view-title').textContent = titles[name] || 'Admin';
  const panel = $(`#view-${name}`);
  if (panel) panel.classList.remove('hidden');
}

$('#admin-login-btn').onclick = async () => {
  const err = $('#admin-login-error');
  err.classList.add('hidden');
  try {
    const data = await api('/api/admin/login', {
      method: 'POST',
      body: JSON.stringify({ username: $('#admin-user').value.trim(), password: $('#admin-pass').value }),
    });
    adminToken = data.token;
    sessionStorage.setItem('hassan_admin_token', adminToken);
    showApp();
    await loadOverview();
    switchView('overview');
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove('hidden');
  }
};

$('#admin-pass').addEventListener('keydown', e => { if (e.key === 'Enter') $('#admin-login-btn').click(); });
$('#admin-logout').onclick = async () => {
  try { await api('/api/admin/logout', { method: 'POST' }); } catch {}
  adminToken = '';
  sessionStorage.removeItem('hassan_admin_token');
  showLogin();
};
$('#refresh-btn').onclick = () => loadOverview().catch(e => alert(e.message));
$('#back-users').onclick = () => { switchView('users'); };

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.onclick = () => switchView(btn.dataset.view);
});

(async function boot() {
  if (adminToken) {
    try {
      await loadOverview();
      showApp();
      switchView('overview');
      return;
    } catch {
      adminToken = '';
      sessionStorage.removeItem('hassan_admin_token');
    }
  }
  showLogin();
})();
