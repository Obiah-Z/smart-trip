# FRP 内网穿透上线记录

本文记录 `smart-trip` 当前通过 FRP 暴露到公网的运行方式。当前方案已经从 `Vite dev server` 改为 `Nginx 静态托管`，并且不使用 `8080` 端口。

## 当前结论

当前公网入口：

```text
http://trip.obiah.xyz
http://obiah.xyz
```

备用访问入口：

```text
http://trip.obiah.xyz:18080
http://obiah.xyz:18080
http://8.153.15.37:18080
```

当前本机 Web 入口：

```text
127.0.0.1:18081
```

说明：

- `8080` 不用于当前 Smart Trip 公网访问链路。
- `5180` 只作为 Vite 本地开发端口，不再承接公网流量。
- `8001` 是 FastAPI 后端本机端口，不直接暴露到公网。
- 公网域名通过 FRP 转发到本机 `18081`，由 Nginx 托管前端静态资源、图片资源，并反向代理 API。

## 当前运行链路

```text
公网用户
  -> trip.obiah.xyz:80 / obiah.xyz:80
  -> frps 公网服务端
  -> 本机 frpc
  -> 127.0.0.1:18081 Nginx
  -> frontend/dist 静态前端
  -> /media/generated/ 静态图片目录
  -> /api/ 代理到 127.0.0.1:8001 FastAPI
  -> /health 代理到 127.0.0.1:8001/health
```

备用端口链路：

```text
公网用户
  -> trip.obiah.xyz:18080 / obiah.xyz:18080 / 8.153.15.37:18080
  -> frps 公网服务端
  -> 本机 frpc
  -> 127.0.0.1:18081 Nginx
```

## 端口分工

| 端口 | 位置 | 用途 | 是否公网暴露 |
| --- | --- | --- | --- |
| `80` | 公网 FRP 服务端 | 域名直连入口 | 是 |
| `18080` | 公网 FRP 服务端 | 备用公网入口 | 是 |
| `18081` | 本机 | Nginx 静态托管入口 | 否，只由 frpc 访问 |
| `8001` | 本机 | FastAPI 后端 | 否 |
| `5180` | 本机 | Vite 开发调试 | 否，不作为公网入口 |
| `8080` | 本机 | 保留给其他用途 | 不使用 |

## Nginx 配置

当前使用项目内独立 Nginx 配置：

```text
/home/obiah/Desktop/smart-trip/deploy/nginx/smart-trip-local-18081.conf
```

该配置监听：

```nginx
listen 127.0.0.1:18081;
```

主要职责：

- `frontend/dist`：托管 Vue 生产构建产物。
- `/assets/`：前端静态 JS/CSS 资源，使用长缓存。
- `/media/generated/`：直接托管生成图片和缩略图，避免图片请求经过 FastAPI。
- `/api/`：反向代理到 `http://127.0.0.1:8001/api/`。
- `/health`：反向代理到 `http://127.0.0.1:8001/health`。
- `/`：回退到 `index.html`，支持 Vue 前端路由。

Nginx 运行时目录：

```text
/tmp/smart-trip-nginx
```

日志位置：

```text
/tmp/smart-trip-nginx/access.log
/tmp/smart-trip-nginx/error.log
/tmp/smart-trip-nginx/stdout.log
```

## 前端构建

公网模式下前端必须构建成同源 API，不要把浏览器 API 地址写死成 `127.0.0.1:8001`。

构建命令：

```bash
cd /home/obiah/Desktop/smart-trip/frontend
env VITE_API_BASE= VITE_MAP_PROVIDER=amap npm run build
```

关键点：

- `VITE_API_BASE=` 为空，表示浏览器请求同源 `/api`。
- `VITE_MAP_PROVIDER=amap` 表示线上使用高德地图。
- 高德地图密钥仍从 `frontend/.env` 读取，不要写入文档或提交记录。

构建产物位置：

```text
/home/obiah/Desktop/smart-trip/frontend/dist
```

## 后端启动

后端监听本机 `8001`：

```bash
cd /home/obiah/Desktop/smart-trip/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

本地健康检查：

```bash
curl -sS http://127.0.0.1:8001/health
```

期望返回：

```json
{"status":"ok"}
```

## 启动本机 Nginx

项目内提供了 `18081` 专用启动脚本：

```bash
cd /home/obiah/Desktop/smart-trip
bash deploy/nginx/start-smart-trip-nginx-18081.sh
```

停止命令：

```bash
cd /home/obiah/Desktop/smart-trip
bash deploy/nginx/stop-smart-trip-nginx-18081.sh
```

手动启动等价命令：

```bash
mkdir -p /tmp/smart-trip-nginx
setsid nginx -p /tmp/smart-trip-nginx/ -c /home/obiah/Desktop/smart-trip/deploy/nginx/smart-trip-local-18081.conf > /tmp/smart-trip-nginx/stdout.log 2>&1 < /dev/null &
```

本地 Nginx 验证：

```bash
curl -I http://127.0.0.1:18081/
curl -i http://127.0.0.1:18081/health
```

期望看到：

```text
HTTP/1.1 200 OK
Server: nginx/1.18.0
```

## FRP 配置

当前正式使用的 FRP 客户端配置文件：

```text
/home/obiah/Downloads/frp_0.68.0_linux_amd64/frpc.toml
```

项目内同步副本：

```text
/home/obiah/Desktop/smart-trip/deploy/frp/smart-trip-frpc.toml
```

Smart Trip 相关代理必须指向 `18081`：

```toml
[[proxies]]
name = "smart-trip-web"
type = "tcp"
localIP = "127.0.0.1"
localPort = 18081
remotePort = 18080

