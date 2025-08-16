from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.apps import apps
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import random

def make_img(text: str) -> ContentFile:
    img = Image.new("RGB", (1280, 800), (230, 233, 239))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    w, h = img.size
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.rectangle([(0, h - 120), (w, h)], fill=(20, 22, 26))
    d.text(((w - tw) // 2, h - 80), text, font=font, fill=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return ContentFile(buf.getvalue(), name=f"demo_{random.randint(1000,9999)}.jpg")

class Command(BaseCommand):
    help = "Create placeholder PropertyImage for each Property"

    def add_arguments(self, parser):
        parser.add_argument("--per", type=int, default=3, help="Images per property")

    def handle(self, *args, **opts):
        Property = apps.get_model("properties", "Property")
        PropertyImage = apps.get_model("properties", "PropertyImage")
        per = max(1, int(opts["per"]))
        count_props = 0
        count_imgs = 0
        for p in Property.objects.all():
            existing = PropertyImage.objects.filter(property=p).count()
            need = max(0, per - existing)
            if need <= 0:
                continue
            for i in range(need):
                img = make_img(f"{p.city} · {p.rooms}к · €{p.price}")
                PropertyImage.objects.create(property=p, image=img, alt=p.title)
                count_imgs += 1
            count_props += 1
        self.stdout.write(self.style.SUCCESS(f"Updated {count_props} properties, created {count_imgs} images."))
