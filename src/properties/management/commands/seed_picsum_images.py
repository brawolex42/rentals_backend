# properties/management/commands/seed_picsum_images.py
import random
import string
from datetime import datetime

from django.core.management.base import BaseCommand
from django.apps import apps
from django.core.files.base import ContentFile
from django.db import transaction

import requests

SIZE_W, SIZE_H = 1280, 853

GERMAN_CITIES = [
    "Berlin", "Hamburg", "München", "Köln", "Frankfurt am Main", "Stuttgart",
    "Düsseldorf", "Dortmund", "Essen", "Leipzig", "Bremen", "Dresden",
    "Hannover", "Nürnberg", "Duisburg", "Bochum", "Wuppertal", "Bielefeld",
    "Bonn", "Münster", "Karlsruhe", "Mannheim", "Augsburg", "Wiesbaden",
    "Gelsenkirchen", "Mönchengladbach", "Braunschweig", "Chemnitz",
]

def _has_field(model, name: str) -> bool:
    return any(getattr(f, "name", None) == name for f in model._meta.get_fields())

def rand_seed(n=8):
    letters = string.ascii_letters + string.digits
    return "".join(random.choice(letters) for _ in range(n))

def fetch_image_bytes(seed: str) -> bytes:
    # Picsum стабилен по seed, без API ключа
    url = f"https://picsum.photos/seed/{seed}/{SIZE_W}/{SIZE_H}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.content

class Command(BaseCommand):
    help = "Качает фото с Picsum и прикрепляет к Property. Докачивает до N фото на объект. Безопасно подстраивается под поля PropertyImage."

    def add_arguments(self, parser):
        parser.add_argument("--per", type=int, default=6, help="Сколько фото должно быть на объекте в итоге (по умолчанию 6).")
        parser.add_argument("--only-empty", action="store_true", help="Обрабатывать только те объекты, у которых сейчас 0 фото.")
        parser.add_argument("--clear-existing", action="store_true", help="Сначала удалить все PropertyImage (осторожно!).")
        parser.add_argument("--limit", type=int, default=None, help="Ограничить кол-во объектов.")
        parser.add_argument("--cities-only-de", action="store_true", help="Фильтровать по городам Германии из списка.")
        parser.add_argument("--ids", type=str, default=None, help="Обработать только перечисленные PK (через запятую).")
        parser.add_argument("--make-primary", action="store_true", help="Если есть поле is_primary — пометить первое фото как главное.")
        parser.add_argument("--owner", type=str, default=None, help="Если у PropertyImage есть owner/created_by/user — проставить этого пользователя (username).")

    def handle(self, *args, **opts):
        per = max(1, int(opts["per"]))
        only_empty = bool(opts["only_empty"])
        clear_existing = bool(opts["clear_existing"])
        limit = opts.get("limit")
        de_filter = bool(opts["cities_only_de"])
        ids_raw = opts.get("ids")
        make_primary = bool(opts["make_primary"])
        owner_username = opts.get("owner")

        Property = apps.get_model("properties", "Property")
        PropertyImage = apps.get_model("properties", "PropertyImage")

        img_field_exists = _has_field(PropertyImage, "image")
        if not img_field_exists:
            self.stderr.write(self.style.ERROR("В PropertyImage нет поля 'image'. Останов."))
            return

        # подготовим owner (если надо)
        owner_user = None
        if owner_username:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                owner_user = User.objects.get(**{User.USERNAME_FIELD: owner_username})
            except User.DoesNotExist:
                self.stderr.write(self.style.WARNING(f"Пользователь '{owner_username}' не найден. Пропускаю установку владельца."))

        if clear_existing:
            deleted = PropertyImage.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Удалены все изображения: {deleted}"))

        qs = Property.objects.all().order_by("id")
        if de_filter and _has_field(Property, "city"):
            qs = qs.filter(city__in=GERMAN_CITIES)
        if ids_raw:
            ids_list = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]
            qs = qs.filter(pk__in=ids_list)
        if limit:
            qs = qs[: int(limit)]

        created_total = 0

        for p in qs:
            # сколько уже есть валидных изображений
            existing_qs = PropertyImage.objects.filter(property=p)
            existing_count = existing_qs.exclude(image="").exclude(image__isnull=True).count()

            if only_empty and existing_count > 0:
                continue

            need = max(0, per - existing_count)
            if need == 0:
                continue

            self.stdout.write(f"Property #{p.pk}: есть {existing_count}, нужно добавить {need}.")

            # базовые значения для полей PropertyImage
            common_kwargs = {}
            if _has_field(PropertyImage, "address_line") and _has_field(Property, "address"):
                addr = getattr(p, "address", None)
                if addr:
                    common_kwargs["address_line"] = addr

            if owner_user:
                for owner_like in ("owner", "created_by", "user"):
                    if _has_field(PropertyImage, owner_like):
                        common_kwargs[owner_like] = owner_user

            # если есть caption/alt — установим из заголовка
            label_text = getattr(p, "title", None) or f"Property {p.pk}"

            with transaction.atomic():
                for idx in range(need):
                    seed = f"{p.pk}-{rand_seed(6)}"
                    try:
                        content = fetch_image_bytes(seed)
                    except Exception as e:
                        self.stderr.write(self.style.WARNING(f"[ERR] seed={seed}: {e}"))
                        continue

                    img_obj = PropertyImage(property=p, **common_kwargs)

                    # позиция
                    if _has_field(PropertyImage, "position"):
                        img_obj.position = existing_count + idx + 1

                    # подпись/alt, если поле есть
                    if _has_field(PropertyImage, "caption"):
                        img_obj.caption = label_text
                    elif _has_field(PropertyImage, "alt"):
                        img_obj.alt = label_text

                    # главное фото
                    if make_primary and _has_field(PropertyImage, "is_primary"):
                        img_obj.is_primary = (existing_count == 0 and idx == 0)

                    # сохраняем через storage, имя — от даты/seed
                    today = datetime.now()
                    filename = f"{today:%Y/%m/%d}/ext_{p.pk}_{rand_seed(6)}.jpg"
                    img_obj.image.save(filename, ContentFile(content), save=False)

                    img_obj.save()
                    created_total += 1

            self.stdout.write(self.style.SUCCESS(f"Property #{p.pk}: добавлено {need} фото."))

        self.stdout.write(self.style.SUCCESS(f"Готово. Всего добавлено изображений: {created_total}."))
