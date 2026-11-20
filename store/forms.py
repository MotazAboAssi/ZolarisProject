from decimal import Decimal

from django import forms

from .models import Product


class ProductForm(forms.ModelForm):
    """Bootstrap 5 styled ModelForm for creating and updating products."""

    class Meta:
        model = Product
        fields = ['category', 'title', 'description', 'price', 'stock', 'image']
        widgets = {
            'category': forms.Select(
                attrs={'class': 'form-select'},
            ),
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g., Wireless Noise-Canceling Headphones',
                    'maxlength': '200',
                },
            ),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 5,
                    'placeholder': 'Describe key features, condition, and specifications...',
                },
            ),
            'price': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'step': '0.01',
                    'min': '0.01',
                    'inputmode': 'decimal',
                    'placeholder': '0.00',
                },
            ),
            'stock': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '0',
                    'step': '1',
                    'inputmode': 'numeric',
                },
            ),
            'image': forms.ClearableFileInput(
                attrs={
                    'class': 'form-control',
                    'accept': 'image/*',
                },
            ),
        }
        help_texts = {
            'price': 'Enter the unit price in USD (minimum $0.01).',
            'stock': 'Available inventory count (0 marks the item as Out of Stock).',
            'image': 'Recommended: landscape 4:3 image (JPEG, PNG, or WebP).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = 'Select a category (optional)'

        # Bind accessible aria-describedby and aria-invalid attributes
        for field_name, field in self.fields.items():
            widget_attrs = field.widget.attrs
            field_id = f'id_{field_name}'
            described_by = []
            if field.help_text:
                described_by.append(f'{field_id}-help')
            if self.is_bound and self.errors.get(field_name):
                described_by.append(f'{field_id}-error')
                widget_attrs['aria-invalid'] = 'true'
                existing_classes = widget_attrs.get('class', '')
                if 'is-invalid' not in existing_classes:
                    widget_attrs['class'] = f'{existing_classes} is-invalid'.strip()
            if described_by:
                widget_attrs['aria-describedby'] = ' '.join(described_by)

    def clean_price(self) -> Decimal:
        price = self.cleaned_data['price']
        if price <= Decimal('0.00'):
            raise forms.ValidationError('Price must be greater than $0.00.')
        return price
