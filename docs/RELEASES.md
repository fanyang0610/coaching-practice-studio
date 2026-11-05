# 版本历史与自动发布

## 正式版本

日期是对应的 GitHub 源码提交日期，使用北京时间。历史版本在整理时补发。

| 版本 | 日期 | 对应提交或分支 | 主要变化 |
| --- | --- | --- | --- |
| [v1.0.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v1.0.0) | 2026-05-10 | `85063f1`，原默认分支 | 旧版 MVP。 |
| [v2.0.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.0.0) | 2026-10-14 | `68b1f12`，首次改名提交 | 改名为教练练习室，更新图标与界面，纳入账号与导师功能。 |
| [v2.1.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.1.0) | 2026-10-19 | `30c5b33`，`scale/phase-0-1` | 自选练习议题、手机布局、朗读和会话收尾。 |
| [v2.2.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.2.0) | 2026-11-04 | `53051b5`，`codex/coach-fresh-session` | AI 教练显式新开会话。 |
| [v2.3.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.3.0) | 2026-11-05 | `b8957a9`，`codex/resume-and-review-retry` | 两个模式各自恢复会话，失败点评可重试。 |
| [v2.3.1](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.3.1) | 2026-11-05 | `b3d749c`，`main` | 重写仓库说明、清理命名并收紧发布文件。 |

