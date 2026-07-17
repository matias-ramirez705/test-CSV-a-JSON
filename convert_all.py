"""
Conversión MASIVA de CSV (Exportify) a JSON (Nuclear Player).

Convierte TODOS los archivos .csv de una carpeta en una sola pasada.
Útil cuando tienes muchas playlists exportadas y no quieres subirlas
una por una desde la interfaz web.

Uso:
    # Convertir todos los CSV de la carpeta por defecto (uploads/):
    python convert_all.py

    # Convertir todos los CSV de una carpeta específica:
    python convert_all.py "C:\\Users\\yo\\Downloads\\mis_playlists"

    # Sobrescribir si ya existen (en vez de crear _1, _2, ...):
    python convert_all.py --overwrite

    # Borrar los CSV originales después de convertirlos exitosamente:
    python convert_all.py --delete-csv

    # Sin backup automático (¡cuidado!):
    python convert_all.py --no-backup

    # Combinar varias banderas:
    python convert_all.py "C:\\csvs" --overwrite --delete-csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Asegurar que el directorio del script esté en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playlist_converter import (
    build_nuclear_playlist,
    create_backup,
    parse_exportify_csv,
    sanitize_filename,
    save_playlist_json,
)


def convert_folder(
    input_dir: Path,
    output_dir: Path,
    backup_dir: Path,
    *,
    overwrite: bool = False,
    auto_backup: bool = True,
    delete_csv: bool = False,
) -> int:
    """
    Convierte todos los .csv de input_dir en .json dentro de output_dir.

    Devuelve el código de salida (0 = ok total, 1 = hubo algún error).
    """
    if not input_dir.exists():
        print(f"Error: la carpeta de entrada no existe: {input_dir}")
        return 1

    csv_files = sorted(input_dir.glob("*.csv"))
    if not csv_files:
        print(f"No se encontraron archivos .csv en: {input_dir}")
        print("Copia tus CSV de Exportify a esa carpeta y vuelve a ejecutar este script.")
        return 1

    # Crear carpetas de salida si no existen
    output_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"  Conversión masiva: {len(csv_files)} CSV encontrados")
    print(f"  Carpeta origen:  {input_dir}")
    print(f"  Carpeta destino: {output_dir}")
    print(f"  Respaldos:       {backup_dir}")
    print(f"  Sobrescribir:    {'sí' if overwrite else 'no (crea _1, _2, ...)'}")
    print(f"  Backup auto:     {'sí' if auto_backup else 'no'}")
    print(f"  Borrar CSV:      {'sí' if delete_csv else 'no'}")
    print("=" * 70)
    print()

    ok_count = 0
    err_count = 0
    total_tracks = 0

    for i, csv_path in enumerate(csv_files, 1):
        prefix = f"[{i:>3}/{len(csv_files)}]"
        try:
            tracks = parse_exportify_csv(str(csv_path))
            if not tracks:
                print(f"{prefix} ✗ {csv_path.name} — CSV vacío o sin tracks válidos")
                err_count += 1
                continue

            playlist_name = csv_path.stem
            playlist = build_nuclear_playlist(playlist_name, tracks)
            out_name = sanitize_filename(playlist_name) + ".json"
            out_path = output_dir / out_name

            backup_path = ""
            if out_path.exists():
                if auto_backup:
                    backup_path = create_backup(str(out_path), str(backup_dir), prefix="auto_")
                if not overwrite:
                    counter = 1
                    while out_path.exists():
                        out_path = output_dir / f"{sanitize_filename(playlist_name)}_{counter}.json"
                        counter += 1

            save_playlist_json(playlist, str(out_path))

            extra = ""
            if backup_path:
                extra += f" · respaldo creado"
            if out_path.name != out_name:
                extra += f" · renombrado a {out_path.name}"
            print(f"{prefix} ✓ {csv_path.name} → {out_path.name} ({len(tracks)} tracks){extra}")

            ok_count += 1
            total_tracks += len(tracks)

            if delete_csv and csv_path.exists():
                try:
                    csv_path.unlink()
                except Exception as e:
                    print(f"        ⚠ no se pudo borrar el CSV: {e}")

        except Exception as e:
            print(f"{prefix} ✗ {csv_path.name} — Error: {e}")
            err_count += 1

    print()
    print("=" * 70)
    print(f"  Resultado: {ok_count} OK, {err_count} con error, {total_tracks} canciones totales")
    print(f"  JSON guardados en: {output_dir}")
    if err_count == 0:
        print("  ¡Todo OK!")
    else:
        print(f"  Revisa los {err_count} errores arriba.")
    print("=" * 70)

    return 0 if err_count == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="Convierte TODOS los CSV de Exportify en una carpeta a JSON Nuclear Player.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python convert_all.py
  python convert_all.py "C:\\Users\\yo\\Downloads\\csvs"
  python convert_all.py --overwrite --delete-csv
  python convert_all.py "C:\\csvs" --no-backup
""",
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=None,
        help="Carpeta con los CSV (por defecto: uploads/ del proyecto)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Carpeta de salida para los JSON (por defecto: playlists/)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescribir JSON existentes (por defecto crea _1, _2, ...)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="No crear respaldo automático antes de sobrescribir",
    )
    parser.add_argument(
        "--delete-csv",
        action="store_true",
        help="Borrar cada CSV después de convertirlo exitosamente",
    )

    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    input_dir = Path(args.input_dir) if args.input_dir else (base / "uploads")
    output_dir = Path(args.output) if args.output else (base / "playlists")
    backup_dir = base / "backups"

    sys.exit(convert_folder(
        input_dir=input_dir,
        output_dir=output_dir,
        backup_dir=backup_dir,
        overwrite=args.overwrite,
        auto_backup=not args.no_backup,
        delete_csv=args.delete_csv,
    ))


if __name__ == "__main__":
    main()
