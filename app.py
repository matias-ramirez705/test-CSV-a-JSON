"""
Aplicación Flask para gestionar playlists:
- Convertir CSV (Exportify) a JSON (Nuclear Player v1)
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
import socket
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
    add_track_to_playlist,
    build_nuclear_playlist,
    create_backup,
    delete_track_by_index,
    extract_items,
    extract_playlist_description,
    extract_playlist_name,
    extract_track_count,
    is_nuclear_v1,
    list_backups,
    list_playlists_in_dir,
    load_playlist_json,
    merge_playlists,
    normalize_to_v1,
    parse_exportify_csv,
    rename_playlist,
    restore_backup,
    sanitize_filename,
    save_playlist_json,
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


def _format_duration_ms(ms: int) -> str:
    """Formatea milisegundos como mm:ss o h:mm:ss."""
    try:
        ms = int(ms)
    except (ValueError, TypeError):
        ms = 0
    seconds = ms // 1000
    if seconds >= 3600:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}"
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _format_duration(seconds: int) -> str:
    """Compat: formatea segundos como mm:ss."""
    return _format_duration_ms(int(seconds) * 1000)


def _find_free_port(start: int = 5000, end: int = 5010) -> int:
    """Busca el primer puerto libre entre start y end (inclusive)."""
    for port in range(start, end + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
                return port
        except OSError:
            continue
    # Si todos están ocupados, dejar que Flask intente con el primero
    return start


def _sum_duration_ms(playlist_data: Dict[str, Any]) -> int:
    """Suma la duración total de la playlist en ms (soporta ambos formatos)."""
    items = extract_items(playlist_data)
    total = 0
    for item in items:
        track = item.get("track", {}) or {}
        total += int(track.get("durationMs", 0) or 0)
    return total


def _playlist_summary(data: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """Construye un dict con metadatos para la vista de lista."""
    total_ms = _sum_duration_ms(data)
    return {
        "filename": filename,
        "name": extract_playlist_name(data),
        "description": extract_playlist_description(data),
        "tracks_count": extract_track_count(data),
        "total_duration_ms": total_ms,
        "total_duration_str": _format_duration_ms(total_ms),
        "is_v1": is_nuclear_v1(data),
    }


# ---------------------------------------------------------------------------
# Rutas de páginas (HTML)
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/edit/<path:filename>")
def edit_page(filename: str):
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
    """Lista todas las playlists disponibles con metadatos."""
    raw = list_playlists_in_dir(str(PLAYLISTS_DIR))
    # Enriquecer con duración total y flag de formato
    enriched = []
    for entry in raw:
        try:
            data = load_playlist_json(entry["path"])
            summary = _playlist_summary(data, entry["filename"])
            summary["size_bytes"] = entry["size_bytes"]
            summary["modified"] = entry["modified"]
            enriched.append(summary)
        except Exception:
            enriched.append(entry)
    return jsonify({"playlists": enriched})


@app.route("/api/playlists/<path:filename>", methods=["GET"])
def api_get_playlist(filename: str):
    """Devuelve una playlist en formato Nuclear v1 (normaliza si estaba en formato viejo)."""
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404
        data = load_playlist_json(str(p))
        # Normalizar SIEMPRE a v1 antes de devolver (la UI espera v1)
        v1 = normalize_to_v1(data)
        # Añadir metadatos internos para la UI (con _)
        total_ms = _sum_duration_ms(v1)
        v1["_filename"] = p.name
        v1["_tracks_count"] = extract_track_count(v1)
        v1["_total_duration_ms"] = total_ms
        v1["_total_duration_str"] = _format_duration_ms(total_ms)
        v1["_is_v1"] = is_nuclear_v1(data)  # si el archivo original ya era v1
        return jsonify(v1)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _convert_csv_file(
    csv_path: Path,
    *,
    auto_backup: bool = True,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Convierte un CSV individual a JSON formato Nuclear v1.

    Devuelve un dict con el resultado del proceso.
    """
    filename = csv_path.name
    if not filename.lower().endswith(".csv"):
        return {"file": filename, "status": "skipped", "reason": "No es CSV"}

    try:
        tracks = parse_exportify_csv(str(csv_path))
        if not tracks:
            return {"file": filename, "status": "error", "reason": "CSV vacío o sin tracks válidos"}

        playlist_name = Path(filename).stem
        playlist = build_nuclear_playlist(playlist_name, tracks)
        out_name = sanitize_filename(playlist_name) + ".json"
        out_path = PLAYLISTS_DIR / out_name

        backup_path = ""
        if out_path.exists():
            if auto_backup:
                backup_path = create_backup(str(out_path), str(BACKUPS_DIR), prefix="auto_")
            if not overwrite:
                counter = 1
                while out_path.exists():
                    out_path = PLAYLISTS_DIR / f"{sanitize_filename(playlist_name)}_{counter}.json"
                    counter += 1

        save_playlist_json(playlist, str(out_path))
        return {
            "file": filename,
            "status": "ok",
            "playlist_file": out_path.name,
            "tracks": len(tracks),
            "backup": backup_path,
        }
    except Exception as e:
        return {"file": filename, "status": "error", "reason": str(e)}


