# 架构方案:REST API + NAS 数据同步 + 微信小程序

> 状态:待确认 | 2026-09-11 | 基于 2.0.0.1

## 0. 已确认的决策与总体原则

| 决策点 | 结论 |
|---|---|
| NAS 环境 | 群晖/QNAP,有 Docker → docker-compose 部署 |
| 小程序技术栈 | 原生微信小程序(无跨端框架) |
| 小程序发布形态 | 体验版先行(免 ICP 备案;家人"体验版 + 打开调试"使用) |

**数据原则(延续"保持数据结构便于迁移")**
- 只增不改:现有 `Category` / `Item` / `ReviewDay` / `User` 四张表零改动;新增表全部为增量迁移。
- 单一写入者:PythonAnywhere 是**唯一主数据源(master)**,所有写入(Web UI、小程序)都进 PA;NAS 是只读副本,上面的改动会在下次同步时被覆盖。
- 小程序 API 指向 PA(主数据源),不指向 NAS。

## 1. 总体架构

```
                    ┌───────────────────────────────┐
                    │   PythonAnywhere (master)      │
                    │   ebbinghaus.pythonanywhere.com│
                    │   MySQL · Web UI + REST API    │
                    └──────────┬─────────┬──────────┘
              HTTPS API (token)│         │ ①每日快照
                               │         │  NAS 定时拉取(pull)
              ┌────────────────┘         ▼
              │                   ┌──────────────────┐
              │                   │  NAS (Docker 副本) │
              │         ②写入      │  SQLite · 只读副本 │
              │                   │  群晖定时任务 04:00 │
┌─────────────┴──────┐            └──────────────────┘
│   微信小程序(原生)   │
│   Ellie 的手机端     │
└────────────────────┘
```

三条线:
1. **API(新 Django app `api/`)**——小程序与 NAS 同步共用;
2. **NAS 同步**——NAS 主动拉取(pull)模式:NAS 无需公网可达、不开端口,安防面最小;
3. **小程序**——原生开发,复用同一套 API。

---

## 2. 里程碑 M1:REST API 基座(Django REST Framework) —— ✅ 已完成(2026-09-11)

> 交付物:新 app `api/`(models/serializers/permissions/urls/views 五模块)、
> 11 个端点、51 个 API 测试(全项目 125 个测试全绿)、curl 端到端验收通过。
> 详见本文档 §2.3 端点清单;实现细节见 `api/` 源码与 `api/tests/`。

### 2.1 选型:DRF + Token 认证

- DRF 是 Django 生态标准件,序列化/权限/测试工具齐全,AI 协作与排错资料最多。
- TokenAuthentication(持久 token,存 `authtoken_token` 表)对小程序场景最简单可靠:登录一次长期有效,可在 Django admin 里直接撤销;不需要 JWT 的过期/刷新复杂度。
- API 挂在 `/api/v1/` 下,与现有 Web UI(session 认证)**完全共存、互不影响**;Web 端一行不改。

### 2.2 代码布局(全部为新增文件)

```
api/                        # 新 Django app,与 EAW 平级
├── apps.py
├── models.py               # WeChatProfile(user 1:1, openid unique)
├── serializers.py
├── urls.py                 # /api/v1/...
├── views/
│   ├── auth.py             # login / wechat_login / wechat_bind
│   ├── items.py            # 列表 / 详情 / 新建 / 类别
│   ├── review.py           # 按日期复习 / 反馈
│   └── backup.py           # 全量快照(仅 superuser token)
└── tests/                  # 与 EAW.tests 同风格的测试
```

### 2.3 端点清单(v1)

| Method | Path | 认证 | 说明 |
|---|---|---|---|
| POST | `/api/v1/auth/login/` | 无 | username/password → `{token, user}` |
| POST | `/api/v1/auth/wechat/` | 无 | `{code}` → 已绑定: `{token}`;未绑定: `{bind_required: true}` |
| POST | `/api/v1/auth/wechat/bind/` | 无 | `{code, username, password}` → 绑定 openid 并发 token |
| GET | `/api/v1/me/` | Token | 用户信息 + 统计(总条目/坚持天数/今日待复习数) |
| GET | `/api/v1/categories/` | Token | 类别列表(带条目计数) |
| GET | `/api/v1/review/?date=YYYY-MM-DD` | Token | 按类别分组,**组内按间隔天数升序**(与 Web 端 `review.py` 新增排序一致) |
| POST | `/api/v1/review/feedback/` | Token | `{id, action: yes\|no\|reset}` 单端点替代 Web 的三个 |
| GET | `/api/v1/items/?page=&q=&category=` | Token | 分页列表 + 搜索 |
| GET | `/api/v1/items/{id}/` | Token | 详情(音标/TTS URL/内容原文) |
| POST | `/api/v1/items/` | Token | 新建条目(支持冒号拆分,同 Web) |
| GET | `/api/v1/backup/snapshot/` | Token + superuser | 全量 JSON 快照,供 NAS 拉取 |

