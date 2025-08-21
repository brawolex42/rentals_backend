# refresh_images_germany.py
import os, random, time
from datetime import datetime
from pathlib import Path

import requests
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.conf import settings
from src.properties.models import Property, PropertyImage

API_KEY = os.getenv("PEXELS_API_KEY") or ""
if not API_KEY:
    raise SystemExit("PEXELS_API_KEY не задан в .env")

ALLOWED = [
    "wohnung","apartment","haus","wohnhaus","reihenhaus","mehrfamilienhaus",
    "innenraum","interior","wohnzimmer","schlafzimmer","küche","kueche","badezimmer","bad",
    "esszimmer","flur","diele","balkon","terrasse",
    "apartment interior","living room","bedroom","kitchen","bathroom"
]
BANNED = [
    "schloss","burg","castle","palast","palace","kloster","kirche","church","kathedrale","moschee",
    "hotel","resort","hostel",
    "büro","buero","office","fabrik","factory","lager","warehouse","schule","school","universität","universitaet",
    "museum","denkmal","brücke","bruecke","bridge","park","strand","beach","meer","see","lake","gebirge","berge","wald","forest",
    "hütte","huette","cabin","cottage","stadion","arena","tempel","pagode"
]

INTERIOR_QUERIES = [
    "Innenraum Wohnung Deutschland",
    "Wohnzimmer Wohnung Deutschland",
    "Schlafzimmer Wohnung Deutschland",
    "Küche Wohnung Deutschland",
    "Badezimmer Wohnung Deutschland",
    "Altbauwohnung Innenraum",
    "Neubauwohnung Innenraum",
    "Reihenhaus Innenraum Deutschland",
    "Mehrfamilienhaus Innenraum Deutschland",
]
EXTERIOR_QUERIES = [
    "Fassade Wohnhaus Deutschland",
    "Mehrfamilienhaus Fassade Deutschland",
    "Reihenhaus Deutschland Außenansicht",
    "Einfamilienhaus Deutschland Außenansicht",
    "Wohnblock Deutschland Fassade",
]

def ok_alt(alt: str, strict: bool = True) -> bool:
    s = (alt or "").lower()
    if any(b in s for b in BANNED):
        return False
    if not strict:
        return True
    return any(a in s for a in ALLOWED)

def fetch_set(headers, queries, need, orientation="landscape", strict=True):
    saved = []
    seen_ids = set()
    today = datetime.now()
    base_dir = Path(settings.MEDIA_ROOT) / "properties" / today.strftime("%Y") / today.strftime("%m") / today.strftime("%d")
    base_dir.mkdir(parents=True, exist_ok=True)

    for q in queries:
        for page in range(1, 5):
            if len(saved) >= need:
                break
            r = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params={
                    "query": q,
                    "per_page": 80,
                    "page": page,
                    "orientation": orientation,
                    "locale": "de-DE",
                },
                timeout=30,
            )
            if r.status_code != 200:
                break
            photos = (r.json() or {}).get("photos") or []
            if not photos:
                break
            for ph in photos:
                pid = ph.get("id")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                alt = ph.get("alt") or ""
                if not ok_alt(alt, strict=strict):
                    continue
                w, h = ph.get("width") or 0, ph.get("height") or 0
                if min(w, h) < 900:
                    continue
                src = (ph.get("src") or {}).get("large2x") or (ph.get("src") or {}).get("large")
                if not src:
                    continue
                try:
                    img = requests.get(src, timeout=30)
                    if img.status_code != 200:
                        continue
                    fn = f"pexels_{pid}_{random.randint(1000,9999)}.jpg"
                    path = base_dir / fn
                    path.write_bytes(img.content)
                    saved.append(path.relative_to(settings.MEDIA_ROOT).as_posix())
                except Exception:
                    continue
            time.sleep(0.2)
        if len(saved) >= need:
            break
    return saved

def main():
    props = list(Property.objects.all().order_by("id"))
    if not props:
        raise SystemExit("Нет объектов Property")

    # очистим привязки у всех, файлы НЕ трогаем (чтобы не бить свежескачанное при повторном запуске)
    for p in props:
        for pi in list(p.images.all()):
            try:
                pi.delete()
            except Exception:
                pass

    headers = {"Authorization": API_KEY}
    need_total = len(props) * 3 + 60

    inter = fetch_set(headers, INTERIOR_QUERIES, need_total, "landscape", strict=True)
    if len(inter) < need_total // 2:
        inter += fetch_set(headers, INTERIOR_QUERIES, need_total - len(inter), "landscape", strict=False)

    exter = fetch_set(headers, EXTERIOR_QUERIES, max(len(props), 60), "landscape", strict=True)

    pool = inter + exter
    random.shuffle(pool)
    used = set()
    attached = 0

    for p in props:
        want = random.choice([2, 3])
        taken = 0
        # стараемся дать 1 экстерьер + 1–2 интерьер
        bucket = []
        for rel in pool:
            if rel in used:
                continue
            if "Innen" in rel or "innen" in rel:
                bucket.append(rel)
        # fallback: берём любые
        for rel in pool:
            if rel in used:
                continue
            if rel not in bucket:
                bucket.append(rel)

        for rel in bucket:
            if rel in used:
                continue
            PropertyImage.objects.create(property=p, image=rel, alt=p.title)
            used.add(rel)
            attached += 1
            taken += 1
            if taken >= want:
                break

    print("Объектов:", len(props), "| Привязано фото:", attached, "| Всего скачано:", len(pool))

if __name__ == "__main__":
    main()
