# 架构与调用链

`frontend/src/App.jsx` 选择桌面／移动布局，`frontend/src/api/request.js` 统一访问 `/api` 并注入浏览器内保存的 JWT。开发代理在 `frontend/vite.config.js`，后端入口为 `api/index.py`。

## 生图与积分

1. `backend/api/image.py::generate_image` 查询用户活跃任务数，校验提示词和迭代限制，先用条件 UPDATE 预占允许档位的试用，否则按配置价格增加 `frozen_points`。预占、`pending` 图片记录和助手方案版本认领在同一事务提交。
2. `BackgroundTasks.add_task` 把任务交给同一 Web 进程；前端用 `/image/status/{id}` 轮询，不是流式百分比进度。
3. `process_image_task` 包装风格提示词、可选上传参考图、按 `IMAGE_PROVIDER` 请求图片 API 或读取内置示例图，再按 `STORAGE_BACKEND` 转存到 COS 或本地。同步存储通过 `run_in_threadpool` 调用。只对连接错误／连接超时最多尝试三次。
4. 成功后在 `session_scope` 中把任务标成 `success`、记录 URL 和耗时，试用任务减少试用余量并释放冻结试用，积分任务减少积分余额并释放冻结积分；异常时标成 `failed` 并释放对应额度。事务辅助在 `backend/models/database.py`。

这展示了预占与结算的分离，但读改写结算、手动 reset 和后台任务之间仅有终态保护而没有跨进程原子状态比较或持久化调度，不能宣称任意并发和重启场景的一致性。

## 账户与后台

`backend/core/deps.py` 验证 JWT 并查询用户；`backend/api/admin.py::admin_required` 校验管理员权限。初始化脚本不导入旧数据，也不提供固定口令。邮件验证码、充值流水、配置、反馈各自使用 SQLAlchemy 模型。

## 配置与存储

`backend/core/config.py::get_config` 每 60 秒刷新配置表缓存，配置为空或不可读时回退到环境变量。JWT 配置由 `backend/core/security.py` 读取并拒绝示例占位密钥。`backend/core/image_provider.py` 在 auto 模式下有 key 用真实上游，否则轮换 `showcase/` PNG。`backend/core/storage.py` 在 COS 四项配全时复用 `backend/core/cos.py`，否则写入 `backend/data/creations/`。显式配置不完整会报错。

本地文件经后端 `/api/creations/` 静态路由和 Vite 的 `/api` 代理访问；分享海报的图片代理可直接读取受限的本地文件路径。发给远端上游的本地参考图内嵌为 data URL，数据库仍保存本地 URL。COS 参考图继续使用原 URL。本轮不增加存储迁移、文件删除或任务持久化机制。

## 支付适配

`backend/api/payment.py` 创建待支付订单、构造签名 URL、处理通知并更新积分；`backend/core/payment.py` 实现签名。回调有行锁和 pending 条件，但金额核对当前被注释，SQLite 也不能证明 MySQL 行锁语义。真实接入前需补充金额、归属、并发和重放验收，详见限制文档。

## 助手方案与系统设置

`CreationPage` 在保留原桌面/移动工作台的基础上切换助手。`backend/api/assistant.py` 按用户持久化对话，消息和手工编辑用 revision 防止覆盖并行修改；每个方案版本为不可变快照。`backend/core/assistant.py` 只输出受校验的回复/方案，不拥有生成工具；复用提示词润色的 provider 选择，无 key 则固定演示。参考图由服务端保存和绑定，不采信模型生成的 URL。

确认时继续 POST `/image/generate`，用 `plan_id + plan_version` 原子认领已有方案，服务端重新读取该版本字段。任务 ID 与预占同时提交；重复请求只回读同一个任务，不重复排入后台。新版本可以再次确认，失败版本需编辑成新版本再重试；删除作品也保留版本的任务标识。普通生成没有新增幂等契约。

`backend/core/billing_config.py` 集中配置默认值、解析和公开费用快照。管理员设置接口只接受本轮白名单键，整批校验后在同一事务保存 `system_configs` 和现有 `RechargeLog` 的零积分审计记录，提交后清当前进程缓存；其余进程仍按 60 秒 TTL 更新。页面监听余额变化，并按试用可用档位、可用试用和未冻结积分显示费用。

`scripts/init_db.py` 调用幂等增量迁移，旧用户新增试用列为 0；只有注册入口显式发新用户试用。旧积分价格、注册积分与邀请奖励现在从系统配置读取。