数据隔离沿用现有模式:所有查询 `filter(user=request.user)`,API 测试中专门覆盖跨用户访问。

### 2.4 配置与依赖变化

- `requirements.txt` 增:`djangorestframework`(锁版本)
- `settings.py` 增:`rest_framework` / `rest_framework.authtoken` / `api` 三个 app + `REST_FRAMEWORK` 基础配置
- `.env` 增(可选):`WECHAT_APPID` / `WECHAT_SECRET`(不配置时微信登录端点返回明确错误,其余 API 不受影响)
- **迁移影响:仅新增 `authtoken_token` 一张表,PA 升级就是 `git pull + pip install + manage.py migrate`,纯增量**

### 2.5 验收标准

- `manage.py test` 全绿(API 测试 + 原 74 个测试);
- curl 脚本能完成:登录 → 取今日复习 → 提交反馈 → 列表查询 的完整闭环。

---

## 3. 里程碑 M2:NAS 部署 + 每日单向同步 —— ✅ 代码与演练完成(2026-09-11)

> 交付物:`api/snapshot.py`(快照核心库)、`sync_snapshot` / `restore_snapshot` 命令、
> 28 个同步测试(全项目 153 个测试全绿)、`nas-deploy/` 部署物、
> 本地端到端演练通过(19 用户 / 9218 条目,数据逐条一致、幂等、角色守卫生效)。
> 部署步骤见 [DEPLOY_NAS.md](DEPLOY_NAS.md)。

### 3.1 同步模型:pull + 每日全量快照

- **方向**:NAS 每天定时向 PA 的 `/api/v1/backup/snapshot/` 发起 HTTPS 请求(带 superuser token)拉取全量 JSON,NAS 无需公网可达、无需在路由器开任何端口。
- **粒度**:全量快照。家庭数据量(数千条、几 MB JSON)下最简单可靠,幂等可重放。
- **不做增量/双向同步**:单一写入者原则下的 KISS 选择;后续有需要再演进。

### 3.2 快照格式(自定义 JSON,不用 dumpdata)

```json
{
  "meta": {"format": 1, "created_at": "...", "source": "服务方主机名"},
  "users":          [{"id", "username", "email", "first_name", "last_name",
                      "password", "is_staff", "is_active", "is_superuser"}],
  "categories":     [全字段 + pk],
  "review_days":    [全字段 + pk],
  "items":          [全字段 + pk],
  "wechat_profiles": [id, user_id, openid, created_at]
}
```

- **保留主键** → NAS 上条目 id 与 PA 完全一致;
- 含密码哈希 → NAS 副本上的账号登录行为与 PA 一致;
- **不含 authtoken 表** → 令牌是实例本地的,PA 的 syncbot token 在 NAS 上无效,从机制上杜绝跨实例误用;
- 不用 `dumpdata`:auth 的 permissions 外键依赖 contenttypes,跨实例恢复易踩坑;自定义格式只含业务数据,DB 无关(PA 是 MySQL、NAS 是 SQLite 也无影响)。

### 3.3 NAS 端命令(实现名:`sync_snapshot` / `restore_snapshot`)

两个管理命令,共用一个核心库 `api/snapshot.py`:

```
python manage.py sync_snapshot [--keep 7] [--dry-run]   # 每日同步入口(下载→校验→落盘→恢复)
python manage.py restore_snapshot --file snapshot.json  # 离线恢复指定快照文件
```

- 事务内执行:校验 meta 与外键完整性 → 用户 **upsert**(绝不删除 NAS 本地管理员账号)→ Category/ReviewDay/Item/WeChatProfile 全删重建(保留主键,用户外键按"快照 id → 本地用户"映射重写);
- 幂等:重复执行结果一致;失败整体回滚,旧数据保留;
- **先校验后落盘**:非法快照不会保存也不会触碰数据库;
- **角色守卫**:仅当环境变量 `EAW_ROLE=replica` 时允许执行(只在 NAS 的 .env 中设置),且守卫在**下载之前**生效;PA 上不设该变量,即使在 PA 控制台误跑也会直接拒绝——防止旧快照反向覆盖主库。

