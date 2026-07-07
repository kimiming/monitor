# Docker 部署指南（Ubuntu）

这份项目建议在 Ubuntu 服务器上用 Docker Compose 运行。容器启动的是 `python run.py`，Flask 服务监听 `0.0.0.0:5000`，前端由 Flask 直接托管。

## 1. 安装 Docker

Ubuntu 服务器需要先安装 Docker Engine 和 Compose 插件：

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

验证：

```bash
docker --version
docker compose version
```

## 2. 上传项目

把项目上传到服务器，例如：

```bash
cd /opt
sudo mkdir -p telegram-monitor
sudo chown -R $USER:$USER telegram-monitor
cd telegram-monitor
```

把代码放到这个目录后，确认根目录里有这些文件：

```bash
Dockerfile
docker-compose.yml
requirements.txt
run.py
backend/
frontend/
config.example.json
```

## 3. 准备持久化目录

```bash
mkdir -p data sessions monitor logs profile_photos temp_media configs
```

这些目录会挂载到容器里：

- `data/`: 保存 `config.json` 和 `personality_recycle.db`
- `sessions/`: 克隆号 `.session` 文件
- `monitor/`: 监控号 `.session` 文件
- `logs/`: 程序日志
- `profile_photos/`: 头像文件
- `temp_media/`: 临时媒体文件
- `configs/`: 预留配置目录

首次运行前建议创建配置文件：

```bash
cp config.example.json data/config.json
```

如果你要沿用本地现有数据，把本地文件放到服务器对应位置：

```bash
# 本地 config.json -> 服务器 data/config.json
# 本地 personality_recycle.db -> 服务器 data/personality_recycle.db
# 本地 sessions/*.session -> 服务器 sessions/
# 本地 monitor/*.session -> 服务器 monitor/
```

## 4. 代理配置注意事项

如果 Telegram 需要走代理，并且代理运行在 Ubuntu 主机上，例如 `127.0.0.1:7897`，容器里的 `127.0.0.1` 不是宿主机，而是容器自己。

这种情况下请在 `data/config.json` 里改成：

```json
{
  "proxy": {
    "use_proxy": true,
    "proxy_type": "SOCKS5",
    "proxy_host": "host.docker.internal",
    "proxy_port": 7897,
    "proxy_username": "",
    "proxy_password": ""
  }
}
```

`docker-compose.yml` 已经配置了：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

所以 Linux Docker 下也可以解析 `host.docker.internal`。

## 5. 启动

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f telegram-bot
```

访问管理界面：

```text
http://服务器IP:5000
```

如果服务器开启了防火墙，需要放行端口：

```bash
sudo ufw allow 5000/tcp
```

## 6. 停止、重启、升级

停止：

```bash
docker compose down
```

重启：

```bash
docker compose restart
```

代码更新后重新构建：

```bash
docker compose up -d --build
```

## 7. 数据备份

至少备份这些目录：

```bash
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz \
  data sessions monitor profile_photos configs
```

## 8. 常见问题

### 启动后页面打不开

检查容器是否运行：

```bash
docker compose ps
docker compose logs --tail=100 telegram-bot
```

确认服务器安全组或防火墙已经放行 `5000/tcp`。

### Telegram 连接失败

优先检查 `data/config.json` 里的代理配置。容器中不要把宿主机代理写成 `127.0.0.1`，应使用 `host.docker.internal`。

### 配置改了没生效

修改 `data/config.json` 后重启容器：

```bash
docker compose restart telegram-bot
```

### 数据库没有持久化

本项目容器内使用：

```text
CONFIG_FILE=/app/data/config.json
DB_FILE=/app/data/personality_recycle.db
```

所以请确认 `docker-compose.yml` 中有：

```yaml
volumes:
  - ./data:/app/data
```
