import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.html import strip_tags
from src.properties.models import Property

def ru_rooms_phrase(n):
    try:
        r = int(n)
    except Exception:
        return "квартира"
    if r <= 0:
        return "студия"
    return f"{r}\u2011комнатная квартира"

def de_rooms_phrase(n):
    try:
        r = int(n)
    except Exception:
        return "Wohnung"
    if r <= 0:
        return "Studio"
    return f"{r}\u2011Zimmer\u2011Wohnung"

def en_rooms_phrase(n):
    try:
        r = int(n)
    except Exception:
        return "apartment"
    if r <= 0:
        return "studio"
    return f"{r}-room apartment"

def gen_desc(lang, city, rooms, area):
    city = city or ""
    try:
        a = int(area) if area else None
    except Exception:
        a = None
    if lang == "de":
        parts = []
        parts.append(f"Helle {de_rooms_phrase(rooms)} in {city}.".strip())
        if a:
            parts.append(f"Fläche {a} m².")
        parts.append("Moderne Ausstattung, gute Aufteilung, gepflegtes Haus.")
        parts.append("Einkaufsmöglichkeiten und ÖPNV in der Nähe. Ideal für langfristige Miete.")
        return " ".join(parts)
    if lang == "en":
        parts = []
        parts.append(f"Bright {en_rooms_phrase(rooms)} in {city}.".strip())
        if a:
            parts.append(f"Total area {a} m².")
        parts.append("Modern finishes, functional layout, well-kept building.")
        parts.append("Shops and public transport nearby. Suitable for long-term rent.")
        return " ".join(parts)
    parts = []
    parts.append(f"Светлая {ru_rooms_phrase(rooms)} в {city}.".strip())
    if a:
        parts.append(f"Площадь {a} м².")
    parts.append("Современный ремонт, удобная планировка, ухоженный дом.")
    parts.append("Рядом магазины и транспорт. Подходит для долгосрочной аренды.")
    return " ".join(parts)

def looks_bad(text):
    if not text:
        return True
    t = strip_tags(text).strip()
    if len(t) < 50:
        return True
    junk = ["каюта", "багров", "пасть", "костер", "изба", "вздрог", "соответств", "инструкция бабочка"]
    low = t.lower()
    if any(w in low for w in junk):
        return True
    return False

class Command(BaseCommand):
    help = "Sanitize property titles/descriptions/district."

    def add_arguments(self, parser):
        parser.add_argument("--lang", type=str, default="ru", choices=["ru","de","en"])
        parser.add_argument("--reset-titles", action="store_true")
        parser.add_argument("--replace-all", action="store_true")
        parser.add_argument("--min-district-len", type=int, default=3)
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        lang = opts["lang"]
        reset_titles = bool(opts["reset_titles"])
        replace_all = bool(opts["replace_all"])
        min_dl = int(opts["min_district_len"])
        limit = opts.get("limit")
        dry = bool(opts["dry_run"])

        qs = Property.objects.all().order_by("id")
        if limit:
            qs = qs[:limit]

        changed = 0
        for p in qs:
            title_old = p.title or ""
            desc_old = p.description or ""
            city = (p.city or "").strip()
            district = (p.district or "").strip()
            rooms = getattr(p, "rooms", None)
            area = getattr(p, "area", None)

            updates = {}

            if district and len(district) < min_dl:
                updates["district"] = ""

            if reset_titles:
                if rooms and str(rooms).isdigit():
                    if lang == "de":
                        new_title = f"{city}: {rooms}\u00A0Zi."
                    elif lang == "en":
                        new_title = f"{city}: {rooms}-room"
                    else:
                        new_title = f"{city}: {rooms}\u00A0комн."
                else:
                    if lang == "de":
                        new_title = f"{city}: Wohnung"
                    elif lang == "en":
                        new_title = f"{city}: Apartment"
                    else:
                        new_title = f"{city}: квартира"
                if new_title != title_old:
                    updates["title"] = new_title

            need_desc = replace_all or looks_bad(desc_old)
            if need_desc:
                new_desc = gen_desc(lang, city, rooms, area)
                if new_desc != desc_old:
                    updates["description"] = new_desc

            if updates:
                changed += 1
                if not dry:
                    for k,v in updates.items():
                        setattr(p, k, v)
                    p.save(update_fields=list(updates.keys()))

        self.stdout.write(f"Updated objects: {changed}")