[[proxies]]
name = "smart-trip-web-80"
type = "tcp"
localIP = "127.0.0.1"
localPort = 18081
remotePort = 80
```

含义：

- `remotePort = 80`：支持 `http://trip.obiah.xyz` 和 `http://obiah.xyz` 直连访问。
- `remotePort = 18080`：保留备用公网访问端口。
- `localPort = 18081`：FRP 转发到本机 Nginx，不再转发到 Vite。

当前配置里还保留了其他代理：

```text
127.0.0.1:22   -> 8.153.15.37:6000
127.0.0.1:3390 -> 8.153.15.37:6001
127.0.0.1:8766 -> 8.153.15.37:8766
```

这些属于额外公网暴露入口。如果不是必须长期使用，建议后续移除，降低暴露面。

## 启动 FRP

启动命令：

```bash
setsid /home/obiah/Downloads/frp_0.68.0_linux_amd64/frpc -c /home/obiah/Downloads/frp_0.68.0_linux_amd64/frpc.toml > /tmp/smart-trip-frpc.log 2>&1 < /dev/null &
```

查看日志：

```bash
sed -n '1,180p' /tmp/smart-trip-frpc.log
```

成功日志应包含：

```text
login to server success
[smart-trip-web] start proxy success
[smart-trip-web-80] start proxy success
```

如果出现：

```text
proxy [smart-trip-web] already exists
```

说明已有旧 `frpc` 连接占用了同名代理。需要停止旧 `frpc` 后重新启动。

## 公网验证

首页：

```bash
curl --noproxy '*' -I http://trip.obiah.xyz/
```

健康检查：

```bash
curl --noproxy '*' -i http://trip.obiah.xyz/health
```

备用端口：

```bash
curl --noproxy '*' -i http://trip.obiah.xyz:18080/health
```

期望看到：

```text
HTTP/1.1 200 OK
Server: nginx/1.18.0
{"status":"ok"}
```

图片静态资源检查：

```bash
curl --noproxy '*' -I 'http://trip.obiah.xyz/media/generated/__thumbs__/640/%E6%9D%AD%E5%B7%9E/attractions/%E8%A5%BF%E6%B9%96-nature-travel-editorial-square-%E6%B8%85%E6%99%A8%E6%9F%94%E5%85%89-%E5%A4%9A%E4%BA%91.jpg'
```

期望看到：

```text
HTTP/1.1 200 OK
Server: nginx/1.18.0
Cache-Control: public, max-age=2592000, stale-while-revalidate=86400
```

## 常见问题

### 1. 公网访问仍然很慢

优先检查图片是否命中 Nginx 静态目录和缩略图：

```bash
curl --noproxy '*' -I 'http://trip.obiah.xyz/media/generated/__thumbs__/640/...jpg'
```

如果返回不是 `Server: nginx/1.18.0`，说明公网还没有走当前 Nginx 链路。

### 2. 公网返回旧页面

可能原因：

- 前端没有重新执行 `npm run build`。
- `frpc.toml` 仍然转发到 `5180`。
- 旧 `frpc` 进程仍在运行。
- 浏览器缓存了旧资源。

排查命令：

```bash
pgrep -af frpc
sed -n '1,180p' /tmp/smart-trip-frpc.log
curl --noproxy '*' -I http://trip.obiah.xyz/
```

### 3. API 请求失败

先确认后端本地可用：

```bash
curl -i http://127.0.0.1:8001/health
```

再确认 Nginx 代理可用：

```bash
curl -i http://127.0.0.1:18081/health
```

最后确认公网可用：

```bash
curl --noproxy '*' -i http://trip.obiah.xyz/health
```

### 4. 不要误用 8080

当前 Smart Trip 公网链路固定为：

```text
FRP remote 80/18080 -> local 127.0.0.1:18081 Nginx
```

不要把 FRP 的 `localPort` 改成 `8080`。该端口保留给其他用途。

## 后续建议

当前方案适合公网演示和轻量上线：

```text
FRP -> Nginx 18081 -> FastAPI 8001
```

如果要更正式地长期运行，建议继续补：

- 使用 systemd 管理 FastAPI、Nginx 独立实例和 frpc。
- 开启 HTTPS，可用 Caddy、Nginx + Certbot 或 CDN。
- 移除不必要的 SSH/RDP 公网代理。
- 把日志、pid、缓存目录从 `/tmp` 迁移到稳定运行目录。
