import random
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from src.properties.models import Property, PropertyImage

COUNT = 50

GER_CITIES = ["Berlin","München","Hamburg","Köln","Frankfurt am Main","Stuttgart","Düsseldorf","Leipzig","Dortmund","Essen","Bremen","Dresden","Hannover","Nürnberg","Bochum","Wuppertal","Bielefeld","Bonn","Münster","Karlsruhe","Mannheim","Augsburg","Wiesbaden","Gelsenkirchen"]
TITLES = ["Einfamilienhaus","Reihenhaus","Modernes Haus","Charmantes Haus"]

User = get_user_model()
owner = (User.objects.filter(email="sakilev.aleksandr@gmail.com").first()
         or User.objects.filter(is_superuser=True).first()
         or User.objects.first())

try:
    from src.shared.enums import PropertyType
    PT_CHOICES = [c[0] for c in getattr(PropertyType, "choices", [])] or ["HOUSE","APARTMENT"]
except Exception:
    PT_CHOICES = ["HOUSE","APARTMENT"]

media_root = Path(settings.MEDIA_ROOT)
all_imgs = []
for ext in ("*.jpg","*.jpeg","*.JPG","*.JPEG","*.png","*.webp","*.PNG","*.WEBP"):
    all_imgs += list((media_root / "properties").rglob(ext))

rel_imgs = [p.relative_to(media_root).as_posix() for p in all_imgs]
if not rel_imgs or len(rel_imgs) < COUNT * 2:
    raise SystemExit("Недостаточно файлов в media/properties")

already = set(PropertyImage.objects.values_list("image", flat=True))
pool = [r for r in rel_imgs if r not in already] or rel_imgs[:]
random.shuffle(pool)
used = set()

created = 0
attached = 0

for _ in range(COUNT):
    city = random.choice(GER_CITIES)
    p = Property.objects.create(
        owner=owner,
        title=f"{random.choice(TITLES)} in {city}",
        description=f"Gemütliches Wohnhaus in {city}.",
        city=city,
        district="",
        price=random.randint(900, 3500),
        rooms=random.randint(2, 6),
        property_type=("HOUSE" if "HOUSE" in PT_CHOICES else random.choice(PT_CHOICES)),
        is_active=True,
    )
    created += 1

    want = random.choice([2, 3])
    taken = 0

    while pool and taken < want:
        rel = pool.pop()
        if rel in used:
            continue
        PropertyImage.objects.create(property=p, image=rel, alt=p.title)
        used.add(rel)
        attached += 1
        taken += 1

    j = 0
    while taken < want and j < len(rel_imgs):
        rel = rel_imgs[j]; j += 1
        PropertyImage.objects.create(property=p, image=rel, alt=p.title)
        attached += 1
        taken += 1

print(f"Создано домов: {created}; привязано фото: {attached}")
