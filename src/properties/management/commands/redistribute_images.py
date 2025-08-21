from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
import os
from src.properties.models import Property, PropertyImage

def collect_images(media_root: Path, images_dir: str, images_list: str):
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    items = []
    if images_list:
        for p in [s.strip() for s in images_list.split(",") if s.strip()]:
            items.append(p.replace("\\","/"))
    elif images_dir:
        base = media_root / images_dir
        if base.exists():
            for root, _, files in os.walk(base):
                for f in files:
                    if Path(f).suffix.lower() in exts:
                        rel = (Path(root) / f).relative_to(media_root)
                        items.append(str(rel).replace("\\","/"))
    return items

class Command(BaseCommand):
    help = "Перераспределяет картинки между существующими объектами Property"

    def add_arguments(self, parser):
        parser.add_argument("--images-dir", type=str, default="")
        parser.add_argument("--images-list", type=str, default="")

    def handle(self, *args, **opts):
        media_root = Path(getattr(settings, "MEDIA_ROOT", "media"))
        pool = collect_images(media_root, opts["images_dir"], opts["images_list"])
        if not pool:
            self.stdout.write(self.style.ERROR("Нет картинок для распределения"))
            return
        props = Property.objects.all().order_by("id")
        total = props.count()
        for i, p in enumerate(props):
            img_rel = pool[i % len(pool)]
            PropertyImage.objects.filter(property=p).delete()
            PropertyImage.objects.create(property=p, image=img_rel, alt=p.title, address_line="")
        self.stdout.write(self.style.SUCCESS(f"Готово! Обновлено объектов: {total}"))
