from django.urls import path
from EAW import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('', views.index, name='index'),  # Index view
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
]