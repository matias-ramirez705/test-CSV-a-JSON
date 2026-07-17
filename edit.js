// edit.js — editor de playlist individual
let currentPlaylist = null;
let currentFilename = window.EDITOR_FILENAME;
let pendingDeleteUuid = null;

async function loadPlaylist() {
  try {
    const data = await api(`/api/playlists/${encodeURIComponent(currentFilename)}`);
    currentPlaylist = data;
    renderEditor();
  } catch (e) {
    document.getElementById('editor-root').innerHTML = `
      <div class="empty">
        <div class="icon">⚠️</div>
        <h3>Error al cargar</h3>
        <p>${escapeHtml(e.message)}</p>
        <a href="/" class="btn btn-primary mt-2">Volver</a>
      </div>`;
  }
}

function renderEditor() {
  if (!currentPlaylist) return;
  const tracks = currentPlaylist.tracks || [];
  const totalDur = tracks.reduce((s, t) => s + (parseInt(t.duration, 10) || 0), 0);

  const html = `
    <div class="card">
      <div class="editor-header">
        <a href="/" class="btn btn-ghost btn-icon" title="Volver">←</a>
        <input class="input name-input" id="playlist-name" value="${escapeHtml(currentPlaylist.name || '')}" placeholder="Nombre de la playlist">
        <button class="btn btn-success" onclick="openSaveModal()">💾 Guardar</button>
        <button class="btn btn-primary" onclick="openModal('add-track-modal')">＋ Añadir canción</button>
        <a class="btn btn-ghost" href="/api/download/${encodeURIComponent(currentFilename)}">⬇️ Descargar</a>
      </div>
      <div class="editor-meta">
        <span>🎵 <strong id="tracks-count">${tracks.length}</strong> canciones</span>
        <span>🕒 Duración total: <strong>${fmtDuration(totalDur)}</strong></span>
        <span>📄 <span class="badge">${escapeHtml(currentFilename)}</span></span>
        ${currentPlaylist.createdAt ? `<span>📅 Creada: ${fmtDate(currentPlaylist.createdAt)}</span>` : ''}
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">Canciones</div>
          <div class="card-subtitle">Arrastra las filas para reordenar. Usa 🗑️ para eliminar.</div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="reorderSave()" id="reorder-btn" style="display:none">
          💾 Guardar nuevo orden
        </button>
      </div>
      ${tracks.length === 0 ? `
        <div class="empty">
          <div class="icon">🎵</div>
          <h3>Playlist vacía</h3>
          <p>Añade canciones con el botón "＋ Añadir canción".</p>
        </div>
      ` : `
        <table class="tracks-table" id="tracks-table">
          <thead>
            <tr>
              <th class="track-num">#</th>
              <th>Título</th>
              <th>Artista</th>
              <th>Álbum</th>
              <th class="track-duration">Duración</th>
              <th class="track-actions"></th>
            </tr>
          </thead>
          <tbody id="tracks-tbody">
            ${tracks.map((t, i) => renderTrackRow(t, i)).join('')}
          </tbody>
        </table>
      `}
    </div>
  `;
  document.getElementById('editor-root').innerHTML = html;
  enableDragAndDrop();
}

function renderTrackRow(t, i) {
  const artist = getArtistName(t);
  return `
    <tr data-uuid="${escapeHtml(t.uuid || '')}" draggable="true">
      <td class="track-num">${i + 1}</td>
      <td class="track-name">${escapeHtml(t.name || '')}</td>
      <td class="track-artist">${escapeHtml(artist)}</td>
      <td class="track-artist">${escapeHtml(t.album || '')}</td>
      <td class="track-duration">${fmtDuration(t.duration)}</td>
      <td class="track-actions">
        <button class="btn btn-ghost btn-icon btn-sm" title="Eliminar"
          onclick="askDeleteTrack('${escapeHtml(t.uuid)}', '${escapeHtml((t.name || '').replace(/'/g,''))}')">🗑️</button>
      </td>
    </tr>
  `;
}

// ---- Drag and drop reordenar ----
let dragSrc = null;
function enableDragAndDrop() {
  const tbody = document.getElementById('tracks-tbody');
  if (!tbody) return;
  tbody.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('dragstart', (e) => {
      dragSrc = tr;
      tr.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    tr.addEventListener('dragend', () => {
      tr.classList.remove('dragging');
      tbody.querySelectorAll('tr').forEach(r => r.classList.remove('drag-over'));
      document.getElementById('reorder-btn').style.display = 'inline-flex';
    });
    tr.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (dragSrc && dragSrc !== tr) {
        tbody.querySelectorAll('tr').forEach(r => r.classList.remove('drag-over'));
        tr.classList.add('drag-over');
      }
    });
    tr.addEventListener('drop', (e) => {
      e.preventDefault();
      if (!dragSrc || dragSrc === tr) return;
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const srcIdx = rows.indexOf(dragSrc);
      const dstIdx = rows.indexOf(tr);
      if (srcIdx < dstIdx) {
        tr.parentNode.insertBefore(dragSrc, tr.nextSibling);
      } else {
        tr.parentNode.insertBefore(dragSrc, tr);
      }
      // Renumerar
      tbody.querySelectorAll('tr').forEach((r, i) => {
        r.querySelector('.track-num').textContent = i + 1;
      });
    });
  });
}

