"""认证端点:账号密码登录、微信 code2session 静默登录、首次绑定。"""

import logging

import requests
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..models import WeChatProfile
from ..serializers import LoginSerializer, UserSerializer

logger = logging.getLogger(__name__)

WECHAT_CODE2SESSION_URL = 'https://api.weixin.qq.com/sns/jscode2session'
WECHAT_CODE2SESSION_TIMEOUT = 10  # 秒


def _token_response(user):
    """生成(或复用)token 并组装统一的登录成功响应。"""
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': UserSerializer(user).data,
    })


def _code2session(code):
    """调用微信 code2session,返回 openid;失败返回 None 并记录原因。

    appsecret 只在服务端使用,永远不会下发给客户端。
    """
    from django.conf import settings
    appid = getattr(settings, 'WECHAT_APPID', None)
    secret = getattr(settings, 'WECHAT_SECRET', None)
    if not appid or not secret:
        logger.error('WECHAT_APPID/WECHAT_SECRET not configured')
        return None

    try:
        resp = requests.get(
            WECHAT_CODE2SESSION_URL,
            params={
                'appid': appid,
                'secret': secret,
                'js_code': code,
                'grant_type': 'authorization_code',
            },
            timeout=WECHAT_CODE2SESSION_TIMEOUT,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.error(f'code2session request failed: {e}')
        return None

    if 'openid' not in data:
        # errcode/errmsg 如 40029 invalid code、45011 频率限制等
        logger.error(f"code2session failed: {data.get('errcode')} {data.get('errmsg')}")
        return None
    return data['openid']


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """账号密码登录,换取持久 token(小程序的兜底登录方式)。"""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        request,
        username=serializer.validated_data['username'],
        password=serializer.validated_data['password'],
    )
    if user is None:
        return Response(
            {'detail': '用户名或密码错误。'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return _token_response(user)


@api_view(['POST'])
@permission_classes([AllowAny])
def wechat_login(request):
    """小程序静默登录:code 换 openid,已绑定则直接发 token。"""
    code = request.data.get('code', '')
    if not code:
        return Response({'detail': '缺少 code。'}, status=status.HTTP_400_BAD_REQUEST)

    openid = _code2session(code)
    if openid is None:
        return Response(
            {'detail': '微信登录失败,请稍后重试。'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    profile = WeChatProfile.objects.select_related('user').filter(openid=openid).first()
    if profile is None:
        return Response({'bind_required': True}, status=status.HTTP_200_OK)
    return _token_response(profile.user)


@api_view(['POST'])
@permission_classes([AllowAny])
def wechat_bind(request):
    """首次绑定:code + Web 端账号密码 → 建立 openid 与账号的关联并发 token。"""
    code = request.data.get('code', '')
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if not code:
        return Response({'detail': '缺少 code。'}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(
        request,
        username=serializer.validated_data['username'],
        password=serializer.validated_data['password'],
    )
    if user is None:
        return Response(
            {'detail': '用户名或密码错误。'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    openid = _code2session(code)
    if openid is None:
        return Response(
            {'detail': '微信登录失败,请稍后重试。'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # 绑定关系以 openid 为准:同一微信号换绑账号时覆盖旧绑定
    WeChatProfile.objects.update_or_create(
        openid=openid,
        defaults={'user': user},
    )
    return _token_response(user)
