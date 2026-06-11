# Smart Trip Deployment

当前推荐的公网演示链路是：

```text
FRP -> 127.0.0.1:18081 Nginx -> frontend/dist + static media + FastAPI 8001
```

该方案不使用 `8080` 端口，`8080` 可保留给其他服务。

## 1. Build Frontend

公网模式下，前端需要构建为同源 API 调用：

```bash
cd /home/obiah/Desktop/smart-trip/frontend
env VITE_API_BASE= VITE_MAP_PROVIDER=amap npm run build
```

构建产物：

```text
/home/obiah/Desktop/smart-trip/frontend/dist
```

## 2. Generate Image Thumbnails

用户侧图片卡片优先加载 `320px/640px` 缩略图，避免公网直接加载原图。

新增或更新图片后执行：

```bash
cd /home/obiah/Desktop/smart-trip/backend
python scripts/generate_trip_image_thumbnails.py --summary-only
```

缩略图目录：

```text
backend/data/generated_images/kolors/__thumbs__/320
backend/data/generated_images/kolors/__thumbs__/640
```

图片 manifest：

```text
backend/data/generated_images/kolors/meta/manifest.json
```

## 3. Start Backend

后端只监听本机：

```bash
cd /home/obiah/Desktop/smart-trip/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

健康检查：

```bash
curl -i http://127.0.0.1:8001/health
```

## 4. Start Local Nginx

当前使用独立 Nginx 配置：

```text
deploy/nginx/smart-trip-local-18081.conf
```

监听地址：

```text
127.0.0.1:18081
```

启动：

```bash
cd /home/obiah/Desktop/smart-trip
bash deploy/nginx/start-smart-trip-nginx-18081.sh
```

停止：

```bash
cd /home/obiah/Desktop/smart-trip
bash deploy/nginx/stop-smart-trip-nginx-18081.sh
```

验证：

```bash
curl -I http://127.0.0.1:18081/
curl -i http://127.0.0.1:18081/health
```

Nginx 职责：

- 托管 `frontend/dist`。
- 直接托管 `/media/generated/` 图片与缩略图。
- 将 `/api/` 代理到 `127.0.0.1:8001/api/`。
- 将 `/health` 代理到 `127.0.0.1:8001/health`。

## 5. Start FRP

FRP 客户端配置：

```text
/home/obiah/Downloads/frp_0.68.0_linux_amd64/frpc.toml
```

项目内副本：

```text
deploy/frp/smart-trip-frpc.toml
```

Smart Trip 代理必须指向本机 `18081`：

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

启动：

```bash
setsid /home/obiah/Downloads/frp_0.68.0_linux_amd64/frpc -c /home/obiah/Downloads/frp_0.68.0_linux_amd64/frpc.toml > /tmp/smart-trip-frpc.log 2>&1 < /dev/null &
```

日志：

```bash
sed -n '1,180p' /tmp/smart-trip-frpc.log
```

## 6. Public URLs

主访问地址：

```text
http://trip.obiah.xyz
http://obiah.xyz
```

备用端口：

```text
http://trip.obiah.xyz:18080
http://obiah.xyz:18080
```

公网验证：

```bash
curl --noproxy '*' -I http://trip.obiah.xyz/
curl --noproxy '*' -i http://trip.obiah.xyz/health
curl --noproxy '*' -i http://trip.obiah.xyz:18080/health
```

期望响应：

```text
HTTP/1.1 200 OK
Server: nginx/1.18.0
```

## 7. Notes

- `8080` 不属于当前部署链路。
- `5180` 只用于 Vite 本地开发，不建议承接公网流量。
- `8001` 不要直接暴露到公网。
- 如果要长期运行，建议用 systemd 管理 `uvicorn`、独立 Nginx 和 `frpc`。
- 如果要正式上线，建议继续补 HTTPS、访问日志轮转和公网暴露面收敛。
