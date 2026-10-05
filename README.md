# AIU 本地 AI 智能体项目

## 当前模型

Ollama 在本机提供模型 API：`http://127.0.0.1:11434`。当前已安装 `qwen3.5:4b`。

直接运行本地 CLI 基线：

```powershell
.\.venv\Scripts\python.exe -m agent
```

## 当前平台目标：Dify

自托管 Dify 已部署到本机 Docker Desktop，Ollama 插件已连接本机 `qwen3.5:4b`。智能体“千问本地智能体”已配置代码计算、时间查询、网页抓取和本机知识文件工具。

启动入口：双击桌面的“启动 Dify 智能体”快捷方式，或运行 `start-dify.ps1`。它会启动 Ollama、Docker Desktop、文件服务和 Dify Compose，并打开智能体页面：`http://127.0.0.1/chat/XDl3dp5fj0mhW7mH`。停止服务运行 `stop-dify.ps1`；该脚本停止文件服务和 Dify，保留数据库和文件卷。Docker Desktop 开机自启动已关闭。

管理控制台：`http://127.0.0.1/signin`。本地管理员账号及智能体 API 密钥保存在 `.setup/dify-admin-credentials.txt` 和 `.setup/dify-agent-api.txt`，两个文件均已限制 Windows 文件访问权限，并由 `.gitignore` 排除。不要把 API 密钥放进浏览器端代码或提交到 GitHub。

完整启动、使用和 API 调用方法见 [Dify 使用说明](Dify使用说明.md)。Dify 通过本机文件 API 列出、读取 `knowledge/` 目录直接下的 `.md`、`.txt` 文件；新建、覆盖和删除先生成待审批请求，由你在本机浏览器确认后执行。桌面的“审批 Dify 文件操作”快捷方式可重新打开审批页面。

## VALORANT 智能体 Web 原型

先启动 Dify 智能体，再运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-valorant-platform.ps1`，浏览器会打开 `http://127.0.0.1:8780`。页面提供本地问答入口、全部特工库和特工详情导航；29 位特工的技能介绍为官网内容的中文摘要，并显示默认 PC 按键；技能点位页提供 13 张常规战术地图的选项，点选地图进入对应的空白页面，后续可补充点位。详情横幅使用网络托管的特工立绘，离线时仍可浏览文字资料，但图片可能无法加载。Dify API 密钥由本机后端从 `.setup/dify-agent-api.txt` 读取，不进入浏览器代码。

仓库配置了 GitHub Pages 静态预览工作流：推送网站前端后会发布 `valorant_platform/web/`。公开预览可浏览特工、技能与地图资料，但智能问答不可用，因为 Python 后端、Dify 和 Ollama 仍运行在本机。所有 Dify 密钥、管理员凭据、文件服务 token 和本机知识文档均被 Git 忽略。首次发布需在仓库的 **Settings → Pages** 中选择 **GitHub Actions** 作为构建源。

## 现有项目内容

- `agent/`：直接调用 Ollama 的模块化 CLI 智能体，含计算器和 `knowledge/` 文件操作工具。
- `file_bridge/`：连接 Dify 与本机知识文件的 HTTP API、OpenAPI 合约及独立审批页面；启动命令为 `.\.venv\Scripts\python.exe -m file_bridge`。
- `knowledge/`：供本地 CLI 智能体与 Dify 文件工具使用的本机知识目录；文档内容不上传到 GitHub。
- `flows/基础聊天问答.json`、`run-langflow.ps1`：此前 Langflow 阶段的流程备份和启动脚本，当前不作为目标平台。
- `start-dify.ps1`、`stop-dify.ps1`：启动 Ollama 与 Dify，或停止 Dify 服务但保留数据。
- `connect-dify-files.ps1`：在本机 Dify 中注册或更新文件工具，并接入现有智能体；通常仅初始化或恢复配置时需要运行。
- `valorant_platform/`：VALORANT 特工问答与资料库 Web 应用；Python 标准库提供本机后端，浏览器原生 HTML/CSS/JavaScript 提供界面。

## Python 环境

项目使用 Python 3.12 和 `uv`。首次安装依赖：

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD ".uv-cache"
uv sync
```

Langflow 依赖仍在锁文件中，因为旧流程和环境暂时保留。Dify Compose 文件和本机数据保存在被忽略的 `.setup/dify-src/docker/` 目录。
