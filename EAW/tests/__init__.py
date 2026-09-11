"""EAW 测试包。

按功能域拆分:
- factories.py      共享的测试数据构造辅助
- test_models.py    模型层(约束、默认类别保护)
- test_accounts.py  注册/登录/个人资料
- test_items.py     条目列表/详情(权限隔离)/搜索
- test_review.py    复习视图与复习反馈
- test_input.py     批量录入与冒号拆分
- test_data_io.py   Excel 导入/导出
- test_translate.py 翻译接口(mock 外部 API)
"""
