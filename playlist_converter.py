"""
Conversor de playlists CSV (Exportify) a JSON (formato Nuclear Player).

Formato Exportify (Spotify CSV):
    Spotify ID, Artist IDs, Track Name, Album Name, Artist Name(s),
    Release Date, Duration (ms), Popularity, Added By, Added At, Genres,
    Danceability, Energy, Key, Loudness, Mode, Speechiness, Acousticness,
    Instrumentalness, Liveness, Valence, Tempo, Time Signature

Formato Nuclear Player (JSON):
    {
        "id": "uuid",
        "name": "Playlist Name",
        "tracks": [
            {
                "uuid": "uuid",
                "name": "Track Name",
                "artist": { "name": "Artist Name" },
                "album": "Album Name",
                "duration": 240,
                "position": 0,
                "thumbnail": "",
                "stream": { "source": "", "id": "" }
            }
        ]
    }
"""
from __future__ import annotations

import csv
import json
import os
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Detección de columnas
# ---------------------------------------------------------------------------

# Nombres de columnas posibles en CSVs de Exportify (varía según versión e idioma).
# Exportify usa el idioma de la cuenta de Spotify del usuario, así que pueden
# venir cabeceras en inglés, español, portugués, francés, alemán, etc.
COLUMN_ALIASES = {
    "track_name": [
        # Español (formato nuevo de Spotify/Exportify)
        "Nombre de la canción", "Nombre de la cancion",
        # Inglés (formato clásico Exportify)
        "Track Name", "Track name",
        # Exportify v3+
        "track_name", "name", "Name",
        # Otros
        "titulo", "Título", "Titulo", "Canción", "Cancion",
    ],
    "album_name": [
        "Nombre del álbum", "Nombre del album",
        "Album Name", "Album",
        "album_name", "album",
        "Álbum", "Album",
    ],
    "artist_name": [
        "Nombre(s) del artista", "Nombre(s) de los artistas",
        "Artist Name(s)", "Artist Name", "Artist(s)",
        "artist_name", "artist", "Artista", "Artistas",
    ],
    "duration_ms": [
        "Duración de la canción (ms)", "Duración de la canción",
        "Duration (ms)", "Duration",
        "duration_ms", "duration",
        "Duración (ms)", "Duracion (ms)", "Duración", "Duracion",
    ],
    "duration_s": ["Duration (s)", "duration_s", "Duración (s)", "Duracion (s)"],
    "spotify_id": [
        "URI de la canción", "URI de la cancion",
        "Spotify ID", "spotify_id", "id", "URI",
        "Spotify URI",
    ],
    "album_art": [
        "URL de la imagen del álbum", "URL de la imagen del album",
        "Album Art URL", "album_art", "thumbnail", "Thumbnail",
        "Imagen del álbum", "Imagen", "Cover URL",
    ],
    "release_date": [
        "Fecha de lanzamiento del álbum", "Fecha de lanzamiento",
        "Release Date", "release_date",
        "Lanzamiento",
    ],
    "popularity": ["Popularity", "popularidad", "Popularidad"],
    "added_at": ["Added At", "added_at", "Añadido en", "Agregado en", "Added"],
    "genres": ["Genres", "genres", "Géneros", "Generos"],
}


def _normalize_header(header: str) -> str:
    """
    Normaliza un encabezado para comparación robusta.

    Quita espacios, _, -, baja a minúsculas y ELIMINA TILDES,
    para que 'Álbum' == 'Album' y 'Canción' == 'Cancion'.
    """
    if not header:
        return ""
    # Quitar tildes/diacríticos (á->a, é->e, ñ->n, ü->u, etc.)
    nfkd = unicodedata.normalize("NFKD", header)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Bajar a minúsculas y quitar espacios/_, -
    return sin_tildes.strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _build_header_map(headers: List[str]) -> Dict[str, str]:
    """Construye un mapa campo_canonico -> columna_real_en_csv."""
    norm_to_real = {_normalize_header(h): h for h in headers}
    mapping: Dict[str, str] = {}
    for canon, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            norm = _normalize_header(alias)
            if norm in norm_to_real:
                mapping[canon] = norm_to_real[norm]
                break
    return mapping


# ---------------------------------------------------------------------------
# Parsing del CSV
# ---------------------------------------------------------------------------

