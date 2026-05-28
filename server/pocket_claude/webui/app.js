// =====================================================================
// Pocket Claude Web-UI v2 — vanilla JS, neue DOM-Struktur.
// =====================================================================
// PC_SSE LOAD MARKER — bump this any time you change PC_SSE logging.
// If you don't see this exact line in the console after reload, the
// browser served a cached app.js.
console.log('PC_SSE: app.js LOADED build=2026-05-26-tracker');
// i18n helper — short alias for the global translator.
const t = (k, ...args) => (window.PocketI18n ? window.PocketI18n.t(k, ...args) : k);

const LS = {
  url:        'pc.serverUrl',
  token:      'pc.serverToken',
  theme:      'pc.theme',
  effort:     'pc.effort',
  lastCid:    'pc.lastCid',
  spMode:     'pc.spMode',
  spCustom:   'pc.spCustom',
  ttsVoice:   'pc.ttsVoice',
  ttsSpeed:   'pc.ttsSpeed',
  sidebar:    'pc.sidebarCollapsed',
  // Lange User-Messages einklappen (ChatGPT-Style). Default: AN. Tap auf die
  // Bubble klappt sie auf / „Mehr anzeigen"-Button.
  collapseUserMsgs: 'pc.collapseUserMsgs',
};

const state = {
  serverUrl: localStorage.getItem(LS.url)        || '',
  token:     localStorage.getItem(LS.token)      || '',
  effort:    localStorage.getItem(LS.effort)     || 'high',
  spMode:    localStorage.getItem(LS.spMode)     || 'STANDARD',
  spCustom:  localStorage.getItem(LS.spCustom)   || '',
  // Default-Voice ist Cloud-TTS Studio-B (deutsch, männlich, premium). Mit
  // Default-Provider Cloud-TTS = 1 Mio Zeichen/Monat gratis bei Privatnutzung.
  ttsVoice:  localStorage.getItem(LS.ttsVoice)   || 'de-DE-Studio-B',
  ttsSpeed:  parseFloat(localStorage.getItem(LS.ttsSpeed) || '1.0'),
  // Long-User-Message-Collapse: Default true, kann in Settings abgeschaltet werden.
  collapseUserMsgs: (localStorage.getItem(LS.collapseUserMsgs) ?? 'true') !== 'false',

  me: null,  // { id, name, is_admin } — vom Server nach Login

  cid:            null,
  title:          'Pocket Claude',
  pinned:         false,
  messages:       [],
  streamingText:  '',
  isStreaming:    false,
  pendingAttach:  [],
  audio:          { msgId: null, playing: false },
  abort:          null,
  _ttsLoaded:     false,
  _allCids:       [],
};

// =========================================================
// DOM-Refs
// =========================================================
const $ = (id) => document.getElementById(id);
const els = {
  login:        $('login'),
  app:          $('app'),
  sidebar:      $('sidebar'),
  chatNav:      $('chat-nav'),
  searchNav:    $('search-nav'),
  searchInput:  $('search-input'),
  newChatBtn:   $('new-chat-btn'),
  settingsBtn:  $('settings-btn'),
  themeToggle:  $('theme-toggle'),
  logoutBtn:    $('logout-btn'),
  sidebarToggle: $('sidebar-toggle'),
  topbarTitle:  $('chat-title'),
  topbarMeta:   $('chat-meta'),
  messages:     $('messages'),
  effortBtn:    $('effort-btn'),
  effortLabel:  $('effort-label'),
  effortMenu:   $('effort-menu'),
  moreBtn:      $('more-btn'),
  moreMenu:     $('more-menu'),
  pinLabel:     $('pin-label'),
  inputForm:    $('input-form'),
  input:        $('input'),
  sendBtn:      $('send-btn'),
  attachBtn:    $('attach-btn'),
  fileInput:    $('file-input'),
  pendingWrap:  $('pending-attachments'),
  audio:        $('audio-player'),
  settingsModal: $('settings-modal'),
  settingsClose: $('settings-close'),
  ttsProvider:      $('tts-provider'),
  ttsProviderHint:  $('tts-provider-hint'),
  ttsVoice:     $('tts-voice'),
  ttsSpeed:     $('tts-speed'),
  ttsSpeedLabel: $('tts-speed-label'),
  spCustom:     $('sp-custom'),
  backupExport: $('backup-export-btn'),
  backupImport: $('backup-import-btn'),
  backupFileInput: $('backup-file-input'),
  backupStatus: $('backup-status'),
  promptModal:  $('prompt-modal'),
  promptTitle:  $('prompt-title'),
  promptText:   $('prompt-text'),
  promptInput:  $('prompt-input'),
  promptOk:     $('prompt-ok'),
  promptCancel: $('prompt-cancel'),
  toast:        $('toast'),
};

// =========================================================
// Theme
// =========================================================
function applyTheme() {
  const saved = localStorage.getItem(LS.theme);
  if (saved === 'light' || saved === 'dark') {
    document.documentElement.dataset.theme = saved;
  } else {
    delete document.documentElement.dataset.theme;
  }
  updateThemeIcon();
}
function updateThemeIcon() {
  const isDark = document.documentElement.dataset.theme === 'dark' ||
    (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
  const icon = els.themeToggle.querySelector('use');
  icon.setAttribute('href', isDark ? '#icon-sun' : '#icon-moon');
}
els.themeToggle.addEventListener('click', () => {
  const current = document.documentElement.dataset.theme;
  const next = current === 'dark' ? 'light' : current === 'light' ? 'dark' : 'light';
  document.documentElement.dataset.theme = next;
  localStorage.setItem(LS.theme, next);
  updateThemeIcon();
  queueSettingsPush();
});
matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', updateThemeIcon);
applyTheme();

// =========================================================
// Toast
// =========================================================
let toastTimer;
function toast(msg, opts = {}) {
  els.toast.textContent = msg;
  els.toast.className = 'toast' + (opts.error ? ' error' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.add('hidden'), opts.duration || 3000);
}

// =========================================================
// Markdown
// =========================================================
marked.setOptions({ breaks: true, gfm: true });
function renderMarkdown(text) {
  if (!text) return '';
  return DOMPurify.sanitize(marked.parse(text), { ADD_ATTR: ['target'] });
}

/** Findet alle <pre><code>…</code></pre>-Blöcke in `root` und packt
 *  Header (Sprache + Copy-Button) drüber. Wird nach jedem Render aufgerufen. */
function enhanceCodeBlocks(root) {
  for (const pre of root.querySelectorAll('pre')) {
    if (pre.parentElement?.classList.contains('codeblock')) continue;  // schon dekoriert
    const code = pre.querySelector('code');
    if (!code) continue;
    // Sprache aus class="language-xyz" rausziehen
    let lang = '';
    for (const cls of code.classList) {
      if (cls.startsWith('language-')) { lang = cls.slice(9); break; }
    }
    const wrap = document.createElement('div');
    wrap.className = 'codeblock';
    const header = document.createElement('div');
    header.className = 'codeblock-header';
    header.innerHTML = `
      <span class="codeblock-lang">${escapeHtml(lang || 'code')}</span>
      <button type="button" class="codeblock-copy" title="${escapeHtml(t('copy_title'))}">
        <svg class="icon icon-sm"><use href="#icon-copy"/></svg>
        <span>${escapeHtml(t('copy'))}</span>
      </button>`;
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(header);
    wrap.appendChild(pre);
    header.querySelector('.codeblock-copy').addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(code.textContent || '');
        const lbl = header.querySelector('.codeblock-copy span');
        const old = lbl.textContent;
        lbl.textContent = t('toast_copied');
        setTimeout(() => lbl.textContent = old, 1200);
      } catch {
        toast(t('toast_copy_failed'), { error: true });
      }
    });
  }
}
function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[m]));
}

// =========================================================
// API
// =========================================================
class ApiError extends Error {
  constructor(status, body) { super(`HTTP ${status}: ${body}`); this.status = status; this.body = body; }
}
async function api(method, path, body, opts = {}) {
  const url = state.serverUrl + path;
  const headers = { 'Authorization': 'Bearer ' + state.token };
  let bodyData = body;
  if (body && !(body instanceof FormData) && !(body instanceof Blob)) {
    headers['Content-Type'] = 'application/json';
    bodyData = JSON.stringify(body);
  }
  const resp = await fetch(url, { method, headers, body: bodyData, ...opts });
  if (!resp.ok) {
    const txt = await resp.text().catch(() => '');
    throw new ApiError(resp.status, txt || resp.statusText);
  }
  if (resp.status === 204) return null;
  const ct = resp.headers.get('content-type') || '';
  return ct.includes('application/json') ? resp.json() : resp.text();
}

// =========================================================
// Login (Username + Passwort) → erstellt Server-Session, Token in localStorage
// =========================================================
$('login-form').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const url = $('login-url').value.trim().replace(/\/+$/, '');
  const username = $('login-username').value.trim();
  const password = $('login-password').value;
  const $st = $('login-status');
  if (!url || !username || !password) {
    $st.className = 'login-status error';
    $st.textContent = t('login_url_required');
    return;
  }
  $st.className = 'login-status';
  $st.textContent = t('login_signing_in');
  try {
    const resp = await fetch(url + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (resp.status === 401) throw new Error(t('login_bad_credentials'));
    if (!resp.ok) {
      const txt = await resp.text().catch(() => '');
      throw new Error('HTTP ' + resp.status + ': ' + txt.slice(0, 200));
    }
    const data = await resp.json();
    state.serverUrl = url;
    state.token     = data.token;
    state.me        = data.user;
    localStorage.setItem(LS.url, url);
    localStorage.setItem(LS.token, data.token);
    $st.className = 'login-status ok';
    $st.textContent = t('login_signed_in');
    // Forced-Password-Change: vor dem Öffnen der App den PW-Change-Modal zeigen
    if (data.user && data.user.must_change_password) {
      $('login-password').value = '';
      openPasswordChange({ forced: true });
    } else {
      setTimeout(showApp, 150);
    }
  } catch (e) {
    $st.className = 'login-status error';
    $st.textContent = t('login_failed', e.message);
  }
});

els.logoutBtn.addEventListener('click', async () => {
  if (!confirm(t('confirm_logout_session'))) return;
  // Server-seitig die Session beenden (best effort — funktioniert nicht immer
  // wenn der Token bereits ungültig ist, dann reicht der lokale Cleanup)
  try { await api('POST', '/auth/logout'); } catch (_) {}
  localStorage.removeItem(LS.token);
  state.token = '';
  state.cid = null;
  location.reload();
});

// =========================================================
// Password-Change-Modal (forced nach Login wenn must_change_password,
// oder via Settings → „Passwort ändern")
// =========================================================
let _pwChangeForced = false;
function openPasswordChange({ forced = false } = {}) {
  _pwChangeForced = !!forced;
  const modal = $('pwchange-modal');
  $('pwchange-title').textContent = forced ? t('pwchange_title_set_now') : t('change_password');
  $('pwchange-text').textContent = forced
    ? t('pwchange_text_forced')
    : t('pwchange_text_normal');
  // Altes-Passwort-Feld nur bei normaler Änderung anzeigen
  $('pwchange-old-field').style.display = forced ? 'none' : '';
  $('pwchange-old').value  = '';
  $('pwchange-new').value  = '';
  $('pwchange-new2').value = '';
  $('pwchange-cancel').style.display = forced ? 'none' : '';
  $('pwchange-status').textContent = '';
  $('pwchange-status').className = 'login-status';
  modal.classList.remove('hidden');
  setTimeout(() => ($(forced ? 'pwchange-new' : 'pwchange-old')).focus(), 100);
}
function closePasswordChange() {
  $('pwchange-modal').classList.add('hidden');
}
$('pwchange-cancel').addEventListener('click', () => { if (!_pwChangeForced) closePasswordChange(); });
$('pwchange-form').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const oldPw = $('pwchange-old').value;
  const newPw = $('pwchange-new').value;
  const newPw2 = $('pwchange-new2').value;
  const $st = $('pwchange-status');
  if (newPw.length < 8) {
    $st.className = 'login-status error'; $st.textContent = t('pwchange_min_chars'); return;
  }
  if (newPw !== newPw2) {
    $st.className = 'login-status error'; $st.textContent = t('pwchange_mismatch'); return;
  }
  $st.className = 'login-status'; $st.textContent = t('pwchange_saving');
  try {
    const body = _pwChangeForced
      ? { new_password: newPw }
      : { old_password: oldPw, new_password: newPw };
    await api('POST', '/auth/change-password', body);
    $st.className = 'login-status ok'; $st.textContent = t('pwchange_done');
    if (state.me) state.me.must_change_password = false;
    setTimeout(() => {
      closePasswordChange();
      if (_pwChangeForced) {
        _pwChangeForced = false;
        showApp();
      } else {
        toast(t('toast_password_changed'));
      }
    }, 250);
  } catch (e) {
    $st.className = 'login-status error';
    $st.textContent = t('pwchange_error_prefix', e.message);
  }
});

// =========================================================
// Server-Side UI-Settings — werden auf dem Mini-PC persistiert, damit
// jeder Browser/Gerät dieselben Settings sieht. Lokales localStorage bleibt
// als Cache + Pre-Login-Fallback.
// =========================================================
const SERVER_SETTING_KEYS = ['theme', 'effort', 'spMode', 'spCustom', 'ttsVoice', 'ttsSpeed', 'sidebar'];
let _settingsPushTimer = null;

