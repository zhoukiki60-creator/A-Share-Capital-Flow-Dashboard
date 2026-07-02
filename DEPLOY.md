# A股资金流向看板 - 部署指南

## 方案一：Render.com 免费部署（推荐，最简单）

> 适合：想要实时数据，不想管服务器

### 步骤

1. **注册账号**
   - 访问 https://render.com
   - 用 GitHub 账号登录（一键注册）

2. **创建 Web Service**
   - 点击 "New +" → "Web Service"
   - 连接你的 GitHub 仓库（或直接用本项目的文件）
   - 配置如下：
     - **Name**: `fund-dashboard`（随便填）
     - **Environment**: `Python 3`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn -w 2 -b 0.0.0.0:$PORT --timeout 120 app:app`
   - 选择 **Free** 计划
   - 点击 "Create Web Service"

3. **等待部署**
   - 首次部署约需 2-3 分钟
   - 部署完成后会给你一个链接，如 `https://fund-dashboard-xxxxx.onrender.com`

4. **首次数据加载**
   - 打开链接后等待约 40 秒（首次拉取数据）
   - 之后每 60 秒自动更新

### 免费计划限制
- 15 分钟无访问会休眠
- 下次访问需 30 秒唤醒
- 可用 **UptimeRobot** 免费定时 ping 保持唤醒

---

## 方案二：GitHub Pages + GitHub Actions（完全免费，永不休眠）

> 适合：纯展示、定时监控、分享给别人看
> 数据每 30 分钟自动更新（交易时段）

### 步骤

1. **创建 GitHub 仓库**
   - 访问 https://github.com/new
   - 仓库名：`fund-dashboard`
   - 选择 Public（免费）

2. **上传项目文件**
   ```bash
   # 在本项目目录下执行
   git init
   git remote add origin https://github.com/你的用户名/fund-dashboard.git
   git add .
   git commit -m "initial commit"
   git push -u origin main
   ```

3. **配置 GitHub Actions 密钥**
   - 进入仓库 → Settings → Secrets and variables → Actions
   - 点击 "New repository secret"
   - Name: `KIMI_API_KEY`
   - Value: 你的 Kimi API Key

4. **启用 GitHub Pages**
   - 进入仓库 → Settings → Pages
   - Source: 选择 "GitHub Actions"

5. **手动触发首次数据拉取**
   - 进入仓库 → Actions
   - 点击 "定时拉取A股资金流向数据"
   - 点击 "Run workflow"

6. **访问**
   - 等 Actions 运行完成后（约 1-2 分钟）
   - 访问 `https://你的用户名.github.io/fund-dashboard`

### 数据更新频率
- 交易时段（周一到周五 9:00-15:30）：每 30 分钟
- 非交易时段：不更新（显示最后一次缓存的数据）

---

## 方案三：Cloudflare Pages（国内访问快）

> 适合：国内用户访问，速度最快

### 步骤

1. **注册 Cloudflare**
   - 访问 https://dash.cloudflare.com/sign-up
   - 用邮箱注册（免费）

2. **创建 Pages 项目**
   - 点击 "Pages" → "Create a project"
   - 连接 GitHub 仓库
   - 框架预设：选 "None"
   - 构建命令：留空
   - 输出目录：`static`
   - 点击 "Save and Deploy"

3. **数据更新**
   - 配合方案二的 GitHub Actions
   - Actions 会自动提交更新的 `data.json` 到仓库
   - Cloudflare Pages 会自动重新部署

4. **访问**
   - `https://你的项目名.pages.dev`
   - 国内访问速度极快

---

## 方案四：本地运行（数据最实时）

```bash
cd fund_dashboard
pip install flask flask-cors
python3 app.py
# 浏览器打开 http://127.0.0.1:5000
```

---

## 方案对比

| 方案 | 成本 | 数据时效 | 维护 | 国内速度 | 适合场景 |
|------|------|----------|------|----------|----------|
| Render.com | 免费 | 实时 | 几乎零 | 一般 | 实时盯盘 |
| GitHub Pages + Actions | 免费 | 30分钟 | 零 | 一般 | 定时监控 |
| Cloudflare Pages | 免费 | 30分钟 | 零 | 极快 | 国内分享 |
| 本地运行 | 免费 | 实时 | 需开机 | 最快 | 个人专用 |

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `app.py` | Flask 后端服务 |
| `data_service.py` | 数据拉取 + 资金流向计算 |
| `static/index.html` | 前端页面 |
| `requirements.txt` | Python 依赖 |
| `Dockerfile` | Docker 容器化配置 |
| `render.yaml` | Render.com 一键部署配置 |
| `.github/workflows/` | GitHub Actions 定时任务 |
| `start.sh` | 本地启动脚本 |