@app.route("/api/upload-csv", methods=["POST"])
def api_upload_csv():
    """Sube uno o más CSVs y los convierte a JSON formato Nuclear v1."""
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

        csv_path = UPLOAD_DIR / filename
        f.save(str(csv_path))

        results.append(_convert_csv_file(
            csv_path,
            auto_backup=auto_backup,
            overwrite=overwrite,
        ))

    return jsonify({"results": results})


@app.route("/api/convert-all-uploads", methods=["POST"])
def api_convert_all_uploads():
    """
    Convierte TODOS los CSV que estén en la carpeta uploads/ en una sola pasada.
    Útil cuando el usuario ya copió muchos CSV a esa carpeta desde el explorador.

    Body opcional (JSON):
        {
            "backup": true,         # default true
            "overwrite": false,     # default false (usa _1, _2, ...)
            "delete_csv": false     # default false (borra el CSV después de convertirlo)
        }
    """
    try:
        data = request.get_json(silent=True) or {}
        auto_backup = bool(data.get("backup", True))
        overwrite = bool(data.get("overwrite", False))
        delete_csv = bool(data.get("delete_csv", False))

        csv_files = sorted(UPLOAD_DIR.glob("*.csv"))
        if not csv_files:
            return jsonify({
                "error": f"No hay archivos .csv en la carpeta uploads/ ({UPLOAD_DIR})",
                "uploads_dir": str(UPLOAD_DIR),
            }), 404

        results = []
        for csv_path in csv_files:
            result = _convert_csv_file(
                csv_path,
                auto_backup=auto_backup,
                overwrite=overwrite,
            )
            # Borrar CSV si se pidió y la conversión fue exitosa
            if delete_csv and result["status"] == "ok" and csv_path.exists():
                try:
                    csv_path.unlink()
                    result["csv_deleted"] = True
                except Exception:
                    result["csv_deleted"] = False
            results.append(result)

        ok_count = sum(1 for r in results if r["status"] == "ok")
        err_count = sum(1 for r in results if r["status"] == "error")
        skip_count = sum(1 for r in results if r["status"] == "skipped")
        total_tracks = sum(r.get("tracks", 0) for r in results if r["status"] == "ok")

        return jsonify({
            "status": "ok",
            "total_csv": len(csv_files),
            "ok": ok_count,
            "errors": err_count,
            "skipped": skip_count,
            "total_tracks": total_tracks,
            "uploads_dir": str(UPLOAD_DIR),
            "playlists_dir": str(PLAYLISTS_DIR),
            "results": results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/uploads", methods=["GET"])
def api_list_uploads():
    """Lista los CSV pendientes en la carpeta uploads/."""
    csv_files = sorted(UPLOAD_DIR.glob("*.csv"))
    return jsonify({
        "uploads_dir": str(UPLOAD_DIR),
        "count": len(csv_files),
        "files": [
            {
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
            for f in csv_files
        ],
    })


@app.route("/api/uploads/clear", methods=["DELETE"])
def api_clear_uploads():
    """Borra todos los CSV de la carpeta uploads/."""
    try:
        csv_files = list(UPLOAD_DIR.glob("*.csv"))
        for f in csv_files:
            f.unlink()
        return jsonify({"status": "ok", "deleted": len(csv_files)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Editar playlist (formato Nuclear v1)
# ---------------------------------------------------------------------------

@app.route("/api/playlists/<path:filename>", methods=["PUT"])
def api_update_playlist(filename: str):
    """
    Actualiza una playlist completa (renombrada, tracks editados, etc.).

    Acepta el payload en formato Nuclear v1. Si la playlist original estaba en
    formato viejo, se normaliza a v1 antes de fusionar los cambios.

    Body (JSON):
        {
            "version": 1,
            "playlist": {
                "name": "...",
                "description": "...",
                "items": [...]
            },
            "save_as_new": false,        // opcional
            "new_filename": "...",        // opcional, sólo si save_as_new=true
            "backup": true                // opcional, default true
        }
    """
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404

        data = request.get_json(force=True, silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Payload inválido"}), 400

        # Normalizar a v1
        v1 = normalize_to_v1(data)
        # Asegurar campos obligatorios
        if not v1["playlist"].get("name"):
            v1["playlist"]["name"] = "Playlist sin nombre"

        save_as_new = bool(data.get("save_as_new", False))
        new_filename = (data.get("new_filename") or "").strip()
        do_backup = data.get("backup", True)

        if save_as_new and new_filename:
            target_name = sanitize_filename(new_filename) + ".json"
            target_path = PLAYLISTS_DIR / target_name
        else:
            target_path = p

        backup_path = ""
        if do_backup and target_path.exists():
            backup_path = create_backup(str(target_path), str(BACKUPS_DIR), prefix="manual_")

        save_playlist_json(v1, str(target_path))

        tracks_count = len(v1["playlist"].get("items", []))
        return jsonify({
            "status": "ok",
            "filename": target_path.name,
            "tracks": tracks_count,
            "backup": backup_path,
            "saved_as_new": save_as_new,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists/<path:filename>", methods=["DELETE"])
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


@app.route("/api/playlists/<path:filename>/add-track", methods=["POST"])
def api_add_track(filename: str):
    """Añade un track a una playlist existente (formato Nuclear v1)."""
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404

        playlist = load_playlist_json(str(p))
        data = request.get_json(force=True, silent=True) or {}

        title = (data.get("name") or data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "Nombre del track requerido"}), 400

        artist = (data.get("artist") or "").strip()
        album = (data.get("album") or "").strip()
        duration_ms = int(data.get("duration_ms", data.get("duration", 0) or 0))
        spotify_id = (data.get("spotify_id") or "").strip()
        thumbnail = (data.get("thumbnail") or "").strip()

        # Backup previo
        backup_path = create_backup(str(p), str(BACKUPS_DIR), prefix="auto_")

        updated = add_track_to_playlist(
            playlist,
            title=title,
            artist=artist,
            album=album,
            duration_ms=duration_ms,
            spotify_id=spotify_id,
            thumbnail=thumbnail,
        )
        save_playlist_json(updated, str(p))

        new_item = updated["playlist"]["items"][-1]
        return jsonify({
            "status": "ok",
            "item": new_item,
            "backup": backup_path,
            "tracks_count": len(updated["playlist"]["items"]),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/playlists/<path:filename>/remove-track/<int:track_index>", methods=["DELETE"])
def api_remove_track(filename: str, track_index: int):
    """Elimina un track por su índice (posición en items[]) y reordena trackNumber."""
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404

        playlist = load_playlist_json(str(p))
        backup_path = create_backup(str(p), str(BACKUPS_DIR), prefix="auto_")
        updated = delete_track_by_index(playlist, track_index)
        save_playlist_json(updated, str(p))

        return jsonify({
            "status": "ok",
            "backup": backup_path,
            "tracks_count": len(updated["playlist"]["items"]),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Reordenar tracks (drag & drop)
# ---------------------------------------------------------------------------

@app.route("/api/playlists/<path:filename>/reorder", methods=["POST"])
def api_reorder_tracks(filename: str):
    """
    Reordena tracks según una lista de item IDs.

    Body:
        { "order": ["item_id_1", "item_id_2", ...] }
    """
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404

        playlist = load_playlist_json(str(p))
        v1 = normalize_to_v1(playlist)
        data = request.get_json(force=True, silent=True) or {}
        new_order = data.get("order", [])
        if not isinstance(new_order, list):
            return jsonify({"error": "Order debe ser una lista de item IDs"}), 400

        items = v1["playlist"].get("items", [])
        by_id = {item.get("id"): item for item in items}
        new_items = []
        for idx, item_id in enumerate(new_order):
            if item_id in by_id:
                item = by_id[item_id]
                # Actualizar trackNumber
                if "track" in item:
                    item["track"]["trackNumber"] = idx + 1
                new_items.append(item)

        if len(new_items) != len(items):
            return jsonify({"error": "Orden no coincide con items existentes"}), 400

        v1["playlist"]["items"] = new_items
        v1["playlist"]["lastModifiedIso"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.") + "000Z"

        backup_path = create_backup(str(p), str(BACKUPS_DIR), prefix="auto_")
        save_playlist_json(v1, str(p))

        return jsonify({"status": "ok", "backup": backup_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Merge
# ---------------------------------------------------------------------------

@app.route("/api/merge", methods=["POST"])
def api_merge_playlists():
    """Combina varias playlists en una nueva (formato Nuclear v1)."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        filenames = data.get("playlists", [])
        new_name = (data.get("name") or "").strip()
        dedupe = data.get("dedupe", True)
        description = (data.get("description") or "").strip()

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

        merged = merge_playlists(playlists, new_name, dedupe=dedupe, description=description)

        out_name = sanitize_filename(new_name) + ".json"
        out_path = PLAYLISTS_DIR / out_name

        if out_path.exists():
            create_backup(str(out_path), str(BACKUPS_DIR), prefix="merge_overwrite_")
            counter = 1
            while out_path.exists():
                out_path = PLAYLISTS_DIR / f"{sanitize_filename(new_name)}_{counter}.json"
                counter += 1

        save_playlist_json(merged, str(out_path))

        tracks_count = len(merged["playlist"]["items"])
        return jsonify({
            "status": "ok",
            "filename": out_path.name,
            "tracks": tracks_count,
            "merged_from": merged["playlist"].get("merged_from", []),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Migrar playlists viejas a formato v1
# ---------------------------------------------------------------------------

@app.route("/api/migrate-all-to-v1", methods=["POST"])
def api_migrate_all_to_v1():
    """
    Migra TODAS las playlists que estén en formato viejo a formato Nuclear v1.
    Las que ya están en v1 se dejan intactas.
    """
    try:
        json_files = sorted(PLAYLISTS_DIR.glob("*.json"))
        results = []
        migrated = 0
        skipped = 0
        errors = 0

        for jp in json_files:
            try:
                data = load_playlist_json(str(jp))
                if is_nuclear_v1(data):
                    skipped += 1
                    results.append({"file": jp.name, "status": "already_v1"})
                    continue
                # Backup del original
                backup_path = create_backup(str(jp), str(BACKUPS_DIR), prefix="pre_migrate_")
                v1 = normalize_to_v1(data)
                save_playlist_json(v1, str(jp))
                migrated += 1
                results.append({
                    "file": jp.name,
                    "status": "migrated",
                    "backup": backup_path,
                    "tracks": len(v1["playlist"]["items"]),
                })
            except Exception as e:
                errors += 1
                results.append({"file": jp.name, "status": "error", "reason": str(e)})

        return jsonify({
            "status": "ok",
            "total": len(json_files),
            "migrated": migrated,
            "skipped": skipped,
            "errors": errors,
            "results": results,
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

        data = request.get_json(force=True, silent=True) or {}
        target_filename = data.get("target")
        if not target_filename:
            return jsonify({"error": "Especificar playlist destino"}), 400

        target_path = _playlist_path(target_filename)

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

@app.route("/api/download/<path:filename>", methods=["GET"])
def api_download_playlist(filename: str):
    """Descarga una playlist. Opcionalmente fuerza la normalización a v1."""
    try:
        p = _playlist_path(filename)
        if not p.exists():
            return jsonify({"error": "Playlist no encontrada"}), 404

        force_v1 = request.args.get("v1", "1") in ("1", "true", "yes")
        if force_v1:
            data = load_playlist_json(str(p))
            if not is_nuclear_v1(data):
                data = normalize_to_v1(data)
                # Guardar en un archivo temporal
                tmp_path = p.parent / f".{p.stem}_v1_tmp.json"
                save_playlist_json(data, str(tmp_path))
                resp = send_file(str(tmp_path), as_attachment=True, download_name=p.name)
                # Borrar tmp después de enviar (en teardown)
                @resp.call_on_close
                def _cleanup():
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                return resp
        return send_file(str(p), as_attachment=True, download_name=p.name)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Health check (para diagnóstico)
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({
        "status": "ok",
        "playlists_dir": str(PLAYLISTS_DIR),
        "backups_dir": str(BACKUPS_DIR),
        "uploads_dir": str(UPLOAD_DIR),
        "playlists_count": len(list(PLAYLISTS_DIR.glob("*.json"))),
        "backups_count": len(list(BACKUPS_DIR.glob("*.json"))),
        "schema_version": "nuclear-v1",
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = _find_free_port(5000, 5010)
    print("=" * 60)
    print("  Playlist Manager - Exportify CSV <-> Nuclear Player JSON (v1)")
    print("=" * 60)
    print(f"  Playlists dir: {PLAYLISTS_DIR}")
    print(f"  Backups dir:   {BACKUPS_DIR}")
    print(f"  Uploads dir:   {UPLOAD_DIR}")
    print(f"  Puerto:        {port}")
    print("=" * 60)
    print(f"  Abre http://127.0.0.1:{port} en tu navegador")
    print("=" * 60)
    # debug=False y use_reloader=False: evita el doble arranque que
    # confundía al usuario (5000 primero, 5001 después) y causaba
    # ERR_CONNECTION_REFUSED al abrir el navegador automáticamente.
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
