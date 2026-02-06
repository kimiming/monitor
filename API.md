# 🚀 API 文档

本文档详细说明了所有可用的 API 接口及其使用方法。

## 📋 基础信息

- **基础 URL**: `http://localhost:5000`
- **Content-Type**: `application/json`
- **CORS**: 已启用，支持跨域请求

---

## 🔧 系统管理 API

### 1. 获取系统状态

获取当前系统的运行状态、账号状态等信息。

```http
GET /api/system/status
```

**响应示例:**

```json
{
  "status": "running",
  "monitor": {
    "session_name": "monitor",
    "is_active": true,
    "phone_number": "+1234567890",
    "user_id": 123456789,
    "login_time": 1674826400,
    "last_check_time": 1674826500
  },
  "senders": [
    {
      "session_name": "sender_1",
      "is_active": true,
      "phone_number": "+0987654321",
      "user_id": 987654321,
      "login_time": 1674826410,
      "last_check_time": 1674826510
    }
  ],
  "queue_size": 5,
  "timestamp": "2024-01-27T10:30:00"
}
```

---

### 2. 获取系统统计

获取指定天数内的消息统计数据。

```http
GET /api/system/stats?days=7
```

**查询参数:**

- `days` (int, 可选): 统计天数，默认为 7

**响应示例:**

```json
{
  "total_messages": 1250,
  "total_senders": 5,
  "days": 7,
  "stats": [
    {
      "sender_name": "sender_1",
      "target_group": "@my_group",
      "message_count": 250,
      "last_forward_time": 1674826500,
      "created_date": "2024-01-27"
    }
  ],
  "timestamp": "2024-01-27T10:30:00"
}
```

---

## ⚙️ 配置管理 API

### 1. 获取所有配置

```http
GET /api/config/all
```

**响应示例:**

```json
{
  "telegram": {
    "monitor_account_id": 6,
    "monitor_api_hash": "xxxx",
    "shared_api_id": 6,
    "shared_api_hash": "xxxx",
    "alert_group": "@aopame3",
    "source_groups": ["@asfaaasfa1"],
    "my_group": "@hgfher2"
  },
  "proxy": {
    "use_proxy": false,
    "proxy_type": "SOCKS5",
    "proxy_host": "127.0.0.1",
    "proxy_port": 7897,
    "proxy_username": "",
    "proxy_password": ""
  },
  "filter": {
    "keywords": ["广告", "加粉", "http"],
    "max_file_size_mb": 10
  },
  "system": {
    "max_concurrent_tasks": 3,
    "msg_queue_size": 500,
    "auto_check_interval": 30,
    "check_status_interval": 30
  }
}
```

---

### 2. 获取 Telegram 配置

```http
GET /api/config/telegram
```

---

### 3. 更新 Telegram 配置

```http
POST /api/config/telegram
```

**请求体:**

```json
{
  "alert_group": "@new_alert_group",
  "source_groups": ["@group1", "@group2"],
  "my_group": "@new_target_group"
}
```

---

### 4. 获取代理配置

```http
GET /api/config/proxy
```

---

### 5. 更新代理配置

```http
POST /api/config/proxy
```

**请求体:**

```json
{
  "use_proxy": true,
  "proxy_type": "SOCKS5",
  "proxy_host": "proxy.example.com",
  "proxy_port": 1080,
  "proxy_username": "user",
  "proxy_password": "pass"
}
```

---

### 6. 获取过滤配置

```http
GET /api/config/filter
```

---

### 7. 更新过滤配置

```http
POST /api/config/filter
```

**请求体:**

```json
{
  "keywords": ["广告", "加粉", "http", "t.me"],
  "max_file_size_mb": 50
}
```

---

### 8. 获取系统配置

```http
GET /api/config/system
```

---

### 9. 更新系统配置

```http
POST /api/config/system
```

**请求体:**

```json
{
  "max_concurrent_tasks": 5,
  "msg_queue_size": 1000,
  "auto_check_interval": 60
}
```

---

## 👤 监控号管理 API

### 1. 监控号登录

登录监控号账户。

```http
POST /api/monitor/login
```

**响应示例:**

```json
{
  "message": "✅ 监控号已登录",
  "status": "active"
}
```

---

### 2. 监控号退登

退登监控号账户。

```http
POST /api/monitor/logout
```

**响应示例:**

```json
{
  "message": "✅ 监控号已退登"
}
```

---

### 3. 获取监控号状态

获取监控号的当前状态。

```http
GET /api/monitor/status
```

**响应示例:**

```json
{
  "session_name": "monitor",
  "is_active": true,
  "phone_number": "+1234567890",
  "user_id": 123456789,
  "login_time": 1674826400,
  "last_check_time": 1674826500
}
```

---

## 🎭 克隆号管理 API

### 1. 登录所有克隆号

登录所有可用的克隆号。

```http
POST /api/senders/login-all
```

**响应示例:**

```json
{
  "message": "✅ 成功登录 5 个克隆号",
  "count": 5
}
```

---

### 2. 退登所有克隆号

退登所有克隆号。

```http
POST /api/senders/logout-all
```

