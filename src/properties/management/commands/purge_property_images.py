# properties/management/commands/purge_property_images.py
from django.core.management.base import BaseCommand
from django.apps import apps
from django.core.files.storage import default_storage
from django.db import transaction
from pathlib import Path

def _has_field(model, name: str) -> bool:
    return any(getattr(f, "name", None) == name for f in model._meta.get_fields())

def _fk_name_to_property(PropertyImage, Property):
    for f in PropertyImage._meta.get_fields():
        rel = getattr(f, "remote_field", None)
        if getattr(rel, "model", None) == Property:
            return f.name
    return "property"

class Command(BaseCommand):
    help = "Удаляет изображения PropertyImage и связанные файлы. По умолчанию чистит только пустые/битые. Есть режим удаления всего."

    def add_arguments(self, parser):
        g = parser
        g.add_argument("--all", action="store_true",
                       help="Удалить ВСЕ изображения для выбранных объектов.")
        g.add_argument("--empties", action="store_true",
                       help="Удалить только пустые/битые записи (по умолчанию, если --all не указан).")
        g.add_argument("--name-contains", type=str, default=None,
                       help="Ограничить удаление файлами, чье имя содержит подстроку (например, 'ext_').")
        g.add_argument("--ids", type=str, default=None,
                       help="Ограничить по PK объектов Property (через запятую).")
        g.add_argument("--city-in", type=str, default=None,
                       help="Фильтр Property.city по списку городов (через запятую).")
        g.add_argument("--dry-run", action="store_true",
                       help="Только показать, что будет удалено, без изменений.")
        g.add_argument("--force", action="store_true",
                       help="Подтверждение на удаление без вопросов.")

    def handle(self, *args, **opts):
        dry = bool(opts["dry_run"])
        do_all = bool(opts["all"])
        empties = bool(opts["empties"]) or not do_all
        name_contains = opts.get("name_contains")
        ids_raw = opts.get("ids")
        cities_raw = opts.get("city_in")
        force = bool(opts["force"])

        Property = apps.get_model("properties", "Property")
        PropertyImage = apps.get_model("properties", "PropertyImage")
        fk = _fk_name_to_property(PropertyImage, Property)

        qs_prop = Property.objects.all()
        if ids_raw:
            ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]
            qs_prop = qs_prop.filter(pk__in=ids)
        if cities_raw and _has_field(Property, "city"):
            cities = [c.strip() for c in cities_raw.split(",") if c.strip()]
            qs_prop = qs_prop.filter(city__in=cities)

        prop_ids = list(qs_prop.values_list("pk", flat=True))
        if not prop_ids:
            self.stdout.write(self.style.WARNING("Нет объектов Property под заданные фильтры — удалять нечего."))
            return

        qs = PropertyImage.objects.filter(**{f"{fk}__in": prop_ids})

        # Фильтр пустых/битых
        to_delete = []
        if empties and not do_all:
            # явные пустые
            for img in qs.filter(image__isnull=True):
                to_delete.append(img)
            for img in qs.filter(image=""):
                to_delete.append(img)
            # битые файлы
            for img in qs.exclude(pk__in=[i.pk for i in to_delete]):
                try:
                    if not img.image or not img.image.name or not default_storage.exists(img.image.name):
                        to_delete.append(img)
                except Exception:
                    to_delete.append(img)
        else:
            to_delete = list(qs)

        # Доп. фильтр по имени
        if name_contains:
            substr = name_contains.lower()
            to_delete = [i for i in to_delete if getattr(i.image, "name", "") and substr in i.image.name.lower()]

        # dry-run
        self.stdout.write(self.style.HTTP_INFO(
            f"Найдено записей к удалению: {len(to_delete)} (из PropertyImage по {len(prop_ids)} объектам)."
        ))
        if dry:
            for i, img in enumerate(to_delete[:20], 1):
                self.stdout.write(f"  {i:02d}) id={img.pk}  file={getattr(img.image, 'name', '')}")
            if len(to_delete) > 20:
                self.stdout.write(f"  ... и ещё {len(to_delete)-20}")
            return

        if not force:
            self.stderr.write(self.style.ERROR("Добавь --force для подтверждения удаления."))
            return

        deleted_db = 0
        deleted_files = 0
        with transaction.atomic():
            for img in to_delete:
                # удаляем файл в storage (если есть)
                try:
                    name = getattr(img.image, "name", None)
                    if name and default_storage.exists(name):
                        img.image.delete(save=False)  # удалит файл
                        deleted_files += 1
                except Exception:
                    pass
                # удаляем запись в БД
                img.delete()
                deleted_db += 1

        self.stdout.write(self.style.SUCCESS(
            f"Удалено записей: {deleted_db}. Удалено файлов: {deleted_files}."
        ))
