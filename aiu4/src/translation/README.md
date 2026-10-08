# 可选中英对照翻译插件

`Translations` 注入 config、Store、Library、Discovery；主程序只组装实例。`translateMetadata(scope,signal,progress)` 翻译当前结果/文献库标题和可获得的摘要；`translateMany(ids,signal,progress)` 收集并翻译整篇可提取正文；`snapshot()` 返回状态及列表译文；`read(id,page)` 返回三页逐段中英配对，不截断正文。

依赖 pdfminer.six 的布局文本块、现有 pypdf 与本机 Ollama 结构化聊天 API。每个原段落拥有独立 ID 和中文字段；长段落内部切片请求，展示时拼回原段落。英文原文不由模型重写。单批不超过 6 段 / 2200 字符，校验返回编号、数量、空值与生成截断，成功后逐批原子保存。失败、停止和重启可继续已有片段。缓存按 PDF SHA-256 / 标题摘要哈希与模型名失效。

全文任务默认最多 2 小时，列表翻译最多 30 分钟，可随时停止；服务进程仍只运行一项任务。`data/papers/ID/bilingual.json` 保存配对和进度，完成后 `bilingual.md` 可直接阅读；列表缓存位于 `data/translations`。本地缓存均不进入 Git。不翻译是纯原文展示，不触发模型。

PDF 缺少原生段落结构，文本块顺序与边界是布局识别结果。跨页段落可能拆开，复杂双栏、图表和公式需查看原 PDF；不对图片执行 OCR，不把翻译当成学术核验或人工译稿。
