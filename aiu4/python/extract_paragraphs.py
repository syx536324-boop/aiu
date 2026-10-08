"""Responsibility: use pdfminer.six layout blocks to preserve page-numbered source paragraphs."""
import json
import re
from pathlib import Path
import sys
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTContainer, LTTextContainer
from pypdf import PdfReader


def text_blocks(node):
    if isinstance(node, LTTextContainer):
        yield node.get_text()
    elif isinstance(node, LTContainer):
        for child in node:
            yield from text_blocks(child)


def extract(source: Path, target: Path):
    reader = PdfReader(source)
    if reader.is_encrypted or len(reader.pages) > 120:
        raise ValueError("Encrypted PDFs or PDFs above 120 pages are not supported.")
    paragraphs, empty_pages = [], []
    characters = 0
    for page, layout in enumerate(extract_pages(source, laparams=LAParams(line_margin=0.3, all_texts=True)), 1):
        count = 0
        for block in text_blocks(layout):
            for part in re.split(r"\n\s*\n", block):
                original = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", part).strip()
                if not original:
                    continue
                count += 1
                characters += len(original)
                if characters > 1_500_000 or len(paragraphs) >= 20_000:
                    raise ValueError("Extracted text exceeds the translation resource limit.")
                paragraphs.append({"id": f"p{page}-{count}", "page": page, "original": original})
        if not count:
            empty_pages.append(page)
    if characters < 100:
        raise ValueError("No usable text layer; OCR is not installed.")
    result = {
        "pages": len(reader.pages), "paragraphs": paragraphs, "emptyPages": empty_pages,
        "method": "pdfminer.six layout text blocks v1",
        "warning": "段落按 PDF 文本块识别，双栏、跨页段落、公式与表格可能断开或顺序不准。只翻译可提取文字；图片中的文字未做 OCR。请对照原始 PDF 核查。",
    }
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    return {"pages": result["pages"], "paragraphs": len(paragraphs), "characters": characters}


if __name__ == "__main__":
    print(json.dumps(extract(Path(sys.argv[1]), Path(sys.argv[2]))))
