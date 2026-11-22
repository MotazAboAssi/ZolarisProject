from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    # Cart
    path('cart/', views.cart_detail, name='cart-detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart-add'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart-remove'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart-update'),
    # Checkout
    path('checkout/', views.checkout, name='checkout'),
    # Order history & detail
    path('orders/', views.order_history, name='order-history'),
    path('orders/<int:pk>/', views.order_detail, name='order-detail'),
]
