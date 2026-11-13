# 截图来源与拍摄方式

这些是 Visionary 实际运行页面的截图。拍摄于 2026-11-13，Playwright 使用 Chromium headless；前端为 `npm run build` 的产物，通过 Vite preview 运行，后端为本地 FastAPI 和独立 SQLite 数据库。

## 截图清单

| 文件 | 页面 | 视口 | 内容 |
| --- | --- | --- | --- |
| [home-generation.png](home-generation.png) | `/` | 1440 × 1000 | 提交提示词后，经真实后台任务和状态轮询显示结果；左侧模糊蒙层为页面自带的查看模式 |
| [history.png](history.png) | `/history` | 1440 × 1000 | 合成历史记录与仓库展示图 |
| [credits-recharge.png](credits-recharge.png) | `/profile` | 1440 × 1000 | 积分余额及充值金额选择面板，未发起支付 |
| [admin-dashboard.png](admin-dashboard.png) | `/admin` | 1440 × 1000 | 仪表盘、风格统计和作品动态；人数、金额等均来自合成数据 |
| [mobile-generation.png](mobile-generation.png) | `/` | 390 × 844 | 移动端输入、生成结果、档位与导航 |

截图未重绘页面，也未通过修改 DOM 或 CSS 美化界面。仅在截图时禁用 CSS 动画以稳定拍摄。

## 数据与图片

- 账号 `demo-creator`、`demo-admin`，邮箱使用保留域名 `example.invalid`；口令和签名密钥在拍摄环境随机生成。
- 用户、积分、充值和历史记录全部在独立的合成数据库中创建，没有读取既有账号或订单。
- 图片只使用仓库的 [旅行手账](../../frontend/public/showcase/travel_journal.png)、[象棋图鉴](../../frontend/public/showcase/master_encyclopedia_chess.png) 和 [人物关系图](../../frontend/public/showcase/master_relation_map.png)。它们是展示素材，非拍摄期间调用模型生成的图片；权利边界见 [已知限制](../LIMITATIONS.md)。
- 假上游监听本机回环地址，接受应用原有的图片生成请求，返回旅行手账素材 URL；拍摄环境用本地存储适配替代 COS 上传。生成入口、后台任务、数据库结算和前端轮询仍执行原代码。
- 后端禁止向外部地址建立连接；浏览器也拦截外部请求，包含 Google Fonts，页面使用系统字体。未访问真实生图、COS、SMTP 或支付服务。

## 拍摄步骤

1. 使用独立 SQLite 数据库初始化表，创建两个合成账号、三条历史记录，以及演示充值流水。
2. 启动本地假上游和存储适配，后端仅监听 `127.0.0.1:8000`。
3. 在 `frontend/` 执行 `npm ci`、`npm run build`、`npm run preview -- --host 127.0.0.1 --port 5173 --strictPort`。
4. Playwright 以 `headless: true` 创建全新浏览器上下文，通过真实登录接口取得合成账号 JWT，并将其写入该上下文的本地存储。公告采用页面已有的“不再显示”标记。
5. 在桌面首页输入“苏州三日旅行手账，蜡笔插画与路线记录”，点击创作，等待轮询成功和图片加载。依次打开历史记录、个人中心充值面板、管理员仪表盘；在移动视口再次提交任务并等待结果。
6. 等待字体和图片完成加载后截图；检查 JavaScript 异常、API 响应及移动端横向溢出。另核对积分明细和普通账号访问后台被拒绝。

拍摄用的假服务和浏览器脚本仅用于离线验证，不随应用启动。图片尺寸、SHA-256、展示素材和脚本哈希记录在 [manifest.json](manifest.json)，以便核对截图与拍摄记录。
