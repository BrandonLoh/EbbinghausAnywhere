"""用户认证相关视图:注册、登录、个人资料维护。"""

import logging
import uuid

from django.contrib import messages
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.shortcuts import redirect, render

from ..forms import (
    CustomPasswordChangeForm,
    CustomUserCreationForm,
    EmailUpdateForm,
    UpdateNameForm,
)
from ..models import Category, ReviewDay

logger = logging.getLogger(__name__)


def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # 使用 authenticate 进行身份验证
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # 如果用户验证通过，则登录并重定向
            login(request, user)
            return redirect('home')  # 登录成功后可以重定向到首页或其他页面
        else:
            # 如果用户名或密码错误，使用消息框架显示错误信息
            messages.error(request, "用户名或密码无效，请检查后重试。")

    return render(request, 'registration/login.html')


def register(request):
    if request.method == 'POST':
        random_id = request.POST.get('random_id', None)  # 获取随机 ID
        # 重构 POST 数据，将动态字段映射回标准字段
        if random_id:
            mapped_post = {
                'username': request.POST.get(f'random_username_{random_id}', ''),
                'email': request.POST.get('email', ''),
                'first_name': request.POST.get('first_name', ''),
                'last_name': request.POST.get('last_name', ''),
                'password1': request.POST.get(f'random_password1_{random_id}', ''),
                'password2': request.POST.get(f'random_password2_{random_id}', ''),
            }
            form = CustomUserCreationForm(mapped_post)
        else:
            form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            try:
                user = form.save()
                username = form.cleaned_data.get('username')

                # 加入 Public 组
                public_group, created = Group.objects.get_or_create(name='Public')
                user.groups.add(public_group)
                user.is_staff = True
                user.save()

                # 创建默认类别和复习计划
                Category.objects.create(user=user, name="单词", sort_order=1, is_default=True)
                review_days = [1, 2, 4, 7, 15, 30, 90, 180, 365]
                ReviewDay.objects.bulk_create(
                    [ReviewDay(user=user, day=day) for day in review_days]
                )

                messages.success(request, f'Account {username} created successfully!')
                return redirect('login')

            except Exception as e:
                logger.error(f"Error during registration: {e}")
                messages.error(request, f"Registration failed: {e}")
        else:
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    if field == 'password2':
                        error = error.replace('password2', 'Password confirmation')
                    error_messages.append(f"<p>{error}</p>")

            form_errors = "".join(error_messages)
            logger.warning(f"Form validation failed: {form.errors}")
            messages.error(request, f"<p>Please fix the following errors: {form_errors}</p>")
    else:
        random_id = uuid.uuid4().hex  # 生成一个随机 ID
        form = CustomUserCreationForm()

    return render(request, 'registration/register.html', {'form': form, 'random_id': random_id})


@login_required
def user_profile(request):
    if request.method == 'POST':
        # Update email
        if 'update_email' in request.POST:
            email_form = EmailUpdateForm(request.user, request.POST)
            if email_form.is_valid():
                request.user.email = email_form.cleaned_data.get('email')
                request.user.save()
                messages.success(request, "Email updated successfully.")
            else:
                messages.error(request, "Failed to update email. Please check the errors.")

        # Update name
        elif 'update_profile' in request.POST:
            name_form = UpdateNameForm(request.POST, instance=request.user)
            if name_form.is_valid():
                name_form.save()
                messages.success(request, "Name updated successfully.")
            else:
                messages.error(request, "Failed to update name. Please check the errors.")

        # Update password
        elif 'change_password' in request.POST:
            password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Keep user logged in
                messages.success(request, "Password updated successfully.")
            else:
                messages.error(request, "Failed to update password. Please check the errors.")

        return redirect('user_profile')

    else:
        email_form = EmailUpdateForm(request.user)
        name_form = UpdateNameForm(instance=request.user)
        password_form = CustomPasswordChangeForm(user=request.user)

    return render(request, 'user_profile.html', {
        'email_form': email_form,
        'name_form': name_form,
        'password_form': password_form,
    })
