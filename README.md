# 教练练习室 · Coaching Practice Studio

[English](README.en.md) · 简体中文

教练练习室是独立、免费、非商业的中英双语网页应用，为想体验教练对话的人、学习教练技能的人，以及带领学员练习的导师提供练习空间。它采用通用的解决方案导向教练方法，帮助使用者探索自己的目标、资源和下一步。

| 模式 | 怎么用 | 结束后可以得到什么 |
| --- | --- | --- |
| **被教练** | 带一个真实议题，由 AI 教练陪你探索。 | 从对话中提取行动卡，记录下一步，以及已表达的目标、时间和支持；没有明确下一步时可能没有卡片。 |
| **练习做教练** | AI 扮演来访者，你来提问和引导；使用随机情境或自选主题。 | 练习回顾：五阶段分项、总分、具体反馈和下一步建议。 |

两种模式都有五阶段进度提示，分别保存会话，可在手机或电脑登录同一账户继续。账户页提供历史翻页、行动卡、练习得分和数据管理。

## 当前功能与状态

本次功能版本 [v2.8.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.8.0) 在帮助页增加中英文“更新动态”：近期功能与修复摘要、页首直达入口及 GitHub 完整更新记录链接。摘要随应用交付；完整源码版本见 [GitHub Releases](https://github.com/fanyang0610/coaching-practice-studio/releases)。

- **继续与恢复**：两种模式各自恢复进度；新开会话成功后再切换。结束时区分未提取到行动、生成失败和保存失败；符合条件的缺失行动卡可由本人从历史恢复，失败的练习点评也可重试。
- **洞察由本人控制**：账户页可逐条编辑、移除或清除 AI 洞察。被教练模式记录来访者表达的观察、资源和问题；陪练模式记录教练练习观察。后续使用读取当前保存内容，近义表述仍可能再次出现。
- **下次练习目标**：从陪练洞察中选择，或自行填写一个教练技能目标，可编辑或清空；用于准备新的 AI 来访者案例，不自动判定达成或进步。
- **导师与隐私**：分配的导师可查看学员的陪练会话；被教练会话默认私密，需本人主动分享。管理员页面管理账户、邀请和额度，展示使用与满意度统计，不提供对话正文的管理入口。用户可下载自己的 JSON 数据、删除单场会话或账户。
- **语言与语音**：支持简体中文和英文，提供浏览器语音输入与朗读；可用性取决于设备、浏览器和系统声音。

每场会话最多 **100 次用户发言**，每条最多 **2,000 字符**。模型请求使用完整对话，接近已识别模型的容量上限时提示收尾；完整输入不保证 AI 理解正确。

这是一款练习工具。五阶段评分的总分由程序求和，但分项、反馈、阶段识别和洞察仍依赖 AI 判断；尚未证明评分稳定、跨会话可比，或使用本工具能够提升教练能力。它不提供专业认证、心理治疗或危机援助。最近修复已做隔离功能、数据库及桌面/手机尺寸浏览器核对；这些结果不代表所有真实模型、生产账号流程或真机 Safari 都经过验证。

## 在线使用

打开[教练练习室](https://fanyang0610-coaching-practice-studio.hf.space)，用邀请链接注册后登录。在页面顶部切换模式，在[帮助](https://fanyang0610-coaching-practice-studio.hf.space/help?lang=zh)中查看使用与隐私规则。

GitHub Release 记录源码版本，线上版本由 Hugging Face 单独部署。实际部署及对应源码说明见 [Space 提交记录](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commits/main)；文档更新不会自动部署线上应用。

## 本地运行

需要 Python 3.10 或以上版本。从仓库根目录运行；Windows PowerShell 的激活命令为 `.venv\Scripts\Activate.ps1`。

```sh
cd "coaching and coachee_agent_mvp"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**快速体验**：运行 `python scripts/dev_server.py`，打开[本地练习室](http://127.0.0.1:8797)，使用终端显示的临时账号和密码。演示使用模拟 AI 和独立临时数据库，无需模型密钥。

**连接自己的模型**：首次配置时复制 `.env.example` 为 `.env`，填写 `OPENAI_API_KEY`、`OPENAI_MODEL`，以及服务商需要的 `OPENAI_BASE_URL`。运行 `python app.py`，打开终端显示的地址，创建首个管理员；之后在管理员页面生成邀请链接。示例配置不代表线上所用模型。

macOS 可运行 `python scripts/check_project.py --launcher` 生成带图标的 `Coaching Practice Studio.app`。把启动器留在应用目录，之后双击启动。

## 技术与维护文档

Gradio 提供练习界面，FastAPI 提供登录、账户、导师和管理页面，Uvicorn 运行服务。AI 通过 OpenAI 兼容接口连接。SQLAlchemy 读写数据，本地默认 SQLite，当前托管环境使用 PostgreSQL；线上体验由 Hugging Face Spaces 托管。

| 文档 | 中文 | English |
| --- | --- | --- |
| Space 介绍 | [README](coaching%20and%20coachee_agent_mvp/README.md) | [README](coaching%20and%20coachee_agent_mvp/README.en.md) |
| 架构与开发检查 | [架构](coaching%20and%20coachee_agent_mvp/docs/ARCHITECTURE.md) | [Architecture](coaching%20and%20coachee_agent_mvp/docs/ARCHITECTURE.en.md) |
| 配置与部署 | [部署](coaching%20and%20coachee_agent_mvp/docs/DEPLOYMENT.md) | [Deployment](coaching%20and%20coachee_agent_mvp/docs/DEPLOYMENT.en.md) |
| 维护交接与已知限制 | [交接](coaching%20and%20coachee_agent_mvp/docs/HANDOFF.md) | [Handoff](coaching%20and%20coachee_agent_mvp/docs/HANDOFF.en.md) |
| 版本历史与双语发布规则 | [版本](docs/RELEASES.md) | [Releases](docs/RELEASES.en.md) |

页面调整沿用应用目录中的 [DESIGN.md](coaching%20and%20coachee_agent_mvp/DESIGN.md) 和 [AGENTS.md](coaching%20and%20coachee_agent_mvp/AGENTS.md)。这些现有规范及带日期的历史审查记录未在本轮改写。