async function loadServerSettings() {
  try {
    const resp = await api('GET', '/ui-settings');
    const s = resp.settings || {};
    // Lokale Werte mit Server-Werten überschreiben
    if (s.theme === 'light' || s.theme === 'dark') {
      localStorage.setItem(LS.theme, s.theme);
      document.documentElement.dataset.theme = s.theme;
      updateThemeIcon();
    }
    if (s.effort)    { localStorage.setItem(LS.effort, s.effort);     state.effort = s.effort; }
    if (s.spMode)    { localStorage.setItem(LS.spMode, s.spMode);     state.spMode = s.spMode; }
    if (s.spCustom !== undefined) { localStorage.setItem(LS.spCustom, s.spCustom); state.spCustom = s.spCustom; }
    if (s.ttsVoice)  { localStorage.setItem(LS.ttsVoice, s.ttsVoice); state.ttsVoice = s.ttsVoice; }
    if (s.ttsSpeed)  { localStorage.setItem(LS.ttsSpeed, s.ttsSpeed); state.ttsSpeed = parseFloat(s.ttsSpeed); }
    if (s.sidebar)   {
      localStorage.setItem(LS.sidebar, s.sidebar);
      if (s.sidebar === '1' && !matchMedia('(max-width: 768px)').matches) {
        els.app.classList.add('sidebar-collapsed');
      }
    }
  } catch (e) {
    // Server kann älter sein und den Endpoint nicht haben — nicht fatal
    console.log('Server-Settings nicht abrufbar:', e.message);
  }
}

function queueSettingsPush() {
  // Debounce: bei mehreren Änderungen kurz hintereinander nur einmal pushen
  clearTimeout(_settingsPushTimer);
  _settingsPushTimer = setTimeout(pushSettingsToServer, 600);
}

async function pushSettingsToServer() {
  const payload = {
    theme:    localStorage.getItem(LS.theme) || '',
    effort:   state.effort,
    spMode:   state.spMode,
    spCustom: state.spCustom,
    ttsVoice: state.ttsVoice,
    ttsSpeed: state.ttsSpeed.toString(),
    sidebar:  localStorage.getItem(LS.sidebar) || '0',
  };
  try { await api('PUT', '/ui-settings', payload); }
  catch (e) { console.log('Settings-Push fehlgeschlagen:', e.message); }
}

// =========================================================
// Bootstrap
// =========================================================
function cidFromHash() {
  // #/chat/abc-123 → "abc-123"
  const m = location.hash.match(/^#\/chat\/([^/?]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

async function showApp() {
  els.login.classList.add('hidden');
  els.app.classList.remove('hidden');
  // /me holen — User-Identität, Admin-Flag (steuert Sichtbarkeit der
  // Admin-Sections)
  try {
    state.me = await api('GET', '/me');
    renderFooterUser();
    applyAdminVisibility();
  } catch (e) {
    state.me = null;
  }
  // Server-Settings holen (überschreibt lokales), dann UI initialisieren
  await loadServerSettings();
  setEffort(state.effort, /*persist*/false);
  refreshChatList().then(() => {
    // Cleaner Link öffnet immer einen neuen Chat (wie ChatGPT/Gemini Web).
    // Vergangene Chats bleiben über die Sidebar erreichbar.
    // Nur wenn ein konkreter Chat im URL-Hash steht (#/chat/<cid>), wird der geladen.
    const fromHash = cidFromHash();
    if (fromHash && state._allCids.includes(fromHash)) {
      openChat(fromHash, { fromHash: true });
    } else {
      newChat();
    }
  });
}

// Browser-Back/Forward: Hash ändert sich → entsprechenden Chat öffnen
window.addEventListener('hashchange', () => {
  const cid = cidFromHash();
  if (cid && cid !== state.cid && state._allCids.includes(cid)) {
    openChat(cid, { fromHash: true });
  }
});
function showLogin() {
  $('login-url').value = state.serverUrl;
  els.login.classList.remove('hidden');
  els.app.classList.add('hidden');
}
if (state.serverUrl && state.token) showApp(); else showLogin();

// =========================================================
// Chat-Liste — gruppiert nach Datum
// =========================================================
async function refreshChatList() {
  try {
    const list = await api('GET', '/conversations');
    state._allCids = list.map(c => c.id);
    renderChatList(list);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return showLogin();
    toast(t('toast_list_failed', e.message), { error: true });
  }
}

function relativeDateGroup(iso) {
  const d = new Date(iso);
  const today = new Date(); today.setHours(0,0,0,0);
  const dDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diff = Math.round((today - dDay) / 86400000);
  if (diff <= 0) return t('group_today');
  if (diff === 1) return t('group_yesterday');
  if (diff < 7) return t('group_this_week');
  if (diff < 30) return t('group_last_30_days');
  return t('group_older');
}

function renderChatList(items) {
  // Sortieren: pinned zuerst (eigene Gruppe), Rest nach last_message_at
  items.sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    const ta = a.last_message_at || a.created_at;
    const tb = b.last_message_at || b.created_at;
    return tb.localeCompare(ta);
  });
  els.chatNav.innerHTML = '';
  if (!items.length) {
    els.chatNav.innerHTML = `<div class="empty-chats">${t('no_chats_yet')}</div>`;
    return;
  }

  // Gruppen aufbauen
  const groups = new Map();
  const pinned = items.filter(c => c.pinned);
  const others = items.filter(c => !c.pinned);
  if (pinned.length) groups.set(t('pinned_group'), pinned);
  for (const c of others) {
    const key = relativeDateGroup(c.last_message_at || c.created_at);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(c);
  }

  for (const [label, chats] of groups) {
    const grp = document.createElement('div');
    grp.className = 'chat-nav-group';
    const h = document.createElement('div');
    h.className = 'chat-nav-label';
    h.textContent = label;
    grp.appendChild(h);
    for (const c of chats) {
      const li = document.createElement('div');
      li.className = 'chat-item' + (c.id === state.cid ? ' active' : '');
      li.dataset.cid = c.id;
      li.innerHTML = `
        <span class="title">${escapeHtml(c.title || t('no_title'))}</span>
        <button class="chat-row-more" type="button" aria-label="${escapeHtml(t('more'))}"
                title="${escapeHtml(t('more'))}">
          <svg><use href="#icon-more"/></svg>
        </button>
      `;
      // Row click → open; "..." click → menu (stopPropagation prevents both)
      li.addEventListener('click', () => openChat(c.id));
      const moreBtn = li.querySelector('.chat-row-more');
      moreBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openChatRowMenu(li, c);
      });
      grp.appendChild(li);
    }
    els.chatNav.appendChild(grp);
  }
}

// =========================================================
// Per-chat row menu (Rename / Pin / Delete)
// =========================================================
let openMenu = null;

function closeChatRowMenu() {
  if (openMenu) {
    openMenu.remove();
    openMenu = null;
  }
  document.querySelectorAll('.chat-item.menu-open').forEach(el => el.classList.remove('menu-open'));
}

function openChatRowMenu(rowEl, chat) {
  closeChatRowMenu();
  rowEl.classList.add('menu-open');

  const menu = document.createElement('div');
  menu.className = 'chat-row-menu';
  menu.innerHTML = `
    <button data-act="rename" type="button">
      <svg><use href="#icon-edit"/></svg> ${escapeHtml(t('rename'))}
    </button>
    <button data-act="pin" type="button">
      <svg><use href="#icon-pin"/></svg> ${escapeHtml(chat.pinned ? t('unpin') : t('pin'))}
    </button>
    <hr>
    <button data-act="delete" class="danger" type="button">
      <svg><use href="#icon-trash"/></svg> ${escapeHtml(t('delete'))}
    </button>
  `;
  // Stop click-through so the row click doesn't fire while the menu is open
  menu.addEventListener('click', e => e.stopPropagation());
  document.body.appendChild(menu);

  // Position next to the "..." trigger
  const btn = rowEl.querySelector('.chat-row-more');
  const rect = btn.getBoundingClientRect();
  const menuW = 180;
  let left = rect.right + 6;
  if (left + menuW > window.innerWidth - 8) left = rect.left - menuW - 6;
  menu.style.left = Math.max(8, left) + 'px';
  menu.style.top = Math.min(rect.bottom + 4, window.innerHeight - 180) + 'px';

  // Wire actions
  menu.querySelector('[data-act="rename"]').addEventListener('click', async () => {
    closeChatRowMenu();
    const next = window.prompt(t('rename'), chat.title || '');
    if (next === null) return;
    const trimmed = next.trim();
    if (!trimmed || trimmed === chat.title) return;
    try {
      await api('PATCH', '/conversations/' + chat.id, { title: trimmed });
      await refreshChatList();
      if (state.cid === chat.id) {
        els.chatTitle.textContent = trimmed;
      }
    } catch (e) {
      toast(t('toast_error_prefix', e.message), { error: true });
    }
  });

  menu.querySelector('[data-act="pin"]').addEventListener('click', async () => {
    closeChatRowMenu();
    try {
      const next = !chat.pinned;
      await api('PATCH', '/conversations/' + chat.id, { pinned: next });
      if (state.cid === chat.id) state.pinned = next;
      await refreshChatList();
    } catch (e) {
      toast(t('toast_error_prefix', e.message), { error: true });
    }
  });

  menu.querySelector('[data-act="delete"]').addEventListener('click', async () => {
    closeChatRowMenu();
    if (!window.confirm(t('confirm_delete_chat', chat.title || t('no_title')))) return;
    try {
      await api('DELETE', '/conversations/' + chat.id);
      // If the deleted chat was open, drop the active chat
      if (state.cid === chat.id) {
        state.cid = null;
        state.pinned = false;
        els.messages.innerHTML = '';
        els.chatTitle.textContent = t('app_name');
      }
      await refreshChatList();
    } catch (e) {
      toast(t('toast_error_prefix', e.message), { error: true });
    }
  });

  openMenu = menu;
}

// Click anywhere else → close
document.addEventListener('click', (e) => {
  if (openMenu && !openMenu.contains(e.target)) closeChatRowMenu();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeChatRowMenu();
});
window.addEventListener('resize', closeChatRowMenu);
els.chatNav.addEventListener('scroll', closeChatRowMenu, { passive: true });

// =========================================================
// Suche
// =========================================================
let searchTimer;
els.searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  const q = els.searchInput.value.trim();
  if (!q) {
    els.searchNav.classList.add('hidden');
    els.chatNav.classList.remove('hidden');
    return;
  }
  searchTimer = setTimeout(() => doSearch(q), 250);
});

async function doSearch(q) {
  try {
    const res = await api('GET', '/search?q=' + encodeURIComponent(q));
    els.searchNav.innerHTML = '';
    if (!res.hits.length) {
      els.searchNav.innerHTML = `<div class="empty-chats">${t('no_search_results', escapeHtml(q))}</div>`;
    } else {
      for (const h of res.hits) {
        const li = document.createElement('div');
        li.className = 'chat-item search-hit';
        const snippet = h.snippet.replace(/\[\[([^\]]+)\]\]/g, '<b>$1</b>');
        li.innerHTML = `
          <span class="title">${escapeHtml(h.conversation_title)}</span>
          <span class="snippet">${snippet}</span>
        `;
        li.addEventListener('click', () => {
          openChat(h.conversation_id);
          els.searchInput.value = '';
          els.searchNav.classList.add('hidden');
          els.chatNav.classList.remove('hidden');
        });
        els.searchNav.appendChild(li);
      }
    }
    els.searchNav.classList.remove('hidden');
    els.chatNav.classList.add('hidden');
  } catch (e) {
    toast(t('toast_search_failed', e.message), { error: true });
  }
}

// =========================================================
// Chat-Aktionen
// =========================================================
async function openChat(cid, opts = {}) {
  if (state.cid === cid && !state.isStreaming) {
    els.sidebar.classList.remove('open');
    return;
  }
  abortStream();
  // Voice-Cleanup beim Chat-Wechsel — sonst hängt eine laufende Aufnahme
  // bzw. ein Auto-Mode-Loop weiter aus dem alten Chat. Audio (TTS-Playback)
  // ebenfalls stoppen, sonst spielt's beim Switch weiter.
  if (window.PocketVoice) {
    try { window.PocketVoice.resetForChatSwitch(); } catch (_) {}
  }
  document.querySelectorAll('audio').forEach((a) => {
    try { a.pause(); a.currentTime = 0; } catch (_) {}
  });
  state.cid = cid;
  localStorage.setItem(LS.lastCid, cid);
  // URL aktualisieren — bei direkter Navigation oder beim Stellen einer
  // neuen Chat-ID. Wir nutzen Hash-Routing damit kein Server-Side-Rewrite
  // nötig ist (alle Static-Routes liefern weiter die index.html).
  if (!opts.fromHash) {
    const wantedHash = '#/chat/' + cid;
    if (location.hash !== wantedHash) {
      history.replaceState(null, '', wantedHash);
    }
  }
  document.querySelectorAll('.chat-item').forEach(el => {
    el.classList.toggle('active', el.dataset.cid === cid);
  });
  els.sidebar.classList.remove('open');
  try {
    const detail = await api('GET', '/conversations/' + cid);
    state.title = detail.title;
    state.pinned = detail.pinned;
    state.messages = detail.messages || [];
    state.streamingText = '';
    state.isStreaming = false;
    updateTopbar(detail.total_tokens || 0);
    renderMessages();
    scrollToVeryBottom();
  } catch (e) {
    toast(t('toast_load_chat_failed', e.message), { error: true });
  }
}

