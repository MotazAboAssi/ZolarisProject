from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'seller', 'price', 'stock', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('title', 'description', 'seller__username')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('category', 'seller')