def parse_exportify_csv(csv_path: str) -> List[Dict[str, Any]]:
    """
    Lee un CSV de Exportify y devuelve una lista de tracks normalizados.

    Cada track tiene:
        - name: str
        - artist: str (uno o varios artistas separados por coma)
        - album: str
        - duration: int (segundos)
        - thumbnail: str
        - spotify_id: str
        - extra: dict (metadatos adicionales)
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV no encontrado: {csv_path}")

    # Detectar delimitador (algunos Exportify usan ; en regiones europeas).
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        sample = f.read(4096)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = None

    with open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        if dialect:
            reader = csv.DictReader(f, dialect=dialect)
        else:
            reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    if not rows:
        return []

    header_map = _build_header_map(fieldnames)

    tracks: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        name = row.get(header_map.get("track_name", ""), "").strip()
        if not name:
            # Saltar filas vacías o sin título
            continue

        artist = row.get(header_map.get("artist_name", ""), "").strip()
        album = row.get(header_map.get("album_name", ""), "").strip()

        # Duración: preferimos ms (Exportify), convertimos a segundos.
        duration = 0
        if "duration_ms" in header_map:
            raw = row.get(header_map["duration_ms"], "0").strip()
            try:
                duration = int(float(raw)) // 1000
            except (ValueError, TypeError):
                duration = 0
        elif "duration_s" in header_map:
            raw = row.get(header_map["duration_s"], "0").strip()
            try:
                duration = int(float(raw))
            except (ValueError, TypeError):
                duration = 0

        thumbnail = row.get(header_map.get("album_art", ""), "").strip()
        spotify_id_raw = row.get(header_map.get("spotify_id", ""), "").strip()
        # Si viene como URI (spotify:track:xxxx), extraer solo el ID
        spotify_id = spotify_id_raw
        if spotify_id_raw.startswith("spotify:track:"):
            spotify_id = spotify_id_raw.rsplit(":", 1)[-1]
        elif spotify_id_raw.startswith("https://open.spotify.com/track/"):
            spotify_id = spotify_id_raw.rsplit("/", 1)[-1].split("?")[0]

        # Conservar metadatos extra por si el usuario quiere re-exportar.
        extra = {
            "release_date": row.get(header_map.get("release_date", ""), "").strip(),
            "popularity": row.get(header_map.get("popularity", ""), "").strip(),
            "added_at": row.get(header_map.get("added_at", ""), "").strip(),
            "genres": row.get(header_map.get("genres", ""), "").strip(),
        }
        # Limpiar vacíos
        extra = {k: v for k, v in extra.items() if v}

        tracks.append({
            "name": name,
            "artist": artist,
            "album": album,
            "duration": duration,
            "thumbnail": thumbnail,
            "spotify_id": spotify_id,
            "extra": extra,
            "position": idx,
        })

    return tracks


# ---------------------------------------------------------------------------
# Conversión a formato Nuclear Player
# ---------------------------------------------------------------------------

def to_nuclear_track(track: Dict[str, Any]) -> Dict[str, Any]:
    """Convierte un track normalizado al formato Nuclear Player."""
    # En Nuclear, "artist" puede ser string o { "name": "..." }
    artist_name = track.get("artist", "")
    nuclear_track = {
        "uuid": str(uuid.uuid4()),
        "name": track.get("name", ""),
        "artist": {"name": artist_name} if artist_name else {"name": ""},
        "album": track.get("album", ""),
        "duration": int(track.get("duration", 0) or 0),
        "position": track.get("position", 0),
        "thumbnail": track.get("thumbnail", ""),
        "stream": {
            "source": "",
            "id": "",
        },
    }
    # Conservar el ID de Spotify como referencia (Nuclear puede usarlo para buscar).
    if track.get("spotify_id"):
        nuclear_track["stream"] = {
            "source": "spotify",
            "id": track["spotify_id"],
        }
    return nuclear_track


def build_nuclear_playlist(name: str, tracks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Construye un objeto playlist completo en formato Nuclear Player."""
    nuclear_tracks = []
    for idx, track in enumerate(tracks):
        track_copy = dict(track)
        track_copy["position"] = idx
        nuclear_track = to_nuclear_track(track_copy)
        nuclear_tracks.append(nuclear_track)
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "tracks": nuclear_tracks,
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# I/O JSON
# ---------------------------------------------------------------------------

