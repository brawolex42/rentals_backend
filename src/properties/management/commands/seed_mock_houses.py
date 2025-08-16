import os
import random
from io import BytesIO
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction, models

from faker import Faker
from PIL import Image, ImageDraw, ImageFont

User = get_user_model()

def _pick_font():
    for p in [
        "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]:
        try:
            return ImageFont.truetype(p, 48)
        except Exception:
            pass
    return ImageFont.load_default()

def _text_size(draw, text, font):
    try:
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        return r - l, b - t
    except Exception:
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

def _fill_required_defaults(model, data: dict):
    for f in model._meta.concrete_fields:
        if f.primary_key or isinstance(f, (models.AutoField, models.BigAutoField, models.UUIDField)):
            continue
        has_default = f.has_default() or (getattr(f, "default", models.NOT_PROVIDED) is not models.NOT_PROVIDED)
        if (f.name not in data) and (not f.null) and (not has_default):
            if isinstance(f, (models.CharField, models.TextField)):
                data[f.name] = "N/A"
            elif isinstance(f, (models.IntegerField, models.BigIntegerField, models.SmallIntegerField, models.PositiveIntegerField)):
                data[f.name] = 0
            elif isinstance(f, models.DecimalField):
                data[f.name] = Decimal("0")
            elif isinstance(f, models.FloatField):
                data[f.name] = 0.0
            elif isinstance(f, models.BooleanField):
                data[f.name] = False
            elif isinstance(f, models.DateField) and not isinstance(f, models.DateTimeField):
                data[f.name] = date.today()
            elif isinstance(f, models.DateTimeField):
                data[f.name] = datetime.now()

class Command(BaseCommand):
    help = "Seed mock properties with generated images"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=20)
        parser.add_argument("--owner", type=str, default=None)

    @transaction.atomic
    def handle(self, *args, **options):
        fake = Faker("de_DE")
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        os.makedirs(os.path.join(settings.MEDIA_ROOT, "seed"), exist_ok=True)

        owner = None
        if options["owner"]:
            owner = User.objects.get(username=options["owner"])

        Property = apps.get_model("properties", "Property")

        PhotoModel = None
        for name in ("PropertyImage", "PropertyPhoto", "Photo", "Image"):
            try:
                PhotoModel = apps.get_model("properties", name)
                break
            except LookupError:
                pass

        prop_fields = {f.name for f in Property._meta.get_fields() if getattr(f, "attname", None)}

        for _ in range(options["count"]):
            city = fake.city()
            district = fake.city_suffix()
            street = fake.street_name()
            house_no = fake.building_number()
            address_line = f"{street} {house_no}"
            postal = fake.postcode()
            full_address = f"{address_line}, {postal} {city}"
            rooms = random.choice([1, 2, 3, 4, 5])
            area = random.choice([28, 36, 45, 52, 64, 72, 85, 98, 120])
            price = random.choice([650, 790, 920, 1100, 1350, 1600, 2000, 2400])
            home_type_raw = random.choice(["apartment", "house", "studio", "room"])
            title = f"{city}: {rooms}-комн., {area} м²"
            desc = f"{full_address}. {rooms} комн."

            data = {}

            if "title" in prop_fields:
                data["title"] = title
            elif "name" in prop_fields:
                data["name"] = title

            if "description" in prop_fields:
                data["description"] = desc

            if "city" in prop_fields: data["city"] = city
            if "district" in prop_fields: data["district"] = district
            if "address" in prop_fields: data["address"] = full_address
            if "address_line" in prop_fields: data["address_line"] = full_address
            if "street" in prop_fields: data["street"] = street
            if "house_number" in prop_fields: data["house_number"] = house_no
            if "postal_code" in prop_fields: data["postal_code"] = postal
            if "country" in prop_fields: data["country"] = "Germany"
            if "address1" in prop_fields: data["address1"] = full_address
            if "address2" in prop_fields: data["address2"] = ""

            if "latitude" in prop_fields: data["latitude"] = float(fake.latitude())
            if "longitude" in prop_fields: data["longitude"] = float(fake.longitude())

            if "price" in prop_fields: data["price"] = price
            if "rooms" in prop_fields: data["rooms"] = rooms
            if "bedrooms" in prop_fields: data["bedrooms"] = max(1, rooms - 1)
            if "bathrooms" in prop_fields: data["bathrooms"] = random.choice([1, 1, 2])
            if "area" in prop_fields: data["area"] = area

            if "home_type" in prop_fields:
                data["home_type"] = home_type_raw
            elif "property_type" in prop_fields:
                data["property_type"] = home_type_raw

            if "rating_avg" in prop_fields: data["rating_avg"] = random.choice([None, 3.8, 4.1, 4.6, 4.9])
            if "reviews_total" in prop_fields: data["reviews_total"] = random.randint(0, 120)
            if "currency" in prop_fields: data["currency"] = "EUR"
            if "is_active" in prop_fields: data["is_active"] = True
            if "available_from" in prop_fields: data["available_from"] = date.today() + timedelta(days=random.randint(1, 60))
            if "status" in prop_fields: data["status"] = "active"

            if "slug" in prop_fields:
                base = f"{city}-{street}-{house_no}".lower().replace(" ", "-")
                data["slug"] = f"{base}-{random.randint(1000,9999)}"

            if "owner" in prop_fields or "owner_id" in prop_fields:
                data["owner"] = (
                    owner
                    or User.objects.filter(is_superuser=True).first()
                    or User.objects.first()
                    or User.objects.create_user("demo_owner", "demo@example.com", "demo12345")
                )

            _fill_required_defaults(Property, data)

            obj = Property.objects.create(**data)

            img = make_img(f"{city} • {rooms} комн • {area} м²")
            model_fields = {f.name for f in Property._meta.get_fields() if getattr(f, "attname", None)}
            if "cover_image" in model_fields:
                obj.cover_image.save(img.name, img, save=True)
            elif "image" in model_fields:
                obj.image.save(img.name, img, save=True)
            elif PhotoModel:
                pmf = {f.name for f in PhotoModel._meta.fields}
                if "property" in pmf:
                    PhotoModel.objects.create(property=obj, image=img)
                elif "listing" in pmf:
                    PhotoModel.objects.create(listing=obj, image=img)
