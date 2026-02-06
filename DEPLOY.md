# 📦 部署指南

本指南介绍如何在不同环境下部署 Telegram 机器人管理系统。

## 🖥️ Windows 部署

### 方式 1: 使用批处理脚本 (推荐)

最简单的方式是使用 `start.bat` 脚本：

1. 双击运行 `start.bat`
2. 脚本会自动:
   - 检查 Python 安装
   - 创建虚拟环境
   - 安装依赖
   - 启动应用

3. 打开浏览器访问 `http://localhost:5000`

### 方式 2: 手动启动

```cmd
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate.bat

# 安装依赖
pip install -r requirements.txt

# 启动应用
python run.py
```

---

## 🐧 Linux/Mac 部署

### 方式 1: 使用 Shell 脚本 (推荐)

```bash
chmod +x start.sh
./start.sh
```

### 方式 2: 手动启动

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动应用
python3 run.py
```

---

## 🌍 使用 Docker 部署

### Dockerfile

创建 `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建必要的目录
RUN mkdir -p sessions logs profile_photos temp_media configs

# 暴露端口
EXPOSE 5000

# 启动应用
CMD ["python", "run.py"]
```

### Docker Compose

创建 `docker-compose.yml`:

```yaml
version: "3.8"

services:
  telegram-bot:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./sessions:/app/sessions
      - ./logs:/app/logs
      - ./profile_photos:/app/profile_photos
      - ./config.json:/app/config.json
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

启动容器:

```bash
docker-compose up -d
```

---

## 🚀 生产环境部署 (Gunicorn + Nginx)

### 1. 安装 Gunicorn

```bash
pip install gunicorn
```

### 2. 启动 Gunicorn

```bash
# 单进程
gunicorn -w 1 -b 0.0.0.0:5000 backend.api:app

# 多进程 (推荐)
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 backend.api:app
```

### 3. 配置 Nginx

创建 `/etc/nginx/sites-available/telegram-bot`:

```nginx
upstream telegram_bot {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name your_domain.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your_domain.com;

    # SSL 证书配置
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # SSL 优化
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 日志
    access_log /var/log/nginx/telegram_bot_access.log;
    error_log /var/log/nginx/telegram_bot_error.log;

    # 反向代理
    location / {
        proxy_pass http://telegram_bot;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # 静态文件
    location /static/ {
        alias /path/to/project/frontend/assets/;
        expires 30d;
    }

    # 前端文件
    location /index.html {
        alias /path/to/project/frontend/index.html;
        expires 1h;
    }
}
```

启用站点:

```bash
sudo ln -s /etc/nginx/sites-available/telegram-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Systemd Service

创建 `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram Bot Management System
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/project/venv/bin"
ExecStart=/path/to/project/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 --timeout 120 backend.api:app
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

启动服务:

```bash
sudo systemctl daemon-reload
sudo systemctl start telegram-bot
sudo systemctl enable telegram-bot
```

查看状态:

```bash
sudo systemctl status telegram-bot
```

---

## 📊 监控和日志

### 查看日志

```bash
# 实时日志
sudo journalctl -u telegram-bot -f

# 最近 50 行
sudo journalctl -u telegram-bot -n 50

# 昨天的日志
sudo journalctl -u telegram-bot --since yesterday
```

### 应用日志

应用日志保存在 `logs/` 目录下:

```bash
# 查看最新日志
tail -f logs/bot_activity.log

# 搜索错误
grep ERROR logs/bot_activity.log
```

---

## 🔒 安全建议

### 1. 环境变量

不要在代码中硬编码敏感信息，使用环境变量:

```python
import os

TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
```

启动时设置:

```bash
export TELEGRAM_API_ID=123456
export TELEGRAM_API_HASH=xxxxx
python run.py
```

### 2. 防火墙配置

```bash
# 只允许本机访问 API (如果使用 Nginx 反向代理)
sudo ufw allow from 127.0.0.1 to any port 5000

# 允许外部访问 Nginx
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### 3. 定期备份

```bash
# 备份数据库和配置
tar -czf backup_$(date +%Y%m%d).tar.gz \
  personality_recycle.db \
  config.json \
  sessions/
```

### 4. API 认证

在生产环境中添加 API 密钥认证:

```python
from functools import wraps

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != os.getenv('API_KEY'):
            return {'error': '未授权'}, 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/protected-route')
@require_api_key
def protected_route():
    return {'message': 'success'}
```

---

## 🆘 故障排除

### 问题 1: 端口被占用

```bash
# 查找占用 5000 端口的进程
lsof -i :5000

# 杀死进程
kill -9 <PID>

# 或修改启动端口
gunicorn -w 4 -b 0.0.0.0:8000 backend.api:app
```

### 问题 2: 导入错误

```bash
# 确保在项目根目录
cd /path/to/project

# 检查虚拟环境激活
source venv/bin/activate

# 重新安装依赖
pip install -r requirements.txt
```

### 问题 3: 数据库锁定

```bash
# 删除旧的数据库文件
rm personality_recycle.db

# 程序会自动重建
python run.py
```

### 问题 4: Telegram 连接问题

- 检查 API ID 和 Hash 是否正确
- 检查网络连接和代理设置
- 查看日志文件获取详细错误信息

---

## 📈 性能优化

### 1. 增加工人数

修改 `config.json`:

```json
{
  "system": {
    "max_concurrent_tasks": 10
  }
}
```

### 2. 增加队列大小

```json
{
  "system": {
    "msg_queue_size": 2000
  }
}
```

### 3. 使用 Redis 缓存

安装 Redis:

```bash
sudo apt-get install redis-server
```

集成 Redis (可选):

```python
import redis
cache = redis.Redis(host='localhost', port=6379, db=0)
```

### 4. 数据库优化

定期清理旧数据:

```bash
# 清理 7 天前的日志
find logs/ -name "*.log.*" -mtime +7 -delete

# 清理数据库
sqlite3 personality_recycle.db "DELETE FROM message_stats WHERE created_date < date('now', '-30 days');"
```

---

## 📚 更多资源

- [Flask 文档](https://flask.palletsprojects.com/)
- [Telethon 文档](https://docs.telethon.dev/)
- [Gunicorn 文档](https://gunicorn.org/)
- [Nginx 文档](https://nginx.org/en/docs/)

---

最后更新: 2026-01-27