async function newChat() {
  abortStream();
  try {
    const c = await api('POST', '/conversations', {});
    state.cid = c.id;
    state.title = c.title;
    state.pinned = false;
    state.messages = [];
    state.streamingText = '';
    state.isStreaming = false;
    updateTopbar(0);
    renderMessages();
    await refreshChatList();
    localStorage.setItem(LS.lastCid, c.id);
    history.replaceState(null, '', '#/chat/' + c.id);
    els.input.focus();
  } catch (e) {
    toast(t('toast_new_chat_failed', e.message), { error: true });
  }
}

function updateTopbar(tokens) {
  els.topbarTitle.textContent = state.title || 'Pocket Claude';
  const pct = Math.round((tokens / 200000) * 100);
  if (state.messages.length) {
    els.topbarMeta.textContent = t('messages_context_format', state.messages.length, pct);
    els.topbarMeta.classList.toggle('warn', pct >= 85);
  } else {
    els.topbarMeta.textContent = '';
  }
}

els.newChatBtn.addEventListener('click', newChat);
els.sidebarToggle.addEventListener('click', () => {
  if (window.matchMedia('(max-width: 768px)').matches) {
    els.sidebar.classList.toggle('open');
  } else {
    const collapsed = els.app.classList.toggle('sidebar-collapsed');
    localStorage.setItem(LS.sidebar, collapsed ? '1' : '0');
    queueSettingsPush();
  }
});
// Sidebar-Zustand beim Start aus localStorage restoren (nur Desktop)
if (localStorage.getItem(LS.sidebar) === '1' &&
    !window.matchMedia('(max-width: 768px)').matches) {
  els.app.classList.add('sidebar-collapsed');
}

// =========================================================
// Effort-Dropdown
// =========================================================
function setEffort(value, persist = true) {
  state.effort = value;
  if (persist) {
    localStorage.setItem(LS.effort, value);
    queueSettingsPush();
  }
  els.effortLabel.textContent = value.charAt(0).toUpperCase() + value.slice(1);
  els.effortMenu.querySelectorAll('button').forEach(b => {
    b.classList.toggle('active', b.dataset.effort === value);
  });
}
els.effortBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  els.effortMenu.classList.toggle('hidden');
  els.moreMenu.classList.add('hidden');
});
els.effortMenu.addEventListener('click', (e) => {
  const v = e.target.dataset.effort;
  if (!v) return;
  setEffort(v);
  els.effortMenu.classList.add('hidden');
});

