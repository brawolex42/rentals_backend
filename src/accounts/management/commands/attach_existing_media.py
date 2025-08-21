from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from pathlib import Path
from itertools import cycle
import random
from src.properties.models import Property, PropertyImage

class Command(BaseCommand):
    help = "Attach existing files from MEDIA_ROOT/properties to PropertyImage records"

    def add_arguments(self, parser):
        parser.add_argument("--per", type=int, default=3)
        parser.add_argument("--replace", action="store_true")
        parser.add_argument("--prefix", type=str, default="")
        parser.add_argument("--shuffle", action="store_true")

    def handle(self, *args, **opts):
        per = max(1, int(opts.get("per") or 1))
        replace = bool(opts.get("replace"))
        prefix = (opts.get("prefix") or "").strip().lower()
        shuffle = bool(opts.get("shuffle"))

        base = Path(settings.MEDIA_ROOT) / "properties"
        if not base.exists():
            self.stdout.write(self.style.ERROR(f"Not found: {base}"))
            return

        files = [p for p in base.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        if prefix:
            files = [p for p in files if p.name.lower().startswith(prefix)]
        files = [p for p in files if p.is_file()]
        if not files:
            self.stdout.write(self.style.ERROR("No image files found"))
            return
        files = sorted(files)
        if shuffle:
            random.shuffle(files)

        props = list(Property.objects.order_by("id"))
        if not props:
            self.stdout.write(self.style.WARNING("No properties found"))
            return

        with transaction.atomic():
            if replace:
                PropertyImage.objects.all().delete()

            imgs_cycle = cycle(files)
            attached_total = 0
            for prop in props:
                have = prop.images.count()
                need = max(0, per - have)
                for _ in range(need):
                    src = next(imgs_cycle)
                    rel = src.relative_to(settings.MEDIA_ROOT).as_posix()
                    pi = PropertyImage(property=prop, alt=prop.title or "")
                    pi.image.name = rel
                    pi.save()
                    attached_total += 1

        self.stdout.write(self.style.SUCCESS(f"Attached {attached_total} images to {len(props)} properties."))
