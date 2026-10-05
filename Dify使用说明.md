# Dify 使用说明

## 启动和打开智能体

1. 双击桌面的 **启动 Dify 智能体** 快捷方式。首次启动 Docker Desktop 可能需要一两分钟。
2. 启动脚本会确保 Ollama 中的 `qwen3.5:4b`、Docker Engine、本机文件服务和 Dify 就绪，然后打开智能体页面。
3. 智能体页面：<http://127.0.0.1/chat/XDl3dp5fj0mhW7mH>
4. Dify 管理控制台：<http://127.0.0.1/signin>

本机管理员账号为 `admin@aiu.local`。首次设置生成的密码保存在 `.setup/dify-admin-credentials.txt`。Docker Desktop 的开机自启动已关闭，因此需要使用桌面快捷方式手动启动。

## 智能体能做什么

“千问本地智能体”使用本机 Ollama 的 `qwen3.5:4b`，已开启这些能力：

- 中文对话和问题解答。
- 通过代码解释器进行精确计算与简单数据处理。
- 通过时间工具查询当前时间。
- 根据用户给出的链接抓取并总结网页。
- 列出和读取 `C:\Users\shao\Desktop\aiu\knowledge` 中的文本文件，并按你的指示提出新建、覆盖或删除请求。

## 用自然语言操作本机文件

文件工具只接受 `knowledge` 文件夹直接下的 `.md`、`.txt` 文件名。可以在同一段 Dify 对话中这样说：

- “列出我的知识文件。”
- “读取示例资料.md，告诉我里面有哪些内容。”
- “新建备忘录.md，内容是：明天下午三点整理资料。”
- “把备忘录.md 中的三点改为四点，保留其余内容。”
- “删除备忘录.md。”

读取和列出会直接返回结果。新建、覆盖或删除时，智能体只提交请求，本机会打开 **AIU 文件操作审批** 页面。核对文件名与拟写入内容后点击“批准此操作”；也可以点击“拒绝”。如果页面没有自动打开，双击桌面的 **审批 Dify 文件操作** 快捷方式。

审批后回到原来的 Dify 对话，说“已批准，请查询刚才操作的结果”。智能体查询到 `completed` 才会报告完成。每条待审批请求有效期为 15 分钟；重启文件服务会清除尚未处理的请求。

文件需为 UTF-8 编码。读取上限为 1 MB，最多向模型返回前 12,000 个字符；新建或覆盖的内容最多 12,000 个字符，原文件超过这个长度时不允许覆盖。其他项目代码、子目录和 Windows 系统文件不在此工具的可访问范围内。PDF、Word 等资料仍可通过 Dify 上传或知识库处理。

## 停止服务

在 PowerShell 中运行：

```powershell
& "$env:USERPROFILE\Desktop\aiu\stop-dify.ps1"
```

也可以双击桌面的 **停止 Dify 服务**。这会停止本机文件服务和 Dify 容器，并保留数据库、知识库及其他 Docker 数据卷。不要运行 `docker compose down -v`，该命令会删除数据卷。

## 文件工具的启动与恢复

平时使用桌面启动快捷方式即可。文件服务的独立启动命令为：

```powershell
Set-Location "$env:USERPROFILE\Desktop\aiu"
.\.venv\Scripts\python.exe -m file_bridge
```

服务只监听本机 `127.0.0.1:8765`。Dify 通过 `host.docker.internal:8765` 调用带 Bearer 认证的 API。模型凭据和本机审批凭据分别保存在受 Windows 权限保护的 `.setup/` 文件中，审批凭据不会提供给 Dify。

如果需要向当前智能体同步文件工具定义、提示词或重新生成的 API 令牌，先启动服务，再在项目目录运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\connect-dify-files.ps1`。该脚本会读取本机保存的 Dify 管理员凭据，更新工具及现有智能体配置。

## 通过 API 接入自己的程序

API 地址为 `http://127.0.0.1/v1`。智能体 API 密钥保存在 `.setup/dify-agent-api.txt`。密钥只应由本机后端或受信任的本地程序读取，不要写进网页前端代码，也不要提交到 GitHub。

PowerShell 调用示例：

```powershell
$apiKey = (Get-Content .setup\dify-agent-api.txt | Where-Object { $_ -like 'API key: *' }) -replace '^API key: ', ''
$body = @{
    inputs = @{}
    query = '请用代码计算 (17 + 25) * 3，并说明步骤。'
    response_mode = 'blocking'
    user = 'aiu-local-user'
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
    -Uri 'http://127.0.0.1/v1/chat-messages' `
    -Method Post `
    -Headers @{ Authorization = "Bearer $apiKey" } `
    -ContentType 'application/json' `
    -Body $body
```

模型和 Dify 服务都在本机运行。使用 API 前需先通过桌面快捷方式启动；不需要 Ollama 云端 API Key。