// More-Menü
els.moreBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  els.pinLabel.textContent = state.pinned ? t('unpin') : t('pin');
  els.moreMenu.classList.toggle('hidden');
  els.effortMenu.classList.add('hidden');
});
els.moreMenu.addEventListener('click', async (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  const action = btn.dataset.action;
  els.moreMenu.classList.add('hidden');
  if (!state.cid) return;
  try {
    if (action === 'rename') {
      const newTitle = prompt(t('rename_prompt'), state.title);
      if (newTitle && newTitle.trim()) {
        await api('PATCH', '/conversations/' + state.cid, { title: newTitle.trim() });
        state.title = newTitle.trim();
        updateTopbar(0);
        refreshChatList();
      }
    } else if (action === 'pin') {
      await api('PATCH', '/conversations/' + state.cid, { pinned: !state.pinned });
      state.pinned = !state.pinned;
      refreshChatList();
    } else if (action === 'share') {
      // Markdown-Export holen
      const md = await api('GET', '/conversations/' + state.cid + '/export.md');
      const blob = new Blob([md], { type: 'text/markdown' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${state.title || 'chat'}.md`.replace(/[^\w.-]+/g, '_');
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(a.href);
    } else if (action === 'auto-mode') {
      // Auto-Mode toggle — delegiert in den Voice-Block unten.
      if (window.PocketVoice) window.PocketVoice.toggleAutoMode();
    } else if (action === 'delete') {
      if (!confirm(t('confirm_delete_chat', state.title))) return;
      await api('DELETE', '/conversations/' + state.cid);
      state.cid = null;
      await refreshChatList();
      if (state._allCids.length) openChat(state._allCids[0]);
      else newChat();
    }
  } catch (e) {
    toast(t('toast_action_failed', e.message), { error: true });
  }
});

// Globaler Click → Dropdowns schließen
document.addEventListener('click', () => {
  els.effortMenu.classList.add('hidden');
  els.moreMenu.classList.add('hidden');
});

// =========================================================
// Render Messages
// =========================================================
function renderMessages() {
  els.messages.innerHTML = '';
  const inner = document.createElement('div');
  inner.className = 'messages-inner';
  els.messages.appendChild(inner);

  if (!state.messages.length && !state.isStreaming) {
    inner.innerHTML = `
      <div class="empty-hint">
        <div class="e-logo">
          <svg width="32" height="32" viewBox="0 0 24 24"><path d="M12 8v6m-3-3 3 3 3-3" stroke="white" stroke-width="1.8" stroke-linecap="round" fill="none"/></svg>
        </div>
        <h3>${escapeHtml(t('empty_hint_title'))}</h3>
        <p>${escapeHtml(t('empty_hint_body'))}</p>
      </div>`;
    return;
  }
  for (const m of state.messages) inner.appendChild(renderMessage(m));
  if (state.isStreaming) {
    inner.appendChild(renderStreamingPlaceholder());
  }
  enhanceCodeBlocks(inner);
}

function renderMessage(m) {
  const div = document.createElement('div');
  div.className = 'msg ' + (m.role === 'user' ? 'user' : 'assistant');
  const attHtml = attachmentsToHtml(m.attachments);
  if (m.role === 'user') {
    const textHtml = escapeHtml(m.content || '').replace(/\n/g, '<br>');
    // Bei aktiviertem collapseUserMsgs starten wir mit .collapsed —
    // applyUserBubbleCollapse() checkt nach dem Layout, ob die Bubble
    // wirklich overflowt, und entfernt sonst die Klasse + den Toggle.
    const bubbleClass = state.collapseUserMsgs ? 'bubble collapsed' : 'bubble';
    div.innerHTML = `
      <div>
        ${attHtml}
        ${m.content ? `<div class="${bubbleClass}">${textHtml}</div>` : ''}
      </div>`;
    if (m.content && state.collapseUserMsgs) {
      const bubble = div.querySelector('.bubble');
      // Tap auf die Bubble toggelt auf/zu — kein separater Button mehr
      // (selbsterklärend). Text-Selektion bleibt unangetastet: wenn der User
      // gerade etwas markiert hat, kein Toggle.
      bubble.addEventListener('click', () => {
        if (window.getSelection().toString()) return;
        bubble.classList.toggle('collapsed');
      });
      // Nach dem Layout entscheiden, ob die Collapse-Klasse überhaupt
      // sinnvoll ist (kein Overflow → kein Collapse).
      requestAnimationFrame(() => {
        const overflows = bubble.scrollHeight > bubble.clientHeight + 1;
        if (!overflows) bubble.classList.remove('collapsed');
      });
    }
  } else {
    const speakerActive = state.audio.msgId === m.id && state.audio.playing;
    div.innerHTML = `
      <div>
        ${attHtml}
        <div class="content">${renderMarkdown(m.content)}</div>
        <div class="msg-tools">
          <button class="icon-btn ${speakerActive ? 'active' : ''}" data-id="${m.id}" data-tool="tts" title="${escapeHtml(t('tts_title'))}">
            <svg class="icon"><use href="#icon-speaker"/></svg>
          </button>
          <button class="icon-btn" data-tool="copy" title="${escapeHtml(t('copy_title'))}">
            <svg class="icon"><use href="#icon-copy"/></svg>
          </button>
        </div>
      </div>`;
    div.querySelector('[data-tool="tts"]').addEventListener('click', (e) => {
      toggleTts(m.id, e.currentTarget);
    });
    div.querySelector('[data-tool="copy"]').addEventListener('click', () => {
      navigator.clipboard.writeText(m.content).then(() => toast(t('toast_copied')));
    });
  }
  return div;
}

function renderStreamingPlaceholder() {
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.id = 'streaming-msg';
  div.innerHTML = `
    <div>
      <div class="content">${state.streamingText
        ? renderMarkdown(state.streamingText)
        : '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>'}</div>
    </div>`;
  return div;
}

function updateStreaming() {
  let div = $('streaming-msg');
  if (!div) { renderMessages(); div = $('streaming-msg'); }
  if (div) {
    const content = div.querySelector('.content');
    content.innerHTML = renderMarkdown(state.streamingText);
    enhanceCodeBlocks(content);
  }
}

function scrollToBottom(force = false) {
  // Bei Streaming-Deltas: nur scrollen wenn der User eh nah am Ende ist
  const m = els.messages;
  const nearBottom = m.scrollHeight - m.scrollTop - m.clientHeight < 200;
  if (force || nearBottom) {
    m.scrollTop = m.scrollHeight + 1000000;
  }
}

// Beim Chat-Öffnen: hart ans Ende halten, bis ALLES gerendert ist
// (Markdown, Code-Highlight, Bilder, Schriften). Strategie:
//  1) Sofort scrollen + Retry-Loop für ~1.5s
//  2) ResizeObserver auf den Messages-Container — solange der „pin to bottom"-
//     Modus aktiv ist, bei jeder Höhen-Änderung wieder runterspringen
//  3) Auf jedes <img load> reagieren
//  4) Modus endet, sobald der User selbst scrollt
let _pinBottomCleanup = null;
async function scrollToVeryBottom() {
  const m = els.messages;
  // alten Pin-Modus aufräumen
  if (_pinBottomCleanup) { _pinBottomCleanup(); _pinBottomCleanup = null; }

  const jump = () => { m.scrollTop = m.scrollHeight + 1000000; };
  jump();

  // (1) Retry-Loop — mehrere Anläufe in einer Sekunde
  const retries = setInterval(jump, 80);
  setTimeout(() => clearInterval(retries), 1500);

  // (2) ResizeObserver: jedes Mal wenn die Höhe wächst → wieder ans Ende
  let userScrolled = false;
  const onScroll = () => {
    // nur als User-Aktion werten, wenn er WIRKLICH weg vom Ende ist
    if (m.scrollHeight - m.scrollTop - m.clientHeight > 80) userScrolled = true;
  };
  m.addEventListener('scroll', onScroll, { passive: true });

  const ro = new ResizeObserver(() => { if (!userScrolled) jump(); });
  ro.observe(m);
  for (const child of m.children) ro.observe(child);

  // (3) Bilder, die später laden, ziehen auch nach unten
  const imgListeners = [];
  for (const img of m.querySelectorAll('img')) {
    if (!img.complete) {
      const h = () => { if (!userScrolled) jump(); };
      img.addEventListener('load', h, { once: true });
      img.addEventListener('error', h, { once: true });
      imgListeners.push([img, h]);
    }
  }

  // Pin-Modus nach 4s automatisch beenden — danach ist „normal nahe-am-Ende"-
  // Scroll-Verhalten zuständig (scrollToBottom bei neuen Messages).
  const stopAt = setTimeout(stop, 4000);
  function stop() {
    clearTimeout(stopAt);
    clearInterval(retries);
    m.removeEventListener('scroll', onScroll);
    ro.disconnect();
    for (const [img, h] of imgListeners) {
      img.removeEventListener('load', h);
      img.removeEventListener('error', h);
    }
    _pinBottomCleanup = null;
  }
  _pinBottomCleanup = stop;
}

// =========================================================
// Attachments
// =========================================================
els.attachBtn.addEventListener('click', () => els.fileInput.click());
els.fileInput.addEventListener('change', async (e) => {
  const files = [...e.target.files];
  els.fileInput.value = '';
  for (const f of files) await uploadAttachment(f);
});

async function uploadAttachment(file) {
  const placeholder = { id: 'pending-' + Math.random(), filename: file.name, _uploading: true, mime_type: file.type };
  // Local preview falls Bild
  if (file.type.startsWith('image/')) {
    placeholder._previewUrl = URL.createObjectURL(file);
  }
  state.pendingAttach.push(placeholder);
  renderPending();
  try {
    const prepared = await maybeCompressImage(file);
    const fd = new FormData();
    fd.append('file', prepared.blob, prepared.filename);
    const r = await api('POST', '/attachments', fd);
    const idx = state.pendingAttach.indexOf(placeholder);
    if (idx >= 0) {
      r._previewUrl = placeholder._previewUrl;  // Preview behalten
      state.pendingAttach[idx] = r;
    }
    renderPending();
  } catch (e) {
    state.pendingAttach = state.pendingAttach.filter(a => a !== placeholder);
    renderPending();
    toast(t('toast_upload_failed', e.message), { error: true });
  }
}

function renderPending() {
  if (!state.pendingAttach.length) {
    els.pendingWrap.classList.add('hidden');
    els.pendingWrap.innerHTML = '';
    return;
  }
  els.pendingWrap.classList.remove('hidden');
  els.pendingWrap.innerHTML = '';
  for (const a of state.pendingAttach) {
    const chip = document.createElement('div');
    chip.className = 'att-chip';
    const preview = a._previewUrl
      ? `<img class="att-preview" src="${a._previewUrl}" alt="">`
      : `<div class="att-preview" style="display:flex;align-items:center;justify-content:center;color:var(--text-muted)"><svg class="icon"><use href="#icon-file"/></svg></div>`;
    const sz = a.size_bytes ? ` · ${(a.size_bytes/1024).toFixed(0)} KB` : '';
    chip.innerHTML = `
      ${preview}
      <div class="att-info">
        <span class="name">${a._uploading ? '⏳ ' : ''}${escapeHtml(a.filename)}</span>
        <span class="meta">${sz}</span>
      </div>
      <button class="rm" type="button" title="${escapeHtml(t('remove_title'))}"><svg class="icon" style="width:14px;height:14px"><use href="#icon-close"/></svg></button>
    `;
    chip.querySelector('.rm').onclick = () => {
      state.pendingAttach = state.pendingAttach.filter(x => x !== a);
      if (a._previewUrl) URL.revokeObjectURL(a._previewUrl);
      renderPending();
    };
    els.pendingWrap.appendChild(chip);
  }
}

function attachmentsToHtml(atts) {
  if (!atts || !atts.length) return '';
  const images = atts.filter(a => (a.mime_type || '').startsWith('image/'));
  const others = atts.filter(a => !(a.mime_type || '').startsWith('image/'));

  let html = '';
  if (images.length) {
    html += '<div class="image-grid">';
    for (const a of images) {
      const url = `${state.serverUrl}/attachments/${a.id}?token=${encodeURIComponent(state.token)}`;
      html += `
        <figure data-att-id="${escapeHtml(a.id)}">
          <img src="${url}" alt="${escapeHtml(a.filename)}" data-lightbox="${url}">
          <div class="img-actions">
            <button title="${escapeHtml(t('img_action_zoom'))}" data-action="zoom" data-url="${url}"><svg class="icon"><use href="#icon-search"/></svg></button>
            <button title="${escapeHtml(t('img_action_edit'))}" data-action="edit" data-att-id="${escapeHtml(a.id)}" data-filename="${escapeHtml(a.filename)}" data-mime="${escapeHtml(a.mime_type)}"><svg class="icon"><use href="#icon-wand"/></svg></button>
            <a href="${url}" download="${escapeHtml(a.filename)}" title="${escapeHtml(t('img_action_download'))}"><button data-action="download"><svg class="icon"><use href="#icon-download"/></svg></button></a>
          </div>
        </figure>`;
    }
    html += '</div>';
  }
  if (others.length) {
    html += '<div class="attachments">';
    for (const a of others) {
      const url = `${state.serverUrl}/attachments/${a.id}?token=${encodeURIComponent(state.token)}`;
      html += `<a class="file-card" href="${url}" target="_blank" rel="noopener">
        <svg class="icon"><use href="#icon-file"/></svg>${escapeHtml(a.filename)}
      </a>`;
    }
    html += '</div>';
  }
  return html;
}

// Lightbox: Bild groß zeigen wenn man drauf klickt
document.addEventListener('click', (e) => {
  const img = e.target.closest && e.target.closest('img[data-lightbox]');
  if (img) {
    const url = img.dataset.lightbox;
    openLightbox(url);
    return;
  }
  const btn = e.target.closest && e.target.closest('button[data-action]');
  if (btn) {
    const act = btn.dataset.action;
    if (act === 'zoom') { openLightbox(btn.dataset.url); }
    else if (act === 'edit') {
      // Bild als Pending-Attachment für Edit-Generation einfügen + Image-Mode an
      state.pendingAttach.push({
        id: btn.dataset.attId,
        filename: btn.dataset.filename,
        mime_type: btn.dataset.mime,
        _existing: true,
      });
      renderPending();
      setImageMode(true);
      els.input.focus();
      toast(t('toast_image_set_as_edit'));
    }
  }
});

function openLightbox(url) {
  const old = document.getElementById('lightbox'); if (old) old.remove();
  const lb = document.createElement('div');
  lb.id = 'lightbox';
  lb.className = 'lightbox';
  lb.innerHTML = `<button class="lb-close" aria-label="${escapeHtml(t('lightbox_close'))}">×</button><img src="${url}">`;
  lb.addEventListener('click', (e) => {
    if (e.target === lb || e.target.classList.contains('lb-close')) lb.remove();
  });
  document.addEventListener('keydown', function esc(e) {
    if (e.key === 'Escape') { lb.remove(); document.removeEventListener('keydown', esc); }
  });
  document.body.appendChild(lb);
}

async function maybeCompressImage(file) {
  const MAX_EDGE = 1568;
  const Q = 0.85;
  const SKIP = 200 * 1024;
  if (!file.type.startsWith('image/')) return { blob: file, filename: file.name };
  if (file.type === 'image/gif') return { blob: file, filename: file.name };
  if (file.size <= SKIP) return { blob: file, filename: file.name };
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: 'from-image' });
    const longest = Math.max(bmp.width, bmp.height);
    if (longest <= MAX_EDGE && file.size <= 1_500_000) {
      bmp.close();
      return { blob: file, filename: file.name };
    }
    const scale = MAX_EDGE / longest;
    const w = Math.round(bmp.width * (scale < 1 ? scale : 1));
    const h = Math.round(bmp.height * (scale < 1 ? scale : 1));
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    canvas.getContext('2d').drawImage(bmp, 0, 0, w, h);
    bmp.close();
    const blob = await new Promise(r => canvas.toBlob(r, 'image/jpeg', Q));
    if (!blob) return { blob: file, filename: file.name };
    return { blob, filename: file.name.replace(/\.[^.]+$/, '') + '.jpg' };
  } catch (_) {
    return { blob: file, filename: file.name };
  }
}

// =========================================================
// Image-Mode (Gemini / Nano Banana)
// =========================================================
const imageState = {
  enabled: false,
  config: null,       // { models, aspect_ratios, max_candidates, default_*, configured, api_key_masked }
  model: null,
  aspect: '1:1',
  count: 1,
  busy: false,
  configLoaded: false,
};

const imgEls = {
  toggle:    $('image-mode-btn'),
  panel:     $('image-options'),
  modelSel:  $('image-model'),
  aspectCh:  $('image-aspect-chips'),
  countCh:   $('image-count-chips'),
  status:    $('image-options-status'),
  composer:  null, // gesetzt unten
  hint:      $('composer-hint'),
  input:     $('input'),
};
imgEls.composer = els.inputForm; // <form class="composer">

async function loadImageConfig() {
  if (imageState.configLoaded) return;
  try {
    imageState.config = await api('GET', '/images/config');
    imageState.configLoaded = true;
    imageState.model = imageState.config.default_model;
    imageState.aspect = imageState.config.default_aspect;
    // Modell-Select
    imgEls.modelSel.innerHTML = '';
    for (const m of imageState.config.models) {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.label;
      opt.title = m.description || '';
      if (m.id === imageState.model) opt.selected = true;
      imgEls.modelSel.appendChild(opt);
    }
    imgEls.modelSel.addEventListener('change', () => {
      imageState.model = imgEls.modelSel.value;
    });
    // Aspect-Chips
    imgEls.aspectCh.innerHTML = '';
    for (const a of imageState.config.aspect_ratios) {
      const b = document.createElement('button');
      b.className = 'chip' + (a.id === imageState.aspect ? ' active' : '');
      b.type = 'button';
      b.dataset.aspect = a.id;
      b.textContent = a.id;
      b.title = a.label;
      b.addEventListener('click', () => {
        imageState.aspect = a.id;
        imgEls.aspectCh.querySelectorAll('.chip').forEach(c =>
          c.classList.toggle('active', c.dataset.aspect === a.id));
      });
      imgEls.aspectCh.appendChild(b);
    }
    // Count-Chips
    imgEls.countCh.querySelectorAll('.chip').forEach(c => {
      const n = parseInt(c.dataset.count, 10);
      c.classList.toggle('active', n === imageState.count);
      c.addEventListener('click', () => {
        imageState.count = n;
        imgEls.countCh.querySelectorAll('.chip').forEach(cc =>
          cc.classList.toggle('active', parseInt(cc.dataset.count, 10) === n));
      });
    });
  } catch (e) {
    setImageStatus(t('image_mode_config_unavailable', e.message), 'error');
  }
}

function setImageStatus(text, kind = '') {
  if (!imgEls.status) return;
  imgEls.status.textContent = text || '';
  imgEls.status.className = 'image-options-status' + (kind ? ' ' + kind : '');
}

async function setImageMode(on) {
  imageState.enabled = !!on;
  imgEls.toggle.classList.toggle('image-active', on);
  imgEls.panel.classList.toggle('hidden', !on);
  imgEls.composer.classList.toggle('image-mode', on);
  if (on) {
    await loadImageConfig();
    imgEls.input.placeholder = t('image_mode_placeholder');
    imgEls.hint.innerHTML = t('image_mode_hint') +
      (imageState.config && !imageState.config.configured
        ? ` · <span style="color:var(--danger)">${t('image_mode_hint_no_key').replace(/^ · /, '')}</span>`
        : ''
      );
    if (!imageState.config?.configured) {
      setImageStatus(t('image_mode_no_key_hint'), 'error');
    } else {
      setImageStatus('');
    }
  } else {
    imgEls.input.placeholder = t('compose_placeholder');
    imgEls.hint.textContent = t('composer_hint');
    setImageStatus('');
  }
}

imgEls.toggle.addEventListener('click', () => setImageMode(!imageState.enabled));

async function generateImage(prompt) {
  if (imageState.busy) return;
  if (!imageState.config?.configured) {
    setImageStatus(t('image_mode_no_key_short'), 'error');
    return;
  }
  imageState.busy = true;
  els.sendBtn.disabled = true;
  setImageStatus(t('image_mode_status_generating', imageState.count, imageState.aspect, imageState.model), 'busy');

  if (!state.cid) await newChat();

  // Optional: gepastete/angehängte Bilder als Referenz nehmen
  const refIds = state.pendingAttach
    .filter(a => !a._uploading && (a.mime_type || '').startsWith('image/'))
    .map(a => a.id);

  try {
    const resp = await api('POST', '/images/generate', {
      prompt,
      conversation_id: state.cid,
      model: imageState.model,
      aspect_ratio: imageState.aspect,
      count: imageState.count,
      reference_attachment_ids: refIds,
    });
    // Pending aufräumen
    for (const a of state.pendingAttach) if (a._previewUrl) URL.revokeObjectURL(a._previewUrl);
    state.pendingAttach = [];
    renderPending();
    els.input.value = '';
    autoResize();
    setImageStatus(
      resp.attachments.length === 1
        ? t('image_mode_status_done_singular', resp.attachments.length)
        : t('image_mode_status_done_plural', resp.attachments.length),
      '',
    );
    // Chat neu laden, damit die neuen Messages erscheinen
    await reloadChatMessages(state.cid);
    setTimeout(scrollToVeryBottom, 50);
  } catch (e) {
    let msg = e.message || 'Unknown error';
    if (e instanceof ApiError) {
      msg = e.status === 502 ? msg : `HTTP ${e.status}: ${msg}`;
    }
    setImageStatus(t('image_mode_error_prefix', msg), 'error');
    toast(t('toast_image_gen_failed', msg), { error: true });
  } finally {
    imageState.busy = false;
    els.sendBtn.disabled = false;
    els.input.focus();
  }
}

async function reloadChatMessages(cid) {
  try {
    const detail = await api('GET', `/conversations/${cid}`);
    state.messages = detail.messages;
    state.title = detail.title;
    state.pinned = !!detail.pinned;
    updateTopbar(detail.total_tokens || 0);
    renderMessages();
  } catch (_) { /* swallow */ }
}

// =========================================================
// Senden + Streaming
// =========================================================
els.inputForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const content = els.input.value.trim();
  if (!content || state.isStreaming) return;
  if (imageState.enabled) { generateImage(content); return; }
  if (!state.cid) await newChat();
  const sentAttach = state.pendingAttach
    .filter(a => !a._uploading)
    .map(a => ({ id: a.id, filename: a.filename, mime_type: a.mime_type }));
  state.messages.push({
    id: -Date.now(),
    role: 'user',
    content,
    attachments: sentAttach,
    created_at: new Date().toISOString(),
  });
  // Pending-Preview-URLs aufräumen
  for (const a of state.pendingAttach) if (a._previewUrl) URL.revokeObjectURL(a._previewUrl);
  state.pendingAttach = [];
  renderPending();
  state.streamingText = '';
  state.isStreaming = true;
  els.input.value = '';
  autoResize();
  els.sendBtn.disabled = true;
  renderMessages();
  scrollToBottom(true);
  // PC_SSE diagnostic — see "denkt"-bug investigation
  state._sseTurnStart = performance.now();
  state._sseGotDone = false;
  state._sseGotError = false;
  state._sseDeltaCount = 0;
  console.log('PC_SSE: submit START cid=%s content_len=%d', state.cid, content.length);
  try {
    await streamReply(content);
  } catch (e) {
    console.log('PC_SSE: submit CATCH', e?.name, e?.message);
    if (e.name !== 'AbortError') toast(t('toast_reply_failed', e.message), { error: true });
  } finally {
    const dt = (performance.now() - state._sseTurnStart).toFixed(0);
    console.log('PC_SSE: submit FINALLY cid=%s gotDone=%s gotError=%s deltas=%d isStreaming=%s elapsed=%sms streamingTextLen=%d',
      state.cid, state._sseGotDone, state._sseGotError,
      state._sseDeltaCount, state.isStreaming, dt, state.streamingText.length);
    // Safety net: if the stream ended without a `done` event but we have
    // accumulated streaming text, the assistant message was very likely
    // saved server-side. Force a reload so the dots-placeholder isn't
    // stuck forever (matches the "refresh fixes it" workaround).
    if (state.isStreaming && !state._sseGotDone && !state._sseGotError) {
      console.warn('PC_SSE: submit RESCUE — stream ended without done; reloading messages');
      const cidAtSubmit = state.cid;
      state.isStreaming = false;
      state.streamingText = '';
      reloadChatMessages(cidAtSubmit);
    }
    state.isStreaming = false;
    els.sendBtn.disabled = false;
    els.input.focus();
  }
});

els.input.addEventListener('input', autoResize);
function autoResize() {
  els.input.style.height = 'auto';
  els.input.style.height = Math.min(240, els.input.scrollHeight) + 'px';
}
els.input.addEventListener('keydown', (e) => {
  // Enter ohne Modifier → senden; Shift+Enter → Zeilenumbruch (ChatGPT-Style)
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    els.inputForm.requestSubmit();
  }
});

function abortStream() {
  if (state.abort) {
    try { state.abort.abort(); } catch {}
    state.abort = null;
  }
}

async function streamReply(content) {
  abortStream();
  const ctrl = new AbortController();
  state.abort = ctrl;
  const resp = await fetch(state.serverUrl + '/conversations/' + state.cid + '/messages', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + state.token,
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify({
      content,
      attachment_ids: state.messages[state.messages.length - 1]?.attachments?.map(a => a.id) || [],
      effort: state.effort,
      system_prompt_mode: state.spMode,
      system_prompt: state.spMode === 'CUSTOM' ? state.spCustom : null,
      // TTS-Hints: Server startet nach Done-Event eine Pre-Generation,
      // sodass der nächste 🔊-Tap Cache-Hit ist.
      tts_voice: state.ttsVoice,
      tts_rate: state.ttsSpeed,
    }),
    signal: ctrl.signal,
  });
  if (!resp.ok) {
    const txt = await resp.text().catch(() => '');
    console.log('PC_SSE: streamReply HTTP-FAIL status=%s body=%s', resp.status, txt.slice(0, 200));
    throw new Error(`HTTP ${resp.status}: ${txt}`);
  }
  console.log('PC_SSE: streamReply HTTP-OK status=%s headers=%o',
    resp.status, Object.fromEntries(resp.headers.entries()));
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let chunkCount = 0;
  let totalBytes = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        console.log('PC_SSE: streamReply READER-DONE chunks=%d bytes=%d buffer_remainder_len=%d gotDone=%s',
          chunkCount, totalBytes, buffer.length, state._sseGotDone);
        if (buffer.length > 0) {
          console.warn('PC_SSE: streamReply UNFLUSHED-BUFFER (no trailing \\n\\n):', buffer.slice(0, 400));
        }
        break;
      }
      chunkCount += 1;
      totalBytes += value?.byteLength || 0;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        handleSseEvent(raw);
      }
    }
  } catch (e) {
    console.log('PC_SSE: streamReply READER-EXC', e?.name, e?.message,
      'chunks=', chunkCount, 'bytes=', totalBytes);
    throw e;
  }
}

function handleSseEvent(raw) {
  let event = 'message';
  let data = '';
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data += line.slice(5).trim();
  }
  let payload = {};
  if (data) { try { payload = JSON.parse(data); } catch {} }
  // PC_SSE diagnostic
  if (event === 'delta') {
    state._sseDeltaCount = (state._sseDeltaCount || 0) + 1;
    if (state._sseDeltaCount <= 3 || state._sseDeltaCount % 25 === 0) {
      console.log('PC_SSE: recv delta #%d len=%d', state._sseDeltaCount, (payload.text || '').length);
    }
  } else {
    console.log('PC_SSE: recv event=%s payload=%o', event, payload);
  }
  switch (event) {
    case 'title':
      state.title = payload.title || state.title;
      els.topbarTitle.textContent = state.title;
      const item = document.querySelector(`.chat-item[data-cid="${state.cid}"] .title`);
      if (item) item.textContent = state.title;
      break;
    case 'user_saved':
      const lastUser = [...state.messages].reverse().find(m => m.role === 'user');
      if (lastUser) lastUser.id = payload.user_message_id;
      break;
    case 'delta':
      state.streamingText += payload.text || '';
      updateStreaming();
      scrollToBottom();
      break;
    case 'done':
      state._sseGotDone = true;
      state.messages.push({
        id: payload.assistant_message_id || payload.message_id,
        role: 'assistant',
        content: state.streamingText,
        tokens: (payload.tokens_in || 0) + (payload.tokens_out || 0),
        created_at: new Date().toISOString(),
      });
      state.streamingText = '';
      state.isStreaming = false;
      renderMessages();
      updateTopbar(payload.tokens_total || 0);
      refreshChatList();
      break;
    case 'error':
      state._sseGotError = true;
      toast(t('toast_server_error', payload.message || ''), { error: true });
      state.isStreaming = false;
      renderMessages();
      break;
    case 'compaction_started':
      toast(t('toast_compacting'));
      break;
  }
}

// =========================================================
// TTS
// =========================================================
els.audio.addEventListener('ended', () => {
  state.audio = { msgId: null, playing: false };
  document.querySelectorAll('.msg-tools [data-tool="tts"]').forEach(b => b.classList.remove('active'));
});

function toggleTts(messageId, btn) {
  if (state.audio.msgId === messageId && state.audio.playing) {
    els.audio.pause();
    state.audio.playing = false;
    btn.classList.remove('active');
    return;
  }
  els.audio.pause();
  document.querySelectorAll('.msg-tools [data-tool="tts"]').forEach(b => b.classList.remove('active'));
  const params = new URLSearchParams({
    voice: state.ttsVoice,
    rate: state.ttsSpeed.toString(),
    token: state.token,
  });
  els.audio.src = `${state.serverUrl}/messages/${messageId}/audio?${params}`;
  els.audio.play().then(() => {
    state.audio = { msgId: messageId, playing: true };
    btn.classList.add('active');
  }).catch(err => toast(t('toast_playback', err.message), { error: true }));
}

// =========================================================
// Settings-Modal
// =========================================================
// Late-bind so the addEventListener picks up the openSettings reassignment
// further down the file (which extends the modal-open with user-list +
// image-key + auth + usage loaders).
els.settingsBtn.addEventListener('click', () => openSettings());
els.settingsClose.addEventListener('click', () => els.settingsModal.classList.add('hidden'));
els.settingsModal.addEventListener('click', (e) => {
  if (e.target === els.settingsModal) els.settingsModal.classList.add('hidden');
});

function _renderTtsProviderHint(status) {
  if (!els.ttsProviderHint) return;
  const p = status.provider || 'edge_tts';
  const lines = [];
  if (p === 'edge_tts') {
    lines.push(t('tts_hint_edge_ok'));
  } else if (p === 'gemini_api') {
    if (status.gemini_api_configured) {
      lines.push(t('tts_hint_gemini_ok'));
    } else {
      lines.push(t('tts_hint_gemini_missing'));
    }
  } else {
    if (status.cloud_tts_configured) {
      lines.push(t('tts_hint_cloud_ok', status.client_email || '?'));
    } else {
      lines.push(t('tts_hint_cloud_missing'));
    }
  }
  els.ttsProviderHint.textContent = lines.join(' ');
}

async function openSettings() {
  document.querySelectorAll('input[name="sp-mode"]').forEach(r => {
    r.checked = (r.value === state.spMode);
  });
  els.spCustom.value = state.spCustom;
  els.ttsSpeed.value = state.ttsSpeed;
  els.ttsSpeedLabel.textContent = state.ttsSpeed.toFixed(2) + '×';
  els.settingsModal.classList.remove('hidden');
  try {
    const s = await api('GET', '/tts/status');
    // Provider-Select setzen (server ist Source-of-Truth)
    if (els.ttsProvider && s.provider) {
      els.ttsProvider.value = s.provider;
      state.ttsProvider = s.provider;
    }
    _renderTtsProviderHint(s);
    if (!state._ttsLoaded) {
      els.ttsVoice.innerHTML = '';
      // Tier-Reihenfolge wie in der App: erst gratis/AI, dann Premium-Tiers.
      // edge + chirp3hd fehlten lange — Server liefert sie via /tts/status,
      // wir haben sie hier aber rausgefiltert und stille im Dropdown
      // verschwinden lassen. Default-Voice für frisch eingerichtete Server
      // ist `edge-de-DE-KatjaNeural` — die war damit gar nicht wählbar.
      const tiers = ['edge','gemini','chirp3hd','studio','neural2','wavenet','standard'];
      const labels = {
        edge:'Edge (gratis)',
        gemini:'Gemini 3.1 Flash',
        chirp3hd:'Chirp 3 HD (1 Mio Zeichen/Monat gratis)',
        studio:'Studio',
        neural2:'Neural2',
        wavenet:'Wavenet',
        standard:'Standard',
      };
      const grouped = {};
      for (const v of (s.voices || [])) (grouped[v.tier]=grouped[v.tier]||[]).push(v);
      for (const t of tiers) {
        if (!grouped[t]) continue;
        const og = document.createElement('optgroup');
        og.label = labels[t] || t;
        for (const v of grouped[t]) {
          const opt = document.createElement('option');
          opt.value = v.id; opt.textContent = v.label;
          if (v.id === state.ttsVoice) opt.selected = true;
          og.appendChild(opt);
        }
        els.ttsVoice.appendChild(og);
      }
      state._ttsLoaded = true;
    } else {
      els.ttsVoice.value = state.ttsVoice;
    }
  } catch (e) { toast(t('toast_tts_error', e.message), { error: true }); }
}

document.querySelectorAll('input[name="sp-mode"]').forEach(r => {
  r.addEventListener('change', () => {
    if (r.checked) {
      state.spMode = r.value;
      localStorage.setItem(LS.spMode, r.value);
      queueSettingsPush();
    }
  });
});
els.spCustom.addEventListener('input', () => {
  state.spCustom = els.spCustom.value;
  localStorage.setItem(LS.spCustom, state.spCustom);
  queueSettingsPush();
});

// "Lange eigene Nachrichten einklappen" — Toggle aus dem Settings-Modal.
// Klassisch in localStorage gespeichert. Beim Toggle alle bereits gerenderten
// User-Bubbles refreshen, damit der Effekt sofort sichtbar wird (statt erst
// nach dem nächsten Send).
const collapseCheckbox = document.getElementById('setting-collapse-user-msgs');
if (collapseCheckbox) {
  collapseCheckbox.checked = state.collapseUserMsgs;
  collapseCheckbox.addEventListener('change', () => {
    state.collapseUserMsgs = collapseCheckbox.checked;
    localStorage.setItem(LS.collapseUserMsgs, String(state.collapseUserMsgs));
    // Re-render alle User-Bubbles: am einfachsten via renderMessages()
    if (typeof renderMessages === 'function') renderMessages();
  });
}
els.ttsVoice.addEventListener('change', () => {
  state.ttsVoice = els.ttsVoice.value;
  localStorage.setItem(LS.ttsVoice, state.ttsVoice);
  queueSettingsPush();
});

if (els.ttsProvider) {
  els.ttsProvider.addEventListener('change', async () => {
    const newProvider = els.ttsProvider.value;
    try {
      const s = await api('PUT', '/tts/provider', { provider: newProvider });
      state.ttsProvider = newProvider;
      _renderTtsProviderHint(s);
      toast(t('toast_provider_changed', newProvider === 'gemini_api' ? t('tts_provider_label_gemini') : t('tts_provider_label_cloud')), { ok: true });
    } catch (e) {
      toast(t('toast_provider_switch_failed', e.message), { error: true });
    }
  });
}
els.ttsSpeed.addEventListener('input', () => {
  state.ttsSpeed = parseFloat(els.ttsSpeed.value);
  els.ttsSpeedLabel.textContent = state.ttsSpeed.toFixed(2) + '×';
  localStorage.setItem(LS.ttsSpeed, state.ttsSpeed.toString());
  queueSettingsPush();
});

// =========================================================
// Backup
// =========================================================
els.backupExport.addEventListener('click', async () => {
  const pw = await showPrompt({
    title: t('backup_encrypt_title'),
    text: t('backup_encrypt_text'),
    placeholder: t('backup_password_placeholder'), type: 'password', okLabel: t('backup_export_button'),
  });
  if (pw === null) return;
  setBackupStatus(t('backup_loading'));
  try {
    const params = new URLSearchParams();
    if (pw) params.set('password', pw);
    const resp = await fetch(`${state.serverUrl}/backup${params.toString() ? '?' + params : ''}`, {
      headers: { 'Authorization': 'Bearer ' + state.token },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    const cd = resp.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename="([^"]+)"/);
    const filename = m ? m[1] : `pocket-claude-backup${pw ? '.enc' : ''}.zip`;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(a.href);
    setBackupStatus(t('backup_export_done', filename, (blob.size/1024/1024).toFixed(1)), 'ok');
  } catch (e) {
    setBackupStatus(t('backup_export_failed', e.message), 'error');
  }
});

els.backupImport.addEventListener('click', () => els.backupFileInput.click());
els.backupFileInput.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (!file) return;
  setBackupStatus(t('backup_checking'));
  try {
    const bytes = await file.arrayBuffer();
    let password = null, manifest;
    while (true) {
      try { manifest = await peekBackup(bytes, password); break; }
      catch (err) {
        if (err.status === 423) {
          const pw = await showPrompt({
            title: t('backup_encrypted_title'),
            text: password ? t('backup_password_wrong') : t('backup_password_enter'),
            placeholder: t('backup_password_placeholder_short'), type: 'password', okLabel: t('backup_unlock'),
          });
          if (!pw) { setBackupStatus(''); return; }
          password = pw;
        } else throw err;
      }
    }
    const mode = await showImportConfirm(manifest);
    if (!mode) { setBackupStatus(''); return; }
    setBackupStatus(t('backup_importing', mode));
    const result = await importBackup(bytes, mode, password);
    setBackupStatus(
      t('backup_import_result', result.conversations_added, result.conversations_skipped, result.messages_imported),
      'ok',
    );
    refreshChatList();
  } catch (err) {
    setBackupStatus(t('backup_import_failed', err.message), 'error');
  }
});

async function peekBackup(buf, password) {
  const fd = new FormData();
  fd.append('file', new Blob([buf]), 'backup.zip');
  const q = password ? `?password=${encodeURIComponent(password)}` : '';
  return api('POST', '/backup/peek' + q, fd);
}
async function importBackup(buf, mode, password) {
  const fd = new FormData();
  fd.append('file', new Blob([buf]), 'backup.zip');
  const params = new URLSearchParams({ mode });
  if (password) params.set('password', password);
  return api('POST', '/backup/import?' + params, fd);
}

function showImportConfirm(m) {
  return new Promise(resolve => {
    const o = document.createElement('div');
    o.className = 'modal';
    o.innerHTML = `
      <div class="modal-card small">
        <div class="modal-header"><h2>${escapeHtml(t('backup_import_title'))}</h2></div>
        <div class="modal-body">
          <p style="margin:0 0 4px">${t('backup_import_summary', m.conversation_count, m.message_count, m.attachment_count)}</p>
          <p style="margin:0 0 14px;color:var(--text-muted);font-size:12px">${escapeHtml(t('backup_import_meta', m.created_at.replace('T',' ').substring(0,19), m.server_version))}</p>
          <p style="margin:0;font-size:13px">${t('backup_import_modes')}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-ghost" data-act="cancel">${escapeHtml(t('cancel'))}</button>
          <button class="btn-secondary" data-act="merge">${escapeHtml(t('backup_merge'))}</button>
          <button class="btn-primary" data-act="replace" style="background:var(--danger)">${escapeHtml(t('backup_replace'))}</button>
        </div>
      </div>`;
    document.body.appendChild(o);
    o.addEventListener('click', (e) => {
      const a = e.target.closest('[data-act]')?.dataset.act;
      if (!a) return;
      o.remove();
      resolve(a === 'cancel' ? null : a);
    });
  });
}

function setBackupStatus(text, cls = '') {
  els.backupStatus.textContent = text;
  els.backupStatus.className = 'backup-status ' + cls;
}

// =========================================================
// Prompt-Modal (Passwort/Confirm)
// =========================================================
function showPrompt({ title, text, placeholder = '', type = 'password', okLabel = 'OK' }) {
  return new Promise(resolve => {
    els.promptTitle.textContent = title;
    els.promptText.textContent = text;
    els.promptInput.type = type;
    els.promptInput.placeholder = placeholder;
    els.promptInput.value = '';
    els.promptOk.textContent = okLabel;
    els.promptModal.classList.remove('hidden');
    els.promptInput.focus();
    const close = (val) => {
      els.promptModal.classList.add('hidden');
      els.promptOk.onclick = null;
      els.promptCancel.onclick = null;
      els.promptInput.onkeydown = null;
      resolve(val);
    };
    els.promptOk.onclick = () => close(els.promptInput.value);
    els.promptCancel.onclick = () => close(null);
    els.promptInput.onkeydown = (e) => {
      if (e.key === 'Enter') { e.preventDefault(); close(els.promptInput.value); }
      if (e.key === 'Escape') { e.preventDefault(); close(null); }
    };
  });
}

// =========================================================
// /me + User-Verwaltung
// =========================================================
function renderFooterUser() {
  const el = document.getElementById('footer-user');
  if (!el) return;
  if (!state.me) { el.innerHTML = ''; return; }
  const initials = (state.me.name || '?').trim().slice(0, 1).toUpperCase();
  el.innerHTML = `
    <div class="avatar">${escapeHtml(initials)}</div>
    <div class="name">${escapeHtml(state.me.name)}</div>
    ${state.me.is_admin ? `<span class="badge">${escapeHtml(t('admin_label'))}</span>` : ''}`;
}

function applyAdminVisibility() {
  const isAdmin = !!(state.me && state.me.is_admin);
  document.querySelectorAll('.admin-only').forEach(el => {
    el.classList.toggle('hidden', !isAdmin);
  });
  // Backup-Hint anpassen
  const hint = document.getElementById('backup-hint');
  if (hint) {
    hint.textContent = isAdmin
      ? t('backup_hint_admin')
      : t('backup_hint_user');
  }
  // Import-Button nur für Admin
  const importBtn = document.getElementById('backup-import-btn');
  if (importBtn) importBtn.style.display = isAdmin ? '' : 'none';
}

async function loadUsersList() {
  if (!(state.me && state.me.is_admin)) return;
  try {
    const r = await api('GET', '/users');
    const wrap = document.getElementById('users-list');
    wrap.innerHTML = '';
    for (const u of r.users) {
      const row = document.createElement('div');
      row.className = 'user-row';
      const statusLabel = u.must_change_password
        ? `<span class="badge warn" title="${escapeHtml(t('user_pw_reset_due_title'))}">${escapeHtml(t('user_pw_reset_due'))}</span>`
        : '';
      row.innerHTML = `
        <span class="name">${escapeHtml(u.name)}</span>
        ${u.is_admin ? `<span class="badge">${escapeHtml(t('admin_label'))}</span>` : ''}
        ${statusLabel}
        <span class="user-spacer"></span>
        <span class="actions">
          <button class="icon-btn" data-act="reset" title="${escapeHtml(t('reset_password_title'))}"><svg class="icon"><use href="#icon-settings"/></svg></button>
          ${u.id === state.me.id ? '' : `<button class="icon-btn" data-act="delete" title="${escapeHtml(t('delete'))}"><svg class="icon"><use href="#icon-trash"/></svg></button>`}
        </span>`;
      const resetBtn = row.querySelector('[data-act="reset"]');
      if (resetBtn) resetBtn.onclick = async () => {
        const custom = prompt(t('user_reset_pw_prompt', u.name), '');
        if (custom === null) return;
        const body = custom.trim() ? { password: custom.trim() } : {};
        try {
          const resp = await api('POST', '/users/' + u.id + '/reset-password', body);
          await loadUsersList();
          // Neues Passwort 1× im UI zeigen + in Zwischenablage
          const pw = resp.new_password;
          try { await navigator.clipboard.writeText(pw); } catch {}
          alert(t('user_reset_pw_alert', u.name, pw));
        } catch (e) { toast(t('toast_reset_failed', e.message), { error: true }); }
      };
      const delBtn = row.querySelector('[data-act="delete"]');
      if (delBtn) delBtn.onclick = async () => {
        if (!confirm(t('confirm_delete_user', u.name))) return;
        try { await api('DELETE', '/users/' + u.id); await loadUsersList(); toast(t('toast_deleted')); }
        catch (e) { toast(t('toast_delete_failed', e.message), { error: true }); }
      };
      wrap.appendChild(row);
    }
  } catch (e) {
    toast(t('toast_user_list_failed', e.message), { error: true });
  }
}

const newUserBtn = document.getElementById('new-user-btn');
if (newUserBtn) {
  newUserBtn.addEventListener('click', async () => {
    const nameInp  = document.getElementById('new-user-name');
    const pwInp    = document.getElementById('new-user-password');
    const adminChk = document.getElementById('new-user-admin');
    const resultEl = document.getElementById('new-user-result');
    const name = nameInp.value.trim();
    const pw   = pwInp.value.trim();
    if (!name) return;
    if (pw && pw.length < 8) {
      toast(t('toast_password_min_chars'), { error: true });
      return;
    }
    try {
      const body = { name, is_admin: adminChk.checked };
      if (pw) body.password = pw;
      const u = await api('POST', '/users', body);
      nameInp.value = ''; pwInp.value = ''; adminChk.checked = false;
      await loadUsersList();
      const initial = u.initial_password;
      if (initial) {
        try { await navigator.clipboard.writeText(initial); } catch {}
        resultEl.className = 'backup-status ok';
        resultEl.innerHTML = t('user_create_success', escapeHtml(name), escapeHtml(initial));
      } else {
        resultEl.className = 'backup-status ok';
        resultEl.textContent = t('user_create_success_no_pw', name);
      }
    } catch (e) {
      resultEl.className = 'backup-status error';
      resultEl.textContent = t('user_create_failed', e.message);
    }
  });
}

// "Mein Konto" — Passwort ändern + Aus allen Geräten ausloggen
const changePwBtn = document.getElementById('change-pw-btn');
if (changePwBtn) changePwBtn.addEventListener('click', () => openPasswordChange({ forced: false }));
const logoutAllBtn = document.getElementById('logout-all-btn');
if (logoutAllBtn) logoutAllBtn.addEventListener('click', async () => {
  if (!confirm(t('confirm_logout_all'))) return;
  try {
    await api('POST', '/auth/logout-all');
    localStorage.removeItem(LS.token);
    state.token = '';
    location.reload();
  } catch (e) { toast(t('toast_logout_all_failed', e.message), { error: true }); }
});

// Beim Öffnen der Settings: Username, User-Liste, Image-Key-Status
const oldOpenSettings = openSettings;
openSettings = async function() {
  await oldOpenSettings();
  const nameEl = document.getElementById('my-account-name');
  if (nameEl && state.me) nameEl.textContent = state.me.name;
  if (state.me && state.me.is_admin) await loadUsersList();
  await loadImageKeyStatus();
};

// =========================================================
// Settings → Bilder: API-Key verwalten
// =========================================================
async function loadImageKeyStatus() {
  try {
    const cfg = await api('GET', '/images/config');
    imageState.config = cfg;
    imageState.configLoaded = true;
    const st = document.getElementById('image-api-key-status');
    if (cfg.configured) {
      st.className = 'backup-status ok';
      st.innerHTML = t('image_key_set', `<code>${escapeHtml(cfg.api_key_masked || '')}</code>`);
    } else {
      st.className = 'backup-status';
      st.textContent = t('image_key_not_set');
    }
  } catch (e) {
    // tolerieren — Server vielleicht älter
  }
}

const imgKeyInput  = document.getElementById('image-api-key-input');
const imgKeySave   = document.getElementById('image-api-key-save');
const imgKeyDelete = document.getElementById('image-api-key-delete');
if (imgKeySave) imgKeySave.addEventListener('click', async () => {
  const key = (imgKeyInput.value || '').trim();
  if (!key) return;
  try {
    await api('PUT', '/images/credentials', { api_key: key });
    imgKeyInput.value = '';
    toast(t('toast_api_key_saved'));
    await loadImageKeyStatus();
    // Wenn aktuell Image-Mode an ist: Status nachschieben
    if (imageState.enabled) setImageStatus(t('image_key_saved_hint'), '');
  } catch (e) {
    toast(t('toast_save_failed', e.message), { error: true });
  }
});
if (imgKeyDelete) imgKeyDelete.addEventListener('click', async () => {
  if (!confirm(t('confirm_remove_api_key'))) return;
  try {
    await api('DELETE', '/images/credentials');
    imgKeyInput.value = '';
    toast(t('toast_removed'));
    await loadImageKeyStatus();
  } catch (e) {
    toast(t('toast_error_prefix', e.message), { error: true });
  }
});

// ───────────────────────────────────────────────────────────────
// i18n bootstrap
// ───────────────────────────────────────────────────────────────
(function initI18n() {
  if (!window.PocketI18n) return;
  // Apply current locale to all data-i18n* nodes already in the DOM.
  window.PocketI18n.applyI18n();
  // Wire the language picker in the settings modal.
  const sel = document.getElementById('ui-locale-select');
  if (sel) {
    const stored = window.localStorage.getItem('pc_locale') || '';
    sel.value = stored;
    sel.addEventListener('change', () => {
      window.PocketI18n.setLocale(sel.value);
    });
  }
})();

// ───────────────────────────────────────────────────────────────
// Claude auth-mode picker + usage widget
// ───────────────────────────────────────────────────────────────
(function initClaudeAuthAndUsage() {
  const $ = (id) => document.getElementById(id);
  const t = (k, ...args) => (window.PocketI18n ? window.PocketI18n.t(k, ...args) : k);

  async function loadClaudeAuth() {
    try {
      const r = await fetch('/me/claude-auth', { headers: { Authorization: 'Bearer ' + (localStorage.getItem('pc.serverToken') || '') } });
      if (!r.ok) return;
      const data = await r.json();
      const mode = data.mode || 'pro_max';

      // Radio buttons
      document.querySelectorAll('input[name="claude-auth-mode"]').forEach((el) => {
        el.checked = (el.value === mode);
      });
      // Hint
      const hintMap = {
        pro_max: 'claude_mode_pro_max_hint',
        api_key: 'claude_mode_api_key_hint',
        bedrock: 'claude_mode_bedrock_hint',
      };
      $('claude-auth-mode-hint').textContent = t(hintMap[mode] || hintMap.pro_max);

      // Show/hide forms
      $('claude-auth-apikey-form').classList.toggle('hidden', mode !== 'api_key');
      $('claude-auth-bedrock-form').classList.toggle('hidden', mode !== 'bedrock');

      // Populate API-key "current"
      const apikeyCurrent = data.api_key_set
        ? t('current_value_label', data.api_key_masked)
        : t('not_configured');
      $('claude-auth-apikey-current').textContent = apikeyCurrent;

      // Populate Bedrock fields
      $('bedrock-region').value = data.aws_region || '';
      $('bedrock-akid').value = '';  // never prefill secrets — show masked next to label
      $('bedrock-secret').value = '';
      $('bedrock-session').value = '';
      $('bedrock-opus').value = data.bedrock_opus_model || '';
      $('bedrock-sonnet').value = data.bedrock_sonnet_model || '';
      $('bedrock-haiku').value = data.bedrock_haiku_model || '';
      document.querySelectorAll('input[name="bedrock-alias"]').forEach((el) => {
        el.checked = (el.value === (data.bedrock_model_alias || 'opus'));
      });
    } catch (e) { /* not signed in yet */ }
  }

  async function putClaudeAuth(payload) {
    const r = await fetch('/me/claude-auth', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + (localStorage.getItem('pc.serverToken') || ''),
      },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const msg = await r.text();
      throw new Error(`HTTP ${r.status}: ${msg}`);
    }
    return r.json();
  }

  // Wire radio buttons → switch mode
  document.querySelectorAll('input[name="claude-auth-mode"]').forEach((el) => {
    el.addEventListener('change', async () => {
      try {
        await putClaudeAuth({ mode: el.value });
        await loadClaudeAuth();
      } catch (e) {
        $('claude-auth-status').textContent = t('toast_error_prefix', e.message);
      }
    });
  });

  // Anthropic API key save/clear
  if ($('claude-anthropic-save')) {
    $('claude-anthropic-save').addEventListener('click', async () => {
      const key = $('claude-anthropic-key').value.trim();
      if (!key) return;
      try {
        await putClaudeAuth({ api_key: key });
        $('claude-anthropic-key').value = '';
        $('claude-auth-status').textContent = t('saved');
        await loadClaudeAuth();
      } catch (e) {
        $('claude-auth-status').textContent = t('toast_error_prefix', e.message);
      }
    });
  }
  if ($('claude-anthropic-clear')) {
    $('claude-anthropic-clear').addEventListener('click', async () => {
      if (!confirm(t('confirm_remove_api_key'))) return;
      try {
        await putClaudeAuth({ api_key: '' });
        await loadClaudeAuth();
      } catch (e) {
        $('claude-auth-status').textContent = t('toast_error_prefix', e.message);
      }
    });
  }

  // Bedrock apply
  if ($('bedrock-apply')) {
    $('bedrock-apply').addEventListener('click', async () => {
      const alias = (document.querySelector('input[name="bedrock-alias"]:checked') || {}).value;
      const body = {
        aws_region: $('bedrock-region').value.trim() || null,
        aws_access_key_id: $('bedrock-akid').value.trim() || null,
        aws_secret_access_key: $('bedrock-secret').value || null,
        aws_session_token: $('bedrock-session').value || null,
        bedrock_opus_model: $('bedrock-opus').value.trim() || null,
        bedrock_sonnet_model: $('bedrock-sonnet').value.trim() || null,
        bedrock_haiku_model: $('bedrock-haiku').value.trim() || null,
        bedrock_model_alias: alias || null,
      };
      // Remove null keys
      Object.keys(body).forEach((k) => body[k] === null && delete body[k]);
      try {
        await putClaudeAuth(body);
        $('bedrock-akid').value = '';
        $('bedrock-secret').value = '';
        $('bedrock-session').value = '';
        $('claude-auth-status').textContent = t('saved');
        await loadClaudeAuth();
      } catch (e) {
        $('claude-auth-status').textContent = t('toast_error_prefix', e.message);
      }
    });
  }
  document.querySelectorAll('input[name="bedrock-alias"]').forEach((el) => {
    el.addEventListener('change', async () => {
      try { await putClaudeAuth({ bedrock_model_alias: el.value }); await loadClaudeAuth(); }
      catch (e) { $('claude-auth-status').textContent = t('toast_error_prefix', e.message); }
    });
  });

  async function loadUsage() {
    try {
      const r = await fetch('/me/usage?period=month', { headers: { Authorization: 'Bearer ' + (localStorage.getItem('pc.serverToken') || '') } });
      if (!r.ok) return;
      const u = await r.json();
      const grid = $('usage-grid');
      grid.innerHTML = '';
      const fmt = (n) => {
        if (n < 1000) return String(n);
        if (n < 1_000_000) return (n / 1000).toFixed(1) + 'K';
        return (n / 1_000_000).toFixed(2) + 'M';
      };
      const rows = [
        [t('usage_input'), fmt(u.input_tokens)],
        [t('usage_output'), fmt(u.output_tokens)],
        [t('usage_cache_create'), fmt(u.cache_create_tokens)],
        [t('usage_cache_read'), fmt(u.cache_read_tokens)],
        [t('usage_requests'), fmt(u.request_count)],
      ];
      if (u.provider) rows.push([t('usage_provider'), u.provider]);
      rows.forEach(([label, val]) => {
        const l = document.createElement('div'); l.textContent = label; l.style.color = 'var(--text-soft)';
        const v = document.createElement('div'); v.textContent = val; v.style.fontWeight = '500'; v.style.textAlign = 'right';
        grid.appendChild(l); grid.appendChild(v);
      });
      const proMaxNote = $('usage-pro-max-note');
      if (proMaxNote) proMaxNote.style.display = (u.provider === 'pro_max' || u.provider === '') ? '' : 'none';
    } catch (e) { /* ignore */ }
  }

  if ($('usage-refresh')) {
    $('usage-refresh').addEventListener('click', loadUsage);
  }

  // Trigger initial loads when the settings modal is opened. No setTimeout
  // needed — the modal is already in the DOM, openSettings just toggles
  // the .hidden class, so we can fetch immediately.
  const settingsBtn = $('settings-btn');
  if (settingsBtn) {
    settingsBtn.addEventListener('click', () => {
      loadClaudeAuth();
      loadUsage();
    });
  }

  // Also clear stale status text whenever the modal closes — keeps users
  // from seeing yesterday's "Error: …" the next time they reopen settings.
  const settingsClose = $('settings-close');
  if (settingsClose) {
    settingsClose.addEventListener('click', () => {
      const s = $('claude-auth-status');
      if (s) s.textContent = '';
    });
  }
})();

// =========================================================
// Voice-Input (Groq Whisper Large v3 Turbo)
// =========================================================
//
// Spiegelt die App-Logik 1:1 (Recording → Upload → Transcript ins Input;
// optional Auto-Mode-Loop). Aufnahme über MediaRecorder + getUserMedia
// (im Browser meist webm/opus); der Server akzeptiert beliebige Audio-
// Container, Groq erkennt das Format selbst.
window.PocketVoice = (() => {
  const $ = (id) => document.getElementById(id);
  const t = (k, ...args) => (window.PocketI18n ? window.PocketI18n.t(k, ...args) : k);

  const micBtn    = $('mic-btn');
  const autoPill  = $('auto-mode-pill');
  const autoLabel = $('auto-mode-label');
  const input     = $('input');

  let mediaRecorder = null;
  let mediaStream = null;
  let chunks = [];
  let micState = 'idle'; // idle | recording | busy
  let autoMode = false;
  let autoAbortController = null;

  // ── LLM-Busy-Check ──
  // `state` ist der globale Chat-State aus app.js (selber File-Scope).
  // Wir greifen direkt drauf zu. isStreaming = Stream läuft;
  // state.audio.playing = TTS spielt grade.
  function isLlmBusy() {
    return !!(state && (state.isStreaming || (state.audio && state.audio.playing)));
  }

  function setMicState(newState) {
    micState = newState;
    if (!micBtn) return;
    micBtn.classList.remove('idle', 'recording', 'busy');
    micBtn.classList.add(newState);
    micBtn.title = newState === 'recording'
        ? t('voice_mic_recording_title')
        : t('voice_mic_title');
    updateMicEnabled();
  }

  /** Mic-Button visuell + funktional disablen wenn LLM busy. Recording
   *  läuft DARF weiter klickbar bleiben (User muss stoppen können). */
  function updateMicEnabled() {
    if (!micBtn) return;
    const shouldDisable = isLlmBusy() && micState !== 'recording';
    micBtn.disabled = shouldDisable;
    micBtn.classList.toggle('mic-disabled', shouldDisable);
  }

  function setAutoModeUi(on) {
    autoMode = on;
    if (autoPill) autoPill.classList.toggle('hidden', !on);
    if (autoLabel) autoLabel.textContent = on ? t('auto_mode_stop') : t('auto_mode_start');
  }

  async function startRecording() {
    if (micState !== 'idle') return false;
    if (isLlmBusy()) {
      toast(t('voice_error_llm_busy'), { error: true });
      return false;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      toast(t('voice_error_no_permission'), { error: true });
      return false;
    }
    chunks = [];
    const opts = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? { mimeType: 'audio/webm;codecs=opus' }
        : {};
    try {
      mediaRecorder = new MediaRecorder(mediaStream, opts);
    } catch (e) {
      stopStream();
      toast(t('voice_error_start_failed', e.message), { error: true });
      return false;
    }
    mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    mediaRecorder.onstop = () => { /* upload triggert die Caller-Logik */ };
    mediaRecorder.start();
    setMicState('recording');
    return true;
  }

  function stopStream() {
    if (mediaStream) {
      mediaStream.getTracks().forEach((tr) => tr.stop());
      mediaStream = null;
    }
    mediaRecorder = null;
  }

  /** Stoppt die Aufnahme und lädt das Audio hoch. Liefert den Transkript-Text
   *  zurück (oder leeren String bei zu kurzer Aufnahme / Fehler). */
  async function stopAndTranscribe() {
    if (micState !== 'recording' || !mediaRecorder) return '';
    const rec = mediaRecorder;
    const done = new Promise((resolve) => {
      rec.addEventListener('stop', resolve, { once: true });
    });
    rec.stop();
    await done;
    const mime = rec.mimeType || 'audio/webm';
    const blob = new Blob(chunks, { type: mime });
    stopStream();
    chunks = [];
    if (blob.size < 1000) {
      setMicState('idle');
      return '';
    }
    setMicState('busy');
    try {
      const locale = (window.localStorage.getItem('pc_locale') || '').trim() ||
                     (navigator.language || 'en');
      const fd = new FormData();
      const ext = mime.includes('webm') ? 'webm' : (mime.includes('mp4') ? 'm4a' : 'wav');
      fd.append('file', blob, `voice-${Date.now()}.${ext}`);
      fd.append('language', locale);
      const r = await fetch('/voice/transcribe', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + (localStorage.getItem('pc.serverToken') || '') },
        body: fd,
      });
      if (!r.ok) {
        const text = await r.text().catch(() => '');
        throw new Error(text || ('HTTP ' + r.status));
      }
      const data = await r.json();
      setMicState('idle');
      return (data.text || '').trim();
    } catch (e) {
      setMicState('idle');
      toast(t('voice_error_transcribe_failed', e.message), { error: true });
      return '';
    }
  }

  function cancelRecording() {
    if (micState !== 'recording' && micState !== 'busy') return;
    try { if (mediaRecorder) mediaRecorder.stop(); } catch (_) {}
    stopStream();
    chunks = [];
    setMicState('idle');
  }

  function insertTranscript(text) {
    if (!text || !input) return;
    if ((input.value || '').trim().length === 0) input.value = text;
    else input.value = input.value + ' ' + text;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
  }

  /** Vom openChat-Aufrufer beim Chat-Wechsel: AUFNAHME ABBRECHEN + Auto-Mode
   *  ausschalten + jedes laufende Upload-Promise auflösen. Sonst hängt der
   *  Singleton-Recorder weiter im alten Chat. */
  function resetForChatSwitch() {
    if (autoMode) {
      setAutoModeUi(false);
      if (autoAbortController) autoAbortController.abort();
    }
    if (micState === 'recording' || micState === 'busy') cancelRecording();
    setMicState('idle');
  }

  // ── Auto-Mode ──
  // Phasen analog zur App: 0) waitUntilSettled (kein Stream / kein TTS)
  //   1) Recording starten 2) auf User-Stop warten 3) auf Transcribe-Idle
  //   4) Buffer 5) auf Stream-Ende 6) auf TTS-Ende → loop.
  // Wichtig: NIE während LLM-Busy starten — sonst landet die TTS-Ausgabe
  // im nächsten Recording.
  async function toggleAutoMode() {
    if (autoMode) {
      setAutoModeUi(false);
      if (autoAbortController) autoAbortController.abort();
      if (micState === 'recording' || micState === 'busy') cancelRecording();
      return;
    }
    setAutoModeUi(true);
    autoAbortController = new AbortController();
    const signal = autoAbortController.signal;
    try {
      while (autoMode && !signal.aborted) {
        // Phase 0: alles ruhig kriegen
        await waitUntilSettled(signal);
        if (signal.aborted) break;

        // Phase 1: Recording starten
        const ok = await startRecording();
        if (!ok || signal.aborted) break;

        // Phase 2: User-Stop abwarten (er klickt Mic erneut → busy → idle)
        await pollUntil(() => micState !== 'recording' || signal.aborted, 150);
        if (signal.aborted) break;

        // Phase 3: Transcribe-Ende abwarten
        await pollUntil(() => micState !== 'busy' || signal.aborted, 150);
        if (signal.aborted) break;

        // Phase 4: Buffer — der Mic-Click-Handler ruft form.requestSubmit()
        // erst NACH stopAndTranscribe. Wir warten kurz dass submitForm()
        // seinen Stream gestartet hat (state.isStreaming = true).
        await sleep(400);

        // Phase 5: Stream-Ende
        await pollUntil(() => !state.isStreaming || signal.aborted, 200);
        if (signal.aborted) break;

        // Phase 6: TTS-Wiedergabe abwarten (auto-speak via Done-Event)
        await sleep(400);
        await pollUntil(() => {
          if (signal.aborted) return true;
          const audios = Array.from(document.querySelectorAll('audio'));
          const anyPlaying = audios.some((a) => !a.paused && !a.ended);
          return !anyPlaying && !(state.audio && state.audio.playing);
        }, 300);
      }
    } catch (_) { /* abort */ }
    finally { setAutoModeUi(false); }
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function pollUntil(predicate, intervalMs) {
    return new Promise((resolve) => {
      const check = () => {
        try { if (predicate()) return resolve(); } catch (_) { return resolve(); }
        setTimeout(check, intervalMs);
      };
      check();
    });
  }

  async function waitUntilSettled(signal) {
    return pollUntil(() => {
      if (signal && signal.aborted) return true;
      if (micState !== 'idle') return false;
      if (state.isStreaming) return false;
      if (state.audio && state.audio.playing) return false;
      // Auch HTML-<audio>-Elemente checken, falls TTS via DOM-Audio läuft
      const audios = Array.from(document.querySelectorAll('audio'));
      if (audios.some((a) => !a.paused && !a.ended)) return false;
      return true;
    }, 200);
  }

  // Mic-Click-Handler: tap toggelt Recording↔Upload. Long-Press (>700 ms)
  // während Recording bricht ab statt zu transkribieren.
  if (micBtn) {
    let pressTimer = null;
    let longPressed = false;
    micBtn.addEventListener('mousedown', () => {
      longPressed = false;
      pressTimer = setTimeout(() => {
        longPressed = true;
        if (micState === 'recording') cancelRecording();
      }, 700);
    });
    micBtn.addEventListener('mouseup', () => {
      clearTimeout(pressTimer); pressTimer = null;
    });
    micBtn.addEventListener('mouseleave', () => {
      clearTimeout(pressTimer); pressTimer = null;
    });
    micBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      if (longPressed) { longPressed = false; return; }
      if (micState === 'idle') {
        if (isLlmBusy()) {
          toast(t('voice_error_llm_busy'), { error: true });
          return;
        }
        await startRecording();
      } else if (micState === 'recording') {
        const text = await stopAndTranscribe();
        if (text) {
          insertTranscript(text);
          // submit nur wenn nicht grade ein Stream läuft (Race-Schutz)
          if (!state.isStreaming) {
            const form = document.getElementById('input-form');
            if (form) form.requestSubmit();
          }
        }
      }
    });
  }

  // Auto-Mode-Pill: Klick = Loop stoppen.
  if (autoPill) {
    autoPill.addEventListener('click', () => toggleAutoMode());
  }

  // Polling-Watcher: alle 400 ms updateMicEnabled aufrufen, damit der Button
  // bei Stream-Ende / TTS-Ende wieder freigeschaltet wird ohne dass wir
  // jeden State-Setter patchen muessen.
  setInterval(updateMicEnabled, 400);

  // Voice-API-Key Save/Delete + Language-Picker + Translate-Status
  const voiceKeyInput  = document.getElementById('voice-api-key-input');
  const voiceKeySave   = document.getElementById('voice-api-key-save');
  const voiceKeyDelete = document.getElementById('voice-api-key-delete');
  const voiceKeyStatus = document.getElementById('voice-api-key-status');

  const langModeAuto      = document.getElementById('voice-lang-mode-auto');
  const langModeOverride  = document.getElementById('voice-lang-mode-override');
  const langOverrideBlock = document.getElementById('voice-lang-override-block');
  const langSelect        = document.getElementById('voice-lang-select');
  const langCustomInput   = document.getElementById('voice-lang-custom');
  const langApplyBtn      = document.getElementById('voice-lang-apply');
  const translateStatus   = document.getElementById('voice-translate-status');
  const promptText        = document.getElementById('voice-prompt-text');
  const promptLabel       = document.getElementById('voice-prompt-label');
  const promptSource      = document.getElementById('voice-prompt-source');
  const promptActions     = document.getElementById('voice-prompt-actions');
  const retranslateBtn    = document.getElementById('voice-retranslate-btn');
  const resetCacheBtn     = document.getElementById('voice-reset-cache-btn');

  const CUSTOM_SENTINEL = '__custom__';
  let lastCfg = null;

  function renderVoiceCfg(cfg) {
    lastCfg = cfg;
    if (voiceKeyStatus) {
      if (cfg.configured) {
        voiceKeyStatus.textContent = `✓ ${cfg.api_key_masked || ''} · ${cfg.model || ''}`;
      } else {
        voiceKeyStatus.textContent = t('voice_key_not_set');
      }
    }
    // Mode-Radios
    const isOverride = cfg.lang_mode === 'override';
    if (langModeAuto) langModeAuto.checked = !isOverride;
    if (langModeOverride) langModeOverride.checked = isOverride;
    if (langOverrideBlock) langOverrideBlock.classList.toggle('hidden', !isOverride);

    // Dropdown populieren (einmalig pro Render)
    if (langSelect) {
      langSelect.innerHTML = '';
      const langs = (cfg.bundled_languages || []).slice().sort((a, b) => {
        const an = (cfg.language_names || {})[a] || a;
        const bn = (cfg.language_names || {})[b] || b;
        return an.localeCompare(bn);
      });
      for (const code of langs) {
        const name = (cfg.language_names || {})[code] || code;
        const opt = document.createElement('option');
        opt.value = code;
        opt.textContent = `${name} (${code})`;
        langSelect.appendChild(opt);
      }
      // Cached aber nicht-bundled Sprachen mit "translated"-Marker auflisten
      for (const code of (cfg.cached_languages || [])) {
        if (!(cfg.bundled_languages || []).includes(code)) {
          const opt = document.createElement('option');
          opt.value = code;
          opt.textContent = `${code} — ${t('voice_lang_tag_translated')}`;
          langSelect.appendChild(opt);
        }
      }
      const customOpt = document.createElement('option');
      customOpt.value = CUSTOM_SENTINEL;
      customOpt.textContent = t('voice_lang_custom');
      langSelect.appendChild(customOpt);

      // Auswahl setzen
      const current = cfg.lang_override || cfg.current_lang || 'en';
      const isCustom = isOverride && !langs.includes(current) && !(cfg.cached_languages || []).includes(current);
      if (isCustom) {
        langSelect.value = CUSTOM_SENTINEL;
        if (langCustomInput) { langCustomInput.value = current || ''; langCustomInput.classList.remove('hidden'); }
        if (langApplyBtn) langApplyBtn.classList.remove('hidden');
      } else {
        langSelect.value = current;
        if (langCustomInput) { langCustomInput.classList.add('hidden'); }
        if (langApplyBtn) langApplyBtn.classList.add('hidden');
      }
    }

    // Prompt-Preview
    if (promptText) promptText.textContent = cfg.current_prompt || '';
    if (promptLabel) promptLabel.textContent = t('voice_prompt_preview_label', cfg.current_lang || 'en');
    if (promptSource) {
      const map = {
        bundled: t('voice_lang_tag_bundled'),
        cache: t('voice_lang_tag_translated'),
        fallback: t('voice_lang_tag_fallback'),
      };
      promptSource.textContent = map[cfg.current_prompt_source] || cfg.current_prompt_source || '';
    }
    if (promptActions) promptActions.classList.toggle('hidden', cfg.current_prompt_source !== 'cache');
  }

  async function loadVoiceConfig() {
    try {
      const cfg = await api('GET', '/voice/config');
      renderVoiceCfg(cfg);
    } catch (_) { /* tolerieren */ }
  }

  async function setLangConfig(mode, locale) {
    try {
      const cfg = await api('PUT', '/voice/lang-config', { mode, locale: locale || null });
      renderVoiceCfg(cfg);
      // Wenn override + nicht-bundled + nicht-cached → automatisch übersetzen
      if (mode === 'override' && cfg.current_prompt_source === 'fallback') {
        await translatePrompt(cfg.current_lang, false);
      } else if (translateStatus) {
        translateStatus.textContent = '';
      }
    } catch (e) {
      if (translateStatus) {
        translateStatus.textContent = t('voice_translate_error', e.message);
        translateStatus.style.color = 'var(--danger, #d33)';
      }
    }
  }

  async function translatePrompt(locale, force) {
    if (!locale) return;
    if (translateStatus) {
      translateStatus.style.color = '';
      translateStatus.textContent = t('voice_translate_running');
    }
    try {
      await api('POST', '/voice/prompt/translate', { locale, force: !!force });
      if (translateStatus) {
        translateStatus.style.color = 'var(--accent)';
        translateStatus.textContent = t('voice_translate_success');
      }
      await loadVoiceConfig();
    } catch (e) {
      if (translateStatus) {
        translateStatus.style.color = 'var(--danger, #d33)';
        translateStatus.textContent = t('voice_translate_error', e.message);
      }
    }
  }

  // ── Events ──
  if (langModeAuto) langModeAuto.addEventListener('change', () => {
    if (langModeAuto.checked) setLangConfig('auto', null);
  });
  if (langModeOverride) langModeOverride.addEventListener('change', () => {
    if (langModeOverride.checked) {
      // Beim ersten Wechsel auf Override gleich die ausgewählte Locale aus dem
      // Dropdown anwenden (oder Default zur App-Sprache)
      const v = (langSelect && langSelect.value && langSelect.value !== CUSTOM_SENTINEL)
                  ? langSelect.value
                  : (lastCfg && lastCfg.current_lang) || 'en';
      setLangConfig('override', v);
    }
  });
  if (langSelect) langSelect.addEventListener('change', () => {
    const v = langSelect.value;
    if (v === CUSTOM_SENTINEL) {
      langCustomInput && langCustomInput.classList.remove('hidden');
      langApplyBtn && langApplyBtn.classList.remove('hidden');
      return;
    }
    langCustomInput && langCustomInput.classList.add('hidden');
    langApplyBtn && langApplyBtn.classList.add('hidden');
    setLangConfig('override', v);
  });
  if (langApplyBtn) langApplyBtn.addEventListener('click', () => {
    const v = (langCustomInput && langCustomInput.value || '').trim().toLowerCase();
    if (v.length < 2) return;
    setLangConfig('override', v);
  });
  if (retranslateBtn) retranslateBtn.addEventListener('click', () => {
    if (lastCfg) translatePrompt(lastCfg.current_lang, true);
  });
  if (resetCacheBtn) resetCacheBtn.addEventListener('click', async () => {
    if (!lastCfg) return;
    try {
      await api('DELETE', '/voice/prompt/cache/' + encodeURIComponent(lastCfg.current_lang));
      await loadVoiceConfig();
      if (translateStatus) translateStatus.textContent = '';
    } catch (e) {
      toast(t('toast_error_prefix', e.message), { error: true });
    }
  });

  if (voiceKeySave) voiceKeySave.addEventListener('click', async () => {
    const key = (voiceKeyInput.value || '').trim();
    if (!key) return;
    try {
      await api('PUT', '/voice/credentials', { api_key: key });
      voiceKeyInput.value = '';
      toast(t('toast_api_key_saved'));
      await loadVoiceConfig();
    } catch (e) {
      toast(t('toast_save_failed', e.message), { error: true });
    }
  });
  if (voiceKeyDelete) voiceKeyDelete.addEventListener('click', async () => {
    if (!confirm(t('confirm_remove_api_key'))) return;
    try {
      await api('DELETE', '/voice/credentials');
      voiceKeyInput.value = '';
      toast(t('toast_removed'));
      await loadVoiceConfig();
    } catch (e) {
      toast(t('toast_error_prefix', e.message), { error: true });
    }
  });
  // beim Öffnen der Settings nachladen
  const settingsBtn = document.getElementById('settings-btn');
  if (settingsBtn) settingsBtn.addEventListener('click', loadVoiceConfig);
  // initial einmal
  loadVoiceConfig();

  setMicState('idle');
  return { toggleAutoMode, resetForChatSwitch };
})();
