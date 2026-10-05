# VALORANT Platform

本模块提供 AIU 的本地 VALORANT 问答网页、29 人特工目录和技能资料页导航。角色名单以 [Riot 官方特工页面](https://playvalorant.com/en-us/agents/)为准。每位特工详情页列出技能名称、中文摘要和默认 PC 按键，并链接到对应 Riot 官方资料；摘要以自己的话概括主要效果，具体数值和当前版本机制以游戏内及官网为准。用户可在游戏设置中更改按键。技能点位页列出 13 张常规战术地图，选中地图后进入对应的空白页面，后续再补充点位内容；团队乱斗地图与靶场不在此列表中。特工立绘由 `media.valorant-api.com` 托管，加载图片需要联网；文字资料仍由本地静态数据提供。对话请求由本模块在服务端加入“沉迷无畏契约的高分段玩家”人设，再转发给现有 Dify 智能体；Dify Studio 中原有提示词不改动。

地图选项为：源工重镇（Bind）、隐世修所（Haven）、霓虹町（Split）、亚海悬城（Ascent）、森寒冬港（Icebox）、微风岛屿（Breeze）、裂变峡谷（Fracture）、深海明珠（Pearl）、莲华古城（Lotus）、日落之城（Sunset）、幽邃地窟（Abyss）、盐海矿镇（Corrode）和天枢云阙（Summit）。地图目录参考[无畏契约地图导航页](https://wiki.biligame.com/valorant/Portal:%E5%9C%B0%E5%9B%BE)。

## 入口与接口

- 启动入口：项目根目录 `start-valorant-platform.ps1`，或在 `aiu` 根目录运行 `..venv\Scripts\python.exe -m valorant_platform`。
- 默认地址：`http://127.0.0.1:8780`；HTTP 服务只监听本机回环地址。
- 前端：`web/index.html`、`web/app.css`、`web/app.js`。
- 角色数据：`web/agents.json`，同时作为同源静态资源提供给前端。
- 后端：`server.py` 的 `POST /api/chat` 代理 Dify 流式聊天，`GET /api/health` 提供就绪状态。API 密钥只从服务端读取。
- Dify API 默认为 `http://127.0.0.1/v1`，可通过 `DIFY_API_BASE` 覆盖。密钥文件默认为 `.setup/dify-agent-api.txt`，可用 `DIFY_API_KEY_FILE` 覆盖。

本模块可在本机完整运行，也可作为 GitHub Pages 静态预览发布。本机运行时先启动 Dify 智能体，再启动本模块；访问 Dify 未启动时，资料库仍可浏览，聊天会显示连接提示。GitHub Pages 预览中会明确关闭聊天输入，仅开放前端资料库；Python 服务和本机 Ollama 不会随静态页面上传。
