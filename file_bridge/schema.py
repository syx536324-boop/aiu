"""Dify 可导入的 OpenAPI 合约：只公开需要 Bearer 认证的模型工具。"""

from __future__ import annotations

from typing import Any

from .config import DEFAULT_PORT


def _json_response(schema: dict[str, Any], description: str = "成功") -> dict[str, Any]:
    return {
        "200": {
            "description": description,
            "content": {"application/json": {"schema": schema}},
        }
    }


def _mutation_body(with_content: bool) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "filename": {
            "type": "string",
            "description": "knowledge 文件夹直接子文件的文件名，只能以 .md 或 .txt 结尾。",
        }
    }
    required = ["filename"]
    if with_content:
        properties["content"] = {
            "type": "string",
            "description": "完整 UTF-8 文件内容，最多 12000 字符。覆盖操作将替换全部原内容。",
        }
        required.append("content")
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": required,
                    "additionalProperties": False,
                    "properties": properties,
                }
            }
        },
    }


def _mutation_path(action: str, summary: str, with_content: bool) -> dict[str, Any]:
    return {
        "post": {
            "operationId": f"request_{action}_knowledge_file",
            "summary": summary,
            "description": (
                "只提交待审批请求；服务不会立即更改文件。"
                "电脑使用者必须在独立的本机审批界面确认，随后可查询操作状态。"
            ),
            "requestBody": _mutation_body(with_content),
            "responses": _json_response(
                {"$ref": "#/components/schemas/OperationStatus"},
                "返回待审批操作编号与状态",
            ),
        }
    }


def openapi_document() -> dict[str, Any]:
    """构造不含任何凭据或本机审批入口的工具规范。"""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "AIU 本地知识文件工具",
            "version": "1.0.0",
            "description": (
                "仅操作本机 aiu/knowledge 文件夹直接下的 .md/.txt 文件。"
                "列出和读取可直接执行；新建、覆盖、删除须由电脑使用者独立批准。"
            ),
        },
        "servers": [{"url": f"http://host.docker.internal:{DEFAULT_PORT}"}],
        "security": [{"BearerAuth": []}],
        "paths": {
            "/files": {
                "get": {
                    "operationId": "list_knowledge_files",
                    "summary": "列出可用知识文件",
                    "responses": _json_response(
                        {
                            "type": "object",
                            "required": ["files"],
                            "properties": {
                                "files": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                }
                            },
                        }
                    ),
                }
            },
            "/files/read": {
                "get": {
                    "operationId": "read_knowledge_file",
                    "summary": "读取知识文件内容",
                    "parameters": [
                        {
                            "name": "filename",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "knowledge 文件夹直接子文件的文件名。",
                        }
                    ],
                    "responses": _json_response(
                        {
                            "type": "object",
                            "required": ["filename", "content", "truncated"],
                            "properties": {
                                "filename": {"type": "string"},
                                "content": {"type": "string"},
                                "truncated": {"type": "boolean"},
                            },
                        }
                    ),
                }
            },
            "/files/create": _mutation_path(
                "create", "请求新建知识文件，须用户批准", True
            ),
            "/files/replace": _mutation_path(
                "replace", "请求完整覆盖知识文件，须用户批准", True
            ),
            "/files/delete": _mutation_path(
                "delete", "请求删除知识文件，须用户批准", False
            ),
            "/operations/{operation_id}": {
                "get": {
                    "operationId": "get_knowledge_file_operation",
                    "summary": "查询待审批文件操作的结果",
                    "parameters": [
                        {
                            "name": "operation_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "提交文件操作时返回的操作编号。",
                        }
                    ],
                    "responses": _json_response(
                        {"$ref": "#/components/schemas/OperationStatus"}
                    ),
                }
            },
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer"}
            },
            "schemas": {
                "OperationStatus": {
                    "type": "object",
                    "required": ["operation_id", "action", "filename", "status", "message"],
                    "properties": {
                        "operation_id": {"type": "string"},
                        "action": {
                            "type": "string",
                            "enum": ["create", "replace", "delete"],
                        },
                        "filename": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": [
                                "pending_approval", "executing", "completed",
                                "rejected", "expired", "failed",
                            ],
                        },
                        "message": {"type": "string"},
                        "expires_in_seconds": {"type": "integer"},
                    },
                }
            },
        },
    }
