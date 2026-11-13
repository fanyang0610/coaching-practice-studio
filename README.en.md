# Coaching Practice Studio · 教练练习室

English · [简体中文](README.md)

Coaching Practice Studio is an independent, free, non-commercial web app in English and Simplified Chinese. It provides a practice space for people exploring coaching, learning coaching skills and mentoring learners. It uses a general solution-focused coaching approach to help people explore their own goals, resources and next steps.

| Mode | How it works | Possible outcome |
| --- | --- | --- |
| **Be coached** | Bring a real topic to a conversation with an AI coach. | An action card extracted from the conversation, with a next step and any stated goal, timing and support. Without a concrete next step, there may be no card. |
| **Practise coaching** | Ask questions and guide an AI coachee through a random scenario or your chosen topic. | A review with five stage scores, a total, specific feedback and a suggested next focus. |

Both modes show five-stage progress and save conversations independently. Sign in to the same account on a phone or computer to continue. The account page provides paginated history, action cards, practice scores and data controls.

## Current features and status

As of **13 November 2026**, application features are released through [v2.7.4](https://github.com/fanyang0610/coaching-practice-studio/releases/tag/v2.7.4). This documentation and release-process update does not change application behavior. See [GitHub Releases](https://github.com/fanyang0610/coaching-practice-studio/releases) for subsequent source versions.

- **Resume and recover**: each mode restores its own progress; a new conversation replaces the current one only after it succeeds. Ending distinguishes no extracted action, generation failure and save failure. Owners can recover eligible missing action cards from history and retry failed practice reviews.
- **Owner-controlled insights**: edit or remove individual AI insights, or clear them. Be coached records observations, resources and questions expressed by the human client; practice mode records observations about coaching practice. Later use reads the currently saved content. Similar wording may still appear as a new observation.
- **Next practice goal**: choose from practice insights or write one coaching skill to work on. Edit or clear it at any time. It informs preparation of a new AI coachee case; the app does not automatically assess achievement or improvement.
- **Mentors and privacy**: assigned mentors can review learners' practice conversations. Be coached conversations stay private unless their owner shares them. Administrator pages manage accounts, invitations and allowances, and show usage and usefulness statistics without an administrative transcript view. Users can download their own JSON data, delete individual conversations or delete their account.
- **Language and voice**: English and Simplified Chinese, browser speech input and read-aloud. Availability depends on the device, browser and installed voices.

Each conversation allows up to **100 user messages**, with **2,000 characters per message**. Model requests include the complete conversation; recognized model capacity limits trigger a wrap-up warning. Receiving the full text does not guarantee correct AI understanding.

This is a practice tool. The program adds the five stage scores, but stage judgments, feedback, progress detection and insights still depend on AI. Stable scoring, comparability between sessions and improvements in coaching ability have not been established. The app does not provide professional certification, therapy or crisis support. Recent fixes received isolated functional, database, desktop and phone-sized browser checks; this does not mean every model, production-account flow or physical-device Safari experience was verified.

## Use online

Open the [studio](https://fanyang0610-coaching-practice-studio.hf.space), register through an invitation link and sign in. Switch modes at the top of the page. See [Help](https://fanyang0610-coaching-practice-studio.hf.space/help?lang=en) for use and privacy rules.

GitHub Releases identify source versions; Hugging Face deployments are separate. The latest recorded application deployment is [4932350](https://huggingface.co/spaces/fanyang0610/Coaching-Practice-Studio/commit/4932350d83865ee343e8371ec8a9bcfc5cb37879), corresponding to v2.7.4. Updating documentation does not automatically deploy the hosted application.

## Run locally

Use Python 3.10 or later. From the repository root, run the following commands. On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

```sh
cd "coaching and coachee_agent_mvp"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**Try the demo**: run `python scripts/dev_server.py`, open the [local studio](http://127.0.0.1:8797), and use the temporary accounts and password printed in the terminal. The demo uses a fake AI service and an isolated temporary database; no model key is needed.

**Connect your own model**: on first setup, copy `.env.example` to `.env`. Set `OPENAI_API_KEY`, `OPENAI_MODEL` and, if required by your provider, `OPENAI_BASE_URL`. Run `python app.py`, open the printed address and create the first administrator. Administrators can then create invitation links. The example configuration does not identify the hosted model.

On macOS, `python scripts/check_project.py --launcher` generates `Coaching Practice Studio.app` with its icon. Keep the launcher in the application directory and double-click it to start.

## Technology and maintainer guides

Gradio provides the practice interface; FastAPI serves sign-in, account, mentor and administrator pages; Uvicorn runs the service. AI connects through an OpenAI-compatible API. SQLAlchemy handles storage, with SQLite by default locally and PostgreSQL in the current hosted environment. The online app runs on Hugging Face Spaces.

| Guide | 中文 | English |
| --- | --- | --- |
| Space introduction | [README](coaching%20and%20coachee_agent_mvp/README.md) | [README](coaching%20and%20coachee_agent_mvp/README.en.md) |
| Architecture and development checks | [架构](coaching%20and%20coachee_agent_mvp/docs/ARCHITECTURE.md) | [Architecture](coaching%20and%20coachee_agent_mvp/docs/ARCHITECTURE.en.md) |
| Configuration and deployment | [部署](coaching%20and%20coachee_agent_mvp/docs/DEPLOYMENT.md) | [Deployment](coaching%20and%20coachee_agent_mvp/docs/DEPLOYMENT.en.md) |
| Maintenance handoff and limitations | [交接](coaching%20and%20coachee_agent_mvp/docs/HANDOFF.md) | [Handoff](coaching%20and%20coachee_agent_mvp/docs/HANDOFF.en.md) |
| Version history and bilingual release rules | [版本](docs/RELEASES.md) | [Releases](docs/RELEASES.en.md) |

UI changes follow the existing [DESIGN.md](coaching%20and%20coachee_agent_mvp/DESIGN.md) and [AGENTS.md](coaching%20and%20coachee_agent_mvp/AGENTS.md) in the application directory. Those existing rules and dated historical reviews were not rewritten in this update.