async function reorderSave() {
  const tbody = document.getElementById('tracks-tbody');
  if (!tbody) return;
  const order = Array.from(tbody.querySelectorAll('tr')).map(r => r.dataset.uuid);
  try {
    const data = await api(`/api/playlists/${encodeURIComponent(currentFilename)}/reorder`, {
      method: 'POST',
      body: JSON.stringify({ order }),
    });
    toast('Orden actualizado', 'success');
    document.getElementById('reorder-btn').style.display = 'none';
    loadPlaylist();
  } catch (e) {
    toast(e.message, 'error', 'Error al reordenar');
  }
}

// ---- Añadir track ----
function submitNewTrack() {
  const name = document.getElementById('new-track-name').value.trim();
  const artist = document.getElementById('new-track-artist').value.trim();
  const album = document.getElementById('new-track-album').value.trim();
  const duration = parseInt(document.getElementById('new-track-duration').value, 10) || 0;
  const thumb = document.getElementById('new-track-thumb').value.trim();

  if (!name) {
    toast('El nombre de la canción es obligatorio', 'warning', 'Atención');
    return;
  }

  api(`/api/playlists/${encodeURIComponent(currentFilename)}/add-track`, {
    method: 'POST',
    body: JSON.stringify({ name, artist, album, duration, thumbnail: thumb }),
  })
  .then(data => {
    toast(`Añadida: ${data.track.name}`, 'success', 'Canción añadida');
    closeModal('add-track-modal');
    // Limpiar
    ['new-track-name','new-track-artist','new-track-album','new-track-duration','new-track-thumb']
      .forEach(id => document.getElementById(id).value = '');
    loadPlaylist();
  })
  .catch(e => toast(e.message, 'error', 'Error'));
}

// ---- Eliminar track ----
function askDeleteTrack(uuid, name) {
  pendingDeleteUuid = uuid;
  document.getElementById('confirm-delete-msg').textContent =
    `Se eliminará "${name}" de la playlist. Se creará un respaldo automáticamente.`;
  document.getElementById('confirm-delete-btn').onclick = () => {
    closeModal('confirm-delete-modal');
    api(`/api/playlists/${encodeURIComponent(currentFilename)}/remove-track/${encodeURIComponent(uuid)}`, {
      method: 'DELETE',
    })
    .then(data => {
      toast('Canción eliminada', 'success');
      loadPlaylist();
    })
    .catch(e => toast(e.message, 'error', 'Error'));
  };
  openModal('confirm-delete-modal');
}

// ---- Guardar / Guardar como ----
function openSaveModal() {
  document.getElementById('save-name').value = currentPlaylist.name || '';
  document.getElementById('save-as-new').checked = false;
  document.getElementById('save-new-filename').value = '';
  document.getElementById('new-filename-field').style.display = 'none';
  document.getElementById('save-backup').checked = true;
  openModal('save-modal');
}

document.addEventListener('change', (e) => {
  if (e.target.id === 'save-as-new') {
    document.getElementById('new-filename-field').style.display = e.target.checked ? 'block' : 'none';
  }
});

async function confirmSave() {
  const name = document.getElementById('save-name').value.trim();
  if (!name) {
    toast('El nombre es obligatorio', 'warning');
    return;
  }
  const saveAsNew = document.getElementById('save-as-new').checked;
  const newFilename = document.getElementById('save-new-filename').value.trim();
  const backup = document.getElementById('save-backup').checked;

  if (saveAsNew && !newFilename) {
    toast('Debes indicar un nombre de archivo para la nueva playlist', 'warning');
    return;
  }

  // Construir payload: solo nombre + tracks (el backend reasigna uuids/positions)
  const payload = {
    name,
    id: currentPlaylist.id,
    createdAt: currentPlaylist.createdAt,
    tracks: (currentPlaylist.tracks || []).map((t, i) => ({
      uuid: t.uuid,
      name: t.name,
      artist: getArtistName(t),
      album: t.album || '',
      duration: parseInt(t.duration, 10) || 0,
      position: i,
      thumbnail: t.thumbnail || '',
      stream: t.stream || { source: '', id: '' },
    })),
    save_as_new: saveAsNew,
    new_filename: newFilename,
    backup,
  };

  try {
    const data = await api(`/api/playlists/${encodeURIComponent(currentFilename)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    toast(data.backup ? `Respaldo: ${data.backup}` : 'Guardado', 'success', 'Playlist guardada');
    closeModal('save-modal');
    if (saveAsNew) {
      window.location.href = `/edit/${encodeURIComponent(data.filename)}`;
    } else {
      currentFilename = data.filename;
      loadPlaylist();
    }
  } catch (e) {
    toast(e.message, 'error', 'Error al guardar');
  }
}

// ---- Init ----
loadPlaylist();
