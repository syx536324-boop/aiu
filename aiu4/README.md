# 华小牛 · AIU4

专注寻找和阅读高质量 AI 论文的本地 Harness。复用 [Pi Agent Core](https://github.com/earendil-works/pi/tree/main/packages/agent) 的智能体循环，接入本机 Ollama，提供官方出处检索、PDF 下载、正文读取、评阅卡与会话保存。

统一仓库中的本项目位于 `aiu4/`。以下命令在该目录打开的 PowerShell 中执行；本机独立安装仍可继续使用原有 `E:\aiu4` 目录。

## 打开

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-aiu4.ps1
```

浏览器地址：<http://127.0.0.1:8784/>。桌面快捷方式也会启动服务并打开页面。

首次安装或重建环境：`powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-aiu4.ps1`。需要 Node.js 22.19+、uv；脚本复用已装 Node，将 Python、依赖和缓存放在本项目。已安装的依赖由 package-lock.json、uv.lock 固定。

停止：`powershell -NoProfile -ExecutionPolicy Bypass -File .\stop-aiu4.ps1`。

对话模型名 `aiu4-research:latest` 是现有 `qwen3.5:4b` 权重的本地配置别名，使用 Modelfile 设置 16K 上下文；不重新训练或下载一套大权重。模型缺失时需要先自行安装基础模型，启动器不会自动拉取。

## 核心功能

- 官方在线目录：ICML 2025、NeurIPS 2025 主会；另有 8 篇经核对的基础论文。扩展索引支持 Semantic Scholar / Crossref，候选出处标为待核对。
- 按研究词初筛，不把引用量或会议名当作质量结论。公开索引可能限流，结果显示实际来源与失败信息。
- 原始 PDF、页码文本、BibTeX、来源与 SHA-256 保存在 `data/papers`。PDF 仅提取文本层，不含 OCR。
- 在线找论文、我的文献库支持可选翻译插件：不翻译 / 全文中英对照。每个段落保留英文原文并紧接中文译文；标题摘要可单独翻译，全文按整篇可提取文字处理，支持停止、续翻和导出 `.md`。使用现有本机模型，无需翻译账号或 API 密钥。
- Pi 驱动本地模型调用工具，研究会话与执行事件持久化；10 分钟、12 轮工具回合上限。
- 评阅卡写出研究问题、方法、证据页、复现条件、局限和阅读建议，明确是需要人工核查的 AI 草稿。

## 目录

`src/main.mjs` 只组装模块；`src/core` 管循环/会话/任务；`src/research` 管检索与论文；`src/translation` 管翻译与缓存；`src/providers` 接模型；`src/tools` 管笔记；`src/web` 暴露 API；`web` 是独立前端；`python` 转换 PDF。前后端通过 HTTP JSON 和 SSE 进度事件通信。

详情见 [使用说明](使用说明.md)、[Harness 是什么](Harness是什么.md)、[论文筛选标准](论文筛选标准.md)、[架构说明](架构说明.md)。

## 数据与配置

默认模型 `aiu4-research:latest`（复用 `qwen3.5:4b` 权重，16K 上下文），默认端口 `8784`。本机覆盖配置放 `.runtime/config.json`，不要提交账号或密钥。`.gitignore` 排除论文下载、个人笔记、会话、日志、环境、缓存及 `.env`。

检索和下载会访问公开论文服务；对话通过本机 Ollama。项目只监听本机，没有公网发布、定时爬取、实验运行、机械臂或投稿功能。

翻译插件复用 [Ollama 结构化输出](https://docs.ollama.com/capabilities/structured-outputs) 与 [pdfminer.six 段落布局识别](https://pdfminersix.readthedocs.io/en/latest/tutorial/extract_pages.html)。全文翻译任务最长 2 小时，列表翻译最长 30 分钟；均与其他任务共享单任务限制。机器译文和 PDF 段落边界需要核查，图片文字未做 OCR。
