from django.contrib import admin
from django.utils.html import format_html
from django.utils.text import slugify

from .models import Property  # прямой импорт модели — безопаснее при регистрации админки


def _detect_fields():
    fset = {f.name for f in Property._meta.fields}
    price_field = "price_per_night" if "price_per_night" in fset else ("price" if "price" in fset else None)
    image_field = "image" if "image" in fset else ("cover_image" if "cover_image" in fset else None)
    slug_field = "slug" if "slug" in fset else None
    return fset, price_field, image_field, slug_field


FSET, PRICE_FIELD, IMAGE_FIELD, SLUG_FIELD = _detect_fields()
LIST_DISPLAY = tuple(x for x in ("id", "thumb", "title", "city", PRICE_FIELD or "rooms", "rooms", "area", "is_active") if x in (FSET | {"thumb"}))


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = LIST_DISPLAY or ("id",)
    list_filter = tuple(x for x in ("city", "rooms", "is_active") if x in FSET)
    search_fields = tuple(x for x in ("title", "city", "district", "address") if x in FSET)
    actions = ["generate_demo_50", "generate_demo_200", "purge_demo"]

    readonly_fields = ("thumb_large",) if IMAGE_FIELD else ()
    if IMAGE_FIELD:
        fieldsets = (
            (None, {"fields": tuple(x for x in ("title", SLUG_FIELD, "description", PRICE_FIELD, "city", "address", "rooms", "area", "is_active") if x and x in FSET)}),
            ("Медиа", {"fields": (IMAGE_FIELD, "thumb_large")}),
        )

    def thumb(self, obj):
        if IMAGE_FIELD:
            img = getattr(obj, IMAGE_FIELD, None)
            if img:
                return format_html('<img src="{}" style="height:40px;width:60px;object-fit:cover;border-radius:6px;" />', img.url)
        return "—"
    thumb.short_description = "Фото"

    def thumb_large(self, obj):
        if IMAGE_FIELD:
            img = getattr(obj, IMAGE_FIELD, None)
            if img:
                return format_html('<img src="{}" style="height:160px;width:240px;object-fit:cover;border-radius:12px;" />', img.url)
        return "—"
    thumb_large.short_description = "Превью"

    def _make_img(self, text: str):
        # импортируем Pillow только когда реально нужно
        from io import BytesIO
        from PIL import Image, ImageDraw, ImageFont
        from django.core.files.base import ContentFile
        import random

        img = Image.new("RGB", (1280, 800), (230, 233, 239))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 46)
        except Exception:
            font = ImageFont.load_default()
        w, h = img.size
        tw, th = d.textbbox((0, 0), text, font=font)[2:]
        d.rectangle([(0, h - 120), (w, h)], fill=(20, 22, 26))
        d.text(((w - tw) // 2, h - 80), text, font=font, fill=(255, 255, 255))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=88)
        return ContentFile(buf.getvalue(), name=f"demo_{random.randint(1000,9999)}.jpg")

    def _fake(self):
        # импортируем Faker только при генерации
        from faker import Faker
        return Faker(["ru_RU", "de_DE", "en_US"])

    def _pick_fields(self):
        # читаем актуальный набор полей на момент вызова, на случай миграций
        fset = {f.name for f in Property._meta.fields}
        price_field = "price_per_night" if "price_per_night" in fset else ("price" if "price" in fset else None)
        image_field = "image" if "image" in fset else ("cover_image" if "cover_image" in fset else None)
        slug_field = "slug" if "slug" in fset else None
        return fset, price_field, image_field, slug_field

    @admin.action(description="Создать ~50 демо-объектов")
    def generate_demo_50(self, request, queryset):
        self._generate_batch(50)
        self.message_user(request, "Создано ~50 демо-объектов")

    @admin.action(description="Создать ~200 демо-объектов")
    def generate_demo_200(self, request, queryset):
        self._generate_batch(200)
        self.message_user(request, "Создано ~200 демо-объектов")

    @admin.action(description="Удалить все объекты")
    def purge_demo(self, request, queryset):
        deleted, _ = Property.objects.all().delete()
        self.message_user(request, f"Удалено {deleted} объектов")

    def _generate_batch(self, count: int):
        from django.contrib.auth import get_user_model
        from django.db import transaction
        import random

        fake = self._fake()
        fset, price_field, image_field, slug_field = self._pick_fields()

        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).first() or User.objects.first()

        cities_pool = [
            "Berlin","Hamburg","München","Köln","Frankfurt","Stuttgart","Düsseldorf","Dresden","Leipzig","Hannover",
            "Moscow","Saint Petersburg","Kazan","Sochi","Novosibirsk","Yekaterinburg","Krasnodar","Voronezh","Kaliningrad","Nizhny Novgorod",
            "London","Manchester","Bristol","Leeds","Liverpool","Edinburgh","Birmingham","Glasgow","Oxford","Cambridge"
        ]

        with transaction.atomic():
            for _ in range(count):
                city = random.choice(cities_pool)
                district = fake.city_suffix()
                address = fake.street_address()
                postal = fake.postcode()
                rooms = random.choice([1, 2, 3, 4, 5])
                area = random.choice([28, 36, 45, 52, 64, 72, 85, 98, 120])
                price = random.choice([45, 69, 79, 99, 120, 150, 180])  # €/ночь
                home_type = random.choice(["apartment", "house", "studio", "room"])

                title = f"{city}: {rooms} комн., {area} м²"
                desc = f"{address}, {postal} {city}. {rooms} комн., {area} м²."

                data = {}
                if "title" in fset: data["title"] = title
                if "name" in fset and "title" not in fset: data["name"] = title
                if "description" in fset: data["description"] = desc
                if "city" in fset: data["city"] = city
                if "district" in fset: data["district"] = district
                if "address" in fset: data["address"] = address
                if "postal_code" in fset: data["postal_code"] = postal
                if price_field and price_field in fset: data[price_field] = price
                if "rooms" in fset: data["rooms"] = rooms
                if "area" in fset: data["area"] = area
                if "home_type" in fset: data["home_type"] = home_type
                if "is_active" in fset: data["is_active"] = True
                if "address_line" in fset and "address" not in fset: data["address_line"] = address
                if "owner" in fset and owner: data["owner"] = owner
                if slug_field and slug_field in fset:
                    data[slug_field] = slugify(f"{title}-{fake.unique.bothify(text='??##')}")

                obj = Property.objects.create(**data)

                if image_field and image_field in fset:
                    img = self._make_img(f"{city} • {rooms} • {area} м²")
                    getattr(obj, image_field).save(img.name, img, save=True)
