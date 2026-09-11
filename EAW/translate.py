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

def baidu_translate(query):
    #print(query)
    # 检查 API 密钥是否配置
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        print("API 密钥未配置")
        return {}  # 统一返回空字典,调用方(视图/工具函数)按"翻译失败"处理
    
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
            return {}

        # 转换 JSON 数据为 Python 字典
        json_response = response.json()
        #print(json_response)
        # 检查返回的数据，判断输入是否为中文
        if 'result' in json_response:
            trans_result = json_response['result'].get('trans_result', [])
            if trans_result:
                dict_content = trans_result[0].get('dict', None)
                if dict_content:
                    dict_data = json.loads(dict_content)  # 解析 dict 字段中的 JSON
                    if dict_data.get('lang') == '0':  # 如果 lang == '0' 表示中文
                        print("输入为中文，返回空结果")
                        return {}  # 返回空字典，表示输入是中文

        # 检查 API 返回的内容是否有效
        if 'result' not in json_response or 'trans_result' not in json_response['result']:
            print("API 返回数据不完整或无翻译结果")
            return {}

        # 提取翻译结果
        trans_result = json_response['result']['trans_result'][0]
        dict_content = trans_result.get('dict', None)
        src_tts = trans_result.get('src_tts', None)
         # 确保 TTS URL 是有效的
        if src_tts and not is_valid_tts_url(src_tts):
            print(f"无效的 TTS URL: {src_tts}")
            src_tts = None

        if not dict_content:
            print("未找到字典内容")
            return {}

        # 解析字典内容并返回字典
        try:
            result_dict = parse_json_to_string(dict_content)
            result_dict["src_tts"] = src_tts  # 将音频链接放到字典中
            #print(result_dict)
            return result_dict
        except ValueError as e:
            print(f"解析字典内容失败: {e}")
            return {}
    except requests.exceptions.RequestException as e:
        print(f"HTTP 请求失败: {e}")
        return {}
    except json.JSONDecodeError as e:
        print(f"解析 JSON 失败: {e}")
        return {}
    except KeyError as e:
        print(f"关键字段缺失: {e}")
        return {}



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

        # 初始化返回的字典
        result = {
            "phonetic": [],  # 存储音标
            "parts_and_means": [],  # 存储词性和释义
            "simple_meaning": []  # 存储简明释义
        }

        # 提取音标
        if symbols:
            for symbol in symbols:
                ph_en = symbol.get("ph_en", None)  # 英式音标
                ph_am = symbol.get("ph_am", None)  # 美式音标

                # 只在音标存在时添加
                if ph_en:
                    result["phonetic"].append(ph_en)
                if ph_am:
                    result["phonetic"].append(ph_am)

        # 提取词性和释义
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
                            result["parts_and_means"].append(f"词性: {part}\n释义: {'; '.join(means_decoded)}")

        # 如果没有找到词性和释义，输出简明释义
        if not has_part_and_means and word_means:
            result["simple_meaning"].append("简明释义: " + "; ".join(word_means))  # 将所有简明释义合并为一行

        return result

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

def is_valid_tts_url(url):
    """
    验证音频链接的有效性和安全性
    - 确保链接以 HTTPS 开头
    - 确保链接来源于可信域名（如百度音频服务域名）
    """
    # 正则表达式检查 HTTPS 协议
    if not url.startswith("https://"):
        return False

    # 正则表达式检查是否来自百度音频服务（例如，假设它是 baidu.com 域名下的）
    if re.search(r"baidu\.com", url):
        return True

    return False
