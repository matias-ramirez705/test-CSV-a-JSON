# Playlist Manager — Exportify CSV ↔ Nuclear Player JSON (v1)

Aplicación web local (Flask) para convertir playlists exportadas desde [exportify.app](https://exportify.app/) (CSV de Spotify) al formato JSON nativo que usa [Nuclear Player](https://nuclearplayer.com/), y gestionarlas después desde el navegador.

## Características

- **Conversión CSV → JSON formato Nuclear v1** (el formato REAL que Nuclear Player importa, no el simplificado de versiones anteriores).
- **Conversión masiva** de todos los CSV en `uploads/` con un clic.
- **Editor web** para renombrar la playlist, cambiar descripción, agregar o eliminar canciones, y reordenar arrastrando.
- **Combinar varias playlists** en una nueva (con opción de eliminar duplicados).
- **Guardar como** nueva playlist o sobrescribir la actual.
- **Backups automáticos** en la carpeta `backups/` antes de cualquier sobrescritura o eliminación.
- **Restaurar respaldos** con un clic (siempre hace un backup del estado actual antes).
- **Migración automática** de playlists en formato legacy al nuevo formato v1.
- **Descargar JSON** listo para importar en Nuclear Player.

## 🆕 Formato Nuclear v1 (real, verificado)

A partir de la versión 2 de esta herramienta, el JSON producido sigue EXACTAMENTE el formato que Nuclear Player exporta cuando uno importa una playlist por URL desde la propia app. Esto significa que ahora **Nuclear reconoce los JSON al importarlos** (la versión anterior producía un formato inventado que Nuclear rechazaba silenciosamente).

Estructura del JSON producido:

```json
{
  "version": 1,
  "playlist": {
    "id": "uuid-v4",
    "name": "Mi Playlist",
    "description": "",
    "artwork": { "items": [] },
    "createdAtIso": "2026-07-17T22:49:03.820Z",
    "lastModifiedIso": "2026-07-17T22:49:03.820Z",
    "isReadOnly": false,
    "items": [
      {
        "id": "16-hex-chars",
        "addedAtIso": "2025-01-03T00:50:39.828Z",
        "track": {
          "title": "Into It",
          "artists": [
            {
              "name": "Steradlye",
              "roles": [],
              "source": { "provider": "spotify", "id": "spotify:artist:2MvfToow2rG2wleBj554BJ" }
            }
          ],
          "album": {
            "title": "Into It",
            "artwork": { "items": [
              { "url": "https://i.scdn.co/image/ab67616d00001e02...", "width": 300, "height": 300 },
              { "url": "https://i.scdn.co/image/ab67616d00004851...", "width": 64,  "height": 64  },
              { "url": "https://i.scdn.co/image/ab67616d0000b273...", "width": 640, "height": 640 }
            ]},
            "source": { "provider": "spotify", "id": "spotify:album:3yzvEUxK50jDtAnrWI2YWx" }
          },
          "durationMs": 235102,
          "trackNumber": 1,
          "disc": "1",
          "artwork": { "items": [ ... tres tamaños ... ] },
          "source": { "provider": "spotify", "id": "spotify:track:7xA5iKvUOIQQj9yVe5OquS" }
        }
      }
    ]
  }
}
```

### Ventajas del formato v1 sobre el legacy

| Aspecto | Legacy (v1 anterior) | Nuclear v1 (actual) |
|---|---|---|
| Estructura top-level | `{id, name, tracks, createdAt}` | `{version:1, playlist: {...}}` |
| Tracks | `tracks[]` con `uuid/name/artist/album/duration/thumbnail/stream` | `items[]` con `id/addedAtIso/track:{title,artists[],album,artwork,source,durationMs,...}` |
| Artist IDs | Se perdían | Se conservan (`spotify:artist:...`) |
| Album Artwork | Una sola URL | Tres tamaños sintetizados desde la URL de Spotify CDN (64/300/640) |
| Duración | Segundos (enteros) | Milisegundos (precisión real) |
| Source IDs | Bare ID | URI completa (`spotify:track:xxx`) |
| Importable por Nuclear | ❌ No | ✅ Sí |

## Estructura del proyecto

```
test-CSV-a-JSON/
├── app.py                    # Servidor Flask (rutas + API)
├── playlist_converter.py     # Lógica de conversión CSV<->JSON v1, migración, edición
├── convert_all.py            # CLI para conversión MASIVA por lotes
├── migrate_old_jsons.py      # 🆕 CLI para migrar JSONs legacy a formato v1
├── requirements.txt          # Dependencias (Flask, Werkzeug)
├── run.bat                   # Lanzador para Windows
├── sample_playlist.csv       # CSV de ejemplo (9 canciones)
├── README.md
├── templates/                # HTML con sintaxis Jinja2
│   ├── base.html
│   ├── index.html
│   ├── edit.html
│   ├── merge.html
│   ├── backups.html
│   └── error.html
├── static/
│   ├── css/style.css
│   └── js/
│       ├── app.js            # utilidades compartidas (helpers para formato v1)
│       ├── index.js          # lógica de la home (incluye modo masivo y migración)
│       ├── edit.js           # lógica del editor (formato v1)
│       ├── merge.js          # lógica de combinar (formato v1 con descripción)
│       └── backups.js        # lógica de respaldos
├── uploads/                  # 📂 TUS CSV van aquí
├── playlists/                # JSON convertidos (los crea la app)
└── backups/                  # Respaldos automáticos (los crea la app)
```

> ⚠️ **Importante**: Los HTML que usan `{{ url_for('static', ...) }}` o `{% extends %}` DEBEN estar en `templates/`, y los CSS/JS DEBEN estar en `static/css/` y `static/js/`. Si los dejas en la raíz, Flask no los encuentra y la página se ve en blanco.

## Instalación y uso (Windows)

1. **Instala Python 3.10+** desde https://www.python.org/downloads/ (marca "Add Python to PATH").
2. **Descarga este proyecto** y descomprímelo en una carpeta.
3. **Doble clic en `run.bat`**. La primera vez tarda un poco porque crea un entorno virtual e instala dependencias.
4. Se abre automáticamente el navegador en `http://127.0.0.1:5000`.
5. Para detener: cierra la ventana negra o pulsa `Ctrl+C`.

## Cómo exportar tus playlists de Spotify

1. Entra a https://exportify.app/
2. Inicia sesión con tu cuenta de Spotify.
3. Selecciona las playlists que quieras exportar y descarga los CSV.
4. **Copia los CSV a la carpeta `uploads/` del proyecto** (puedes seleccionarlos todos en el explorador de Windows y arrastrarlos a esa carpeta).
5. Sigue las instrucciones de "Procesamiento masivo" más abajo.

## 🚀 Procesamiento masivo (muchas playlists a la vez)

Hay dos formas de convertir muchos CSV de una sola vez:

### Opción A — Desde la web (recomendada)

1. **Copia todos tus CSV** a la carpeta `uploads/` del proyecto (desde el explorador de archivos de Windows).
2. Ejecuta `run.bat` y abre `http://127.0.0.1:5000`.
3. En la home verás la tarjeta **⚡ Procesamiento masivo** con el contador de CSV pendientes.
4. Pulsa **↻ Refrescar** si no se actualizó solo.
5. Opcionalmente marca:
   - **Sobrescribir si ya existe** — reemplaza el JSON anterior (crea backup antes).
   - **Borrar CSV originales** — limpia la carpeta `uploads/` después de convertir.
6. Pulsa **⚡ Convertir todos los CSV**.
7. Aparecerá un resumen con: total convertidos, con error, canciones totales.
8. Tus JSON estarán en `playlists/` — descárgalos desde la lista de "Mis playlists".

### Opción B — Desde la consola (sin abrir la web)

Si prefieres no abrir el navegador y solo quieres convertir todo de golpe:

```bash
# Convertir todos los CSV de uploads/ a playlists/
python convert_all.py

# Convertir todos los CSV de una carpeta específica
python convert_all.py "C:\Users\yo\Downloads\mis_csvs"

# Sobrescribir JSON existentes (con backup previo)
python convert_all.py --overwrite

# Borrar los CSV después de convertirlos
python convert_all.py --delete-csv

# Combinar todo
python convert_all.py "C:\csvs" --overwrite --delete-csv
```

El script muestra un progreso `[  1/50]`, `[  2/50]`, ... y al final un resumen:

```
======================================================================
  Resultado: 50 OK, 0 con error, 1247 canciones totales
  JSON guardados en: /home/z/.../playlists
  ¡Todo OK!
======================================================================
```

## 🔄 Migrar playlists viejas al formato v1

Si ya tenías playlists creadas con una versión anterior de esta herramienta (formato legacy con `tracks[]`), puedes migrarlas al nuevo formato Nuclear v1:

### Desde la web

1. Abre la home (`http://127.0.0.1:5000`).
2. En la tarjeta **Mis playlists**, pulsa el botón **🔄 Migrar a v1** (arriba a la derecha).
3. Confirma. Se creará un backup automático de cada playlist antes de migrarla.

### Desde la consola

```bash
# Migrar todos los JSON de playlists/ a v1 (con backup previo)
python migrate_old_jsons.py

# Migrar JSON de otra carpeta
python migrate_old_jsons.py "C:\ruta\a\mis_jsons"

# Ver qué migraría sin tocar archivos
python migrate_old_jsons.py --dry-run

# Migrar sin backup (¡peligroso!)
python migrate_old_jsons.py --no-backup
```

## Cómo importar a Nuclear Player

1. Abre Nuclear Player.
2. Ve a **Playlists** (barra lateral).
3. Pulsa el botón de importar (símbolo `+` o "Import playlist" según versión).
4. Selecciona el archivo `.json` que descargaste desde Playlist Manager.
5. La playlist aparecerá con todas sus canciones; Nuclear intentará buscar cada canción en los proveedores de streaming que tengas configurados.

> 💡 **Tip**: Como el JSON ahora incluye los Spotify Track IDs en el formato correcto (`spotify:track:xxx`), Nuclear puede encontrar las canciones directamente sin necesidad de buscar por título/artista.

## Uso desde línea de comandos (sin interfaz web)

Si solo quieres convertir un CSV a JSON sin abrir el navegador:

```bash
python playlist_converter.py mi_playlist.csv -o salida.json -n "Mi Playlist"
```

## Diagnóstico de problemas

### Nuclear no reconoce los JSON al importarlos

Este era el bug de la versión 1.x de la herramienta: el formato producido era un invento propio (`{id, name, tracks[], createdAt}`) que Nuclear no reconoce.

**Solución**: Actualiza a esta versión (2.x) y vuelve a generar tus JSON. El nuevo formato sigue EXACTAMENTE el esquema que Nuclear Player exporta al importar una playlist por URL desde la propia app. Si tienes JSONs viejos, usa el botón **🔄 Migrar a v1** o ejecuta `python migrate_old_jsons.py`.

### La página web se ve en blanco / no carga

Causa casi segura: los HTML no están en `templates/` o los CSS/JS no están en `static/`. Verifica la estructura mostrada arriba.

### ERR_CONNECTION_REFUSED al abrir el navegador

En versiones anteriores, `debug=True` en `app.run()` hacía que Flask arrancara dos veces (una en 5000, otra en 5001 porque el primero estaba ocupado). El navegador abría 5000 pero el servidor respondía en 5001.

**Solución**: Esta versión usa `debug=False, use_reloader=False`. Además, `run.bat` mata procesos previos en el puerto 5000 antes de arrancar.

### El puerto 5000 está ocupado

El `app.py` prueba automáticamente puertos del 5000 al 5010 y usa el primero libre. Mira la consola para ver qué puerto eligió.

### `python` o `py` no se reconoce

Instala Python desde https://www.python.org/downloads/ y **marca "Add Python to PATH"** durante la instalación. Cierra y vuelve a abrir la consola.

### El CSV no se convierte (0 tracks)

Abre el CSV con un editor de texto (no Excel) y verifica que la primera fila tenga cabeceras como `Track Name`, `Artist Name(s)`, `Album Name`, `Duration (ms)`. El conversor es robusto con variaciones de nombre (español, inglés, portugués, etc.) y soporta BOM, pero si los campos faltan por completo no hay nada que convertir.

### Health check

Abre `http://127.0.0.1:5000/api/health` para ver el estado del servidor y las carpetas que está usando. Debe mostrar `schema_version: nuclear-v1`.

## API REST

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET    | `/api/playlists` | Lista playlists convertidas (con flag `is_v1`) |
| GET    | `/api/playlists/<filename>` | Detalle de una playlist (siempre en formato v1) |
| POST   | `/api/upload-csv` | Sube CSVs (multipart) |
| POST   | `/api/convert-all-uploads` | Convierte todos los CSV de `uploads/` a v1 |
| GET    | `/api/uploads` | Lista CSV pendientes en `uploads/` |
| DELETE | `/api/uploads/clear` | Vacía la carpeta `uploads/` |
| POST   | `/api/migrate-all-to-v1` | 🆕 Migra JSONs legacy a formato v1 |
| PUT    | `/api/playlists/<filename>` | Guarda cambios (renombrar, tracks, save_as_new) en v1 |
| DELETE | `/api/playlists/<filename>` | Elimina playlist (con backup) |
| POST   | `/api/playlists/<filename>/add-track` | Añade canción (formato v1 con artwork sintetizado) |
| DELETE | `/api/playlists/<filename>/remove-track/<index>` | Elimina canción por índice |
| POST   | `/api/playlists/<filename>/reorder` | Reordena canciones (lista de item IDs) |
| POST   | `/api/merge` | Combina varias playlists en v1 |
| GET    | `/api/backups` | Lista respaldos |
| GET    | `/api/backups/<filename>` | Descarga respaldo |
| POST   | `/api/backups/<filename>/restore` | Restaura respaldo |
| DELETE | `/api/backups/<filename>` | Elimina respaldo |
| GET    | `/api/download/<filename>` | Descarga playlist JSON (normaliza a v1 si era legacy) |
| GET    | `/api/health` | Estado del servidor |

## Licencia

MIT.
