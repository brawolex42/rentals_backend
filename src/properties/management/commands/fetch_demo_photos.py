import os
import io
import random
import string
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.crypto import get_random_string

from src.properties.models import Property, PropertyImage

SIZE_W, SIZE_H = 1280, 853

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def rand_seed(n=8):
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for _ in range(n))

def fetch_image_bytes(seed: str):
    # Picsum без ключа: стабильно по seed
    url = f"https://picsum.photos/seed/{seed}/{SIZE_W}/{SIZE_H}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.content

class Command(BaseCommand):
    help = "Скачивает красивые демо-фото (Picsum) и привязывает к Property, заменяя заглушки."

    def add_arguments(self, parser):
        parser.add_argument("--per-property", type=int, default=4)
        parser.add_argument("--clear-existing", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **opts):
        per_prop = int(opts["per_property"])
        clear = bool(opts["clear_existing"])
        limit = opts.get("limit")

        props_qs = Property.objects.all().order_by("id")
        if limit:
            props_qs = props_qs[:limit]

        if clear:
            PropertyImage.objects.all().delete()

        today = datetime.now()
        media_subdir = f"properties/{today:%Y/%m/%d}"
        dst_dir = os.path.join(settings.MEDIA_ROOT, media_subdir.replace("/", os.sep))
        ensure_dir(dst_dir)

        total = 0
        for p in props_qs:
            if not clear and PropertyImage.objects.filter(property=p).exists():
                continue

            for _ in range(per_prop):
                seed = f"{p.id}-{rand_seed(6)}"
                try:
                    content = fetch_image_bytes(seed)
                except Exception as e:
                    self.stderr.write(f"[ERR] {seed}: {e}")
                    continue

                filename = f"ext_{p.id}_{get_random_string(6)}.jpg"
                rel_path = f"{media_subdir}/{filename}"
                abs_path = os.path.join(settings.MEDIA_ROOT, rel_path.replace("/", os.sep))
                with open(abs_path, "wb") as f:
                    f.write(content)

                PropertyImage.objects.create(
                    property=p,
                    image=rel_path,
                    alt=p.title or seed
                )
                total += 1
                self.stdout.write(f"[OK] {rel_path} -> Property {p.id}")

        self.stdout.write(self.style.SUCCESS(f"Готово. Привязано файлов: {total}"))
