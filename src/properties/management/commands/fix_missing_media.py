
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.crypto import get_random_string

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except Exception:
    PIL_OK = False

from src.properties.models import PropertyImage, Property

PLACEHOLDER_SIZE = (1280, 853)  # 3:2
BG_COLORS = ["#e2e8f0", "#f1f5f9", "#e5e7eb", "#d1d5db", "#cbd5e1"]


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def safe_font():
    # Пытаемся взять «живой» TTF, иначе дефолтный bitmap
    try:
        return ImageFont.truetype("arial.ttf", 60)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", 60)
        except Exception:
            return ImageFont.load_default()


def text_size(draw: "ImageDraw.ImageDraw", text: str, font: "ImageFont.ImageFont"):
    """
    Универсальное измерение текста:
    - Pillow>=8: draw.textbbox
    - Иначе: anchor="mm" без вычислений
    Возвращает (w,h) или None, если измерить нельзя.
    """

    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        return w, h

    return None


def draw_placeholder(text: str):
    img = Image.new("RGB", PLACEHOLDER_SIZE, BG_COLORS[hash(text) % len(BG_COLORS)])
    draw = ImageDraw.Draw(img)
    font = safe_font()

    ts = text_size(draw, text, font)
    if ts is not None:
        w, h = ts
        x = (PLACEHOLDER_SIZE[0] - w) // 2
        y = (PLACEHOLDER_SIZE[1] - h) // 2
        draw.text((x, y), text, fill="#111111", font=font)
    else:

        cx = PLACEHOLDER_SIZE[0] // 2
        cy = PLACEHOLDER_SIZE[1] // 2
        try:
            draw.text((cx, cy), text, fill="#111111", font=font, anchor="mm")
        except TypeError:

            draw.text((PLACEHOLDER_SIZE[0] * 0.1, PLACEHOLDER_SIZE[1] * 0.45),
                      text, fill="#111111", font=font)
    return img


class Command(BaseCommand):
    help = "Создаёт недостающие файлы картинок для PropertyImage, чтобы убрать 404 по /media/..."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Ограничить кол-во восстановлений")

    def handle(self, *args, **opts):
        if not hasattr(settings, "MEDIA_ROOT"):
            self.stderr.write("MEDIA_ROOT не задан. Проверь settings.")
            return

        if not PIL_OK:
            self.stdout.write(self.style.WARNING(
                "Pillow не установлен. Установи: pip install Pillow\n"
                "Команда всё равно создаст минимальные заглушки."
            ))

        fixed = 0
        missing = 0
        limit = opts.get("limit")

        qs = PropertyImage.objects.select_related("property").all().order_by("id")

        for pi in qs:
            rel_name = pi.image.name or ""
            if not rel_name:
                today = datetime.now()
                rel_name = f"properties/{today:%Y/%m/%d}/auto_{get_random_string(6)}.jpg"
                pi.image.name = rel_name

            abs_path = os.path.join(settings.MEDIA_ROOT, rel_name.replace("/", os.sep))
            if not os.path.exists(abs_path):
                missing += 1
                ensure_dir(os.path.dirname(abs_path))

                if PIL_OK:
                    title = getattr(pi.property, "title", "") or f"Property #{pi.property_id}"
                    img = draw_placeholder(title[:40])
                    img.save(abs_path, format="JPEG", quality=85)
                else:
                    # Минимальный валидный JPEG-заголовок
                    with open(abs_path, "wb") as f:
                        f.write(b"\xFF\xD8\xFF\xD9")

                pi.save(update_fields=["image"])
                fixed += 1
                self.stdout.write(f"[FIXED] {rel_name}")

                if limit and fixed >= limit:
                    break

        self.stdout.write(self.style.SUCCESS(f"Готово. Недостающих: {missing}, создано файлов: {fixed}."))


        no_image_props = Property.objects.filter(images__isnull=True).order_by("id").distinct()
        created_links = 0
        for p in no_image_props:
            today = datetime.now()
            rel_name = f"properties/{today:%Y/%m/%d}/auto_{get_random_string(6)}.jpg"
            abs_path = os.path.join(settings.MEDIA_ROOT, rel_name.replace("/", os.sep))
            ensure_dir(os.path.dirname(abs_path))

            if PIL_OK:
                img = draw_placeholder((p.title or f"Property #{p.id}")[:40])
                img.save(abs_path, format="JPEG", quality=85)
            else:
                with open(abs_path, "wb") as f:
                    f.write(b"\xFF\xD8\xFF\xD9")

            PropertyImage.objects.create(property=p, image=rel_name, alt=p.title or "")
            created_links += 1
            self.stdout.write(f"[LINKED] {rel_name} -> Property {p.id}")

        if created_links:
            self.stdout.write(self.style.SUCCESS(
                f"Добавлены заглушки для объектов без фото: {created_links}"
            ))
