"""
Conversor de playlists CSV (Exportify) a JSON (formato Nuclear Player).

Formato Exportify (Spotify CSV):
    Spotify ID, Artist IDs, Track Name, Album Name, Artist Name(s),
    Release Date, Duration (ms), Popularity, Added By, Added At, Genres,
    Danceability, Energy, Key, Loudness, Mode, Speechiness, Acousticness,
    Instrumentalness, Liveness, Valence, Tempo, Time Signature

Formato Nuclear Player (JSON real, v1):
    {
      "version": 1,
      "playlist": {
        "id": "uuid",
        "name": "Playlist Name",
        "description": "",
        "artwork": { "items": [{"url": "..."}] },
        "createdAtIso": "ISO-8601",
        "lastModifiedIso": "ISO-8601",
        "origin": { "provider": "...", "id": "...", "url": "..." },
        "isReadOnly": false,
        "items": [
          {
            "id": "16-hex-chars",
            "addedAtIso": "ISO-8601",
            "track": {
              "title": "Track Name",
              "artists": [
                {
                  "name": "Artist Name",
                  "roles": [],
                  "source": { "provider": "spotify", "id": "spotify:artist:..." }
                }
              ],
              "album": {
                "title": "Album Name",
                "artwork": { "items": [{"url": "...", "width": 300, "height": 300}, ...] },
                "source": { "provider": "spotify", "id": "spotify:album:..." }
              },
              "durationMs": 235000,
              "trackNumber": 1,
              "disc": "1",
              "artwork": { "items": [...] },
              "source": { "provider": "spotify", "id": "spotify:track:..." }
            }
          }
        ]
      }
    }
"""
from __future__ import annotations

import csv
import json
import os
import re
import secrets
import unicodedata
import uuid
from datetime import datetime, timezone
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
        "Nombre de la canción", "Nombre de la cancion",
        "Track Name", "Track name",
        "track_name", "name", "Name",
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
    "artist_ids": [
        "Artist IDs", "Artist ID(s)", "Artist ID",
        "IDs de artista", "IDs de artistas", "ID de artista",
        "artist_ids", "artist_id",
    ],
    "album_id": [
        "Album ID", "Album URI", "URI del álbum", "URI del album",
        "album_id", "album_uri",
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
        "Spotify URI", "Track URI", "Track ID",
    ],
    "album_art": [
        "URL de la imagen del álbum", "URL de la imagen del album",
        "Album Art URL", "album_art", "thumbnail", "Thumbnail",
        "Imagen del álbum", "Imagen", "Cover URL",
        "Album Art", "Cover",
    ],
    "release_date": [
        "Fecha de lanzamiento del álbum", "Fecha de lanzamiento",
        "Release Date", "release_date",
        "Lanzamiento",
    ],
    "popularity": ["Popularity", "popularidad", "Popularidad"],
    "added_at": ["Added At", "added_at", "Añadido en", "Agregado en", "Added"],
    "genres": ["Genres", "genres", "Géneros", "Generos"],
    "track_number": ["Track Number", "track_number", "Número de pista", "Numero de pista"],
    "disc_number": ["Disc Number", "disc_number", "Disco"],
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
# Utilidades para IDs de Spotify y artwork
# ---------------------------------------------------------------------------

def _to_spotify_uri(raw_id: str, kind: str = "track") -> Optional[str]:
    """
    Convierte un ID de Spotify en una URI completa 'spotify:track:xxxx'.
    Acepta:
        - ID pelado: 7xA5iKvUOIQQj9yVe5OquS
        - URI: spotify:track:7xA5iKvUOIQQj9yVe5OquS
        - URL: https://open.spotify.com/track/7xA5iKvUOIQQj9yVe5OquS
    Devuelve None si el input está vacío o no es recognizable.
    """
    if not raw_id:
        return None
    raw_id = raw_id.strip()
    if not raw_id:
        return None

    # Caso URI completa
    if raw_id.startswith(f"spotify:{kind}:"):
        return raw_id

    # Caso URL
    if "open.spotify.com" in raw_id:
        m = re.search(rf"/{kind}/([A-Za-z0-9]+)", raw_id)
        if m:
            return f"spotify:{kind}:{m.group(1)}"
        return None

    # Caso ID pelado (Spotify IDs son base62 de 22 chars)
    if re.fullmatch(r"[A-Za-z0-9]{16,30}", raw_id):
        return f"spotify:{kind}:{raw_id}"

    return None


