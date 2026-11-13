# 配置与部署

[English](DEPLOYMENT.en.md) · 简体中文

## 运行配置

本地使用应用目录下的 `.env`。托管环境通过平台配置变量和密钥。参见 [`.env.example`](../.env.example)。示例模型不代表线上配置，不要提交密钥、数据库或真实对话。

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

## GitHub 发布与文档

GitHub Release 记录源码，不会自动更新线上 Space。每次发布按[双语发布规则](../../docs/RELEASES.md)核对 README、功能状态、架构、配置及维护交接；需要变化的文档同步更新中英文，并在发布说明记录文档核对结论。

当前容量规则位于 [coaching_core.py](../coaching_core.py)，按配置的模型标识识别部分容量，服务商错误仍为准。更换模型时核对完整历史、结构化输出、语言和容量表现。代码支持某个标识不代表该直连服务已完成真实验证；本轮不更换模型或配置。

## Hugging Face Spaces

1. 在现有 Space 中配置模型、PostgreSQL 和签名密钥。用同一个数据库地址升级。首次设置还需要管理员配置。
2. 从应用目录运行 `python scripts/deploy_hf_space.py --dry-run` 检查发布文件。发布清单在脚本的 `SPACE_FILES` 中，`scripts/needs_hf_upload.py` 使用同一清单判断本地改动。检查已提交的改动时，可把应用目录下的文件路径作为参数传入。
3. 在获准部署后运行 `python scripts/deploy_hf_space.py --commit-message "Deploy <GitHub commit>"`。脚本把本地 `web_app.py` 放到 Space 的 `app.py`。应用目录的 [README](../README.md) 包含 Space 配置头，`sdk_version` 须与 `requirements.txt` 的 Gradio 版本一致。
4. 等构建运行后，用 Space 直达地址检查登录、两种会话和账户页。用 `/ping` 检查进程，用 `/healthz` 检查数据库连接。若 Space 已有旧部署留下的开发工具或本地文件，检查远端清单后单独清理。

发布清单仅上传应用 README.md，其中保留英文入口；完整英文 README 在 GitHub。等待构建完成后，还应确认实际运行 SHA 与本次部署提交一致。健康页不能证明模型语义或业务流程正确。

截至 2026-11-13，最近一次已记录应用部署为 [4932350](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/4932350d83865ee343e8371ec8a9bcfc5cb37879)，对应 GitHub v2.7.4；此前已记录运行 SHA、健康及中英文登录核对。本轮文档更新仅发布 GitHub。

## Docker 与数据库

应用目录内的 [Dockerfile](../Dockerfile) 提供容器启动方式。以应用目录为构建上下文，使用 PostgreSQL 和 HTTPS 对外提供服务。使用单进程运行，当前频率限制保存在进程内。

启动会创建缺少的表。以后修改已有表结构时，需要单独设计数据库迁移和回退步骤。备份和恢复由托管数据库或本地运维负责，升级时保留原数据库和签名密钥。

当前洞察和下次练习目标沿用画像 JSON，不需要新表。代码回退不应覆盖真实数据和用户更正。v2.7.4 的上一应用版本为 GitHub v2.7.3 / `9fb6392`、Space `d51bdc1ca859bc4fe0c961db59926fb1651272fc`；回退前重新判断数据兼容性。本轮文档与发布流程变化不涉及应用数据迁移。
