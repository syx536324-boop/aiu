# 本地模型

`createLocalModel(config)` 使用 Pi AI 的 OpenAI completions 适配器连接本机 Ollama；`modelStatus` 读模型列表。只允许 localhost 模型地址，模型名在配置中指定。检索和收集不依赖模型在线。

`translator.mjs` 的 `translateSegments(config,items,signal)` 使用 Ollama `/api/chat` 的 JSON schema 结构化输出翻译已有段落片段，关闭思考输出、保留取消信号，并校验返回编号、数量和生成截断。翻译不拥有工具调用或文件操作权限，源文只作为待翻译数据。参考官方接口：https://docs.ollama.com/api/chat 。