def _to_bare_spotify_id(raw_id: str, kind: str = "track") -> Optional[str]:
    """Devuelve solo el ID (sin prefijo spotify:track:)."""
    uri = _to_spotify_uri(raw_id, kind)
    if not uri:
        return None
    return uri.rsplit(":", 1)[-1]


# Spotify CDN size markers (encontrados en el JSON real exportado por Nuclear):
#   ab67616d00001e02 = 300x300
#   ab67616d00004851 = 64x64
#   ab67616d0000b273 = 640x640
# Si la URL contiene uno de estos markers, podemos sintetizar los otros tamaños.
_SPOTIFY_CDN_SIZE_MARKERS = {
    300: "00001e02",
    64: "00004851",
    640: "0000b273",
}


def _build_artwork_items(url: str) -> List[Dict[str, Any]]:
    """
    Construye el array de artwork items con múltiples tamaños.
    Si es una URL de Spotify CDN, sintetiza 64/300/640.
    Si no, devuelve un único item sin width/height.
    """
    if not url or not url.strip():
        return []
    url = url.strip()

    # Detectar si es URL de Spotify CDN con marker de tamaño
    m = re.search(r"(ab67616d)([0-9a-fA-F]{8})", url)
    if m:
        prefix = m.group(1)
        items = []
        for size, marker in _SPOTIFY_CDN_SIZE_MARKERS.items():
            sized_url = url.replace(prefix + m.group(2), prefix + marker)
            items.append({"url": sized_url, "width": size, "height": size})
        return items

    # URL genérica: devolver un solo item sin dimensiones
    return [{"url": url}]


def _split_artists(names_str: str, ids_str: str = "") -> List[Tuple[str, Optional[str]]]:
    """
    Separa 'Awakend, Rickie Nolls' y '4lFbV0wEuW8ulSq6NBYg4O,4kbFvZah1kAfBm1kM66Nj6'
    en [(name, artist_id), ...].
    Maneja comas y punto y coma como separadores.
    """
    if not names_str:
        return []
    # Split por coma o punto y coma
    names = [n.strip() for n in re.split(r"[,;]", names_str) if n.strip()]
    if not ids_str:
        ids = []
    else:
        ids = [i.strip() for i in re.split(r"[,;]", ids_str) if i.strip()]
    # Emparejar
    result = []
    for idx, name in enumerate(names):
        artist_id = ids[idx] if idx < len(ids) else None
        result.append((name, artist_id))
    return result


def _now_iso() -> str:
    """ISO timestamp con milisegundos y Z (formato que usa Nuclear)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
           f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


def _parse_iso_date(raw: str) -> Optional[str]:
    """
    Convierte una fecha de Added At (que puede venir en varios formatos)
    a ISO 8601 con Z. Devuelve None si no puede parsear.
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    # Si ya viene como ISO con Z, devolver tal cual
    if re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", raw):
        # Asegurar que termine en Z
        if raw.endswith("Z"):
            return raw
        # Si tiene zona horaria tipo +00:00, convertir a Z
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
                   f"{dt.microsecond // 1000:03d}Z"
        except ValueError:
            return raw + "Z"
    # Probar formatos comunes: YYYY-MM-DD, YYYY/MM/DD
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"
        except ValueError:
            continue
    return None


def _generate_item_id() -> str:
    """Genera un ID de 16 hex chars como los que usa Nuclear para items."""
    return secrets.token_hex(8)


# ---------------------------------------------------------------------------
# Parsing del CSV
# ---------------------------------------------------------------------------