后续版本见 [GitHub Releases](https://github.com/fanyang0610/coaching-practice-studio/releases)。原 `legacy-mvp` 标签与 `v1.0.0` 指向同一个提交。

## 以后怎么发版

推送到 `main` 后，GitHub Actions 从上一个版本起检查提交说明，为这次推送生成一个 Release。一次推送有多条提交时，按其中最大的改动升级。开发分支在合入 `main` 时纳入正式版本。

| 提交说明 | 版本变化 | 从 `2.3.1` 出发 |
| --- | --- | --- |
| `feat!:`、`fix!:` 等带 `!` 的前缀，或 `BREAKING CHANGE:` 说明 | 升主版本 | `3.0.0` |
| `feat:` 或 `feat(模块):` | 升次版本 | `2.4.0` |
| `fix:`、文档、维护和其他提交 | 升修订号 | `2.3.2` |

提交前请标明改动类型。若合并时会把多个提交压成一条，最终的合并提交标题也要保留正确类型。Release 会附上这一版的提交清单和完整差异。同一个提交重复运行不会重复发布。

GitHub Release 记录仓库源码。线上体验版对应 [Hugging Face 的部署记录](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commits/main)，按[部署说明](../coaching%20and%20coachee_agent_mvp/docs/DEPLOYMENT.md)单独发布。

## 可核对的历史部署

以下时间来自 Space 提交记录，使用北京时间。GitHub 对应提交按当时可见的核心运行文件比对。若多条 GitHub 提交的运行文件相同，优先列出相应正式版本或产生改动的提交。

| Space 时间 | Space 提交 | GitHub 提交 | 变化 |
| --- | --- | --- | --- |
| 2026-05-07 09:25 | [`b8c3463`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/b8c34633ad94c07a8af5448668b36e6ff655b9b8) | [`85063f1`](https://github.com/fanyang0610/coaching-practice-studio/commit/85063f121dfef8c3471f3752f12cd56b3d43f1bc) · v1.0.0 | MVP 网页入口部署 |
| 2026-10-15 01:16 | [`a9e75eb`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/a9e75eb393eb3e6c893a6c036dfc5935a66b096c) | [`85063f1`](https://github.com/fanyang0610/coaching-practice-studio/commit/85063f121dfef8c3471f3752f12cd56b3d43f1bc) · v1.0.0 | 旧站移除旧品牌文件和内部说明，核心运行文件仍对应 MVP |
| 2026-10-15 01:16 | [`1e91c36`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/1e91c363c7895497d29ff354a45aabe1bb40a21c) | [`624ff32`](https://github.com/fanyang0610/coaching-practice-studio/commit/624ff32a33039b7ae6b1cc5ff9cf5626a2971c47) | 首个可配对的 Studio 上线记录，包含邀请登录与手机布局 |
| 2026-10-15 01:20 | [`6b0cfc7`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/6b0cfc7d83ca9827c304dcec4922f8a00fc5f3ec) | [`2bb3c9f`](https://github.com/fanyang0610/coaching-practice-studio/commit/2bb3c9f382d7f24867f0b5ba9dd93476b4051d0f) | 账号页面直接提供服务，修正部署入口 |
| 2026-10-15 01:38 | [`a8f8488`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/a8f84881c0b7d71df36bf7e98c8ca830fb347cd0) | [`69b095d`](https://github.com/fanyang0610/coaching-practice-studio/commit/69b095d439ddd4b31dd0576c148f888e51ead6f1) | 调整手机输入区、页头与语言切换 |
| 2026-10-15 01:50 | [`52b207d`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/52b207df1f1535e0e3fbfe0406f1c0d78d9c0c92) | [`8e783b1`](https://github.com/fanyang0610/coaching-practice-studio/commit/8e783b14a9cdef75fab761fe9d20650cb22b37e2) | 重试繁忙模型请求，修正翻译失败后的语言状态 |
| 2026-10-15 01:57 | [`2cbde44`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/2cbde4444eb5b21968cbb6c8ae35d6bf0110c666) | [`8dbf413`](https://github.com/fanyang0610/coaching-practice-studio/commit/8dbf413193c5ada6e0e46ff9f1d900a17184ce26) | 简化额度提示，调整 iPhone 页头 |
| 2026-10-15 10:20 | [`841a635`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/841a6357cd15dc8a823ef299a11b8159f9835d28) | [`8d70c8d`](https://github.com/fanyang0610/coaching-practice-studio/commit/8d70c8d7a6f89dc393e81a23ecd95e253b348cbf) | 处理中国大陆网络下的 Space 加载问题 |
| 2026-10-15 21:12 | [`9916516`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/9916516ce8224a9f99e2d8950dad8f7898943772) | [`423ea93`](https://github.com/fanyang0610/coaching-practice-studio/commit/423ea93c3a3f944f445dda025a029b0aa3f7fa43) | 改进会话阶段跟踪，加入会话满意度 |
| 2026-10-15 23:54 | [`61fa6a4`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/61fa6a45cfa4f8bda4e3cf9f48a22bbcaa7522ed) | [`5573d13`](https://github.com/fanyang0610/coaching-practice-studio/commit/5573d1390828943f5bfa72f81161bdd184a44b92) | 加入批量邀请、登录限速、单条会话删除与服务探活 |
| 2026-10-16 08:03 | [`ca8dc50`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/ca8dc501278501adb5b63a9ae1189140e645bf32) | [`3c129ec`](https://github.com/fanyang0610/coaching-practice-studio/commit/3c129ec8c30b613871117d1be245bd172feeded4) | 练习做教练支持自选议题 |
| 2026-10-16 08:33 | [`c5492f8`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/c5492f8f883b0112aaaba5c5cc1785dc7d71e67c) | [`9e8e516`](https://github.com/fanyang0610/coaching-practice-studio/commit/9e8e51688bb3fae036bcdb64a8127516a4a63dfe) | 自选议题提交后收起输入区，修正首轮阶段识别 |
| 2026-10-16 09:02 | [`8cc10ce`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/8cc10ce577f8fffae9f0255e8115f4b3cb9d6743) | [`7bb9117`](https://github.com/fanyang0610/coaching-practice-studio/commit/7bb9117b51daf0f9db9a8e3c238807869ac71771) | 练习先完成目标合同，再推进阶段 |
| 2026-10-16 09:50 | [`7d43048`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/7d430489f40a60d1c22dca19393159c9d935858b) | [`7ac1a1d`](https://github.com/fanyang0610/coaching-practice-studio/commit/7ac1a1daaea4bd557021913e8b43f8499aa11d7f) | AI 来访者和练习反馈纳入节奏与信任 |
| 2026-10-16 13:03 | [`b6d54fb`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/b6d54fb5b7462746c3983bf08d787a06ab7f8004) | [`9d18234`](https://github.com/fanyang0610/coaching-practice-studio/commit/9d1823430b5b81e9e45722e38e756987849900cd) | 调整朗读声音优先级及浏览器说明 |
| 2026-10-16 19:21 | [`474ff00`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/474ff00005e8589a4051456e31b35c11cc32ffab) | [`2144f7e`](https://github.com/fanyang0610/coaching-practice-studio/commit/2144f7e73d02ec4c395835d863aa2a3fac2ecf06) | 加入朗读声音检查页面 |
| 2026-10-16 23:35 | [`764a66e`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/764a66e6acd6e5cde2aa8027472f7e42ab64b1ff) | [`0bd04a8`](https://github.com/fanyang0610/coaching-practice-studio/commit/0bd04a8c7db7b5fcd058338899ce1344839791ac) | 完善 iPhone 朗读限制和声音提示 |
| 2026-10-17 16:13 | [`850e753`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/850e753af8e6289d46dfa62eb105eff0cc569199) | [`be48daa`](https://github.com/fanyang0610/coaching-practice-studio/commit/be48daaf88b7bb7aee4c1716b176c37d032d1994) | 简化朗读声音检查页面 |
| 2026-10-19 22:37 | [`169099c`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/169099ccc2596c651e1220a423ed5efee6283299) | [`30c5b33`](https://github.com/fanyang0610/coaching-practice-studio/commit/30c5b33afdaf53e0226c7233cbf377575d376d14) · v2.1.0 | 100 条消息上限、剩余提醒与自动收尾 |
| 2026-11-04 17:01 | [`f6c4865`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/f6c48651b60eaa422be916abda1e49d832ee783a) | [`53051b5`](https://github.com/fanyang0610/coaching-practice-studio/commit/53051b558302cb970a528b2b8fc6eb983a77b077) · v2.2.0 | AI 教练显式新开会话 |
| 2026-11-05 09:47 | [`e7bee8a`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/e7bee8a94cc518166044ada57edd974a0b6849c0) | [`b8957a9`](https://github.com/fanyang0610/coaching-practice-studio/commit/b8957a9ef15f7aa435333ff824274ae8ace5781d) · v2.3.0 | 各模式会话恢复，失败点评可重试 |
| 2026-11-05 10:27 | [`98bf670`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/98bf670cc0584a97bf865526a0e264123a0a171e) | [`b3d749c`](https://github.com/fanyang0610/coaching-practice-studio/commit/b3d749c14b8652b8a290ad843f4288ef4e97de1c) · v2.3.1 | 部署仓库整理版，按发布清单上传并清理旧文件 |

## 仅留有 Space 记录的早期改动

这些改动发生于 MVP 早期，尚未找到运行文件一致的 GitHub 提交。按原 Space 提交保留，单次上传、改名或删除记录只说明仓库发生过变化。

| Space 时间 | Space 提交 | 记录 |
| --- | --- | --- |
| 2026-05-02 23:53 | [`ddf9240`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/ddf9240bcc771f2a0bc5be98da9977f071ffd575) | 移除旧的角色实现文件 |
| 2026-05-02 23:53 | [`a2abd07`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/a2abd07e502a61c8c47adc419cb402fa57ea7fb3) | 移除当时的 Git 文件属性配置 |
| 2026-05-02 23:54 | [`51710f2`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/51710f2116cd8bd9326f62199e8c3ce941f22d71) | 移除当时的网页入口 |
| 2026-05-02 23:54 | [`9c07913`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/9c079135177fb9f69a2d3f972e69bd14aa98f30a) | 上传 10 个文件 |
| 2026-05-02 23:59 | [`13ea4cc`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/13ea4ccf7945d5fefa8cb71b4f1a49ac0827ed2b) | 上传 README |
| 2026-05-03 00:22 | [`795fffd`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/795fffd79ff0e44f86dc7f67ce10156d60df3a9d) | 上传项目文档 |
| 2026-05-03 01:00 | [`0a9cbe7`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/0a9cbe7c5f56a46ea7d05a5b68860cc40494754c) | 上传 4 个文件 |
| 2026-05-03 10:21 | [`1573734`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/15737348c2f1ad90fab20da271ffc64329cd78c8) | 上传 2 个文件 |
| 2026-05-03 19:43 | [`e3aa031`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/e3aa031720f09c24aa73510fc93e13ecaaff9252) | 修正本地 Chrome 自动打开 |
| 2026-05-03 19:48 | [`90681b4`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/90681b47096f6cfb65ca97cf8c8ec7d4b6dffa5c) | 移除当时的网页入口 |
| 2026-05-03 19:48 | [`a285bff`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/a285bff9186ccf2a3bf3c587f606aa8aaa1048bd) | 切换网页入口文件名 |
| 2026-05-03 20:08 | [`ccf166d`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/ccf166db99e69ad157ca78a6264bb8e84b2aa05b) | 修正 Mac 启动器及手机设置布局 |
| 2026-05-03 20:40 | [`99c7ea1`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/99c7ea19e5fccc1076e503322b97dd9fbeb17793) | 移除当时的网页入口 |
| 2026-05-03 20:40 | [`7f18922`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/7f18922e274c25283a19cb16a47769055aedc94a) | 切换网页入口文件名 |
| 2026-05-03 20:46 | [`2706db0`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/2706db0b788e833c62d693fefaeadae7ceec2b88) | 记录 Space 入口部署规则 |
| 2026-05-03 20:46 | [`50c9ec8`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/50c9ec8caacaddd769df51492d503fa840292650) | 补充 Space 入口部署说明 |
| 2026-05-03 23:58 | [`227d2b9`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/227d2b900c68e51628738ec3f23f0518f6d7f77c) | 修正桌面设置布局与文字裁切 |
| 2026-05-04 01:58 | [`7e2eb1f`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/7e2eb1fbed14024f3dae13963ea7f64ca068937c) | 上传 README |
| 2026-05-04 01:58 | [`78c358f`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/78c358f03b76951a48c0b6032c76bd08e3946391) | 上传测试文件 |
| 2026-05-05 20:47 | [`77a5285`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/77a52858eb313f1db78c0a154612488dbcb23cc7) | 调整旧版响应式界面 |
| 2026-05-05 21:53 | [`695abf9`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/695abf93c0481ddbb3470031636f1c01c5d3a72f) | 调整手机布局密度 |
| 2026-05-05 22:08 | [`396a4c0`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/396a4c094b3473d91e5a3b9e8cf9004b11edf0e8) | 上传 2 个文件 |
| 2026-05-06 19:20 | [`884729e`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/884729e2a110a5e5eb8b29071bd25cbac46f3187) | 改进 AI 表达变化及模式说明换行 |
| 2026-05-06 23:25 | [`d583060`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/d583060c75cb3adae007f9d5fe50b8007ce5021b) | 上传项目交接文档 |
| 2026-05-06 23:25 | [`793844e`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/793844e9baf84e7b8885bb2089bd6ff9435f242b) | 上传 2 个文件 |
| 2026-05-06 23:26 | [`c1c5ddf`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/c1c5ddf9b243692134607e1b87e8b16af3699d38) | 上传 11 个文件 |
| 2026-05-06 23:26 | [`3b463d7`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/3b463d7378c6d9d34a22d061b2620677ac3d0988) | 上传网页入口 |
| 2026-05-06 23:36 | [`029da1f`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/029da1ff2b16505239a132df1786d3eb95eb7320) | 上传 5 个文件 |
