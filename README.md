# Visionary

An AI image generation web app with credit accounting and an admin dashboard.

Visionary 是一个用 React 与 FastAPI 编写的 AI 生图网站项目，包含生图、历史记录、积分和管理后台。本仓库整理了早期源码，移除了旧部署信息、个人联系方式、数据库和开发过程文件，使用全新 Git 历史。

## 功能与代码

| 功能 | 实现位置 |
| --- | --- |
| 文生图、参考图生图、画面比例、风格提示词与迭代字段 | [生成接口](backend/api/image.py)、[请求结构](backend/schemas/image.py)、[桌面页面](frontend/src/pages/HomePage.jsx)、[移动页面](frontend/src/pages/MobileHomePage.jsx) |
| 后台生成与状态轮询，连接失败时有限重试 | [process_image_task / generate_image / get_task_status](backend/api/image.py)、[前端轮询](frontend/src/pages/HomePage.jsx) |
| 提示词润色：优先 Qwen，未配置时走兼容聊天接口；每用户内存限流 | [润色逻辑](backend/core/prompt_enhance.py)、[限流入口](backend/api/image.py) |
| 积分预冻结、成功后扣费、失败释放冻结积分，消费和充值流水 | [生成与结算](backend/api/image.py)、[数据模型](backend/models/models.py)、[流水](backend/api/user.py) |
| JWT 登录，用户名／邮箱／手机号检索；邮件验证码注册与找回密码 | [账号接口](backend/api/auth.py)、[JWT 与 bcrypt](backend/core/security.py)、[邮件](backend/core/email.py) |
| 图片历史、删除、下载跳转、分享海报 | [历史接口](backend/api/image.py)、[历史页面](frontend/src/pages/HistoryPage.jsx)、[海报组件](frontend/src/components/SharePosterModal.jsx) |
| 人工充值申请与审核、管理员加分、统计面板、反馈处理 | [管理员接口](backend/api/admin.py)、[充值逻辑](backend/crud/recharge.py)、[反馈接口](backend/api/feedback.py)、[后台页面](frontend/src/pages/AdminPage.jsx) |
| 支付订单、签名回调和状态查询适配代码 | [支付路由](backend/api/payment.py)、[签名逻辑](backend/core/payment.py)；未配置商户时不可用 |
| 腾讯云 COS 图片存储，配置表缓存与环境变量回退 | [存储](backend/core/cos.py)、[配置](backend/core/config.py) |
| 桌面／移动端页面与 PWA 安装引导 | [路由布局](frontend/src/App.jsx)、[安装 Hook](frontend/src/hooks/usePWA.js)、[Manifest](frontend/public/manifest.json) |

这里的功能列表描述代码能力，不代表外部服务已验收。生图是 FastAPI 进程内后台任务，不是持久化消息队列；没有已接入的全站日消费熔断或内容审核服务。详细边界见 [已知限制](docs/LIMITATIONS.md)。

## 技术栈

- 前端：React 19、Vite 8、React Router 7、Axios、Lucide、html2canvas、qrcode.react、CSS。版本以 [package.json](frontend/package.json) 和锁文件为准。
- 后端：Python、FastAPI、SQLAlchemy、Pydantic、HTTPX、python-jose、bcrypt、腾讯云 COS SDK。依赖见 [requirements.txt](requirements.txt)。
- 本地数据库：SQLite；原实现保留了 PyMySQL 依赖，但本次没有验证 MySQL，不能直接把 SQLite 的建表流程当作 MySQL 迁移方案。

## 本地运行

本轮在 Python 3.14.3、Node.js 20.19.2、npm 10.8.2 下完成安装、后端离线验证与前端构建。建议用独立虚拟环境；Node 版本须满足 Vite 的要求。

```bash
git clone https://github.com/bmdy6/visionary.git
cd visionary
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

把生成的随机串填入 `.env` 的 `SECRET_KEY`。保留示例里的本地 SQLite 地址即可，外部服务字段先留空。项目没有预置用户、默认管理员密码或真实积分记录。

```bash
# 初始化空表；可选创建一个本地管理员，密码交互输入
python -m scripts.init_db --admin local-admin
# 在当前终端启动后端
python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
```

另开终端运行前端：

```bash
cd visionary/frontend
npm ci
npm run dev -- --host 127.0.0.1
```

打开 `http://127.0.0.1:5173`，使用自己创建的管理员账号登录；接口文档在 `http://127.0.0.1:8000/docs`，健康检查为 `/api/health`。Vite 把 `/api` 代理到本地后端。管理员有 100 个本地演示积分，用于查看界面和离线开发，不代表付款。

```bash
# 仅检查后端加载（需要先配置 .env）
python -c 'from api.index import app; print(app.title)'
# 前端生产构建
cd frontend
npm ci && npm run build
```

真实生图需要配置自己的 `OPENAI_API_KEY`、兼容 API 地址及 COS 凭据。当前代码发送模型字符串 `gpt-image-2`，调用 `/images/generations`；参考图走 `/images/edits` 的 JSON `images` 数组，均使用 `quality: low`。这是源码约定的请求格式，不等同于所有上游服务都兼容，也不把 DALL-E 3 与该模型名称混用。画质档位主要影响计费、提示词和迭代限制，不应据此推断上游实际画质档位。见 [请求构造](backend/api/image.py)。

邮件功能需要 SMTP；支付适配需要自备商户配置和可达回调地址；示例地址仅为占位。本地浏览、管理员登录和后台查看不要求这些外部服务。不要在未评估 [已知限制](docs/LIMITATIONS.md) 前接入真实支付或直接对外提供服务。

## 示例素材

下图来自原仓库 `showcase/`，仅为展示素材，并非本轮生成结果或网站截图。已目视检查，没有发现手机号、个人账号或二维码。来源和权利边界见 [限制说明](docs/LIMITATIONS.md)。

![旅行手账示例](showcase/travel_journal.png)

## 目录

```text
api/                 FastAPI 应用入口
backend/api/         账号、生图、积分、支付、后台、反馈
backend/core/        配置、认证、邮件、提示词和 COS
backend/models/      SQLAlchemy 表结构
backend/crud/        数据访问
backend/schemas/     请求与响应模型
frontend/            React 页面与静态素材
scripts/init_db.py   空白本地数据库与可选管理员初始化
docs/                架构与已知限制
showcase/            审查后的原仓库示例图
```

## 许可

代码采用 [MIT License](LICENSE)，Copyright (c) 2026 bmdy6。第三方依赖遵循各自许可证；示例图片不构成其中品牌、人物或作品的权利授权。
