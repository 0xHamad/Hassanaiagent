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

function shortUa(ua) {
  if (!ua || ua === '—') return '—';
  return ua.length > 80 ? ua.slice(0, 77) + '…' : ua;
}

async function loadOverview() {
  overviewData = await api('/api/admin/overview');
  const settings = await api('/api/admin/settings');
  overviewData.signup_limit = settings.signup_limit;
  $('#stat-users').textContent = overviewData.user_count ?? 0;
  $('#stat-sessions').textContent = overviewData.session_count ?? 0;
  $('#stat-chats').textContent = overviewData.conversation_count ?? 0;
  $('#stat-msgs').textContent = overviewData.message_count ?? 0;
  const limit = settings.signup_limit ?? 0;
  const used = settings.user_count ?? overviewData.user_count ?? 0;
  $('#overview-limit-note').textContent = limit > 0
    ? `Signup limit: ${used} / ${limit} users`
    : 'Signup limit: unlimited';
  $('#signup-limit-input').value = limit;
  $('#settings-status-text').textContent = `Current: ${used} users registered`;
  renderUsersTable();
  renderSessionsTable();
  renderChatsTable();
}

function renderUsersTable() {
  const tbody = $('#users-table');
  const users = overviewData?.users || [];
  tbody.innerHTML = users.map(u => `
    <tr>
      <td><strong>${esc(u.username)}</strong><br><code class="tiny">${esc(u.id)}</code></td>
      <td>${u.is_blocked ? '<span class="badge blocked">Blocked</span>' : '<span class="badge active">Active</span>'}</td>
      <td>${u.device_count ?? 0}</td>
      <td>${u.active_sessions ?? 0}</td>
      <td>${fmtDate(u.created_at)}</td>
      <td class="actions-cell">
        <button type="button" class="link-btn" data-action="view" data-user="${esc(u.id)}">View</button>
        <button type="button" class="link-btn" data-action="password" data-user="${esc(u.id)}" data-name="${esc(u.username)}">Password</button>
        <button type="button" class="link-btn ${u.is_blocked ? '' : 'warn'}" data-action="block" data-user="${esc(u.id)}" data-blocked="${u.is_blocked ? '1' : '0'}">${u.is_blocked ? 'Unblock' : 'Block'}</button>
        <button type="button" class="link-btn danger" data-action="delete" data-user="${esc(u.id)}" data-name="${esc(u.username)}">Delete</button>
      </td>
    </tr>`).join('') || '<tr><td colspan="6">No users yet</td></tr>';

  tbody.querySelectorAll('[data-action]').forEach(btn => {
    btn.onclick = () => handleUserAction(btn);
  });
}

