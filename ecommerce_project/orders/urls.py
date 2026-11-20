from django.urls import path

from .views import cart_add_placeholder, cart_detail_placeholder

app_name = 'orders'

urlpatterns = [
    path('cart/', cart_detail_placeholder, name='cart-detail'),
    path('cart/add/<int:product_id>/', cart_add_placeholder, name='cart-add'),
]
