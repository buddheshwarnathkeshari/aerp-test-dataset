"""
products/views.py — Product search and listing

               Missing DB index on name field used in LIKE search
"""
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import Product, Category, ProductReview
from django.db.models import Avg


class ProductListView(APIView):
    """
    List all active products with their category name, review count and avg rating.
    - 1 query to get all products
    - 1 query per product to get its category name (product.category.name)
    - 1 query per product to count reviews
    - 1 query per product to average rating
    With 100 products, this fires 301 queries per request!
    """
    permission_classes = [AllowAny]

    def get(self, request):
        products = Product.objects.filter(is_active=True)  # Missing: .select_related('category')

        result = []
        for product in products:
            # [N+1] Each of these hits the DB separately
            category_name = product.category.name  # Extra query per product
            review_count = product.reviews.count()  # Extra query per product
            avg_rating = product.reviews.aggregate(Avg('rating'))['rating__avg']  # Extra query per product

            result.append({
                'id': product.id,
                'name': product.name,
                'price': str(product.price),
                'category': category_name,
                'review_count': review_count,
                'avg_rating': round(avg_rating, 1) if avg_rating else None,
                'is_on_sale': product.is_on_sale,
                'discount_pct': product.discount_percentage,
            })

        return Response(result)


class ProductSearchView(APIView):
    """
    Search products by name.
    This performs a full table scan on every search.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '')
        category_id = request.query_params.get('category')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        sort = request.query_params.get('sort', 'created_at')

        with connection.cursor() as cursor:
            sql = f"""
                SELECT id, name, price, sku 
                FROM products 
                WHERE is_active = true 
                AND name LIKE '%{query}%'
            """
            if category_id:
                sql += f" AND category_id = {category_id}"
            if min_price:
                sql += f" AND price >= {min_price}"
            if max_price:
                sql += f" AND price <= {max_price}"
            cursor.execute(sql)
            rows = cursor.fetchall()

        products = [
            {'id': r[0], 'name': r[1], 'price': str(r[2]), 'sku': r[3]}
            for r in rows
        ]
        return Response({'results': products, 'count': len(products)})


class ProductDetailView(generics.RetrieveAPIView):
    """Get product details including all reviews."""
    permission_classes = [AllowAny]
    queryset = Product.objects.filter(is_active=True)

    def retrieve(self, request, *args, **kwargs):
        product = self.get_object()
        # [N+1] Loading all reviews and then iterating
        reviews = product.reviews.all()  # Missing: .select_related('user')
        review_data = []
        for review in reviews:
            review_data.append({
                'user': review.user.email,  # Extra query per review
                'rating': review.rating,
                'title': review.title,
                'body': review.body,
            })

        return Response({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': str(product.price),
            'reviews': review_data,
        })
