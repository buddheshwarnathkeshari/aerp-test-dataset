# ShopCore — Django E-Commerce Backend

A production-style Django REST API for an e-commerce platform.

## Stack
- Django 4.2 + Django REST Framework
- PostgreSQL (via psycopg2)
- Celery + Redis (async tasks)
- JWT Authentication (simplejwt)

## Apps
- `users` — Registration, login, JWT auth, profile management
- `products` — Product catalog, search, categories
- `orders` — Cart, checkout, order lifecycle
- `payments` — Payment processing, refunds
- `inventory` — Stock management
- `coupons` — Discount codes and promotions

## Setup
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Environment
```
DATABASE_URL=postgresql://user:pass@localhost:5432/shopcore
SECRET_KEY=your-secret-key
DEBUG=True
```
