# 架构与调用链

`frontend/src/App.jsx` 选择桌面／移动布局，`frontend/src/api/request.js` 统一访问 `/api` 并注入浏览器内保存的 JWT。开发代理在 `frontend/vite.config.js`，后端入口为 `api/index.py`。

## 生图与积分

1. `backend/api/image.py::generate_image` 查询用户活跃任务数，校验提示词，通过带余额条件的 SQL UPDATE 增加 `frozen_points`，创建 `pending` 图片记录。
2. `BackgroundTasks.add_task` 把任务交给同一 Web 进程；前端用 `/image/status/{id}` 轮询，不是流式百分比进度。
3. `process_image_task` 包装风格提示词、可选上传参考图、请求图片 API，再把结果转存 COS。COS 同步 SDK 通过 `run_in_threadpool` 调用。只对连接错误／连接超时最多尝试三次。
4. 成功后在 `session_scope` 中把任务标成 `success`、记录 URL 和耗时，减少余额并释放冻结积分；异常时标成 `failed` 并释放冻结积分。事务辅助在 `backend/models/database.py`。

这展示了预占与结算的分离，但读改写结算、手动 reset 和后台任务之间没有统一状态比较或持久化调度，不能宣称任意并发和重启场景的一致性。

## 账户与后台

`backend/core/deps.py` 验证 JWT 并查询用户；`backend/api/admin.py::admin_required` 校验管理员权限。初始化脚本不导入旧数据，也不提供固定口令。邮件验证码、充值流水、配置、反馈各自使用 SQLAlchemy 模型。

## 配置与存储

`backend/core/config.py::get_config` 每 60 秒刷新配置表缓存，配置为空或不可读时回退到环境变量。JWT 配置由 `backend/core/security.py` 读取并拒绝示例占位密钥。COS 适配在 `backend/core/cos.py`，需自备账号和存储桶。

## 支付适配

`backend/api/payment.py` 创建待支付订单、构造签名 URL、处理通知并更新积分；`backend/core/payment.py` 实现签名。回调有行锁和 pending 条件，但金额核对当前被注释，SQLite 也不能证明 MySQL 行锁语义。真实接入前需补充金额、归属、并发和重放验收，详见限制文档。
