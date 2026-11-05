# 架构与开发检查

## 一次请求经过哪里

FastAPI 接收请求，校验登录会话，再把已登录的用户交给 Gradio。Gradio 根据当前模式加载该用户的对话。两种 AI 角色通过共享模型客户端生成回复，应用将会话、阶段和结束结果写入数据库。两种模式分别保存进度，显式新开会话会先生成开场，再切换到新会话。

| 模块 | 职责 |
| --- | --- |
| [`app.py`](../app.py) / [`web_app.py`](../web_app.py) | 本地入口、FastAPI 装配、Gradio 页面和事件，以及会话恢复、保存和结束。 |
| [`coach_agent.py`](../coach_agent.py) / [`coachee_agent.py`](../coachee_agent.py) | 分别负责 AI 教练和 AI 来访者、阶段推进、行动卡与练习回顾。配套的 `*_data.py` 保存内置问题和案例。 |
| [`coaching_core.py`](../coaching_core.py) | 模型连接、流式回复、阶段标记、用量、结构化结果和翻译。 |
| [`accounts.py`](../accounts.py) / [`account_pages.py`](../account_pages.py) | 登录签名、密码、表单校验和记录访问权限，以及登录、邀请、账户、导师、管理和帮助页面。 |
| [`db.py`](../db.py) / [`memory.py`](../memory.py) | SQLite/PostgreSQL 存储、按用户和模式隔离的记录及练习洞察。 |
| [`web_assets.py`](../web_assets.py) / [`DESIGN.md`](../DESIGN.md) | 网页文案、样式、语音相关浏览器脚本和设计规则。 |
| [`quota.py`](../quota.py) / [`safety.py`](../safety.py) / [`mailer.py`](../mailer.py) | 使用额度与频率限制、AI 教练的危机提示，以及可选的密码重置邮件。 |

会话以 JSON 保存，数据库的更新时间用于防止旧标签页覆盖较新记录。权限判断集中在账号模块。管理员可管理账号和额度。对话权限取决于记录归属、导师分配和学员的分享选择。

## 开发命令

在应用目录内运行。安装步骤见[项目首页](../../README.md#本地运行)。

```sh
python scripts/dev_server.py
python tests.py
python scripts/check_project.py
```

- 演示服务使用临时账号、数据库和模拟 AI。`--ai-down` 模拟模型服务不可用。
- `tests.py` 覆盖会话、账号、权限、存储、模型错误和网页行为。装有 Node.js 时也检查浏览器脚本。
- `check_project.py` 还会检查 Python 文件能否编译，并预览 Space 发布文件。`--browser` 使用隔离的 Chrome 配置，生成登录后的桌面和 iPhone 尺寸截图。`--launcher` 在 macOS 上重新生成启动器和图标。
- 涉及存储或并发会话时，可按 [`scripts/pg_test.py`](../scripts/pg_test.py) 的命令运行临时 PostgreSQL 测试。涉及并发请求时，可用 [`scripts/load_test.py`](../scripts/load_test.py) 模拟多个登录用户。
