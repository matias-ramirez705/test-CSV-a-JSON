// utils.js — funciones compartidas
window.fmtDuration = function(seconds) {
  seconds = parseInt(seconds || 0, 10);
  if (seconds >= 3600) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  }
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2,'0')}`;
};

window.fmtBytes = function(bytes) {
  if (!bytes) return '0 B';
  const units = ['B','KB','MB','GB'];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
  return `${bytes.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
};

window.fmtDate = function(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' });
  } catch { return iso; }
};

window.toast = function(msg, type = 'info', title = '') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `
    <div style="flex:1">
      ${title ? `<div class="title">${title}</div>` : ''}
      <div class="msg">${msg}</div>
    </div>
    <button class="btn btn-ghost btn-icon btn-sm" onclick="this.parentElement.remove()">✕</button>
  `;
  container.appendChild(t);
  setTimeout(() => {
    if (t.parentElement) t.remove();
  }, 6000);
};

window.openModal = function(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add('show');
};
window.closeModal = function(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove('show');
};

// Cerrar modal al click fuera
document.addEventListener('click', (e) => {
  if (e.target.classList && e.target.classList.contains('modal-backdrop')) {
    e.target.classList.remove('show');
  }
});

window.api = async function(url, opts = {}) {
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  let data;
  try { data = await r.json(); }
  catch { data = {}; }
  if (!r.ok) {
    const err = new Error(data.error || `HTTP ${r.status}`);
    err.data = data;
    err.status = r.status;
    throw err;
  }
  return data;
};

window.escapeHtml = function(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
};

window.getArtistName = function(track) {
  if (!track) return '';
  if (typeof track.artist === 'string') return track.artist;
  if (track.artist && typeof track.artist === 'object') return track.artist.name || '';
  return '';
};
