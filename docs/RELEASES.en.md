# Version history and bilingual releases

English · [简体中文](RELEASES.md)

## Stable versions

Dates are source-commit dates in Beijing time. Historical versions were backfilled. Every GitHub release has Chinese and English notes. v2.7.5 changed documentation and the release process only; v2.8.0 adds What's new to Help.

| Version | Date | Source ref | Main changes |
| --- | --- | --- | --- |
| [v1.0.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v1.0.0) | 2026-05-10 | `996c9e3` | First complete MVP source milestone; core runtime matches the 7 May deployment. |
| [v1.0.1](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v1.0.1) | 2026-05-10 | `85063f1` | Add the root README; same source as the legacy-mvp tag. |
| [v1.0.2](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v1.0.2) | 2026-05-13 | `842e6f4` | Improve isolated-browser checks and layout tests. |
| [v1.0.3](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v1.0.3) | 2026-05-23 | `34461bf` | Add the Hugging Face upload checker and checks. |
| [v2.0.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.0.0) | 2026-10-14 | `68b1f12` | Rename the app, update icons/UI, include accounts, mentors and allowances. |
| [v2.1.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.1.0) | 2026-10-19 | `30c5b33` | Custom topics, phone layout, read-aloud and session wrap-up. |
| [v2.2.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.2.0) | 2026-11-04 | `53051b5` | Explicitly start fresh AI coach sessions. |
| [v2.3.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.3.0) | 2026-11-05 | `b8957a9` | Restore each mode independently and retry failed reviews. |
| [v2.3.1](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.3.1) | 2026-11-05 | `b3d749c` | Rewrite guides, retain legacy configuration and restrict upload files. |
| [v2.3.2](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.3.2) | 2026-11-05 | `595a19b` | Automatic releases and backfilled GitHub/early Space history. |
| [v2.3.3](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.3.3) | 2026-11-05 | `8098675` | Identify the first source milestone as the MVP baseline. |
| [v2.3.4](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.3.4) | 2026-11-05 | `718b7a9` | More natural and varied AI coach openings. |
| [v2.4.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.4.0) | 2026-11-10 | `93c0215` | Action-card failure notices and owner recovery from history. |
| [v2.4.1](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.4.1) | 2026-11-10 | `a0d5fe4` | Complete long-conversation input and capacity wrap-up notices. |
| [v2.4.2](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.4.2) | 2026-11-10 | `95b30ef` | Sum five stage scores and remove turn-count score caps. |
| [v2.5.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.5.0) | 2026-11-10 | `e28bdac` | Owners can edit and remove individual insights. |
| [v2.6.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.6.0) | 2026-11-10 | `77351f8` | Choose, edit or clear one next practice goal. |
| [v2.7.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.7.0) | 2026-11-11 | `a4f2215` | Group account sections and simplify coaching controls. |
| [v2.7.1](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.7.1) | 2026-11-11 | `4174f0f` | Application fixes for long-session endings, persistence, permissions and local tools. |
| [v2.7.2](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.7.2) | 2026-11-11 | `a3f2527` | Drafts, insight concurrency, history pagination, action cards and allowance recovery. |
| [v2.7.3](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.7.3) | 2026-11-13 | `9fb6392` | Correct insight attribution and preserve originals on invalid translation. |
| [v2.7.4](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.7.4) | 2026-11-13 | `4fb3a63` | Administrator concurrency protection, older invites, restored ratings and support replies. |
| [v2.7.5](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.7.5) | 2026-11-13 | `v2.7.5` | Bilingual guides and historical release notes; pre-release documentation review; no app behavior change. |
| [v2.8.0](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.8.0) | 2026-11-13 | `v2.8.0` | What's new in Help, bilingual recent highlights and full GitHub history link. |
| [v2.8.1](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.8.1) | 2026-11-13 | `v2.8.1` | Fill in missing latest-release highlights; the first bilingual entry now covers through v2.8.1. |

v1.0.0 is the first explicitly identified complete MVP source milestone. Its ten core runtime files match the 7 May Space deployment. The later root-README release v1.0.1 shares its source with the original legacy-mvp tag. Source and deployment dates are recorded separately.

