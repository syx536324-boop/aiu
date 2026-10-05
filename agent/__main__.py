"""命令行入口：组装 Ollama 客户端与智能体，并启动交互对话。"""

from __future__ import annotations

import os

from agent.ollama_client import OllamaClient, OllamaClientError
from agent.runner import AgentRunner

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def main() -> None:
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
    base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)
    assistant = AgentRunner(
        client=OllamaClient(base_url),
        model=model,
        confirm_tool_action=confirm_file_action,
    )

    print(f"AIU 本地智能体（模型：{model}）")
    print("可进行中文对话、算术计算和本地知识文件问答与管理。")
    print("文件工具仅作用于项目 knowledge 文件夹中的 .md / .txt 文件。")
    print("创建、覆盖和删除前，需要在终端输入对应确认词。")
    print("输入 /clear 清空对话，输入 /exit 退出。")

    while True:
        try:
            user_text = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            return

        if not user_text:
            continue
        if user_text.lower() in {"/exit", "/quit", "exit", "quit"}:
            print("已退出。")
            return
        if user_text.lower() == "/clear":
            assistant.clear_history()
            print("对话记录已清空。")
            continue

        try:
            result = assistant.ask(user_text)
        except OllamaClientError as exc:
            print(f"连接 Ollama 失败：{exc}")
            continue

        for trace in result.tool_traces:
            print(f"工具> {trace.name}({trace.arguments}) → {trace.result}")
        print(f"千问> {result.reply}\n")


def confirm_file_action(action: str, confirmation_phrase: str) -> bool:
    """展示文件变更内容，并要求用户输入精确确认词后才执行。"""
    print("\n文件操作待确认：")
    print(_escape_terminal_controls(action))
    try:
        answer = input(
            f"\n输入 {confirmation_phrase} 确认，其它输入取消："
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消文件操作。")
        return False
    return answer == confirmation_phrase


def _escape_terminal_controls(value: str) -> str:
    """把终端控制字符显示成可见文本，避免确认预览操纵终端显示。"""
    return "".join(
        character
        if character in "\n\t" or ord(character) >= 32 and ord(character) != 127
        else f"\\x{ord(character):02x}"
        for character in value
    )


if __name__ == "__main__":
    main()
