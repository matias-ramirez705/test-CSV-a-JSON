// app.js — funciones compartidas (formato Nuclear v1)

// Formatea segundos como mm:ss o h:mm:ss (legacy, para compatibilidad)
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

// Formatea milisegundos como mm:ss o h:mm:ss (formato Nuclear v1 usa durationMs)
window.fmtDurationMs = function(ms) {
  return window.fmtDuration(Math.floor(parseInt(ms || 0, 10) / 1000));
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

// ---- Helpers para formato Nuclear v1 ----

// Devuelve la lista de items desde un playlist_data (formato v1 normalizado por la API)
window.getItems = function(playlistData) {
  if (!playlistData) return [];
  if (playlistData.playlist && Array.isArray(playlistData.playlist.items)) {
    return playlistData.playlist.items;
  }
  // Legacy fallback
  if (Array.isArray(playlistData.tracks)) {
    return playlistData.tracks.map((t, i) => ({
      id: t.uuid || `legacy-${i}`,
      addedAtIso: t.addedAtIso || '',
      track: {
        title: t.name || '',
        artists: [{ name: window.getArtistName(t), roles: [] }],
        album: { title: t.album || '', artwork: { items: [] } },
        durationMs: parseInt(t.duration, 10) * 1000 || 0,
        trackNumber: i + 1,
        disc: '1',
        artwork: { items: [] },
        source: t.stream || { source: '', id: '' },
      }
    }));
  }
  return [];
};

// Devuelve el nombre del primer artista (o string vacío)
window.getArtistName = function(track) {
  if (!track) return '';
  // Formato v1: track.artists[] (cada uno con .name)
  if (Array.isArray(track.artists)) {
    return track.artists.map(a => a && a.name ? a.name : '').filter(Boolean).join(', ');
  }
  // Legacy: track.artist puede ser string o {name: '...'}
  if (typeof track.artist === 'string') return track.artist;
  if (track.artist && typeof track.artist === 'object') return track.artist.name || '';
  return '';
};

// Devuelve el título del track (formato v1 usa .title, legacy usa .name)
window.getTrackTitle = function(item) {
  if (!item) return '';
  // v1: item.track.title
  if (item.track && item.track.title) return item.track.title;
  // Legacy directo
  if (item.name) return item.name;
  return '';
};

// Devuelve el nombre del álbum
window.getAlbumTitle = function(item) {
  if (!item) return '';
  if (item.track && item.track.album) {
    return item.track.album.title || '';
  }
  if (item.album) {
    // Legacy: album es string
    return typeof item.album === 'string' ? item.album : (item.album.title || '');
  }
  return '';
};

// Devuelve la duración en ms (formato v1) o en segundos (legacy)
window.getDurationMs = function(item) {
  if (!item) return 0;
  if (item.track && item.track.durationMs != null) {
    return parseInt(item.track.durationMs, 10) || 0;
  }
  // Legacy: duration en segundos
  return parseInt(item.duration, 10) * 1000 || 0;
};

// Devuelve el ID del item (v1 usa .id, legacy usa .uuid)
window.getItemId = function(item) {
  if (!item) return '';
  return item.id || item.uuid || '';
};

// Devuelve el ID del track de Spotify (bare ID sin prefijo)
window.getSpotifyTrackId = function(item) {
  if (!item || !item.track) return '';
  const src = item.track.source || {};
  const id = src.id || '';
  // Si es spotify:track:xxx, devolver xxx
  if (id.startsWith('spotify:track:')) return id.split(':').pop();
  return id;
};

// Devuelve el thumbnail del track (primera artwork URL disponible)
window.getThumbnail = function(item) {
  if (!item || !item.track) return '';
  const arts = (item.track.artwork && item.track.artwork.items) || [];
  if (arts.length > 0 && arts[0].url) return arts[0].url;
  // Fallback al artwork del album
  const albumArts = (item.track.album && item.track.album.artwork && item.track.album.artwork.items) || [];
  if (albumArts.length > 0 && albumArts[0].url) return albumArts[0].url;
  return '';
};
