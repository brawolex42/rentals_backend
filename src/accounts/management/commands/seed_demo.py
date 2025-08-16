from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.apps import apps
from faker import Faker
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from django.core.files.base import ContentFile
import random

Property = apps.get_model("properties", "Property")
PropertyPhoto = apps.get_model("properties", "PropertyPhoto")

def make_img(text: str) -> ContentFile:
    img = Image.new("RGB", (1280, 800), random.choice([(230,240,255),(255,240,230),(240,255,230),(240,240,240)]))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 46)
    except Exception:
        font = ImageFont.load_default()
    w, h = img.size
    tw, th = d.textbbox((0, 0), text, font=font)[2:]
    d.rectangle([(0, h - 120), (w, h)], fill=(20, 22, 26))
    d.text(((w - tw) // 2, h - 80), text, font=font, fill=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return ContentFile(buf.getvalue(), name=f"demo_{random.randint(1000,9999)}.jpg")

class Command(BaseCommand):
    help = "Generate demo properties with photos"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=30)
        parser.add_argument("--purge", action="store_true")

    def handle(self, *args, **opts):
        count = opts["count"]
        purge = opts["purge"]

        if purge:
            PropertyPhoto.objects.all().delete()
            Property.objects.all().delete()
            self.stdout.write(self.style.WARNING("Purged all properties & photos"))

        f = {f.name for f in Property._meta.fields}
        fake = Faker(["ru_RU", "de_DE", "en_US"])

        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not owner:
            owner = User.objects.create_user(username="demo_owner", email="demo@example.com", password="demo12345")

        cities = ["Berlin","Hamburg","München","Köln","Frankfurt","Stuttgart","Düsseldorf",
                  "Dresden","Leipzig","Hannover","Moscow","Saint Petersburg","Kazan",
                  "Sochi","Novosibirsk","Yekaterinburg","Krasnodar","Voronezh",
                  "Kaliningrad","Nizhny Novgorod","London","Manchester","Bristol",
                  "Leeds","Liverpool","Edinburgh","Birmingham","Glasgow","Oxford","Cambridge"]

        created = 0
        for _ in range(count):
            city = random.choice(cities)
            district = fake.city_suffix()
            rooms = random.choice([1,2,3,4,5])
            area = random.choice([28, 36, 45, 52, 64, 72, 85, 98, 120])
            price = random.choice([650, 790, 920, 1100, 1350, 1600, 2000, 2400])
            property_type = random.choice(["apartment","house","studio","room"])
            title = f"{city}: {rooms} комн., {area} м²"
            desc = fake.paragraph(nb_sentences=4)

            data = dict(
                owner=owner if "owner" in f else None,
                title=title if "title" in f else None,
                description=desc if "description" in f else None,
                city=city if "city" in f else None,
                district=district if "district" in f else None,
                price=price if "price" in f else None,
                rooms=rooms if "rooms" in f else None,
                property_type=property_type if "property_type" in f else None,
                area=area if "area" in f else None,
                is_active=True if "is_active" in f else None,
            )
            # удалим None-ключи
            data = {k: v for k, v in data.items() if v is not None}

            p = Property.objects.create(**data)

            for _i in range(random.choice([1,1,2,3])):  # 1–3 фото
                img = make_img(f"{city} • {rooms} • {area} м² • {price}€")
                PropertyPhoto.objects.create(property=p, image=img)

            created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} properties with photos"))
