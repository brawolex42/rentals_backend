# Rentals Backend (Django + DRF + MySQL)

Бэкенд для системы аренды жилья: объявления, поиск/фильтрация/сортировка, бронирования с подтверждением, отзывы, популярные поиски.

## Быстрый старт (локально)
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
# source .venv/bin/activate

pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

JWT:
- POST /api/auth/register/
- POST /api/auth/token/
- POST /api/auth/token/refresh/

Properties:
- GET /api/properties/?search=слово&min_price=...&max_price=...&city=...&min_rooms=...&max_rooms=...&property_type=apartment&ordering=price
- POST /api/properties/ (landlord)
- POST /api/properties/{id}/toggle_active/
- POST /api/properties/{id}/viewed/

Bookings:
- POST /api/bookings/ (tenant)
- POST /api/bookings/{id}/cancel/
- POST /api/bookings/{id}/approve/ (landlord)
- POST /api/bookings/{id}/decline/ (landlord)

Reviews:
- POST /api/reviews/ (auth)

Analytics:
- GET /api/analytics/popular-searches/
```

## MySQL
Настрой переменные в `.env`. В Docker по умолчанию `rootpass`.

## Docker
```bash
docker compose up -d --build
```

Сервер откроется на http://localhost:8000
