// backups.js — gestionar respaldos
let currentRestoreSource = null;

async function loadBackups() {
  const container = document.getElementById('backups-container');
  try {
    const data = await api('/api/backups');
    const backups = data.backups || [];
    if (backups.length === 0) {
      container.innerHTML = `
        <div class="empty">
          <div class="icon">📦</div>
          <h3>Sin respaldos</h3>
          <p>Los respaldos se crean automáticamente cuando editas, eliminas o sobrescribes una playlist.</p>
        </div>`;
      return;
    }
    container.innerHTML = `<div class="backup-list">` + backups.map(b => `
      <div class="backup-item">
        <div class="info">
          <div class="filename">📦 ${escapeHtml(b.filename)}</div>
          <div class="meta">${fmtDate(b.modified)} · ${fmtBytes(b.size_bytes)}</div>
        </div>
        <div class="actions">
          <button class="btn btn-primary btn-sm" onclick="openRestoreModal('${escapeHtml(b.filename)}')">↩️ Restaurar</button>
          <a class="btn btn-ghost btn-sm" href="/api/backups/${encodeURIComponent(b.filename)}">⬇️ Descargar</a>
          <button class="btn btn-danger btn-sm" onclick="deleteBackup('${escapeHtml(b.filename)}')">🗑️</button>
        </div>
      </div>
    `).join('') + `</div>`;
  } catch (e) {
    container.innerHTML = `<div class="empty"><div class="icon">⚠️</div><h3>Error</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}

async function openRestoreModal(filename) {
  currentRestoreSource = filename;
  document.getElementById('restore-source-name').textContent = `Origen: ${filename}`;

  // Cargar lista de playlists para destino
  const select = document.getElementById('restore-target');
  select.innerHTML = '<option value="">— Selecciona una playlist —</option>';
  try {
    const data = await api('/api/playlists');
    for (const p of (data.playlists || [])) {
      const opt = document.createElement('option');
      opt.value = p.filename;
      opt.textContent = `${p.name} (${p.filename})`;
      select.appendChild(opt);
    }
  } catch (e) {
    toast(e.message, 'error', 'Error al cargar playlists');
  }
  openModal('restore-modal');
}

async function confirmRestore() {
  const target = document.getElementById('restore-target').value;
  if (!target) {
    toast('Selecciona una playlist destino', 'warning', 'Atención');
    return;
  }
  if (!confirm(`¿Restaurar "${currentRestoreSource}" sobre "${target}"?\n\nSe creará un respaldo del estado actual antes de sobrescribir.`)) return;

  try {
    const data = await api(`/api/backups/${encodeURIComponent(currentRestoreSource)}/restore`, {
      method: 'POST',
      body: JSON.stringify({ target }),
    });
    toast(`Respaldo del estado actual: ${data.backup_current || '(no había archivo previo)'}`, 'success', 'Restaurado');
    closeModal('restore-modal');
  } catch (e) {
    toast(e.message, 'error', 'Error al restaurar');
  }
}

async function deleteBackup(filename) {
  if (!confirm(`¿Eliminar el respaldo "${filename}"?\nEsta acción no se puede deshacer.`)) return;
  try {
    await api(`/api/backups/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    toast('Respaldo eliminado', 'success');
    loadBackups();
  } catch (e) {
    toast(e.message, 'error', 'Error');
  }
}

loadBackups();
