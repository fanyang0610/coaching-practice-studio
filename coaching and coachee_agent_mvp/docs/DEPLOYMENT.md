# 配置与部署

## 运行配置

本地使用应用目录下的 `.env`。托管环境通过平台配置变量和密钥。参见 [`.env.example`](../.env.example)。

| 变量 | 用途 |
| --- | --- |
| `OPENAI_API_KEY` | 服务端模型密钥。 |
| `OPENAI_MODEL`、`OPENAI_BASE_URL` | 模型和 OpenAI 兼容服务地址。直连 OpenAI 可省略地址。通过其他服务时填该服务的地址和模型标识。 |
| `OPENAI_EXTRA_BODY` | 可选的服务商专用 JSON 参数。 |
| `DATABASE_URL` | 托管使用持久化 PostgreSQL。本地省略时使用应用目录内的 SQLite。 |
| `STUDIO_SECRET_KEY` | 托管必填，用于登录签名。首次设置可用 `python -c "import secrets; print(secrets.token_hex(32))"` 生成。升级时复用原有签名密钥。 |
| `STUDIO_ADMIN_EMAIL`、`STUDIO_ADMIN_PASSWORD` | 首次托管启动时创建管理员，密码至少 10 字符。本地可通过首次设置页创建管理员。 |
| `STUDIO_PUBLIC_URL` | 可选，显式指定邀请和重置链接使用的外部地址。 |
| `STUDIO_DATA_LOCATIONS`、`STUDIO_CONTACT` | 隐私页的数据处理地点和帮助页的联系信息。地点应与实际部署和模型配置一致。 |
| `STUDIO_INBROWSER` | 本地设为 `1` 时自动打开浏览器，默认关闭。 |
| `SMTP_HOST`、`SMTP_PORT`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM` | 可选，配置自助找回密码。管理员也可生成单次密码重置链接。 |
| `GRADIO_SERVER_NAME`、`GRADIO_SERVER_PORT` / `PORT` | 服务监听地址和端口。公网入口使用 HTTPS。 |
| `SENTRY_DSN` | 可选，启用错误报告。应用配置关闭请求正文和局部变量的采集。 |

已有安装会继续读取旧版环境变量，新的 `STUDIO_*` 设置优先。新版会继续使用已有的本地数据库和签名文件。全新安装使用 `studio.db` 和 `.studio_secret`。已有登录和语言设置也可以由新版读取。若逐项改名，复制配置值，尤其是登录签名密钥。

## Hugging Face Spaces

1. 在现有 Space 中配置模型、PostgreSQL 和签名密钥。用同一个数据库地址升级。首次设置还需要管理员配置。
2. 从应用目录运行 `python scripts/deploy_hf_space.py --dry-run` 检查发布文件。发布清单在脚本的 `SPACE_FILES` 中，`scripts/needs_hf_upload.py` 使用同一清单判断本地改动。检查已提交的改动时，可把应用目录下的文件路径作为参数传入。
3. 在获准部署后运行 `python scripts/deploy_hf_space.py --commit-message "Deploy <GitHub commit>"`。脚本把本地 `web_app.py` 放到 Space 的 `app.py`。应用目录的 [README](../README.md) 包含 Space 配置头，`sdk_version` 须与 `requirements.txt` 的 Gradio 版本一致。
4. 等构建运行后，用 Space 直达地址检查登录、两种会话和账户页。用 `/ping` 检查进程，用 `/healthz` 检查数据库连接。若 Space 已有旧部署留下的开发工具或本地文件，检查远端清单后单独清理。

## Docker 与数据库

应用目录内的 [Dockerfile](../Dockerfile) 提供容器启动方式。以应用目录为构建上下文，使用 PostgreSQL 和 HTTPS 对外提供服务。使用单进程运行，当前频率限制保存在进程内。

启动会创建缺少的表。以后修改已有表结构时，需要单独设计数据库迁移和回退步骤。备份和恢复由托管数据库或本地运维负责，升级时保留原数据库和签名密钥。
