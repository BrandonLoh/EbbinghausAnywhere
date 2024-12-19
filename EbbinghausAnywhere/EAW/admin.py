from django.contrib import admin
from django.urls import path
from django.utils.translation import gettext_lazy as _
from .models import Category, Item, ReviewDay
from .forms import CategoryAdminForm, ItemAdminForm, ReviewDayAdminForm
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils.html import format_html
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .translate import baidu_translate, check_api_keys
from django.template.response import TemplateResponse
import re
import logging
import difflib

logger = logging.getLogger(__name__)

class BaseAdmin(admin.ModelAdmin):
    """
    自定义基类Admin，用于实现普通用户只能看到自己的条目，
    超级用户可以看到所有条目。
    """
    exclude = ('user',)

    def get_queryset(self, request):
        """
        限制普通用户只能查看自己的条目，超级用户可以查看所有条目。
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # 超级用户可以看到所有条目
        return qs.filter(user=request.user)  # 普通用户只能看到自己的条目

    def save_model(self, request, obj, form, change):
        """
        保存模型时，普通用户只能修改自己的条目，超级用户可以修改所有条目。
        """
        if not obj.pk:  # 如果是新创建的对象
            obj.user = request.user
        elif not request.user.is_superuser and obj.user != request.user:
            raise PermissionError("普通用户不能修改其他用户的条目。")
        obj.save()

class UserCategoryFilter(admin.SimpleListFilter):
    """
    自定义过滤器，确保普通用户只能看到自己创建的类别，超级用户可以看到所有类别。
    """
    title = _('Category')  # 过滤器标题
    parameter_name = 'category'  # 过滤器参数名称

    def lookups(self, request, model_admin):
        """
        提供过滤器的选择项，普通用户只能看到自己创建的类别，超级用户可以看到所有类别。
        """
        if request.user.is_superuser:
            # 超级用户可以看到所有的类别
            return [(category.id, category.name) for category in Category.objects.all()]
        else:
            # 普通用户只能看到自己创建的类别
            return [(category.id, category.name) for category in Category.objects.filter(user=request.user)]

    def queryset(self, request, queryset):
        """
        根据过滤条件进行查询集过滤
        """
        if self.value():
            # 如果有选择的值，则按category进行过滤
            return queryset.filter(category_id=self.value())
        return queryset


class CategoryAdmin(BaseAdmin):
    form = CategoryAdminForm
    list_display = ('name', 'user')  # 超级用户可以在列表中看到用户信息
    ordering = ('sort_order', 'name')  # 默认按排序顺序和名称排序

    def get_list_filter(self, request):
        """
        动态调整过滤器，普通用户只能按类别筛选，超级用户能够按 user 筛选。
        """
        filters = ['sort_order']
        if request.user.is_superuser:
            filters.append('user')  # 超级用户可以按 user 筛选
        return filters

    def get_queryset(self, request):
        """
        普通用户只能看到自己创建的Category，超级用户可以看到所有的Category。
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # 超级用户可以看到所有类别
        return qs.filter(user=request.user)  # 普通用户只能看到自己创建的类别
    
    def save_model(self, request, obj, form, change):
        """
        自定义保存逻辑，阻止非法操作。
        """
        if change and obj.is_default and 'name' in form.changed_data:
            messages.error(request, "Cannot modify the name of the default category.")
            return  # 中断保存操作
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        """
        自定义删除逻辑，阻止删除默认分类。
        """
        if obj.is_default:
            messages.error(request, "Cannot delete the default category.")
            return  # 中断删除操作
        super().delete_model(request, obj)

    def response_change(self, request, obj):
        """
        自定义修改后的响应，避免阻止字段修改时显示保存成功的提示。
        """
        # 检测是否试图修改默认分类的名称
        if obj.is_default and 'name' in request.POST:
            submitted_name = request.POST.get('name', '').strip()
            if submitted_name != obj.name:
                # 阻止保存，添加错误消息
                messages.error(request, "Cannot modify the name of the default category.")
                # 重新渲染页面，无保存成功提示
                return self.render_change_form(
                    request,
                    context=self.get_changeform_initial_data(request, obj),
                    obj=obj,
                    form_url=None,
                    add=False,
                    change=True,
                )

        # 对于合法操作，调用父类方法，显示正常提示
        return super().response_change(request, obj)