## Before every release

1. Determine whether changes affect purpose, usage, features, permissions, data, limitations, configuration or deployment. Review the root README, application/Space README, ARCHITECTURE, DEPLOYMENT, HANDOFF and this guide. Update DESIGN and AGENTS when their rules change. Dated reviews retain their historical context.
2. Update affected documents in Chinese and English, retaining language-switch links. Do not rewrite unaffected documents just for a release; record a specific reason. Do not describe partial checks as complete acceptance or source publication as hosted deployment.
3. Update `.github/release-notes.json`: `zh` and `en` contain the release's substantive notes; `documentation_zh` and `documentation_en` record the documentation decision, changed files or reasons no update is needed. Both languages cover the same facts and limits. Bilingual headings or untranslated commit titles are insufficient. This file holds the current release's notes; GitHub Releases retain historical bodies.
   For application features or user-visible fixes, also maintain the concise Chinese and English `HELP_UPDATES` highlights in `account_pages.py`, newest first, describing only changes delivered with that application. Check that the first entry covers the version being shipped and its user-visible changes, including changes to Help itself. Help keeps recent highlights and links to GitHub Releases for the full history; documentation-only and internal maintenance changes usually do not need highlights. Help does not fetch the latest release at runtime because it may not be deployed yet.
4. Use Conventional Commits, complete relevant checks and push the necessary release commits together to main. The script requires the notes file to differ from the previous version and rejects empty fields, missing language content and TODO/TBD placeholders. It cannot assess translation quality or factual accuracy, which still require maintainer review.

## Automatic publication rules

After a push to main, GitHub Actions reads commit messages since the latest stable tag and creates one release. For several commits in one push, the largest change determines the bump. Development-branch changes are included when merged to main. Rerunning the same commit does not create a duplicate. Missing updated bilingual notes or documentation decisions cause the workflow to fail without creating a release; correct the notes and publish without bypassing the bilingual requirement.

| Commit message | Bump | Starting from 2.7.4 |
| --- | --- | --- |
| A ! prefix such as feat!: or fix!:, or a BREAKING CHANGE: body | Major | 3.0.0 |
| feat: or feat(scope): | Minor | 2.8.0 |
| fix:, docs:, maintenance and other commits | Patch | 2.7.5 |

Retain the right prefix in squash-merge titles. Notes include Chinese and English sections and a documentation decision in each language, plus the full diff and original commit log. Manual creation/editing follows the same bilingual requirement. Translation does not recreate versions or tags; old releases still describe their own time.

GitHub records source. [Hugging Face commits](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commits/main) record the hosted app, deployed separately under [Deployment](../coaching%20and%20coachee_agent_mvp/docs/DEPLOYMENT.en.md). This update does not deploy the Space.

## Traceable historical deployments

Times below come from Space commits and use Beijing time. GitHub matches were established from the then-visible core runtime files. When several commits had identical runtime files, the corresponding release or change-producing commit is preferred.

