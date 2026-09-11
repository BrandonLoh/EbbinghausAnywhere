# -*- coding: utf-8 -*-
"""
一次性数据整理脚本:调用 DeepSeek 合并单词释义(按词性分类、去除重复)。
与 Django 应用无关,独立运行;密钥从环境变量 DEEPSEEK_API_KEY 读取。

用法:
    export DEEPSEEK_API_KEY=sk-...   # 或 set DEEPSEEK_API_KEY=sk-... (Windows)
    python deepseek_merge.py
"""

import os
import sys

from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def get_client():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        sys.exit("请先设置环境变量 DEEPSEEK_API_KEY")
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def merge_definitions_with_deepseek(client, definition_text):
    """
    调用 DeepSeek 模型合并释义，按词性分类并去除重复内容。
    """
    # 构建提示词
    prompt = f"""
    请将以下单词释义按词性分类，并确保合并后的释义清晰、准确且不重复：

    释义文本：
    {definition_text}

    要求：
    0. 识别哪些文本是来自词典释义，哪些是手工输入的笔记，保留笔记，并在其上加入【笔记】标签
    1. 按词性（如 n., adj., v. 等）分类。
    2. 合并相同词性的释义，去除重复内容。
    3. 确保释义清晰、准确。
    4. 输出结果为纯文本格式，不要使用 Markdown 符号（如 #, -, ** 等）。
    5. 不要额外输出解释，如“合并后的释义”等

    合并后的释义：
    """

    # 调用 DeepSeek API
    response = client.chat.completions.create(
        model="deepseek-chat",  # 使用 DeepSeek 模型
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,  # 控制生成文本的随机性
        max_tokens=500  # 限制生成文本的长度
    )

    # 提取合并后的释义
    merged_definition = response.choices[0].message.content
    return merged_definition


if __name__ == "__main__":
    # 示例字符串
    definition_text = """
    n. （非正式）妈妈；（非正式）（栽培的）菊花；啤酒
    adj. 沉默的；守密的
    v. 在传统假面哑剧中扮演（角色）；在英格兰民俗剧中扮演（角色）
    词性: n.
    释义: 妈妈; 妈; <口>菊花; 沉默，缄默; 马姆酒（17-18世纪英国的一种烈性啤酒）
    词性: adj.
    释义: 沉默的，无言的
    词性: v.
    释义: （节日期间）化装（或戴面具）作乐; 化装; 参加化装舞会; 化装演出哑剧
    """

    client = get_client()
    merged_definition = merge_definitions_with_deepseek(client, definition_text)
    print("合并后的释义：")
    print(merged_definition)
