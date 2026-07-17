# Playlist Manager · Exportify CSV → Nuclear Player JSON

Herramienta Python con interfaz web para gestionar tus playlists:

- 📥 **Convertir** CSVs de Exportify (Spotify) al formato JSON de Nuclear Player
- ✏️ **Editar** playlists: renombrar, añadir/eliminar canciones, reordenar con drag & drop
- 🔀 **Combinar** varias playlists en una nueva (con o sin deduplicación)
- 💾 **Guardar** con el mismo nombre o como nueva playlist
- 📦 **Respaldos** automáticos antes de cada modificación, con opción de restaurar
- 🎨 Interfaz web oscura y responsive en español

---

## Requisitos

- Python 3.9+
- Flask (se instala automáticamente)

## Instalación y ejecución

```bash
cd playlist_manager
python3 -m venv venv
source venv/bin/activate          # en Windows: venv\Scripts\activate
pip install -r requirements.txt

python app.py
```

Luego abre tu navegador en: **http://127.0.0.1:5000**

## Uso

### 1. Importar CSVs desde Exportify

1. Ve a https://exportify.app/ y exporta tus playlists como CSV
2. En la pestaña **Playlists**, arrastra uno o varios CSVs a la zona de upload
3. Marca las opciones deseadas:
   - **Backup automático**: si la playlist ya existe, se guarda una copia en `backups/` antes de sobrescribirla
   - **Sobrescribir**: si existe, la reemplaza (en lugar de crear `_1.json`, `_2.json`, etc.)
4. Pulsa "Convertir a JSON" — se crean los archivos en `playlists/` con el formato Nuclear

### 2. Editar una playlist

- Click en **✏️ Editar** en cualquier playlist
- Cambia el nombre en el campo superior
- Añade canciones con **＋ Añadir canción**
- Elimina canciones con el botón 🗑️
- Reordena arrastrando las filas (aparecerá el botón "Guardar nuevo orden")
- Pulsa **💾 Guardar**:
  - Puedes cambiar el nombre
  - Puedes marcar **Guardar como nueva playlist** (no toca la original)
  - Puedes marcar **Crear respaldo** (recomendado)

### 3. Combinar playlists

- Ve a la pestaña **Combinar**
- Marca las playlists que quieres unir (mínimo 2)
- Pon nombre a la nueva playlist combinada
- Marca **Eliminar duplicados** si no quieres canciones repetidas (mismo nombre + artista)
- Pulsa "Combinar"
- Las playlists originales **no se modifican**

### 4. Respaldos

- En la pestaña **Respaldos** verás todos los backups con timestamp
- **Restaurar**: copia el backup sobre una playlist existente (haciendo backup del estado actual antes)
- **Descargar**: descarga el backup como archivo JSON
- **Eliminar**: borra el backup permanentemente

### 5. Importar a Nuclear Player

Una vez tienes tus JSONs en `playlists/`:

**Opción A — Copiar manualmente** (más fiable):
1. Cierra Nuclear Player
2. Copia los `.json` de `playlists/` a la carpeta de playlists de Nuclear:
   - Linux: `~/.config/Nuclear/playlists/`
   - Windows: `%APPDATA%\Nuclear\playlists\`
   - macOS: `~/Library/Application Support/Nuclear/playlists/`
3. Abre Nuclear — tus playlists aparecerán en la sección de playlists

**Opción B — Descargar y usar "Import Playlist"** en Nuclear si la versión lo soporta.

> Nota: Nuclear buscará cada canción en los proveedores configurados (YouTube, SoundCloud, etc.) cuando la reproduzcas. Si tu JSON incluye `spotify_id`, Nuclear puede usarlo para hacer búsquedas más precisas.

---

## Estructura del proyecto

```
playlist_manager/
├── app.py                    # Servidor Flask con todos los endpoints
├── playlist_converter.py     # Lógica de conversión CSV ↔ JSON + backups + merge
├── requirements.txt
├── templates/                # Plantillas HTML
│   ├── base.html
│   ├── index.html            # Lista de playlists + upload CSV
│   ├── edit.html             # Editor de playlist
│   ├── merge.html            # Combinar playlists
│   ├── backups.html          # Respaldos
│   └── error.html
├── static/
│   ├── css/style.css         # Estilos (tema oscuro)
│   └── js/
│       ├── app.js            # Utils compartidos
│       ├── index.js
│       ├── edit.js
│       ├── merge.js
│       └── backups.js
├── uploads/                  # CSVs subidos (temporales)
├── playlists/                # JSONs convertidos (formato Nuclear)
└── backups/                  # Respaldos con timestamp
```

## Formato Nuclear Player (JSON)

```json
{
  "id": "uuid",
  "name": "Mi Playlist",
  "tracks": [
    {
      "uuid": "uuid",
      "name": "Canción",
      "artist": { "name": "Artista" },
      "album": "Álbum",
      "duration": 240,
      "position": 0,
      "thumbnail": "https://...",
      "stream": {
        "source": "spotify",
        "id": "spotify_track_id"
      }
    }
  ],
  "createdAt": "2026-01-01T00:00:00Z"
}
```

## Uso del conversor desde CLI (sin interfaz web)

Si solo quieres convertir un CSV a JSON rápidamente:

```bash
python playlist_converter.py mi_playlist.csv -o playlists/mi_playlist.json -n "Mi Playlist"
```

## Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET    | `/api/playlists` | Lista todas las playlists |
| GET    | `/api/playlists/<file>` | Obtiene una playlist por nombre de archivo |
| POST   | `/api/upload-csv` | Sube y convierte CSVs (`multipart/form-data`, campo `files`) |
| PUT    | `/api/playlists/<file>` | Actualiza (renombrar, editar tracks, guardar como nuevo) |
| DELETE | `/api/playlists/<file>` | Elimina playlist (con backup opcional) |
| POST   | `/api/playlists/<file>/add-track` | Añade una canción |
| DELETE | `/api/playlists/<file>/remove-track/<uuid>` | Elimina una canción |
| POST   | `/api/playlists/<file>/reorder` | Reordena tracks (lista de UUIDs) |
| POST   | `/api/merge` | Combina varias playlists |
| GET    | `/api/backups` | Lista respaldos |
| GET    | `/api/backups/<file>` | Descarga un backup |
| POST   | `/api/backups/<file>/restore` | Restaura un backup sobre una playlist |
| DELETE | `/api/backups/<file>` | Elimina un backup |
| GET    | `/api/download/<file>` | Descarga una playlist |

## Notas

- Los CSVs de Exportify con delimitador `,` o `;` se detectan automáticamente
- Las columnas se reconocen por varios alias posibles (`Track Name`, `track_name`, etc.)
- La duración de Spotify (en ms) se convierte a segundos para Nuclear
- El `spotify_id` se conserva en el campo `stream` para que Nuclear pueda buscarlo
- Cada vez que se edita, elimina o sobrescribe una playlist, se crea un backup con timestamp en `backups/`