def parse_exportify_csv(csv_path: str) -> List[Dict[str, Any]]:
    """
    Lee un CSV de Exportify y devuelve una lista de tracks normalizados.

    Cada track tiene:
        - name: str
        - artist: str (uno o varios artistas separados por coma)
        - artists: List[Tuple[str, Optional[str]]]  (nombre, spotify_artist_id)
        - album: str
        - album_id: Optional[str]  (Spotify album ID)
        - duration_ms: int
        - duration: int (segundos, legacy)
        - thumbnail: str
        - spotify_id: str (bare ID sin prefijo)
        - track_number: Optional[int]
        - disc_number: Optional[str]
        - added_at_iso: Optional[str]
        - extra: dict (metadatos adicionales)
        - position: int
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV no encontrado: {csv_path}")

    # Detectar BOM y encoding
    raw_bytes = csv_path.read_bytes()[:4]
    encoding = "utf-8-sig" if raw_bytes.startswith(b"\xef\xbb\xbf") else "utf-8"

    # Detectar delimitador (algunos Exportify usan ; en regiones europeas).
    with open(csv_path, "r", encoding=encoding, errors="replace") as f:
        sample = f.read(4096)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = None

    with open(csv_path, "r", encoding=encoding, errors="replace", newline="") as f:
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

        # Artist IDs (lista separada por comas)
        artist_ids_raw = row.get(header_map.get("artist_ids", ""), "").strip()
        artists_pairs = _split_artists(artist, artist_ids_raw)

        # Album ID
        album_id_raw = row.get(header_map.get("album_id", ""), "").strip()
        album_id = _to_bare_spotify_id(album_id_raw, "album") if album_id_raw else None

        # Duración: preferimos ms (Exportify), y guardamos ambos.
        duration_ms = 0
        if "duration_ms" in header_map:
            raw = row.get(header_map["duration_ms"], "0").strip()
            try:
                duration_ms = int(float(raw))
            except (ValueError, TypeError):
                duration_ms = 0
        elif "duration_s" in header_map:
            raw = row.get(header_map["duration_s"], "0").strip()
            try:
                duration_ms = int(float(raw)) * 1000
            except (ValueError, TypeError):
                duration_ms = 0
        duration_s = duration_ms // 1000

        thumbnail = row.get(header_map.get("album_art", ""), "").strip()
        spotify_id_raw = row.get(header_map.get("spotify_id", ""), "").strip()
        spotify_id = _to_bare_spotify_id(spotify_id_raw, "track") or spotify_id_raw

        # Track number / disc
        track_number = None
        if "track_number" in header_map:
            tn_raw = row.get(header_map["track_number"], "").strip()
            try:
                track_number = int(float(tn_raw)) if tn_raw else None
            except (ValueError, TypeError):
                track_number = None
        disc_number = None
        if "disc_number" in header_map:
            disc_raw = row.get(header_map["disc_number"], "").strip()
            if disc_raw:
                disc_number = disc_raw

        # Added At (ISO)
        added_at_raw = row.get(header_map.get("added_at", ""), "").strip()
        added_at_iso = _parse_iso_date(added_at_raw) if added_at_raw else None

        # Conservar metadatos extra por si el usuario quiere re-exportar.
        extra = {
            "release_date": row.get(header_map.get("release_date", ""), "").strip(),
            "popularity": row.get(header_map.get("popularity", ""), "").strip(),
            "genres": row.get(header_map.get("genres", ""), "").strip(),
            "added_at_raw": added_at_raw,
        }
        # Limpiar vacíos
        extra = {k: v for k, v in extra.items() if v}

        tracks.append({
            "name": name,
            "artist": artist,
            "artists": artists_pairs,
            "album": album,
            "album_id": album_id,
            "duration_ms": duration_ms,
            "duration": duration_s,
            "thumbnail": thumbnail,
            "spotify_id": spotify_id,
            "track_number": track_number,
            "disc_number": disc_number,
            "added_at_iso": added_at_iso,
            "extra": extra,
            "position": idx,
        })

    return tracks


# ---------------------------------------------------------------------------
# Conversión a formato Nuclear Player (versión 1, real)
# ---------------------------------------------------------------------------

def _build_nuclear_artist(name: str, spotify_artist_id: Optional[str]) -> Dict[str, Any]:
    """Construye un objeto artist en formato Nuclear."""
    artist: Dict[str, Any] = {
        "name": name,
        "roles": [],
    }
    if spotify_artist_id:
        artist["source"] = {
            "provider": "spotify",
            "id": f"spotify:artist:{spotify_artist_id}",
        }
    return artist


def _build_nuclear_album(title: str, album_id: Optional[str], artwork_url: str) -> Dict[str, Any]:
    """Construye un objeto album en formato Nuclear. Siempre incluye 'artwork' (aunque vacío)."""
    album: Dict[str, Any] = {
        "title": title,
        "artwork": {"items": _build_artwork_items(artwork_url) if artwork_url else []},
    }
    if album_id:
        album["source"] = {
            "provider": "spotify",
            "id": f"spotify:album:{album_id}",
        }
    return album


def to_nuclear_item(track: Dict[str, Any], position: int, now_iso: Optional[str] = None) -> Dict[str, Any]:
    """
    Convierte un track normalizado a un 'item' de Nuclear Player.

    Un item tiene: {id, addedAtIso, track: {...}}
    """
    if now_iso is None:
        now_iso = _now_iso()

    artists_pairs = track.get("artists") or []
    if not artists_pairs:
        # Fallback: si no hay artists parseados, usar el string 'artist'
        artist_str = track.get("artist", "")
        if artist_str:
            artists_pairs = _split_artists(artist_str, "")

    nuclear_artists = [
        _build_nuclear_artist(name, artist_id)
        for name, artist_id in artists_pairs
    ]
    if not nuclear_artists:
        # Al menos un artist vacío para no romper el schema
        nuclear_artists = [_build_nuclear_artist("", None)]

    artwork_url = track.get("thumbnail", "") or ""
    nuclear_album = _build_nuclear_album(
        track.get("album", "") or "",
        track.get("album_id"),
        artwork_url,
    )

    # durationMs: si el track viene de un JSON viejo (que tenía 'duration' en segundos)
    # convertirlo a ms.
    duration_ms = track.get("duration_ms")
    if not duration_ms:
        duration_s = track.get("duration", 0) or 0
        duration_ms = int(duration_s) * 1000
    duration_ms = int(duration_ms)

    # Spotify track URI
    spotify_id = track.get("spotify_id", "")
    track_source = None
    if spotify_id:
        track_source = {
            "provider": "spotify",
            "id": f"spotify:track:{spotify_id}",
        }

    # Artwork del track (igual al del album normalmente)
    track_artwork = {"items": _build_artwork_items(artwork_url)} if artwork_url else {"items": []}

    # trackNumber y disc
    track_number = track.get("track_number") or (position + 1)
    disc_number = track.get("disc_number") or "1"

    added_at_iso = track.get("added_at_iso") or now_iso

    nuclear_track: Dict[str, Any] = {
        "title": track.get("name", ""),
        "artists": nuclear_artists,
        "album": nuclear_album,
        "durationMs": duration_ms,
        "trackNumber": int(track_number),
        "disc": str(disc_number),
        "artwork": track_artwork,
    }
    if track_source:
        nuclear_track["source"] = track_source

    return {
        "id": _generate_item_id(),
        "addedAtIso": added_at_iso,
        "track": nuclear_track,
    }


def build_nuclear_playlist(
    name: str,
    tracks: List[Dict[str, Any]],
    description: str = "",
    playlist_artwork_url: str = "",
    origin: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construye un objeto playlist completo en formato Nuclear Player v1.

    Args:
        name: Nombre de la playlist.
        tracks: Lista de tracks normalizados (provenientes de parse_exportify_csv o de
                extraer de un JSON viejo).
        description: Descripción opcional de la playlist.
        playlist_artwork_url: URL de artwork a nivel playlist (opcional).
        origin: Objeto origin opcional {provider, id, url} si la playlist viene de un source.

    Returns:
        Playlist en formato Nuclear Player v1 lista para serializar.
    """
    now_iso = _now_iso()
    items = []
    for idx, track in enumerate(tracks):
        # Asegurar position
        track_copy = dict(track)
        track_copy["position"] = idx
        items.append(to_nuclear_item(track_copy, idx, now_iso))

    playlist: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": description or "",
        "artwork": {"items": _build_artwork_items(playlist_artwork_url)} if playlist_artwork_url else {"items": []},
        "createdAtIso": now_iso,
        "lastModifiedIso": now_iso,
        "isReadOnly": False,
        "items": items,
    }
    if origin:
        playlist["origin"] = origin

    return {
        "version": 1,
        "playlist": playlist,
    }


