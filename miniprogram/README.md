# 万物皆可艾宾浩斯 · 微信小程序端

Ebbinghaus Anywhere 的微信小程序客户端，复用主站(PythonAnywhere)的 REST API。

## 功能范围(M3)

- 微信静默登录 + 首次绑定（用主站账号密码绑定一次，之后自动登录）
- 首页统计：今日待复习 / 条目总数 / 坚持天数
- 复习闭环：按日期拉取复习清单 → 查看条目 → YES / NO / RESET 反馈
- 发音播放（百度 TTS 链接）
- 条目内容暂以纯文本展示（M4 接入 Markdown / LaTeX 渲染）

## 用微信开发者工具打开

1. 安装[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)（Windows 稳定版）
2. 「导入项目」→ 目录选择本文件夹（`miniprogram/`）
3. AppID 填你自己的小程序 AppID（**不要填 AppSecret**，它只放服务端）
4. 打开即可预览。项目默认已关闭「合法域名校验」（`project.config.json` 里 `urlCheck: false`），
   开发阶段无需配置服务器域名

> **请用「导入项目」，不要用「新建项目」**（后者会从模板生成新代码）。
> 若对话框询问选项：**开发模式选「小程序」，后端服务选「不使用云服务」**——
> 本项目后端是自建的 PythonAnywhere API，不用微信云开发。

## 后端配置（一次性）

PA 的 `.env` 需要配置（服务端调微信 code2session 用）：

```
WECHAT_APPID=wx...
WECHAT_SECRET=...
```

配置后到 PA「Web」标签页点一次 Reload。
**在此之前**微信登录会失败——此时可用登录页底部的「仅登录（暂不绑定微信）」按钮调试。

## 手机体验版

1. 管理后台 → 成员管理 → 添加「体验成员」（家人的微信号）
2. 开发者工具 → 上传 → 管理后台把该版本设为「体验版」
3. **手机打开体验版 → 右上角胶囊「…」→ 开发调试 → 打开调试**（每个家人首次都要做一次，此后长期有效）

> **为什么必须「打开调试」**：真机上的开发版/体验版会强制校验「服务器域名白名单」，
> 而本项目后端在 pythonanywhere.com，无法加入白名单（微信要求域名有 ICP 备案）。
> 打开调试后该校验被跳过，请求才能发出去。
> **未打开调试的症状**：登录时提示「网络异常」（请求根本没离开手机）。
>
> 将来若需免调试直接使用（如给不熟悉操作的长辈），需换用**已备案域名**并加入
> 小程序后台的「request 合法域名」——这是正式发布时的必经步骤。

## 结构

```
app.js / app.json / app.wxss   入口、页面注册、全局样式
utils/api.js                   API 封装（令牌注入、401 处理、全部端点）
utils/util.js                  小工具（本地日期等）
pages/login                    登录 / 微信绑定
pages/index                    首页统计
pages/review                   复习清单（按日期）
pages/item                     条目详情 + YES / NO / RESET
```

## 改环境

后端地址在 `utils/api.js` 顶部的 `BASE_URL`（默认指向
`https://ebbinghaus.pythonanywhere.com/api/v1`）。
