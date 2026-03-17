# hamr-browser

浏览器自动化 API 服务。全局共享一个 Playwright 浏览器实例，登录一次后 Cookie 持久化复用，将任意网站的操作流程包装为 HTTP API。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 2. 配置 secrets
cp secrets.example.yaml secrets.yaml
# 编辑 secrets.yaml，填写账号密码

# 3. 配置环境变量（可选）
cp .env.example .env

# 4. 启动服务
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API 文档：http://localhost:8000/docs

## 调用 Demo

**查询 SellerSprite 销量**（首次调用会自动登录）：

```bash
curl -X POST http://localhost:8000/flows/sellersprite_sales/run \
  -H "Content-Type: application/json" \
  -d '{"asin": "B0D81C6WGH", "market": "UK"}'
```

**响应**：
```json
{
  "flow_id": "sellersprite_sales",
  "status": "success",
  "duration_ms": 3420,
  "data": { ... }
}
```

## 流程管理

```bash
GET    /flows                      # 列出所有流程
GET    /flows/{id}                 # 查看流程详情
POST   /flows/{id}/run             # 执行流程
POST   /flows                      # 上传新流程 YAML
PUT    /flows/{id}                 # 更新流程
DELETE /flows/{id}                 # 删除流程

GET    /browser/status             # 浏览器状态
POST   /browser/restart            # 重启浏览器
GET    /browser/{site}/cookies     # 查看 Cookie
DELETE /browser/{site}/cookies     # 清除 Cookie
GET    /health                     # 健康检查
```

## 流程配置（YAML）

```yaml
id: my_flow
name: 我的流程
parameters:
  - name: keyword
    type: string
    required: true

auth:                              # 可选，不需要登录则删除此节
  check:
    type: navigate_and_check
    url: "https://example.com/login"
    logged_in_indicator:
      type: url_not_contains
      value: "/login"
  login:
    steps:
      - type: navigate
        url: "https://example.com/login"
      - type: fill
        selector: "input[name=username]"
        value: "{{ _auth.username }}"
      - type: fill
        selector: "input[name=password]"
        value: "{{ _auth.password }}"
      - type: click
        selector: "button[type=submit]"
      - type: wait_for_url
        url_pattern: "**/dashboard**"
  secrets_key: my_site            # 对应 secrets.yaml 中的 key

steps:
  - type: new_tab
  - type: navigate
    url: "https://example.com/search?q={{ keyword }}"

capture:
  type: wait_for_response
  url_pattern: "**/api/search**"
  timeout: 15000
```

## Docker 部署

```bash
cp secrets.example.yaml secrets.yaml
# 编辑 secrets.yaml

docker compose up -d
```
