"""Ebbinghaus Anywhere REST API (v1)。

为微信小程序与 NAS 数据同步提供接口:
- 认证: 账号密码 / 微信 code2session 绑定 (TokenAuthentication)
- 业务: 用户概览 / 类别 / 复习 / 复习反馈 / 条目列表与详情
- 运维: 全量快照 (仅 superuser, 供 NAS 每日拉取)

所有查询均按 request.user 隔离,与 Web 端一致。
"""
