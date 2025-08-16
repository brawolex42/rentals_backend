import os
from pathlib import Path
from typing import Set

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.storage import default_storage

from src.properties.models import PropertyImage


def iter_fs_files(root: Path) -> Set[str]:
    files = set()
    if not root.exists():
        return files
    root_str = str(root)
    for dirpath, _, filenames in os.walk(root_str):
        for fn in filenames:
            rel = str((Path(dirpath) / fn).relative_to(settings.MEDIA_ROOT)).replace("\\", "/")
            files.add(rel)
    return files


def delete_empty_dirs(root: Path):
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        p = Path(dirpath)
        if not dirnames and not filenames:
            try:
                p.rmdir()
            except OSError:
                pass


class Command(BaseCommand):
    help = "Purge property media files and/or DB records."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--orphaned", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--yes", action="store_true")

    def handle(self, *args, **opts):
        do_all = bool(opts["all"])
        orphaned = bool(opts["orphaned"])
        dry = bool(opts["dry_run"])
        yes = bool(opts["yes"])

        media_root = Path(settings.MEDIA_ROOT)
        props_dir = media_root / "properties"

        if not (do_all or orphaned):
            self.stdout.write("Укажи режим: --all или --orphaned")
            return

        db_paths = set(p for p in PropertyImage.objects.values_list("image", flat=True) if p)
        fs_paths = iter_fs_files(props_dir)

        to_delete_files = set()
        to_delete_db_ids = set()

        if do_all:
            to_delete_files = fs_paths
            to_delete_db_ids = set(PropertyImage.objects.values_list("id", flat=True))
        elif orphaned:
            to_delete_files = set(p for p in fs_paths if p not in db_paths)

        self.stdout.write(f"В БД изображений: {len(db_paths)}")
        self.stdout.write(f"Файлов на диске: {len(fs_paths)}")
        if do_all:
            self.stdout.write(f"Будет удалено записей PropertyImage: {len(to_delete_db_ids)}")
        self.stdout.write(f"Будет удалено файлов: {len(to_delete_files)}")

        if dry:
            sample = list(to_delete_files)[:10]
            if sample:
                self.stdout.write("Примеры файлов на удаление:")
                for s in sample:
                    self.stdout.write(f" - {s}")
            return

        if not yes:
            self.stdout.write("Добавь --yes для подтверждения удаления.")
            return

        deleted_files = 0
        for rel in to_delete_files:
            try:
                default_storage.delete(rel)
                deleted_files += 1
            except Exception as e:
                self.stderr.write(f"[ERR FILE] {rel}: {e}")

        deleted_db = 0
        if do_all and to_delete_db_ids:
            qs = PropertyImage.objects.filter(id__in=to_delete_db_ids)
            deleted_db = qs.count()
            qs.delete()

        delete_empty_dirs(props_dir)

        self.stdout.write(f"Удалено файлов: {deleted_files}. Удалено записей: {deleted_db}.")
