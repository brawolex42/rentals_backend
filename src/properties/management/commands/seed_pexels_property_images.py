from django.core.management.base import BaseCommand
from django.apps import apps
from django.core.files.base import ContentFile
from django.conf import settings
from django.db import transaction
import os, random, time

try:
    import requests
except Exception:
    requests = None

CATS = ["exterior", "living", "bedroom", "kitchen", "bathroom"]

PEXELS_QUERIES = {
    "exterior":  ["house exterior germany", "modern house exterior", "home facade", "brick house exterior"],
    "living":    ["living room interior", "modern living room", "cozy living room"],
    "bedroom":   ["bedroom interior", "modern bedroom", "cozy bedroom"],
    "kitchen":   ["kitchen interior", "modern kitchen", "white kitchen"],
    "bathroom":  ["bathroom interior", "modern bathroom", "shower bathroom"],
}

def _has_field(model, name: str) -> bool:
    return any(getattr(f, "name", None) == name for f in model._meta.get_fields())

def _fk_name(PropertyImage, Property):
    for f in PropertyImage._meta.get_fields():
        if getattr(getattr(f, "remote_field", None), "model", None) == Property:
            return f.name
    return "property"

def pexels_search(q: str, per_page: int, page: int, api_key: str):
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": api_key}
    params = {"query": q, "per_page": per_page, "page": page, "orientation": "landscape"}
    r = requests.get(url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    photos = r.json().get("photos", [])
    out = []
    for ph in photos:
        src = ph.get("src", {})
        # берём самое приличное из доступных
        u = src.get("large2x") or src.get("large") or src.get("original")
        if u:
            out.append(u)
    return out

class Command(BaseCommand):
    help = "Скачивает реальные фото с Pexels и прикрепляет к Property: 2 экстерьера + 4 интерьера на объект."

    def add_arguments(self, parser):
        parser.add_argument("--per", type=int, default=6, help="Сколько фото на объект в итоге (по умолчанию 6).")
        parser.add_argument("--exteriors", type=int, default=2, help="Сколько экстерьеров на объект (по умолчанию 2).")
        parser.add_argument("--replace", action="store_true", help="Удалить текущие фото объектов и заменить новыми.")
        parser.add_argument("--make-primary", action="store_true", help="Первое фото пометить is_primary=True (если поле есть).")
        parser.add_argument("--city-in", type=str, default=None, help="Список городов через запятую (фильтр Property.city).")
        parser.add_argument("--limit", type=int, default=None, help="Ограничить число объектов.")
        parser.add_argument("--sleep", type=float, default=0.1, help="Пауза между скачиваниями (по умолчанию 0.1).")

    def handle(self, *args, **opts):
        if requests is None:
            self.stderr.write(self.style.ERROR("Нужен пакет 'requests' (pip install requests)"))
            return

        api_key = getattr(settings, "PEXELS_API_KEY", "") or os.getenv("PEXELS_API_KEY", "")
        if not api_key:
            self.stderr.write(self.style.ERROR("PEXELS_API_KEY пуст. Добавь в .env.local и перезапусти."))
            return

        per = max(1, int(opts["per"]))
        exteriors = max(0, min(per, int(opts["exteriors"])))
        replace = bool(opts["replace"])
        make_primary = bool(opts["make_primary"])
        cities_raw = opts.get("city_in")
        limit = opts.get("limit")
        sleep_s = float(opts["sleep"])

        Property = apps.get_model("properties", "Property")
        PropertyImage = apps.get_model("properties", "PropertyImage")
        fk = _fk_name(PropertyImage, Property)

        if not _has_field(PropertyImage, "image"):
            self.stderr.write(self.style.ERROR("У модели PropertyImage нет поля 'image'."))
            return

        # Собираем пул URL по категориям (по ~200 на категорию)
        self.stdout.write(self.style.HTTP_INFO("Собираю список URL с Pexels..."))
        pool = {c: [] for c in CATS}
        for cat in CATS:
            qs = PEXELS_QUERIES[cat][:]
            random.shuffle(qs)
            need = 200
            page = 1
            while need > 0 and qs:
                q = random.choice(qs)
                try:
                    batch = pexels_search(q, per_page=min(80, need), page=page, api_key=api_key)
                except Exception as e:
                    self.stderr.write(self.style.WARNING(f"[{cat}] Пропуск запроса: {e}"))
                    batch = []
                if not batch:
                    page += 1
                    if page > 5:  # не упираться бесконечно
                        qs.pop()  # меняем ключевик
                        page = 1
                    continue
                for u in batch:
                    if u not in pool[cat]:
                        pool[cat].append(u)
                need -= len(batch)
                page += 1
                time.sleep(sleep_s)

            if not pool[cat]:
                self.stderr.write(self.style.ERROR(f"Не нашли фото для категории '{cat}'."))
                return

        # Подбираем свойства
        qs = Property.objects.all().order_by("pk")
        if cities_raw and _has_field(Property, "city"):
            cities = [c.strip() for c in cities_raw.split(",") if c.strip()]
            qs = qs.filter(city__in=cities)
        if limit:
            qs = qs[: int(limit)]

        total_added = 0
        session = requests.Session()

        for prop in qs:
            # Текущее
            existing_qs = PropertyImage.objects.filter(**{fk: prop})
            if replace:
                # удаляем и файлы и записи
                for img in existing_qs:
                    try:
                        img.image.delete(save=False)
                    except Exception:
                        pass
                    img.delete()
                existing = 0
            else:
                existing = existing_qs.exclude(image="").exclude(image__isnull=True).count()

            need = max(0, per - existing)
            if need == 0:
                continue

            # Выбор URL: 2 экстерьера, остальное интерьеры
            chosen = []
            if pool["exterior"]:
                k = min(exteriors, need, len(pool["exterior"]))
                chosen += random.sample(pool["exterior"], k=k)
            interior = pool["living"] + pool["bedroom"] + pool["kitchen"] + pool["bathroom"]
            if interior and len(chosen) < need:
                k = min(need - len(chosen), len(interior))
                chosen += random.sample(interior, k=k)
            if len(chosen) < need:
                # добиваем чем есть
                rest = []
                for c in CATS:
                    rest += pool[c]
                k = min(need - len(chosen), len(rest))
                if k > 0:
                    chosen += random.sample(rest, k=k)

            added_here = 0

            with transaction.atomic():
                for idx, url in enumerate(chosen, start=1):
                    try:
                        r = session.get(url, timeout=20)
                        if r.status_code != 200:
                            continue
                        content = r.content
                    except Exception:
                        continue

                    img = PropertyImage()
                    setattr(img, fk, prop)

                    if _has_field(PropertyImage, "position"):
                        img.position = existing + idx
                    label = getattr(prop, "title", None) or f"Property {prop.pk}"
                    if _has_field(PropertyImage, "caption"):
                        img.caption = label
                    elif _has_field(PropertyImage, "alt"):
                        img.alt = label
                    if make_primary and _has_field(PropertyImage, "is_primary"):
                        img.is_primary = (existing == 0 and idx == 1)

                    # сохраняем через storage
                    fname = f"pexels_{prop.pk}_{random.randint(100000,999999)}.jpg"
                    img.image.save(fname, ContentFile(content), save=False)
                    img.save()
                    added_here += 1
                    total_added += 1
                    time.sleep(sleep_s)

            self.stdout.write(self.style.SUCCESS(f"Property #{prop.pk}: добавлено {added_here} фото (нужно было {need})."))

        self.stdout.write(self.style.SUCCESS(f"Готово. Всего добавлено: {total_added}."))
