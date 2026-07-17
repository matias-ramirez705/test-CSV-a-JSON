// edit.js — editor de playlist individual (formato Nuclear v1)
let currentPlaylist = null;
let currentFilename = window.EDITOR_FILENAME;
let pendingDeleteIndex = null;

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
  // El API devuelve el JSON en formato Nuclear v1: {version, playlist: {name, items, ...}}
  const playlist = currentPlaylist.playlist || {};
  const items = getItems(currentPlaylist);
  const totalMs = items.reduce((s, it) => s + (getDurationMs(it) || 0), 0);
  const isV1 = currentPlaylist._is_v1 !== false;

  const html = `
    <div class="card">
      <div class="editor-header">
        <a href="/" class="btn btn-ghost btn-icon" title="Volver">←</a>
        <input class="input name-input" id="playlist-name" value="${escapeHtml(playlist.name || currentPlaylist.name || '')}" placeholder="Nombre de la playlist">
        <button class="btn btn-success" onclick="openSaveModal()">💾 Guardar</button>
        <button class="btn btn-primary" onclick="openModal('add-track-modal')">＋ Añadir canción</button>
        <a class="btn btn-ghost" href="/api/download/${encodeURIComponent(currentFilename)}">⬇️ Descargar</a>
      </div>
      <div class="editor-meta">
        <span>🎵 <strong id="tracks-count">${items.length}</strong> canciones</span>
        <span>🕒 Duración total: <strong>${fmtDurationMs(totalMs)}</strong></span>
        <span>📄 <span class="badge">${escapeHtml(currentFilename)}</span></span>
        ${playlist.createdAtIso ? `<span>📅 Creada: ${fmtDate(playlist.createdAtIso)}</span>` : ''}
        <span class="badge ${isV1 ? 'badge-success' : 'badge-warning'}">${isV1 ? 'Formato v1' : 'Legacy (migrará al guardar)'}</span>
      </div>
      ${playlist.description ? `<div class="editor-meta"><span>📝 ${escapeHtml(playlist.description)}</span></div>` : ''}
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
      ${items.length === 0 ? `
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
            ${items.map((it, i) => renderItemRow(it, i)).join('')}
          </tbody>
        </table>
      `}
    </div>
  `;
  document.getElementById('editor-root').innerHTML = html;
  enableDragAndDrop();
}

function renderItemRow(item, i) {
  const title = getTrackTitle(item);
  const artist = getArtistName(item.track || {});
  const album = getAlbumTitle(item);
  const durationMs = getDurationMs(item);
  const itemId = getItemId(item);
  const thumb = getThumbnail(item);

  return `
    <tr data-item-id="${escapeHtml(itemId)}" data-index="${i}" draggable="true">
      <td class="track-num">${i + 1}</td>
      <td class="track-name">
        ${thumb ? `<img src="${escapeHtml(thumb)}" alt="" style="width:24px;height:24px;border-radius:3px;vertical-align:middle;margin-right:6px" onerror="this.style.display='none'">` : ''}
        ${escapeHtml(title)}
      </td>
      <td class="track-artist">${escapeHtml(artist)}</td>
      <td class="track-artist">${escapeHtml(album)}</td>
      <td class="track-duration">${fmtDurationMs(durationMs)}</td>
      <td class="track-actions">
        <button class="btn btn-ghost btn-icon btn-sm" title="Eliminar"
          data-index="${i}"
          data-name="${escapeHtml(title)}"
          onclick="askDeleteTrack(parseInt(this.dataset.index, 10), this.dataset.name)">🗑️</button>
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
        r.dataset.index = i;
      });
    });
  });
}

async function reorderSave() {
  const tbody = document.getElementById('tracks-tbody');
  if (!tbody) return;
  const order = Array.from(tbody.querySelectorAll('tr')).map(r => r.dataset.itemId);
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
  const durationSec = parseInt(document.getElementById('new-track-duration').value, 10) || 0;
  const durationMs = durationSec * 1000;
  const thumb = document.getElementById('new-track-thumb').value.trim();
  const spotifyId = document.getElementById('new-track-spotify-id').value.trim();

  if (!name) {
    toast('El nombre de la canción es obligatorio', 'warning', 'Atención');
    return;
  }

  api(`/api/playlists/${encodeURIComponent(currentFilename)}/add-track`, {
    method: 'POST',
    body: JSON.stringify({
      name,
      artist,
      album,
      duration_ms: durationMs,
      thumbnail: thumb,
      spotify_id: spotifyId,
    }),
  })
  .then(data => {
    const newItem = data.item || {};
    const newTitle = (newItem.track && newItem.track.title) || name;
    toast(`Añadida: ${newTitle}`, 'success', 'Canción añadida');
    closeModal('add-track-modal');
    // Limpiar
    ['new-track-name','new-track-artist','new-track-album','new-track-duration','new-track-thumb','new-track-spotify-id']
      .forEach(id => document.getElementById(id).value = '');
    loadPlaylist();
  })
  .catch(e => toast(e.message, 'error', 'Error'));
}

// ---- Eliminar track (por index, no por uuid) ----
function askDeleteTrack(index, name) {
  pendingDeleteIndex = index;
  document.getElementById('confirm-delete-msg').textContent =
    `Se eliminará "${name}" de la playlist. Se creará un respaldo automáticamente.`;
  document.getElementById('confirm-delete-btn').onclick = () => {
    closeModal('confirm-delete-modal');
    api(`/api/playlists/${encodeURIComponent(currentFilename)}/remove-track/${index}`, {
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
  const playlist = currentPlaylist.playlist || {};
  document.getElementById('save-name').value = playlist.name || currentPlaylist.name || '';
  document.getElementById('save-description').value = playlist.description || '';
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
  const description = document.getElementById('save-description').value.trim();
  const saveAsNew = document.getElementById('save-as-new').checked;
  const newFilename = document.getElementById('save-new-filename').value.trim();
  const backup = document.getElementById('save-backup').checked;

  if (saveAsNew && !newFilename) {
    toast('Debes indicar un nombre de archivo para la nueva playlist', 'warning');
    return;
  }

  // Construir payload en formato Nuclear v1: enviar toda la playlist
  // tal como está, solo actualizamos nombre y descripción.
  const playlist = currentPlaylist.playlist || {};
  const payload = {
    version: 1,
    playlist: {
      id: playlist.id || currentPlaylist.id,
      name,
      description,
      artwork: playlist.artwork || { items: [] },
      createdAtIso: playlist.createdAtIso || currentPlaylist.createdAt,
      lastModifiedIso: new Date().toISOString(),
      isReadOnly: false,
      items: (playlist.items || getItems(currentPlaylist)).map((item, i) => {
        // Mantener el item tal cual, pero actualizar trackNumber
        const newItem = Object.assign({}, item);
        if (newItem.track) {
          newItem.track = Object.assign({}, newItem.track, { trackNumber: i + 1 });
        }
        return newItem;
      }),
    },
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
