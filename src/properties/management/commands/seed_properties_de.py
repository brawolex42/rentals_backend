from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.conf import settings
from pathlib import Path
import random
from src.properties.models import Property, PropertyImage


class Command(BaseCommand):
    help = "Seed German properties with images"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=40)

    def handle(self, *args, **opts):
        count = int(opts.get("count") or 40)
        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not owner:
            owner = User.objects.create_superuser(username="admin", email="admin@example.com", password="admin12345")
        choices = []
        try:
            fld = Property._meta.get_field("property_type")
            if getattr(fld, "choices", None):
                choices = [c[0] for c in fld.choices if c and c[0]]
        except Exception:
            choices = []
        if not choices:
            choices = ["apartment", "house", "studio", "room"]
        cities = [
            "Berlin","Hamburg","München","Köln","Frankfurt am Main","Stuttgart","Düsseldorf","Dresden","Leipzig","Hannover",
            "Nürnberg","Bremen","Essen","Dortmund","Mannheim","Bonn","Karlsruhe","Wiesbaden","Münster","Augsburg"
        ]
        exts = []
        base = Path(settings.BASE_DIR) / "src" / "shared" / "static" / "real_images"
        for sub in ["exterior","living","kitchen","bedroom"]:
            d = base / sub
            if d.exists():
                exts += sorted([p for p in d.glob("**/*") if p.suffix.lower() in {".jpg",".jpeg",".png"}])
        fallback = Path(settings.BASE_DIR) / "media" / "properties" / "2025" / "08" / "19" / "pexels_47_453068.jpg"

        with transaction.atomic():
            items = []
            for i in range(count):
                city = random.choice(cities)
                rooms = random.choice([1,2,3,4,5])
                price = random.choice([850,990,1200,1450,1680,1850,2100,2400])
                ptype = random.choice(choices)
                title = random.choice([
                    "Loft im Zentrum","Helles Familienhaus","Komfortables Apartment","Ruhiges Reihenhaus",
                    "Charmantes Haus mit Garten","Gemütliches Einfamilienhaus","Modernes Studio","Elegantes Apartment"
                ])
                obj = Property(
                    owner=owner,
                    title=f"{title}",
                    description=f"Schöne Unterkunft in {city}. {rooms} Zimmer. Sofort bezugsfertig.",
                    city=city,
                    district="",
                    price=price,
                    rooms=rooms,
                    property_type=ptype,
                    is_active=True,
                )
                items.append(obj)
            created = Property.objects.bulk_create(items)

            for obj in created:
                pics = []
                for _ in range(1):
                    src = random.choice(exts) if exts else (fallback if fallback.exists() else None)
                    if src and src.exists():
                        data = src.read_bytes()
                    else:
                        data = b""
                    name = f"seed_{obj.pk or random.randint(1000,9999)}_{random.randint(1000,9999)}.jpg"
                    pics.append(PropertyImage(property=obj, alt=obj.title))
                    pics[-1].image.save(name, ContentFile(data), save=False)
                PropertyImage.objects.bulk_create(pics)

        self.stdout.write(self.style.SUCCESS(f"Created {len(created)} properties with images."))