### 3.4 NAS 部署物(docker-compose) —— ✅ 已实现

```
nas-deploy/
├── docker-compose.yml     # web 服务:gunicorn + whitenoise + SQLite(挂 ./data 卷)
├── Dockerfile             # python:3.11-slim + 主依赖 + gunicorn/whitenoise
├── entrypoint.sh          # 容器启动: migrate → collectstatic → gunicorn
├── .env.example           # SECRET_KEY 与同步 token 模板(复制为 .env)
└── sync.sh                # 同步入口, 由 NAS 任务计划 04:00 调用
```

- 数据卷 `nas-deploy/data/` 同时放 SQLite 数据库与 `snapshots/`(保留最近 7 份,供回滚);
- 仓库根 `.dockerignore` 确保本地数据库/密钥/日志不进镜像;
- 群晖「任务计划」(或 QNAP crontab)每天 **04:00** 执行 `sync.sh`(自动识别 `docker compose` / `docker-compose`);
- 失败处理:任一步骤失败即中止并保留当前库,退出码非 0;群晖任务计划可配置失败邮件通知。

### 3.5 验收标准

- 快照导出→恢复的 roundtrip 测试全绿(含:NAS 本地管理员不被删、重复恢复幂等);
- 未设置 `EAW_ROLE=replica` 的环境(即 PA 形态)执行 restore_snapshot 被拒绝;
- NAS 手动执行一次后,Web UI 数据与 PA 一致;
- 连续 3 天定时同步成功(检查 snapshots 目录与日志)。

**已知限制**:NAS 数据最多落后 PA 24 小时(定位是备份/容灾,主用 PA)。

### 3.6 首次同步引导(bootstrap)

初始数据不需要任何特殊的"初始导入"机制:第一次同步与之后的每日同步走**完全相同的路径**,唯一的引导步骤是铸造快照 token。

1. 部署 M1 到 PA(`git pull` + `pip install` + `migrate`,纯增量);
2. 在 PA Bash 控制台为专用同步账号铸造 token:`python manage.py drf_create_token syncbot`(建议专用 superuser,泄露时只删该账号 token,不影响真人用户);
3. NAS `docker-compose up` → 容器启动自动 `migrate` 建空表 → `createsuperuser` 建 NAS 本地应急管理员;
4. token 写入 NAS `.env`,**手动执行一次** `sync.sh` → 全量数据落库(密码哈希随快照同步,NAS 登录密码 = PA 登录密码,家人无需任何额外设置);
5. 核对 NAS Web UI 与 PA 数据一致后,启用每日 04:00 定时任务。

注意事项:
- 仓库中的 `db.sqlite3` 是 2025-01 的历史开发库,**不是初始数据源**;真实数据只从 PA 现拉,快照 JSON 与数据库引擎无关,PA 为 MySQL 也不影响;
- 首次手动执行即在生产验证了整条同步管线,任何格式/权限问题当天暴露,不留到定时任务里;
- 首日恢复不会删除 NAS 本地管理员(upsert 语义);同名用户以 PA 侧为准。

### 3.7 多实例同代码的角色分工

同一份 git 仓库部署到两处**不会互相干扰**:代码是角色无关的,角色由各实例本地 `.env` 决定,而 `.env` 永不进 git。

| | PythonAnywhere(master) | NAS(replica) |
|---|---|---|
| `EAW_ROLE` | 不设(默认 master) | `replica` |
| 业务 Web UI / API | ✅ 唯一写入入口 | ✅ 数据为 ≤24h 副本,写入无意义(会被覆盖) |
| 快照端点 | ✅ 被 NAS 拉取 | 存在但无人调用 |
| `restore_snapshot` | ❌ 角色守卫拒绝执行 | ✅ 每日执行 |
| `sync.sh` / 定时器 | 不存在、无调度 | ✅ 每天 04:00 |
| token | syncbot token 仅在 PA 有效 | token 全部为本实例铸造 |

---

## 4. 里程碑 M3-M5:微信小程序(原生) —— 🔄 M3 骨架已完成(2026-09-12)

> 交付物:`miniprogram/` 原生小程序工程(4 个页面 + API 封装),
> 已通过 JSON/JS 语法校验,待微信开发者工具联调。
> 使用说明见 [miniprogram/README.md](../miniprogram/README.md)。

