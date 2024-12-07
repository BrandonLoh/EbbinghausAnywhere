import requests
import json
import environ
from django.http import JsonResponse
import re

env = environ.Env(
    DEBUG=(bool, False)
)

# 获取 BAIDU 的 API 密钥
BAIDU_API_KEY = env('BAIDU_API_KEY', default=None)
BAIDU_SECRET_KEY = env('BAIDU_SECRET_KEY', default=None)

# BAIDU API 获取释义
def baidu_translate(query):
    # 检查 API 密钥是否配置
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        print("API 密钥未配置")
        return JsonResponse({"success": False, "message": "未配置百度 API 密钥"}, status=400)
    query = standardize_input(query)
    try:
        # 构造请求 URL
        url = f"https://aip.baidubce.com/rpc/2.0/mt/texttrans-with-dict/v1?access_token={get_access_token()}"

        # 构造请求数据
        payload = json.dumps({
            "from": "en",
            "to": "zh",
            "q": query
        })
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        # 发送请求
        response = requests.request("POST", url, headers=headers, data=payload)

        # 检查响应状态
        if response.status_code != 200:
            print(f"请求失败，HTTP 状态码: {response.status_code}")
            return ""

        # 转换 JSON 数据为 Python 字典
        json_response = response.json()
        #print(json_response)

        # 检查 API 返回的内容是否有效
        if 'result' not in json_response or 'trans_result' not in json_response['result']:
            print("API 返回数据不完整或无翻译结果")
            return ""

        # 提取翻译结果
        trans_result = json_response['result']['trans_result'][0]
        dict_content = trans_result.get('dict', None)
        src_tts = trans_result.get('src_tts',None)
        #print(dict_content)
        if not dict_content:
            print("未找到字典内容")
            return ""

        # 解析字典内容
        try:
            result = parse_json_to_string(dict_content)
            result_list = [src_tts, result]
            print(result)
            return result_list
        except ValueError as e:
            print(f"解析字典内容失败: {e}")
            return ""
    except requests.exceptions.RequestException as e:
        print(f"HTTP 请求失败: {e}")
        return ""
    except json.JSONDecodeError as e:
        print(f"解析 JSON 失败: {e}")
        return ""
    except KeyError as e:
        print(f"关键字段缺失: {e}")
        return ""

def get_access_token():
    """
    使用 AK，SK 生成鉴权签名（Access Token）
    :return: access_token，或是None(如果错误)
    """
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        return None
    
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {"grant_type": "client_credentials", "client_id": BAIDU_API_KEY, "client_secret": BAIDU_SECRET_KEY}
    response = requests.post(url, params=params)
    
    if response.status_code == 200:
        return str(response.json().get("access_token"))
    else:
        print(f"获取 access_token 失败: {response.status_code}")
        return None

def parse_json_to_string(json_string):
    try:
        # 解析 JSON
        data = json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 格式错误: {e}")

    # 提取字段
    try:
        simple_means = data.get("word_result", {}).get("simple_means")
        if not simple_means:
            raise KeyError("simple_means 字段缺失或为空")

        symbols = simple_means["symbols"]
        word_means = simple_means["word_means"]
            # 初始化输出内容
        output = []

            # 检查是否有词性和释义
        has_part_and_means = False

        if symbols:
            for symbol in symbols:
                part_details = symbol.get("parts", [])
                for detail in part_details:
                    part = detail.get("part", None)  # 词性
                    means = detail.get("means", [])  # 中文释义

                    if part and means:
                        has_part_and_means = True
                        means_decoded = []
                        for m in means:
                            if isinstance(m, dict):
                                means_decoded.append(m.get('mean', ''))
                            else:
                                means_decoded.append(m)

                        if means_decoded:
                            result = f"词性: {part}\n释义: {'; '.join(means_decoded)}"
                            output.append(result)

            # 如果有音标并且有词性和释义，输出音标
            if has_part_and_means and symbols:
                phonetic_output = []
                ph_en = symbols[0].get("ph_en", None)  # 英式音标
                ph_am = symbols[0].get("ph_am", None)  # 美式音标

                # 只在音标存在时输出
                if ph_en:
                    phonetic_output.append(f"英式音标: /{ph_en}/")
                if ph_am:
                    phonetic_output.append(f"美式音标: /{ph_am}/")

                if phonetic_output:
                    output.insert(0, "\n".join(phonetic_output))  # 将音标插入最前面

            # 如果没有词性和释义，输出简明释义，并且不输出音标
            if not has_part_and_means and word_means:
                output.append("简明释义: " + "; ".join(word_means))  # 将所有简明释义合并为一行

        return "\n\n".join(output) if output else ""  # 如果没有任何输出则返回空字符串
    except KeyError as e:
        raise ValueError(f"字段提取失败: {e}")

# 创建接口检查 API 配置是否存在
def check_api_keys():
    """
    检查是否配置了百度 API 密钥
    :return: True 如果配置了密钥，否则返回 False
    """
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        return False
    return True

def standardize_input(query):
    """
    对输入内容进行标准化处理，去除前后空格，多个空格替换为一个空格
    :param query: 输入的查询内容
    :return: 标准化后的查询内容
    """
    query = query.strip()  # 去除前后空格
    query = re.sub(r'\s+', ' ', query)  # 将多个空格替换为单个空格
    return query