| Space time | Space commit | GitHub commit | Change |
| --- | --- | --- | --- |
| 2026-05-07 09:25 | [`b8c3463`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/b8c34633ad94c07a8af5448668b36e6ff655b9b8) | [`996c9e3`](https://github.com/fanyang0610/coaching-practice-studio/commit/996c9e3e1fe77b5e3b8b2b7eae059cd42902125d) · v1.0.0 | Deploy the MVP web entry point |
| 2026-10-15 01:16 | [`a9e75eb`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/a9e75eb393eb3e6c893a6c036dfc5935a66b096c) | [`996c9e3`](https://github.com/fanyang0610/coaching-practice-studio/commit/996c9e3e1fe77b5e3b8b2b7eae059cd42902125d) · v1.0.0 | Remove old branding/internal notes; core runtime still matches the MVP |
| 2026-10-15 01:16 | [`1e91c36`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/1e91c363c7895497d29ff354a45aabe1bb40a21c) | [`624ff32`](https://github.com/fanyang0610/coaching-practice-studio/commit/624ff32a33039b7ae6b1cc5ff9cf5626a2971c47) | First matched Studio deployment, including invitation sign-in and phone layout |
| 2026-10-15 01:20 | [`6b0cfc7`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/6b0cfc7d83ca9827c304dcec4922f8a00fc5f3ec) | [`2bb3c9f`](https://github.com/fanyang0610/coaching-practice-studio/commit/2bb3c9f382d7f24867f0b5ba9dd93476b4051d0f) | Serve account pages directly and correct the deployment entry point |
| 2026-10-15 01:38 | [`a8f8488`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/a8f84881c0b7d71df36bf7e98c8ca830fb347cd0) | [`69b095d`](https://github.com/fanyang0610/coaching-practice-studio/commit/69b095d439ddd4b31dd0576c148f888e51ead6f1) | Adjust phone composer, header and language switching |
| 2026-10-15 01:50 | [`52b207d`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/52b207df1f1535e0e3fbfe0406f1c0d78d9c0c92) | [`8e783b1`](https://github.com/fanyang0610/coaching-practice-studio/commit/8e783b14a9cdef75fab761fe9d20650cb22b37e2) | Retry busy model requests and fix language state after translation failure |
| 2026-10-15 01:57 | [`2cbde44`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/2cbde4444eb5b21968cbb6c8ae35d6bf0110c666) | [`8dbf413`](https://github.com/fanyang0610/coaching-practice-studio/commit/8dbf413193c5ada6e0e46ff9f1d900a17184ce26) | Simplify allowance notices and adjust the iPhone header |
| 2026-10-15 10:20 | [`841a635`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/841a6357cd15dc8a823ef299a11b8159f9835d28) | [`8d70c8d`](https://github.com/fanyang0610/coaching-practice-studio/commit/8d70c8d7a6f89dc393e81a23ecd95e253b348cbf) | Address Space loading on mainland China networks |
| 2026-10-15 21:12 | [`9916516`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/9916516ce8224a9f99e2d8950dad8f7898943772) | [`423ea93`](https://github.com/fanyang0610/coaching-practice-studio/commit/423ea93c3a3f944f445dda025a029b0aa3f7fa43) | Improve stage tracking and add session usefulness ratings |
| 2026-10-15 23:54 | [`61fa6a4`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/61fa6a45cfa4f8bda4e3cf9f48a22bbcaa7522ed) | [`5573d13`](https://github.com/fanyang0610/coaching-practice-studio/commit/5573d1390828943f5bfa72f81161bdd184a44b92) | Add group invitations, login rate limits, individual session deletion and health checks |
| 2026-10-16 08:03 | [`ca8dc50`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/ca8dc501278501adb5b63a9ae1189140e645bf32) | [`3c129ec`](https://github.com/fanyang0610/coaching-practice-studio/commit/3c129ec8c30b613871117d1be245bd172feeded4) | Support custom topics for coaching practice |
| 2026-10-16 08:33 | [`c5492f8`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/c5492f8f883b0112aaaba5c5cc1785dc7d71e67c) | [`9e8e516`](https://github.com/fanyang0610/coaching-practice-studio/commit/9e8e51688bb3fae036bcdb64a8127516a4a63dfe) | Collapse submitted topic input and fix first-turn stage detection |
| 2026-10-16 09:02 | [`8cc10ce`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/8cc10ce577f8fffae9f0255e8115f4b3cb9d6743) | [`7bb9117`](https://github.com/fanyang0610/coaching-practice-studio/commit/7bb9117b51daf0f9db9a8e3c238807869ac71771) | Complete the goal agreement before advancing practice stages |
| 2026-10-16 09:50 | [`7d43048`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/7d430489f40a60d1c22dca19393159c9d935858b) | [`7ac1a1d`](https://github.com/fanyang0610/coaching-practice-studio/commit/7ac1a1daaea4bd557021913e8b43f8499aa11d7f) | Include pace and trust in AI coachee behavior and feedback |
| 2026-10-16 13:03 | [`b6d54fb`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/b6d54fb5b7462746c3983bf08d787a06ab7f8004) | [`9d18234`](https://github.com/fanyang0610/coaching-practice-studio/commit/9d1823430b5b81e9e45722e38e756987849900cd) | Adjust read-aloud voice preference and browser guidance |
| 2026-10-16 19:21 | [`474ff00`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/474ff00005e8589a4051456e31b35c11cc32ffab) | [`2144f7e`](https://github.com/fanyang0610/coaching-practice-studio/commit/2144f7e73d02ec4c395835d863aa2a3fac2ecf06) | Add a read-aloud voice-check page |
| 2026-10-16 23:35 | [`764a66e`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/764a66e6acd6e5cde2aa8027472f7e42ab64b1ff) | [`0bd04a8`](https://github.com/fanyang0610/coaching-practice-studio/commit/0bd04a8c7db7b5fcd058338899ce1344839791ac) | Improve iPhone speech-limit guidance and voice notices |
| 2026-10-17 16:13 | [`850e753`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/850e753af8e6289d46dfa62eb105eff0cc569199) | [`be48daa`](https://github.com/fanyang0610/coaching-practice-studio/commit/be48daaf88b7bb7aee4c1716b176c37d032d1994) | Simplify the voice-check page |
| 2026-10-19 22:37 | [`169099c`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/169099ccc2596c651e1220a423ed5efee6283299) | [`30c5b33`](https://github.com/fanyang0610/coaching-practice-studio/commit/30c5b33afdaf53e0226c7233cbf377575d376d14) · v2.1.0 | 100-user-message limit, remaining-message notices and automatic wrap-up |
| 2026-11-04 17:01 | [`f6c4865`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/f6c48651b60eaa422be916abda1e49d832ee783a) | [`53051b5`](https://github.com/fanyang0610/coaching-practice-studio/commit/53051b558302cb970a528b2b8fc6eb983a77b077) · v2.2.0 | Explicitly start a fresh AI coach session |
| 2026-11-05 09:47 | [`e7bee8a`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/e7bee8a94cc518166044ada57edd974a0b6849c0) | [`b8957a9`](https://github.com/fanyang0610/coaching-practice-studio/commit/b8957a9ef15f7aa435333ff824274ae8ace5781d) · v2.3.0 | Restore each mode and retry failed reviews |
| 2026-11-05 10:27 | [`98bf670`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/98bf670cc0584a97bf865526a0e264123a0a171e) | [`b3d749c`](https://github.com/fanyang0610/coaching-practice-studio/commit/b3d749c14b8652b8a290ad843f4288ef4e97de1c) · v2.3.1 | Deploy repository cleanup, use the upload list and remove old files |

## Early changes recorded only on the Space

These records go back to creation of the Space on 7 March 2026. No GitHub commit with matching runtime files has been identified. Original Space commits are retained; an upload, rename or deletion alone only establishes a repository change.

| Space time | Space commit | Record |
| --- | --- | --- |
| 2026-03-07 11:08 | [`bd247f2`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/bd247f2060dfc0bff07956606fe7bb78848fdbb9) | Create the Space repository |
| 2026-03-07 11:14 | [`49519a9`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/49519a95c6d7f48761797914ead0068abc5dba57) | Upload three files, including `agent.py`, `requirements.txt`, `web_app.py` |
| 2026-03-07 11:16 | [`67dcda2`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/67dcda2e0757da0d7c95544a4e5131094e10aea8) | Upload the web entry point |
| 2026-03-07 14:33 | [`4da32b9`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/4da32b96819ee9196ca59b367f28b61bd8571a87) | Remove the then-current web implementation |
| 2026-03-07 14:49 | [`5227ee6`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/5227ee60510cdbe1d54282c191cadfc9bd3f961f) | Upload two files, including `app.py` |
| 2026-03-07 14:49 | [`9a1f9fd`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/9a1f9fdbcdb11914d50a4208ea46f7ecd4033e86) | Upload the coach-role implementation |
| 2026-03-07 15:04 | [`2e9d6dc`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/2e9d6dc24f4bca03a92b1b229a9a376b2d39e790) | Upload the web entry point |
| 2026-03-07 15:11 | [`a260843`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/a260843f9b407274d32673e5b28d63fb495a2a3d) | Upload the web entry point |
| 2026-03-07 15:17 | [`2951fd7`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/2951fd7d02419619e976cdb02732a666554fcccc) | Upload the web entry point |
| 2026-03-07 17:50 | [`bba62eb`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/bba62eb1e510a5e2d8b19939cdc2b13d9305bca0) | Upload the web entry point |
| 2026-03-07 17:55 | [`ab55115`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/ab55115e442f8602470054cd51e68493b5029981) | Upload the web entry point |
| 2026-03-07 19:06 | [`6f97203`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/6f972039a09a110e224448e8ccd9368f4addfae0) | Upload the web entry point |
| 2026-03-07 21:06 | [`e95d2b4`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/e95d2b4118aab2ae5de5b65d7eb174e3c01b7b54) | Upload the web entry point |
| 2026-03-07 21:44 | [`12ff8f2`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/12ff8f2da3f01af9d070a197970aef4bfc3ddd47) | Upload the web entry point |
| 2026-03-08 11:08 | [`7d348f3`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/7d348f34cf46bb82b34eb041896483743e3f958a) | Upload three files, including `app.py`, `agent.py` |
| 2026-03-08 11:50 | [`e07c69d`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/e07c69d4d4365cf1bd6455051d280a56b86db6d9) | Upload the web entry point |
| 2026-03-08 12:06 | [`368a51e`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/368a51e493fc5e3c6e7a29b22b8ba8758d50ac62) | Upload the web entry point |
| 2026-03-08 12:36 | [`0f08964`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/0f089648801d45a7bc4e2cb6adc31108161c4ecb) | Upload the web entry point |
| 2026-03-08 12:45 | [`78c35ff`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/78c35fff817814ddc2df0af7f38c2773eff02f7c) | Upload the web entry point |
| 2026-03-08 13:08 | [`edde368`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/edde368e889fab1626a57bed142d3be1d3197cd7) | Upload the web entry point |
| 2026-03-09 21:42 | [`d6164a0`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/d6164a0ce8ff5134d7abd84f357ab9dfdb340fb2) | Upload two files, including `app.py`, `agent.py` |
| 2026-03-09 21:49 | [`7a29b66`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/7a29b6614468c9d1f569ee714b7d998c4037498c) | Upload four files, including `agent.py`, `coachee_agent.py` |
| 2026-03-09 22:25 | [`5d97c16`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/5d97c161150fed2d28afd49f949e0273175ac447) | Upload two files, including `app.py`, `coachee_agent.py` |
| 2026-03-09 22:36 | [`7a6adc9`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/7a6adc9f368c1cc407ea06eab4ea8adbf9cac8fb) | Upload two files, including `app.py`, `coachee_agent.py` |
| 2026-03-09 22:43 | [`ed94ec8`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/ed94ec8f8831a910a7989c958f5dcf055ca57fda) | Upload the web entry point |
| 2026-03-09 22:50 | [`ebcbd4e`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/ebcbd4efc10d1478c0ca26a65a6909ce0106abea) | Upload the web entry point |
| 2026-03-09 23:19 | [`3df98bc`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/3df98bc54e396a4342ccb46dcdc2ef132d84c022) | Upload two files, including `coachee_agent.py` |
| 2026-03-11 19:28 | [`635400f`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/635400f881e95edddda28cf6a0d988ef797bd717) | Upload two files, including `agent.py`, `coachee_agent.py` |
| 2026-03-11 20:01 | [`26aca8c`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/26aca8cd7ed7b8616957d9dc006ef949e080dd5a) | Upload five files, including `app.py`, `agent.py`, `requirements.txt`, `coachee_agent.py`, `memory.py` |
| 2026-05-02 23:53 | [`ddf9240`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/ddf9240bcc771f2a0bc5be98da9977f071ffd575) | Remove the old role implementation |
| 2026-05-02 23:53 | [`a2abd07`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/a2abd07e502a61c8c47adc419cb402fa57ea7fb3) | Remove the then-current Git attributes configuration |
| 2026-05-02 23:54 | [`51710f2`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/51710f2116cd8bd9326f62199e8c3ce941f22d71) | Remove the then-current web entry point |
| 2026-05-02 23:54 | [`9c07913`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/9c079135177fb9f69a2d3f972e69bd14aa98f30a) | Upload ten files |
| 2026-05-02 23:59 | [`13ea4cc`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/13ea4ccf7945d5fefa8cb71b4f1a49ac0827ed2b) | Upload README |
| 2026-05-03 00:22 | [`795fffd`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/795fffd79ff0e44f86dc7f67ce10156d60df3a9d) | Upload project documentation |
| 2026-05-03 01:00 | [`0a9cbe7`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/0a9cbe7c5f56a46ea7d05a5b68860cc40494754c) | Upload four files |
| 2026-05-03 10:21 | [`1573734`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/15737348c2f1ad90fab20da271ffc64329cd78c8) | Upload two files |
| 2026-05-03 19:43 | [`e3aa031`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/e3aa031720f09c24aa73510fc93e13ecaaff9252) | Fix automatic local Chrome opening |
| 2026-05-03 19:48 | [`90681b4`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/90681b47096f6cfb65ca97cf8c8ec7d4b6dffa5c) | Remove the then-current web entry point |
| 2026-05-03 19:48 | [`a285bff`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/a285bff9186ccf2a3bf3c587f606aa8aaa1048bd) | Change the web entry-point filename |
| 2026-05-03 20:08 | [`ccf166d`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/ccf166db99e69ad157ca78a6264bb8e84b2aa05b) | Fix the Mac launcher and phone settings layout |
| 2026-05-03 20:40 | [`99c7ea1`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/99c7ea19e5fccc1076e503322b97dd9fbeb17793) | Remove the then-current web entry point |
| 2026-05-03 20:40 | [`7f18922`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/7f18922e274c25283a19cb16a47769055aedc94a) | Change the web entry-point filename |
| 2026-05-03 20:46 | [`2706db0`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/2706db0b788e833c62d693fefaeadae7ceec2b88) | Record Space entry-point deployment rules |
| 2026-05-03 20:46 | [`50c9ec8`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/50c9ec8caacaddd769df51492d503fa840292650) | Expand Space entry-point deployment guidance |
| 2026-05-03 23:58 | [`227d2b9`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/227d2b900c68e51628738ec3f23f0518f6d7f77c) | Fix desktop settings layout and clipped text |
| 2026-05-04 01:58 | [`7e2eb1f`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/7e2eb1fbed14024f3dae13963ea7f64ca068937c) | Upload README |
| 2026-05-04 01:58 | [`78c358f`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/78c358f03b76951a48c0b6032c76bd08e3946391) | Upload test files |
| 2026-05-05 20:47 | [`77a5285`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/77a52858eb313f1db78c0a154612488dbcb23cc7) | Adjust the legacy responsive interface |
| 2026-05-05 21:53 | [`695abf9`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/695abf93c0481ddbb3470031636f1c01c5d3a72f) | Adjust phone layout density |
| 2026-05-05 22:08 | [`396a4c0`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/396a4c094b3473d91e5a3b9e8cf9004b11edf0e8) | Upload two files |
| 2026-05-06 19:20 | [`884729e`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/884729e2a110a5e5eb8b29071bd25cbac46f3187) | Vary AI phrasing and fix mode-description wrapping |
| 2026-05-06 23:25 | [`d583060`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/d583060c75cb3adae007f9d5fe50b8007ce5021b) | Upload project handoff notes |
| 2026-05-06 23:25 | [`793844e`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/793844e9baf84e7b8885bb2089bd6ff9435f242b) | Upload two files |
| 2026-05-06 23:26 | [`c1c5ddf`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/c1c5ddf9b243692134607e1b87e8b16af3699d38) | Upload eleven files |
| 2026-05-06 23:26 | [`3b463d7`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/3b463d7378c6d9d34a22d061b2620677ac3d0988) | Upload the web entry point |
| 2026-05-06 23:36 | [`029da1f`](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/029da1ff2b16505239a132df1786d3eb95eb7320) | Upload five files |
