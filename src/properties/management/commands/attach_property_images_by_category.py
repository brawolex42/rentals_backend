from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from django.core.files import File
from pathlib import Path
import random, uuid

CATS = ["exterior", "living", "bedroom", "kitchen", "bathroom"]

def _has_field(model, name: str) -> bool:
    return any(getattr(f, "name", None) == name for f in model._meta.get_fields())

def _fk_name(PropertyImage, Property):
    for f in PropertyImage._meta.get_fields():
        if getattr(getattr(f, "remote_field", None), "model", None) == Property:
            return f.name
    return "property"

def _collect_pool(base: Path):
    pool = {c: [] for c in CATS}
    for c in CATS:
        d = base / c
        if d.is_dir():
            for p in d.rglob("*"):
                if p.suffix.lower() in {".jpg",".jpeg",".png",".webp"}:
                    pool[c].append(p)
    return pool

class Command(BaseCommand):
    help = "Прикрепляет фото из папок по категориям: exterior, living, bedroom, kitchen, bathroom. 2 экстерьера + 4 интерьера на объект (по умолчанию)."

    def add_arguments(self, parser):
        parser.add_argument("--dir", type=str, default="static/real_images", help="База с поддиректориями категорий.")
        parser.add_argument("--per", type=int, default=6, help="Сколько фото на объект в итоге.")
        parser.add_argument("--exteriors", type=int, default=2, help="Сколько экстерьеров на объект.")
        parser.add_argument("--replace", action="store_true", help="Удалить текущие изображения объекта и заменить новыми.")
        parser.add_argument("--make-primary", action="store_true", help="Первое фото пометить is_primary=True (если поле есть).")
        parser.add_argument("--city-in", type=str, default=None, help="Список городов через запятую (фильтр Property.city).")
        parser.add_argument("--ids", type=str, default=None, help="Только эти PK (через запятую).")

    def handle(self, *args, **opts):
        base = Path(opts["dir"])
        per = max(1, int(opts["per"]))
        exteriors = max(0, min(per, int(opts["exteriors"])))
        replace = bool(opts["replace"])
        make_primary = bool(opts["make_primary"])
        cities_raw = opts.get("city_in")
        ids_raw = opts.get("ids")

        Property = apps.get_model("properties", "Property")
        PropertyImage = apps.get_model("properties", "PropertyImage")
        fk_name = _fk_name(PropertyImage, Property)

        if not _has_field(PropertyImage, "image"):
            self.stderr.write(self.style.ERROR("PropertyImage.image не найден"))
            return

        pool = _collect_pool(base)
        if not any(pool.values()):
            self.stderr.write(self.style.ERROR(f"Нет картинок в {base}. Ожидаются подпапки: {', '.join(CATS)}"))
            return

        qs = Property.objects.all().order_by("pk")
        if cities_raw and _has_field(Property, "city"):
            cities = [c.strip() for c in cities_raw.split(",") if c.strip()]
            qs = qs.filter(city__in=cities)
        if ids_raw:
            ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]
            qs = qs.filter(pk__in=ids)

        attached_total = 0
        for prop in qs:
            # существующие
            existing_qs = PropertyImage.objects.filter(**{fk_name: prop})
            if replace:
                existing_qs.delete()
                existing_count = 0
            else:
                existing_count = existing_qs.exclude(image="").exclude(image__isnull=True).count()

            need = max(0, per - existing_count)
            if need == 0:
                continue

            # выбираем 2 экстерьера + остальное интерьеры
            chosen = []
            if pool["exterior"]:
                k = min(exteriors, need, len(pool["exterior"]))
                chosen += random.sample(pool["exterior"], k=k)
            interior_pool = pool["living"] + pool["bedroom"] + pool["kitchen"] + pool["bathroom"]
            if interior_pool and len(chosen) < need:
                k = min(need - len(chosen), len(interior_pool))
                chosen += random.sample(interior_pool, k=k)
            # если внезапно не хватило — добиваем чем есть
            if len(chosen) < need:
                rest = []
                for c in CATS:
                    rest += pool[c]
                if rest:
                    k = min(need - len(chosen), len(rest))
                    chosen += random.sample(rest, k=k)

            created_here = 0
            for idx, path in enumerate(chosen, start=1):
                sid = transaction.savepoint()
                try:
                    img = PropertyImage()
                    setattr(img, fk_name, prop)
                    if _has_field(PropertyImage, "position"):
                        img.position = existing_count + idx
                    if _has_field(PropertyImage, "caption"):
                        img.caption = f"{prop.title or 'Property'}"
                    if make_primary and _has_field(PropertyImage, "is_primary"):
                        img.is_primary = (existing_count == 0 and idx == 1)
                    with open(path, "rb") as fh:
                        name = f"{prop.pk}_{uuid.uuid4().hex[:8]}{path.suffix.lower()}"
                        img.image.save(name, File(fh), save=False)
                    img.save()
                    transaction.savepoint_commit(sid)
                    created_here += 1
                    attached_total += 1
                except Exception as e:
                    transaction.savepoint_rollback(sid)
                    self.stderr.write(self.style.WARNING(f"Property #{prop.pk}: не удалось прикрепить {path.name}: {e}"))

            self.stdout.write(self.style.SUCCESS(f"Property #{prop.pk}: добавлено {created_here} фото (нужно было {need})."))

        self.stdout.write(self.style.SUCCESS(f"Готово. Всего прикреплено: {attached_total}."))
