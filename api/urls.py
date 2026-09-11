"""API v1 路由。全部挂在 /api/v1/ 下(见项目 urls.py)。"""

from django.urls import path

from .views import auth, backup, items, review, users

urlpatterns = [
    # 认证
    path('auth/login/', auth.login_view, name='api-login'),
    path('auth/wechat/', auth.wechat_login, name='api-wechat-login'),
    path('auth/wechat/bind/', auth.wechat_bind, name='api-wechat-bind'),

    # 用户与类别
    path('me/', users.me, name='api-me'),
    path('categories/', users.CategoryListView.as_view(), name='api-categories'),

    # 复习
    path('review/', review.review_list, name='api-review'),
    path('review/feedback/', review.review_feedback, name='api-review-feedback'),

    # 条目
    path('items/', items.items_collection, name='api-items'),
    path('items/<int:pk>/', items.item_detail, name='api-item-detail'),

    # 运维:NAS 同步快照(仅 superuser)
    path('backup/snapshot/', backup.snapshot, name='api-backup-snapshot'),
]
