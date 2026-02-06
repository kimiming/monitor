# 🎯 项目快速入门

欢迎使用 **Telegram 机器人管理系统**！这是一个完全模块化、前后端分离的现代化系统。

## ⚡ 5 分钟快速开始

### Windows 用户

1. 双击 `start.bat` 文件
2. 等待依赖安装完成
3. 打开浏览器访问 `http://localhost:5000`
4. 开始使用管理系统！

### Linux/Mac 用户

```bash
chmod +x start.sh
./start.sh
```

## 📁 项目文件说明

```
项目根目录/
├── 📂 backend/                    # 后端核心模块
│   ├── config_manager.py         # 配置管理
│   ├── db_manager.py             # 数据库管理
│   ├── logger_manager.py         # 日志管理
│   ├── account_manager.py        # 账号管理
│   ├── telegram_service.py       # Telegram 服务
│   ├── worker.py                 # 消息处理工人
│   ├── api.py                    # Flask API
│   └── __init__.py               # 包初始化
│
├── 📂 frontend/                   # 前端管理系统
│   ├── index.html                # 主页面
│   └── 📂 assets/
│       ├── style.css             # 样式表
│       └── app.js                # Vue 应用
│
├── 📂 sessions/                   # Telegram 会话文件
├── 📂 logs/                       # 日志文件
├── 📂 profile_photos/             # 头像图片
├── 📂 temp_media/                 # 临时文件
│
├── run.py                         # 启动脚本
├── start.bat                      # Windows 启动脚本
├── start.sh                       # Linux/Mac 启动脚本
├── requirements.txt               # 依赖清单
├── config.json                    # 配置文件 (自动生成)
├── config.example.json            # 配置示例
├── personality_recycle.db         # SQLite 数据库
│
├── README.md                      # 项目说明
├── API.md                         # API 文档
├── DEPLOY.md                      # 部署指南
└── QUICKSTART.md                  # 本文件
```

## 🎮 使用流程

### 1️⃣ 启动系统

```bash
python run.py
# 或双击 start.bat (Windows)
# 或执行 ./start.sh (Linux/Mac)
```

### 2️⃣ 打开管理界面

浏览器访问: `http://localhost:5000`

### 3️⃣ 登录账号

- 点击 "账号管理" 标签
- 登录监控号
- 登录所有克隆号

### 4️⃣ 配置设置

- 点击 "配置设置" 标签
- 修改 Telegram 参数、过滤规则等
- 点击保存按钮

### 5️⃣ 启动脚本

- 回到 "仪表板"
- 点击 "▶️ 启动脚本"
- 系统开始运行

### 6️⃣ 监控运行

- 查看 "日志监控" 了解系统状态
- 查看 "数据统计" 了解转发情况

## 🔌 API 调用示例

### Python

```python
import requests

# 获取系统状态
response = requests.get('http://localhost:5000/api/system/status')
print(response.json())

# 启动脚本
requests.post('http://localhost:5000/api/script/start')

# 获取日志
logs = requests.get('http://localhost:5000/api/logs/recent?limit=50').json()
```

### JavaScript

```javascript
// 获取系统状态
fetch("http://localhost:5000/api/system/status")
  .then((r) => r.json())
  .then((data) => console.log(data));

// 启动脚本
fetch("http://localhost:5000/api/script/start", { method: "POST" });
```

### cURL

```bash
# 获取系统状态
curl http://localhost:5000/api/system/status

# 启动脚本
curl -X POST http://localhost:5000/api/script/start
```

## ⚙️ 配置常见操作

### 修改警告群

编辑 `config.json`:

```json
{
  "telegram": {
    "alert_group": "@your_new_alert_group"
  }
}
```

或通过管理界面修改 (推荐)

### 添加过滤关键词

通过管理界面 → 配置设置 → 过滤配置

或编辑 `config.json`:

```json
{
  "filter": {
    "keywords": ["广告", "加粉", "你的关键词"]
  }
}
```

### 配置代理

