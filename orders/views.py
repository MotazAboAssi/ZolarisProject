from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from store.models import Product


def cart_detail_placeholder(request):
    """Placeholder cart page reserved for the teammate's orders module."""
    return render(request, 'orders/cart_placeholder.html')


@require_POST
def cart_add_placeholder(request, product_id: int):
    """Placeholder Add-to-Cart endpoint wired from store/product_detail.html."""
    product = get_object_or_404(Product, pk=product_id)
    quantity = request.POST.get('quantity', '1')
    messages.info(
        request,
        f'Cart hook triggered for "{product.title}" (qty: {quantity}). '
        'Full cart persistence will be handled by the orders module.',
    )
    return redirect('store:product-detail', pk=product.pk)
