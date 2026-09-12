"""录入视图:批量录入条目(可选百度释义抓取)。

防重复提交:
- 每次渲染表单时下发一次性令牌(submit_token),提交成功后把令牌记入会话;
- 再次收到同一令牌的提交(双击、网络中断后重试、回退重发)直接忽略并提示,
  不会重复建条目;
- 只拦"确认已处理过"的令牌,未知或缺失令牌一律放行,不会阻塞正常提交。

另:一次提交整批原子写入,失败不会只写一半;空行/只有冒号的行会被跳过
(与 API 端 `_create_items` 的行为一致),不再产生空名条目。
"""

import re
import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from ..forms import InputForm
from ..models import Category, Item
from ..translate import baidu_translate

SUBMIT_TOKEN_FIELD = 'submit_token'
# 会话中记录"最近处理过的提交令牌",用于识别迟到的重复提交
_USED_TOKENS_SESSION_KEY = 'input_used_submit_tokens'
_USED_TOKENS_KEEP = 10


def split_string(s):
    """按最先出现的冒号(英文/中文)拆分为 (名称, 内容)。"""
    pos = s.find(":")
    pos_cn = s.find("：")

    # 找到最先出现的冒号位置
    if pos == -1 or (pos_cn != -1 and pos_cn < pos):
        pos = pos_cn

    # 如果没有冒号，返回原字符串和空字符串
    if pos == -1:
        return s, ""

    # 根据位置分割字符串
    return s[:pos], s[pos + 1:]


def _issue_submit_token():
    return secrets.token_urlsafe(16)


def _is_replayed_submit(request):
    """本次提交是否是一次已经处理过的重复提交。"""
    token = request.POST.get(SUBMIT_TOKEN_FIELD, '')
    if not token:
        return False
    return token in request.session.get(_USED_TOKENS_SESSION_KEY, [])


def _mark_submit_token_used(request):
    """记录该令牌已处理(保留最近若干个,便于识别迟到的重试)。"""
    token = request.POST.get(SUBMIT_TOKEN_FIELD, '')
    if not token:
        return
    used = [t for t in request.session.get(_USED_TOKENS_SESSION_KEY, []) if t != token]
    request.session[_USED_TOKENS_SESSION_KEY] = ([token] + used)[:_USED_TOKENS_KEEP]


@login_required
def InputView(request):
    if request.method == 'POST':
        # 重复提交(双击/网络重试):直接忽略,不重复建条目
        if _is_replayed_submit(request):
            messages.info(request, '这次提交已经处理过了（重复点击或网络重试），没有重复录入。')
            return redirect(reverse('item-list'))

        form = InputForm(request.POST, user=request.user)  # 传递当前用户
        if form.is_valid():
            data = {
                'input_date': form.cleaned_data['input_date'],
                'category': form.cleaned_data['category'].name,
                'input': form.cleaned_data['input']
            }
            category_object = Category.objects.get(name=data['category'], user=request.user)  # 仅查找当前用户的类别

            # 获取是否勾选了翻译复选框，并且类别为"单词"
            translate = 'translate' in request.POST and data['category'] == '单词'

            items_to_create = []
            for line in re.split(r'\r\n|\n', data['input']):
                explain_txt = ''
                result_dict = None
                translated_content = ''
                simple_meaning = ''
                item_name, explain_txt = split_string(line)  # 如果有拆分功能
                item_name = item_name.strip()
                if not item_name:
                    # 空行 / 只有冒号的行:跳过,不产生空名条目
                    continue
                # 初始化 phonetic_am 和 phonetic_en 为 None
                phonetic_am = phonetic_en = None
                src_tts = None

                # 如果勾选了 "获取释义" 复选框，则调用百度翻译函数
                if translate:
                    result_dict = baidu_translate(item_name)
                    if result_dict:  # 如果返回的字典非空
                        # 从 result_dict 中提取各个部分
                        phonetic = result_dict.get('phonetic', [])
                        phonetic_am = phonetic[1] if len(phonetic) > 1 else None  # 美式音标
                        phonetic_en = phonetic[0] if len(phonetic) > 0 else None  # 英式音标
                        src_tts = result_dict.get('src_tts', None)  # TTS URL
                        translated_content = result_dict.get('parts_and_means', [])  # 词性和释义
                        simple_meaning = result_dict.get('simple_meaning', [])  # 简明释义

                        # 拼接解释文本
                        # 确保是字符串并避免空行
                        if translated_content:
                            if explain_txt:  # 如果原来已有内容，才添加换行
                                explain_txt += "\n\n"
                            explain_txt += "\n".join([str(item) for item in translated_content])  # 拼接详细释义

                        # 如果有 translated_content 或音标，则不存储 simple_meaning
                        if not translated_content:
                            # 如果没有翻译内容才拼接简明释义
                            if simple_meaning:
                                if explain_txt:  # 如果原来已有内容，才添加换行
                                    explain_txt += "\n\n"
                                explain_txt += "\n".join([str(item) for item in simple_meaning])  # 拼接简明释义
                    else:
                        phonetic_am = phonetic_en = src_tts = None

                # 收集待创建的 Item,整批写入
                items_to_create.append(Item(
                    user=request.user,
                    item=item_name,
                    inputDate=data['input_date'],
                    initDate=data['input_date'],
                    category=category_object,
                    content=explain_txt,
                    src_tts=src_tts if translate else None,  # 如果未勾选翻译，TTS 地址为 None
                    us_phonetic=phonetic_am,  # 存储美式音标
                    uk_phonetic=phonetic_en   # 存储英式音标
                ))

            if not items_to_create:
                messages.warning(request, '没有解析到有效条目（空行会被忽略），未做任何写入。')
                return redirect(reverse('item-list'))

            # 整批原子写入:要么全部成功,要么全部不写入
            with transaction.atomic():
                Item.objects.bulk_create(items_to_create)

            _mark_submit_token_used(request)
            messages.success(request, f'已录入 {len(items_to_create)} 个条目。')
            return redirect(reverse('item-list'))  # 重定向到项列表页面
    else:
        form = InputForm(user=request.user)  # 传递当前用户

    return render(request, 'input.html', {
        'form': form,
        SUBMIT_TOKEN_FIELD: _issue_submit_token(),
    })
