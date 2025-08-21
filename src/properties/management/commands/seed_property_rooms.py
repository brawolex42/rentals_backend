from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from django.contrib.auth import get_user_model
import random

# ---- утилиты introspection ----
def _get_model_or_none(app_label: str, model_name: str):
    try:
        return apps.get_model(app_label, model_name)
    except Exception:
        return None

def _has_field(model, name: str) -> bool:
    return any(getattr(f, "name", None) == name for f in model._meta.get_fields())

def _get_field(model, name: str):
    try:
        return model._meta.get_field(name)
    except Exception:
        return None

def _set_if_exists(obj, **kwargs):
    for k, v in kwargs.items():
        if v is None:
            continue
        if _has_field(obj.__class__, k):
            setattr(obj, k, v)

def _find_fk_to(model_child, model_parent):
    """
    Возвращает имя FK из model_child -> model_parent (напр., 'property').
    """
    for f in model_child._meta.get_fields():
        rel = getattr(f, "remote_field", None)
        if getattr(rel, "model", None) == model_parent:
            return f.name
    return None

def _set_choice_field(obj, field_name: str, desired_values: list[str]):
    """
    Аккуратно проставляет значение для поля с choices.
    desired_values — список предпочтений по порядку.
    """
    if not _has_field(obj.__class__, field_name):
        return
    f = _get_field(obj.__class__, field_name)
    if not f:
        return
    choices = getattr(f, "choices", None)
    if not choices:
        # обычное текстовое поле
        setattr(obj, field_name, desired_values[0])
        return
    keys = [c[0] for c in choices]
    # 1) прямое совпадение
    for d in desired_values:
        if d in keys:
            setattr(obj, field_name, d)
            return
    # 2) без регистра
    lower_map = {str(k).lower(): k for k in keys}
    for d in desired_values:
        lk = lower_map.get(str(d).lower())
        if lk is not None:
            setattr(obj, field_name, lk)
            return
    # 3) fallback — первый ключ
    if keys:
        setattr(obj, field_name, keys[0])

# ---- генерация набора комнат ----
ROOM_CATALOG = [
    # (room_type, display_name, default_beds, min_area, max_area)
    ("bedroom",       "Schlafzimmer",   1, 10, 18),
    ("living",        "Wohnzimmer",     0, 14, 28),
    ("kitchen",       "Küche",          0,  8, 14),
    ("bathroom",      "Badezimmer",     0,  4,  8),
    ("office",        "Arbeitszimmer",  0,  8, 14),
    ("kids",          "Kinderzimmer",   1,  9, 14),
    ("guest",         "Gästezimmer",    1,  9, 14),
]

def _mk_rooms_plan(total_rooms: int | None, bedrooms_hint: int | None):
    """
    Возвращает список спецификаций для создания комнат.
    Если total_rooms/bedrooms_hint неизвестно — делаем реалистично: 2-5 комнат.
    """
    if total_rooms is None:
        total_rooms = random.randint(2, 5)
    if bedrooms_hint is None:
        bedrooms_hint = min(max(1, total_rooms - 2), 3)

    plan = []
    # 1) спальни
    for _ in range(max(1, bedrooms_hint)):
        plan.append(("bedroom", "Schlafzimmer", random.choice([1, 1, 2])))
    # 2) гостиная
    plan.append(("living", "Wohnzimmer", 0))
    # 3) кухня
    plan.append(("kitchen", "Küche", 0))
    # 4) добиваем до total_rooms случайными
    TYPES = [("bathroom", "Badezimmer", 0), ("office", "Arbeitszimmer", 0),
             ("kids", "Kinderzimmer", 1), ("guest", "Gästezimmer", 1)]
    while len(plan) < total_rooms:
        plan.append(random.choice(TYPES))
    return plan[:total_rooms]

