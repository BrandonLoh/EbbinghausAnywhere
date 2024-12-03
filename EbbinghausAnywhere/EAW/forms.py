from django import forms
from .models import Category, Item, ReviewDay

# Category的ModelForm
class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and hasattr(self, 'request'):
            # 如果是新建Category实例且request存在，自动设置user为当前请求的user
            self.instance.user = self.request.user

# Item的ModelForm
class ItemAdminForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and hasattr(self, 'request'):
            # 如果是新建Item实例且request存在，自动设置user为当前请求的user
            self.instance.user = self.request.user

# ReviewDay的ModelForm
class ReviewDayAdminForm(forms.ModelForm):
    class Meta:
        model = ReviewDay
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and hasattr(self, 'request'):
            # 如果是新建ReviewDay实例且request存在，自动设置user为当前请求的user
            self.instance.user = self.request.user
