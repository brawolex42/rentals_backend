from pathlib import Path
import random
from django.conf import settings
from django.db.models import Count
from src.properties.models import Property, PropertyImage

MIN_PER = 6  # минимум фото на объект

root = Path(settings.MEDIA_ROOT) / "properties"
paths = []
for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
    paths.extend(root.rglob(ext))

rel_paths = sorted({p.relative_to(settings.MEDIA_ROOT).as_posix() for p in paths})
existing = set(PropertyImage.objects.values_list("image", flat=True))
free_pool = [p for p in rel_paths if p not in existing]
random.shuffle(free_pool)
free_iter = iter(free_pool)

added_total = 0

for prop in Property.objects.all().order_by("id"):
    current = set(PropertyImage.objects.filter(property=prop).values_list("image", flat=True))
    need = max(0, MIN_PER - len(current))

    # Сначала берём свободные (ещё нигде не используемые) картинки
    while need > 0:
        try:
            rel = next(free_iter)
        except StopIteration:
            break
        if rel in current:
            continue
        PropertyImage.objects.create(property=prop, image=rel, alt=prop.title)
        current.add(rel)
        need -= 1
        added_total += 1

    # Если свободные кончились — переиспользуем из общего пула (без дублей внутри объекта)
    if need > 0:
        for rel in rel_paths:
            if rel in current:
                continue
            PropertyImage.objects.create(property=prop, image=rel, alt=prop.title)
            current.add(rel)
            need -= 1
            added_total += 1
            if need == 0:
                break

mn_list = list(Property.objects.annotate(n=Count("images")).values_list("n", flat=True))
mn = min(mn_list) if mn_list else 0
print("Добавлено всего фото:", added_total)
print("Объектов:", Property.objects.count())
print("Всего фото:", PropertyImage.objects.count())
print("Минимум фото на объект:", mn)
