# CMMS Local API

## 项目简介
这是一个本地 CMMS LLM API 包装器，运行在 Windows 上。

- 使用本地 `Ollama` 的 `qwen3:8b` 模型
- 提供受控的 CMMS 工单 intake AI 辅助接口
- 仅用于摘要、字段提取、规则验证和草稿生成
- 不直接写入 CMMS、不创建工单、不审批、不发送邮件

## 快速启动

1. 创建并激活 Python 虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

2. 安装依赖：

```powershell
pip install -r requirements.txt
```

3. 设置 AI API key：

```powershell
$env:LLM_API_KEY="your-secret-key"
```

4. 启动服务：

```powershell
uvicorn main:app --host 127.0.0.1 --port 8000
```

5. 打开浏览器访问：

```text
http://127.0.0.1:8000
```

## 推荐启动方式

运行以下脚本启动本地服务：

```powershell
.\Start-CMMS-LLM-API.ps1
```

或双击：

```text
Start-CMMS-LLM-API.bat
```

## 主要 API 端点

- `GET /health`
- `POST /api/ai/summarize-work-order`
- `POST /api/ai/extract-work-order-fields`
- `POST /api/ai/cmms-intake`
- `GET /ui`

## 目标

这个项目旨在为 CMMS 工作单 intake 提供一个安全、可审计的本地 AI 辅助层。它的设计原则是“AI 只建议，不越权”。

The UI calls only the controlled advisory endpoints. It is not a generic chat interface.

The UI also includes a local process log panel and local-only controls for:

- Checking service/Ollama status.
- Viewing recent log lines.
- Generating named API keys.
- Disabling generated API keys.
- Starting Ollama if it is stopped.
- Stopping Ollama.
- Stopping the FastAPI service.

System control endpoints require an authenticated admin portal session and are restricted to local requests from `127.0.0.1` or `::1`.
API key generation, disabling, user management, environment management, and process controls require an admin portal session.

## Logs

Runtime logs are written to:

```text
logs/cmms-llm-api.log
```

The API logs:

- Service startup and shutdown.
- API calls with method, path, status, duration, and client IP.
- API calls by `key_id` and key name.
- Ollama start/stop requests from the local UI.

The API does not log API keys.

## API keys

The environment variable `LLM_API_KEY` is a compatibility API key for direct AI endpoint calls only.
It must not be used for portal administration and cannot access `/api/admin/*`.
Generated API key records are stored in SQLite:

```text
data/portal.db
```

Generated keys:

- Are shown only once when created.
- Must be copied from the `api_key` field, not the `key_id` field.
- Are stored as SHA-256 hashes, not plaintext.
- Can be disabled from the local UI.
- Can call the controlled AI endpoints while enabled.
- Cannot access admin endpoints.
- Are logged by `key_id` and name for usage tracking.

Do not commit `api_keys.json`.

## Environments

Admin users can create environment codes in the portal. API calls can pass:

```json
{
  "environment_code": "DEFAULT",
  "text": "The air conditioner in ARC room 205 is making loud noise."
}
```

When `environment_code` is provided, the API loads buildings, rooms, priorities, work order types, assignment values, employee numbers, and job types from the saved environment configuration.

The older `valid_buildings` and `valid_priorities` request shape still works for compatibility.
