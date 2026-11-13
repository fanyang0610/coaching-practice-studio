# 架构与开发检查

[English](ARCHITECTURE.en.md) · 简体中文

## 请求与保存

FastAPI 校验登录，将用户交给 Gradio。两种 AI 角色共用 OpenAI 兼容客户端，但各自保存对话、阶段和结束结果。新开会话先生成并保存开场，再切换；切换模式各自继续。完整对话用于续聊、回顾和洞察分析，不再按末尾若干条截断。

| 模块 | 职责 |
| --- | --- |
| [app.py](../app.py) / [web_app.py](../web_app.py) | 本地入口、FastAPI 装配、Gradio 事件、会话恢复、草稿、保存、结束和容量提示。 |
| [coach_agent.py](../coach_agent.py) / [coachee_agent.py](../coachee_agent.py) | AI 教练、AI 来访者、五阶段推进、行动卡和回顾；配套的 *_data.py 保存问题和案例。 |
| [coaching_core.py](../coaching_core.py) | 模型连接、流式回复、容量估算、阶段标记、用量、结构化结果和翻译。 |
| [accounts.py](../accounts.py) / [account_pages.py](../account_pages.py) | 登录签名、密码、表单校验、权限，以及登录、邀请、账户、导师、管理和帮助页面。 |
| [db.py](../db.py) / [memory.py](../memory.py) | SQLite/PostgreSQL、按用户和模式隔离的会话、画像、本人洞察修正和下次练习目标。 |
| [web_assets.py](../web_assets.py) / [DESIGN.md](../DESIGN.md) | 网页文案、样式、浏览器语音和设计规则。 |
| [quota.py](../quota.py) / [safety.py](../safety.py) / [mailer.py](../mailer.py) | 额度与频率限制、固定危机提示及可选密码重置邮件。 |

会话与画像以 JSON 保存，版本条件更新防止旧标签页或迟到分析覆盖较新内容。画像按模式隔离，纠正后的当前值用于后续实际读取；显式新开的被教练会话从当次话题开始。历史错误洞察不批量改写。

新行动卡必须包含非空下一步；失败状态随会话保存，历史恢复限本人且不能覆盖已保存卡片。新 AI 回顾的五阶段各占 20 分，由程序求和为总分，模型判断仍可能有偏差；旧回顾不重算。模板演示使用独立规则，不能作为真实 AI 质量证据。

权限集中于账号和存储入口。导师看分配学员的陪练及本人主动分享的被教练记录；管理员页面不提供正文查看。账户/导师历史和管理邀请均支持翻页。最后有效管理员的角色与删除约束在存储事务内串行处理。

## 限额与失败处理

每场最多 100 次用户发言，每条最多 2,000 字符；案例主题和下次练习目标各最多 300 字符。模型容量按已识别配置估算，服务商容量错误仍为准。请求保留原文，接近容量时允许收尾，不通过删掉中间对话来继续。

额度采用滚动 24 小时窗口：两种模式的完成/开启次数分别计数，tokens 共用。多个限额同时命中时按最晚恢复时点提示；零额度联系管理员。频率限制在进程内，部署维持单进程。生成、翻译或保存失败应保留已有记录；回复和手动推进期间不覆盖用户新输入的草稿，未发送草稿不承诺跨刷新保存。

## 开发命令

在应用目录运行，安装见[项目首页](../../README.md)。

```sh
python scripts/dev_server.py
python tests.py
python scripts/check_project.py
```

- 演示服务使用临时账号、数据库和模拟 AI；`--ai-down` 模拟模型不可用。
- `tests.py` 检查会话、权限、存储、模型错误和网页行为；安装 Node.js 时也检查浏览器脚本。
- `check_project.py` 运行项目测试、Python 编译检查及 Space 文件预览。`--browser` 使用隔离 Chrome 和临时登录生成桌面/iPhone 尺寸截图；`--launcher` 在 macOS 重编译启动器。它们不是仅执行单项操作的快捷命令。
- 存储或并发修改按需使用 [pg_test.py](../scripts/pg_test.py) 和 [load_test.py](../scripts/load_test.py)，使用隔离数据库及虚构账号。
- 根据实际影响选择验证，复用有效结果。应用代码修改遵守 [AGENTS.md](../AGENTS.md) 的双端与启动器要求；只有文档和仓库发布流程变化时无需重复应用验收。

当前限制见[维护交接](HANDOFF.md)，发布前的双语说明和文档核对规则见[版本说明](../../docs/RELEASES.md)。
