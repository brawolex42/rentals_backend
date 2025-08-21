from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from django.core.files import File
from django.conf import settings

from pathlib import Path
import random
import uuid


try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except Exception:
    PIL_OK = False

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

SEARCH_DIRS = [
    Path("static/seed_images"),
    Path("seed_images"),
    Path("properties/seed_images"),
    Path("shared/seed_images"),
]

def _has_field(model, name: str) -> bool:
    return any(getattr(f, "name", None) == name for f in model._meta.get_fields())

def _get_fk_name_to_property(PropertyImage, Property):
    for f in PropertyImage._meta.get_fields():
        if getattr(getattr(f, "remote_field", None), "model", None) == Property:
            return f.name
    return "property"

def _collect_images_recursively(dirs):
    pool = []
    for d in dirs:
        if d.is_dir():
            for p in d.rglob("*"):
                if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                    pool.append(p)
    return pool

def _ensure_pool(img_dir: str | None):
    dirs = []
    if img_dir:
        dirs.append(Path(img_dir))
    dirs.extend(SEARCH_DIRS)

    pool = _collect_images_recursively(dirs)
    if pool:
        return pool


    if not PIL_OK:
        return []

    target_dir = Path("static/seed_images")
    target_dir.mkdir(parents=True, exist_ok=True)

    W, H = 1600, 1067
    colors = [(200, 210, 230), (210, 230, 200), (230, 210, 200), (220, 220, 220), (200, 225, 215)]
    font = None
    try:
        # Без внешних шрифтов: Pillow возьмет дефолтный
        font = ImageFont.load_default()
    except Exception:
        font = None

    generated = []
    for i in range(1, 25):  # 24 плейсхолдера
        img = Image.new("RGB", (W, H), random.choice(colors))
        d = ImageDraw.Draw(img)
        text = f"Sample Home {i}"
        tw, th = d.textbbox((0, 0), text, font=font)[2:]
        d.text(((W - tw) / 2, (H - th) / 2), text, fill=(60, 60, 60), font=font)
        out = target_dir / f"placeholder_{i:02d}.jpg"
        img.save(out, quality=90)
        generated.append(out)

    return generated

class Command(BaseCommand):
    help = "Привязывает по N изображений к каждому Property (по умолчанию 5). Ищет рекурсивно; при отсутствии изображений генерирует плейсхолдеры."

    def add_arguments(self, parser):
        parser.add_argument("--per", type=int, default=5, help="Сколько фото на один объект (по умолчанию 5).")
        parser.add_argument("--dir", type=str, default=None, help="Папка с картинками (поиск рекурсивный).")
        parser.add_argument("--only-empty", action="store_true", help="Только объекты без изображений.")
        parser.add_argument("--country", type=str, default=None, help="Фильтр по стране (например, 'Germany').")
        parser.add_argument("--ids", type=str, default=None, help="Список PK через запятую.")
        parser.add_argument("--min", dest="min_id", type=int, default=None, help="Минимальный PK (включительно).")
        parser.add_argument("--max", dest="max_id", type=int, default=None, help="Максимальный PK (включительно).")

    def handle(self, *args, **opts):
        per = max(1, int(opts["per"]))
        img_dir = opts.get("dir")
        only_empty = bool(opts["only_empty"])
        country = opts.get("country")
        ids_raw = opts.get("ids")
        min_id = opts.get("min_id")
        max_id = opts.get("max_id")

        Property = apps.get_model("properties", "Property")
        PropertyImage = apps.get_model("properties", "PropertyImage")
        fk_name = _get_fk_name_to_property(PropertyImage, Property)

        pool = _ensure_pool(img_dir)
        if not pool:
            self.stderr.write(self.style.ERROR(
                "Не найдены изображения и не удалось сгенерировать плейсхолдеры. "
                "Положи файлы в 'static/seed_images' или укажи --dir и установи Pillow: pip install pillow"
            ))
            return

        qs = Property.objects.all().order_by("pk")
        if country and _has_field(Property, "country"):
            qs = qs.filter(country=country)
        if min_id is not None:
            qs = qs.filter(pk__gte=min_id)
        if max_id is not None:
            qs = qs.filter(pk__lte=max_id)
        if ids_raw:
            ids_list = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]
            qs = qs.filter(pk__in=ids_list)

        attached_total = 0
        for prop in qs:
            if only_empty:
                if PropertyImage.objects.filter(**{fk_name: prop}).exists():
                    continue

            existing_count = PropertyImage.objects.filter(**{fk_name: prop}).count()
            need = max(0, per - existing_count)
            if need == 0:
                continue

            chosen = random.sample(pool, k=min(need, len(pool)))
            created_here = 0

            for idx, path in enumerate(chosen, start=1):
                sid = transaction.savepoint()
                try:
                    img_obj = PropertyImage()
                    setattr(img_obj, fk_name, prop)

                    # Полезные поля, если есть
                    if _has_field(PropertyImage, "caption"):
                        setattr(img_obj, "caption", "Außenansicht")
                    if _has_field(PropertyImage, "address_line") and hasattr(prop, "address"):
                        setattr(img_obj, "address_line", getattr(prop, "address"))
                    if _has_field(PropertyImage, "position"):
                        setattr(img_obj, "position", existing_count + idx)
                    if _has_field(PropertyImage, "is_primary"):
                        setattr(img_obj, "is_primary", existing_count == 0 and idx == 1)

                    if not _has_field(PropertyImage, "image"):
                        transaction.savepoint_rollback(sid)
                        self.stderr.write(self.style.ERROR("У модели PropertyImage нет поля 'image'."))
                        break

                    with open(path, "rb") as fh:
                        ext = path.suffix.lower()
                        base = f"{prop.pk}_{uuid.uuid4().hex[:8]}{ext}"
                        img_obj.image.save(base, File(fh), save=False)

                    img_obj.save()
                    transaction.savepoint_commit(sid)
                    created_here += 1
                    attached_total += 1
                except Exception as e:
                    transaction.savepoint_rollback(sid)
                    self.stderr.write(self.style.WARNING(f"Пропустил фото для Property #{prop.pk}: {e}"))

            self.stdout.write(self.style.SUCCESS(
                f"Property #{prop.pk}: добавлено {created_here} фото (нужно было {need})."
            ))

        self.stdout.write(self.style.SUCCESS(f"Готово. Всего добавлено изображений: {attached_total}."))
