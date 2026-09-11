# -*- coding: utf-8 -*-
"""
一次性数据整理脚本:批量处理 Excel 导出文件,用 DeepSeek 合并"单词"类别条目的释义。
与 Django 应用无关,独立运行;依赖 deepseek_merge.py 与环境变量 DEEPSEEK_API_KEY。

用法: 修改下方 input_file/output_file 后运行
    python merge_excel.py
"""

import pandas as pd
from deepseek_merge import get_client, merge_definitions_with_deepseek


def process_excel(client, file_path, output_path, category_column='Category', content_column='Content'):
    """
    处理Excel文件，对指定category的内容进行智能合并
    :param client: OpenAI 客户端(由 deepseek_merge.get_client 创建)
    :param file_path: 输入Excel文件路径
    :param output_path: 输出Excel文件路径
    :param category_column: 分类列名，默认为'Category'
    :param content_column: 内容列名，默认为'Content'
    """
    # 读取Excel文件
    df = pd.read_excel(file_path)

    # 筛选出category为'单词'的行
    word_df = df[df[category_column] == '单词']

    # 对每个单词进行智能合并
    merged_results = []
    for _, row in word_df.iterrows():
        # 假设content列包含多个释义，用换行符分隔
        definitions = row[content_column].split('\n')

        # 如果有多个释义，进行合并
        if len(definitions) > 1:
            # 将所有释义作为列表传入
            merged_definition = merge_definitions_with_deepseek(client, definitions)
        else:
            merged_definition = definitions[0]

        # 保存合并结果
        merged_results.append({
            '原始内容': row[content_column],
            '合并结果': merged_definition
        })

    # 创建新的DataFrame保存结果
    result_df = pd.DataFrame(merged_results)

    # 保存到新的Excel文件
    result_df.to_excel(output_path, index=False)


if __name__ == "__main__":
    input_file = 'd:/Brandon/Desktop/test_merge.xlsx'
    output_file = 'd:/Brandon/Desktop/merged_definitions.xlsx'
    client = get_client()
    process_excel(client, input_file, output_file)
