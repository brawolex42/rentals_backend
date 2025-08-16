import os
import shutil
import random
from glob import glob
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.crypto import get_random_string

from src.properties.models import Property, PropertyImage

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def collect_seed_files():
    base = str(settings.BASE_DIR)
    candidates = [
        os.path.join(base, "seed_images"),
        os.path.join(base, "shared", "seed_images"),
        os.path.join(base, "static", "seed_images"),
        os.path.join(base, "shared", "static", "seed_images"),
    ]
    files = []
    exts = ("*.jpg", "*.jpeg", "*.png", "*.webp")
    for root in candidates:
        if os.path.isdir(root):
            for ext in exts:
                files.extend(glob(os.path.join(root, "**", ext), recursive=True))
    files = [f for f in files if os.path.isfile(f)]
    return files

class Command(BaseCommand):
    help = "Привязывает реальные demo-фото из seed_images к объектам Property."

    def add_arguments(self, parser):
        parser.add_argument("--per-property", type=int, default=4)
        parser.add_argument("--clear-existing", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **opts):
        per_prop = int(opts["per_property"])
        clear = bool(opts["clear_existing"])
        limit = opts.get("limit")

        seed_files = collect_seed_files()
        if not seed_files:
            self.stderr.write("❌ Не нашёл ни одного файла. Положи .jpg/.png в одну из папок: "
                              "seed_images/, shared/seed_images/, static/seed_images/, shared/static/seed_images/")
            return

        props_qs = Property.objects.all().order_by("id")
        if limit:
            props_qs = props_qs[:limit]

        if clear:
            PropertyImage.objects.all().delete()

        random.shuffle(seed_files)
        num_files = len(seed_files)
        idx = 0

        today = datetime.now()
        media_subdir = f"properties/{today:%Y/%m/%d}"
        media_abs_dir = os.path.join(settings.MEDIA_ROOT, media_subdir.replace("/", os.sep))
        ensure_dir(media_abs_dir)

        total = 0
        for p in props_qs:
            if not clear and PropertyImage.objects.filter(property=p).exists():
                continue
            for _ in range(per_prop):
                src = seed_files[idx % num_files]
                idx += 1
                ext = os.path.splitext(src)[1].lower() or ".jpg"
                filename = f"seed_{p.id}_{get_random_string(6)}{ext}"
                dst_rel = f"{media_subdir}/{filename}"
                dst_abs = os.path.join(settings.MEDIA_ROOT, dst_rel.replace("/", os.sep))
                shutil.copyfile(src, dst_abs)
                PropertyImage.objects.create(property=p, image=dst_rel, alt=p.title or os.path.basename(src))
                total += 1
                self.stdout.write(f"[OK] {dst_rel} ← {os.path.basename(src)} -> Property {p.id}")

        self.stdout.write(self.style.SUCCESS(f"Готово. Привязано файлов: {total}."))

