from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models

from store.models import Product


class Order(models.Model):
    """A placed order belonging to a registered user."""

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_SHIPPED = 'shipped'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Order #{self.pk} by {self.user.username} ({self.status})'

    def calculate_total(self) -> Decimal:
        """Recalculate and save the order total from its items."""
        total = sum((item.line_total for item in self.items.all()), Decimal('0.00'))
        self.total_price = total
        self.save(update_fields=['total_price'])
        return total


class OrderItem(models.Model):
    """A single product line within an order."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items',
    )
    # Snapshot of product title at purchase time (survives product deletion)
    product_title = models.CharField(max_length=200)
    # Snapshot of price at purchase time so historical totals stay accurate
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self) -> str:
        return f'{self.quantity} × {self.product_title}'

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity
