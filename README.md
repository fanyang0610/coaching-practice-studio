# 教练练习室 · Coaching Practice Studio

教练练习室是一个中英双语的网页应用，为想体验教练对话的人、正在学习教练技能的人，以及带领学员练习的导师提供练习空间。项目以通用的解决方案导向教练方法为基础，独立运营，免费、非商业。

| 模式 | 怎么用 | 你会得到什么 |
| --- | --- | --- |
| **被教练** | 带一个真实议题进入对话，由 AI 教练陪你探索目标和下一步。 | 一张行动卡，记录目标、下一步、时间和所需支持。 |
| **练习做教练** | 由 AI 扮演来访者，你来提问和引导。可以用随机情境，也可以自选主题。 | 一份练习回顾，包含评分和具体反馈。 |

两种模式都有五阶段进度提示，各自保存对话进度。可以在手机或电脑上继续，也可以在账户页查看历史记录。被教练的对话默认仅自己可见。分配给导师的学员，其练习记录可由导师查看。

## 在线使用

打开[教练练习室](https://fanyang0610-coaching-practice-studio.hf.space)，用邀请链接注册后即可登录。在页面顶部切换两种模式，在「帮助」里了解练习和隐私规则。[使用帮助](https://fanyang0610-coaching-practice-studio.hf.space/help?lang=zh)

## 本地运行

准备 Python 3.10 或以上版本。下载或克隆仓库后，从仓库根目录运行下面的命令。Windows 上把激活命令换成 `.venv\Scripts\Activate.ps1`（PowerShell）。

```sh
cd "coaching and coachee_agent_mvp"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**快速体验**。运行 `python scripts/dev_server.py`，打开 [本地练习室](http://127.0.0.1:8797)。使用终端显示的临时账号登录。演示使用模拟 AI 和独立的临时数据库，无需模型密钥。

**连接自己的模型**。首次配置时把 `.env.example` 复制为 `.env`，填写 `OPENAI_API_KEY`、模型名称，以及所选服务需要的 `OPENAI_BASE_URL`。运行 `python app.py`，打开终端显示的地址，按提示创建首个管理员。日常使用可在管理员页面生成邀请链接。

在 macOS 上，可以运行 `python scripts/check_project.py --launcher` 生成带图标的 `Coaching Practice Studio.app`。把启动器留在应用目录里，之后双击即可启动。

## 技术与目录

应用界面用 **Gradio**，登录、账户、导师和管理页面由 **FastAPI** 提供，服务通过 **Uvicorn** 运行。AI 通过 OpenAI 兼容接口连接模型。数据通过 **SQLAlchemy** 读写，本地默认使用 **SQLite**，托管环境使用 **PostgreSQL**。线上体验由 Hugging Face Spaces 托管。

应用文件位于 [应用目录](./coaching%20and%20coachee_agent_mvp/)。`web_app.py` 是网页交互入口，`coach_agent.py` 和 `coachee_agent.py` 实现两种练习角色，`account_pages.py` 和 `accounts.py` 处理账号及权限，`db.py` 负责存储。

- [架构与开发检查](./coaching%20and%20coachee_agent_mvp/docs/ARCHITECTURE.md)
- [配置与部署](./coaching%20and%20coachee_agent_mvp/docs/DEPLOYMENT.md)
- [维护交接](./coaching%20and%20coachee_agent_mvp/docs/HANDOFF.md)
- [版本历史与自动发布规则](./docs/RELEASES.md)
