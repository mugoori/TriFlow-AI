"""
MCP Test HTTP Server
파일시스템 MCP 서버의 도구들을 HTTP로 구현

실행: python mcp_test_server.py
포트: 3001
"""
import os
import json
from pathlib import Path
from typing import Any
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="MCP Test Server - Filesystem")

# 테스트 디렉토리
TEST_DIR = Path("C:/temp/mcp_test")
TEST_DIR.mkdir(parents=True, exist_ok=True)

# 테스트 파일 생성
(TEST_DIR / "hello.txt").write_text("Hello from MCP!\nThis is a test file.", encoding="utf-8")
(TEST_DIR / "data.json").write_text(json.dumps({"temperature": 25.5, "humidity": 60, "status": "normal"}), encoding="utf-8")


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict = {}
    id: Any = None


@app.post("/mcp")
async def mcp_call(request: JSONRPCRequest):
    """JSON-RPC 2.0 MCP 호출 처리"""
    method = request.method
    params = request.params or {}
    request_id = request.id

    # tools/list - 사용 가능한 도구 목록
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "read_file",
                        "description": "Read contents of a file",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path to the file"}
                            },
                            "required": ["path"]
                        }
                    },
                    {
                        "name": "write_file",
                        "description": "Write contents to a file",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path to the file"},
                                "content": {"type": "string", "description": "Content to write"}
                            },
                            "required": ["path", "content"]
                        }
                    },
                    {
                        "name": "list_directory",
                        "description": "List files in a directory",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path to the directory"}
                            },
                            "required": ["path"]
                        }
                    },
                    {
                        "name": "get_sensor_data",
                        "description": "Get sensor data from JSON file",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            },
            "id": request_id
        }

    # tools/call - 도구 호출
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # read_file
        if tool_name == "read_file":
            file_path = arguments.get("path", "")
            # 보안: TEST_DIR 내부 파일만 허용
            try:
                full_path = TEST_DIR / Path(file_path).name
                if full_path.exists():
                    content = full_path.read_text(encoding="utf-8")
                    return {
                        "jsonrpc": "2.0",
                        "result": {
                            "content": [{"type": "text", "text": content}]
                        },
                        "id": request_id
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": f"File not found: {file_path}"},
                        "id": request_id
                    }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(e)},
                    "id": request_id
                }

        # write_file
        elif tool_name == "write_file":
            file_path = arguments.get("path", "")
            content = arguments.get("content", "")
            try:
                full_path = TEST_DIR / Path(file_path).name
                full_path.write_text(content, encoding="utf-8")
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "content": [{"type": "text", "text": f"File written: {full_path.name}"}]
                    },
                    "id": request_id
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(e)},
                    "id": request_id
                }

        # list_directory
        elif tool_name == "list_directory":
            try:
                files = [f.name for f in TEST_DIR.iterdir()]
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(files, indent=2)}],
                        "files": files
                    },
                    "id": request_id
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(e)},
                    "id": request_id
                }

        # get_sensor_data
        elif tool_name == "get_sensor_data":
            try:
                data_file = TEST_DIR / "data.json"
                if data_file.exists():
                    data = json.loads(data_file.read_text(encoding="utf-8"))
                    return {
                        "jsonrpc": "2.0",
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(data)}],
                            "sensor_data": data
                        },
                        "id": request_id
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": "Sensor data file not found"},
                        "id": request_id
                    }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(e)},
                    "id": request_id
                }

        else:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                "id": request_id
            }

    # 알 수 없는 메서드
    return {
        "jsonrpc": "2.0",
        "error": {"code": -32601, "message": f"Method not found: {method}"},
        "id": request_id
    }


@app.get("/health")
async def health():
    """헬스체크"""
    return {"status": "healthy", "server": "mcp-filesystem-test"}


@app.get("/")
async def root():
    return {
        "name": "MCP Filesystem Test Server",
        "version": "1.0.0",
        "test_directory": str(TEST_DIR),
        "tools": ["read_file", "write_file", "list_directory", "get_sensor_data"]
    }


if __name__ == "__main__":
    print(f"MCP Test Server starting...")
    print(f"Test directory: {TEST_DIR}")
    print(f"Endpoint: http://localhost:3002/mcp")
    uvicorn.run(app, host="0.0.0.0", port=3002)
