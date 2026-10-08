# 本机 API

`serve(app)` 启动 127.0.0.1 上的 HTTP 服务，公开 JSON 操作与 SSE 进度，托管独立 `web` 前端。接口详见根目录架构说明。任务规则由注入的模块处理。

翻译模块经 `app.translations` 注入。`/api/translate` 和 `/api/translate-metadata` 启动可停止任务；`/api/translations`、`/api/translation`、`/api/bilingual-file` 读取结果。正文原文阅读 API 返回当前三页全部可提取文字，不使用模型工具的 11000 字符限制；模型工具继续保留其输入限制。
