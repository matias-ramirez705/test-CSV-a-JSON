// index.js — lógica de la página principal
let selectedFiles = [];

async function loadStats() {
  try {
    const [playlists, backups] = await Promise.all([
      api('/api/playlists'),
      api('/api/backups'),
    ]);
    const plist = playlists.playlists || [];
    const bklist = backups.backups || [];
    const totalTracks = plist.reduce((s, p) => s + (p.tracks_count || 0), 0);
    const totalSize = plist.reduce((s, p) => s + (p.size_bytes || 0), 0)
                      + bklist.reduce((s, b) => s + (b.size_bytes || 0), 0);

    document.getElementById('stat-playlists').textContent = plist.length;
    document.getElementById('stat-tracks').textContent = totalTracks;
    document.getElementById('stat-backups').textContent = bklist.length;
    document.getElementById('stat-size').textContent = fmtBytes(totalSize);
  } catch (e) {
    console.error(e);
  }
}

async function loadPlaylists() {
  const container = document.getElementById('playlists-container');
  try {
    const data = await api('/api/playlists');
    const playlists = data.playlists || [];
    if (playlists.length === 0) {
      container.innerHTML = `
        <div class="empty">
          <div class="icon">🎵</div>
          <h3>No hay playlists</h3>
          <p>Sube un CSV desde Exportify para empezar.</p>
        </div>`;
      return;
    }
    container.innerHTML = `<div class="playlist-grid">` + playlists.map(p => `
      <div class="playlist-card">
        <div class="name">${escapeHtml(p.name)}</div>
        <div class="meta">
          <span>🎵 ${p.tracks_count} canciones</span>
          <span>📦 ${fmtBytes(p.size_bytes)}</span>
        </div>
        <div class="meta">
          <span>🕒 ${fmtDate(p.modified)}</span>
        </div>
        <div class="meta">
          <span class="badge">📄 ${escapeHtml(p.filename)}</span>
        </div>
        <div class="actions">
          <a class="btn btn-primary btn-sm" href="/edit/${encodeURIComponent(p.filename)}">✏️ Editar</a>
          <button class="btn btn-ghost btn-sm" onclick="downloadPlaylist('${encodeURIComponent(p.filename)}')">⬇️ Descargar</button>
          <button class="btn btn-danger btn-sm" onclick="deletePlaylist('${encodeURIComponent(p.filename)}', '${escapeHtml(p.name)}')">🗑️</button>
        </div>
      </div>
    `).join('') + `</div>`;
  } catch (e) {
    container.innerHTML = `<div class="empty"><div class="icon">⚠️</div><h3>Error</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}

function downloadPlaylist(filename) {
  window.location.href = `/api/download/${filename}`;
}

async function deletePlaylist(filename, name) {
  if (!confirm(`¿Eliminar la playlist "${name}"?\n\nSe creará un respaldo en la carpeta de respaldos antes de eliminarla.`)) return;
  try {
    const data = await api(`/api/playlists/${filename}?backup=true`, { method: 'DELETE' });
    toast(`Respaldo creado: ${data.backup || 'sin respaldo'}`, 'success', 'Playlist eliminada');
    loadPlaylists();
    loadStats();
  } catch (e) {
    toast(e.message, 'error', 'Error');
  }
}

// ---- Upload ----
const uploadZone = document.getElementById('upload-zone');
const csvInput = document.getElementById('csv-input');
const fileList = document.getElementById('file-list');
const uploadBtn = document.getElementById('upload-btn');

uploadZone.addEventListener('click', () => csvInput.click());
uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  handleFiles(e.dataTransfer.files);
});
csvInput.addEventListener('change', (e) => handleFiles(e.target.files));

function handleFiles(files) {
  const csvFiles = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.csv'));
  if (csvFiles.length === 0) {
    toast('Solo se aceptan archivos .csv', 'warning', 'Atención');
    return;
  }
  // Evitar duplicados
  for (const f of csvFiles) {
    if (!selectedFiles.find(x => x.name === f.name)) {
      selectedFiles.push(f);
    }
  }
  renderFileList();
}

function renderFileList() {
  if (selectedFiles.length === 0) {
    fileList.innerHTML = '';
    uploadBtn.disabled = true;
    return;
  }
  fileList.innerHTML = selectedFiles.map((f, i) => `
    <div class="backup-item" style="padding:8px 12px">
      <div class="info">
        <div class="filename">📄 ${escapeHtml(f.name)}</div>
        <div class="meta">${fmtBytes(f.size)}</div>
      </div>
      <button class="btn btn-ghost btn-sm" onclick="removeFile(${i})">✕</button>
    </div>
  `).join('');
  uploadBtn.disabled = false;
}

function removeFile(i) {
  selectedFiles.splice(i, 1);
  renderFileList();
}

document.getElementById('clear-btn').addEventListener('click', () => {
  selectedFiles = [];
  csvInput.value = '';
  renderFileList();
});

document.getElementById('upload-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (selectedFiles.length === 0) return;

  const backup = document.getElementById('backup-checkbox').checked;
  const overwrite = document.getElementById('overwrite-checkbox').checked;

  const fd = new FormData();
  for (const f of selectedFiles) fd.append('files', f);
  fd.append('backup', backup ? 'true' : 'false');
  fd.append('overwrite', overwrite ? 'true' : 'false');

  uploadBtn.disabled = true;
  uploadBtn.innerHTML = '<span class="spinner"></span> Convirtiendo...';

  try {
    const r = await fetch('/api/upload-csv', { method: 'POST', body: fd });
    const data = await r.json();
    let okCount = 0, errCount = 0;
    for (const res of (data.results || [])) {
      if (res.status === 'ok') {
        okCount++;
        toast(`${res.tracks} canciones · ${res.playlist_file}`, 'success', `✓ ${res.file}`);
      } else if (res.status === 'error') {
        errCount++;
        toast(res.reason || 'Error', 'error', `✗ ${res.file}`);
      }
    }
    if (okCount > 0) {
      toast(`${okCount} playlist(s) convertidas${errCount ? ', ' + errCount + ' con error' : ''}`, 'success', 'Importación completada');
      selectedFiles = [];
      csvInput.value = '';
      renderFileList();
      loadPlaylists();
      loadStats();
    }
  } catch (err) {
    toast(err.message, 'error', 'Error de red');
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.innerHTML = '<span>Convertir a JSON</span>';
  }
});

// ---- Init ----
loadStats();
loadPlaylists();
