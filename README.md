# Playlist Manager — Exportify CSV ↔ Nuclear Player JSON

Aplicación web local (Flask) para convertir playlists exportadas desde [exportify.app](https://exportify.app/) (CSV de Spotify) al formato JSON que usa [Nuclear Player](https://nuclearplayer.com/), y gestionarlas después desde el navegador.

## Características

- **Conversión CSV → JSON** con detección robusta de columnas (Exportify cambia nombres entre versiones).
- **Editor web** para renombrar la playlist, agregar o eliminar canciones, y reordenar arrastrando.
- **Combinar varias playlists** en una nueva (con opción de eliminar duplicados).
- **Guardar como** nueva playlist o sobrescribir la actual.
- **Backups automáticos** en la carpeta `backups/` antes de cualquier sobrescritura o eliminación.
- **Restaurar respaldos** con un clic (siempre hace un backup del estado actual antes).
- **Descargar JSON** listo para importar en Nuclear Player.

## Estructura del proyecto

```
test-CSV-a-JSON/
├── app.py                    # Servidor Flask (rutas + API)
├── playlist_converter.py     # Lógica de conversión CSV<->JSON y backups
├── convert_all.py            # 🆕 CLI para conversión MASIVA por lotes
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
│       ├── app.js            # utilidades compartidas
│       ├── index.js          # lógica de la home (incluye modo masivo)
│       ├── edit.js           # lógica del editor
│       ├── merge.js          # lógica de combinar
│       └── backups.js        # lógica de respaldos
├── uploads/                  # 📂 TUS CSV van aquí
├── playlists/                # JSON convertidos (los crea la app)
└── backups/                  # Respaldos automáticos (los crea la app)
```

> ⚠️ **Importante**: Los HTML que usan `{{ url_for('static', ...) }}` o `{% extends %}` DEBEN estar en `templates/`, y los CSS/JS DEBEN estar en `static/css/` y `static/js/`. Si los dejas en la raíz, Flask no los encuentra y la página se ve en blanco — ese era el bug de la versión anterior.

## Instalación y uso (Windows)

1. **Instala Python 3.10+** desde https://www.python.org/downloads/ (marca "Add Python to PATH").
2. **Descarga este proyecto** y descomprímelo en una carpeta.
3. **Doble clic en `run.bat`**. La primera vez tarda un poco porque crea un entorno virtual e instala dependencias.
4. Se abre automáticamente el servidor. Abre `http://127.0.0.1:5000` en el navegador.
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

## Cómo importar a Nuclear Player

1. Abre Nuclear Player.
2. Ve a **Playlists** (barra lateral).
3. Pulsa el botón de importar (símbolo `+` o "Import playlist" según versión).
4. Selecciona el archivo `.json` que descargaste desde Playlist Manager.
5. La playlist aparecerá con todas sus canciones; Nuclear intentará buscar cada canción en los proveedores de streaming que tengas configurados.

## Uso desde línea de comandos (sin interfaz web)

Si solo quieres convertir un CSV a JSON sin abrir el navegador:

```bash
python playlist_converter.py mi_playlist.csv -o salida.json -n "Mi Playlist"
```

## Diagnóstico de problemas

### La página web se ve en blanco / no carga

Causa casi segura: los HTML no están en `templates/` o los CSS/JS no están en `static/`. Verifica la estructura mostrada arriba. Si clonaste el repo viejo, los archivos están sueltos en la raíz — solo muévelos:

```
mkdir templates static\css static\js
move *.html templates\
move style.css static\css\
move *.js static\js\
```

### El puerto 5000 está ocupado

El `app.py` ahora prueba automáticamente puertos del 5000 al 5010 y usa el primero libre. Mira la consola para ver qué puerto eligió.

### `python` o `py` no se reconoce

Instala Python desde https://www.python.org/downloads/ y **marca "Add Python to PATH"** durante la instalación. Cierra y vuelve a abrir la consola.

### El CSV no se convierte (0 tracks)

Abre el CSV con un editor de texto (no Excel) y verifica que la primera fila tenga cabeceras como `Track Name`, `Artist Name(s)`, `Album Name`, `Duration (ms)`. El conversor es robusto con variaciones de nombre, pero si los campos faltan por completo no hay nada que convertir.

### Health check

Abre `http://127.0.0.1:5000/api/health` para ver el estado del servidor y las carpetas que está usando.

## API REST

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET    | `/api/playlists` | Lista playlists convertidas |
| GET    | `/api/playlists/<filename>` | Detalle de una playlist |
| POST   | `/api/upload-csv` | Sube CSVs (multipart) |
| POST   | `/api/convert-all-uploads` | 🆕 Convierte todos los CSV de `uploads/` |
| GET    | `/api/uploads` | 🆕 Lista CSV pendientes en `uploads/` |
| DELETE | `/api/uploads/clear` | 🆕 Vacía la carpeta `uploads/` |
| PUT    | `/api/playlists/<filename>` | Guarda cambios (renombrar, tracks, save_as_new) |
| DELETE | `/api/playlists/<filename>` | Elimina playlist (con backup) |
| POST   | `/api/playlists/<filename>/add-track` | Añade canción |
| DELETE | `/api/playlists/<filename>/remove-track/<uuid>` | Elimina canción |
| POST   | `/api/playlists/<filename>/reorder` | Reordena canciones |
| POST   | `/api/merge` | Combina varias playlists |
| GET    | `/api/backups` | Lista respaldos |
| GET    | `/api/backups/<filename>` | Descarga respaldo |
| POST   | `/api/backups/<filename>/restore` | Restaura respaldo |
| DELETE | `/api/backups/<filename>` | Elimina respaldo |
| GET    | `/api/download/<filename>` | Descarga playlist JSON |
| GET    | `/api/health` | Estado del servidor |

## Formato Nuclear Player (JSON)

El JSON que produce esta herramienta sigue este esquema:

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
      "duration": 354,
      "position": 0,
      "thumbnail": "",
      "stream": { "source": "", "id": "" }
    }
  ],
  "createdAt": "2024-01-15T10:30:00.000000Z"
}
```

Si tu versión de Nuclear espera campos distintos, edita `playlist_converter.py::to_nuclear_track` y `build_nuclear_playlist`.

## Licencia

MIT.
