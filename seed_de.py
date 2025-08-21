# seed_de.py
import os
import random
import itertools
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from src.properties.models import Property, PropertyImage  # noqa: E402

try:
    from src.shared.enums import PropertyType  # noqa: E402
    PT_CHOICES = [c[0] for c in getattr(PropertyType, "choices", [])] or ["APARTMENT", "HOUSE"]
except Exception:
    PT_CHOICES = ["APARTMENT", "HOUSE"]


def main():
    User = get_user_model()
    owner = (
        User.objects.filter(email="sakilev.aleksandr@gmail.com").first()
        or User.objects.filter(is_superuser=True).first()
    )
    if not owner:
        raise SystemExit("Нет пользователя-владельца (ни суперюзера, ни указанного email).")

    root = Path(settings.MEDIA_ROOT) / "properties"
    paths = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        paths += list(root.rglob(ext))
    rel_paths = sorted({p.relative_to(settings.MEDIA_ROOT).as_posix() for p in paths})
    random.shuffle(rel_paths)
    print("Найдено файлов изображений:", len(rel_paths))

    GER_CITIES = [
        "Berlin", "München", "Hamburg", "Köln", "Frankfurt am Main", "Stuttgart", "Düsseldorf", "Leipzig",
        "Dortmund", "Essen", "Bremen", "Dresden", "Hannover", "Nürnberg", "Duisburg", "Bochum", "Wuppertal",
        "Bielefeld", "Bonn", "Münster", "Karlsruhe", "Mannheim", "Augsburg", "Wiesbaden", "Gelsenkirchen",
    ]

    TARGET = 70
    existing = list(Property.objects.all())
    need = max(0, TARGET - len(existing))
    print("Существующих объектов:", len(existing), "| нужно создать:", need)

    TITLES = ["Elegantes Apartment", "Charmantes Haus", "Loft", "Ruhiges Reihenhaus", "Helles Familienhaus"]

    for _ in range(need):
        city = random.choice(GER_CITIES)
        rooms = random.randint(1, 5)
        price = float(random.randint(450, 2400))
        p = Property.objects.create(
            owner=owner,
            title=f"{random.choice(TITLES)} in {city}",
            description=f"Gemütliche Unterkunft in {city}.",
            city=city,
            district="",
            price=price,
            rooms=rooms,
            property_type=random.choice(PT_CHOICES),
            is_active=True,
        )
        existing.append(p)

    used = set(PropertyImage.objects.values_list("image", flat=True))
    attached = 0
    img_iter = itertools.cycle(rel_paths) if rel_paths else iter(())

    for p in existing:
        current = set(PropertyImage.objects.filter(property=p).values_list("image", flat=True))
        want = 3 if len(current) == 0 else (2 if len(current) == 1 else len(current))
        want = max(2, min(3, want))
        while len(current) < want and rel_paths:
            candidate = next(img_iter)
            if candidate in used:
                continue
            PropertyImage.objects.create(property=p, image=candidate, alt=p.title)
            current.add(candidate)
            used.add(candidate)
            attached += 1

    print(
        "Готово. Всего объектов:",
        Property.objects.count(),
        "| Всего изображений:",
        PropertyImage.objects.count(),
        "| Новых привязок:",
        attached,
    )


if __name__ == "__main__":
    main()

