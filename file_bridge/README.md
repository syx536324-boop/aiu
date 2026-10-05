# AIU 文件桥接服务

本目录为自托管 Dify 提供 HTTP 文件工具。服务只监听 Windows 本机的 127.0.0.1:8765；Docker 内的 Dify 使用 host.docker.internal:8765 访问。工具只列出、读取或提出对项目 knowledge 文件夹直接子文件的修改请求，文件类型限 .md 和 .txt。

## 模块

- __main__.py：加载凭据、启动服务，以及打开审批页或停止服务的命令入口。
- config.py：本机监听配置、受限凭据文件和 PID 文件。
- knowledge.py：验证目录、文件名和内容，复用 agent.knowledge 的约束及新建实现。
- safe_file.py：通过 Windows 文件句柄锁定并核对最终路径，再读取、覆盖或删除。
- approvals.py：15 分钟过期的一次性审批队列。
- http.py：JSON API、本机浏览器审批页和独立审批会话。
- schema.py：供 Dify 导入的 OpenAPI 合约。
- dify_instructions.txt：注册脚本写入 Dify 智能体的中文文件操作说明。

## 启动

在 C:\Users\shao\Desktop\aiu 目录运行：

    .\.venv\Scripts\python.exe -m file_bridge

首启自动生成 .setup/file-bridge-token.txt，文件内只有一行随机 Bearer token。Windows ACL 仅允许当前用户、SYSTEM 和 Administrators 访问。启动成功后写 .setup/file-bridge.pid；正常停止时删除 PID 和本次运行的审批密钥。API token 保留供 Dify 使用。

健康检查为 GET http://127.0.0.1:8765/health，返回 {"status":"ok","service":"aiu-file-bridge"}。OpenAPI 文档为 GET http://127.0.0.1:8765/openapi.json，文档中的服务地址指向 http://host.docker.internal:8765。文件接口均需 Authorization: Bearer <token>。

根目录 `connect-dify-files.ps1` 将此 OpenAPI 和凭据注册到现有 Dify 智能体。当前本机 Dify 的 Squid 配置仅额外放行 `host.docker.internal:8765`，以供自定义工具调用。

## 本机审批

列出和读取文件直接返回。新建、完整覆盖及删除只会产生待审批编号；Dify 不会得到审批密钥，也不能凭工具参数批准。首个待审批请求会尝试自动打开本机浏览器。浏览器中会显示操作、文件名及拟写入的完整内容，用户点击“批准此操作”后才会执行。审批前会再次核对原文件状态；若已变化，需要重新发起请求。待审批请求 15 分钟后失效，同一编号只执行一次。

如果审批页没有自动打开，在项目根目录运行：

    .\.venv\Scripts\python.exe -m file_bridge --approve

审批入口使用独立的本机密钥和浏览器会话，并校验表单令牌。该密钥不在 OpenAPI 文档及 Dify 工具响应中出现。用户在审批页拒绝后，文件保持原状。Dify 可用操作编号查询最终状态。

覆盖前，原文件必须为 UTF-8、最多 1 MB 且不超过 12000 字符，避免模型基于截断内容覆盖文档。覆盖在锁定的 Windows 文件句柄上完成；若写入报错会尝试恢复原内容。计算机在写入瞬间掉电时，仍可能留下部分内容，重要文件应另有备份。

温和停止文件服务：

    .\.venv\Scripts\python.exe -m file_bridge --stop