def save_playlist_json(playlist: Dict[str, Any], output_path: str) -> None:
    """Guarda una playlist como JSON con UTF-8 y indentación."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(playlist, f, ensure_ascii=False, indent=2)


def load_playlist_json(input_path: str) -> Dict[str, Any]:
    """Carga una playlist desde un archivo JSON."""
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"JSON no encontrado: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_playlists_in_dir(directory: str) -> List[Dict[str, Any]]:
    """Lista todas las playlists JSON en un directorio."""
    directory = Path(directory)
    if not directory.exists():
        return []
    result = []
    for fp in sorted(directory.glob("*.json")):
        try:
            data = load_playlist_json(str(fp))
            result.append({
                "filename": fp.name,
                "path": str(fp),
                "name": data.get("name", fp.stem),
                "tracks_count": len(data.get("tracks", [])),
                "size_bytes": fp.stat().st_size,
                "modified": datetime.fromtimestamp(fp.stat().st_mtime).isoformat(),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return result


def sanitize_filename(name: str) -> str:
    """Convierte un nombre en un nombre de archivo seguro."""
    keep = "-_."
    out = []
    for ch in name.strip():
        if ch.isalnum() or ch in keep:
            out.append(ch)
        elif ch in " /\\__":
            out.append("_")
    cleaned = "".join(out).strip("._")
    return cleaned or "playlist"


# ---------------------------------------------------------------------------
# Combinar playlists
# ---------------------------------------------------------------------------

def merge_playlists(
    playlists: List[Dict[str, Any]],
    new_name: str,
    dedupe: bool = True,
) -> Dict[str, Any]:
    """
    Combina varias playlists en una nueva.

    Args:
        playlists: Lista de objetos playlist formato Nuclear.
        new_name: Nombre de la playlist resultante.
        dedupe: Si True, elimina duplicados (mismo name + artist).

    Returns:
        Nueva playlist en formato Nuclear Player.
    """
    seen = set()
    merged_tracks: List[Dict[str, Any]] = []
    for playlist in playlists:
        for track in playlist.get("tracks", []):
            name = (track.get("name") or "").strip().lower()
            artist = ""
            if isinstance(track.get("artist"), dict):
                artist = (track["artist"].get("name") or "").strip().lower()
            elif isinstance(track.get("artist"), str):
                artist = track["artist"].strip().lower()

            key = (name, artist) if dedupe else None
            if dedupe and key in seen:
                continue
            if dedupe:
                seen.add(key)

            # Copiar y reasignar uuid/position
            new_track = dict(track)
            new_track["uuid"] = str(uuid.uuid4())
            new_track["position"] = len(merged_tracks)
            merged_tracks.append(new_track)

    return {
        "id": str(uuid.uuid4()),
        "name": new_name,
        "tracks": merged_tracks,
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "merged_from": [p.get("name", "") for p in playlists],
    }


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

def create_backup(
    source_path: str,
    backup_dir: str,
    prefix: str = "",
) -> str:
    """
    Copia un archivo a la carpeta de backups con timestamp.

    Returns:
        Ruta del archivo de backup creado.
    """
    source_path = Path(source_path)
    if not source_path.exists():
        return ""

    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{prefix}{source_path.stem}_{timestamp}{source_path.suffix}"
    backup_path = backup_dir / backup_name

    # Si ya existe (poco probable), añadir contador
    counter = 1
    while backup_path.exists():
        backup_name = f"{prefix}{source_path.stem}_{timestamp}_{counter}{source_path.suffix}"
        backup_path = backup_dir / backup_name
        counter += 1

    # Copiar contenido
    with open(source_path, "r", encoding="utf-8") as src:
        content = src.read()
    with open(backup_path, "w", encoding="utf-8") as dst:
        dst.write(content)

    return str(backup_path)


def list_backups(backup_dir: str) -> List[Dict[str, Any]]:
    """Lista los backups disponibles con metadatos."""
    backup_dir = Path(backup_dir)
    if not backup_dir.exists():
        return []
    result = []
    for fp in sorted(backup_dir.glob("*.json"), reverse=True):
        stat = fp.stat()
        result.append({
            "filename": fp.name,
            "path": str(fp),
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return result


def restore_backup(backup_path: str, target_path: str) -> str:
    """Restaura un backup a una ruta destino (haciendo backup del actual antes)."""
    backup_path = Path(backup_path)
    target_path = Path(target_path)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup no encontrado: {backup_path}")

    with open(backup_path, "r", encoding="utf-8") as f:
        content = f.read()
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)
    return str(target_path)


# ---------------------------------------------------------------------------
# CLI básico (uso sin interfaz web)
# ---------------------------------------------------------------------------

def cli_convert(csv_path: str, output_path: str, playlist_name: Optional[str] = None) -> str:
    """Convierte un CSV a JSON desde línea de comandos."""
    tracks = parse_exportify_csv(csv_path)
    if not playlist_name:
        playlist_name = Path(csv_path).stem
    playlist = build_nuclear_playlist(playlist_name, tracks)
    save_playlist_json(playlist, output_path)
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convierte playlists CSV (Exportify) a JSON (Nuclear Player)."
    )
    parser.add_argument("csv", help="Ruta al archivo CSV de Exportify")
    parser.add_argument("-o", "--output", help="Ruta de salida JSON")
    parser.add_argument("-n", "--name", help="Nombre de la playlist (por defecto: nombre del CSV)")

    args = parser.parse_args()
    output = args.output or f"playlists/{Path(args.csv).stem}.json"
    result = cli_convert(args.csv, output, args.name)
    print(f"Playlist convertida: {result}")
