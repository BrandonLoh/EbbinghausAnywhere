from django import forms
from .models import Category, Item, ReviewDay

# Category的ModelForm
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

    def clean_name(self):
        """
        验证默认分类是否被修改了 name。
        """
        if self.instance.is_default and self.cleaned_data['name'] != self.instance.name:
            raise forms.ValidationError("Cannot modify the name of the default category.")
        return self.cleaned_data['name']


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

class InputForm(forms.Form):
    input_date = forms.DateField(input_formats=['%Y-%m-%d'])
    
    def clean_input_date(self):
        data = self.cleaned_data['input_date']
        return data
    
    # 限制类别只显示当前用户的类别
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=True)  

    input = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # 从视图传入当前用户
        super().__init__(*args, **kwargs)

        if user:
            # 仅显示当前用户的类别
            self.fields['category'].queryset = Category.objects.filter(user=user) 