# ---------------------------------------------------------------------------
# Lectura: soporte para formato viejo Y nuevo (compatibilidad)
# ---------------------------------------------------------------------------

def is_nuclear_v1(data: Dict[str, Any]) -> bool:
    """Detecta si un JSON está en formato Nuclear v1 (con 'version' y 'playlist')."""
    return (
        isinstance(data, dict)
        and "version" in data
        and "playlist" in data
        and isinstance(data["playlist"], dict)
    )


def is_legacy_format(data: Dict[str, Any]) -> bool:
    """Detecta si un JSON está en formato viejo (tracks[] con uuid/name/artist...)."""
    return (
        isinstance(data, dict)
        and "tracks" in data
        and isinstance(data["tracks"], list)
        and "version" not in data
    )


def extract_playlist_name(data: Dict[str, Any]) -> str:
    """Devuelve el nombre de la playlist desde cualquiera de los dos formatos."""
    if is_nuclear_v1(data):
        return data["playlist"].get("name", "")
    return data.get("name", "")


def extract_playlist_description(data: Dict[str, Any]) -> str:
    """Devuelve la descripción de la playlist (vacía si no existe)."""
    if is_nuclear_v1(data):
        return data["playlist"].get("description", "") or ""
    return ""


def extract_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Devuelve la lista de 'items' (formato Nuclear v1) desde cualquiera de los dos formatos.

    Si el JSON está en formato viejo, convierte los tracks legacy a items v1 al vuelo.
    """
    if is_nuclear_v1(data):
        return data["playlist"].get("items", []) or []
    if is_legacy_format(data):
        # Convertir tracks viejos a items v1
        now_iso = _now_iso()
        items = []
        for idx, track in enumerate(data.get("tracks", [])):
            # Extraer artistas del formato viejo
            artist_field = track.get("artist")
            if isinstance(artist_field, dict):
                artist_name = artist_field.get("name", "")
            else:
                artist_name = artist_field or ""

            # Stream viejo: {source: "spotify", id: "7xA5i..."}
            stream = track.get("stream", {}) or {}
            spotify_id = stream.get("id", "") if isinstance(stream, dict) else ""
            if spotify_id and not spotify_id.startswith("spotify:"):
                # Es bare ID, mantener así (lo convertirá to_nuclear_item)
                pass

            normalized = {
                "name": track.get("name", ""),
                "artist": artist_name,
                "artists": _split_artists(artist_name, ""),
                "album": track.get("album", ""),
                "album_id": None,
                "duration_ms": int(track.get("duration", 0) or 0) * 1000,
                "duration": int(track.get("duration", 0) or 0),
                "thumbnail": track.get("thumbnail", "") or "",
                "spotify_id": spotify_id,
                "track_number": idx + 1,
                "disc_number": "1",
                "added_at_iso": track.get("addedAtIso") or now_iso,
                "extra": {},
                "position": idx,
            }
            items.append(to_nuclear_item(normalized, idx, now_iso))
        return items
    return []


def extract_track_count(data: Dict[str, Any]) -> int:
    """Devuelve el número de tracks en la playlist desde cualquiera de los dos formatos."""
    return len(extract_items(data))


def normalize_to_v1(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza un JSON (viejo o nuevo) al formato Nuclear v1.
    Si ya es v1, devuelve tal cual. Si es viejo, convierte.
    """
    if is_nuclear_v1(data):
        return data
    if is_legacy_format(data):
        name = data.get("name", "")
        items = extract_items(data)
        now_iso = _now_iso()
        return {
            "version": 1,
            "playlist": {
                "id": data.get("id") or str(uuid.uuid4()),
                "name": name,
                "description": "",
                "artwork": {"items": []},
                "createdAtIso": data.get("createdAt") or now_iso,
                "lastModifiedIso": now_iso,
                "isReadOnly": False,
                "items": items,
            },
        }
    # Si no es reconocido, devolver un esqueleto vacío
    return build_nuclear_playlist("Unknown", [])


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
    """Carga una playlist desde un archivo JSON (acepta formato viejo o nuevo)."""
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
                "name": extract_playlist_name(data),
                "tracks_count": extract_track_count(data),
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
    description: str = "",
) -> Dict[str, Any]:
    """
    Combina varias playlists en una nueva.

    Args:
        playlists: Lista de objetos playlist (formato viejo o Nuclear v1).
        new_name: Nombre de la playlist resultante.
        dedupe: Si True, elimina duplicados (mismo title + primer artist).
        description: Descripción opcional.

    Returns:
        Nueva playlist en formato Nuclear v1.
    """
    seen = set()
    merged_tracks: List[Dict[str, Any]] = []
    sources = []

    for playlist in playlists:
        items = extract_items(playlist)
        sources.append(extract_playlist_name(playlist))

        for item in items:
            track = item.get("track", {}) or {}
            title = (track.get("title") or "").strip().lower()
            artists = track.get("artists") or []
            first_artist = (artists[0].get("name") or "").strip().lower() if artists else ""

            key = (title, first_artist) if dedupe else None
            if dedupe and key in seen:
                continue
            if dedupe:
                seen.add(key)

            # Reutilizar el track tal cual pero con nuevo item.id
            new_item = {
                "id": _generate_item_id(),
                "addedAtIso": item.get("addedAtIso") or _now_iso(),
                "track": track,
            }
            merged_tracks.append(new_item)

    now_iso = _now_iso()
    return {
        "version": 1,
        "playlist": {
            "id": str(uuid.uuid4()),
            "name": new_name,
            "description": description or "",
            "artwork": {"items": []},
            "createdAtIso": now_iso,
            "lastModifiedIso": now_iso,
            "isReadOnly": False,
            "items": merged_tracks,
            "merged_from": sources,
        },
    }


