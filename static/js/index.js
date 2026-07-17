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
          ${p.total_duration_str ? `<span>⏱️ ${escapeHtml(p.total_duration_str)}</span>` : ''}
        </div>
        <div class="meta">
          <span class="badge">📄 ${escapeHtml(p.filename)}</span>
          ${p.is_v1 === false ? '<span class="badge badge-warning" title="Esta playlist está en formato legacy. Se migrará a v1 al editarla.">legacy</span>' : '<span class="badge badge-success" title="Formato Nuclear v1 nativo">v1</span>'}
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
loadPendingUploads();

// ============================================================
// 🆕 Procesamiento masivo desde carpeta uploads/
// ============================================================

async function loadPendingUploads() {
  const countEl = document.getElementById('pending-count');
  const pathEl = document.getElementById('uploads-path');
  const listEl = document.getElementById('uploads-list');
  const convertBtn = document.getElementById('batch-convert-btn');
  const clearBtn = document.getElementById('batch-clear-btn');

  try {
    const data = await api('/api/uploads');
    countEl.textContent = data.count;
    pathEl.textContent = data.uploads_dir;

    if (data.count === 0) {
      listEl.innerHTML = `
        <div class="empty" style="padding:20px">
          <div class="icon" style="font-size:24px;opacity:0.5">📂</div>
          <p style="font-size:12px;color:var(--text-dim);margin-top:6px">
            Copia tus CSV a la carpeta <code>uploads/</code> del proyecto y luego pulsa "Refrescar".
          </p>
        </div>`;
      convertBtn.disabled = true;
      clearBtn.disabled = true;
    } else {
      listEl.innerHTML = `
        <div style="font-size:12px;color:var(--text-dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.04em;font-weight:600">
          CSV listos para convertir:
        </div>
        <div class="backup-list" style="max-height:140px">
          ${data.files.map(f => `
            <div class="backup-item" style="padding:6px 10px">
              <div class="info">
                <div class="filename" style="font-size:12px">📄 ${escapeHtml(f.filename)}</div>
                <div class="meta">${fmtBytes(f.size_bytes)} · ${fmtDate(f.modified)}</div>
              </div>
            </div>
          `).join('')}
        </div>`;
      convertBtn.disabled = false;
      clearBtn.disabled = false;
    }
  } catch (e) {
    countEl.textContent = '?';
    pathEl.textContent = 'Error: ' + escapeHtml(e.message);
    listEl.innerHTML = '';
    convertBtn.disabled = true;
    clearBtn.disabled = true;
  }
}

async function convertAllUploads() {
  const backup = document.getElementById('batch-backup').checked;
  const overwrite = document.getElementById('batch-overwrite').checked;
  const deleteCsv = document.getElementById('batch-delete-csv').checked;

  const btn = document.getElementById('batch-convert-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Convirtiendo...';

  const resultDiv = document.getElementById('batch-result');
  resultDiv.style.display = 'block';
  resultDiv.innerHTML = `
    <div class="card" style="background:var(--bg-elev-2);padding:16px">
      <div class="card-title" style="font-size:14px"><span class="spinner"></span> Procesando...</div>
    </div>`;

  try {
    const data = await api('/api/convert-all-uploads', {
      method: 'POST',
      body: JSON.stringify({ backup, overwrite, delete_csv: deleteCsv }),
    });

    const ok = data.ok || 0;
    const err = data.errors || 0;
    const skip = data.skipped || 0;
    const total = data.total_csv || 0;
    const tracks = data.total_tracks || 0;

    const statusColor = err > 0 ? 'warning' : 'success';
    resultDiv.innerHTML = `
      <div class="card" style="background:var(--bg-elev-2);padding:16px;border-left:4px solid var(--${statusColor})">
        <div class="card-title" style="font-size:16px">
          ${err === 0 ? '✓' : '⚠️'} Conversión masiva completada
        </div>
        <div class="row mt-2">
          <div class="field" style="margin:0">
            <label style="margin:0">Total CSV</label>
            <div style="font-size:20px;font-weight:700">${total}</div>
          </div>
          <div class="field" style="margin:0">
            <label style="margin:0">Convertidos</label>
            <div style="font-size:20px;font-weight:700;color:var(--success)">${ok}</div>
          </div>
          <div class="field" style="margin:0">
            <label style="margin:0">Con error</label>
            <div style="font-size:20px;font-weight:700;color:var(--danger)">${err}</div>
          </div>
          <div class="field" style="margin:0">
            <label style="margin:0">Canciones totales</label>
            <div style="font-size:20px;font-weight:700">${tracks}</div>
          </div>
        </div>
        ${err > 0 ? `
          <div class="mt-2">
            <label>Detalles de errores:</label>
            <div style="max-height:120px;overflow-y:auto;background:var(--bg);padding:8px;border-radius:6px;font-size:12px">
              ${data.results.filter(r => r.status === 'error').map(r => `
                <div style="margin-bottom:4px">
                  <strong>${escapeHtml(r.file)}</strong>: ${escapeHtml(r.reason)}
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
        <div class="flex gap-1 mt-2">
          <a class="btn btn-primary" href="/">↻ Ver mis playlists</a>
        </div>
      </div>
    `;

    toast(
      `${ok} de ${total} playlists convertidas (${tracks} canciones)${err ? ', ' + err + ' con error' : ''}`,
      err ? 'warning' : 'success',
      'Conversión masiva'
    );

    loadPlaylists();
    loadStats();
    loadPendingUploads();
  } catch (e) {
    resultDiv.innerHTML = `
      <div class="card" style="background:var(--bg-elev-2);padding:16px;border-left:4px solid var(--danger)">
        <div class="card-title text-danger">⚠️ Error</div>
        <p class="mt-1">${escapeHtml(e.message)}</p>
      </div>`;
    toast(e.message, 'error', 'Error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>⚡ Convertir todos los CSV</span>';
  }
}

async function clearUploads() {
  if (!confirm('¿Borrar TODOS los CSV de la carpeta uploads/?\nEsta acción no se puede deshacer.')) return;
  try {
    const data = await api('/api/uploads/clear', { method: 'DELETE' });
    toast(`${data.deleted} CSV eliminados`, 'success');
    loadPendingUploads();
  } catch (e) {
    toast(e.message, 'error');
  }
}

// ============================================================
// 🔄 Migrar playlists viejas a formato Nuclear v1
// ============================================================

async function migrateAllToV1() {
  if (!confirm(
    '¿Migrar TODAS las playlists en formato legacy al formato Nuclear v1?\n\n' +
    '• Las que ya están en v1 se dejan intactas.\n' +
    '• Las que están en formato viejo se convierten a v1 (con backup previo).\n' +
    '• Esta acción es recomendable si tienes playlists creadas con versiones anteriores de la app.'
  )) return;

  try {
    const data = await api('/api/migrate-all-to-v1', { method: 'POST' });
    toast(
      `${data.migrated} migradas, ${data.skipped} ya estaban en v1, ${data.errors} errores`,
      data.errors > 0 ? 'warning' : 'success',
      'Migración completada'
    );
    loadPlaylists();
    loadStats();
  } catch (e) {
    toast(e.message, 'error', 'Error en migración');
  }
}
