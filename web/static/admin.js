'use strict';

let adminToken = sessionStorage.getItem('hassan_admin_token') || '';
let overviewData = null;
let currentUserId = null;

const $ = (s) => document.querySelector(s);

function headers() {
  return adminToken ? { 'x-admin-token': adminToken } : {};
}

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { 'Content-Type': 'application/json', ...headers(), ...(opts.headers || {}) } });
  const text = await r.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text.slice(0, 200) }; }
  if (!r.ok) {
    const detail = data.detail;
    const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg || d).join(', ') : `HTTP ${r.status}`;
    throw new Error(msg);
  }
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
  const s = String(ua || '');
  if (!s) return '—';
  if (s.length <= 48) return s;
  return s.slice(0, 45) + '…';
}

function passwordCell(pw, userId) {
  const val = pw || '';
  if (!val) return '<span class="muted">—</span>';
  return `
    <span class="pw-mask" id="pw-${esc(userId)}">••••••••</span>
    <span class="pw-plain hidden" id="pw-plain-${esc(userId)}">${esc(val)}</span>
    <button type="button" class="link-btn pw-toggle" data-pw-user="${esc(userId)}">Show</button>`;
}

function renderSignupStatus() {
  const el = $('#signup-status');
  if (!el || !overviewData) return;
  const limit = overviewData.signup_limit ?? 0;
  const total = overviewData.user_count ?? 0;
  if (limit <= 0) {
    el.innerHTML = '<span class="badge badge-open">Signups open — no limit</span>';
    return;
  }
  const remaining = overviewData.slots_remaining ?? Math.max(0, limit - total);
  if (overviewData.signup_open) {
    el.innerHTML = `<span class="badge badge-open">Signups open — ${remaining} slot(s) left (${total}/${limit})</span>`;
  } else {
    el.innerHTML = `<span class="badge badge-closed">Signup limit reached (${total}/${limit})</span>`;
  }
}

function renderSettingsPanel() {
  const input = $('#signup-limit-input');
  if (input && overviewData) input.value = overviewData.signup_limit ?? 0;
}

async function loadOverview() {
  overviewData = await api('/api/admin/overview');
  $('#stat-users').textContent = overviewData.user_count ?? 0;
  $('#stat-sessions').textContent = overviewData.session_count ?? 0;
  $('#stat-blocked').textContent = overviewData.blocked_count ?? 0;
  $('#stat-chats').textContent = overviewData.conversation_count ?? 0;
  $('#stat-msgs').textContent = overviewData.message_count ?? 0;
  renderSignupStatus();
  renderSettingsPanel();
  renderUsersTable();
  renderSessionsTable();
  renderChatsTable();
}

function renderUsersTable() {
  const tbody = $('#users-table');
  const users = overviewData?.users || [];
  tbody.innerHTML = users.map(u => {
    const blocked = u.is_blocked;
    const status = blocked
      ? '<span class="badge badge-blocked">Blocked</span>'
      : '<span class="badge badge-active">Active</span>';
    const devices = u.device_count ?? 0;
    return `
    <tr class="${blocked ? 'row-blocked' : ''}">
      <td><strong>${esc(u.username)}</strong><br><code class="tiny">${esc(u.id)}</code></td>
      <td class="pw-cell">${passwordCell(u.password_plain, u.id)}</td>
      <td>${status}</td>
      <td>${devices}</td>
      <td>${fmtDate(u.created_at)}</td>
      <td class="actions-cell">
        <button type="button" class="link-btn" data-action="view" data-user="${esc(u.id)}">View</button>
        ${blocked
          ? `<button type="button" class="link-btn btn-unblock" data-action="unblock" data-user="${esc(u.id)}">Unblock</button>`
          : `<button type="button" class="link-btn btn-block" data-action="block" data-user="${esc(u.id)}">Block</button>`}
        <button type="button" class="link-btn btn-danger" data-action="delete" data-user="${esc(u.id)}">Delete</button>
      </td>
    </tr>`;
  }).join('') || '<tr><td colspan="6">No users yet</td></tr>';

  tbody.querySelectorAll('[data-action]').forEach(btn => {
    btn.onclick = () => handleUserAction(btn.dataset.action, btn.dataset.user);
  });
  tbody.querySelectorAll('.pw-toggle').forEach(btn => {
    btn.onclick = () => {
      const uid = btn.dataset.pwUser;
      const mask = document.getElementById(`pw-${uid}`);
      const plain = document.getElementById(`pw-plain-${uid}`);
      if (!mask || !plain) return;
      const showing = !plain.classList.contains('hidden');
      plain.classList.toggle('hidden', showing);
      mask.classList.toggle('hidden', !showing);
      btn.textContent = showing ? 'Show' : 'Hide';
    };
  });
}

