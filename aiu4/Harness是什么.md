# Harness 是什么？

## 通俗解释

把 AI 模型想成“会思考的研究员”，Harness 就像给它配好的工作台和工作流程：有哪些工具、资料放哪、做到了哪一步、出错怎么处理、什么时候停下来。

普通模型可以告诉你“建议看某篇论文”。接入 Harness 后，它能调用检索工具找到真实记录，下载原文，再读取页码、写笔记；每一步都留下记录。

## 原理

1. 用户给任务，Harness 把任务、历史和工具说明交给模型。
2. 模型返回文字或结构化工具请求，例如 `collect_paper({id:"react2023"})`。
3. Harness 校验参数，由工具执行下载。工具结果回到对话上下文。
4. 模型依据真实结果继续选择动作，例如 `read_paper`、`save_review`，直到完成、用户停止或达到上限。

它包括 **模型接入、工具执行、状态保存、上下文管理、任务限制、可观察记录**。它不是重新训练一个模型，也不是只写一句人设提示词。

## 本项目怎么参考 Pi Agent

本项目直接使用开源 **Pi Agent Core** 的 `Agent` 和工具循环，并用 **Pi AI** 连接 Ollama 的兼容接口；自己实现领域工具和工作台。

```text
浏览器 / CLI
    ↓ 任务
Harness（Pi Agent + 会话 + 任务限制 + 事件记录）
    ↕ 本机 Ollama：思考与工具请求
    ↓ 参数校验、逐个执行
检索 → 原文下载 → 按页读取 → 评阅卡 / 笔记
    ↓ 真实结果
本地文件与下一轮上下文
```

例如“找智能体主会论文并整理一篇”，不是一个假装完成的长回答，而是若干真实工具步骤。下载失败就保存失败原因；没有读到的实验章节就不能声称已经核查实验。

## 边界

当前实现专注论文发现和阅读，不等同于无人值守完成科研。任务单次运行，最多 10 分钟和 12 轮模型回合；用户可以停止。未接入实验、机械臂、投稿或自动发表。

论文是外部资料，不能改变工具权限；只开放论文来源下载和项目笔记读写，没有任意 shell 工具。AI 评阅仍需人工核查。

## 官方参考

- [Pi Agent Core 与事件/工具接口](https://github.com/earendil-works/pi/tree/main/packages/agent)
- [Pi AI 模型接入](https://github.com/earendil-works/pi/tree/main/packages/ai)
- [Ollama 工具调用](https://docs.ollama.com/capabilities/tool-calling)
- [ICML 2025 正式论文集 PMLR 267](https://proceedings.mlr.press/v267/)
- [NeurIPS 2025 主会论文集](https://proceedings.neurips.cc/paper_files/paper/2025/vol38-main-conference)
