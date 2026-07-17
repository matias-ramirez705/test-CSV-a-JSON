// merge.js — combinar playlists
let selectedForMerge = new Set();

async function loadMergeList() {
  const container = document.getElementById('merge-list');
  try {
    const data = await api('/api/playlists');
    const playlists = data.playlists || [];
    if (playlists.length === 0) {
      container.innerHTML = `
        <div class="empty">
          <div class="icon">🎵</div>
          <h3>No hay playlists</h3>
          <p>Necesitas al menos 2 playlists para combinar.</p>
        </div>`;
      return;
    }
    if (playlists.length < 2) {
      container.innerHTML = `
        <div class="empty">
          <div class="icon">⚠️</div>
          <h3>Solo tienes 1 playlist</h3>
          <p>Necesitas al menos 2 playlists para combinar.</p>
        </div>`;
    }
    container.innerHTML = playlists.map(p => `
      <div class="merge-item ${selectedForMerge.has(p.filename) ? 'selected' : ''}"
           data-filename="${escapeHtml(p.filename)}"
           onclick="toggleMerge('${escapeHtml(p.filename)}')">
        <input type="checkbox" ${selectedForMerge.has(p.filename) ? 'checked' : ''} onclick="event.stopPropagation()">
        <div class="info">
          <div class="name">${escapeHtml(p.name)}</div>
          <div class="meta">🎵 ${p.tracks_count} canciones · ${fmtBytes(p.size_bytes)} · ${escapeHtml(p.filename)}</div>
        </div>
      </div>
    `).join('');
    updateMergeButton();
  } catch (e) {
    container.innerHTML = `<div class="empty"><div class="icon">⚠️</div><h3>Error</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}

function toggleMerge(filename) {
  if (selectedForMerge.has(filename)) {
    selectedForMerge.delete(filename);
  } else {
    selectedForMerge.add(filename);
  }
  loadMergeList();
}

function clearSelection() {
  selectedForMerge.clear();
  loadMergeList();
}

function updateMergeButton() {
  const count = selectedForMerge.size;
  document.getElementById('merge-count').textContent = count;
  document.getElementById('merge-btn').disabled = count < 2;
}

async function doMerge() {
  if (selectedForMerge.size < 2) return;
  const name = document.getElementById('merge-name').value.trim();
  if (!name) {
    toast('Indica un nombre para la nueva playlist', 'warning', 'Atención');
    return;
  }
  const dedupe = document.getElementById('merge-dedupe').checked;
  const description = (document.getElementById('merge-description') || {}).value || '';

  const btn = document.getElementById('merge-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Combinando...';

  try {
    const data = await api('/api/merge', {
      method: 'POST',
      body: JSON.stringify({
        playlists: Array.from(selectedForMerge),
        name,
        dedupe,
        description,
      }),
    });
    const resultDiv = document.getElementById('merge-result');
    const content = document.getElementById('merge-result-content');
    content.innerHTML = `
      <div class="row">
        <div class="field">
          <label>Archivo creado</label>
          <div><span class="badge badge-success">${escapeHtml(data.filename)}</span></div>
        </div>
        <div class="field">
          <label>Canciones totales</label>
          <div style="font-size:18px;font-weight:600">${data.tracks}</div>
        </div>
      </div>
      <div class="field mt-2">
        <label>Combinada desde</label>
        <div>${(data.merged_from || []).map(n => `<span class="badge">${escapeHtml(n)}</span>`).join(' ')}</div>
      </div>
      <div class="flex gap-1 mt-2">
        <a class="btn btn-primary" href="/edit/${encodeURIComponent(data.filename)}">✏️ Editar playlist combinada</a>
        <a class="btn btn-ghost" href="/api/download/${encodeURIComponent(data.filename)}">⬇️ Descargar JSON</a>
      </div>
    `;
    resultDiv.style.display = 'block';
    toast(`${data.tracks} canciones combinadas`, 'success', 'Playlist creada');
    // Limpiar selección
    selectedForMerge.clear();
    document.getElementById('merge-name').value = '';
    loadMergeList();
  } catch (e) {
    toast(e.message, 'error', 'Error al combinar');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>Combinar <span id="merge-count">${selectedForMerge.size}</span> playlists</span>`;
  }
}

loadMergeList();
