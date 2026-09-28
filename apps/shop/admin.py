"""Admin Boutique (ajout seul)."""
from django.contrib import admin
from .models import ProductCategory, Product, Order, OrderItem


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'sort_order']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'price', 'stock_quantity', 'status', 'merchant']
    list_filter = ['status', 'merchant']
    search_fields = ['sku', 'name']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['total_price']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer', 'merchant', 'total', 'status', 'created_at']
    list_filter = ['status', 'merchant']
    search_fields = ['order_number', 'customer__phone_number']
    inlines = [OrderItemInline]
    readonly_fields = ['order_number', 'subtotal', 'fee', 'total', 'transaction', 'paid_at']
