from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from pathlib import Path
from decimal import Decimal
import random, os
from datetime import date, timedelta

try:
    from faker import Faker
except Exception:
    Faker = None

from src.properties.models import Property, PropertyImage
try:
    from src.shared.enums import PropertyType
    PTYPES = [c[0] for c in PropertyType.choices]
except Exception:
    PTYPES = ["apartment", "house", "townhouse", "loft", "studio"]

GERMAN_CITIES = [
    "Berlin","Hamburg","München","Köln","Frankfurt am Main","Stuttgart","Düsseldorf","Dortmund","Essen","Leipzig",
    "Bremen","Dresden","Hannover","Nürnberg","Duisburg","Bochum","Wuppertal","Bielefeld","Bonn","Münster",
    "Karlsruhe","Mannheim","Augsburg","Wiesbaden","Gelsenkirchen","Mönchengladbach","Braunschweig","Chemnitz",
    "Kiel","Aachen","Halle (Saale)","Magdeburg","Freiburg im Breisgau","Krefeld","Lübeck","Oberhausen","Erfurt",
    "Mainz","Rostock","Kassel","Hagen","Saarbrücken","Hamm","Potsdam","Ludwigshafen am Rhein","Oldenburg",
    "Leverkusen","Osnabrück","Solingen","Heidelberg","Darmstadt","Herne"
]

DISTRICTS = [
    "Mitte","Altstadt","Nord","Süd","West","Ost","Innenstadt","Neustadt","Linden","Charlottenburg","Schwabing",
    "Sachsenhausen","Vahrenwald","Barmbek","Friedrichshain","Prenzlauer Berg","Eimsbüttel","Neukölln","Pasing"
]

TITLE_TEMPLATES = [
    "Loft im Zentrum","Helles Familienhaus","Komfortables Apartment","Ruhiges Reihenhaus","Gemütliches Einfamilienhaus",
    "Modernes Studio","Stilvolle Stadtwohnung","Geräumige 3-Zimmer-Wohnung","Maisonette mit Balkon","Penthouse mit Aussicht"
]

def get_owner(opts):
    User = get_user_model()
    if opts.get("owner_id"):
        try:
            return User.objects.get(pk=opts["owner_id"])
        except User.DoesNotExist:
            raise CommandError(f"User with id={opts['owner_id']} not found")
    if opts.get("owner_email"):
        owner, _ = User.objects.get_or_create(
            email=opts["owner_email"],
            defaults={"username": opts["owner_email"], "is_active": True},
        )
        return owner
    owner = User.objects.filter(is_superuser=True).first()
    if owner:
        return owner
    owner = User.objects.first()
    if owner:
        return owner
    owner = User.objects.create(username="demo_owner", email="demo-owner@example.com", is_active=True)
    try:
        owner.set_password("demo1234")
        owner.save(update_fields=["password"])
    except Exception:
        pass
    return owner

def collect_images(media_root: Path, images_dir: str, images_list: str, fallback_rel: str):
    exts = {".jpg",".jpeg",".png",".webp",".bmp"}
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
    if not items and fallback_rel:
        items = [fallback_rel.replace("\\","/")]
    return items

class Command(BaseCommand):
    help = "Добавляет демо-объекты недвижимости в Германии"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=40)
        parser.add_argument("--with-images", action="store_true")
        parser.add_argument("--image-path", type=str, default="properties/2025/08/19/pexels_47_453068.jpg")
        parser.add_argument("--images-dir", type=str, default="")
        parser.add_argument("--images-list", type=str, default="")
        parser.add_argument("--owner-id", type=int)
        parser.add_argument("--owner-email", type=str)

    @transaction.atomic
    def handle(self, *args, **opts):
        count = opts["count"]
        with_images = opts["with_images"]
        image_rel = opts["image_path"]
        images_dir = opts["images_dir"]
        images_list = opts["images_list"]
        fake = Faker("de_DE") if Faker else None
        media_root = Path(getattr(settings, "MEDIA_ROOT", "media"))
        pool = collect_images(media_root, images_dir, images_list, image_rel)
        can_attach = with_images and len(pool) > 0
        owner = get_owner(opts)
        created = 0
        for i in range(count):
            city = random.choice(GERMAN_CITIES)
            district = random.choice(DISTRICTS)
            title = f"{random.choice(TITLE_TEMPLATES)} – {city}"
            kwargs = {
                "owner": owner,
                "title": title,
                "description": (fake.paragraph(nb_sentences=3) if fake else "Schöne Immobilie zur Miete in Deutschland."),
                "city": city,
                "district": district,
                "price": Decimal(random.randint(650, 3500)),
                "rooms": random.randint(1, 5),
                "property_type": random.choice(PTYPES),
                "is_active": True,
            }
            obj = Property.objects.create(**kwargs)
            if can_attach:
                try:
                    img_rel = pool[i % len(pool)]
                    PropertyImage.objects.create(property=obj, image=img_rel, alt=title, address_line="")
                except Exception:
                    pass
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Готово! Создано объектов: {created}"))
