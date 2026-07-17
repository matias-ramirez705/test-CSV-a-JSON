"""
Aplicación Flask para gestionar playlists:
- Convertir CSV (Exportify) a JSON (Nuclear Player)
- Editar playlists (renombrar, agregar/eliminar canciones)
- Combinar varias playlists en una nueva
- Guardar con respaldo automático en /backups
- Restaurar versiones anteriores

Uso:
    python app.py
    # luego abrir http://127.0.0.1:5000
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from playlist_converter import (
    build_nuclear_playlist,
    create_backup,
    list_backups,
    list_playlists_in_dir,
    load_playlist_json,
    merge_playlists,
    parse_exportify_csv,
    restore_backup,
    sanitize_filename,
    save_playlist_json,
    to_nuclear_track,
)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
PLAYLISTS_DIR = BASE_DIR / "playlists"
BACKUPS_DIR = BASE_DIR / "backups"

for d in (UPLOAD_DIR, PLAYLISTS_DIR, BACKUPS_DIR):
    d.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _playlist_path(filename: str) -> Path:
    """Devuelve la ruta absoluta de una playlist, validando que esté en PLAYLISTS_DIR."""
    safe = secure_filename(filename)
    if not safe.endswith(".json"):
        safe += ".json"
    p = (PLAYLISTS_DIR / safe).resolve()
    if not str(p).startswith(str(PLAYLISTS_DIR.resolve())):
        raise ValueError("Ruta inválida")
    return p


def _format_duration(seconds: int) -> str:
    """Formatea segundos como mm:ss o h:mm:ss."""
    try:
        seconds = int(seconds)
    except (ValueError, TypeError):
        seconds = 0
    if seconds >= 3600:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}"
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Rutas de páginas (HTML)
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/edit/<filename>")
def edit_page(filename: str):
    # Validar que existe
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return render_template("error.html", message=f"Playlist no encontrada: {filename}"), 404
    except ValueError as e:
        return render_template("error.html", message=str(e)), 400
    return render_template("edit.html", filename=p.name)


@app.route("/merge")
def merge_page():
    return render_template("merge.html")


@app.route("/backups")
def backups_page():
    return render_template("backups.html")


# ---------------------------------------------------------------------------
# API: Listar / obtener / crear
# ---------------------------------------------------------------------------

@app.route("/api/playlists", methods=["GET"])
def api_list_playlists():
    playlists = list_playlists_in_dir(str(PLAYLISTS_DIR))
    return jsonify({"playlists": playlists})


@app.route("/api/playlists/<filename>", methods=["GET"])
def api_get_playlist(filename: str):
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404
        data = load_playlist_json(str(p))
        # Añadir metadatos de archivo
        data["_filename"] = p.name
        data["_tracks_count"] = len(data.get("tracks", []))
        # Calcular duración total
        total = sum(int(t.get("duration", 0) or 0) for t in data.get("tracks", []))
        data["_total_duration"] = total
        data["_total_duration_str"] = _format_duration(total)
        return jsonify(data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload-csv", methods=["POST"])
def api_upload_csv():
    """Sube uno o más CSVs y los convierte a JSON formato Nuclear."""
    if "files" not in request.files:
        return jsonify({"error": "No se enviaron archivos"}), 400

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No se seleccionaron archivos"}), 400

    auto_backup = request.form.get("backup", "true").lower() in ("true", "1", "yes")
    overwrite = request.form.get("overwrite", "false").lower() in ("true", "1", "yes")

    results = []
    for f in files:
        filename = secure_filename(f.filename or "")
        if not filename.lower().endswith(".csv"):
            results.append({"file": filename, "status": "skipped", "reason": "No es CSV"})
            continue

        # Guardar CSV en uploads/
        csv_path = UPLOAD_DIR / filename
        f.save(str(csv_path))

        try:
            tracks = parse_exportify_csv(str(csv_path))
            if not tracks:
                results.append({"file": filename, "status": "error", "reason": "CSV vacío o sin tracks válidos"})
                continue

            playlist_name = Path(filename).stem
            playlist = build_nuclear_playlist(playlist_name, tracks)
            out_name = sanitize_filename(playlist_name) + ".json"
            out_path = PLAYLISTS_DIR / out_name

            # Si existe y se pidió backup, hacerlo
            backup_path = ""
            if out_path.exists():
                if auto_backup:
                    backup_path = create_backup(str(out_path), str(BACKUPS_DIR), prefix="auto_")
                if not overwrite:
                    # Generar nombre alternativo
                    counter = 1
                    while out_path.exists():
                        out_path = PLAYLISTS_DIR / f"{sanitize_filename(playlist_name)}_{counter}.json"
                        counter += 1

            save_playlist_json(playlist, str(out_path))
            results.append({
                "file": filename,
                "status": "ok",
                "playlist_file": out_path.name,
                "tracks": len(tracks),
                "backup": backup_path,
            })
        except Exception as e:
            results.append({"file": filename, "status": "error", "reason": str(e)})

    return jsonify({"results": results})


# ---------------------------------------------------------------------------
# API: Editar playlist
# ---------------------------------------------------------------------------

@app.route("/api/playlists/<filename>", methods=["PUT"])
def api_update_playlist(filename: str):
    """Actualiza una playlist completa (renombrada, tracks editados, etc.)."""
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404

        data = request.get_json(force=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Payload inválido"}), 400

        new_name = data.get("name", "").strip()
        tracks = data.get("tracks", [])
        save_as_new = data.get("save_as_new", False)
        new_filename = data.get("new_filename", "").strip()
        do_backup = data.get("backup", True)

        # Validar tracks
        cleaned_tracks = []
        for idx, t in enumerate(tracks):
            if not isinstance(t, dict):
                continue
            name = (t.get("name") or "").strip()
            if not name:
                continue
            artist = t.get("artist", "")
            if isinstance(artist, dict):
                artist_name = (artist.get("name") or "").strip()
            else:
                artist_name = (str(artist) or "").strip()
            album = (t.get("album") or "").strip()
            duration = int(t.get("duration", 0) or 0)
            thumbnail = t.get("thumbnail", "")
            stream = t.get("stream", {}) or {}

            new_track = {
                "uuid": t.get("uuid") or str(uuid.uuid4()),
                "name": name,
                "artist": {"name": artist_name},
                "album": album,
                "duration": duration,
                "position": idx,
                "thumbnail": thumbnail,
                "stream": stream if stream else {"source": "", "id": ""},
            }
            cleaned_tracks.append(new_track)

        # Construir objeto playlist
        playlist_obj = {
            "id": data.get("id") or str(uuid.uuid4()),
            "name": new_name or "Playlist sin nombre",
            "tracks": cleaned_tracks,
            "createdAt": data.get("createdAt") or datetime.utcnow().isoformat() + "Z",
            "updatedAt": datetime.utcnow().isoformat() + "Z",
        }

        # Determinar ruta de guardado
        if save_as_new and new_filename:
            target_name = sanitize_filename(new_filename) + ".json"
            target_path = PLAYLISTS_DIR / target_name
        else:
            target_path = p

        # Backup del destino si existe
        backup_path = ""
        if do_backup and target_path.exists():
            backup_path = create_backup(str(target_path), str(BACKUPS_DIR), prefix="manual_")

        save_playlist_json(playlist_obj, str(target_path))

        return jsonify({
            "status": "ok",
            "filename": target_path.name,
            "tracks": len(cleaned_tracks),
            "backup": backup_path,
            "saved_as_new": save_as_new,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists/<filename>", methods=["DELETE"])
def api_delete_playlist(filename: str):
    """Elimina una playlist (con backup opcional)."""
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404

        do_backup = request.args.get("backup", "true").lower() in ("true", "1", "yes")
        backup_path = ""
        if do_backup:
            backup_path = create_backup(str(p), str(BACKUPS_DIR), prefix="deleted_")

        p.unlink()
        return jsonify({"status": "ok", "backup": backup_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists/<filename>/add-track", methods=["POST"])
def api_add_track(filename: str):
    """Añade un track a una playlist existente."""
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404

        playlist = load_playlist_json(str(p))
        data = request.get_json(force=True)

        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Nombre del track requerido"}), 400

        artist = (data.get("artist") or "").strip()
        album = (data.get("album") or "").strip()
        duration = int(data.get("duration", 0) or 0)
        thumbnail = data.get("thumbnail", "")

        new_track = {
            "uuid": str(uuid.uuid4()),
            "name": name,
            "artist": {"name": artist},
            "album": album,
            "duration": duration,
            "position": len(playlist.get("tracks", [])),
            "thumbnail": thumbnail,
            "stream": {"source": "", "id": ""},
        }
        playlist.setdefault("tracks", []).append(new_track)

        # Backup antes de guardar
        backup_path = create_backup(str(p), str(BACKUPS_DIR), prefix="auto_")
        save_playlist_json(playlist, str(p))

        return jsonify({
            "status": "ok",
            "track": new_track,
            "backup": backup_path,
            "tracks_count": len(playlist["tracks"]),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists/<filename>/remove-track/<track_uuid>", methods=["DELETE"])
def api_remove_track(filename: str, track_uuid: str):
    """Elimina un track por UUID y reordena posiciones."""
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404

        playlist = load_playlist_json(str(p))
        tracks = playlist.get("tracks", [])
        original_len = len(tracks)
        tracks = [t for t in tracks if t.get("uuid") != track_uuid]

        if len(tracks) == original_len:
            return jsonify({"error": "Track no encontrado"}), 404

        # Reordenar posiciones
        for idx, t in enumerate(tracks):
            t["position"] = idx
        playlist["tracks"] = tracks

        backup_path = create_backup(str(p), str(BACKUPS_DIR), prefix="auto_")
        save_playlist_json(playlist, str(p))

        return jsonify({
            "status": "ok",
            "backup": backup_path,
            "tracks_count": len(tracks),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Reordenar tracks (drag & drop)
# ---------------------------------------------------------------------------

@app.route("/api/playlists/<filename>/reorder", methods=["POST"])
def api_reorder_tracks(filename: str):
    """Reordena tracks según una lista de UUIDs."""
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404

        playlist = load_playlist_json(str(p))
        data = request.get_json(force=True)
        new_order = data.get("order", [])
        if not isinstance(new_order, list):
            return jsonify({"error": "Order debe ser una lista de UUIDs"}), 400

        # Mapear por uuid
        by_uuid = {t.get("uuid"): t for t in playlist.get("tracks", [])}
        new_tracks = []
        for idx, u in enumerate(new_order):
            if u in by_uuid:
                t = by_uuid[u]
                t["position"] = idx
                new_tracks.append(t)

        if len(new_tracks) != len(playlist.get("tracks", [])):
            return jsonify({"error": "Orden no coincide con tracks existentes"}), 400

        playlist["tracks"] = new_tracks
        backup_path = create_backup(str(p), str(BACKUPS_DIR), prefix="auto_")
        save_playlist_json(playlist, str(p))

        return jsonify({"status": "ok", "backup": backup_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Merge
# ---------------------------------------------------------------------------

@app.route("/api/merge", methods=["POST"])
def api_merge_playlists():
    """Combina varias playlists en una nueva."""
    try:
        data = request.get_json(force=True)
        filenames = data.get("playlists", [])
        new_name = (data.get("name") or "").strip()
        dedupe = data.get("dedupe", True)

        if not filenames:
            return jsonify({"error": "No se seleccionaron playlists"}), 400
        if not new_name:
            return jsonify({"error": "Nombre de la nueva playlist requerido"}), 400

        playlists = []
        for fn in filenames:
            p = _playlist_path(fn)
            if not p.exists():
                return jsonify({"error": f"Playlist no encontrada: {fn}"}), 404
            playlists.append(load_playlist_json(str(p)))

        merged = merge_playlists(playlists, new_name, dedupe=dedupe)

        out_name = sanitize_filename(new_name) + ".json"
        out_path = PLAYLISTS_DIR / out_name

        # Si existe, hacer backup y usar nombre alternativo
        if out_path.exists():
            backup_path = create_backup(str(out_path), str(BACKUPS_DIR), prefix="merge_overwrite_")
            counter = 1
            while out_path.exists():
                out_path = PLAYLISTS_DIR / f"{sanitize_filename(new_name)}_{counter}.json"
                counter += 1

        save_playlist_json(merged, str(out_path))

        return jsonify({
            "status": "ok",
            "filename": out_path.name,
            "tracks": len(merged["tracks"]),
            "merged_from": merged.get("merged_from", []),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Backups
# ---------------------------------------------------------------------------

@app.route("/api/backups", methods=["GET"])
def api_list_backups():
    backups = list_backups(str(BACKUPS_DIR))
    return jsonify({"backups": backups})


@app.route("/api/backups/<path:filename>", methods=["GET"])
def api_download_backup(filename: str):
    safe = secure_filename(filename)
    p = BACKUPS_DIR / safe
    if not p.exists():
        return jsonify({"error": "Backup no encontrado"}), 404
    return send_file(str(p), as_attachment=True, download_name=safe)


@app.route("/api/backups/<path:filename>/restore", methods=["POST"])
def api_restore_backup(filename: str):
    """Restaura un backup sobre una playlist destino."""
    try:
        safe = secure_filename(filename)
        bp = BACKUPS_DIR / safe
        if not bp.exists():
            return jsonify({"error": "Backup no encontrado"}), 404

        data = request.get_json(force=True)
        target_filename = data.get("target")
        if not target_filename:
            return jsonify({"error": "Especificar playlist destino"}), 400

        target_path = _playlist_path(target_filename)

        # Backup del estado actual antes de restaurar (para no perder nada)
        backup_current = ""
        if target_path.exists():
            backup_current = create_backup(str(target_path), str(BACKUPS_DIR), prefix="pre_restore_")

        restore_backup(str(bp), str(target_path))

        return jsonify({
            "status": "ok",
            "target": target_path.name,
            "backup_current": backup_current,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/backups/<path:filename>", methods=["DELETE"])
def api_delete_backup(filename: str):
    safe = secure_filename(filename)
    p = BACKUPS_DIR / safe
    if not p.exists():
        return jsonify({"error": "Backup no encontrado"}), 404
    p.unlink()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# API: Descarga
# ---------------------------------------------------------------------------

@app.route("/api/download/<filename>", methods=["GET"])
def api_download_playlist(filename: str):
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404
        return send_file(str(p), as_attachment=True, download_name=p.name)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  Playlist Manager - Exportify CSV <-> Nuclear Player JSON")
    print("=" * 60)
    print(f"  Playlists dir: {PLAYLISTS_DIR}")
    print(f"  Backups dir:   {BACKUPS_DIR}")
    print(f"  Uploads dir:   {UPLOAD_DIR}")
    print("=" * 60)
    print("  Abre http://127.0.0.1:5000 en tu navegador")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
