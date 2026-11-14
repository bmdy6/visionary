# README 截图来源

这些图片是 Visionary 实际运行页面的 headless Playwright 截图。账号、UID、对话、提示词与任务均为合成演示数据；仅使用仓库已有的 `showcase/travel_journal.png`，未调用真实模型、付费生图、COS、邮件或支付。演示不根据提示词、比例或参考图绘制新内容，作品页的三个任务因此显示同一张内置样图。图像素材的权利限制见 [README](../../README.md#已知限制)。

## 采集方式

- 应用源码：`9b5afd88044c42c78248d58a1dabb92230127a70`（main 的 #8）；没有修改应用代码或用设计稿替换页面。
- 独立 Git worktree，临时 SQLite，`IMAGE_PROVIDER=demo`、`STORAGE_BACKEND=local`；后端 18080，前端 15173，均仅监听回环地址。
- 使用 readme-from-code 的 `capture --type web-app` 启停自有服务；`webCapture.prepare` 中的 Playwright 脚本完成普通生成、助手两轮对话与确认、Token API 生成、各页面导航及六张截图。随后内置页面采集再次确认工作台正常渲染，工具在 finally 中关闭自有服务。
- 采集入口：`node scripts/run.mjs capture --type web-app --repo "$CHECKOUT" --work "$WORK" --id demo-final --brief "$WORK/brief.json"`（在 readme-from-code 技能目录执行）。浏览器状态、采集 brief、脚本和原始回执保留在任务工作目录，不提交登录凭据。
- 浏览器使用 light 配色、zh-CN 语言，阻止 Service Worker 和远程 HTTP(S) 资源。没有修改 DOM、CSS 或请求响应来美化页面。
- PNG 原图以 Pillow 转为 WebP，`quality=90, method=6`；仅格式压缩，没有拼接、重绘或改字。API 页创建 Token 后已关闭明文，画面只有临时 Token 的遮罩与原有配置占位符。

## 页面与文件

| 文件 | 页面与操作 | 原始视口 | WebP 字节 | SHA-256 |
| --- | --- | --- | ---: | --- |
| [creation.webp](creation.webp) | `/` · 创作页：描述、比例、档位与生成结果。 | 1440 × 900 | 103916 | `ce76a2e07093ef589961f54e056f80a37ccce6d9c887bc002f2a53e134606185` |
| [api-mcp.webp](api-mcp.webp) | `/profile` · API 与 MCP：管理个人 Token，并复制 Agent 接入配置；图中仅显示临时 Token 的遮罩与配置占位符。 | 1440 × 1080 | 60620 | `49ff04332f30444a9bf5b7209b71b4f23af8a75889d8b49fc141836f2efeccf8` |
| [assistant.webp](assistant.webp) | `/` · AI 助手：先讨论方案，确认后再生成，结果保留在同一工作台。 | 1440 × 1280 | 124552 | `71b4aa5242af136393c21d8907c715f03c817be5cc6e4b60a17308b53209771d` |
| [works.webp](works.webp) | `/history` · 我的作品：网页、AI 助手与 MCP 的任务统一归档，可按来源筛选。 | 1440 × 680 | 118268 | `5f37afe6d12f4e76d17741c7ac647599f4aa74590961613a122a368bfa6f3a5c` |
| [mobile.webp](mobile.webp) | `/` · 手机端：390 × 844 浏览器视口中的结果预览与底部输入区。 | 390 × 844 | 41270 | `613fd544e6562c704ebebc0e866ac80b630cdcdf7b5ae2c0527dbff372740cfd` |
| [admin.webp](admin.webp) | `/admin` · 管理后台：查看用户、本月生成、充值、上游成本估算和最近任务。 | 1440 × 760 | 43444 | `90b8d7078c51c810e1d1add019b651607e2d061bedd49cf28fdbd4deb5acbb51` |

## 校验基线

`manifest.json` 的 `originalBaseline` 指向整理前的 main；`baseline` 指向先完成 tidy 的提交。加图校验移除精确声明的图片块后，与 tidy 基线逐字节比较；不把该结果称为整理前全文未改。原有功能、命令、表格与限制的保留检查另行执行。