# ---- команда ----
class Command(BaseCommand):
    help = "Создаёт связанные комнаты для объектов Property. Поддерживает фильтры и only-empty."

    def add_arguments(self, parser):
        parser.add_argument("--country", type=str, default="Germany", help="Фильтр по стране (по умолчанию Germany).")
        parser.add_argument("--only-empty", action="store_true", help="Создавать комнаты только там, где их ещё нет.")
        parser.add_argument("--ids", type=str, default=None, help="Список PK через запятую.")
        parser.add_argument("--min", dest="min_id", type=int, default=None, help="Мин. PK.")
        parser.add_argument("--max", dest="max_id", type=int, default=None, help="Макс. PK.")
        parser.add_argument("--per", type=int, default=None, help="Жёстко задать количество комнат на объект.")
        parser.add_argument("--bedrooms", type=int, default=None, help="Подсказка: сколько спален создавать.")
        parser.add_argument("--owner", type=str, default=None, help="Если у Room есть владелец — проставим owner/created_by/user.")

    def handle(self, *args, **opts):
        # модели
        Property = _get_model_or_none("properties", "Property")
        Room = _get_model_or_none("properties", "Room") or _get_model_or_none("properties", "PropertyRoom")
        if not Property:
            self.stderr.write(self.style.ERROR("Не найдена модель properties.Property"))
            return
        if not Room:
            self.stderr.write(self.style.ERROR(
                "Не найдена модель комнат (properties.Room / properties.PropertyRoom). "
                "Пришли код модели комнаты — подгоню команду в ноль."
            ))
            return

        fk_room_to_property = _find_fk_to(Room, Property)
        if not fk_room_to_property:
            self.stderr.write(self.style.ERROR("Не удалось найти ForeignKey из Room к Property."))
            return

        # фильтруем объекты
        qs = Property.objects.all().order_by("pk")
        country = opts.get("country")
        if country and _has_field(Property, "country"):
            qs = qs.filter(country=country)
        if opts.get("min_id") is not None:
            qs = qs.filter(pk__gte=int(opts["min_id"]))
        if opts.get("max_id") is not None:
            qs = qs.filter(pk__lte=int(opts["max_id"]))
        if opts.get("ids"):
            ids_list = [int(x) for x in opts["ids"].split(",") if x.strip().isdigit()]
            qs = qs.filter(pk__in=ids_list)

        # flags
        only_empty = bool(opts.get("only_empty"))
        per = opts.get("per")
        per = int(per) if per is not None else None
        bedrooms_hint = opts.get("bedrooms")
        bedrooms_hint = int(bedrooms_hint) if bedrooms_hint is not None else None

        # владелец для комнаты (если поля есть)
        room_owner = None
        if opts.get("owner"):
            User = get_user_model()
            try:
                room_owner = User.objects.get(**{User.USERNAME_FIELD: opts["owner"]})
            except User.DoesNotExist:
                room_owner = None

        created_total = 0
        for prop in qs:
            # пропустим, если only_empty и комнаты уже есть
            existing = Room.objects.filter(**{fk_room_to_property: prop}).count()
            if only_empty and existing > 0:
                continue

            # числа из Property при наличии
            total_rooms = None
            if _has_field(Property, "rooms"):
                try:
                    total_rooms = int(getattr(prop, "rooms") or 0) or None
                except Exception:
                    total_rooms = None
            prop_bedrooms = None
            if _has_field(Property, "bedrooms"):
                try:
                    prop_bedrooms = int(getattr(prop, "bedrooms") or 0) or None
                except Exception:
                    prop_bedrooms = None

            if per is not None:
                total_rooms = per
            if bedrooms_hint is None:
                bedrooms_hint = prop_bedrooms

            plan = _mk_rooms_plan(total_rooms, bedrooms_hint)
            position_base = existing

            created_here = 0
            for idx, (rtype, display_name, beds) in enumerate(plan, start=1):
                sid = transaction.savepoint()
                try:
                    room = Room()

                    setattr(room, fk_room_to_property, prop)

                    # Имена/заголовки
                    if _has_field(Room, "name"):
                        room.name = display_name
                    elif _has_field(Room, "title"):
                        room.title = display_name
                    elif _has_field(Room, "label"):
                        room.label = display_name


                    _set_choice_field(room, "room_type", [rtype, display_name, rtype.upper()])


                    if _has_field(Room, "beds"):
                        room.beds = int(beds)

                    # Площадь (м²)
                    if _has_field(Room, "area"):
                        min_a, max_a = 8, 28
                        # подправим для типов
                        for t, _, _, amin, amax in ROOM_CATALOG:
                            if t == rtype:
                                min_a, max_a = amin, amax
                                break
                        room.area = random.randint(min_a, max_a)

                    # Этаж (если есть)
                    if _has_field(Room, "floor"):
                        room.floor = 0

                    # Позиция/порядок
                    if _has_field(Room, "position"):
                        room.position = position_base + idx

                    # Прочие булевые, если вдруг есть
                    if _has_field(Room, "ensuite") and rtype in ("bedroom", "guest"):
                        room.ensuite = random.choice([False, False, True])
                    if _has_field(Room, "has_window"):
                        room.has_window = True
                    if _has_field(Room, "is_primary"):
                        room.is_primary = (rtype in ("living", "kitchen")) and (idx == 1)

                    # Описание
                    if _has_field(Room, "description"):
                        room.description = f"{display_name} innerhalb der Wohnung/Haus."

                    # Владельцы / создатели
                    if room_owner:
                        _set_if_exists(room, owner=room_owner, created_by=room_owner, user=room_owner)
                    else:
                        # если нет явного owner — попробуем взять у Property
                        owner_like = None
                        for attr in ("owner", "host", "created_by", "user"):
                            if hasattr(prop, attr):
                                owner_like = getattr(prop, attr)
                                if owner_like:
                                    break
                        if owner_like:
                            _set_if_exists(room, owner=owner_like, created_by=owner_like, user=owner_like)

                    room.save()
                    transaction.savepoint_commit(sid)
                    created_here += 1
                    created_total += 1
                except Exception as e:
                    transaction.savepoint_rollback(sid)
                    self.stderr.write(self.style.WARNING(f"Property #{prop.pk}: пропущена комната ({rtype}) — {e}"))

            self.stdout.write(self.style.SUCCESS(
                f"Property #{prop.pk}: создано комнат {created_here} (ранее было {existing})."
            ))

        self.stdout.write(self.style.SUCCESS(f"Готово. Всего создано комнат: {created_total}."))