# ---------------------------------------------------------------------------
# Operaciones de edición (borrar/agregar track, renombrar)
# ---------------------------------------------------------------------------

def delete_track_by_index(playlist_data: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Elimina un track por su índice en la playlist. Devuelve la playlist modificada (formato v1)."""
    v1 = normalize_to_v1(playlist_data)
    items = v1["playlist"].get("items", [])
    if 0 <= index < len(items):
        items.pop(index)
        # Reasignar trackNumber (posición) en los restantes
        for i, item in enumerate(items):
            if "track" in item:
                item["track"]["trackNumber"] = i + 1
    v1["playlist"]["items"] = items
    v1["playlist"]["lastModifiedIso"] = _now_iso()
    return v1


def add_track_to_playlist(
    playlist_data: Dict[str, Any],
    title: str,
    artist: str,
    album: str = "",
    duration_ms: int = 0,
    spotify_id: str = "",
    thumbnail: str = "",
) -> Dict[str, Any]:
    """Agrega un track al final de la playlist. Devuelve la playlist modificada (formato v1)."""
    v1 = normalize_to_v1(playlist_data)
    items = v1["playlist"].setdefault("items", [])

    normalized = {
        "name": title,
        "artist": artist,
        "artists": _split_artists(artist, ""),
        "album": album,
        "album_id": None,
        "duration_ms": duration_ms,
        "duration": duration_ms // 1000 if duration_ms else 0,
        "thumbnail": thumbnail,
        "spotify_id": spotify_id,
        "track_number": len(items) + 1,
        "disc_number": "1",
        "added_at_iso": _now_iso(),
        "extra": {},
        "position": len(items),
    }
    items.append(to_nuclear_item(normalized, len(items)))
    v1["playlist"]["items"] = items
    v1["playlist"]["lastModifiedIso"] = _now_iso()
    return v1


def rename_playlist(playlist_data: Dict[str, Any], new_name: str) -> Dict[str, Any]:
    """Renombra la playlist. Devuelve la playlist modificada (formato v1)."""
    v1 = normalize_to_v1(playlist_data)
    v1["playlist"]["name"] = new_name
    v1["playlist"]["lastModifiedIso"] = _now_iso()
    return v1


def update_playlist_description(playlist_data: Dict[str, Any], new_description: str) -> Dict[str, Any]:
    """Actualiza la descripción de la playlist. Devuelve la playlist modificada (formato v1)."""
    v1 = normalize_to_v1(playlist_data)
    v1["playlist"]["description"] = new_description or ""
    v1["playlist"]["lastModifiedIso"] = _now_iso()
    return v1


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
        description="Convierte playlists CSV (Exportify) a JSON (Nuclear Player v1)."
    )
    parser.add_argument("csv", help="Ruta al archivo CSV de Exportify")
    parser.add_argument("-o", "--output", help="Ruta de salida JSON")
    parser.add_argument("-n", "--name", help="Nombre de la playlist (por defecto: nombre del CSV)")

    args = parser.parse_args()
    output = args.output or f"playlists/{Path(args.csv).stem}.json"
    result = cli_convert(args.csv, output, args.name)
    print(f"Playlist convertida: {result}")
