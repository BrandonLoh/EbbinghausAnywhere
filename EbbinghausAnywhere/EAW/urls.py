from django.urls import path, re_path
from EAW import views
from django.contrib.auth import views as auth_views
from .views import ItemDetailView


urlpatterns = [
    path('', views.index, name='index'),  # Index view
    # 将 'home' 指向 'index' 页面
    path('home/', views.index, name='home'),  # Home view，直接指向 index
    # 用户认证相关的URL
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),  # 登录
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),  # 退出
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),  # 更改密码
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),  # 密码更改成功
    path('accounts/password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),  # 找回密码
    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),  # 找回密码邮件发送成功
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),  # 确认密码重置
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),  # 密码重置完成
    # 用户注册视图
    path('accounts/register/', views.register, name='register'),
    path('list/', views.item_list, name='item-list'),
    path('item/<int:pk>/', ItemDetailView.as_view(), name='item-detail'),
    path('search/', views.SearchView, name='search'),  # 注册搜索页面的路由
    # 路由：显示选择日期的页面
    path('review/', views.ReviewHomeView, name='review-home'),    
    # 路由：根据选定的日期显示复习内容
    re_path(r'^review/(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})/$', views.ReviewView, name='review-view'),  # 按日期显示复习
    #re_path(r'^review/(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})/(?P<pk>\d+)/$', views.ReviewDetailView, name='review-detail'),  # 复习详情
    # 复习反馈的POST请求
    path('review-feedback/yes/', views.ReviewFeedbackYes, name='review-feedback-yes'),
    path('review-feedback/no/', views.ReviewFeedbackNo, name='review-feedback-no'),
    path('review-feedback/reset/', views.ReviewFeedbackReset, name='review-feedback-reset'),
    path('translate/', views.translate, name='translate'),#后端处理翻译请求
    path('translate_test/', views.translate_test, name='translate_test'),#BAIDU API获取释义测试页面
    path('api/check-baidi-keys/', views.check_api_keys_view, name='check-api-keys'),#检测是否配置了BAIDU API

]