#!/usr/bin/env python3
"""
Migra todos los JSON en formato viejo (tracks[]) al formato Nuclear v1 nativo
(version + playlist + items[]).

Uso:
    python migrate_old_jsons.py [directorio] [--no-backup] [--dry-run]

Si no se especifica directorio, se usa playlists/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Añadir el directorio del proyecto al path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playlist_converter import (
    create_backup,
    is_nuclear_v1,
    load_playlist_json,
    normalize_to_v1,
    save_playlist_json,
)


def migrate_directory(directory: Path, backup: bool = True, dry_run: bool = False) -> None:
    json_files = sorted(directory.glob("*.json"))
    if not json_files:
        print(f"No hay archivos .json en {directory}")
        return

    print("=" * 60)
    print(f"  Migrando {len(json_files)} archivo(s) en {directory}")
    print(f"  Backup: {'sí' if backup else 'no'}  |  Dry-run: {'sí' if dry_run else 'no'}")
    print("=" * 60)

    migrated = 0
    skipped = 0
    errors = 0

    for jp in json_files:
        try:
            data = load_playlist_json(str(jp))
            if is_nuclear_v1(data):
                skipped += 1
                print(f"  [SKIP] {jp.name}  (ya es v1)")
                continue

            if dry_run:
                v1 = normalize_to_v1(data)
                print(f"  [DRY ] {jp.name}  →  v1 con {len(v1['playlist']['items'])} items")
                migrated += 1
                continue

            if backup:
                backup_path = create_backup(str(jp), str(jp.parent / "backups"), prefix="pre_migrate_")
                print(f"  [BACK] backup: {Path(backup_path).name}")

            v1 = normalize_to_v1(data)
            save_playlist_json(v1, str(jp))
            print(f"  [OK  ] {jp.name}  →  {len(v1['playlist']['items'])} items migrados")
            migrated += 1
        except Exception as e:
            print(f"  [ERR ] {jp.name}: {e}")
            errors += 1

    print("=" * 60)
    print(f"  Resumen: {migrated} migradas, {skipped} ya v1, {errors} errores")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Migra JSONs viejos (tracks[]) a formato Nuclear v1 (items[])."
    )
    parser.add_argument("directory", nargs="?", default="playlists",
                        help="Directorio con los JSON a migrar (default: playlists/)")
    parser.add_argument("--no-backup", action="store_true",
                        help="No crear backup de los originales (peligroso)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo mostrar qué se migraría, sin tocar archivos")
    args = parser.parse_args()

    directory = Path(args.directory).resolve()
    if not directory.exists():
        print(f"Error: el directorio {directory} no existe")
        sys.exit(1)

    migrate_directory(directory, backup=not args.no_backup, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
