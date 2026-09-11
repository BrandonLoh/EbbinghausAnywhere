"""
Views 包:原 778 行的 views.py 按功能域拆分而成。

- misc.py         首页 / 关于 / README
- accounts.py     注册 / 登录 / 个人资料
- items.py        条目列表 / 详情 / 搜索
- review.py       复习主页 / 复习视图 / 复习反馈
- input.py        录入
- data_io.py      Excel 导入 / 导出
- translate_api.py 百度翻译 AJAX 接口

这里重新导出全部视图名,使 `from EAW import views` 与
`from .views import X` 的旧导入路径保持不变,urls.py 无需改动。
"""

from .misc import home, about, readme_view
from .accounts import custom_login, register, user_profile
from .items import item_list, ItemDetailView, SearchView
from .review import (
    ReviewHomeView,
    ReviewView,
    ReviewFeedbackYes,
    ReviewFeedbackNo,
    ReviewFeedbackReset,
)
from .input import InputView, split_string
from .data_io import export_user_data_to_excel, import_items_from_excel
from .translate_api import translate, translate_test, check_api_keys_view

__all__ = [
    'home', 'about', 'readme_view',
    'custom_login', 'register', 'user_profile',
    'item_list', 'ItemDetailView', 'SearchView',
    'ReviewHomeView', 'ReviewView',
    'ReviewFeedbackYes', 'ReviewFeedbackNo', 'ReviewFeedbackReset',
    'InputView', 'split_string',
    'export_user_data_to_excel', 'import_items_from_excel',
    'translate', 'translate_test', 'check_api_keys_view',
]
