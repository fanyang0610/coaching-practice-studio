# 维护交接

2026-11-13：六项串行修复已逐项验证并独立提交，最终351项整合检查通过。洞察归属及异常翻译保留原文已作为第一批v2.7.3上线；管理员并发保护、旧邀请分页、评价恢复及日志失败不阻断支持提示作为第二批由本次main推送发布。完整授权、逐项证据、限制与两批发布状态见[六项修复交接](../../docs/SIX_FIXES_HANDOFF_20261111.md)。各项已完成双端核对及必要启动器重编译；不自动扩展其他改进。

教练练习室是独立、非商业的中英双语教练练习应用，支持「被教练」和「练习做教练」。面向使用者和新维护者的入口在[仓库首页](../../README.md)。

- GitHub 默认分支 `main` 展示当前维护版本，旧 MVP 从 GitHub Releases 查阅。线上版本以 [Hugging Face Space 提交记录](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commits/main) 为准，GitHub 合并与线上部署是两个独立操作。
- 线上使用 Hugging Face，托管数据使用 PostgreSQL。本地默认使用 SQLite。配置、发布清单和升级兼容见[配置与部署](DEPLOYMENT.md)。
- 每种模式独立保存会话。显式新开 AI 教练会话从当次话题开始，生成或保存失败时可继续原会话。练习回顾失败后可从账户页重试。
- 会话、账号、权限和模型的代码入口见[架构与开发检查](ARCHITECTURE.md)。页面调整前查看 [DESIGN.md](../DESIGN.md)，修改后按 [AGENTS.md](../AGENTS.md) 做双端检查。
- [历史交接和调试记录](https://github.com/fanyang0610/coaching-practice-studio/blob/b8957a9ef15f7aa435333ff824274ae8ace5781d/coaching%20and%20coachee_agent_mvp/docs/HANDOFF.md) 保存在整理前的提交里。
