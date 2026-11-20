from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ProductForm
from .models import Category, Product


def _parse_non_negative_decimal(raw_value: str) -> Decimal | None:
    """Safely parse a finite, non-negative Decimal from a query parameter."""
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    try:
        parsed = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < Decimal('0'):
        return None
    return parsed


class ProductOwnerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict access so only the seller who owns the product can modify or delete it."""

    def test_func(self) -> bool:
        return self.get_object().seller == self.request.user


class ProductListView(ListView):
    """Storefront catalog with keyword search, category/price filters, and pagination."""

    model = Product
    template_name = 'store/product_list.html'
    context_object_name = 'products'
    paginate_by = 9

    def get_queryset(self):
        queryset = Product.objects.select_related('category', 'seller')

        # 1. Keyword search across title and description
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            )

        # 2. Category filter (supports slug, or numeric ID fallback)
        category_param = self.request.GET.get('category', '').strip()
        if category_param:
            if category_param.isdigit():
                queryset = queryset.filter(
                    Q(category__slug=category_param) | Q(category__id=int(category_param))
                )
            else:
                queryset = queryset.filter(category__slug=category_param)

        # 3. Price range filters (gracefully ignore malformed/non-finite numeric input)
        min_price = _parse_non_negative_decimal(self.request.GET.get('min_price', ''))
        if min_price is not None:
            queryset = queryset.filter(price__gte=min_price)

        max_price = _parse_non_negative_decimal(self.request.GET.get('max_price', ''))
        if max_price is not None:
            queryset = queryset.filter(price__lte=max_price)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        current_q = self.request.GET.get('q', '').strip()
        current_category = self.request.GET.get('category', '').strip()
        current_min_price = self.request.GET.get('min_price', '').strip()
        current_max_price = self.request.GET.get('max_price', '').strip()

        # Preserve all active query parameters except 'page' for pagination links
        query_params = self.request.GET.copy()
        query_params.pop('page', None)

        context.update(
            {
                'categories': Category.objects.all(),
                'current_q': current_q,
                'current_category': current_category,
                'current_min_price': current_min_price,
                'current_max_price': current_max_price,
                'has_active_filters': any(
                    [current_q, current_category, current_min_price, current_max_price]
                ),
                'query_string': query_params.urlencode(),
            }
        )

        if context.get('is_paginated'):
            context['page_range'] = context['paginator'].get_elided_page_range(
                context['page_obj'].number,
                on_each_side=2,
                on_ends=1,
            )

        return context


class ProductDetailView(DetailView):
    """Display full product details, seller metadata, and cart/owner actions."""

    model = Product
    template_name = 'store/product_detail.html'
    context_object_name = 'product'

    def get_queryset(self):
        return Product.objects.select_related('category', 'seller')


class ProductCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """Allow authenticated users to publish new product listings."""

    model = Product
    form_class = ProductForm
    template_name = 'store/product_form.html'
    success_message = 'Product "%(title)s" was published successfully.'

    def form_valid(self, form):
        form.instance.seller = self.request.user
        return super().form_valid(form)


class ProductUpdateView(ProductOwnerRequiredMixin, SuccessMessageMixin, UpdateView):
    """Allow product owners to update their own listings."""

    model = Product
    form_class = ProductForm
    template_name = 'store/product_form.html'
    success_message = 'Product "%(title)s" was updated successfully.'


class ProductDeleteView(ProductOwnerRequiredMixin, DeleteView):
    """Allow product owners to delete their own listings after confirmation."""

    model = Product
    template_name = 'store/product_confirm_delete.html'
    success_url = reverse_lazy('store:product-list')

    def form_valid(self, form):
        product_title = self.get_object().title
        messages.success(self.request, f'Product "{product_title}" was deleted.')
        return super().form_valid(form)