class ItemAdmin(BaseAdmin):
    form = ItemAdminForm
    list_display = ('item', 'proficiency', 'category', 'user')  # 超级用户可看到用户信息
    search_fields = ('item', 'content')  # 支持按单词和内容搜索
    change_form_template = 'admin/item_change_form.html'  # 添加自定义模板

    def get_list_filter(self, request):
        filters = ['proficiency', UserCategoryFilter]  # 默认只显示类别和掌握程度的过滤器
        if request.user.is_superuser:
            filters.append('user')  # 超级用户可以根据 `user` 过滤
        return filters

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            if not request.user.is_superuser:
                kwargs["queryset"] = Category.objects.filter(user=request.user)  # 普通用户只能看到自己的类别
            else:
                kwargs["queryset"] = Category.objects.all()  # 超级用户可以看到所有类别
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(user=request.user)  # 普通用户只能看到自己创建的条目
        return qs  # 超级用户可以看到所有条目

    # 添加翻译按钮
    def get_translate_button(self, obj):
        if obj.category.name == "单词":
            return format_html(
                '<button class="button translate-button" data-id="{}">获取释义</button>',
                obj.id
            )
        return "-"

    get_translate_button.short_description = "操作"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('translate/<int:item_id>/', self.translate_item, name='translate_item'),
        ]
        return custom_urls + urls
    
    @staticmethod
    def clean_and_split_lines(content):
        """
        清理内容并按行分割，去除无关符号和空行。
        """
        if not content:
            return []
        # 去除前后空白字符，并按行分割
        cleaned_lines = [line.strip() for line in content.strip().split('\n') if line.strip()]
        return cleaned_lines

    @staticmethod
    def compare_and_merge(existing_lines, new_lines, threshold=0.8):
        """
        逐行比较新旧内容，使用difflib筛选出相似度低于阈值的行，并合并。
        """
        merged_lines = existing_lines.copy()  # 保留原有内容
        existing_set = set(existing_lines)  # 用集合快速去重

        for new_line in new_lines:
            is_duplicate = False
            for existing_line in existing_lines:
                # 计算相似度
                similarity = difflib.SequenceMatcher(None, existing_line, new_line).ratio()
                if similarity >= threshold:
                    is_duplicate = True
                    break
            # 仅在不重复的情况下添加
            if not is_duplicate and new_line not in existing_set:
                merged_lines.append(new_line)

        return merged_lines


    def translate_item(self, request, item_id):
        """
        调用翻译函数，逐行比较释义并合并新内容。
        """
        logger.debug(f"Received item_id: {item_id}")
        item = get_object_or_404(Item, id=item_id)
        if item.category.name != "单词":
            return JsonResponse({"success": False, "message": "当前类别不是 '单词'，无法翻译。"})

        # 调用翻译函数
        translation_result = baidu_translate(item.item)
        if not translation_result:
            return JsonResponse({"success": False, "message": "翻译失败，请稍后重试。"})

        # 解析翻译结果
        parts_and_means = translation_result.get('parts_and_means', [])
        simple_meaning = translation_result.get('simple_meaning', [])
        src_tts = translation_result.get('src_tts', '')
        phonetic = translation_result.get('phonetic', [])
        phonetic_am = phonetic[1] if len(phonetic) > 1 else None
        phonetic_en = phonetic[0] if len(phonetic) > 0 else None

        # 获取新旧内容
        current_content = item.content or ""
        new_content = "\n".join(parts_and_means if parts_and_means else simple_meaning)

        # 清理并分割内容
        existing_lines = self.clean_and_split_lines(current_content)
        new_lines = self.clean_and_split_lines(new_content)

        # 逐行比较并合并
        updated_lines = self.compare_and_merge(existing_lines, new_lines, threshold=0.8)

        # 合并后的内容
        updated_content = "\n".join(updated_lines)

        # 更新条目
        item.content = updated_content
        item.src_tts = src_tts
        item.us_phonetic = phonetic_am
        item.uk_phonetic = phonetic_en
        item.save()

        # 返回结果
        return JsonResponse({
            "success": True,
            "definition": updated_content,
            "src_tts": src_tts,
            "phonetic_am": phonetic_am,
            "phonetic_en": phonetic_en
        })

    def change_view(self, request, object_id, form_url='', extra_context=None):
        # 检查 API 配置状态
        api_status = "available" if check_api_keys() else "unavailable"

        # 将 API 状态传入模板上下文
        extra_context = extra_context or {}
        extra_context['api_status'] = api_status
        return super().change_view(request, object_id, form_url, extra_context=extra_context)




class ReviewDayAdmin(BaseAdmin):
    form = ReviewDayAdminForm
    list_display = ('day', 'user')  # 超级用户可看到用户信息

    def get_list_filter(self, request):
        """
        动态调整ReviewDay的过滤器，超级用户能看到按 user 筛选。
        """
        filters = []
        if request.user.is_superuser:
            filters.append('user')  # 超级用户能够按 user 筛选
        return filters

    def get_queryset(self, request):
        """
        普通用户只能看到自己创建的ReviewDay，超级用户可以看到所有的ReviewDay。
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # 超级用户可以看到所有复习天
        return qs.filter(user=request.user)  # 普通用户只能看到自己创建的复习天


# 注册所有模型到admin
admin.site.register(Category, CategoryAdmin)
admin.site.register(Item, ItemAdmin)
admin.site.register(ReviewDay, ReviewDayAdmin)
