# PDF 文本提取

`extract_pdf.py 输入.pdf 输出.md` 使用 pypdf 提取文本层，按原 PDF 页码写入 `## Page N`，返回 JSON 页数和字符数。由论文模块调用项目 `.venv` 中的 Python；不含 OCR，图表公式看原文。

`extract_paragraphs.py 输入.pdf 输出.json` 使用 pdfminer.six 的布局文本块识别原文段落，保留页码与段落 ID，供全文翻译插件使用。最多 120 页、150 万字符、2 万文本块；英文原段落保留断行，不由翻译模型重新生成。PDF 文本块与真正的语义段落可能不完全一致，跨页段落和双栏需对照原 PDF。依赖由根目录 uv.lock 锁定。
