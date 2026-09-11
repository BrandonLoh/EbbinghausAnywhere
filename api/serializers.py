"""序列化器:字段命名与 JSON 结构即小程序的契约,保持稳定。"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers

from EAW.models import Category, Item, Proficiency, ReviewDay

PROFICIENCY_VALUE_MAP = {code: label for code, label in Proficiency.PROFICIENCY_DEGREE}


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'display_name')
        read_only_fields = fields

    def get_display_name(self, obj):
        # 与 Web 首页一致的显示名逻辑: 优先姓名,回退 username
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}"
        return obj.first_name or obj.last_name or obj.username


class CategorySerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'sort_order', 'is_default', 'item_count')
        read_only_fields = fields


class ReviewDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewDay
        fields = ('id', 'day')
        read_only_fields = fields


class ItemListSerializer(serializers.ModelSerializer):
    """列表页用轻量字段;content 原文较大,详情页再给。"""

    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    proficiency_label = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            'id', 'item', 'category', 'category_name',
            'inputDate', 'initDate', 'proficiency', 'proficiency_label',
        )
        read_only_fields = fields

    def get_proficiency_label(self, obj):
        return PROFICIENCY_VALUE_MAP.get(obj.proficiency, '')


class ItemDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    proficiency_label = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            'id', 'item', 'content', 'category', 'category_name',
            'inputDate', 'initDate', 'proficiency', 'proficiency_label',
            'src_tts', 'us_phonetic', 'uk_phonetic',
        )
        read_only_fields = fields

    def get_proficiency_label(self, obj):
        return PROFICIENCY_VALUE_MAP.get(obj.proficiency, '')


class ItemCreateSerializer(serializers.Serializer):
    """新建条目:冒号拆分规则与 Web 端 InputView 完全一致。"""

    item_text = serializers.CharField(help_text='条目行,可含冒号分隔的名称与内容')
    input_date = serializers.DateField()
    category_id = serializers.IntegerField()

    def validate_category_id(self, value):
        user = self.context['request'].user
        try:
            category = Category.objects.get(pk=value, user=user)
        except Category.DoesNotExist:
            raise serializers.ValidationError('Category not found.')
        return category


class ReviewItemSerializer(serializers.Serializer):
    """复习列表中的单个条目(嵌在分组结构里,不直接作为页面主体)。"""

    id = serializers.IntegerField()
    item = serializers.CharField()
    content = serializers.CharField()
    review_day = serializers.IntegerField(help_text='命中的复习间隔天数')
    proficiency = serializers.IntegerField()
    proficiency_label = serializers.CharField()
    src_tts = serializers.CharField(allow_null=True, required=False)
    us_phonetic = serializers.CharField(allow_null=True, required=False)
    uk_phonetic = serializers.CharField(allow_null=True, required=False)


class FeedbackSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=['yes', 'no', 'reset'])
