import os
import random
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.apps import apps
from django.db import transaction
from django.conf import settings
from faker import Faker
from PIL import Image, ImageDraw, ImageFont

User = get_user_model()

def _pick_font():
    candidates = [
        "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, 48)
        except:
            continue
    return ImageFont.load_default()

def _text_size(draw, text, font):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except:
        return draw.textsize(text, font=font)

def make_img(text: str) -> ContentFile:
    img = Image.new("RGB", (1280, 800), (random.randint(20, 80), random.randint(40, 90), random.randint(90, 160)))
    d = ImageDraw.Draw(img)
    font = _pick_font()
    w, h = img.size
    tw, th = _text_size(d, text, font)
    d.rectangle([(0, h - 120), (w, h)], fill=(0, 0, 0))
    d.text(((w - tw) // 2, h - 80), text, font=font, fill=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return ContentFile(buf.getvalue(), name=f"seed/faker_{random.randint(1000,9999)}.jpg")

class Command(BaseCommand):
    def add_arguments(self, p):
        p.add_argument("--count", type=int, default=20)
        p.add_argument("--owner", type=str, default=None)

    @transaction.atomic
    def handle(self, *a, **o):
        fake = Faker("de_DE")
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        os.makedirs(os.path.join(settings.MEDIA_ROOT, "seed"), exist_ok=True)

        owner = None
        if o["owner"]:
            owner = get_user_model().objects.get(username=o["owner"])

        Property = apps.get_model("properties", "Property")
        PhotoModel = None
        for name in ("PropertyImage", "PropertyPhoto", "Photo", "Image"):
            try:
                PhotoModel = apps.get_model("properties", name)
                break
            except LookupError:
                pass

        fields = {f.name for f in Property._meta.fields}

        for _ in range(o["count"]):
            city = fake.city()
            district = fake.city_suffix()
            address = fake.street_address()
            postal = fake.postcode()
            rooms = random.choice([1, 2, 3, 4, 5])
            area = random.choice([28, 36, 45, 52, 64, 72, 85, 98, 120])
            price = random.choice([650, 790, 920, 1100, 1350, 1600, 2000, 2400])
            ht = random.choice(["apartment", "house", "studio", "room"])
            title = f"{city}: {rooms}-комн., {area} м²"
            desc = f"{address}, {postal} {city}. {rooms} комн."

            data = {}
            if "title" in fields: data["title"] = title
            if "name" in fields and "title" not in fields: data["name"] = title
            if "description" in fields: data["description"] = desc
            if "city" in fields: data["city"] = city
            if "district" in fields: data["district"] = district
            if "address" in fields: data["address"] = address
            if "postal_code" in fields: data["postal_code"] = postal
            if "price" in fields: data["price"] = price
            if "rooms" in fields: data["rooms"] = rooms
            if "area" in fields: data["area"] = area
            if "home_type" in fields: data["home_type"] = ht
            if "rating_avg" in fields: data["rating_avg"] = random.choice([None, 3.8, 4.1, 4.6, 4.9])
            if "reviews_total" in fields: data["reviews_total"] = random.randint(0, 120)
            if "is_active" in fields: data["is_active"] = True
            if "owner" in fields:
                data["owner"] = owner or User.objects.filter(is_superuser=True).first() or User.objects.first() or User.objects.create_user("demo_owner", "demo@example.com", "demo12345")

            obj = Property.objects.create(**data)

            img = make_img(f"{city} • {rooms} комн • {area} м²")
            if "cover_image" in fields:
                obj.cover_image.save(img.name, img, save=True)
            elif "image" in fields:
                obj.image.save(img.name, img, save=True)
            elif PhotoModel:
                pmf = {f.name for f in PhotoModel._meta.fields}
                if "property" in pmf:
                    PhotoModel.objects.create(property=obj, image=img)
                elif "listing" in pmf:
                    PhotoModel.objects.create(listing=obj, image=img)