function renderSessionsTable() {
  const tbody = $('#sessions-table');
  const sessions = overviewData?.sessions || [];
  tbody.innerHTML = sessions.map(s => `
    <tr>
      <td><strong>${esc(s.username || '—')}</strong><br><code class="tiny">${esc(s.user_id)}</code></td>
      <td><code>${esc(s.ip_address || '—')}</code></td>
      <td title="${esc(s.user_agent || '')}">${esc(shortUa(s.user_agent))}</td>
      <td>${fmtDate(s.created_at)}</td>
      <td>${fmtDate(s.expires_at)}</td>
    </tr>`).join('') || '<tr><td colspan="5">No sessions</td></tr>';
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

async function handleUserAction(btn) {
  const userId = btn.dataset.user;
  const action = btn.dataset.action;
  if (action === 'view') return openUserDetail(userId);
  if (action === 'password') {
    const pw = prompt(`New password for ${btn.dataset.name}:`);
    if (!pw) return;
    if (pw.length < 6) { alert('Password must be at least 6 characters'); return; }
    await api(`/api/admin/users/${encodeURIComponent(userId)}/password`, {
      method: 'PATCH',
      body: JSON.stringify({ password: pw }),
    });
    alert('Password updated. User must login again.');
    return;
  }
  if (action === 'block') {
    const blocked = btn.dataset.blocked !== '1';
    const msg = blocked ? 'Block this user? They cannot login until unblocked.' : 'Unblock this user?';
    if (!confirm(msg)) return;
    await api(`/api/admin/users/${encodeURIComponent(userId)}/block`, {
      method: 'PATCH',
      body: JSON.stringify({ blocked }),
    });
    await loadOverview();
    switchView('users');
    return;
  }
  if (action === 'delete') {
    if (!confirm(`Delete user "${btn.dataset.name}" and all their data? This cannot be undone.`)) return;
    await api(`/api/admin/users/${encodeURIComponent(userId)}`, { method: 'DELETE' });
    await loadOverview();
    switchView('users');
  }
}

async function openUserDetail(userId) {
  const data = await api(`/api/admin/users/${encodeURIComponent(userId)}`);
  document.querySelectorAll('.view-panel').forEach(p => p.classList.add('hidden'));
  $('#user-detail').classList.remove('hidden');
  $('#view-title').textContent = 'User detail';
  $('#detail-username').textContent = data.user.username;
  const blocked = data.user.is_blocked;
  $('#detail-meta').textContent = `ID: ${data.user.id} · Joined ${fmtDate(data.user.created_at)} · ${data.sessions.length} session(s) · ${data.conversations.length} chat(s) · ${blocked ? 'BLOCKED' : 'Active'}`;

  $('#detail-actions').innerHTML = `
    <button type="button" class="ghost-btn" data-action="password" data-user="${esc(userId)}" data-name="${esc(data.user.username)}">Change password</button>
    <button type="button" class="ghost-btn ${blocked ? '' : 'warn'}" data-action="block" data-user="${esc(userId)}" data-blocked="${blocked ? '1' : '0'}">${blocked ? 'Unblock' : 'Block'}</button>
    <button type="button" class="ghost-btn danger" data-action="delete" data-user="${esc(userId)}" data-name="${esc(data.user.username)}">Delete account</button>
  `;
  $('#detail-actions').querySelectorAll('[data-action]').forEach(btn => {
    btn.onclick = async () => {
      await handleUserAction(btn);
      if (btn.dataset.action !== 'view') {
        const still = overviewData?.users?.find(u => u.id === userId);
        if (!still && btn.dataset.action === 'delete') {
          switchView('users');
          return;
        }
        if (still || btn.dataset.action === 'block') openUserDetail(userId);
      }
    };
  });

  const dev = data.devices || {};
  $('#detail-devices').innerHTML = `
    <h4>Devices &amp; IPs (${dev.device_count ?? 0} device(s), ${dev.active_sessions ?? 0} active session(s))</h4>
    <div class="table-wrap">
      <table>
        <thead><tr><th>IP</th><th>Browser / Device</th><th>Sessions</th><th>Last seen</th></tr></thead>
        <tbody>
          ${(dev.devices || []).map(d => `
            <tr>
              <td><code>${esc(d.ip_address)}</code></td>
              <td title="${esc(d.user_agent)}">${esc(shortUa(d.user_agent))}</td>
              <td>${d.session_count ?? 1}</td>
              <td>${fmtDate(d.last_seen)}</td>
            </tr>`).join('') || '<tr><td colspan="4">No active devices</td></tr>'}
        </tbody>
      </table>
    </div>`;

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
  const titles = {
    overview: 'Overview',
    settings: 'Signup Limits',
    users: 'All Users',
    sessions: 'Login Sessions',
    chats: 'Chat History',
  };
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
$('#save-signup-limit').onclick = async () => {
  const limit = parseInt($('#signup-limit-input').value, 10);
  if (Number.isNaN(limit) || limit < 0) { alert('Enter a valid limit (0 = unlimited)'); return; }
  const data = await api('/api/admin/settings/signup-limit', {
    method: 'POST',
    body: JSON.stringify({ limit }),
  });
  $('#settings-status-text').textContent = `Saved. ${data.user_count} users registered (limit: ${data.signup_limit}).`;
  await loadOverview();
};

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