通过管理界面 → 配置设置 → 代理配置

启用代理并填入:

- 代理地址
- 代理端口
- 代理用户名 (可选)
- 代理密码 (可选)

## 🆘 常见问题

### Q: 如何添加新的克隆号?

A: 将会话文件 (.session) 放在 `sessions/` 目录下，然后在管理界面登录该克隆号。

### Q: 如何查看详细的错误日志?

A:

- 方法 1: 管理界面 → 日志监控
- 方法 2: 查看 `logs/bot_activity.log` 文件
- 方法 3: 调用 API `/api/logs/recent`

### Q: 监控号为什么无法登录?

A: 检查:

1. API ID 和 Hash 是否正确
2. 网络连接是否正常
3. 代理设置是否正确
4. 账号是否被限制

### Q: 如何重置系统?

A:

```bash
# 备份重要数据
cp personality_recycle.db personality_recycle.db.backup

# 删除数据库
rm personality_recycle.db

# 重启应用，数据库会自动重建
python run.py
```

### Q: 如何修改克隆号的昵称和头像?

A: 程序会在登录时自动从以下位置获取:

- 昵称: `name.txt` (逐行写入昵称)
- 头像: `profile_photos/` (放入 jpg/png 文件)

## 📊 理解仪表板

| 卡片       | 说明                           |
| ---------- | ------------------------------ |
| 系统状态   | 显示系统是否运行中             |
| 监控号状态 | 显示监控号的登录状态和电话号码 |
| 克隆号统计 | 显示活跃的克隆号数量           |
| 消息队列   | 显示待处理的消息数             |

## 🔄 消息处理流程

```
源群消息
   ↓
监控号监听 (events.NewMessage)
   ↓
消息过滤 (关键词、URL 等)
   ↓
消息入队 (msg_queue)
   ↓
多个工人并发处理
   ↓
获取/分配克隆号
   ↓
转发到目标群
   ↓
更新统计数据
```

## 🛠️ 高级配置

### 增加并发处理数

编辑 `config.json`:

```json
{
  "system": {
    "max_concurrent_tasks": 10
  }
}
```

值越大处理越快，但对系统负担越大。

### 修改健康检查间隔

```json
{
  "system": {
    "auto_check_interval": 60
  }
}
```

单位为秒。

### 增加消息队列大小

```json
{
  "system": {
    "msg_queue_size": 1000
  }
}
```

## 📞 获取帮助

- 📖 **详细文档**: 查看 `README.md`
- 🔗 **API 文档**: 查看 `API.md`
- 🚀 **部署指南**: 查看 `DEPLOY.md`
- 📋 **日志信息**: 查看 `logs/` 目录

## ✨ 主要特性总结

✅ **模块化设计** - 功能独立，易于维护和扩展  
✅ **前后端分离** - 独立部署和开发  
✅ **实时监控** - Web 界面实时显示系统状态  
✅ **完整的 API** - 支持第三方集成  
✅ **自动化管理** - 自动登录、转发、错误处理  
✅ **灵活的配置** - 支持自定义各种参数  
✅ **详细的日志** - 便于追踪和调试  
✅ **生产级别** - 支持 Docker、Nginx、Systemd 等部署方式

## 🎓 学习资源

本项目涉及的技术:

- **后端**: Python 3, Flask, Telethon, SQLite, asyncio
- **前端**: Vue 3, HTML5, CSS3, JavaScript
- **部署**: Docker, Nginx, Gunicorn, Systemd

推荐学习顺序:

1. 阅读 README.md 了解项目整体
2. 使用管理界面熟悉功能
3. 查看 API.md 了解接口
4. 阅读代码理解实现原理
5. 参考 DEPLOY.md 部署上线

## 🎉 开始使用

现在您已经准备好了！

**立即启动系统**:

```bash
python run.py
```

**访问管理界面**:
打开浏览器并访问 `http://localhost:5000`

祝您使用愉快！🚀

---

**最后更新**: 2026-01-27  
**版本**: 1.0.0
