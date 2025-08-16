import os
import io
import random
import shutil
from datetime import datetime

import requests
from PIL import Image

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.crypto import get_random_string

from src.properties.models import Property, PropertyImage


PEXELS_ENDPOINT = "https://api.pexels.com/v1/search"
TARGET_SIZE = (1280, 853)  # 3:2


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def center_crop_resize(img: Image.Image, size=(1280, 853)) -> Image.Image:
    tw, th = size
    w, h = img.size
    target_ratio = tw / th
    ratio = w / h
    if ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
        img = img.crop(box)
    elif ratio < target_ratio:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)
        img = img.crop(box)
    return img.resize(size, Image.LANCZOS)


def pexels_search(api_key: str, query: str, per_page: int = 30, page: int = 1):
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": per_page, "page": page, "locale": "en-US"}
    r = requests.get(PEXELS_ENDPOINT, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def download_and_prepare(url: str) -> bytes:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    img = center_crop_resize(img, TARGET_SIZE)
    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=88)
    return bio.getvalue()


def choose_queries(p: Property):
    qs = [
        "modern apartment interior",
        "living room interior apartment",
        "bedroom interior apartment",
        "kitchen interior apartment",
        "bathroom interior apartment",
        "apartment building exterior",
        "house exterior modern",
        "dining room interior apartment",
    ]
    if getattr(p, "rooms", None):
        try:
            r = int(p.rooms)
            if r >= 4:
                qs = [
                    "spacious living room interior",
                    "large bedroom interior",
                    "modern kitchen interior",
                    "apartment building exterior",
                ] + qs
            elif r == 1:
                qs = [
                    "studio apartment interior",
                    "compact living room interior",
                    "small kitchen interior",
                ] + qs
        except Exception:
            pass
    random.shuffle(qs)
    return qs


class Command(BaseCommand):
    help = "Скачивает тематические фото интерьеров/домов с Pexels и привязывает к Property."

    def add_arguments(self, parser):
        parser.add_argument("--per-property", type=int, default=4)
        parser.add_argument("--clear-existing", action="store_true")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        api_key = os.getenv("PEXELS_API_KEY")
        if not api_key:
            self.stderr.write("PEXELS_API_KEY не задан. Добавь его в .env.local и перезапусти.")
            return

        per_prop = int(opts["per_property"])
        clear = bool(opts["clear_existing"])
        limit = opts.get("limit")
        dry = bool(opts["dry_run"])

        props = Property.objects.all().order_by("id")
        if limit:
            props = props[:limit]

        if clear and not dry:
            PropertyImage.objects.all().delete()

        today = datetime.now()
        media_subdir = f"properties/{today:%Y/%m/%d}"
        media_dir = os.path.join(settings.MEDIA_ROOT, media_subdir.replace("/", os.sep))
        ensure_dir(media_dir)

        total = 0

        for p in props:
            if not clear and PropertyImage.objects.filter(property=p).exists():
                continue

            attached = 0
            tried = set()
            queries = choose_queries(p)

            for q in queries:
                if attached >= per_prop:
                    break
                if q in tried:
                    continue
                tried.add(q)

                try:
                    data = pexels_search(api_key, q, per_page=30, page=1)
                except Exception as e:
                    self.stderr.write(f"[ERR] search '{q}': {e}")
                    continue

                photos = data.get("photos", [])
                random.shuffle(photos)

                for ph in photos:
                    if attached >= per_prop:
                        break
                    src = ph.get("src", {})
                    url = src.get("large") or src.get("large2x") or src.get("original")
                    if not url:
                        continue

                    try:
                        content = download_and_prepare(url)
                    except Exception as e:
                        self.stderr.write(f"[ERR] download: {e}")
                        continue

                    filename = f"pex_{p.id}_{get_random_string(6)}.jpg"
                    rel_path = f"{media_subdir}/{filename}"
                    abs_path = os.path.join(settings.MEDIA_ROOT, rel_path.replace("/", os.sep))

                    if not dry:
                        with open(abs_path, "wb") as f:
                            f.write(content)
                        PropertyImage.objects.create(property=p, image=rel_path, alt=p.title or q)

                    attached += 1
                    total += 1
                    self.stdout.write(f"[OK] {rel_path} <- {q} -> Property {p.id}")

            if attached < per_prop:
                self.stderr.write(f"[WARN] Property {p.id}: прикреплено {attached}/{per_prop}")

        self.stdout.write(self.style.SUCCESS(f"Готово. Привязано файлов: {total}"))