async function handleUserAction(action, userId) {
  if (action === 'view') {
    await openUserDetail(userId);
    return;
  }
  if (action === 'block') {
    if (!confirm('Block this account? User will be logged out.')) return;
    await api(`/api/admin/users/${encodeURIComponent(userId)}/block`, { method: 'POST' });
    await loadOverview();
    if (currentUserId === userId) await openUserDetail(userId);
    return;
  }
  if (action === 'unblock') {
    await api(`/api/admin/users/${encodeURIComponent(userId)}/unblock`, { method: 'POST' });
    await loadOverview();
    if (currentUserId === userId) await openUserDetail(userId);
    return;
  }
  if (action === 'delete') {
    if (!confirm('Delete this user permanently? All chats will be removed.')) return;
    await api(`/api/admin/users/${encodeURIComponent(userId)}`, { method: 'DELETE' });
    currentUserId = null;
    switchView('users');
    await loadOverview();
  }
}

function renderSessionsTable() {
  const tbody = $('#sessions-table');
  const sessions = overviewData?.sessions || [];
  tbody.innerHTML = sessions.map(s => `
    <tr>
      <td><code>${esc(s.user_id)}</code></td>
      <td><code>${esc(s.ip_address || '—')}</code></td>
      <td title="${esc(s.user_agent)}">${esc(shortUa(s.user_agent))}</td>
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

function renderDetailActions(user) {
  const box = $('#detail-actions');
  const blocked = user.is_blocked;
  box.innerHTML = `
    <div class="action-bar">
      ${blocked
        ? `<button type="button" class="action-btn btn-unblock" id="detail-unblock">Unblock account</button>`
        : `<button type="button" class="action-btn btn-block" id="detail-block">Block account</button>`}
      <button type="button" class="action-btn" id="detail-password">Reset password</button>
      <button type="button" class="action-btn btn-danger" id="detail-delete">Delete account</button>
    </div>`;

  $('#detail-block')?.addEventListener('click', async () => {
    if (!confirm('Block this account?')) return;
    await api(`/api/admin/users/${encodeURIComponent(user.id)}/block`, { method: 'POST' });
    await loadOverview();
    await openUserDetail(user.id);
  });
  $('#detail-unblock')?.addEventListener('click', async () => {
    await api(`/api/admin/users/${encodeURIComponent(user.id)}/unblock`, { method: 'POST' });
    await loadOverview();
    await openUserDetail(user.id);
  });
  $('#detail-password')?.addEventListener('click', async () => {
    const pw = prompt('New password (min 6 characters):');
    if (!pw) return;
    if (pw.length < 6) { alert('Password must be at least 6 characters'); return; }
    await api(`/api/admin/users/${encodeURIComponent(user.id)}/password`, {
      method: 'POST',
      body: JSON.stringify({ password: pw }),
    });
    alert('Password updated. User must log in again.');
  });
  $('#detail-delete')?.addEventListener('click', async () => {
    if (!confirm('Delete this user permanently?')) return;
    await api(`/api/admin/users/${encodeURIComponent(user.id)}`, { method: 'DELETE' });
    currentUserId = null;
    switchView('users');
    await loadOverview();
  });
}

async function openUserDetail(userId) {
  currentUserId = userId;
  const data = await api(`/api/admin/users/${encodeURIComponent(userId)}`);
  document.querySelectorAll('.view-panel').forEach(p => p.classList.add('hidden'));
  $('#user-detail').classList.remove('hidden');
  $('#view-title').textContent = 'User detail';

  const user = data.user;
  const blocked = user.is_blocked;
  $('#detail-username').textContent = user.username + (blocked ? ' (Blocked)' : '');
  $('#detail-meta').textContent =
    `Username: ${user.username} · Password: ${data.user.password_plain || '— (older account)'} · ID: ${user.id} · Joined ${fmtDate(user.created_at)} · ${data.device_count ?? data.sessions?.length ?? 0} device(s) · ${data.conversations?.length ?? 0} chat(s)`;

  const ips = data.ip_addresses || [];
  $('#detail-ips').innerHTML = ips.length
    ? `<div class="ip-list"><strong>IP addresses:</strong> ${ips.map(ip => `<code>${esc(ip)}</code>`).join(' ')}</div>`
    : '<p class="muted">No IP addresses recorded yet.</p>';

  if (data.sessions?.length) {
    $('#detail-ips').innerHTML += `
      <div class="session-list">
        <strong>Active sessions</strong>
        <table class="mini-table">
          <thead><tr><th>IP</th><th>Device</th><th>Since</th></tr></thead>
          <tbody>
            ${data.sessions.map(s => `
              <tr>
                <td><code>${esc(s.ip_address || '—')}</code></td>
                <td title="${esc(s.user_agent)}">${esc(shortUa(s.user_agent))}</td>
                <td>${fmtDate(s.created_at)}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }

  renderDetailActions(user);

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
    settings: 'Settings',
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

$('#back-users').onclick = () => { currentUserId = null; switchView('users'); };

$('#save-signup-limit').onclick = async () => {
  const msg = $('#signup-limit-msg');
  try {
    const limit = parseInt($('#signup-limit-input').value, 10);
    const data = await api('/api/admin/settings/signup-limit', {
      method: 'POST',
      body: JSON.stringify({ limit: Number.isFinite(limit) ? limit : 0 }),
    });
    overviewData = { ...overviewData, ...data };
    renderSignupStatus();
    msg.textContent = 'Signup limit saved.';
    msg.classList.remove('err');
  } catch (e) {
    msg.textContent = e.message;
    msg.classList.add('err');
  }
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
