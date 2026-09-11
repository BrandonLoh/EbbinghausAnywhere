# 万物皆可艾宾浩斯
# Ebbinghaus Anywhere 

*EbbinghausAnywhere is an open sourced memory tool for my girl Ellie.*

## 1. 项目介绍
2022年，应Ellie妈的要求，我写了一个Excel VBA来帮助Ellie通过艾宾浩斯曲线复习单词。到了2023年底，为了让Ellie在出门旅行时也能快乐的背单词，我基于Django写了一个网页版的程序，部署在www.pythonanywhere.com上。随着使用，这个程序的功能也逐渐丰富，比如通过MathJax，mhchem来支持数学公式、化学方程式等的输入与显示等。2024年底，我将这个项目通过ChatGPT重构,增加了多用户功能，重新设计了UI界面并将它作为一个开源项目放在Github上。
万物皆可艾宾浩斯是要一个基于Django和bootstrap的网页版记忆工具，支持桌面端和移动端访问，支持多用户登录并建立各自独立的数据集。通过Apache2.0协议开源，项目地址在 [Github.com](https://github.com/BrandonLoh/EbbinghausAnywhere)上。 感兴趣的同学可以自行下载部署，也可以通过托管在PythonAnywhere上的[万物皆可艾宾浩斯](https://Ebbinghaus.pythonanywhere.com/ "托管在PythonAnywhere上的免费网站") 来访问和使用这个工具。

## 2. 使用方法
可在页面右上角弹出式菜单内选择相应功能
### 2.1 设置类别和复习周期
在Manage Data选项可进入管理台页面，对Category和Review Days进行自定义设置，单词类别作为默认类别不能更改。
### 2.2 录入新条目
- 在Input页面可以录入新条目，选择日期和类别进行保存
- 输入时可以通过冒号":"区分条目名称和内容
- 条目内容支持Markdown语法（标题、列表、粗体斜体、代码块、表格等），在复习页面和条目详情页面自动渲染
- 通过mathjax支持使用LaTeX语法输入数学公式和符号并支持mhchem输入化学方程式，冒号后输入“\$\$公式内容$$”或“\$公式内容\$”即可调用mathjax渲染公式。详细用法参见[mathjax文档](https://www.osgeo.cn/mathjax/index.html)和[mhchem for MathJax](https://mhchem.github.io/MathJax-mhchem/)
- 勾选“Fetch Translations”选项可对单词类别的内容查询音标、发音和中文释义。
### 2.3 进行复习
- 在Review页面可以选择日期进行复习，默认为当日。点击条目可以选择"Yes" "No" 来表示掌握程度，"Reset"可将该条目复习周期重置为从当日开始。
### 2.4 导入和导出数据
在Manage Profile页面可以更改账号信息，导入和导出数据
## 3. 部署方法
- 需要在根目录下创建本地.env文件放置密钥，如果需要开启在线查询单词释义功能，需要在其中放入百度api应用ID和密钥，参考[文本翻译-词典版](https://cloud.baidu.com/doc/MT/s/nkqrzmbpc)
```
    # SECURITY WARNING: keep the secret key used in production secret!
    SECRET_KEY=your_django_secret_key
    # BAIDU的应用ID
    BAIDU_API_KEY=your_baidu_api_key
    # BAIDU的应用密钥
    BAIDU_SECRET_KEY=your_baidu_secret_key
```

- 需要在EbbinghausAnywhere目录下创建本地local_settings文件放置数据库信息等
```
    from .settings import BASE_DIR  # 导入 settings.py 中定义的 BASE_DIR

    # Replace the following Database setting to your datebase setting.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

    # SECURITY WARNING: don't run with debug turned on in production!
    DEBUG = True
```
## 4 开源项目
本项目基于 Apache License 2.0 授权发布。您可以在遵守许可协议条款的前提下自由使用、修改和分发本软件。许可协议的主要内容包括：
- 您可以自由使用和分发本软件，包括商业用途。
- 允许修改代码，但需保留相同的许可协议。
- 重新分发时必须包含原始版权声明和许可协议文本。
- 本软件不提供任何担保或责任承诺。
- 完整的许可协议文本，请参见项目中的 LICENSE 文件或访问 Apache License 2.0 官网。

**开源软件声明**  
Ebbinghaus Anywhere 项目使用了以下开源软件和工具：  
Python  
用于项目的核心开发语言。Python 是由 Python Software Foundation 开发和维护的开源软件，遵循 Python Software Foundation License。  
Django  
用于构建项目的后端框架。Django 是由 Django Software Foundation 开发和维护的开源框架，遵循 BSD License。  
MathJax  
用于网页中渲染数学公式。MathJax 是一个开源工具，遵循 Apache License 2.0。  
Bootstrap  
用于前端 UI 的样式设计与组件构建。Bootstrap 是由 Twitter 开发的开源框架，遵循 MIT License。  
MySQL  
用于存储和管理项目数据库。MySQL 是由 Oracle Corporation 开发的开源数据库管理系统，遵循 GPL License（社区版）。  
Flatpickr  
用于日期选择器功能。Flatpickr 是一款轻量级的开源日期选择器插件，遵循 MIT License。  
Stylish Portfolio Bootstrap 模板  
用于前端页面的布局设计。该模板是基于 Bootstrap 的免费模板，遵循 Creative Commons Attribution 3.0 License。  
此外，本项目使用了以下付费服务：  
百度翻译 API：提供文本翻译服务，具体信息请参阅 百度翻译 API 官网.
