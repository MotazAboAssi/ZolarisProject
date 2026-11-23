from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from store.models import Product

from .cart import Cart
from .models import Order, OrderItem


# ------------------------------------------------------------------ #
# Cart
# ------------------------------------------------------------------ #

def cart_detail(request):
    """Display the current session cart."""
    cart = Cart(request)
    return render(request, 'orders/cart.html', {'cart': cart})


@require_POST
def cart_add(request, product_id: int):
    """Add a product to the cart (POST: quantity, optional override)."""
    product = get_object_or_404(Product, pk=product_id)
    cart = Cart(request)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        messages.error(request, 'Invalid quantity.')
        return redirect('store:product-detail', pk=product_id)

    if quantity < 1:
        messages.error(request, 'Quantity must be at least 1.')
        return redirect('store:product-detail', pk=product_id)

    if product.stock == 0:
        messages.error(request, f'"{product.title}" is out of stock.')
        return redirect('store:product-detail', pk=product_id)

    # Check total quantity already in cart + new addition
    existing = cart.cart.get(str(product_id), {}).get('quantity', 0)
    override = request.POST.get('override') == '1'
    new_qty = quantity if override else existing + quantity

    if new_qty > product.stock:
        messages.error(
            request,
            f'Only {product.stock} unit(s) of "{product.title}" available.',
        )
        return redirect('store:product-detail', pk=product_id)

    cart.add(product, quantity=quantity, override_qty=override)
    messages.success(request, f'"{product.title}" added to your cart.')
    return redirect('orders:cart-detail')


@require_POST
def cart_remove(request, product_id: int):
    """Remove a product from the cart."""
    cart = Cart(request)
    cart.remove(product_id)
    messages.success(request, 'Item removed from cart.')
    return redirect('orders:cart-detail')


@require_POST
def cart_update(request, product_id: int):
    """Update the quantity of a cart item."""
    product = get_object_or_404(Product, pk=product_id)
    cart = Cart(request)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        messages.error(request, 'Invalid quantity.')
        return redirect('orders:cart-detail')

    if quantity < 1:
        cart.remove(product_id)
        messages.success(request, 'Item removed from cart.')
        return redirect('orders:cart-detail')

    if quantity > product.stock:
        messages.error(
            request,
            f'Only {product.stock} unit(s) of "{product.title}" available.',
        )
        return redirect('orders:cart-detail')

    cart.add(product, quantity=quantity, override_qty=True)
    messages.success(request, 'Cart updated.')
    return redirect('orders:cart-detail')


# ------------------------------------------------------------------ #
# Checkout
# ------------------------------------------------------------------ #

@login_required
def checkout(request):
    """Show checkout summary (GET) or place the order (POST)."""
    cart = Cart(request)

    if cart.is_empty():
        messages.error(request, 'Your cart is empty.')
        return redirect('orders:cart-detail')

    if request.method == 'POST':
        # Re-validate stock inside a transaction
        with transaction.atomic():
            cart_items = list(cart)  # consumes iterator, also cleans deleted items

            if not cart_items:
                messages.error(request, 'Your cart is empty.')
                return redirect('orders:cart-detail')

            errors = []
            locked_products = {}
            for item in cart_items:
                try:
                    product = Product.objects.select_for_update().get(pk=item['product'].pk)
                except Product.DoesNotExist:
                    errors.append(f'"{item["product"].title}" is no longer available.')
                    continue
                locked_products[product.pk] = product
                if product.stock < item['quantity']:
                    errors.append(
                        f'Only {product.stock} unit(s) of "{product.title}" left in stock.'
                    )

            if errors:
                for err in errors:
                    messages.error(request, err)
                return redirect('orders:cart-detail')

            # Create order
            order = Order.objects.create(user=request.user, total_price=Decimal('0.00'))

            total = Decimal('0.00')
            for item in cart_items:
                product = locked_products[item['product'].pk]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_title=product.title,
                    unit_price=item['price'],
                    quantity=item['quantity'],
                )
                product.stock -= item['quantity']
                product.save(update_fields=['stock'])
                total += item['line_total']

            order.total_price = total
            order.save(update_fields=['total_price'])

        cart.clear()
        messages.success(request, f'Order #{order.pk} placed successfully!')
        return redirect('orders:order-detail', pk=order.pk)

    return render(request, 'orders/checkout.html', {'cart': cart})


# ------------------------------------------------------------------ #
# Order history & detail
# ------------------------------------------------------------------ #

@login_required
def order_history(request):
    """Paginated order history for the logged-in user."""
    status_filter = request.GET.get('status', '')
    orders_qs = Order.objects.filter(user=request.user).prefetch_related('items')

    if status_filter and status_filter in dict(Order.STATUS_CHOICES):
        orders_qs = orders_qs.filter(status=status_filter)

    paginator = Paginator(orders_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'orders/order_history.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'status_choices': Order.STATUS_CHOICES,
    })


@login_required
def order_detail(request, pk: int):
    """Detail view for a single order — only the owning user may view it."""
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})