### 4.1 工程结构

```
miniprogram/
├── app.js / app.json
├── utils/api.js           # 统一 request 封装:自动注入 token,401 → 跳登录页
├── pages/
│   ├── login/             # 首次绑定(用户名+密码,只需一次)
│   ├── index/             # 首页:统计卡片 + 今日待复习入口
│   ├── review/            # 复习:日期选择 → 分类分组,组内按天数升序
│   ├── review-detail/     # 条目详情 + Yes/No/Reset 按钮
│   ├── items/             # 列表 + 搜索
│   ├── item-detail/       # 详情 + TTS 播放
│   └── input/             # (M4)批量录入
└── components/            # (M4)towxml Markdown 渲染组件
```

### 4.2 登录与绑定流程(code2session)

```
wx.login() → code
POST /api/v1/auth/wechat/ {code}
  ├─ 服务端 code2session 换 openid,已绑定 → {token}   ← 之后全部静默登录
  └─ 未绑定 → {bind_required: true}
       → 用户输入 Web 端的 username/password
       POST /api/v1/auth/wechat/bind/ {code, username, password} → {token}
token 存本地 storage,后续请求带 Authorization: Token xxx
```

- `code2session` 在服务端调用(appsecret 不出后端),走 `requests`(已是现有依赖);
- 新增表 `api_wechatprofile`(1:1 User + unique openid)——**又一个纯增量迁移**。

### 4.3 内容渲染分级(务实策略)

- **M3(核心闭环)**:content 以保留换行的纯文本展示——先让复习跑起来;
- **M4**:接入 **towxml** 渲染 Markdown(标题/列表/粗斜体/代码块/表格)+ KaTeX 数学公式;
- **已知限制**:mhchem 化学式在小程序端无等价渲染器,降级为原文显示(以背单词为主的日常场景影响很小,Web 端不受影响)。

### 4.4 TTS 播放

条目详情返回 `src_tts`,`wx.createInnerAudioContext` 直接播放百度音频 URL;体验版调试模式下域名校验关闭,可直接用。

### 4.5 验收标准

- **M3**:Ellie 的手机(体验版)完成一次完整复习:打开即静默登录 → 看到今日待复习 → 逐条 Yes/No;
- **M4**:小程序覆盖 Web 端日常场景(列表/搜索/详情/TTS/Markdown);
- **M5(按需)**:统计图表、录入页、设置页。

---

## 5. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| PA 免费账户 CPU 配额 | API 并发受限 | 家庭用量小;接口全部分页;上线后观察配额,吃紧再考虑升级 PA(或未来把 API 迁到自有服务器) |
| 同步窗口(≤24h) | NAS 数据滞后 | NAS 定位是备份/容灾;后续可加手动触发按钮 |
| 体验版需开调试 | 新成员首次要"打开调试" | 准备一页图文引导;若将来要免调试,再走 ICP 备案流程(方案已预留:换域名即可,代码不动) |
| mhchem 化学式 | 小程序显示原文 | 文档标注已知限制 |
| token 泄露 | 单用户数据暴露 | authtoken 表可在 admin 撤销;体验版阶段可控 |

## 6. 实施顺序与工作量预估(单人 + AI 协作)

| 里程碑 | 内容 | 预估 | 状态 |
|---|---|---|---|
| M1 | API 基座 + 认证 + 全部业务端点 + 测试 | 1-2 个晚上 | ✅ 已上线(2.1.0.2) |
| M2 | 快照核心库 + sync/restore 命令 + docker-compose + sync.sh + 本地演练 | 1 个晚上 + NAS 侧调试 | ✅ 代码完成,待 NAS 部署 |
| M3 | 小程序骨架 + 绑定登录 + 复习闭环(纯文本) | 2-3 个晚上 | 待开始 |
| M4 | 列表/搜索/详情 + TTS + towxml Markdown | 2 个晚上 | 待开始 |
| M5 | 打磨(统计/录入/体验版分发) | 按需 | 待开始 |

顺序即依赖:M1 是 M2(快照走 API)和 M3(小程序调 API)的共同地基,先行实施。

## 7. 对现有部署的影响清单

- PA 升级 = `git pull` + `pip install -r requirements.txt`(新增 djangorestframework) + `manage.py migrate`(仅新增 authtoken / wechatprofile 表);
- 现有 Web UI、模板、EAW app 代码零改动;
- NAS 为全新部署,不触碰 PA 任何数据。