**响应示例:**

```json
{
  "message": "✅ 成功退登 5 个克隆号",
  "count": 5
}
```

---

### 3. 登录指定克隆号

登录指定的克隆号。

```http
POST /api/senders/login/<session_name>
```

**路径参数:**

- `session_name`: 克隆号会话名称 (例如: sender_1)

**响应示例:**

```json
{
  "message": "✅ sender_1 已登录"
}
```

---

### 4. 退登指定克隆号

退登指定的克隆号。

```http
POST /api/senders/logout/<session_name>
```

**响应示例:**

```json
{
  "message": "✅ sender_1 已退登"
}
```

---

### 5. 获取所有克隆号状态

获取所有克隆号的状态信息。

```http
GET /api/senders/status
```

**响应示例:**

```json
{
  "senders": [
    {
      "session_name": "sender_1",
      "is_active": true,
      "phone_number": "+1111111111",
      "user_id": 111111111,
      "login_time": 1674826410,
      "last_check_time": 1674826510
    },
    {
      "session_name": "sender_2",
      "is_active": false,
      "phone_number": null,
      "user_id": null,
      "login_time": null,
      "last_check_time": null
    }
  ]
}
```

---

## 🎬 脚本控制 API

### 1. 启动脚本

启动整个系统 (登录账号、启动消息工人等)。

```http
POST /api/script/start
```

**响应示例:**

```json
{
  "message": "✅ 脚本已启动"
}
```

---

### 2. 停止脚本

停止整个系统。

```http
POST /api/script/stop
```

**响应示例:**

```json
{
  "message": "✅ 脚本已停止"
}
```

---

## 📋 日志 API

### 1. 获取最近日志

获取内存中的最近日志。

```http
GET /api/logs/recent?level=INFO&limit=100
```

**查询参数:**

- `level` (string, 可选): 日志级别 (INFO, WARNING, ERROR)
- `limit` (int, 可选): 返回数量，默认 100

**响应示例:**

```json
{
  "logs": [
    {
      "timestamp": "2024-01-27T10:30:00",
      "level": "INFO",
      "message": "✅ 系统已初始化",
      "module": "api"
    },
    {
      "timestamp": "2024-01-27T10:30:05",
      "level": "WARNING",
      "message": "⚠️ 代理连接超时",
      "module": "telegram_service"
    }
  ]
}
```

---

### 2. 获取日志文件列表

获取所有日志文件。

```http
GET /api/logs/files
```

**响应示例:**

```json
{
  "files": [
    "bot_activity.log",
    "bot_activity.log.2024-01-27",
    "bot_activity.log.2024-01-26"
  ]
}
```

---

### 3. 读取日志文件

读取指定日志文件的内容。

```http
GET /api/logs/file/<filename>
```

**路径参数:**

- `filename`: 日志文件名 (例如: bot_activity.log)

**响应示例:**

```json
{
  "filename": "bot_activity.log",
  "content": "2024-01-27 10:30:00 - INFO - ✅ 系统已初始化\n2024-01-27 10:30:05 - WARNING - ⚠️ 代理连接超时\n..."
}
```

---

## 🔍 错误响应

### 错误格式

所有错误响应都遵循以下格式:

```json
{
  "error": "错误消息描述"
}
```

### 常见错误码

| 状态码 | 说明                   |
| ------ | ---------------------- |
| 200    | 请求成功               |
| 400    | 请求参数错误或操作失败 |
| 500    | 服务器内部错误         |

### 错误示例

```json
{
  "error": "❌ 监控号登录失败"
}
```

---

## 🧪 测试示例

使用 curl 测试 API:

```bash
# 获取系统状态
curl http://localhost:5000/api/system/status

# 登录监控号
curl -X POST http://localhost:5000/api/monitor/login

# 获取所有配置
curl http://localhost:5000/api/config/all

# 更新过滤配置
curl -X POST http://localhost:5000/api/config/filter \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["广告", "http"], "max_file_size_mb": 20}'

# 启动脚本
curl -X POST http://localhost:5000/api/script/start

# 获取最近 50 条 ERROR 日志
curl "http://localhost:5000/api/logs/recent?level=ERROR&limit=50"
```

---

## 📝 SDK 示例

### Python

```python
import requests

BASE_URL = "http://localhost:5000"

# 获取系统状态
response = requests.get(f"{BASE_URL}/api/system/status")
print(response.json())

# 登录监控号
response = requests.post(f"{BASE_URL}/api/monitor/login")
print(response.json())

# 启动脚本
response = requests.post(f"{BASE_URL}/api/script/start")
print(response.json())
```

### JavaScript

```javascript
const BASE_URL = "http://localhost:5000";

// 获取系统状态
fetch(`${BASE_URL}/api/system/status`)
  .then((res) => res.json())
  .then((data) => console.log(data));

// 登录监控号
fetch(`${BASE_URL}/api/monitor/login`, { method: "POST" })
  .then((res) => res.json())
  .then((data) => console.log(data));
```

---

## 📞 更多帮助

如有问题，请查看项目的 README.md 或日志文件。
