import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

# Tests must never reach the real model: blank the key before web_app loads .env (which won't override it).
os.environ["OPENAI_API_KEY"] = ""

import accounts  # noqa: E402
import db  # noqa: E402

from coach_agent import CoachAgent
from coachee_agent import CoacheeAgent
from coaching_core import CoachingState, _clean_response_language, _response_text
from memory import MAX_PROFILE_ITEMS, UserProfile, merge_analysis


class TestAgentModuleBoundaries(unittest.TestCase):
    def test_explicit_agent_modules_replace_generic_agent_file(self):
        root = Path(__file__).resolve().parent

        self.assertIsNotNone(importlib.util.find_spec("coach_agent"))
        self.assertIsNotNone(importlib.util.find_spec("coaching_core"))
        self.assertFalse((root / "agent.py").exists())


class TestEntrypointsAndDeploymentIgnores(unittest.TestCase):
    def test_app_import_exposes_gradio_demo_without_cli_input(self):
        import app
        import web_app

        self.assertIs(app.demo, web_app.demo)
        self.assertIs(app.launch_demo, web_app.launch_demo)

    def test_cli_entrypoint_preserves_terminal_main(self):
        import cli_app

        self.assertTrue(callable(cli_app.main))

    def test_space_runs_the_gradio_version_tested_here(self):
        # Unpinned, the Space installed whatever Gradio was newest (6.30 while this Mac had 6.8), so the hosted app ran
        # a version never checked here; the China loading fix and the layout rules depend on Gradio's internals.
        import gradio

        root = Path(__file__).resolve().parent
        sdk = re.search(r"^sdk_version:\s*(\S+)\s*$", (root / "README.md").read_text(encoding="utf-8"), re.M)
        pin = re.search(r"^gradio==(\S+)\s*$", (root / "requirements.txt").read_text(encoding="utf-8"), re.M)

        self.assertIsNotNone(sdk, "README front matter needs sdk_version")
        self.assertIsNotNone(pin, "requirements.txt needs an exact gradio==version")
        self.assertEqual(sdk.group(1), pin.group(1))
        self.assertEqual(gradio.__version__, pin.group(1), "install the pinned Gradio here: pip install -r requirements.txt")

    def test_hf_deploy_helper_stages_web_app_as_remote_app(self):
        root = Path(__file__).resolve().parent
        helper_path = root / "scripts" / "deploy_hf_space.py"
        spec = importlib.util.spec_from_file_location("deploy_hf_space", helper_path)
        deploy_hf_space = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deploy_hf_space)

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "source"
            for path in (*deploy_hf_space.SPACE_FILES, Path("app.py")):
                target = fixture / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / path, target)

            extras = (".env", ".env.local", ".venv/bin/python", "scratch.db", "user_profile.json",
                      "docs/HANDOFF.md", "tests.py", "assets/icons/local-note.txt")
            for name in extras:
                path = fixture / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("local-only fixture", encoding="utf-8")

            staged_root = Path(temp_dir) / "stage"
            staged_files = deploy_hf_space.stage_space(fixture, staged_root)

            self.assertIn(Path("app.py"), staged_files)
            self.assertNotIn(Path("web_app.py"), staged_files)
            for name in extras:
                self.assertFalse((staged_root / name).exists(), name)
            self.assertEqual(
                (staged_root / "app.py").read_bytes(),
                (root / "web_app.py").read_bytes(),
            )
            self.assertNotEqual(
                (staged_root / "app.py").read_bytes(),
                (root / "app.py").read_bytes(),
            )

    def test_hf_upload_decision_reports_local_verification_changes_only(self):
        root = Path(__file__).resolve().parent
        helper_path = root / "scripts" / "needs_hf_upload.py"
        spec = importlib.util.spec_from_file_location("needs_hf_upload", helper_path)
        needs_hf_upload = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(needs_hf_upload)

        decision = needs_hf_upload.decide_upload_need([Path("manual_ui_probe.py"), Path("tests.py")])

        self.assertFalse(decision.needs_upload)
        self.assertEqual(decision.deploy_worthy, [])
        self.assertEqual([item.path for item in decision.local_only], [Path("manual_ui_probe.py"), Path("tests.py")])

    def test_hf_upload_decision_uses_deploy_entrypoint_mapping(self):
        root = Path(__file__).resolve().parent
        deploy_path = root / "scripts" / "deploy_hf_space.py"
        deploy_spec = importlib.util.spec_from_file_location("deploy_hf_space", deploy_path)
        deploy_hf_space = importlib.util.module_from_spec(deploy_spec)
        deploy_spec.loader.exec_module(deploy_hf_space)

        helper_path = root / "scripts" / "needs_hf_upload.py"
        helper_spec = importlib.util.spec_from_file_location("needs_hf_upload", helper_path)
        needs_hf_upload = importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(needs_hf_upload)

        decision = needs_hf_upload.decide_upload_need([Path("web_app.py"), Path("app.py")])

        self.assertTrue(decision.needs_upload)
        self.assertEqual(len(decision.deploy_worthy), 1)
        self.assertEqual(decision.deploy_worthy[0].path, Path("web_app.py"))
        self.assertEqual(decision.deploy_worthy[0].remote_path, deploy_hf_space.REMOTE_ENTRYPOINT)
        self.assertIn("Space entrypoint", decision.deploy_worthy[0].reason)
        self.assertEqual([item.path for item in decision.local_only], [Path("app.py")])

    def test_hf_upload_decision_strips_repo_prefix_from_git_paths(self):
        root = Path(__file__).resolve().parent
        helper_path = root / "scripts" / "needs_hf_upload.py"
        spec = importlib.util.spec_from_file_location("needs_hf_upload", helper_path)
        needs_hf_upload = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(needs_hf_upload)

        prefix = "coaching and coachee_agent_mvp/"
        status_output = "\0".join(
            [
                f" M {prefix}web_app.py",
                f"?? {prefix}tests.py",
                f"R  {prefix}assets/icons/studio-icon-180.png",
                f"{prefix}assets/icons/previous-icon.png",
                " M README.md",
                "",
            ]
        )

        changed_paths = needs_hf_upload._parse_git_status(status_output, prefix)
        decision = needs_hf_upload.decide_upload_need(changed_paths)

        self.assertEqual(
            changed_paths,
            [Path("web_app.py"), Path("tests.py"), Path("assets/icons/studio-icon-180.png"),
             Path("assets/icons/previous-icon.png")],
        )
        self.assertTrue(decision.needs_upload)
        self.assertIn(Path("web_app.py"), [item.path for item in decision.deploy_worthy])
        self.assertNotIn(Path("README.md"), [item.path for item in decision.deploy_worthy])
        self.assertIn(Path("assets/icons/studio-icon-180.png"), [item.path for item in decision.deploy_worthy])
        self.assertEqual([item.path for item in decision.local_only],
                         [Path("assets/icons/previous-icon.png"), Path("tests.py")])

    def test_macos_launcher_disables_default_browser_auto_open(self):
        root = Path(__file__).resolve().parent
        launcher_text = (root / "Coaching Practice Studio Launcher.applescript").read_text(encoding="utf-8")

        self.assertIn("STUDIO_INBROWSER=0", launcher_text)

    def test_macos_launcher_opens_ui_through_project_launcher(self):
        root = Path(__file__).resolve().parent
        launcher_text = (root / "Coaching Practice Studio Launcher.applescript").read_text(encoding="utf-8")

        self.assertIn("python3 mac_launcher.py", launcher_text)

    def test_mac_launcher_uses_isolated_chrome_profile(self):
        import mac_launcher

        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / "studio-coach-chrome-profile"
            with patch.object(mac_launcher, "CHROME_PROFILE", profile):
                cmd = mac_launcher.chrome_command("http://127.0.0.1:7860")

        self.assertIn(f"--user-data-dir={profile}", cmd)
        self.assertIn("--no-first-run", cmd)
        self.assertIn("http://127.0.0.1:7860", cmd)

    def test_project_check_runner_exists(self):
        root = Path(__file__).resolve().parent
        helper_path = root / "scripts" / "check_project.py"
        spec = importlib.util.spec_from_file_location("check_project", helper_path)
        self.assertIsNotNone(spec)
        check_project = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(check_project)

        self.assertTrue(callable(check_project.main))

    def test_project_check_reinstalls_custom_launcher_icon_after_compile(self):
        root = Path(__file__).resolve().parent
        helper_path = root / "scripts" / "check_project.py"
        spec = importlib.util.spec_from_file_location("check_project", helper_path)
        check_project = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(check_project)

        self.assertEqual(
            check_project.LAUNCHER_ICON_SOURCE,
            root / "assets" / "icons" / "StudioIcon.icns",
        )
        self.assertTrue(check_project.LAUNCHER_ICON_SOURCE.exists())
        self.assertEqual(
            check_project.LAUNCHER_ICON_TARGET,
            root / "Coaching Practice Studio.app" / "Contents" / "Resources" / "applet.icns",
        )
        self.assertTrue(callable(check_project.compile_launcher))


class TestExistingInstallation(unittest.TestCase):
    def test_existing_local_database_and_signing_file_are_used_in_place(self):
        import web_app
        from studio_config import LEGACY_NAME

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old_db = root / f"{LEGACY_NAME}.db"
            old_secret = root / f".{LEGACY_NAME}_secret"
            old_secret.write_text("existing-local-secret", encoding="utf-8")
            store = db.Store(f"sqlite:///{old_db}")
            user_id = store.create_user("owner@example.test", "Owner", accounts.hash_password("existing-password"),
                                        role="admin", consented=True)
            session_id = store.create_session(user_id, "coach", "zh", "template", "CONTRACT", {"context": []})
            store.engine.dispose()

            with patch.object(db, "DEFAULT_SQLITE_PATH", root / "studio.db"), \
                    patch.object(web_app, "LOCAL_SECRET_FILE", root / ".studio_secret"):
                upgraded_store = db.Store(db.database_url({}))
                try:
                    self.assertEqual(upgraded_store.get_session(session_id)["user_id"], user_id)
                    self.assertEqual(web_app._secret_key({}), "existing-local-secret")
                finally:
                    upgraded_store.engine.dispose()

            self.assertFalse((root / "studio.db").exists())
            self.assertFalse((root / ".studio_secret").exists())

    def test_old_hosted_settings_and_cookies_keep_login_and_csrf_working(self):
        from fastapi.testclient import TestClient
        from studio_config import LEGACY_NAME
        import web_app

        secret = "existing-hosted-secret"
        email = "owner@example.test"
        old_prefix = LEGACY_NAME.upper()
        env = {"SPACE_ID": "test", f"{old_prefix}_SECRET_KEY": secret,
               f"{old_prefix}_ADMIN_EMAIL": email, f"{old_prefix}_ADMIN_PASSWORD": "existing-password"}
        self.assertEqual(web_app._secret_key(dict(env, STUDIO_SECRET_KEY="new-secret")), "new-secret")
        store = db.Store("sqlite://")
        app = web_app.create_app(store=store, env=env)
        with TestClient(app, base_url="https://studio.example.test") as client:
            value = accounts.make_session_cookie(store.get_user_by_email(email), secret)
            client.cookies.set(f"{LEGACY_NAME}_session", value, domain="studio.example.test")
            client.cookies.set(f"{LEGACY_NAME}_lang", "zh", domain="studio.example.test")
            csrf = accounts.csrf_token(value, secret)
            page = client.get("/account", follow_redirects=False)
            self.assertEqual(page.status_code, 200)
            self.assertIn('<html lang="zh', page.text)
            self.assertIn(f'name="csrf" value="{csrf}"', page.text)

            response = client.post("/logout", data={"csrf": csrf}, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(client.get("/account", follow_redirects=False).status_code, 303)


class TestCoachAgent(unittest.TestCase):
    def setUp(self):
        self.agent = CoachAgent(mode="template")

    def test_initial_state(self):
        self.assertEqual(self.agent.current_state, CoachingState.CONTRACT)
        self.assertEqual(self.agent.mode, "template")

    def test_mode_switch(self):
        self.agent.set_mode("llm")
        self.assertEqual(self.agent.mode, "llm")
        self.agent.set_mode("invalid_mode")
        self.assertEqual(self.agent.mode, "llm")

    def test_template_state_progression_matches_contract(self):
        self.agent.generate_response("")
        self.assertEqual(self.agent.current_state, CoachingState.CONTRACT)

        self.agent.generate_response("I want to get better at managing my time.")
        self.assertEqual(self.agent.current_state, CoachingState.CONTRACT)

        self.agent.generate_response("I usually get distracted easily.")
        self.assertEqual(self.agent.current_state, CoachingState.CONTRACT)

        self.agent.generate_response("But I am good at making lists.")
        self.assertEqual(self.agent.current_state, CoachingState.CONTRACT)

        self.agent.generate_response("I could try the Pomodoro technique.")
        self.assertEqual(self.agent.current_state, CoachingState.CONTRACT)

        self.agent.generate_response("I'll set a timer for 25 minutes.")
        self.assertEqual(self.agent.current_state, CoachingState.EXPERIENCE)

    def test_llm_opening_prompt_includes_session_variation(self):
        captured_messages = []

        class FakeCompletions:
            def create(self, **kwargs):
                captured_messages.extend(kwargs["messages"])
                message = type("Message", (), {"content": "What would be most useful to explore today?"})()
                choice = type("Choice", (), {"message": message})()
                return type("Response", (), {"choices": [choice]})()

        class FakeClient:
            chat = type("Chat", (), {"completions": FakeCompletions()})()

        agent = CoachAgent(mode="llm", language="en")
        with patch("coach_agent._build_client", return_value=FakeClient()):
            agent._get_llm_opening_response("server-key")

        prompt = captured_messages[0]["content"]
        self.assertIn("Session variation seed:", prompt)
        self.assertIn(agent.opening_variation_seed, prompt)
        self.assertIn("avoid repeating common default openings", prompt)

    def test_force_next_state(self):
        self.assertEqual(self.agent.current_state, CoachingState.CONTRACT)

        self.agent.force_next_state()
        self.assertEqual(self.agent.current_state, CoachingState.EXPERIENCE)

        self.agent.force_next_state()
        self.agent.force_next_state()
        self.assertEqual(self.agent.current_state, CoachingState.VALUE)

        self.agent.force_next_state()
        self.assertEqual(self.agent.current_state, CoachingState.CLOSING)

        self.assertFalse(self.agent.force_next_state())
        self.assertEqual(self.agent.current_state, CoachingState.CLOSING)

    def test_translate_history_handles_bridge_messages(self):
        agent = CoachAgent(mode="template", language="zh")
        agent.generate_response("")
        agent.generate_response("目标是改善时间管理")
        agent.generate_response("我经常拖延")
        agent.generate_response("但我会列清单")
        agent.generate_response("我可以试试番茄钟")

        agent.translate_history("en")

        coach_messages = [msg["content"] for msg in agent.context if msg["role"] == "coach"]
        self.assertTrue(any(any(marker in msg for marker in ("What ", "How ", "If ", "Tell me", "On a scale")) for msg in coach_messages))
        self.assertTrue(any("Now that we have a clear focus" in msg for msg in coach_messages))

    def test_get_stage_prompt_requires_key_in_llm_mode(self):
        agent = CoachAgent(mode="llm")
        with self.assertRaises(ValueError):
            agent.get_stage_prompt()

    def test_response_text_handles_structured_and_empty_content(self):
        part = type("Part", (), {"text": "Structured reply"})()
        message = type("Message", (), {"content": [part], "refusal": None})()
        response = type("Response", (), {"choices": [type("Choice", (), {"message": message})()]})()
        self.assertEqual(_response_text(response), "Structured reply")

        empty_message = type("Message", (), {"content": None, "refusal": None})()
        empty_response = type("Response", (), {"choices": [type("Choice", (), {"message": empty_message})()]})()
        with self.assertRaises(ValueError):
            _response_text(empty_response)

    def test_empty_ai_reply_is_tried_once_more_then_reported_not_replaced(self):
        # No canned stand-in: the web app keeps the client's message and asks them to send it again.
        agent = CoachAgent(mode="llm", language="en")
        agent.context = [{"role": "coach", "content": "What brings you here?"}]
        empty = ValueError("Model returned no text content.")

        with patch.object(agent, "_get_llm_response", side_effect=[empty, iter([("Say more?", "GOAL")])]):
            self.assertEqual(agent.generate_response("A career decision.", api_key="server-key"), "Say more?")
        with patch.object(agent, "_get_llm_response", side_effect=[empty, empty]):
            with self.assertRaises(ValueError):
                agent.generate_response("Still there?", api_key="server-key")

        self.assertEqual(agent.context[-1]["content"], "Say more?")  # the failed turn left nothing behind
        self.assertEqual(agent.mode, "llm")

    def test_chinese_ai_output_removes_pinyin_and_english_translation(self):
        mixed = (
            "今天，你希望在我们的谈话中，关注到什么呢？ "
            "（Jīntiān, nǐ xīwàng zài wǒmen de tánhuà zhōng, guānzhù dào shénme ne?）\n\n"
            "(Today, what would you like to focus on in our conversation?)"
        )

        self.assertEqual(
            _clean_response_language(mixed, "zh"),
            "今天，你希望在我们的谈话中，关注到什么呢？",
        )


class TestWebAppLayout(unittest.TestCase):
    def test_launch_injects_mobile_viewport_head(self):
        import web_app

        head = web_app.head
        self.assertIn('name="viewport"', head)
        self.assertIn("width=device-width", head)
        self.assertIn("initial-scale=1", head)
        self.assertIn("interactive-widget=resizes-content", head)
        with patch.object(web_app.gr, "mount_gradio_app") as mount:
            web_app.create_app(store=db.Store("sqlite://"), env={"STUDIO_SECRET_KEY": "test-secret"})
        self.assertEqual(web_app.head, mount.call_args.kwargs["head"])
    def test_mobile_css_uses_real_mobile_layout_not_viewport_clamps(self):
        from web_app import css

        self.assertIn("@media (max-width: 768px)", css)
        self.assertNotIn("calc(100vw - 72px)", css)
        self.assertNotIn("calc(100vw - 76px)", css)
        self.assertNotIn("max-width: 300px", css)
        self.assertIn("height: 100dvh", css)
        self.assertIn("#topbar.module-tabs", css)
        self.assertIn("overflow: hidden", css)

    def test_mobile_module_tabs_stay_two_up_and_chat_clear_is_hidden(self):
        from web_app import css, global_viewport_style

        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr)) !important", css)
        self.assertIn("#topbar.module-tabs > .form > div", css)
        self.assertIn("flex: 1 1 0", css)
        combined_css = f"{css}\n{global_viewport_style}"
        self.assertIn('button[title="Clear"]', combined_css)
        self.assertIn('[aria-label="Clear"]', combined_css)

    def test_settings_controls_fill_desktop_and_stack_on_mobile(self):
        root = Path(__file__).resolve().parent
        source = (root / "web_app.py").read_text(encoding="utf-8")
        from web_app import css

        self.assertIn("settings-controls", css)
        self.assertIn('with gr.Row(elem_classes="settings-controls")', source)
        self.assertIn(".settings-controls {\n    display: block !important", css)
        self.assertIn(".settings-controls > .form {\n    display: grid !important", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr)) !important", css)
        self.assertIn("grid-template-columns: minmax(0, 1fr) !important", css)

    def test_settings_text_has_left_breathing_room(self):
        from web_app import css

        self.assertIn(".settings-hint", css)
        self.assertIn("padding-left: 2px !important", css)
        self.assertIn(".memory-dashboard ul", css)
        self.assertIn("padding-left: 1.15em !important", css)
        self.assertIn("overflow: visible !important", css)

    def test_module_buttons_explain_user_roles(self):
        import web_app

        self.assertIn("被教练\nAI 为你做教练", web_app._module_button_text("coach", "zh", "coach"))
        self.assertIn("练习做教练\nAI 扮演来访者", web_app._module_button_text("coachee", "zh", "coach"))
        self.assertIn("Be coached\nby the AI", web_app._module_button_text("coach", "en", "coach"))
        self.assertIn("Practise coaching\nwith an AI client", web_app._module_button_text("coachee", "en", "coach"))

    def test_transformational_studio_contract(self):
        root = Path(__file__).resolve().parent
        source = (root / "web_app.py").read_text(encoding="utf-8")
        import web_app

        header_html = web_app._header_markdown({"agent": web_app._new_session()["agent"], "module": "coach"})
        mode_html = web_app._mode_context_html({"agent": web_app._new_session()["agent"], "module": "coach"})

        self.assertIn("studio-header", header_html)
        self.assertIn('src="/icons/studio-icon-192.png"', header_html)
        self.assertIn('href="/account"', header_html)
        self.assertIn('href="/help"', header_html)
        self.assertNotIn("base64", header_html)
        self.assertIn("教练练习室", header_html)
        self.assertNotIn("transformation-hero", header_html)
        self.assertIn("mode-context-card", mode_html)
        self.assertIn("真实话题", mode_html)
        self.assertLess(source.index('elem_classes="module-card-btn"'), source.index('elem_classes="mode-context-md"'))
        self.assertIn("custom-mic-btn", source)
        self.assertIn("mic-glyph", source)
        self.assertIn("M12 15a3 3 0 0 0 3-3V8", source)
        import re
        visible_header_html = re.sub(r'src="[^"]+"', 'src="[icon]"', header_html)

        for customer_hidden_text in (
            "Recommended Redesign Direction",
            "design principle",
            "设计原则",
            "LIFE-CHANGING PATH",
            "桌面端增加",
            "45+",
            "75K",
            "179",
            "ICF",
        ):
            self.assertNotIn(customer_hidden_text, visible_header_html)
            self.assertNotIn(customer_hidden_text, mode_html)

    def test_mobile_contract_keeps_same_top_elements_as_desktop(self):
        from web_app import css

        self.assertIn("@media (max-width: 768px)", css)
        self.assertIn(".mode-context-md", css)
        self.assertIn(".mode-context-card", css)
        self.assertIn(".intro-md {\n    display: block !important", css)
        self.assertNotIn(".intro-md,\n    .intro-md .transformation-hero,\n    .transformation-hero {\n        display: none !important", css)
        self.assertIn("-webkit-text-fill-color: #ffffff !important", css)
        self.assertIn("grid-template-rows: auto auto !important", css)

    def test_gradio_never_puts_its_own_server_in_front_of_the_account_pages(self):
        import gradio as gr
        import web_app

        with patch.object(web_app.gr, "mount_gradio_app", wraps=gr.mount_gradio_app) as mount:
            web_app.create_app(store=db.Store("sqlite://"), env={"STUDIO_SECRET_KEY": "x" * 64, "GRADIO_SSR_MODE": "true"})

        self.assertIs(mount.call_args.kwargs["ssr_mode"], False)

    def test_hugging_face_space_badge_is_hidden(self):
        from web_assets import head

        self.assertIn("#huggingface-space-header { display: none !important; }", head)

    def test_compact_phone_layout_uses_selectors_gradio_can_match(self):
        from web_app import css

        block = css[css.index("/* Compact phone layout"):]
        # Gradio prefixes every selector with its container, so a selector starting at body never matches.
        self.assertNotIn("body main.contain", block)
        self.assertIn("@media (max-width: 767px)", block)
        self.assertIn('grid-template-areas: "input actions" "steps steps"', block)
        self.assertIn("#app-shell #action-panel {\n        display: contents", block)
        self.assertIn("font-size: 16px !important", block)  # smaller text makes iPhones zoom on focus

    def test_mode_context_note_wraps_instead_of_single_line_ellipsis(self):
        from web_app import UI, css

        self.assertLessEqual(len(UI["en"]["coachee_module_note"]), 58)
        note_block = css[css.index(".mode-context-card p {"): css.index("#settings-sheet", css.index(".mode-context-card p {"))]
        self.assertIn("white-space: normal", note_block)
        self.assertIn("-webkit-line-clamp: 2", note_block)
        self.assertNotIn("text-overflow: ellipsis", note_block)

    def test_row_level_surfaces_share_one_alignment_contract(self):
        from web_app import css

        contract = css[css.index("/* Row alignment contract */"):]
        for selector in (
            ".intro-md",
            "#topbar.module-tabs",
            ".mode-context-md",
            "#settings-sheet",
            ".tracker-shell",
            "#chat-stage",
            "#composer-shell",
        ):
            self.assertIn(selector, contract)
        self.assertIn("width: 100% !important", contract)
        self.assertIn("max-width: none !important", contract)
        self.assertIn("align-self: stretch !important", contract)

    def test_home_screen_icons_are_declared(self):
        import web_app

        root = Path(__file__).parent
        icon_paths = {
            root / "assets" / "icons" / "studio-icon-source.png": 1024,
            root / "assets" / "icons" / "studio-icon.svg": None,
            root / "assets" / "icons" / "studio-icon-180.png": 180,
            root / "assets" / "icons" / "studio-icon-192.png": 192,
            root / "assets" / "icons" / "studio-icon-512.png": 512,
            root / "site.webmanifest": None,
        }
        for path in icon_paths:
            self.assertTrue(path.exists(), path)
        for path, expected_size in icon_paths.items():
            if expected_size is None:
                continue
            with path.open("rb") as image_file:
                self.assertEqual(image_file.read(8), b"\x89PNG\r\n\x1a\n")
                self.assertEqual(int.from_bytes(image_file.read(4), "big"), 13)
                self.assertEqual(image_file.read(4), b"IHDR")
                self.assertEqual(int.from_bytes(image_file.read(4), "big"), expected_size)
                self.assertEqual(int.from_bytes(image_file.read(4), "big"), expected_size)

        self.assertIn('rel="apple-touch-icon"', web_app.head)
        self.assertIn('rel="manifest"', web_app.head)
        self.assertIn('rel="icon"', web_app.head)

    def test_respond_empty_message_returns_all_outputs(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "zh")

        result = list(web_app.respond("", [], session, "coach", "模板", "中文", request))[-1]

        self.assertEqual(web_app.RESPOND_OUTPUT_COUNT, len(result))
    def test_blocked_next_stage_returns_all_outputs(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coachee", "template", "zh")

        result = web_app.next_stage([], session, "coachee", "模板", "中文", request)

        self.assertEqual(web_app.NEXT_STAGE_OUTPUT_COUNT, len(result))
    def test_coachee_manual_advance_to_closing_ends_session_and_disables_input(self):
        from coaching_core import CoachingSubPhase

        web_app, store, user, request = _signed_in()
        session = web_app._open_session(user, "coachee", "template", "en")
        agent = session["agent"]
        agent.current_state = CoachingState.VALUE
        agent.current_sub_phase = CoachingSubPhase.BRIDGE
        agent.metrics.stage_questions[CoachingState.VALUE] = 1

        result = web_app.next_stage([], session, "coachee", "Template", "English", request)

        self.assertEqual(web_app.NEXT_STAGE_OUTPUT_COUNT, len(result))
        self.assertTrue(agent.is_session_ended())
        self.assertEqual(agent.current_state, CoachingState.CLOSING)
        self.assertEqual(result[0]["interactive"], False)
        self.assertEqual(store.get_session(session["id"])["status"], "completed")
    def test_browser_auto_open_can_be_disabled_for_screenshot_runs(self):
        from web_app import _launch_inbrowser

        self.assertFalse(_launch_inbrowser({"STUDIO_INBROWSER": "0"}))
        self.assertFalse(_launch_inbrowser({"STUDIO_INBROWSER": "false"}))
        self.assertFalse(_launch_inbrowser({"CODEX_SANDBOX": "seatbelt"}))
        self.assertFalse(_launch_inbrowser({"CODEX_CI": "1"}))
        self.assertTrue(_launch_inbrowser({"CODEX_SANDBOX": "seatbelt", "STUDIO_INBROWSER": "1"}))
        self.assertTrue(_launch_inbrowser({"STUDIO_INBROWSER": "1"}))
        self.assertFalse(_launch_inbrowser({}))


class TestManualUiProbe(unittest.TestCase):
    def test_mobile_capture_uses_mobile_emulation_path(self):
        import manual_ui_probe

        output = Path("/private/tmp/mobile.png")
        with patch.object(manual_ui_probe, "_capture_mobile") as mobile_capture:
            with patch.object(manual_ui_probe, "_capture_desktop") as desktop_capture:
                manual_ui_probe.capture("http://127.0.0.1:8787", output, 390, 844, mobile=True)

        mobile_capture.assert_called_once_with("http://127.0.0.1:8787", output, 390, 844)
        desktop_capture.assert_not_called()

    def test_readiness_probe_checks_key_controls_and_processing_state(self):
        import manual_ui_probe

        self.assertIn("#chat-input-msg textarea", manual_ui_probe.READY_JS)
        self.assertIn("#custom-mic-btn", manual_ui_probe.READY_JS)
        self.assertIn("processing", manual_ui_probe.READY_JS)
        self.assertIn("row alignment", manual_ui_probe.READY_JS)
        self.assertIn(".intro-md", manual_ui_probe.READY_JS)
        self.assertIn(".tracker-shell", manual_ui_probe.READY_JS)
        self.assertIn("clipped text", manual_ui_probe.READY_JS)
        self.assertIn("outer-page scrolling", manual_ui_probe.READY_JS)
        self.assertIn("module card balance", manual_ui_probe.READY_JS)
        self.assertIn("scrollHeight", manual_ui_probe.READY_JS)
        self.assertIn(".module-card-btn", manual_ui_probe.READY_JS)


class TestStaticModuleBoundaries(unittest.TestCase):
    def test_web_static_assets_are_importable_without_building_demo(self):
        import web_assets

        self.assertIn("zh", web_assets.UI)
        self.assertIn("css", web_assets.__all__)
        self.assertIn("@media (max-width: 768px)", web_assets.css)
        self.assertIn("SpeechSynthesisUtterance", web_assets.tts_js)

    def test_agent_static_data_modules_are_importable(self):
        import coach_data
        import coachee_data

        self.assertIn("en", coach_data.OPENING_QUESTIONS)
        self.assertGreaterEqual(len(coachee_data.SCENARIOS), 1)


class TestWebAppServerConfig(unittest.TestCase):
    def test_ai_mode_is_default_without_client_key(self):
        import web_app

        self.assertEqual(web_app.default_mode, "llm")

    def test_server_key_comes_from_environment_only(self):
        import web_app

        with patch.object(web_app, "_load_dotenv", return_value=None):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}, clear=True):
                self.assertEqual(web_app.get_server_api_key(), "server-key")

            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(web_app.get_server_api_key(), "")

    def test_no_hardcoded_api_key_or_api_textbox_remains(self):
        root = Path(__file__).parent
        secret_prefixes = ["sk" + "-", "sk" + "-or" + "-"]

        for path in root.glob("*.py"):
            if path.name == "tests.py":
                continue
            text = path.read_text(encoding="utf-8")
            for prefix in secret_prefixes:
                self.assertNotIn(prefix, text, path.name)

        web_source = (root / "web_app.py").read_text(encoding="utf-8")
        self.assertNotIn("api_input = gr.Textbox", web_source)

    def test_missing_server_key_returns_configuration_message(self):
        import web_app

        with patch.object(web_app, "_load_dotenv", return_value=None):
            with patch.dict(os.environ, {}, clear=True):
                session = web_app._new_session(module="coach", mode="llm", language="en")
                prompt = web_app._append_opening_prompt(session["agent"])

        self.assertIn("server", prompt.lower())
        self.assertIn("OPENAI_API_KEY", prompt)
        self.assertEqual(session["agent"].mode, "llm")

    def test_ai_opening_uses_llm_when_server_key_exists(self):
        import web_app

        session = web_app._new_session(module="coach", mode="llm", language="en")
        agent = session["agent"]

        with patch.object(web_app, "_load_dotenv", return_value=None):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}, clear=True):
                with patch.object(agent, "_get_llm_opening_response", return_value="LLM opening") as opening:
                    prompt = web_app._append_opening_prompt(agent)

        opening.assert_called_once_with("server-key")
        self.assertEqual(prompt, "LLM opening")
        self.assertEqual(agent.mode, "llm")
        self.assertEqual(agent.context[-1]["content"], prompt)

    def test_ai_opening_failure_shows_a_plain_notice_and_stores_nothing(self):
        # No canned opening when the AI can't answer (e.g. the account is out of credit). The member sees why, can
        # try again with New Session, and the failed try doesn't count against today's allowance.
        web_app, store, user, _ = _signed_in()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}), \
                patch.object(CoachAgent, "_get_llm_opening_response",
                             side_effect=ValueError("Model returned no text content.")), \
                patch.object(web_app.logger, "exception"):
            session = web_app._open_session(user, "coach", "llm", "zh")

        self.assertEqual(session["unavailable"], web_app.UI["zh"]["ai_unavailable"])
        self.assertEqual(session["agent"].context, [{"role": "coach", "content": web_app.UI["zh"]["ai_unavailable"]}])
        self.assertNotIn("id", session)
        self.assertEqual(store.list_sessions(user["id"]), [])
        self.assertFalse(web_app._session_start_outputs(session)["msg"]["interactive"])

    def test_an_empty_ai_opening_is_tried_again_then_reported(self):
        # Seen with a fake model: an English opening in a Chinese session was cleaned to nothing, leaving a blank bubble.
        web_app, store, user, _ = _signed_in()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}), \
                patch("coach_agent._build_client", return_value=_fake_llm_client(["Hello there.", "今天想聊点什么？"], [])):
            session = web_app._open_session(user, "coach", "llm", "zh")
        self.assertEqual(session["agent"].context[-1]["content"], "今天想聊点什么？")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}), \
                patch("coach_agent._build_client", return_value=_fake_llm_client(["Hello.", "Hi again."], [])), \
                patch.object(web_app.logger, "exception"):
            session = web_app._open_session(user, "coach", "llm", "zh")
        self.assertEqual(session["unavailable"], web_app.UI["zh"]["ai_unavailable"])

    def test_practice_does_not_open_when_the_ai_service_is_down(self):
        # An unreadable practice case falls back to a built-in one, but a service that refuses every request (no credit,
        # wrong key) must not open a practice that can't continue.
        import httpx
        import openai

        web_app, store, user, _ = _signed_in()
        refused = openai.APIStatusError("Insufficient credits", response=httpx.Response(
            402, request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")), body=None)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}), \
                patch("coachee_agent._json_completion", side_effect=refused), patch.object(web_app.logger, "exception"):
            session = web_app._open_session(user, "coachee", "llm", "en")

        self.assertEqual(session["unavailable"], web_app.UI["en"]["ai_unavailable"])
        self.assertEqual(store.list_sessions(user["id"]), [])

    def test_one_page_ui_contract_is_present(self):
        root = Path(__file__).parent
        import web_app

        self.assertTrue((root / "DESIGN.md").exists())
        self.assertIn(".module-tabs", web_app.css)
        self.assertIn("height: 100dvh", web_app.css)
        self.assertIn("overflow: hidden", web_app.css)

class TestCoacheeAgent(unittest.TestCase):
    def setUp(self):
        self.agent = CoacheeAgent(mode="template", language="en")

    def test_opening_prompt_comes_from_ai_coachee(self):
        opening = self.agent.get_stage_prompt()
        self.assertTrue(opening)
        self.assertIn("I ", opening)

    def test_llm_scenario_prompt_includes_session_variation(self):
        captured_messages = []
        payload = (
            '{"intro":"I am stuck choosing my next step.",'
            '"contract":{"goal":["I want clarity.","I need a next step."],"importance":["It matters now.","I feel blocked."],"success":["I would know my next action.","I would feel clearer."]},'
            '"experience":{"reality":["It has been messy.","I keep delaying."],"obstacle":["I am overthinking.","I avoid deciding."],"strength":["I can reflect.","I have support."],"past_success":["I handled change before.","I made a hard choice before."],"scale":["About a four.","Maybe a five."]},'
            '"action":{"possibility":["I could ask for input.","I could test one option."],"stretch":["I could decide this week.","I could stop waiting."],"support":["A peer could help.","My manager could advise."]},'
            '"value":{"commitment":["I will list options.","I will choose one test."],"timeline":["Tomorrow.","By Friday."],"risk":["I may hesitate.","I may seek too much certainty."],"accountability":["I will tell a peer.","I will calendar it."]},'
            '"closing":{"reflection":["I feel clearer.","I know the next step."]}}'
        )

        class FakeCompletions:
            def create(self, **kwargs):
                captured_messages.extend(kwargs["messages"])
                message = type("Message", (), {"content": payload})()
                choice = type("Choice", (), {"message": message})()
                return type("Response", (), {"choices": [choice]})()

        class FakeClient:
            chat = type("Chat", (), {"completions": FakeCompletions()})()

        agent = CoacheeAgent(mode="llm", language="en")
        with patch("coachee_agent._build_client", return_value=FakeClient()):
            agent._ensure_llm_scenario("server-key")

        prompt = captured_messages[0]["content"]
        self.assertIn("Session variation seed:", prompt)
        self.assertIn(agent.scenario_variation_seed, prompt)
        self.assertIn("Do not default to generic career or management dilemmas", prompt)

    def test_training_flow_reaches_scored_closing_review(self):
        opening = self.agent.get_stage_prompt()
        self.agent.context.append({"role": self.agent.assistant_role, "content": opening})

        prompts = [
            "What would you like to achieve by the end of this coaching conversation?",
            "Why is that goal especially important right now?",
            "How would you know this session has been successful for you?",
            "What is happening in your current situation?",
            "What seems to be getting in the way?",
            "What strengths or resources do you already have here?",
            "What different options could you try?",
            "If you were being bold, what else could you do?",
            "What support could help you move this forward?",
            "What specific action will you commit to?",
            "When exactly will you take that first step?",
            "What might get in the way, and how will you stay accountable?",
            "What are you taking away from this coaching conversation overall?",
            "As we close, what feels most valuable from this session?",
            "How would you summarize the value of this coaching process for yourself?",
        ]

        final_response = ""
        for prompt in prompts:
            final_response = self.agent.generate_response(prompt)

        self.assertTrue(self.agent.is_session_ended())
        self.assertEqual(self.agent.current_state, CoachingState.CLOSING)
        self.assertIn("Session Result:", final_response)
        self.assertIn("Score:", final_response)
        self.assertIn("What worked:", final_response)
        self.assertIn("What to improve:", final_response)

    def test_skip_ahead_moves_one_stage_per_press(self):
        # It used to take two presses: the first changed nothing the coach could see.
        opening = self.agent.get_stage_prompt()
        self.agent.context.append({"role": self.agent.assistant_role, "content": opening})

        self.assertTrue(self.agent.force_next_state())
        self.assertEqual(self.agent.current_state, CoachingState.EXPERIENCE)

    def test_closing_is_practised_before_the_review(self):
        agent = CoacheeAgent(mode="llm", language="en")
        agent._llm_scenario_ready = True
        agent.current_state = CoachingState.VALUE
        agent.contract_done = True
        agent.context = [{"role": "coachee", "content": "I'll start on Monday."}]
        agent.metrics.stage_questions[CoachingState.VALUE] = 1
        replies = ["That I can start small.", "Thanks, bye!", "Session Result: ok\nScore: 30/100"]

        with patch("coachee_agent._build_client", return_value=_fake_llm_client(replies, [])), _coach_labels("CLOSING", "END"):
            reply = agent.generate_response("What are you taking away from today?", api_key="server-key")
            self.assertEqual((reply, agent.current_state), ("That I can start small.", CoachingState.CLOSING))
            self.assertFalse(agent.is_session_ended())
            review = agent.generate_response("Thank you, goodbye!", api_key="server-key")

        self.assertTrue(agent.is_session_ended())
        self.assertTrue(review.startswith("Session Result: ok"))

    def test_skip_ahead_from_closing_ends_the_practice(self):
        agent = CoacheeAgent(mode="llm", language="en")
        agent.current_state = CoachingState.VALUE
        self.assertTrue(agent.force_next_state())
        self.assertEqual((agent.current_state, agent.is_session_ended()), (CoachingState.CLOSING, False))
        self.assertTrue(agent.force_next_state())
        self.assertTrue(agent.is_session_ended())
        self.assertFalse(agent.force_next_state())

        self.agent.current_state = CoachingState.VALUE  # template mode has no closing conversation
        self.assertTrue(self.agent.force_next_state())
        self.assertTrue(self.agent.is_session_ended())

    def test_manual_advance_guard_blocks_empty_stage_skips(self):
        self.assertIn("at least one coaching question", self.agent.manual_advance_guard())

    def test_incomplete_review_stays_low_without_real_coaching_evidence(self):
        review = self.agent._build_final_review()
        self.assertIn("Score: 0/100", review)
        self.assertIn("not enough evidence", review.lower())


class TestMemoryPrivacy(unittest.TestCase):
    def test_profile_merge_keeps_newest_items_without_duplicates(self):
        profile = UserProfile(strengths=["Listening", "Clarity"], growth_areas=["Silence"], session_count=2)

        merged = merge_analysis(profile, {"strengths": ["listening", "Curiosity"], "growth_areas": [], "coaching_style": "Warm"})

        self.assertEqual(merged.strengths, ["listening", "Curiosity", "Clarity"])
        self.assertEqual(merged.growth_areas, ["Silence"])
        self.assertEqual(merged.coaching_style_insights, "Warm")
        self.assertEqual(merged.session_count, 3)

    def test_profile_lists_are_capped_for_prompts(self):
        many = [f"item {i}" for i in range(20)]

        merged = merge_analysis(UserProfile(), {"strengths": many, "growth_areas": many})

        self.assertEqual(len(merged.strengths), MAX_PROFILE_ITEMS)
        self.assertEqual(merged.strengths[0], "item 0")
    def test_profiles_are_stored_per_user_and_module(self):
        store = db.Store("sqlite://")
        amy = store.create_user("amy@example.com", "Amy", accounts.hash_password("a-long-password"))
        bo = store.create_user("bo@example.com", "Bo", accounts.hash_password("a-long-password"))

        store.save_profile(amy, "coach", {"strengths": ["Calm"]})

        self.assertEqual(store.get_profile(amy, "coach"), {"strengths": ["Calm"]})
        self.assertIsNone(store.get_profile(amy, "coachee"))
        self.assertIsNone(store.get_profile(bo, "coach"))
    def test_requirements_keep_mvp_dependencies_tight(self):
        root = Path(__file__).parent
        requirements = (root / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("gradio", requirements)
        self.assertIn("openai", requirements)
        self.assertNotIn("requests", requirements)
        self.assertNotIn("cryptography", requirements)


def _fake_llm_client(replies, calls):
    """Stand-in OpenAI client: each create() returns the next reply, streamed in small chunks when stream=True."""

    class FakeStream:
        def __init__(self, text):
            self.text = text

        def __iter__(self):
            for i in range(0, len(self.text), 4):
                delta = type("Delta", (), {"content": self.text[i:i + 4]})()
                yield type("Chunk", (), {"choices": [type("Choice", (), {"delta": delta})()]})()

        def close(self):
            pass

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            text = replies.pop(0)
            if kwargs.get("stream"):
                return FakeStream(text)
            message = type("Message", (), {"content": text, "refusal": None})()
            return type("Response", (), {"choices": [type("Choice", (), {"message": message})()]})()

    return type("FakeClient", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})()


def _coach_labels(*signals):
    """Stand-in for the short request that labels the coach's message in practice mode (it runs alongside the reply)."""
    queue = list(signals)

    def label(agent, api_key, result):
        result["signal"] = queue.pop(0)

    return patch.object(CoacheeAgent, "_label_coach_message", label)


class TestSingleCallStageDecisions(unittest.TestCase):
    def _deepening_coach(self):
        from coaching_core import CoachingSubPhase

        agent = CoachAgent(mode="llm", language="en")
        agent.context = [
            {"role": "coach", "content": "What would you like to focus on?"},
            {"role": "client", "content": "My time management."},
        ]
        agent.current_sub_phase = CoachingSubPhase.DEEPEN
        agent.turns_in_current_stage = 2
        return agent

    def test_split_stage_signal_hides_markers_while_streaming(self):
        from coaching_core import _split_stage_signal

        self.assertEqual(_split_stage_signal("[[NE"), (None, ""))
        self.assertEqual(_split_stage_signal("[[NEXT]] Great"), ("NEXT", "Great"))
        self.assertEqual(_split_stage_signal("Sounds good [[ST"), (None, "Sounds good"))
        self.assertEqual(_split_stage_signal("Plain reply"), (None, "Plain reply"))
        self.assertEqual(_split_stage_signal("[[2]] Great"), ("2", "Great"))
        self.assertEqual(_split_stage_signal("[[ Commitment ]]Great"), ("COMMITMENT", "Great"))

    def test_coach_reply_names_its_stage_and_the_tracker_moves_at_once(self):
        from coaching_core import CoachingSubPhase

        agent = self._deepening_coach()
        calls = []
        client = _fake_llm_client(["[[REALITY]] You have a clear goal. What is happening right now?"], calls)

        with patch("coach_agent._build_client", return_value=client):
            partials = list(agent.stream_response("I want two focused hours a day.", api_key="server-key"))

        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["stream"])
        self.assertIn("The conversation has reached [[GOAL]]", calls[0]["messages"][0]["content"])
        self.assertTrue(all("[[" not in text for text in partials))
        self.assertEqual(partials[-1], "You have a clear goal. What is happening right now?")
        self.assertEqual(agent.current_state, CoachingState.EXPERIENCE)
        self.assertEqual((agent.current_sub_phase, agent.turns_in_current_stage), (CoachingSubPhase.DEEPEN, 0))
        self.assertEqual(agent.context[-1], {"role": "coach", "content": partials[-1], "stage": 2})

    def test_past_replies_reach_the_model_with_their_markers(self):
        # Shown their earlier replies without markers, models stopped writing markers after a few turns.
        agent = self._deepening_coach()
        agent.context[0]["stage"] = 1
        calls = []

        with patch("coach_agent._build_client", return_value=_fake_llm_client(["[[GOAL]] What else?"], calls)):
            agent.generate_response("Mornings.", api_key="server-key")

        sent = [m["content"] for m in calls[0]["messages"][1:]]
        self.assertEqual(sent, ["[[GOAL]] What would you like to focus on?", "My time management.", "Mornings."])
        self.assertEqual(agent.context[0]["content"], "What would you like to focus on?")
        self.assertEqual(agent.context[-1]["stage"], 1)

    def test_coach_stage_follows_the_client_forward_but_never_back(self):
        agent = CoachAgent(mode="llm", language="en")
        agent.context = [{"role": "coach", "content": "What would you like from today?"}]
        replies = ["[[OPTIONS]] You already know mornings work. What could you try first?", "[[GOAL]] What do you want?",
                   "[[CLOSING]] What will you take away from today?", "[[END]] A timer and Monday. Good luck!"]

        with patch("coach_agent._build_client", return_value=_fake_llm_client(replies, [])):
            agent.generate_response("I want to write daily and mornings already work for me.", api_key="server-key")
            self.assertEqual(agent.current_state, CoachingState.ACTION)  # decided on the very first answer
            agent.generate_response("Maybe a timer.", api_key="server-key")
            self.assertEqual(agent.current_state, CoachingState.ACTION)
            agent.generate_response("I'll start tomorrow.", api_key="server-key")
            # Closing is a conversation of its own: the client still answers the closing question.
            self.assertEqual(agent.current_state, CoachingState.CLOSING)
            self.assertFalse(agent.is_session_ended())
            self.assertEqual(agent.skipped_stages, {2, 4})
            agent.generate_response("That small steps work for me.", api_key="server-key")

        self.assertTrue(agent.is_session_ended())
        self.assertEqual(agent.context[-1], {"role": "coach", "content": "A timer and Monday. Good luck!", "stage": "END"})
        restored = CoachAgent.from_dict(json.loads(json.dumps(agent.to_dict())))
        self.assertEqual((restored.is_session_ended(), restored.skipped_stages), (True, {2, 4}))

    def test_a_reply_that_runs_past_its_question_is_cut_there(self):
        # Seen with DeepSeek: a stray word, then the client's next answer, written into the coach's reply.
        agent = self._deepening_coach()
        client = _fake_llm_client(["[[COMMITMENT]] When will you start? সংগ্রহেরTomorrow, after work."], [])

        with patch("coach_agent._build_client", return_value=client):
            partials = list(agent.stream_response("I'll try a timer.", api_key="server-key"))

        self.assertEqual(partials[-1], "When will you start?")
        self.assertTrue(all("Tomorrow" not in text and "সং" not in text for text in partials))
        self.assertEqual(agent.context[-1]["content"], "When will you start?")

    def test_the_model_sees_its_past_replies_without_short_opening_echoes(self):
        # It copies its own earlier replies, so echoes it could see bred an echo at the start of every reply.
        agent = self._deepening_coach()
        agent.context += [{"role": "coach", "content": "Time management. What matters most about it?", "stage": 1},
                          {"role": "client", "content": "Getting evenings back."}]
        calls = []

        with patch("coach_agent._build_client", return_value=_fake_llm_client(["[[GOAL]] What would evenings hold?"], calls)):
            agent.generate_response("Mostly reading.", api_key="server-key")

        sent = calls[0]["messages"]
        self.assertIn({"role": "assistant", "content": "[[GOAL]] What matters most about it?"}, sent)
        self.assertIn("go straight to your question", sent[-1]["content"])  # a note beside the latest message
        self.assertEqual(agent.context[2]["content"], "Time management. What matters most about it?")

    def test_skip_ahead_reaches_closing_before_ending_the_session(self):
        agent = CoachAgent(mode="llm", language="en")
        agent.current_state = CoachingState.VALUE
        agent.context = [{"role": "coach", "content": "When will you start?"}]
        calls = []

        with patch("coach_agent._build_client", return_value=_fake_llm_client(["What are you taking away?", "Goodbye."], calls)):
            self.assertTrue(agent.force_next_state())
            self.assertEqual(agent.get_stage_prompt("server-key"), "What are you taking away?")
            self.assertFalse(agent.is_session_ended())
            self.assertIn("chosen to skip ahead", calls[0]["messages"][0]["content"])
            self.assertTrue(agent.force_next_state())
            self.assertTrue(agent.is_session_ended())
            self.assertFalse(agent.force_next_state())

    def test_template_mode_finishes_a_whole_session(self):
        # It used to stop at the end of the commitment stage: there were no closing questions to hand over to.
        for language in ("en", "zh"):
            agent = CoachAgent(mode="template", language=language)
            agent.context.append({"role": "coach", "content": agent.get_stage_prompt()})
            for turn in range(30):
                reply = agent.generate_response(f"answer {turn}")
                if agent.is_session_ended():
                    break
            self.assertTrue(agent.is_session_ended())
            self.assertNotIn("?", reply)
            self.assertNotIn("？", reply)

    def test_coach_is_nudged_to_move_on_after_a_long_stage(self):
        agent = self._deepening_coach()
        agent.turns_in_current_stage = 4
        calls = []

        with patch("coach_agent._build_client", return_value=_fake_llm_client(["[[GOAL]] What else matters?"], calls)):
            agent.generate_response("It matters a lot.", api_key="server-key")

        self.assertIn("This stage has already taken 5 exchanges. Unless the client is in the middle of something important, "
                      "now move on with [[REALITY]]", calls[0]["messages"][0]["content"])

    def test_coach_reply_can_end_the_session(self):
        agent = self._deepening_coach()
        calls = []
        client = _fake_llm_client(["[[END]] Thank you for the work you did today."], calls)

        with patch("coach_agent._build_client", return_value=client):
            reply = agent.generate_response("That's all I need, thanks!", api_key="server-key")

        self.assertEqual(reply, "Thank you for the work you did today.")
        self.assertTrue(agent.is_session_ended())
        self.assertEqual(len(calls), 1)

    def test_coach_reply_without_marker_stays_in_stage(self):
        from coaching_core import CoachingSubPhase

        agent = self._deepening_coach()
        calls = []
        client = _fake_llm_client(["What else matters about that?"], calls)

        with patch("coach_agent._build_client", return_value=client):
            reply = agent.generate_response("It matters a lot.", api_key="server-key")

        self.assertEqual(reply, "What else matters about that?")
        self.assertEqual(agent.current_state, CoachingState.CONTRACT)
        self.assertEqual(agent.current_sub_phase, CoachingSubPhase.DEEPEN)

    def test_coach_reply_without_marker_moves_on_once_nudged(self):
        agent = self._deepening_coach()
        agent.turns_in_current_stage = 4
        calls = []
        client = _fake_llm_client(["Let's look at where things stand now."], calls)

        with patch("coach_agent._build_client", return_value=client):
            agent.generate_response("Yes, that's the goal.", api_key="server-key")

        self.assertEqual(agent.current_state, CoachingState.EXPERIENCE)

    def test_reply_in_the_wrong_language_is_tried_once_more(self):
        agent = CoachAgent(mode="llm", language="zh")
        agent.context = [{"role": "coach", "content": "你今天想聚焦什么？"}]
        calls = []
        client = _fake_llm_client(["What would help most this week?", "[[GOAL]] 这周什么最能帮到你？"], calls)

        with patch("coach_agent._build_client", return_value=client):
            partials = list(agent.stream_response("我想更好地管理时间。", api_key="server-key"))

        self.assertEqual(partials[-1], "这周什么最能帮到你？")
        self.assertEqual(len(calls), 2)
        self.assertEqual(agent.context[-1]["content"], partials[-1])

    def test_practice_turn_the_ai_cannot_answer_is_undone(self):
        agent = CoacheeAgent(mode="llm", language="en")
        agent._llm_scenario_ready = True
        agent.context = [{"role": "coachee", "content": agent.scenario.intro["en"]}]
        empty = ValueError("Model returned no text content.")

        with patch.object(agent, "_get_llm_response", side_effect=[empty, empty]), _coach_labels("REALITY"):
            with self.assertRaises(ValueError):
                agent.generate_response("What have you tried?", api_key="server-key")

        self.assertEqual(len(agent.context), 1)  # resending won't count the question twice
        self.assertEqual(agent.metrics.total_questions, 0)
        self.assertEqual(agent.current_state, CoachingState.CONTRACT)

    def test_coach_goodbye_brings_the_review_without_showing_a_reply(self):
        agent = CoacheeAgent(mode="llm", language="en")
        agent._llm_scenario_ready = True
        agent.context = [{"role": "coachee", "content": agent.scenario.intro["en"]}]
        calls = []
        client = _fake_llm_client(["Thanks, I feel ready.", "Session Result: Solid start.\nScore: 7/100"], calls)

        with patch("coachee_agent._build_client", return_value=client), _coach_labels("END"):
            partials = list(agent.stream_response("Goodbye and good luck!", api_key="server-key"))

        self.assertEqual(partials, ["Session Result: Solid start.\nScore: 7/100"])
        self.assertTrue(agent.is_session_ended())
        self.assertTrue(calls[0]["stream"])
        self.assertFalse(calls[1].get("stream", False))

    def test_coach_message_is_labelled_by_a_short_request_of_its_own(self):
        # Labelling the coach while playing the client, the model mostly repeated its own previous label.
        agent = CoacheeAgent(mode="llm", language="en")
        agent.context = [{"role": "coachee", "content": "I keep putting it off."},
                         {"role": "coach", "content": "What have you tried so far?"}]
        calls, result = [], {}

        with patch("coachee_agent._build_client", return_value=_fake_llm_client(["[[REALITY]]"], calls)):
            agent._label_coach_message("server-key", result)

        self.assertEqual(result, {"signal": "REALITY"})
        self.assertLessEqual(calls[0]["max_tokens"], 10)
        self.assertIn("Coach: What have you tried so far?", calls[0]["messages"][1]["content"])
        self.assertIn("The conversation has reached [[GOAL]]", calls[0]["messages"][0]["content"])

    def test_coachee_follows_the_stage_the_coach_is_asking_about(self):
        agent = CoacheeAgent(mode="llm", language="en")
        agent._llm_scenario_ready = True
        agent.contract_done = True  # after contracting the tracker follows the coach (see TestOwnPracticeTopic)
        agent.context = [{"role": "coachee", "content": agent.scenario.intro["en"]}]
        calls = []
        client = _fake_llm_client(["I could ask my manager for one quiet afternoon."], calls)

        with patch("coachee_agent._build_client", return_value=client), _coach_labels("OPTIONS"):
            reply = agent.generate_response("What options do you see?", api_key="server-key")

        self.assertEqual(reply, "I could ask my manager for one quiet afternoon.")
        self.assertEqual(agent.current_state, CoachingState.ACTION)
        self.assertEqual(agent.skipped_stages, {2})
        self.assertEqual(agent.metrics.stage_questions[CoachingState.ACTION], 1)
        self.assertEqual(agent.metrics.stage_questions[CoachingState.CONTRACT], 0)
        self.assertIsNone(agent.manual_advance_guard())
        prompt = calls[0]["messages"][0]["content"]
        # The whole case is there, so the answer can come from the stage the coach asked about.
        self.assertIn("Stage 3:", prompt)
        self.assertIn(agent.scenario.action["possibility"]["en"][0], prompt)
        self.assertNotIn("[[", prompt)  # the client's reply carries no stage marker any more

    def test_history_translation_is_one_call(self):
        agent = CoachAgent(mode="llm", language="en")
        agent.context = [
            {"role": "coach", "content": "What brings you here?"},
            {"role": "client", "content": "Stress."},
            {"role": "coach", "content": "What would help most?"},
        ]
        calls = []
        client = _fake_llm_client(['["是什么让你来到这里？", "什么最有帮助？"]'], calls)

        with patch("coaching_core._build_client", return_value=client):
            agent.translate_history("zh", api_key="server-key")

        self.assertEqual(len(calls), 1)
        self.assertEqual(agent.context[0]["content"], "是什么让你来到这里？")
        self.assertEqual(agent.context[2]["content"], "什么最有帮助？")
        self.assertEqual(agent.language, "zh")

    def test_llm_client_is_shared_and_fails_fast(self):
        import coaching_core

        first = coaching_core._build_client("server-key", "http://127.0.0.1:9/v1")
        second = coaching_core._build_client("server-key", "http://127.0.0.1:9/v1")

        self.assertIs(first.client, second.client)
        self.assertEqual(first.client.timeout, coaching_core.LLM_TIMEOUT_SECONDS)
        self.assertEqual(first.client.max_retries, coaching_core.LLM_MAX_RETRIES)


def _conversation(agent, sent: int) -> list[dict]:
    """A conversation in which the person has already sent this many messages, each answered."""
    return [message for i in range(sent) for message in ({"role": agent.user_role, "content": f"Message {i}"},
                                                           {"role": agent.assistant_role, "content": "Mm."})]


def _signed_in(role="user", **fields):
    """A fresh in-memory store with one signed-in person; returns (web_app, store, user, gr.Request)."""
    import gradio as gr
    import quota
    import web_app

    store = db.Store("sqlite://")
    web_app.set_store(store)
    web_app._message_limiter = quota.MessageRateLimiter()
    user_id = store.create_user(f"{role}@example.com", role.title(), accounts.hash_password("a-long-password"), role=role)
    if fields:
        store.update_user(user_id, **fields)
    return web_app, store, store.get_user(user_id), gr.Request(username=str(user_id))


class TestHostedAccessAndLimits(unittest.TestCase):
    def test_public_launch_without_secret_key_refuses_to_start(self):
        import web_app

        with patch.object(web_app.gr, "mount_gradio_app") as mount:
            with self.assertRaises(SystemExit):
                web_app.create_app(store=db.Store("sqlite://"), env={"SPACE_ID": "fanyang0610/Coaching-Practice-Studio"})
            mount.assert_not_called()
            web_app.create_app(store=db.Store("sqlite://"), env={"SPACE_ID": "x", "STUDIO_SECRET_KEY": "k" * 64})

        kwargs = mount.call_args.kwargs
        self.assertIsNotNone(kwargs["auth_dependency"])
        self.assertNotIn("api", kwargs["footer_links"])
        self.assertTrue(web_app._is_public({"GRADIO_SERVER_NAME": "0.0.0.0"}))
        self.assertFalse(web_app._is_public({}))

    def test_server_port_follows_host_conventions(self):
        import web_app

        self.assertEqual(web_app._server_port({"GRADIO_SERVER_PORT": "8800", "PORT": "9000"}), 8800)
        self.assertEqual(web_app._server_port({"PORT": "9000"}), 9000)

    def test_error_reports_never_include_transcripts(self):
        import sys
        import types
        import web_app

        fake_sentry = types.SimpleNamespace(init=lambda **kwargs: calls.append(kwargs))
        calls = []
        with patch.dict(sys.modules, {"sentry_sdk": fake_sentry}):
            web_app._init_error_reporting({})
            web_app._init_error_reporting({"SENTRY_DSN": "https://key@example.ingest.sentry.io/1"})

        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0]["send_default_pii"])
        self.assertFalse(calls[0]["include_local_variables"])
        self.assertEqual(calls[0]["max_request_body_size"], "never")

    def test_first_admin_comes_from_environment_once(self):
        import web_app

        store = db.Store("sqlite://")
        env = {"SPACE_ID": "x", "STUDIO_SECRET_KEY": "k" * 64, "STUDIO_ADMIN_EMAIL": "Owner@Example.com",
               "STUDIO_ADMIN_PASSWORD": "a-long-password"}
        with patch.object(web_app.gr, "mount_gradio_app"):
            web_app.create_app(store=store, env=env)
            web_app.create_app(store=store, env=env)

        owner = store.get_user_by_email("owner@example.com")
        self.assertEqual(owner["role"], "admin")
        self.assertEqual(len(store.list_users()), 1)
        self.assertTrue(accounts.verify_password("a-long-password", owner["password_hash"]))

    def test_model_events_share_one_concurrency_pool_and_stay_off_the_api_page(self):
        import web_app

        backend_fns = [fn for fn in web_app.demo.fns.values() if fn.fn is not None]
        model_fns = [fn for fn in backend_fns if fn.name not in ("record_feedback", "rate_session")]

        self.assertGreaterEqual(len(model_fns), 8)
        for fn in model_fns:
            self.assertEqual(fn.concurrency_id, "llm", fn.name)
            self.assertEqual(fn.concurrency_limit, web_app.LLM_CONCURRENCY, fn.name)
        for fn in backend_fns:
            self.assertEqual(fn.api_visibility, "private", fn.name)

    def test_handlers_require_a_signed_in_user(self):
        import gradio as gr

        web_app, _, _, _ = _signed_in()
        with self.assertRaises(gr.Error):
            list(web_app.respond("hello", [], None, "coach", "Template", "English", gr.Request(username=None)))

    def test_respond_streams_partial_transcripts(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        opening = web_app._chat_history_from_context(session["agent"])

        outputs = list(web_app.respond("I want more focus.", opening, session, "coach", "Template", "English", request))

        self.assertGreaterEqual(len(outputs), 2)
        self.assertTrue(all(len(output) == web_app.RESPOND_OUTPUT_COUNT for output in outputs))
        self.assertEqual(outputs[0][1][-1], {"role": "user", "content": "I want more focus."})
        self.assertEqual(outputs[-1][1][-1]["role"], "assistant")

    def test_respond_rejects_overlong_messages_before_calling_the_agent(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        with patch.object(web_app.gr, "Warning") as warning:
            outputs = list(web_app.respond("x" * (web_app.MAX_MESSAGE_CHARS + 1), [], session, "coach", "Template", "English", request))

        self.assertEqual(len(outputs), 1)
        self.assertIn(str(web_app.MAX_MESSAGE_CHARS), warning.call_args.args[0])
        self.assertEqual(len(session["agent"].context), 1)

    def test_the_last_messages_of_a_conversation_are_counted_down(self):
        # Fan: say what the limit is and how far they have come, not just that it is near.
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        agent = session["agent"]
        agent.context = _conversation(agent, web_app.MAX_USER_TURNS_PER_SESSION - 7)
        with patch.object(web_app.gr, "Warning") as warning:
            list(web_app.respond("One more thing.", [], session, "coach", "Template", "English", request))
        self.assertFalse(warning.called)  # 6 left

        with patch.object(web_app.gr, "Warning") as warning:
            list(web_app.respond("And another.", [], session, "coach", "Template", "English", request))
        self.assertEqual(warning.call_args.args[0], "Each conversation allows up to 100 messages. You've sent 95, so 5 "
                                                    "left. Time to start wrapping up.")

    def test_the_last_message_ends_a_practice_with_its_review(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coachee", "template", "zh")
        agent = session["agent"]
        agent.context = _conversation(agent, web_app.MAX_USER_TURNS_PER_SESSION - 1)
        with patch.object(web_app.gr, "Info") as info:
            outputs = list(web_app.respond("你今天最想谈什么？", [], session, "coachee", "Template", "中文", request))

        self.assertTrue(agent.is_session_ended())
        self.assertIn("这次练习已经发满 100 条消息的上限，到此结束。下面是你的得分和反馈。", [c.args[0] for c in info.call_args_list])
        self.assertIn("最后得分", agent.context[-1]["content"])
        self.assertFalse(outputs[-1][0]["interactive"])

    def test_the_last_message_ends_ai_coach_with_a_goodbye(self):
        import coach_agent

        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        agent = session["agent"]
        agent.context = _conversation(agent, web_app.MAX_USER_TURNS_PER_SESSION - 1)
        outputs = list(web_app.respond("That helps.", [], session, "coach", "Template", "English", request))

        self.assertTrue(agent.is_session_ended())
        self.assertEqual(agent.context[-1]["content"], coach_agent.LIMIT_GOODBYE["en"])
        self.assertFalse(outputs[-1][0]["interactive"])

    def test_a_conversation_already_at_the_limit_ends_with_its_review_instead_of_locking(self):
        # Xiaofang's practice under the old 40-message cap: the box locked at stage 3, Skip Ahead stopped at stage 4 (it
        # wants a question there first), and she had no way to finish and get her review.
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coachee", "template", "zh")
        agent = session["agent"]
        agent.context = _conversation(agent, web_app.MAX_USER_TURNS_PER_SESSION)
        list(web_app.respond("还有一个问题？", [], session, "coachee", "Template", "中文", request))

        self.assertTrue(agent.is_session_ended())
        self.assertEqual(web_app._user_turns(agent), web_app.MAX_USER_TURNS_PER_SESSION)
        self.assertIn("最后得分", agent.context[-1]["content"])

    def test_respond_refuses_overlapping_sends_on_one_conversation(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        lock = web_app._agent_lock(session["agent"])
        lock.acquire()
        try:
            with patch.object(web_app.gr, "Warning") as warning:
                list(web_app.respond("hello", [], session, "coach", "Template", "English", request))
        finally:
            lock.release()

        self.assertEqual(warning.call_args.args[0], web_app.UI["en"]["busy_warning"])
        self.assertEqual(len(session["agent"].context), 1)

    def test_respond_limits_messages_per_minute(self):
        import quota

        web_app, _, user, request = _signed_in()
        web_app._message_limiter = quota.MessageRateLimiter(limit=1)
        session = web_app._open_session(user, "coach", "template", "en")
        list(web_app.respond("first", [], session, "coach", "Template", "English", request))
        with patch.object(web_app.gr, "Warning") as warning:
            list(web_app.respond("second", [], session, "coach", "Template", "English", request))

        self.assertEqual(warning.call_args.args[0], web_app.UI["en"]["rate_limited"])

    def test_model_errors_are_logged_not_shown_to_users(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        session["agent"].mode = "llm"
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}, clear=True):
            with patch.object(session["agent"], "_get_llm_response", side_effect=RuntimeError("upstream 502 from https://internal")):
                with patch.object(web_app.gr, "Warning") as warning, patch.object(web_app.logger, "exception"):
                    outputs = list(web_app.respond("hello", [], session, "coach", "AI", "English", request))

        self.assertEqual(warning.call_args.args[0], web_app.UI["en"]["ai_reply_error"])
        self.assertEqual(outputs[-1][0]["value"], "hello")
        self.assertEqual(outputs[-1][1], [])


class TestStoredSessions(unittest.TestCase):
    def test_new_ai_coach_button_starts_fresh_and_keeps_that_boundary_after_refresh(self):
        import datetime as dt

        web_app, store, user, request = _signed_in()
        original = web_app._open_session(user, "coach", "template", "en")
        agent = original["agent"]
        agent.context.append({"role": "client", "content": "OLD_TRANSCRIPT: a ceramics course."})
        agent.session_complete = True
        web_app._save(original)
        card = {"goal": "OLD_CARD: learn pottery", "next_step": "Book the studio"}
        store.save_session_result(original["id"], user["id"], "coach", card=card)
        with store.engine.begin() as conn:
            conn.execute(db.session_results.update().values(created_at=db.utcnow() - dt.timedelta(days=1)))
        profile = UserProfile(coaching_style_insights="OLD_STYLE: workshop confidence",
                              strengths=["OLD_STRENGTH: patience at the wheel"],
                              growth_areas=["OLD_GROWTH: sharing my ceramics"], last_updated="yesterday")
        store.save_profile(user["id"], "coach", profile.to_dict())
        calls = []
        fake = _fake_llm_client([
            "What feels worth talking about today? What else?",
            "Where would you like to begin?",
            "Take your time. What would you like to talk through?",
            "[[REALITY]] What has made commuting difficult?",
            "[[REALITY]] What have you already tried?",
            "[[OPTIONS]] What would help with the pottery course now?",
        ], calls)

        with (
            patch.object(web_app, "_safe_key", return_value="server-key"),
            patch("coach_agent._build_client", return_value=fake),
        ):
            session = original
            for opening in ("What feels worth talking about today?", "Where would you like to begin?",
                            "Take your time. What would you like to talk through?"):
                outputs = web_app.reset_session("English", "coach", "AI", session, request)
                session = outputs[-1]
                self.assertEqual(outputs[0], [{"role": "assistant", "content": opening}])
                self.assertEqual(store.latest_active_session(user["id"])["id"], session["id"])
                self.assertEqual(session["agent"].current_state, CoachingState.CONTRACT)

            first_turn = list(web_app.respond("I want to rethink my commute.", outputs[0], session,
                                             "coach", "AI", "English", request))
            session = first_turn[-1][-1]
            reopened = web_app.initial_load(None, "coach", "AI", "English", request)
            self.assertEqual(reopened[0], first_turn[-1][1])
            self.assertEqual(reopened[-1]["id"], session["id"])
            self.assertEqual(reopened[-1]["agent"].current_state, CoachingState.EXPERIENCE)
            session = reopened[-1]
            list(web_app.respond("The trains are crowded.", [], session, "coach", "AI", "English", request))
            list(web_app.respond("Actually, I want to revisit my pottery course.", [], session, "coach", "AI", "English", request))

        for call in calls[:3]:
            self.assertIn("Invite them to choose whatever they would like to talk about", call["messages"][0]["content"])
        self.assertEqual(len({call["messages"][0]["content"] for call in calls[:3]}), 3)
        self.assertTrue(all("OLD_" not in json.dumps(call["messages"]) for call in calls))
        self.assertIn("I want to rethink my commute.", json.dumps(calls[4]["messages"]))
        self.assertIn("Actually, I want to revisit my pottery course.", json.dumps(calls[5]["messages"]))
        self.assertEqual(store.get_session(original["id"])["status"], "completed")
        self.assertEqual(store.session_results(user["id"], "coach")[0]["card"], card)
        self.assertEqual(store.get_profile(user["id"], "coach"), profile.to_dict())
        self.assertEqual(sum(row["status"] == "active" for row in store.list_sessions(user["id"])), 1)

    def test_new_ai_coach_button_preserves_the_current_session_on_failure_and_retries(self):
        import uuid

        web_app, store, user, request = _signed_in()
        fake = _fake_llm_client(["What would you like to discuss?", "[[REALITY]] What matters about that?",
                                 "What would you like to talk through?", "Where would you like to begin?",
                                 "What's on your mind today?"], [])
        with (
            patch.object(web_app, "_safe_key", return_value="server-key"),
            patch("coach_agent._build_client", return_value=fake) as client,
            patch.object(web_app.gr, "Warning") as warning,
            patch.object(web_app.logger, "exception"),
        ):
            current = web_app._open_session(user, "coach", "llm", "en")
            for failure in ("model", "save"):
                before = store.get_session(current["id"])
                if failure == "model":
                    client.side_effect = RuntimeError("simulated outage")
                    outputs = web_app.reset_session("English", "coach", "AI", current, request)
                    client.side_effect = None
                else:
                    # Reuse the original ID to fail the actual insert and verify the old session's update rolls back.
                    with patch("web_app.uuid.uuid4", return_value=uuid.UUID(current["id"])):
                        outputs = web_app.reset_session("English", "coach", "AI", current, request)

                self.assertEqual(outputs, (web_app.gr.skip(),) * web_app.NEW_SESSION_OUTPUT_COUNT)
                self.assertEqual(store.get_session(current["id"]), before)
                self.assertEqual(len(store.list_sessions(user["id"])), 1)
                warning.assert_called_with(web_app.UI["en"]["new_session_failed"])
                if failure == "model":
                    list(web_app.respond("Here is my unsent draft.", [], current, "coach", "AI", "English", request))
                    self.assertEqual(store.get_session(current["id"])["user_turns"], 1)

            new = web_app.reset_session("English", "coach", "AI", current, request)[-1]
            stale = web_app.reset_session("English", "coach", "AI", current, request)
            self.assertEqual(stale, (web_app.gr.skip(),) * web_app.NEW_SESSION_OUTPUT_COUNT)
            warning.assert_called_with(web_app.UI["en"]["session_moved"])

        self.assertEqual(store.get_session(current["id"])["status"], "abandoned")
        self.assertEqual(store.latest_active_session(user["id"])["id"], new["id"])
        self.assertEqual(new["agent"].context[0]["content"], "Where would you like to begin?")

    def test_reload_reopens_the_unfinished_session(self):
        web_app, _, user, request = _signed_in()
        first = web_app._open_session(user, "coachee", "template", "en")
        list(web_app.respond("What would you like from today?", [], first, "coachee", "Template", "English", request))

        outputs = web_app.initial_load(None, "coach", "AI", "中文", request)
        restored = outputs[-1]

        self.assertEqual(restored["id"], first["id"])
        self.assertEqual(restored["module"], "coachee")
        self.assertEqual(restored["agent"].context, first["agent"].context)
        self.assertEqual(outputs[11]["value"], "coachee")
        self.assertEqual(outputs[12]["value"], "English")

    def test_unreadable_stored_session_is_set_aside_not_fatal(self):
        web_app, store, user, request = _signed_in()
        broken = store.create_session(user["id"], "coach", "en", "llm", "CONTRACT", {"context": []})

        with patch.object(web_app.logger, "exception"):
            outputs = web_app.initial_load(None, "coach", "Template", "English", request)

        self.assertNotEqual(outputs[-1]["id"], broken)
        self.assertEqual(store.get_session(broken)["status"], "abandoned")

    def test_new_session_marks_the_old_one_abandoned(self):
        web_app, store, user, request = _signed_in()
        first = web_app._open_session(user, "coach", "template", "en")

        outputs = web_app.reset_session("English", "coach", "Template", first, request)

        self.assertEqual(store.get_session(first["id"])["status"], "abandoned")
        self.assertNotEqual(outputs[-1]["id"], first["id"])

    def test_a_session_object_never_crosses_to_another_user(self):
        import gradio as gr

        web_app, store, amy, _ = _signed_in()
        amy_session = web_app._open_session(amy, "coach", "template", "en")
        bo_id = store.create_user("bo@example.com", "Bo", accounts.hash_password("a-long-password"))

        outputs = list(web_app.respond("hi", [], amy_session, "coach", "Template", "English", gr.Request(username=str(bo_id))))

        self.assertEqual(outputs[-1][-1]["user_id"], bo_id)
        self.assertNotEqual(outputs[-1][-1]["id"], amy_session["id"])
        self.assertEqual(len(amy_session["agent"].context), 1)

    def test_an_old_tab_shows_the_latest_turns_instead_of_overwriting_them(self):
        # Seen in the app: a message sent from a phone vanished when a laptop tab opened earlier sent its own.
        web_app, store, user, request = _signed_in()
        laptop = web_app._open_session(user, "coach", "template", "en")
        phone = web_app._restore_session(store.get_session(laptop["id"]), user)
        list(web_app.respond("PHONE: I want to sleep earlier.", [], phone, "coach", "Template", "English", request))

        with patch.object(web_app.gr, "Info") as info:
            outputs = list(web_app.respond("LAPTOP: I keep scrolling.", [], laptop, "coach", "Template", "English", request))

        info.assert_called_with(web_app.UI["en"]["session_changed_elsewhere"])
        shown = [message["content"] for message in outputs[-1][1]]
        self.assertIn("PHONE: I want to sleep earlier.", shown)
        self.assertNotIn("LAPTOP: I keep scrolling.", shown)
        self.assertNotIn("value", outputs[-1][0])  # the laptop's message stays in the box
        self.assertTrue(outputs[-1][0]["interactive"])

        list(web_app.respond("LAPTOP: I keep scrolling.", [], outputs[-1][-1], "coach", "Template", "English", request))
        saved = [message["content"] for message in json.loads(store.get_session(laptop["id"])["state"])["context"]]
        self.assertIn("PHONE: I want to sleep earlier.", saved)
        self.assertIn("LAPTOP: I keep scrolling.", saved)

    def test_a_turn_saved_elsewhere_first_is_never_overwritten(self):
        # Two pages replying at the same moment: the first save wins, and the other page reloads it next time.
        web_app, store, user, _ = _signed_in()
        laptop = web_app._open_session(user, "coach", "template", "en")
        phone = web_app._restore_session(store.get_session(laptop["id"]), user)
        phone["agent"].context.append({"role": "client", "content": "PHONE"})
        web_app._save(phone)
        laptop["agent"].context.append({"role": "client", "content": "LAPTOP"})

        with patch.object(web_app.gr, "Warning") as warning:
            web_app._save(laptop)

        warning.assert_called_with(web_app.UI["en"]["reply_not_saved"])
        self.assertEqual(json.loads(store.get_session(laptop["id"])["state"])["context"][-1]["content"], "PHONE")
        reloaded = web_app._ensure_session(laptop, user, "coach", "Template", "English")
        self.assertTrue(reloaded.pop("changed_elsewhere"))
        self.assertEqual(reloaded["agent"].context[-1]["content"], "PHONE")

    def test_modes_resume_independently_with_no_opening_call_even_when_allowance_is_used(self):
        web_app, store, user, request = _signed_in()
        coach = web_app._open_session(user, "coach", "template", "en")
        list(web_app.respond("I want to sleep earlier.", [], coach, "coach", "Template", "English", request))
        practice = web_app.select_module("coachee", "English", "Template", coach, request=request)[-1]
        list(web_app.respond("What would you like from today?", [], practice, "coachee", "Template", "English", request))
        web_app.next_stage([], practice, "coachee", "Template", "English", request)
        before = {session["id"]: store.get_session(session["id"]) for session in (coach, practice)}
        store.update_user(user["id"], daily_session_limit=0)

        with patch.object(web_app, "_append_opening_prompt", side_effect=AssertionError("must resume")):
            for module, expected in (("coach", coach), ("coachee", practice), ("coach", coach)):
                resumed = web_app.select_module(module, "English", "AI", request=request)[-1]
                reopened = web_app.initial_load(None, "coach", "AI", "English", request)[-1]
                for session in (resumed, reopened):
                    self.assertEqual(session["id"], expected["id"])
                    self.assertEqual(session["agent"].context, expected["agent"].context)
                    self.assertEqual(session["agent"].current_state, expected["agent"].current_state)
                    self.assertEqual(store.get_session(session["id"]), before[session["id"]])

    def test_replacing_one_mode_keeps_the_other_and_rejects_an_old_tab(self):
        import gradio as gr

        web_app, store, user, request = _signed_in()
        laptop = web_app._open_session(user, "coach", "template", "en")
        phone = web_app._restore_session(store.get_session(laptop["id"]), user)
        practice = web_app.select_module("coachee", "English", "Template", phone, request=request)[-1]
        saved_practice = store.get_session(practice["id"])

        replaced = web_app.reset_session("English", "coach", "Template", phone, request)[-1]
        with self.assertRaises(gr.Error) as raised:
            list(web_app.respond("hello", [], laptop, "coach", "Template", "English", request))

        self.assertEqual(raised.exception.message, web_app.UI["en"]["session_moved"])
        self.assertEqual(store.get_session(practice["id"]), saved_practice)
        self.assertEqual(store.resumable_session(user["id"], "coach")["id"], replaced["id"])

    def test_a_turn_saved_while_a_new_opening_is_generated_wins(self):
        web_app, store, user, request = _signed_in()
        old = web_app._open_session(user, "coachee", "template", "en")
        other_tab = web_app._restore_session(store.get_session(old["id"]), user)
        original_opening = web_app._append_opening_prompt

        def racing_opening(agent):
            other_tab["agent"].context.append({"role": "coach", "content": "Saved during the opening."})
            web_app._save(other_tab)
            return original_opening(agent)

        with patch.object(web_app, "_append_opening_prompt", side_effect=racing_opening), patch.object(web_app.gr, "Warning"):
            failed = web_app.reset_session("English", "coachee", "Template", old, request)
        self.assertEqual(failed, (web_app.gr.skip(),) * web_app.NEW_SESSION_OUTPUT_COUNT)
        row = store.resumable_session(user["id"], "coachee")
        self.assertEqual(row["id"], old["id"])
        self.assertEqual(json.loads(row["state"])["context"][-1]["content"], "Saved during the opening.")
        self.assertEqual(len(store.list_sessions(user["id"])), 1)

    def test_two_first_openings_in_one_mode_converge_on_one_session(self):
        from concurrent.futures import ThreadPoolExecutor
        import tempfile
        from threading import Barrier

        import web_app

        with tempfile.TemporaryDirectory() as directory:
            store = db.Store(f"sqlite:///{directory}/race.db")
            self.addCleanup(store.engine.dispose)
            web_app.set_store(store)
            uid = store.create_user("race@example.test", "Race", "fake-hash")
            user = store.get_user(uid)
            barrier = Barrier(2)
            opening = web_app._append_opening_prompt

            def wait_for_other_tab(agent):
                barrier.wait(timeout=5)
                return opening(agent)

            with patch.object(web_app, "_append_opening_prompt", side_effect=wait_for_other_tab):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    opened = list(executor.map(lambda _: web_app._resume_mode(user, "coachee", "template", "en"), range(2)))
            self.assertEqual(len(store.list_sessions(uid)), 1)
            self.assertEqual(opened[0]["id"], opened[1]["id"])

    def test_completed_mode_waits_for_the_new_session_button(self):
        web_app, store, user, request = _signed_in()
        practice = web_app._open_session(user, "coachee", "template", "en")
        practice["agent"].current_state = CoachingState.CLOSING
        web_app.next_stage([], practice, "coachee", "Template", "English", request)
        coach = web_app.select_module("coach", "English", "Template", practice, request=request)[-1]
        returned = web_app.select_module("coachee", "English", "Template", coach, request=request)[-1]
        reopened = web_app.initial_load(None, "coach", "Template", "English", request)[-1]

        self.assertEqual(returned["id"], practice["id"])
        self.assertEqual(reopened["id"], practice["id"])
        self.assertTrue(reopened["agent"].is_session_ended())
        self.assertEqual(len(store.list_sessions(user["id"])), 2)
        replacement = web_app.reset_session("English", "coachee", "Template", reopened, request)[-1]
        self.assertNotEqual(replacement["id"], practice["id"])
        self.assertEqual(store.get_session(practice["id"])["status"], "completed")
        self.assertEqual(store.get_session(coach["id"])["status"], "active")

    def test_new_session_in_an_old_tab_leaves_a_session_finished_elsewhere_finished(self):
        web_app, store, user, request = _signed_in()
        laptop = web_app._open_session(user, "coach", "template", "en")
        phone = web_app._restore_session(store.get_session(laptop["id"]), user)
        phone["agent"].session_complete = True
        web_app._save(phone)

        web_app.reset_session("English", "coach", "Template", laptop, request)

        self.assertEqual(store.get_session(laptop["id"])["status"], "completed")

    def test_turns_are_saved_after_each_reply(self):
        web_app, store, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")

        list(web_app.respond("I want more focus.", [], session, "coach", "Template", "English", request))

        row = store.get_session(session["id"])
        self.assertEqual(row["user_turns"], 1)
        self.assertEqual(json.loads(row["state"])["context"], session["agent"].context)

    def test_over_allowance_no_session_starts_and_the_page_says_when(self):
        # No canned replies standing in for the AI: the person is told plainly when they can start again.
        web_app, store, user, request = _signed_in(daily_session_limit=0)
        store.update_user(user["id"], daily_session_limit=None)  # only the coach mode is used up
        store.set_setting("role_limits", {"user": {"coach": 0, "coachee": 5, "tokens": None}})
        session = web_app._open_session(store.get_user(user["id"]), "coach", "llm", "en")

        notice = session["unavailable"]
        self.assertIn("You can start a new one in about 24 h", notice)
        self.assertIn("still has sessions left today", notice)
        self.assertNotIn("id", session)
        self.assertEqual(store.list_sessions(user["id"]), [])
        with patch.object(web_app.gr, "Info") as info:
            outputs = list(web_app.respond("hello", [], session, "coach", "AI", "English", request))
        info.assert_called_with(notice)
        self.assertFalse(outputs[-1][0]["interactive"])
        self.assertEqual(outputs[-1][1], [{"role": "assistant", "content": notice}])
        self.assertFalse(web_app._session_start_outputs(session)["msg"]["interactive"])
        with patch.object(web_app.gr, "Info"):
            web_app.next_stage([], session, "coach", "AI", "English", request)
        self.assertEqual(store.list_sessions(user["id"]), [])

    def test_switching_to_ai_midway_respects_the_allowance(self):
        web_app, _, user, request = _signed_in(daily_session_limit=0)
        session = web_app._open_session(user, "coach", "template", "en")
        with patch.object(web_app.gr, "Warning"):
            list(web_app.respond("hello", [], session, "coach", "AI", "English", request))

        self.assertEqual(session["agent"].mode, "template")

    def test_crisis_message_gets_safety_reply_without_a_model_call(self):
        import safety

        web_app, store, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        with patch.object(session["agent"], "stream_response", side_effect=AssertionError("model should not be called")):
            outputs = list(web_app.respond("Honestly I want to kill myself", [], session, "coach", "Template", "English", request))

        self.assertEqual(outputs[-1][1][-1]["content"], safety.CRISIS_REPLY["en"])
        self.assertIn("safety_flag", [entry["action"] for entry in store.audit_entries()])
        self.assertFalse(safety.looks_like_crisis("I want to kill this procrastination habit"))
        self.assertTrue(safety.looks_like_crisis("我真的不想活了"))

    def test_crisis_check_catches_common_phrasings_and_skips_everyday_idioms(self):
        import safety

        for text in ("活着没意思", "有时候想一了百了", "我想死", "我都想死了", "我想去死", "想过跳楼", "我割腕过",
                     "I don't want to wake up tomorrow", "I've thought about how to take my own life",
                     "I don't want to be here anymore"):
            self.assertTrue(safety.looks_like_crisis(text), text)
        # "I miss you so much", anger at someone else, and shop talk for a price cut aren't about the person's safety.
        for text in ("想死你了", "可想死我了", "大家想死你们了", "你去死吧", "让他去死", "跳楼价清仓", "跳楼大甩卖",
                     "I'm dying to try this", "I want to be here more often"):
            self.assertFalse(safety.looks_like_crisis(text), text)

    def test_crisis_reply_names_help_in_mainland_china(self):
        # Many members are in mainland China, where findahelpline.com alone is little help.
        import safety

        for lang in ("en", "zh"):
            for number in ("12356", "120", "110", "findahelpline.com"):
                self.assertIn(number, safety.CRISIS_REPLY[lang])

    def test_feedback_is_saved_per_message(self):
        import gradio as gr

        web_app, store, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")

        web_app.record_feedback(session, gr.LikeData(None, {"index": 0, "value": "x", "liked": True}), request)
        self.assertEqual(store.feedback_for_session(session["id"]), {0: "like"})
        web_app.record_feedback(session, gr.LikeData(None, {"index": 0, "value": "x", "liked": False}), request)
        self.assertEqual(store.feedback_for_session(session["id"]), {0: "dislike"})

    def test_finished_session_updates_that_users_module_profile(self):
        web_app, store, user, _ = _signed_in()
        session = web_app._open_session(user, "coachee", "template", "en")
        with patch.object(session["agent"], "analyze_session_for_memory", return_value={"strengths": ["Calm presence"]}):
            web_app._learn_from_session(session, "server-key")

        self.assertEqual(store.get_profile(user["id"], "coachee")["strengths"], ["Calm presence"])
        self.assertIsNone(store.get_profile(user["id"], "coach"))
        self.assertEqual(session["agent"].user_profile.strengths, ["Calm presence"])

    def test_model_usage_is_metered_against_the_session(self):
        web_app, store, user, _ = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")

        session["agent"].on_usage("some-model", 100, 20)

        self.assertEqual(store.tokens_since(user["id"], db.utcnow() - db.dt.timedelta(minutes=5)), 120)


class TestAgentPersistence(unittest.TestCase):
    def test_coach_agent_round_trips_through_json(self):
        agent = CoachAgent(mode="template", language="en")
        for text in ("", "I want calmer mornings.", "It matters for my family.", "I'd feel rested."):
            agent.generate_response(text)

        restored = CoachAgent.from_dict(json.loads(json.dumps(agent.to_dict())))

        self.assertEqual(restored.to_dict(), agent.to_dict())
        self.assertTrue(restored.generate_response("Let's keep going."))

    def test_coachee_agent_round_trips_through_json(self):
        agent = CoacheeAgent(mode="template", language="en")
        agent.context.append({"role": agent.assistant_role, "content": agent.get_stage_prompt()})
        for text in ("What would you like to achieve today?", "Why does that matter now?", "How will you know it worked?"):
            agent.generate_response(text)

        restored = CoacheeAgent.from_dict(json.loads(json.dumps(agent.to_dict())))

        self.assertEqual(restored.to_dict(), agent.to_dict())
        self.assertEqual(restored.metrics.stage_questions, agent.metrics.stage_questions)
        self.assertTrue(restored.generate_response("What is happening right now?"))


class TestStore(unittest.TestCase):
    def setUp(self):
        self.store = db.Store("sqlite://")
        self.uid = self.store.create_user("Amy@Example.com ", "Amy", accounts.hash_password("a-long-password"))

    def test_a_save_based_on_an_old_version_changes_nothing(self):
        # Keeps an old tab or device from overwriting newer turns (see web_app._save). Also run on Postgres (pg_test.py).
        session_id = self.store.create_session(self.uid, "coach", "en", "llm", "CONTRACT", {"context": []})
        save = dict(stage="CONTRACT", user_turns=1, language="en", mode="llm")
        first = self.store.save_session(session_id, state={"context": ["first"]}, status="active", **save)
        second = self.store.save_session(session_id, state={"context": ["second"]}, status="active", expected_version=first, **save)
        stale = self.store.save_session(session_id, state={"context": ["stale"]}, status="active", expected_version=first, **save)

        self.assertIsNotNone(second)
        self.assertIsNone(stale)
        self.assertEqual(json.loads(self.store.get_session(session_id)["state"])["context"], ["second"])
        self.assertEqual(self.store.session_version(session_id)["updated_at"], second)
        self.assertIsNotNone(self.store.save_session(session_id, state={"context": []}, status="completed",
                                                     expected_version=second, **save))
        self.store.abandon_session(session_id)  # an old tab's New Session leaves a finished session finished
        self.assertEqual(self.store.get_session(session_id)["status"], "completed")

    def test_deleting_a_session_takes_its_result_rating_and_feedback_with_it(self):
        # A member deleting one conversation from the Account page (also run on Postgres by pg_test.py).
        gone = self.store.create_session(self.uid, "coachee", "en", "llm", "CLOSING", {"context": []})
        keep = self.store.create_session(self.uid, "coachee", "en", "llm", "CLOSING", {"context": []})
        for session_id in (gone, keep):
            self.store.save_session_result(session_id, self.uid, "coachee", score=60)
            self.store.rate_session(session_id, self.uid, "coachee", 4)
            self.store.set_feedback(self.uid, session_id, 1, "like")

        self.store.delete_session(gone)

        self.assertIsNone(self.store.get_session(gone))
        self.assertIsNone(self.store.session_rating(gone))
        self.assertEqual(self.store.feedback_for_session(gone), {})
        self.assertEqual([row["session_id"] for row in self.store.session_results(self.uid, "coachee")], [keep])
        self.assertEqual(self.store.session_rating(keep), 4)

    def test_session_ratings_average_per_module_and_go_with_the_account(self):
        coaching = self.store.create_session(self.uid, "coach", "en", "llm", "CLOSING", {"context": []})
        other = self.store.create_session(self.uid, "coach", "en", "llm", "CLOSING", {"context": []})
        practice = self.store.create_session(self.uid, "coachee", "zh", "llm", "CLOSING", {"context": []})
        self.store.rate_session(coaching, self.uid, "coach", 2)
        self.store.rate_session(coaching, self.uid, "coach", 4)  # changed, not added
        self.store.rate_session(other, self.uid, "coach", 5)
        self.store.rate_session(practice, self.uid, "coachee", 3)

        summary = self.store.ratings_since(db.utcnow().replace(year=2000))
        self.assertEqual(summary, {"coach": (2, 4.5), "coachee": (1, 3.0)})
        self.assertEqual({row["id"]: row["rating"] for row in self.store.recent_sessions()},
                         {coaching: 4, other: 5, practice: 3})
        self.store.delete_user(self.uid)
        self.assertEqual(self.store.ratings_since(db.utcnow().replace(year=2000)), {})

    def test_session_results_join_lists_export_and_go_with_the_account(self):
        import datetime as dt

        trainer = self.store.create_user("trainer@example.com", "Tess", "x", role="trainer")
        self.store.update_user(self.uid, trainer_id=trainer)
        practice = self.store.create_session(self.uid, "coachee", "en", "llm", "CLOSING", {"context": []})
        coaching = self.store.create_session(self.uid, "coach", "en", "llm", "CLOSING", {"context": []})
        self.store.save_session_result(practice, self.uid, "coachee", score=60)
        self.store.save_session_result(practice, self.uid, "coachee", score=65)
        self.store.save_session_result(coaching, self.uid, "coach", card={"goal": "Rest", "next_step": "Walk at lunch"})
        now = db.utcnow()

        listed = {row["id"]: row for row in self.store.list_sessions(self.uid)}
        self.assertEqual(listed[practice]["score"], 65)
        self.assertEqual(listed[coaching]["card"]["next_step"], "Walk at lunch")
        self.assertEqual(self.store.trainer_visible_sessions(trainer)[0]["score"], 65)
        self.assertEqual([r["score"] for r in self.store.session_results(self.uid, "coachee")], [65])
        self.assertEqual(self.store.latest_card(self.uid, now - dt.timedelta(days=1), now + dt.timedelta(minutes=1))["goal"], "Rest")
        self.assertIsNone(self.store.latest_card(self.uid, now - dt.timedelta(days=1), now - dt.timedelta(hours=8)))
        exported = {row["id"]: row for row in self.store.export_user(self.uid)["sessions"]}
        self.assertEqual(exported[practice]["score"], 65)
        self.assertEqual(exported[coaching]["action_card"]["goal"], "Rest")

        self.store.delete_user(self.uid)
        self.assertEqual(self.store.session_results(self.uid, "coachee"), [])

    def test_emails_are_normalised(self):
        self.assertEqual(self.store.get_user_by_email(" amy@example.COM")["id"], self.uid)

    def test_invite_can_be_used_once(self):
        code = self.store.create_invite(self.uid, role="trainer")

        self.assertIsNotNone(self.store.usable_invite(code))
        self.assertTrue(self.store.consume_invite(code))
        self.assertFalse(self.store.consume_invite(code))
        self.assertIsNone(self.store.usable_invite(code))

    def test_revoked_and_expired_invites_are_unusable(self):
        revoked = self.store.create_invite(self.uid)
        self.store.revoke_invite(revoked)
        expired = self.store.create_invite(self.uid, days_valid=-1)

        self.assertIsNone(self.store.usable_invite(revoked))
        self.assertIsNone(self.store.usable_invite(expired))
        self.assertFalse(self.store.consume_invite(expired))

    def test_password_reset_tokens_are_single_use_and_stored_hashed(self):
        token = self.store.create_password_reset(self.uid)

        stored = self.store._all(db.sa.select(db.password_resets))
        self.assertNotEqual(stored[0]["token_hash"], token)
        self.assertEqual(self.store.consume_password_reset(token), self.uid)
        self.assertIsNone(self.store.consume_password_reset(token))

    def test_trainer_sees_practice_and_shared_sessions_only(self):
        trainer = self.store.create_user("t@example.com", "Trainer", "x", role="trainer")
        self.store.update_user(self.uid, trainer_id=trainer)
        other = self.store.create_user("o@example.com", "Other", "x")
        practice = self.store.create_session(self.uid, "coachee", "en", "llm", "CONTRACT", {"context": []})
        private = self.store.create_session(self.uid, "coach", "en", "llm", "CONTRACT", {"context": []})
        shared = self.store.create_session(self.uid, "coach", "en", "llm", "CONTRACT", {"context": []})
        self.store.set_session_shared(shared, True)
        self.store.create_session(other, "coachee", "en", "llm", "CONTRACT", {"context": []})

        visible = {row["id"] for row in self.store.trainer_visible_sessions(trainer)}

        self.assertEqual(visible, {practice, shared})
        self.assertNotIn(private, visible)

    def test_deleting_a_user_removes_their_data_but_keeps_the_audit_trail(self):
        session_id = self.store.create_session(self.uid, "coach", "en", "llm", "CONTRACT", {"context": []})
        self.store.save_profile(self.uid, "coach", {"strengths": ["x"]})
        self.store.record_usage(self.uid, session_id, "m", 1, 1)
        self.store.set_feedback(self.uid, session_id, 0, "like")
        self.store.log(self.uid, "session_viewed", target_session_id=session_id)

        self.store.delete_user(self.uid)

        self.assertIsNone(self.store.get_session(session_id))
        self.assertIsNone(self.store.get_profile(self.uid, "coach"))
        self.assertEqual(self.store.tokens_since(self.uid, db.utcnow() - db.dt.timedelta(days=1)), 0)
        self.assertEqual(len(self.store.audit_entries()), 1)

    def test_export_includes_transcripts_and_feedback(self):
        session_id = self.store.create_session(self.uid, "coach", "en", "llm", "CONTRACT",
                                               {"context": [{"role": "coach", "content": "Hello"}]})
        self.store.set_feedback(self.uid, session_id, 0, "like")

        export = self.store.export_user(self.uid)

        self.assertEqual(export["account"]["email"], "amy@example.com")
        self.assertEqual(export["sessions"][0]["transcript"][0]["content"], "Hello")
        self.assertEqual(export["sessions"][0]["feedback"], {0: "like"})
        self.assertNotIn("password_hash", json.dumps(export, default=str))

    def test_completion_time_is_recorded_once(self):
        session_id = self.store.create_session(self.uid, "coach", "en", "llm", "CONTRACT", {"context": []})
        save = dict(state={"context": []}, stage="CLOSING", user_turns=3, language="en", mode="llm")
        self.store.save_session(session_id, status="completed", **save)
        first = self.store.get_session(session_id)["completed_at"]
        self.store.save_session(session_id, status="completed", **save)

        self.assertIsNotNone(first)
        self.assertEqual(self.store.get_session(session_id)["completed_at"], first)


class TestAccounts(unittest.TestCase):
    def setUp(self):
        self.store = db.Store("sqlite://")
        self.uid = self.store.create_user("amy@example.com", "Amy", accounts.hash_password("a-long-password"))

    def test_password_hashing(self):
        stored = self.store.get_user(self.uid)["password_hash"]

        self.assertTrue(accounts.verify_password("a-long-password", stored))
        self.assertFalse(accounts.verify_password("a-long-passwore", stored))
        self.assertFalse(accounts.verify_password("anything", "not-a-hash"))
        self.assertEqual(accounts.password_problem("short"), "password_too_short")
        self.assertEqual(accounts.password_problem("a-long-password", "other-password"), "password_mismatch")

    def test_session_cookie_round_trip_and_tampering(self):
        cookie = accounts.make_session_cookie(self.store.get_user(self.uid), "secret")

        self.assertEqual(accounts.read_session_cookie(cookie, "secret", self.store.get_user)["id"], self.uid)
        self.assertIsNone(accounts.read_session_cookie(cookie, "other-secret", self.store.get_user))
        user_id, expires, signature = cookie.split(".")
        self.assertIsNone(accounts.read_session_cookie(f"{user_id}.{int(expires) + 999}.{signature}", "secret", self.store.get_user))
        self.assertIsNone(accounts.read_session_cookie("garbage", "secret", self.store.get_user))

    def test_cookie_stops_working_after_password_change_disable_or_expiry(self):
        cookie = accounts.make_session_cookie(self.store.get_user(self.uid), "secret")
        self.assertIsNone(accounts.read_session_cookie(cookie, "secret", self.store.get_user, now=time.time() + 15 * 86400))

        self.store.update_user(self.uid, status="disabled")
        self.assertIsNone(accounts.read_session_cookie(cookie, "secret", self.store.get_user))
        self.store.update_user(self.uid, status="active", password_hash=accounts.hash_password("a-new-long-password"))
        self.assertIsNone(accounts.read_session_cookie(cookie, "secret", self.store.get_user))

    def test_csrf_token_is_tied_to_the_login(self):
        token = accounts.csrf_token("cookie-a", "secret")

        self.assertTrue(accounts.csrf_ok("cookie-a", "secret", token))
        self.assertFalse(accounts.csrf_ok("cookie-b", "secret", token))
        self.assertFalse(accounts.csrf_ok(None, "secret", token))

    def test_login_throttle_blocks_after_repeated_failures(self):
        throttle = accounts.LoginThrottle(max_failures=3, window_seconds=60)
        for _ in range(3):
            throttle.failed("amy|1.2.3.4", now=100)

        self.assertTrue(throttle.blocked("amy|1.2.3.4", now=101))
        self.assertFalse(throttle.blocked("amy|1.2.3.4", now=200))
        self.assertFalse(throttle.blocked("bo|1.2.3.4", now=101))

    def test_transcript_visibility_rules(self):
        owner = {"id": 1, "role": "user", "trainer_id": 2}
        practice = {"user_id": 1, "module": "coachee", "shared_with_trainer": False}
        private = {"user_id": 1, "module": "coach", "shared_with_trainer": False}
        shared = {"user_id": 1, "module": "coach", "shared_with_trainer": True}
        trainer = {"id": 2, "role": "trainer"}
        other_trainer = {"id": 3, "role": "trainer"}
        admin = {"id": 4, "role": "admin"}
        stranger = {"id": 5, "role": "user"}

        self.assertTrue(accounts.can_view_session(owner, private, owner))
        self.assertTrue(accounts.can_view_session(trainer, practice, owner))
        self.assertTrue(accounts.can_view_session(trainer, shared, owner))
        self.assertFalse(accounts.can_view_session(trainer, private, owner))
        self.assertFalse(accounts.can_view_session(other_trainer, practice, owner))
        self.assertFalse(accounts.can_view_session(stranger, practice, owner))
        for session in (practice, private, shared):
            self.assertFalse(accounts.can_view_session(admin, session, owner))

    def test_an_admin_who_is_the_assigned_mentor_sees_only_what_a_mentor_sees(self):
        owner = {"id": 1, "role": "user", "trainer_id": 4}
        admin_mentor = {"id": 4, "role": "admin"}

        self.assertTrue(accounts.can_view_session(admin_mentor, {"user_id": 1, "module": "coachee", "shared_with_trainer": False}, owner))
        self.assertTrue(accounts.can_view_session(admin_mentor, {"user_id": 1, "module": "coach", "shared_with_trainer": True}, owner))
        self.assertFalse(accounts.can_view_session(admin_mentor, {"user_id": 1, "module": "coach", "shared_with_trainer": False}, owner))


class TestQuota(unittest.TestCase):
    def setUp(self):
        self.store = db.Store("sqlite://")

    def _user(self, role="user", **fields):
        user_id = self.store.create_user(f"{role}{len(self.store.list_users())}@example.com", "P", "x", role=role)
        if fields:
            self.store.update_user(user_id, **fields)
        return self.store.get_user(user_id)

    def _session(self, user, module="coach", completed=False):
        session_id = self.store.create_session(user["id"], module, "en", "llm", "CONTRACT", {"context": []})
        if completed:
            self.store.save_session(session_id, state={"context": []}, status="completed", stage="CLOSING",
                                    user_turns=5, language="en", mode="llm")

    def test_ai_coach_and_coachee_lab_have_separate_allowances(self):
        import quota

        user = self._user()
        for _ in range(3):
            self._session(user, "coach", completed=True)

        coach = quota.allowance(self.store, user, "coach")
        practice = quota.allowance(self.store, user, "coachee")
        self.assertEqual((coach.blocked_reason, coach.sessions_left), ("sessions", 0))
        self.assertEqual((practice.blocked_reason, practice.sessions_left, practice.session_limit), (None, 5, 5))

    def test_abandoned_starts_are_capped_at_twice_the_allowance(self):
        import quota

        user = self._user()
        for _ in range(6):
            self._session(user, "coach")

        self.assertEqual(quota.allowance(self.store, user, "coach").blocked_reason, "starts")
        self.assertIsNone(quota.allowance(self.store, user, "coachee").blocked_reason)

    def test_tokens_are_one_daily_backstop_for_both_modules(self):
        import quota

        user = self._user()
        self.store.record_usage(user["id"], None, "m", 350_000, 50_000)

        self.assertEqual(quota.allowance(self.store, user, "coach").blocked_reason, "tokens")
        self.assertEqual(quota.allowance(self.store, user, "coachee").blocked_reason, "tokens")

    def test_blocked_allowance_says_when_ai_returns(self):
        import quota

        user = self._user()
        for _ in range(3):
            self._session(user, "coach", completed=True)
        allowance = quota.allowance(self.store, user, "coach")

        self.assertEqual(allowance.hours_until_available(now=db.utcnow()), 24)
        self.assertEqual(allowance.hours_until_available(now=db.utcnow() + db.dt.timedelta(hours=20)), 4)

    def test_admins_are_unlimited_and_per_person_overrides_apply(self):
        import quota

        admin = self._user("admin")
        for _ in range(10):
            self._session(admin, completed=True)
        self.assertIsNone(quota.allowance(self.store, admin, "coach").blocked_reason)
        self.assertIsNone(quota.allowance(self.store, admin, "coach").session_limit)

        generous = self._user(daily_session_limit=10)
        for _ in range(5):
            self._session(generous, completed=True)
        allowance = quota.allowance(self.store, generous, "coach")
        self.assertEqual((allowance.session_limit, allowance.start_limit, allowance.sessions_left), (10, 20, 5))

    def test_admin_can_change_role_defaults(self):
        import quota

        quota.save_role_limits(self.store, "user", 4, None, 500_000)
        user = self._user()

        self.assertEqual(quota.role_limits(self.store)["user"], {"coach": 4, "coachee": None, "tokens": 500_000})
        self.assertEqual(quota.allowance(self.store, user, "coach").session_limit, 4)
        self.assertIsNone(quota.allowance(self.store, user, "coachee").session_limit)
        self.assertEqual(quota.role_limits(self.store)["trainer"], quota.ROLE_DEFAULTS["trainer"])

    def test_message_rate_limiter(self):
        import quota

        limiter = quota.MessageRateLimiter(limit=2)

        self.assertTrue(limiter.allow(1, now=100))
        self.assertTrue(limiter.allow(1, now=101))
        self.assertFalse(limiter.allow(1, now=102))
        self.assertTrue(limiter.allow(2, now=102))
        self.assertTrue(limiter.allow(1, now=161))


class TestUsageMetering(unittest.TestCase):
    def _raw_client(self, response=None, chunks=None):
        class Completions:
            def create(self, **kwargs):
                if kwargs.get("stream"):
                    return FakeStream(chunks)
                return response

        class FakeStream:
            def __init__(self, chunks):
                self.chunks = chunks
                self.closed = False

            def __iter__(self):
                return iter(self.chunks)

            def close(self):
                self.closed = True

        return type("Raw", (), {"chat": type("Chat", (), {"completions": Completions()})()})()

    @staticmethod
    def _chunk(text=None, usage=None):
        choices = [type("Choice", (), {"delta": type("Delta", (), {"content": text})()})()] if text is not None else []
        return type("Chunk", (), {"choices": choices, "usage": usage})()

    def test_non_streaming_call_reports_provider_usage(self):
        from coaching_core import _MeteredClient

        usage = type("Usage", (), {"prompt_tokens": 120, "completion_tokens": 30})()
        message = type("Message", (), {"content": "Hi"})()
        response = type("Response", (), {"choices": [type("Choice", (), {"message": message})()], "usage": usage})()
        seen = []

        _MeteredClient(self._raw_client(response=response), lambda *args: seen.append(args)).chat.completions.create(model="m", messages=[])

        self.assertEqual(seen, [("m", 120, 30)])

    def test_streaming_call_reports_usage_from_the_final_chunk_once(self):
        from coaching_core import _MeteredClient, _stream_text

        usage = type("Usage", (), {"prompt_tokens": 80, "completion_tokens": 6})()
        chunks = [self._chunk("Hello "), self._chunk("there"), self._chunk(usage=usage)]
        seen = []
        client = _MeteredClient(self._raw_client(chunks=chunks), lambda *args: seen.append(args))

        text = list(_stream_text(client, model="m", messages=[]))[-1]

        self.assertEqual(text, "Hello there")
        self.assertEqual(seen, [("m", 80, 6)])

    def test_usage_is_estimated_when_the_provider_omits_it(self):
        from coaching_core import _MeteredClient

        chunks = [self._chunk("x" * 30)]
        seen = []
        client = _MeteredClient(self._raw_client(chunks=chunks), lambda *args: seen.append(args))
        stream = client.chat.completions.create(model="m", messages=[{"role": "user", "content": "y" * 60}], stream=True)
        for _ in stream:
            pass
        stream.close()

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][2], 10)
        self.assertGreater(seen[0][1], 20)


class TestAccountPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import web_app

        cls.web_app = web_app
        cls.secret = "test-secret"
        cls.app = web_app.create_app(store=db.Store("sqlite://"), env={"STUDIO_SECRET_KEY": cls.secret})

    def setUp(self):
        from fastapi.testclient import TestClient

        self.store = db.Store("sqlite://")
        self.web_app.set_store(self.store)
        self.client = TestClient(self.app)

    def _person(self, email, role="user", **fields):
        user_id = self.store.create_user(email, email.split("@")[0].title(), accounts.hash_password("a-long-password"), role=role)
        if fields:
            self.store.update_user(user_id, **fields)
        return user_id

    def _sign_in(self, email, client=None):
        from fastapi.testclient import TestClient

        client = client or TestClient(self.app)
        response = client.post("/login", data={"email": email, "password": "a-long-password"}, follow_redirects=False)
        self.assertEqual(response.status_code, 303, response.text[:200])
        return client

    def _csrf(self, client):
        return accounts.csrf_token(client.cookies.get(accounts.SESSION_COOKIE), self.secret)

    def test_setup_page_exists_only_before_the_first_account(self):
        self.assertEqual(self.client.get("/login", follow_redirects=False).headers["location"], "/setup")
        self._person("owner@example.com", role="admin")

        self.assertEqual(self.client.get("/setup", follow_redirects=False).headers["location"], "/login")
        response = self.client.post("/setup", data={"name": "X", "email": "x@example.com", "password": "a-long-password",
                                                    "confirm": "a-long-password"}, follow_redirects=False)
        self.assertEqual(response.headers["location"], "/login")
        self.assertEqual(len(self.store.list_users()), 1)

    def test_invite_signup_needs_consent_and_works_once(self):
        admin = self._person("owner@example.com", role="admin")
        trainer = self._person("trainer@example.com", role="trainer")
        code = self.store.create_invite(admin, role="user", trainer_id=trainer, email="new@example.com")
        form = {"name": "New", "email": "someone-else@example.com", "password": "a-long-password", "confirm": "a-long-password"}

        self.assertEqual(self.client.post(f"/invite/{code}", data=form).status_code, 200)
        self.assertIsNone(self.store.get_user_by_email("new@example.com"))
        response = self.client.post(f"/invite/{code}", data={**form, "consent": "yes"}, follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        person = self.store.get_user_by_email("new@example.com")
        self.assertEqual((person["role"], person["trainer_id"]), ("user", trainer))
        self.assertIsNotNone(person["consented_at"])
        self.assertEqual(self.client.get(f"/invite/{code}").status_code, 410)

    def test_guessing_from_ever_changing_addresses_still_hits_a_limit(self):
        # The address comes from X-Forwarded-For, which a caller controls, so the email address is counted on its own too.
        from fastapi.testclient import TestClient
        import account_pages

        self._person("target@example.com")
        wrong = {"email": "target@example.com", "password": "wrong-password"}
        for n in range(account_pages.EMAIL_MAX_FAILURES):
            client = TestClient(self.app, client=(f"10.0.0.{n}", 5000))
            self.assertEqual(client.post("/login", data=wrong).status_code, 401)

        fresh = TestClient(self.app, client=("10.0.1.1", 5000))
        right = fresh.post("/login", data={**wrong, "password": "a-long-password"}, follow_redirects=False)
        self.assertEqual(right.status_code, 429)

    def test_wrong_password_is_rejected_then_throttled(self):
        self._person("amy@example.com")
        for _ in range(8):
            response = self.client.post("/login", data={"email": "amy@example.com", "password": "wrong-password"})
            self.assertEqual(response.status_code, 401)

        response = self.client.post("/login", data={"email": "amy@example.com", "password": "a-long-password"})
        self.assertEqual(response.status_code, 429)

    def test_app_page_answers_gradios_space_status_check_without_huggingface_co(self):
        # huggingface.co is blocked in mainland China; waiting on it kept the app on "loading" there.
        import gradio
        import web_assets

        self._person("amy@example.com")
        page = self._sign_in("amy@example.com").get("/")

        self.assertEqual(page.status_code, 200)
        self.assertIn("<head><script>" + web_assets.space_status_js + "</script>", page.text)
        self.assertLess(page.text.index("by-subdomain"), page.text.index('<script type="module"'))
        self.assertEqual(int(page.headers["content-length"]), len(page.content))
        self.assertEqual(self.client.get("/", follow_redirects=False).headers["location"], "/login")
        # The address Gradio asks must still be the one the answer covers.
        frontend = Path(gradio.__file__).parent / "templates" / "frontend" / "assets"
        self.assertTrue(any("https://huggingface.co/api/spaces/by-subdomain/" in path.read_text(encoding="utf-8")
                            for path in frontend.glob("index-*.js")))

    def test_transcripts_follow_the_visibility_rules_and_are_audited(self):
        admin = self._person("owner@example.com", role="admin")
        trainer = self._person("trainer@example.com", role="trainer")
        learner = self._person("learner@example.com", trainer_id=trainer)
        self._person("stranger@example.com")
        practice = self.store.create_session(learner, "coachee", "en", "llm", "CONTRACT",
                                             {"context": [{"role": "coachee", "content": "I feel stuck <b>here</b>"}]})
        private = self.store.create_session(learner, "coach", "en", "llm", "CONTRACT", {"context": []})

        learner_client = self._sign_in("learner@example.com")
        trainer_client = self._sign_in("trainer@example.com")
        stranger_client = self._sign_in("stranger@example.com")
        admin_client = self._sign_in("owner@example.com")

        page = learner_client.get(f"/sessions/{practice}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("&lt;b&gt;here&lt;/b&gt;", page.text)
        self.assertEqual(stranger_client.get(f"/sessions/{practice}").status_code, 403)
        self.assertEqual(trainer_client.get(f"/sessions/{practice}").status_code, 200)
        self.assertEqual(trainer_client.get(f"/sessions/{private}").status_code, 403)

        self.assertEqual(admin_client.get(f"/sessions/{practice}").status_code, 403)
        self.assertEqual(admin_client.get(f"/sessions/{private}").status_code, 403)

        learner_client.post(f"/account/sessions/{private}/share", data={"csrf": self._csrf(learner_client), "shared": "yes"})
        self.assertEqual(trainer_client.get(f"/sessions/{private}").status_code, 200)
        self.assertEqual(admin_client.get(f"/sessions/{private}").status_code, 403)

        viewers = [entry["actor_id"] for entry in self.store.audit_entries() if entry["action"] == "session_viewed"]
        self.assertCountEqual(viewers, [trainer, trainer])

    def test_failed_practice_review_retries_the_original_transcript_and_saves_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        import gradio as gr
        from coachee_agent import REVIEW_UNAVAILABLE

        mentor = self._person("mentor@example.com", role="trainer")
        uid = self._person("learner@example.com", trainer_id=mentor, daily_session_limit=1)
        user = self.store.get_user(uid)
        request = gr.Request(username=str(uid))
        owner = self._sign_in("learner@example.com")
        owner.cookies.set("studio_lang", "zh")
        trainer = self._sign_in("mentor@example.com")
        path_calls = []
        start = db.utcnow() - db.dt.timedelta(hours=1)
        processing, release = Event(), Event()
        replies = ["", "Sorry, the service is unavailable.", "", "暂时无法写出点评。", "会话结果：练习已保存。\n最后得分：42/100"]

        def fake_client(key, on_usage=None):
            client = _fake_llm_client(replies, path_calls)
            create = client.chat.completions.create

            def metered(**kw):
                if len(replies) == 1:
                    processing.set()
                    if not release.wait(timeout=8):
                        raise RuntimeError("test timed out")
                response = create(**kw)
                on_usage("fake", 100, 20)
                return response

            client.chat.completions.create = metered
            return client

        app = self.web_app
        # Reopen a practice whose next send has to finish at the existing message limit.
        agent = CoacheeAgent(mode="llm", language="zh")
        agent.context = _conversation(agent, 100)
        agent.current_state = CoachingState.ACTION
        practice = self.store.create_session(uid, "coachee", "zh", "llm", "ACTION", agent.to_dict())
        session = app._restore_session(self.store.get_session(practice), user)
        detail = f"/sessions/{practice}"
        retry = detail + "/retry-review"
        token = {"csrf": self._csrf(owner)}

        with patch.object(app, "_safe_key", return_value="fake"), patch("coachee_agent._build_client", side_effect=fake_client), \
                patch.object(app, "_learn_from_session"), patch("coachee_agent.logger.warning"), patch.object(app.gr, "Info"):
            list(app.respond("Finish at the limit.", [], session, "coachee", "AI", "中文", request))
            failed = self.store.get_session(practice)
            failed_state = json.loads(failed["state"])
            self.assertTrue(failed_state["review_failed"])
            self.assertEqual(failed_state["stopped_at_limit"], 100)
            self.assertEqual(failed_state["context"][:-1], agent.context)
            self.assertEqual(failed_state["context"][-1]["content"], REVIEW_UNAVAILABLE["zh"])
            self.assertIn("重新生成点评", owner.get(detail).text)
            self.assertNotIn("Regenerate review", trainer.get(detail).text)
            self.assertEqual(trainer.post(retry, data={"csrf": self._csrf(trainer)}).status_code, 403)
            self.assertEqual(owner.post(retry, data={"csrf": "wrong"}, follow_redirects=False).headers["location"],
                             f"/login?next={detail}/retry-review")
            self.assertIn("可以再试一次", owner.post(retry, data=token).text)
            self.assertEqual(json.loads(self.store.get_session(practice)["state"]), failed_state)
            self.assertEqual(self.store.session_results(uid, "coachee"), [])

            second_tab = self._sign_in("learner@example.com")
            with ThreadPoolExecutor(max_workers=1) as executor:
                first_request = executor.submit(owner.post, retry, data=token)
                try:
                    self.assertTrue(processing.wait(timeout=5))
                    response = second_tab.post(retry, data={"csrf": self._csrf(second_tab)}, follow_redirects=False)
                    self.assertIn("retry_busy", response.headers["location"])
                finally:
                    release.set()
                self.assertIn("本次练习的点评已生成", first_request.result(timeout=8).text)

            self.assertEqual(owner.post(retry, data=token).status_code, 403)

        final = self.store.get_session(practice)
        final_state = json.loads(final["state"])
        self.assertEqual(final_state["context"][:-1], agent.context)
        self.assertEqual(final["completed_at"], failed["completed_at"])
        self.assertEqual(final["score"], 42)
        self.assertEqual(self.store.ai_sessions_since(uid, start, "coachee", completed=True)[0], 1)
        self.assertEqual([result["score"] for result in self.store.session_results(uid, "coachee")], [42])
        self.assertEqual(len(path_calls), 5)
        prompt = path_calls[-1]["messages"][0]["content"]
        self.assertTrue(all(call["messages"][0]["content"] == prompt for call in path_calls))
        self.assertIn("Coach: Message 50", prompt)
        self.assertIn("used all 100 messages", prompt)
        self.assertIn("Simplified Chinese", prompt)
        self.assertNotIn(REVIEW_UNAVAILABLE["zh"], prompt)
        self.assertEqual(self.store.tokens_since(uid, start), 600)
        self.assertNotIn("重新生成点评", owner.get(detail).text)
        for page in (owner.get(detail), owner.get("/account"), trainer.get(detail), trainer.get("/mentor")):
            self.assertIn("42/100", page.text)

    def test_only_recognizable_failed_completed_practice_can_regenerate(self):
        from coachee_agent import REVIEW_UNAVAILABLE

        uid = self._person("learner@example.com")
        owner = self._sign_in("learner@example.com")
        token = {"csrf": self._csrf(owner)}
        for status, content, eligible in (
            ("active", REVIEW_UNAVAILABLE["en"], False),
            ("abandoned", REVIEW_UNAVAILABLE["en"], False),
            ("completed", "Some old practice feedback with no score.", False),
            ("completed", REVIEW_UNAVAILABLE["en"], True),
            ("deleted", REVIEW_UNAVAILABLE["en"], False),
        ):
            with self.subTest(status=status, content=content):
                agent = CoacheeAgent(mode="llm", language="en")
                agent.session_complete = status == "completed"
                agent.current_state = CoachingState.CLOSING
                agent.context = [{"role": "coach", "content": "What would you like to take away?"},
                                 {"role": "coachee", "content": content}]
                state = agent.to_dict()
                state.pop("review_failed")
                state.pop("stopped_at_limit")
                sid = self.store.create_session(uid, "coachee", "en", "llm", "CLOSING", state)
                if status == "deleted":
                    self.store.delete_session(sid)
                else:
                    self.store.set_session_status(sid, status)
                url = f"/sessions/{sid}"
                self.assertEqual("Regenerate review" in owner.get(url).text, eligible)
                with patch.object(self.web_app, "_safe_key", return_value="fake"), \
                        patch("coachee_agent._build_client", return_value=_fake_llm_client(
                            ["Session Result: A clear question.\nScore: 7/100"], [])):
                    response = owner.post(url + "/retry-review", data=token, follow_redirects=False)
                self.assertEqual(response.status_code, 303 if eligible else 403)

    def test_admin_page_lists_sessions_without_opening_them(self):
        self._person("owner@example.com", role="admin")
        learner = self._person("learner@example.com")
        session = self.store.create_session(learner, "coachee", "en", "llm", "CONTRACT",
                                            {"context": [{"role": "coachee", "content": "A very private sentence"}]})
        admin_client = self._sign_in("owner@example.com")

        page = admin_client.get("/admin?lang=en").text

        self.assertIn("AI Coachee Lab", page)
        self.assertIn("not what was said", page)
        self.assertNotIn(f"/sessions/{session}", page)
        self.assertNotIn("A very private sentence", page)

    def test_account_page_mentions_a_mentor_only_to_people_who_have_one(self):
        self._person("solo@example.com")
        self._person("learner@example.com", trainer_id=self._person("trainer@example.com", role="trainer"))

        solo = self._sign_in("solo@example.com").get("/account?lang=en").text
        learner = self._sign_in("learner@example.com").get("/account?lang=en").text

        self.assertIn("Only you can see your sessions.", solo)
        self.assertNotIn("Your mentor can review", solo)
        self.assertIn("Your mentor can review", learner)

    def test_member_and_mentor_see_scores_and_action_cards_but_the_admin_does_not(self):
        self._person("owner@example.com", role="admin")
        trainer = self._person("trainer@example.com", role="trainer")
        learner = self._person("learner@example.com", trainer_id=trainer)
        practice = self.store.create_session(learner, "coachee", "en", "llm", "CLOSING", {"context": []})
        self.store.save_session_result(practice, learner, "coachee", score=81)
        coaching = self.store.create_session(learner, "coach", "en", "llm", "CLOSING", {"context": []})
        self.store.save_session_result(coaching, learner, "coach",
                                       card={"goal": "Run 5 km", "next_step": "Buy running shoes", "by_when": "Saturday", "support": ""})

        account = self._sign_in("learner@example.com").get("/account?lang=en").text
        mentor = self._sign_in("trainer@example.com").get("/mentor?lang=en").text
        admin = self._sign_in("owner@example.com").get("/admin?lang=en").text

        self.assertIn("Buy running shoes", account)
        self.assertIn("Latest 81/100", account)
        self.assertIn("81/100", mentor)
        self.assertNotIn("Buy running shoes", mentor)
        self.assertNotIn("81/100", admin)
        self.assertNotIn("Buy running shoes", admin)

    def test_changing_a_members_mentor_makes_their_shared_sessions_private(self):
        admin = self._person("owner@example.com", role="admin")
        trainer = self._person("trainer@example.com", role="trainer")
        learner = self._person("learner@example.com", trainer_id=trainer)
        private = self.store.create_session(learner, "coach", "en", "llm", "CONTRACT", {"context": []})
        self.store.set_session_shared(private, True)
        admin_client = self._sign_in("owner@example.com")

        admin_client.post(f"/admin/users/{learner}", data={"csrf": self._csrf(admin_client), "role": "user",
                                                           "trainer_id": str(admin), "status": "active"})

        self.assertEqual(self.store.get_user(learner)["trainer_id"], admin)
        self.assertFalse(self.store.get_session(private)["shared_with_trainer"])
        self.assertEqual(admin_client.get(f"/sessions/{private}").status_code, 403)

    def test_posts_without_a_csrf_token_change_nothing(self):
        learner = self._person("learner@example.com", trainer_id=self._person("trainer@example.com", role="trainer"))
        private = self.store.create_session(learner, "coach", "en", "llm", "CONTRACT", {"context": []})
        client = self._sign_in("learner@example.com")

        response = client.post(f"/account/sessions/{private}/share", data={"shared": "yes"}, follow_redirects=False)
        client.post("/account/delete", data={"confirm": "DELETE"}, follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertFalse(self.store.get_session(private)["shared_with_trainer"])
        self.assertIsNotNone(self.store.get_user(learner))

    def test_admin_reset_link_works_once_and_signs_out_old_logins(self):
        self._person("owner@example.com", role="admin")
        learner = self._person("learner@example.com")
        admin_client = self._sign_in("owner@example.com")
        learner_client = self._sign_in("learner@example.com")

        page = admin_client.post(f"/admin/users/{learner}/reset-link", data={"csrf": self._csrf(admin_client)})
        link = page.text.split("/reset/")[1].split("<")[0]
        form = {"password": "brand-new-password", "confirm": "brand-new-password"}

        self.assertEqual(self.client.post(f"/reset/{link}", data=form, follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.get(f"/reset/{link}").status_code, 410)
        self.assertEqual(learner_client.get("/account", follow_redirects=False).status_code, 303)

    def test_last_admin_cannot_demote_themselves(self):
        admin = self._person("owner@example.com", role="admin")
        client = self._sign_in("owner@example.com")

        client.post(f"/admin/users/{admin}", data={"csrf": self._csrf(client), "role": "user", "status": "active",
                                                   "trainer_id": "", "daily_session_limit": "", "daily_token_limit": ""})

        self.assertEqual(self.store.get_user(admin)["role"], "admin")

    def test_admin_sets_roles_trainers_and_limits(self):
        self._person("owner@example.com", role="admin")
        trainer = self._person("trainer@example.com", role="trainer")
        learner = self._person("learner@example.com")
        client = self._sign_in("owner@example.com")

        client.post(f"/admin/users/{learner}", data={"csrf": self._csrf(client), "role": "user", "status": "disabled",
                                                     "trainer_id": str(trainer), "daily_session_limit": "5", "daily_token_limit": ""})

        person = self.store.get_user(learner)
        self.assertEqual((person["trainer_id"], person["status"], person["daily_session_limit"], person["daily_token_limit"]),
                         (trainer, "disabled", 5, None))
        self.assertEqual(self.client.post("/login", data={"email": "learner@example.com", "password": "a-long-password"}).status_code, 401)

    def test_learners_cannot_reach_trainer_or_admin_pages(self):
        self._person("learner@example.com")
        client = self._sign_in("learner@example.com")

        self.assertEqual(client.get("/admin", follow_redirects=False).status_code, 303)
        self.assertEqual(client.get("/mentor", follow_redirects=False).status_code, 303)

    def test_trainer_invites_assign_new_learners_to_them(self):
        trainer = self._person("trainer@example.com", role="trainer")
        client = self._sign_in("trainer@example.com")

        page = client.post("/mentor/invites", data={"csrf": self._csrf(client), "email": ""})
        code = page.text.split("/invite/")[1].split("<")[0]

        self.assertEqual(self.store.get_invite(code)["trainer_id"], trainer)
        self.assertEqual(self.store.get_invite(code)["role"], "user")

    def test_a_group_invite_lets_in_as_many_people_as_set_then_closes(self):
        # Inviting a WeChat group shouldn't take one link per person.
        import datetime as dt

        self._person("owner@example.com", role="admin")
        client = self._sign_in("owner@example.com")
        page = client.post("/admin/invites?lang=en", data={"csrf": self._csrf(client), "email": "", "role": "user",
                                                           "uses": "2", "days": "7"})
        code = page.text.split("/invite/")[1].split("<")[0]
        invite = self.store.get_invite(code)

        self.assertIn("Group invite link (valid 7 days, for up to 2 people)", page.text)
        self.assertEqual(invite["max_uses"], 2)
        self.assertAlmostEqual((invite["expires_at"] - invite["created_at"]).days, 7)
        for n in (1, 2):
            form = {"name": f"P{n}", "email": f"p{n}@example.com", "password": "a-long-password",
                    "confirm": "a-long-password", "consent": "yes"}
            self.assertEqual(self.client.post(f"/invite/{code}", data=form, follow_redirects=False).status_code, 303)
            self.client.cookies.clear()
        self.assertEqual(self.client.get(f"/invite/{code}").status_code, 410)
        self.assertIn("2 of 2 used", client.get("/admin?lang=en").text)

    def test_invite_size_and_length_stay_within_bounds(self):
        import account_pages

        self.assertEqual(account_pages.invite_limits("", ""), (1, 14))
        self.assertEqual(account_pages.invite_limits("0", "0"), (1, 1))
        self.assertEqual(account_pages.invite_limits("5000", "999"), (account_pages.MAX_INVITE_USES, account_pages.MAX_INVITE_DAYS))
        self.assertEqual(account_pages.invite_limits("-3", "abc"), (1, 14))
        self.assertEqual(account_pages.invite_limits("30", "7", locked=True), (1, 7))  # one address, one person

        trainer = self._person("trainer@example.com", role="trainer")
        client = self._sign_in("trainer@example.com")
        page = client.post("/mentor/invites?lang=zh", data={"csrf": self._csrf(client), "email": "", "uses": "12", "days": "30"})
        code = page.text.split("/invite/")[1].split("<")[0]
        self.assertIn("群组邀请链接（30 天内有效，最多 12 人使用）", page.text)
        self.assertEqual((self.store.get_invite(code)["max_uses"], self.store.get_invite(code)["trainer_id"]), (12, trainer))

    def test_export_and_delete_my_account(self):
        learner = self._person("learner@example.com")
        self.store.create_session(learner, "coach", "en", "llm", "CONTRACT", {"context": [{"role": "coach", "content": "Hi"}]})
        client = self._sign_in("learner@example.com")

        export = client.get("/account/export")
        self.assertEqual(export.json()["sessions"][0]["transcript"][0]["content"], "Hi")

        client.post("/account/delete", data={"csrf": self._csrf(client), "confirm": "DELETE"})
        self.assertIsNone(self.store.get_user(learner))
        self.assertEqual(self.store.list_sessions(learner), [])

    def test_a_member_can_delete_one_session_and_nobody_else_can(self):
        learner = self._person("learner@example.com")
        self._person("mentor@example.com", role="trainer")
        self.store.update_user(learner, trainer_id=self.store.get_user_by_email("mentor@example.com")["id"])
        keep = self.store.create_session(learner, "coach", "en", "llm", "CLOSING", {"context": [{"role": "coach", "content": "Hi"}]})
        gone = self.store.create_session(learner, "coachee", "en", "llm", "CLOSING", {"context": [{"role": "coachee", "content": "Hi"}]})
        self.store.save_session_result(gone, learner, "coachee", score=70)
        self.store.rate_session(gone, learner, "coachee", 4)
        client = self._sign_in("learner@example.com")

        page = client.get("/account?lang=en").text
        self.assertIn(f'action="/account/sessions/{gone}/delete"', page)
        self.assertIn('data-confirm="Delete this conversation for good?', page)

        mentor = self._sign_in("mentor@example.com")  # can read practice sessions, but they aren't theirs to delete
        self.assertEqual(mentor.post(f"/account/sessions/{gone}/delete", data={"csrf": self._csrf(mentor)}).status_code, 403)
        client.post(f"/account/sessions/{gone}/delete", data={"csrf": "not-the-token"})
        self.assertIsNotNone(self.store.get_session(gone))

        page = client.post(f"/account/sessions/{gone}/delete", data={"csrf": self._csrf(client)})
        self.assertIn("The conversation was deleted.", page.text)
        self.assertIsNone(self.store.get_session(gone))
        self.assertEqual(self.store.session_results(learner, "coachee"), [])
        self.assertIsNone(self.store.session_rating(gone))
        self.assertIsNotNone(self.store.get_session(keep))
        self.assertIn("session_deleted", [entry["action"] for entry in self.store.audit_entries()])

    def test_public_icons_and_manifest_need_no_sign_in(self):
        self.assertEqual(self.client.get("/icons/studio-icon-180.png").status_code, 200)
        self.assertEqual(self.client.get("/site.webmanifest").status_code, 200)
        self.assertEqual(self.client.get("/privacy").status_code, 200)
        self.assertEqual(self.client.get("/healthz").json(), {"ok": True})

    def test_ping_answers_without_waking_the_database(self):
        # An uptime monitor on a database-checking URL keeps Neon's free database awake and uses up its monthly hours.
        with patch.object(self.store, "has_users", side_effect=AssertionError("the database was queried")), \
                patch.object(self.store.engine, "connect", side_effect=AssertionError("the database was queried")):
            self.assertEqual(self.client.get("/ping").json(), {"ok": True})


class TestSessionTakeaways(unittest.TestCase):
    """The coach remembers the goal, and finished sessions leave something to keep: an action card or a score."""

    def test_conversation_window_keeps_the_start_and_the_latest_messages(self):
        from coaching_core import _conversation_window

        context = [{"role": "client", "content": str(i)} for i in range(40)]
        window = _conversation_window(context)

        self.assertEqual([m["content"] for m in window[:6]], ["0", "1", "2", "3", "4", "5"])
        self.assertEqual(window[-1]["content"], "39")
        self.assertEqual(len(window), 22)
        self.assertEqual(_conversation_window(context[:10]), context[:10])

    def test_coach_still_sees_the_agreed_goal_late_in_a_long_session(self):
        from coaching_core import CoachingSubPhase

        calls = []
        agent = CoachAgent(mode="llm", language="en")
        agent.context = [{"role": "coach", "content": "What would you like to focus on?"},
                         {"role": "client", "content": "My goal is to run a half marathon in May."}]
        agent.context += [{"role": "coach" if i % 2 == 0 else "client", "content": f"turn {i}"} for i in range(30)]
        agent.current_sub_phase = CoachingSubPhase.DEEPEN
        with patch("coach_agent._build_client", return_value=_fake_llm_client(["What will help most?"], calls)):
            list(agent._get_llm_response("server-key"))

        sent = " ".join(message["content"] for message in calls[0]["messages"])
        self.assertIn("half marathon", sent)
        self.assertIn("turn 29", sent)

    def test_action_card_reads_the_plan_and_skips_sessions_without_one(self):
        calls = []
        agent = CoachAgent(mode="llm", language="en")
        agent.context = [{"role": "client", "content": "I'll call my sister on Sunday."}]
        replies = [json.dumps({"goal": "Reconnect with my sister", "next_step": "Call her", "by_when": "Sunday", "support": ""}),
                   json.dumps({"goal": "", "next_step": ""})]
        with patch("coach_agent._build_client", return_value=_fake_llm_client(replies, calls)):
            card = agent.action_card("server-key")
            empty = agent.action_card("server-key")

        self.assertEqual(card, {"goal": "Reconnect with my sister", "next_step": "Call her", "by_when": "Sunday", "support": ""})
        self.assertIsNone(empty)
        self.assertIn("never invent", calls[0]["messages"][0]["content"])

    def test_opening_follows_up_on_the_last_plan(self):
        calls = []
        agent = CoachAgent(mode="llm", language="en")
        agent.last_card = {"goal": "Sleep better", "next_step": "Phone out of the bedroom", "by_when": "tonight", "support": ""}
        with patch("coach_agent._build_client", return_value=_fake_llm_client(["How did it go?"], calls)):
            agent._get_llm_opening_response("server-key")

        prompt = calls[0]["messages"][0]["content"]
        self.assertIn("FOLLOW-UP", prompt)
        self.assertIn("Phone out of the bedroom", prompt)

    def test_skipping_to_the_end_closes_with_a_real_summary(self):
        calls = []
        agent = CoachAgent(mode="llm", language="en")
        agent.context = [{"role": "coach", "content": "What matters here?"}, {"role": "client", "content": "Time with my family."}]
        agent.current_state = CoachingState.VALUE
        agent.force_next_state()
        with patch("coach_agent._build_client", return_value=_fake_llm_client(["You found what matters most."], calls)):
            closing = agent.get_stage_prompt("server-key")

        self.assertEqual(closing, "You found what matters most.")

    def test_ending_an_ai_coach_session_adds_the_action_card_after_the_closing(self):
        from coaching_core import CoachingSubPhase

        web_app, store, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        agent = session["agent"]
        agent.mode = "llm"
        agent.current_state = CoachingState.VALUE
        agent.current_sub_phase = CoachingSubPhase.DEEPEN
        agent.turns_in_current_stage = 3
        card = {"goal": "Learn Spanish", "next_step": "Book the course", "by_when": "Friday", "support": "My partner"}
        fake = _fake_llm_client(["[[END]] You have a clear plan.", json.dumps(card)], [])
        with patch.object(web_app, "_safe_key", return_value="server-key"), patch("coach_agent._build_client", return_value=fake), \
                patch.object(web_app, "_learn_from_session"):
            outputs = list(web_app.respond("I'll book it on Friday, thanks!", [], session, "coach", "AI", "English", request))

        closing_only, final = outputs[-2][1], outputs[-1][1]
        self.assertEqual(closing_only[-1]["content"], "You have a clear plan.")
        self.assertEqual(final[-2]["content"], "You have a clear plan.")
        self.assertIn("Next step: Book the course", final[-1]["content"])
        self.assertIn("Saved on your Account page.", final[-1]["content"])
        self.assertEqual(store.session_results(user["id"], "coach")[0]["card"], card)
        self.assertEqual(store.get_session(session["id"])["status"], "completed")

    def test_finished_practice_session_keeps_its_score(self):
        web_app, store, user, _ = _signed_in()
        session = web_app._open_session(user, "coachee", "template", "en")
        session["agent"].context.append({"role": "coachee", "content": "Session Result: solid.\nScore: 74/100\nWhat worked: ..."})

        session["agent"].session_complete = True
        web_app._save(session)

        self.assertEqual(store.session_results(user["id"], "coachee")[0]["score"], 74)
        self.assertEqual(web_app.review_score("会话结果：完整。\n最后得分：68/100"), 68)
        self.assertIsNone(web_app.review_score("No score here."))

    def test_new_ai_coach_session_follows_up_only_on_a_plan_from_earlier(self):
        import datetime as dt

        web_app, store, user, _ = _signed_in()
        earlier = store.create_session(user["id"], "coach", "en", "llm", "CLOSING", {"context": []})
        store.save_session_result(earlier, user["id"], "coach", card={"goal": "Sleep better", "next_step": "No phone in bed"})

        straight_after = web_app._open_session(user, "coach", "llm", "en", expected=(earlier, store.get_session(earlier)["updated_at"]))
        with store.engine.begin() as conn:
            conn.execute(db.session_results.update().values(created_at=db.utcnow() - dt.timedelta(days=1)))
        next_day = web_app._open_session(user, "coach", "llm", "en",
                                        expected=(straight_after["id"], straight_after["version"]))

        self.assertIsNone(straight_after["agent"].last_card)
        self.assertEqual(next_day["agent"].last_card["next_step"], "No phone in bed")

    def test_mode_card_shows_sessions_left_or_used_today(self):
        web_app, store, user, _ = _signed_in()
        admin_id = store.create_user("boss@example.com", "Boss", "x", role="admin")

        member = web_app._mode_context_html(web_app._open_session(user, "coach", "template", "en"))
        admin = web_app._mode_context_html(web_app._open_session(store.get_user(admin_id), "coachee", "template", "zh"))

        self.assertIn("3 of 3 left today", member)
        self.assertIn("今日已用 0 次", admin)

    def test_switching_language_translates_the_ai_opening_question(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        agent = session["agent"]
        agent.mode = "llm"
        agent.context = [{"role": "coach", "content": "What would you most like to focus on today?"}]
        reply = json.dumps({"translations": ["今天你最想聚焦在什么上？"]}, ensure_ascii=False)
        with patch.object(web_app, "_safe_key", return_value="server-key"), \
                patch("coaching_core._build_client", return_value=_fake_llm_client([reply], [])):
            outputs = web_app.switch_lang("中文", session, "coach", "AI", request=request)

        self.assertEqual(agent.language, "zh")
        self.assertEqual(agent.context[0]["content"], "今天你最想聚焦在什么上？")
        self.assertEqual(outputs[0][0]["content"], "今天你最想聚焦在什么上？")

    def test_switching_language_keeps_the_chosen_voice(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "zh")
        voice = web_app.switch_lang("English", session, "coach", "Template", "男声", request=request)[15]
        self.assertEqual((voice["choices"], voice["value"]), (["Female", "Male"], "Male"))
        voice = web_app.switch_lang("中文", session, "coach", "Template", "Female", request=request)[15]
        self.assertEqual(voice["value"], "女声")

    def test_busy_ai_service_is_tried_again_but_a_timeout_is_not(self):
        import httpx
        import openai
        from coaching_core import _create_with_busy_retry

        request = httpx.Request("POST", "https://example.test/v1/chat/completions")
        calls = []

        def busy_twice(**kwargs):
            calls.append(kwargs)
            if len(calls) < 3:
                raise openai.RateLimitError("busy", response=httpx.Response(429, request=request), body=None)
            return "reply"

        def timeout(**kwargs):
            raise openai.APITimeoutError(request=request)

        with patch("coaching_core.time.sleep") as sleep, self.assertLogs("coaching_studio", level="WARNING"):
            self.assertEqual(_create_with_busy_retry(busy_twice, model="m"), "reply")
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.5, 3.0])
        with patch("coaching_core.time.sleep") as sleep, self.assertRaises(openai.APITimeoutError):
            _create_with_busy_retry(timeout)
        sleep.assert_not_called()

    def test_failed_translation_changes_nothing(self):
        agent = CoachAgent(mode="llm", language="en")
        agent.context = [{"role": "coach", "content": "What would you most like to focus on today?"}]
        with patch("coach_agent._translate_texts", side_effect=RuntimeError("busy")), self.assertLogs("coaching_studio", level="WARNING"):
            self.assertFalse(agent.translate_history("zh", api_key="server-key"))

        self.assertEqual(agent.language, "en")
        self.assertEqual(agent.context[0]["content"], "What would you most like to focus on today?")

    def test_when_translation_fails_the_page_keeps_the_conversations_language(self):
        import gradio as gr
        import coachee_agent

        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coachee", "template", "zh")
        agent = session["agent"]
        agent.mode = "llm"
        agent.context = [{"role": "coachee", "content": "我最近感到很迷茫。"}]
        web_app._save(session)
        english_phone = gr.Request(username=str(user["id"]), headers={"accept-language": "en-US"}, cookies={"studio_lang": "en"})

        with patch.object(web_app, "_safe_key", return_value="server-key"), \
                patch("coachee_agent._translate_texts", side_effect=RuntimeError("busy")), \
                patch.object(coachee_agent.logger, "warning"), patch.object(web_app.gr, "Warning") as warning:
            switched = web_app.switch_lang("English", session, "coachee", "AI", request=request)
            reopened = web_app.initial_load(None, "coachee", "AI", "English", english_phone)

        self.assertEqual(agent.language, "zh")
        self.assertEqual(agent.context[0]["content"], "我最近感到很迷茫。")
        self.assertEqual(switched[12]["value"], "中文")
        self.assertEqual(reopened[-1]["agent"].language, "zh")
        self.assertEqual(reopened[12]["value"], "中文")
        self.assertIn("stays in Chinese", warning.call_args_list[0].args[0])

    def test_template_session_keeps_its_mode_without_repeating_the_allowance_warning(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")

        with patch.object(web_app.gr, "Warning") as warning:
            list(web_app.respond("I want more focus.", [], session, "coach", "AI", "English", request))

        self.assertEqual(session["agent"].mode, "template")
        warning.assert_not_called()

    def test_members_see_no_mode_switch_and_read_aloud_starts_off(self):
        import web_app

        components = {getattr(block, "label", None): block for block in web_app.demo.blocks.values()}
        self.assertFalse(components["模式"].visible)
        self.assertFalse(components["自动朗读回复"].value)

    def test_welcome_card_shows_only_on_the_first_visit(self):
        web_app, _, _, request = _signed_in()

        first = web_app.initial_load(None, "coach", "Template", "English", request)
        again = web_app.initial_load(None, "coach", "Template", "English", request)

        self.assertIn("AI Insights", first[14])
        self.assertIn("welcome-layer", first[15])
        self.assertIn("data-welcome-close", first[15])
        self.assertIn('href="/help"', first[15])
        self.assertEqual(again[15], "")


class TestSessionRating(unittest.TestCase):
    def test_a_finished_session_asks_how_useful_it_was_and_keeps_the_answer(self):
        web_app, store, user, request = _signed_in()
        session = web_app._open_session(user, "coachee", "template", "en")
        self.assertFalse(web_app._rating_updates(session)[0]["visible"])
        session["agent"].session_complete = True

        card, prompt, buttons = web_app._rating_updates(session)
        self.assertTrue(card["visible"] and buttons["visible"])
        self.assertIn("How useful was this session?", prompt["value"])
        *updates, session = web_app.rate_session("4", session, request)
        *_, session = web_app.rate_session("5", session, request)  # a second tap changes it

        self.assertEqual(store.session_rating(session["id"]), 5)
        self.assertIn("your rating is saved", updates[1]["value"])
        self.assertFalse(updates[2]["visible"])
        self.assertEqual(store.ratings_since(db.utcnow().replace(year=2000)), {"coachee": (1, 5.0)})
        self.assertEqual(store.export_user(user["id"])["sessions"][0]["usefulness_rating"], 5)

    def test_admin_page_shows_ratings_without_opening_sessions(self):
        from fastapi.testclient import TestClient
        import web_app

        app = web_app.create_app(store=db.Store("sqlite://"), env={"STUDIO_SECRET_KEY": "test-secret"})
        store = web_app.get_store()
        admin = store.create_user("owner@example.com", "Owner", accounts.hash_password("a-long-password"), role="admin")
        session_id = store.create_session(admin, "coach", "en", "llm", "CLOSING", {"context": []})
        store.rate_session(session_id, admin, "coach", 4)
        client = TestClient(app)
        client.post("/login", data={"email": "owner@example.com", "password": "a-long-password"})

        page = client.get("/admin?lang=en").text

        self.assertIn("How useful people found their sessions in the last 30 days: AI Coach 4.0/5 (1 rated)", page)
        self.assertIn("Useful 4/5", page)

    def test_only_the_owner_rates_and_only_once_the_session_has_ended(self):
        import gradio as gr

        web_app, store, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "zh")
        web_app.rate_session("5", session, request)
        self.assertIsNone(store.session_rating(session["id"]))

        session["agent"].session_complete = True
        self.assertIn("这次会话对你有多大帮助", web_app._rating_updates(session)[1]["value"])
        other = store.create_user("bo@example.com", "Bo", accounts.hash_password("a-long-password"))
        web_app.rate_session("5", session, gr.Request(username=str(other)))
        web_app.rate_session("9", session, request)
        self.assertIsNone(store.session_rating(session["id"]))


class TestStructuredReplies(unittest.TestCase):
    """Requests that must come back as JSON survive the slips real models make."""

    def test_bracket_repair_fixes_the_slips_seen_from_deepseek(self):
        from coaching_core import _repair_json_brackets

        missing = '{"contract": {"success": ["a", "b"}, "experience": {"reality": ["c"]}}'
        swapped = '{"contract": {"success": ["a", "b"}}, "experience": {"reality": ["c"]}}'
        for raw in (missing, swapped):
            data = json.loads(_repair_json_brackets(raw))
            self.assertEqual(data["contract"]["success"], ["a", "b"])
            self.assertEqual(data["experience"]["reality"], ["c"])
        self.assertEqual(json.loads(_repair_json_brackets('{"a": "x}y", "b": [1, 2]}')), {"a": "x}y", "b": [1, 2]})
        self.assertEqual(json.loads(_repair_json_brackets('{"a": ["x"')), {"a": ["x"]})

    def test_json_completion_uses_json_mode_and_asks_again_after_unusable_output(self):
        from coaching_core import _json_completion

        calls = []
        client = _fake_llm_client(["not json at all", '{"ok": true}'], calls)

        data = _json_completion(client, messages=[{"role": "system", "content": "Reply in JSON."}], max_tokens=10, temperature=0.9)

        self.assertEqual(data, {"ok": True})
        self.assertEqual(calls[0]["response_format"], {"type": "json_object"})
        self.assertEqual((calls[0]["temperature"], calls[1]["temperature"]), (0.9, 0.3))

    def test_practice_session_opens_with_a_built_in_case_when_the_ai_case_is_unusable(self):
        import coachee_agent

        agent = CoacheeAgent(mode="llm", language="zh")
        built_in = agent.scenario
        with patch("coachee_agent._build_client", return_value=_fake_llm_client(["{broken", "{still broken"], [])), \
                patch.object(coachee_agent.logger, "warning"):
            opening = agent.get_stage_prompt("server-key")

        self.assertEqual(opening, built_in.intro["zh"])

    def test_practice_case_sections_nested_by_mistake_are_lifted_back(self):
        from coachee_data import _scenario_bundle_from_single_language

        pair = ["I want this.", "I really do."]
        data = {"intro": "Hi.", "contract": {"goal": pair, "experience": {"reality": pair}},
                "action": {"possibility": pair}, "value": {"commitment": pair}, "closing": {"reflection": pair}}

        bundle = _scenario_bundle_from_single_language(data)

        self.assertEqual(bundle.experience["reality"]["en"], pair)
        self.assertNotIn("experience", bundle.contract)

    def test_practice_review_scores_each_stage(self):
        calls = []
        agent = CoacheeAgent(mode="llm", language="en")
        agent.context = [{"role": "coach", "content": "What would you like from today?"}]
        with patch("coachee_agent._build_client", return_value=_fake_llm_client(["Score: 40/100"], calls)):
            agent._build_llm_final_review("server-key")

        prompt = calls[0]["messages"][0]["content"]
        self.assertIn("Stage scores: Contract <n>/20", prompt)
        self.assertIn("A stage the coach skipped earns 0", prompt)
        self.assertIn("The coach spoke 1 times in this session, so the total must not exceed 8.", prompt)

    def test_a_practice_ended_at_the_limit_is_reviewed_whole_and_says_why_it_stopped(self):
        calls = []
        agent = CoacheeAgent(mode="llm", language="en")
        agent.current_state = CoachingState.ACTION
        agent.context = _conversation(agent, 100)
        with patch("coachee_agent._build_client", return_value=_fake_llm_client(["Score: 40/100"], calls)):
            review = agent.end_at_limit(100, "server-key")

        prompt = calls[0]["messages"][0]["content"]
        self.assertIn("used all 100 messages a conversation allows, during the Possibilities stage", prompt)
        self.assertIn("Coach: Message 50", prompt)  # the middle of a long practice is reviewed too
        self.assertTrue(agent.session_complete)
        self.assertEqual(agent.context[-1]["content"], review)

    def test_practice_scores_are_held_to_the_ceiling_for_short_sessions(self):
        agent = CoacheeAgent(mode="llm", language="zh")
        agent.context = [{"role": "coach", "content": f"问题 {i}"} for i in range(5)]
        with patch("coachee_agent._build_client", return_value=_fake_llm_client(["会话结果：不错。\n最后得分：70/100"], [])):
            review = agent._build_llm_final_review("server-key")

        self.assertIn("最后得分：40/100", review)
        self.assertEqual(agent._apply_score_ceiling("Score: 30/100"), "Score: 30/100")
        capped = agent._apply_score_ceiling("分阶段得分：目标合同 18/20 · 现实探索 12/20 · 可能方案 14/20 · 行动承诺 18/20 · 结束回顾 16/20\n最后得分：78/100")
        stage_scores = [int(n) for n in re.findall(r"(\d+)/20", capped)]
        self.assertEqual(sum(stage_scores), 40)
        self.assertIn("最后得分：40/100", capped)

    def test_a_stray_bullet_before_a_one_paragraph_reply_is_removed(self):
        self.assertEqual(_clean_response_language("- You want evenings back. What matters most?", "en"),
                         "You want evenings back. What matters most?")
        self.assertEqual(_clean_response_language("- one\n- two", "en"), "- one\n- two")

    def test_whole_reply_quote_marks_are_removed(self):
        self.assertEqual(_clean_response_language('"How did it go?"', "en"), "How did it go?")
        self.assertEqual(_clean_response_language("“上次的计划进展如何？”", "zh"), "上次的计划进展如何？")
        self.assertEqual(_clean_response_language('"Yes" or "no" both work.', "en"), '"Yes" or "no" both work.')
        self.assertEqual(_clean_response_language("'Tis the season, isn't it'", "en"), "'Tis the season, isn't it'")

    def test_coach_can_close_between_stage_decisions(self):
        calls = []
        agent = CoachAgent(mode="llm", language="en")
        agent.context = [{"role": "coach", "content": "What would you like to focus on?"}]
        with patch("coach_agent._build_client", return_value=_fake_llm_client(["[[END]] Take care, and well done today."], calls)):
            reply = agent.generate_response("That's all for today, I need to go.", "server-key")

        self.assertEqual(reply, "Take care, and well done today.")
        self.assertTrue(agent.is_session_ended())
        self.assertIn("A thank-you on its own is not a request to finish", calls[0]["messages"][0]["content"])

    def test_practice_client_closes_when_the_coach_says_goodbye_between_stage_decisions(self):
        agent = CoacheeAgent(mode="llm", language="en")
        agent._llm_scenario_ready = True
        agent.context = [{"role": "coachee", "content": agent.scenario.intro["en"]}]
        with patch("coachee_agent._build_client", return_value=_fake_llm_client(["Thanks!", "Score: 6/100"], [])), \
                _coach_labels("END"):
            reply = agent.generate_response("Good luck, that's all for today. Goodbye!", "server-key")

        self.assertTrue(agent.is_session_ended())
        self.assertEqual(reply, "Score: 6/100")


class TestLanguageAndLocalisation(unittest.TestCase):
    def test_language_preference_cookie_then_browser(self):
        import account_pages

        self.assertEqual(account_pages.preferred_language({"studio_lang": "zh"}, {"accept-language": "en-US"}), "zh")
        self.assertEqual(account_pages.preferred_language({}, {"accept-language": "zh-CN,zh;q=0.9"}), "zh")
        self.assertEqual(account_pages.preferred_language({}, {"accept-language": "en-GB,zh;q=0.5"}), "en")
        self.assertEqual(account_pages.preferred_language({}, {}, fallback="zh"), "zh")

    def test_first_session_opens_in_the_browsers_language(self):
        import gradio as gr

        web_app, _, user, _ = _signed_in()
        english_browser = gr.Request(username=str(user["id"]), headers={"accept-language": "en-US,en;q=0.9"}, cookies={})

        outputs = web_app.initial_load(None, "coach", "Template", "中文", english_browser)

        self.assertEqual(outputs[-1]["agent"].language, "en")
        self.assertEqual(outputs[12]["value"], "English")

    def test_reopened_session_keeps_its_language_and_version(self):
        import gradio as gr

        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        chinese_choice = gr.Request(username=str(user["id"]), headers={"accept-language": "en-US"}, cookies={"studio_lang": "zh"})

        outputs = web_app.initial_load(None, "coach", "AI", "English", chinese_choice)

        self.assertEqual(outputs[-1]["id"], session["id"])
        self.assertEqual(outputs[-1]["agent"].language, "en")
        self.assertEqual(outputs[-1]["version"], session["version"])
        self.assertEqual(outputs[12]["value"], "English")
        self.assertIn("Coaching Practice Studio", outputs[2])

    def test_switching_language_in_the_app_is_remembered_for_the_pages(self):
        import web_app

        self.assertIn("studio_lang=", web_app.remember_lang_js)
        language_events = [fn for fn in web_app.demo.fns.values() if fn.fn is None and fn.js == web_app.remember_lang_js]
        self.assertEqual(len(language_events), 1)

    def test_every_page_string_exists_in_both_languages(self):
        import account_pages

        self.assertEqual(set(account_pages.T["en"]), set(account_pages.T["zh"]))
        self.assertEqual(set(account_pages.T["en"]["audit_actions"]), set(account_pages.T["zh"]["audit_actions"]))
        self.assertEqual(set(account_pages.ROLE_LABELS["en"]), set(account_pages.ROLE_LABELS["zh"]))

    def test_every_app_string_exists_in_both_languages(self):
        from web_assets import UI

        self.assertEqual(set(UI["en"]), set(UI["zh"]))

    def test_human_roles_do_not_reuse_the_ai_coachee_wording(self):
        import account_pages
        from web_assets import UI

        for lang in ("en", "zh"):
            for label in account_pages.ROLE_LABELS[lang].values():
                self.assertNotIn(label, UI[lang]["coachee_module"])
                self.assertNotIn(label.lower(), ("trainee", "learner", "学员"))


class TestSelfServiceAndAdminControls(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        import web_app

        self.sent = []
        self.store = db.Store("sqlite://")
        with patch.object(web_app.mailer, "smtp_sender", return_value=lambda *args: self.sent.append(args)):
            app = web_app.create_app(store=self.store, env={"STUDIO_SECRET_KEY": "test-secret", "SMTP_HOST": "smtp.example.com"})
        self.client = TestClient(app)
        self.secret = "test-secret"

    def _person(self, email, role="user"):
        return self.store.create_user(email, email.split("@")[0].title(), accounts.hash_password("a-long-password"), role=role)

    def _wait_for_mail(self, count):
        deadline = time.time() + 5
        while len(self.sent) < count and time.time() < deadline:
            time.sleep(0.02)

    def test_forgot_password_emails_a_working_link_without_revealing_accounts(self):
        self._person("amy@example.com")

        known = self.client.post("/forgot", data={"email": "amy@example.com"}, headers={"accept-language": "zh-CN"})
        unknown = self.client.post("/forgot", data={"email": "nobody@example.com"}, headers={"accept-language": "zh-CN"})
        self._wait_for_mail(1)

        self.assertEqual(known.status_code, unknown.status_code)
        self.assertIn("重置链接已经发出", known.text)
        self.assertEqual(len(self.sent), 1)
        to, subject, body = self.sent[0]
        self.assertEqual(to, "amy@example.com")
        self.assertIn("重置", subject)
        token = body.split("/reset/")[1].split()[0]
        reset = self.client.post(f"/reset/{token}", data={"password": "brand-new-password", "confirm": "brand-new-password"}, follow_redirects=False)
        self.assertEqual(reset.status_code, 303)

    def test_login_page_offers_reset_only_when_email_is_configured(self):
        import web_app
        from fastapi.testclient import TestClient

        self._person("owner@example.com", role="admin")
        self.assertIn('href="/forgot"', self.client.get("/login").text)

        without_email = TestClient(web_app.create_app(store=self.store, env={"STUDIO_SECRET_KEY": "test-secret"}))
        self.assertNotIn('href="/forgot"', without_email.get("/login").text)
        self.assertEqual(without_email.get("/forgot", follow_redirects=False).status_code, 303)

    def test_admin_edits_allowances_and_reads_translated_audit_log_with_local_times(self):
        import quota

        self._person("owner@example.com", role="admin")
        self.client.post("/login", data={"email": "owner@example.com", "password": "a-long-password"})
        csrf = accounts.csrf_token(self.client.cookies.get(accounts.SESSION_COOKIE), self.secret)

        page = self.client.post("/admin/allowances?lang=zh", data={"csrf": csrf, "role": "user", "coach": "4", "coachee": "", "tokens": "500000"})

        self.assertEqual(quota.role_limits(self.store)["user"], {"coach": 4, "coachee": None, "tokens": 500_000})
        self.assertIn("修改每日额度", page.text)
        self.assertNotIn(">limits_updated<", page.text)
        self.assertIn("<time datetime=", page.text)

    def test_admin_page_shows_failed_ai_requests(self):
        # When the AI account runs out of credit every request fails; the owner should hear it from the Admin page.
        import datetime as dt
        import coaching_core
        import httpx
        import openai
        import web_app

        self._person("owner@example.com", role="admin")
        self.client.post("/login", data={"email": "owner@example.com", "password": "a-long-password"})
        self.assertIn("No AI errors in the last 24 hours.", self.client.get("/admin?lang=en").text)

        web_app.set_store(self.store)
        web_app._last_failure_logged = None
        refused = openai.APIStatusError("Error code: 402", response=httpx.Response(
            402, request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")),
            body={"error": {"message": "Insufficient credits", "code": 402}})

        def create(**kwargs):
            raise refused

        for _ in range(3):  # a failing service fails every request; one note a minute is enough
            with self.assertRaises(openai.APIStatusError):
                coaching_core._create_with_busy_retry(create, model="m", messages=[])

        failures = self.store.audit_since("ai_error", db.utcnow() - dt.timedelta(hours=1))
        self.assertEqual([entry["detail"] for entry in failures], ["402: Insufficient credits"])
        page = self.client.get("/admin?lang=zh").text
        self.assertIn("过去 24 小时有 AI 请求失败（1 次", page)
        self.assertIn("402: Insufficient credits", page)
        self.assertIn("AI 请求失败", page)  # the audit log names it too

    def test_admin_page_shows_the_ai_credit_and_warns_when_it_runs_low(self):
        from fastapi.testclient import TestClient
        import web_app

        self._person("owner@example.com", role="admin")
        for credit, expected in ((3.78, "Credit left on the AI account (OpenRouter): $3.78."),
                                 (1.25, "AI credit is running low: $1.25 left.")):
            with patch.object(web_app, "_ai_credit_left", return_value=credit):
                client = TestClient(web_app.create_app(store=self.store, env={"STUDIO_SECRET_KEY": self.secret}))
            client.post("/login", data={"email": "owner@example.com", "password": "a-long-password"})
            self.assertIn(expected, client.get("/admin?lang=en").text)

    def test_credit_is_read_only_for_openrouter(self):
        import coaching_core

        with patch("urllib.request.urlopen") as urlopen:
            self.assertIsNone(coaching_core.openrouter_credit_left("sk-deepseek", "https://api.deepseek.com"))
            self.assertIsNone(coaching_core.openrouter_credit_left("", "https://openrouter.ai/api/v1"))
        urlopen.assert_not_called()

    def test_account_page_shows_each_modules_allowance(self):
        self._person("amy@example.com")
        self.client.post("/login", data={"email": "amy@example.com", "password": "a-long-password"})

        page = self.client.get("/account?lang=en").text

        self.assertIn("AI Coach: 3 of 3 AI sessions left today", page)
        self.assertIn("Coachee Lab: 5 of 5 AI sessions left today", page)

    def test_local_runs_keep_their_signing_key_between_restarts(self):
        import web_app

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(web_app, "LOCAL_SECRET_FILE", Path(folder) / ".studio_secret"):
                first = web_app._secret_key({})
                second = web_app._secret_key({})
                mode = (Path(folder) / ".studio_secret").stat().st_mode & 0o777

        self.assertEqual(first, second)
        self.assertEqual(mode, 0o600)


class TestProviderAndRegionSupport(unittest.TestCase):
    def test_deepseek_gets_thinking_switched_off_on_every_call(self):
        import coaching_core

        calls = []
        raw = _fake_llm_client(["Hello", "Hi there"], calls)
        with patch.dict(os.environ, {"OPENAI_EXTRA_BODY": ""}):
            with patch.object(coaching_core, "_shared_client", return_value=raw):
                client = coaching_core._build_client("key", "https://api.deepseek.com")
                client.chat.completions.create(model="deepseek-flash", messages=[])
                list(coaching_core._stream_text(coaching_core._build_client("key", "https://api.deepseek.com", on_usage=lambda *a: None),
                                                model="deepseek-flash", messages=[]))

        self.assertEqual(calls[0]["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(calls[1]["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(calls[1]["stream_options"], {"include_usage": True})

    def test_extra_request_fields_can_be_set_for_any_provider(self):
        import coaching_core

        with patch.dict(os.environ, {"OPENAI_EXTRA_BODY": '{"enable_thinking": false}'}):
            self.assertEqual(coaching_core._provider_extra_body("https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
                             {"enable_thinking": False})
        with patch.dict(os.environ, {"OPENAI_EXTRA_BODY": ""}):
            self.assertEqual(coaching_core._provider_extra_body("https://api.example.com/v1"), {})

    def test_openrouter_only_uses_hosts_that_dont_collect_the_conversation(self):
        # People bring their real lives to the AI Coach; OpenRouter may otherwise route to a host that keeps prompts.
        import coaching_core

        with patch.dict(os.environ, {"OPENAI_EXTRA_BODY": ""}):
            self.assertEqual(coaching_core._provider_extra_body("https://openrouter.ai/api/v1"),
                             {"provider": {"data_collection": "deny"}})
            calls = []
            raw = type("Raw", (), {"chat": type("Chat", (), {"completions": type("C", (), {
                "create": lambda self, **kwargs: calls.append(kwargs) or "done"})()})()})()
            with patch.object(coaching_core, "_shared_client", return_value=raw):
                coaching_core._build_client("sk-or-v1-test").chat.completions.create(model="m", messages=[])
            self.assertEqual(calls[0]["extra_body"], {"provider": {"data_collection": "deny"}})
        # The owner can choose the stricter zero-retention routing without a code change.
        with patch.dict(os.environ, {"OPENAI_EXTRA_BODY": '{"provider": {"zdr": true}}'}):
            self.assertEqual(coaching_core._provider_extra_body("https://openrouter.ai/api/v1"), {"provider": {"zdr": True}})

    def test_no_fonts_are_downloaded_from_google(self):
        import gradio as gr
        import web_app

        fonts = web_app.clean_indigo_theme._font + web_app.clean_indigo_theme._font_mono
        self.assertFalse(any(isinstance(font, gr.themes.GoogleFont) for font in fonts))
        self.assertNotIn("googleapis", web_app.css + web_app.head)

    def test_browser_scripts_are_valid_javascript(self):
        import shutil
        import subprocess
        import web_assets

        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        with tempfile.TemporaryDirectory() as folder:
            scripts = {name: "(" + getattr(web_assets, name) + ")" for name in ("force_light_js", "tts_js", "voice_note_js", "scroll_js",
                                                                              "remember_lang_js")}
            # An HTML block's js_on_load is a function body that receives the block as `element`.
            scripts["welcome_js"] = "(function (element) {" + web_assets.welcome_js + "})"
            scripts["space_status_js"] = web_assets.space_status_js  # a whole <script>, not an expression
            for name, source in scripts.items():
                script = Path(folder) / f"{name}.js"
                script.write_text(source, encoding="utf-8")
                result = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")

    def test_voice_input_explains_failures(self):
        import web_assets

        for code in ("network", "service-not-allowed", "not-allowed"):
            self.assertIn(code, web_assets.force_light_js)
        self.assertIn("showMicHint(errorEvent && errorEvent.error)", web_assets.force_light_js)

    def test_privacy_page_can_say_where_data_is_processed(self):
        from fastapi.testclient import TestClient
        import web_app

        app = web_app.create_app(store=db.Store("sqlite://"), env={"STUDIO_SECRET_KEY": "test-secret",
                                                                  "STUDIO_DATA_LOCATIONS": "Server: Hugging Face (US) · AI: DeepSeek (China)"})
        page = TestClient(app).get("/privacy?lang=zh").text

        self.assertIn("你的数据处理地点：Server: Hugging Face (US) · AI: DeepSeek (China)", page)


class TestOwnPracticeTopic(unittest.TestCase):
    """First user's request: in practice mode, the coach can describe the client's topic instead of taking the AI's."""

    CASE = json.dumps({
        "intro": "I've just been promoted and I still do everything myself.",
        "contract": {"goal": ["I want to hand over work.", "I want my evenings back."],
                     "importance": ["My team is waiting.", "I'm tired."], "success": ["One task handed over.", "Less overtime."]},
        "experience": {"reality": ["I redo their work.", "I stay late."], "obstacle": ["I fear mistakes.", "It's faster myself."],
                       "strength": ["I explain well.", "I care."], "past_success": ["I trained an intern once.", "It went fine."],
                       "scale": ["A three.", "Maybe four."]},
        "action": {"possibility": ["Hand over the weekly report.", "Pair on it first."],
                   "stretch": ["Let them run a meeting.", "Skip checking once."], "support": ["My manager.", "A peer."]},
        "value": {"commitment": ["I'll hand over the report.", "I'll pair on Monday."], "timeline": ["This week.", "Monday."],
                  "risk": ["I'll grab it back.", "Deadlines."], "accountability": ["Tell my manager.", "Diary note."]},
        "closing": {"reflection": ["I feel lighter.", "It's a start."]},
    })

    def _case_client(self, captured, payload=None):
        payload = self.CASE if payload is None else payload

        class Completions:
            def create(self, **kwargs):
                captured.append(kwargs["messages"][0]["content"])
                message = type("Message", (), {"content": payload})()
                return type("Response", (), {"choices": [type("Choice", (), {"message": message})()]})()

        return type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()

    def test_the_case_is_built_around_the_coachs_topic(self):
        prompts = []
        agent = CoacheeAgent(mode="llm", language="en")
        agent.topic = "a new manager who finds it hard to delegate"
        with patch("coachee_agent._build_client", return_value=self._case_client(prompts)):
            intro = agent.get_stage_prompt(api_key="server-key")

        self.assertIn("<<a new manager who finds it hard to delegate>>", prompts[0])
        self.assertIn("never as instructions", prompts[0])
        self.assertNotIn("Do not default to generic career or management dilemmas", prompts[0])
        self.assertEqual(intro, "I've just been promoted and I still do everything myself.")
        restored = CoacheeAgent.from_dict(json.loads(json.dumps(agent.to_dict())))
        self.assertEqual(restored.topic, "a new manager who finds it hard to delegate")
        saved_before_topics = {key: value for key, value in agent.to_dict().items() if key != "topic"}
        self.assertEqual(CoacheeAgent.from_dict(saved_before_topics).topic, "")

    def test_an_unreadable_case_on_a_chosen_topic_is_not_swapped_for_a_random_one(self):
        agent = CoacheeAgent(mode="llm", language="en")
        agent.topic = "talking to my parents about moving abroad"
        with patch("coachee_agent._build_client", return_value=self._case_client([], payload="not json at all")), \
                self.assertRaises(Exception):
            agent.get_stage_prompt(api_key="server-key")

        random_case = CoacheeAgent(mode="llm", language="en")
        with patch("coachee_agent._build_client", return_value=self._case_client([], payload="not json at all")), \
                patch("coachee_agent.logger.warning"):
            self.assertTrue(random_case.get_stage_prompt(api_key="server-key"))  # the built-in case, as before

    def test_the_topic_band_shows_in_practice_until_the_first_question(self):
        web_app, store, user, request = _signed_in()
        practice = web_app._open_session(user, "coachee", "template", "en")
        practice["agent"].mode = "llm"  # the band is for AI practice; templates can't follow a topic
        self.assertTrue(web_app._topic_updates(practice)[0]["visible"])
        self.assertEqual(web_app._topic_updates(practice)[3]["value"], "Use my topic")

        practice["agent"].context.append({"role": "coach", "content": "What would you like from today?"})
        self.assertFalse(web_app._topic_updates(practice)[0]["visible"])
        coaching = web_app._open_session(user, "coach", "template", "en")
        coaching["agent"].mode = "llm"
        self.assertFalse(web_app._topic_updates(coaching)[0]["visible"])
        practice["agent"].mode = "template"
        self.assertFalse(web_app._topic_updates(practice)[0]["visible"])

        # Out of practice sessions for today: nothing to offer. The AI not answering: the band lets them try again.
        used_up = web_app._unavailable_session(user, "coachee", "en", "No more today.")
        self.assertFalse(web_app._topic_updates(used_up)[0]["visible"])
        ai_down = web_app._unavailable_session(user, "coachee", "en", "AI down.", reason="ai")
        self.assertTrue(web_app._topic_updates(ai_down)[0]["visible"])

    def test_asking_a_question_hides_the_band_while_the_reply_streams(self):
        web_app, _, user, _ = _signed_in()
        practice = web_app._open_session(user, "coachee", "template", "en")
        outputs = web_app._streaming_outputs([{"role": "user", "content": "Hi"}], practice)

        self.assertEqual(len(outputs), web_app.RESPOND_OUTPUT_COUNT)
        self.assertEqual(outputs[-1 - web_app.TOPIC_OUTPUT_COUNT], {"__type__": "update", "visible": False})
        self.assertIs(outputs[-1], practice)

    def test_use_my_topic_starts_a_new_practice_on_it(self):
        web_app, store, user, request = _signed_in()
        first = web_app._open_session(user, "coachee", "template", "en")
        prompts = []

        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}), \
                patch("coachee_agent._build_client", return_value=self._case_client(prompts)):
            outputs = web_app.start_with_topic("  a new manager who finds it hard to delegate ", "English", "AI", first, request)

        session = outputs[-1]
        self.assertEqual(len(outputs), web_app.NEW_SESSION_OUTPUT_COUNT)
        self.assertEqual(session["module"], "coachee")
        self.assertEqual(session["agent"].topic, "a new manager who finds it hard to delegate")
        self.assertIn("<<a new manager who finds it hard to delegate>>", prompts[0])
        self.assertEqual(outputs[0][-1]["content"], "I've just been promoted and I still do everything myself.")
        self.assertEqual(store.get_session(first["id"])["status"], "abandoned")
        self.assertEqual(json.loads(store.get_session(session["id"])["state"])["topic"], session["agent"].topic)
        # Fan's feedback: once the topic is in use, the band goes straight away rather than after the first question.
        topic_card = outputs[-1 - web_app.TOPIC_OUTPUT_COUNT]
        self.assertFalse(topic_card["visible"])

    def test_an_empty_or_long_topic_changes_nothing(self):
        import gradio as gr

        web_app, store, user, request = _signed_in()
        current = web_app._open_session(user, "coachee", "template", "en")
        for topic, message in (("   ", "Describe the topic first."), ("x" * (web_app.MAX_TOPIC_CHARS + 1), "under 300 characters")):
            with patch.object(web_app.gr, "Warning") as warning:
                outputs = web_app.start_with_topic(topic, "English", "AI", current, request)
            self.assertIn(message, warning.call_args.args[0])
            self.assertEqual(len(outputs), web_app.NEW_SESSION_OUTPUT_COUNT)
            self.assertTrue(all(output == gr.skip() for output in outputs))
        self.assertEqual(store.get_session(current["id"])["status"], "active")

    def test_a_crisis_topic_is_turned_away_with_a_reason(self):
        # A practice client in crisis would teach coaching through it instead of referring the person on.
        import safety

        web_app, store, user, request = _signed_in()
        for topic in ("a client who has been thinking about ending their life", "a manager who hurts himself when stressed",
                      "来访者最近有自杀的念头", "a suicidal client"):
            self.assertTrue(safety.crisis_topic(topic), topic)
            with patch.object(web_app.gr, "Warning") as warning:
                web_app.start_with_topic(topic, "English", "AI", None, request)
            warning.assert_called_with(web_app.UI["en"]["topic_crisis"])
        self.assertEqual(store.list_sessions(user["id"]), [])
        for topic in ("a new manager who finds it hard to delegate", "想和父母谈搬去外地工作的事", "ending a long friendship"):
            self.assertFalse(safety.crisis_topic(topic), topic)

    def test_a_plain_invitation_to_say_more_keeps_the_stage(self):
        # Fan saw the tracker jump to reality on a first "tell me more"; the labelling request took it for exploring.
        from coachee_agent import _invites_more

        for text in ("Tell me more.", "Can you tell me more about that?", "What else?", "能多说一说吗？", "还有呢？", "然后呢"):
            self.assertTrue(_invites_more(text), text)
        for text in ("What else could you do?", "还有别的办法吗？", "能说说你现在的情况吗？", "What have you tried so far?"):
            self.assertFalse(_invites_more(text), text)

        agent = CoacheeAgent(mode="llm", language="zh")
        agent.context = [{"role": "coachee", "content": "我一直不知道怎么跟父母开口。"}]
        agent._llm_scenario_ready = True
        with patch("coachee_agent._build_client", return_value=_fake_llm_client(["嗯……就是怕他们反对。"], [])), \
                patch.object(CoacheeAgent, "_label_coach_message", side_effect=AssertionError("no labelling request")):
            agent.generate_response("能多说一说吗？", api_key="server-key")
        self.assertEqual(agent.current_state, CoachingState.CONTRACT)

    def _practice_turns(self, *turns):
        """A practice session in AI mode, the coach asking each question in turn; labels are the stage of each."""
        agent = CoacheeAgent(mode="llm", language="zh")
        agent._llm_scenario_ready = True
        agent.context = [{"role": "coachee", "content": "团队中有个成员总是质疑我的决定，让我感到很无力。"}]
        questions, labels = zip(*turns)
        with patch("coachee_agent._build_client", return_value=_fake_llm_client(["嗯……"] * len(turns), [])), \
                _coach_labels(*labels):
            for question in questions:
                agent.generate_response(question, api_key="server-key")
        return agent

    def test_a_later_question_before_contracting_keeps_the_contract_stage_quietly(self):
        # Fan's choice (2026-10-16): contract first, with no pop-up judging each question (that felt "programmed");
        # the client's reaction and the review give the feedback instead.
        web_app, store, user, request = _signed_in()
        replies = [self.CASE, "可能是因为我比他年轻吧。"]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}), \
                patch("coachee_agent._build_client", return_value=_fake_llm_client(replies, [])), \
                _coach_labels("REALITY"), patch.object(web_app.gr, "Info") as info:
            session = web_app._open_session(user, "coachee", "llm", "zh")
            outputs = list(web_app.respond("为什么你会觉得他不服你？", [], session, "coachee", "AI", "中文", request))

        agent = outputs[-1][-1]["agent"]
        self.assertEqual(agent.current_state, CoachingState.CONTRACT)
        self.assertEqual(agent.held_stage, CoachingState.EXPERIENCE)
        self.assertEqual((agent.skipped_stages, agent.contract_done), (set(), False))
        info.assert_not_called()
        self.assertIn("当前阶段: 目标合同", outputs[-1][2])

    def test_the_client_opens_up_as_trust_grows_and_the_review_watches_pace(self):
        calls = []
        agent = CoacheeAgent(mode="llm", language="en")
        agent._llm_scenario_ready = True
        agent.context = [{"role": "coachee", "content": "A colleague keeps questioning my decisions."}]
        with patch("coachee_agent._build_client", return_value=_fake_llm_client(["Maybe because I'm young."], calls)), \
                _coach_labels("REALITY"):
            agent.generate_response("Why do you think he doesn't respect you?", api_key="server-key")
        client_prompt = calls[0]["messages"][0]["content"]
        self.assertIn("Trust builds gradually", client_prompt)
        self.assertIn("answer just the surface of the question", client_prompt)
        # Analysing before any contracting: this reply comes from a client who doesn't feel heard yet.
        from coachee_agent import RUSHED_NOTE
        self.assertTrue(calls[0]["messages"][-1]["content"].endswith(RUSHED_NOTE["en"]))

        for labels, questions in ((("GOAL",), ["What would you like from today?"]),
                                  (("GOAL", "REALITY"), ["What would you like from today?", "Why does he do that?"])):
            calls.clear()
            fresh = CoacheeAgent(mode="llm", language="en")
            fresh._llm_scenario_ready = True
            fresh.context = [{"role": "coachee", "content": "A colleague keeps questioning my decisions."}]
            with patch("coachee_agent._build_client", return_value=_fake_llm_client(["Mm."] * len(questions), calls)), \
                    _coach_labels(*labels):
                for question in questions:
                    fresh.generate_response(question, api_key="server-key")
            self.assertTrue(all(RUSHED_NOTE["en"] not in call["messages"][-1]["content"] for call in calls), labels)

        review_calls = []
        with patch("coachee_agent._build_client",
                   return_value=_fake_llm_client(["Session Result: ok\nScore: 10/100"], review_calls)):
            agent._build_llm_final_review("server-key")
        review_prompt = review_calls[0]["messages"][0]["content"]
        self.assertIn("Pay particular attention to pace and trust", review_prompt)
        self.assertIn("quote the coach's own words", review_prompt)

    def test_after_contracting_the_tracker_follows_the_coach(self):
        import web_app

        agent = self._practice_turns(("为什么你会觉得他不服你？", "REALITY"), ("今天这次谈话，你希望有什么收获？", "GOAL"),
                                     ("你之前试过怎么处理？", "REALITY"))
        self.assertEqual(agent.current_state, CoachingState.EXPERIENCE)
        self.assertTrue(agent.contract_done)
        self.assertIsNone(agent.held_stage)
        self.assertEqual(agent.skipped_stages, set())
        restored = CoacheeAgent.from_dict(json.loads(json.dumps(agent.to_dict())))
        self.assertTrue(restored.contract_done)

        # A jump over a later stage still shows as skipped, and the note says so.
        agent = self._practice_turns(("今天你希望有什么收获？", "GOAL"), ("你打算先做哪一步？什么时候？", "COMMITMENT"))
        self.assertEqual((agent.current_state, agent.skipped_stages), (CoachingState.VALUE, {2, 3}))
        self.assertEqual(web_app._stage_change_notice(agent, "coachee", set()),
                         "进入「行动承诺」，跳过了「现实探索」「可能方案」。虚线圆点表示跳过的阶段。")

    def test_tell_me_more_is_not_contracting(self):
        agent = self._practice_turns(("能多说一说吗？", "unused"))
        self.assertFalse(agent.contract_done)
        self.assertEqual((agent.current_state, agent.held_stage), (CoachingState.CONTRACT, None))

    def test_skip_ahead_without_contracting_shows_the_contract_as_skipped(self):
        agent = self._practice_turns(("为什么你会觉得他不服你？", "REALITY"))
        self.assertIsNone(agent.manual_advance_guard())  # a question was asked, so Skip Ahead is allowed
        agent.force_next_state()
        self.assertEqual((agent.current_state, agent.skipped_stages), (CoachingState.EXPERIENCE, {1}))
        # Agreeing the goal later counts the contract as done; the tracker stays where it is.
        with patch("coachee_agent._build_client", return_value=_fake_llm_client(["嗯……"], [])), _coach_labels("GOAL"):
            agent.generate_response("今天这次谈话，你希望有什么收获？", api_key="server-key")
        self.assertEqual((agent.current_state, agent.skipped_stages, agent.contract_done),
                         (CoachingState.EXPERIENCE, set(), True))

    def test_sessions_saved_before_the_contract_rule_carry_on(self):
        agent = CoacheeAgent(mode="llm", language="en")
        saved = {key: value for key, value in agent.to_dict().items() if key != "contract_done"}
        self.assertFalse(CoacheeAgent.from_dict(saved).contract_done)
        self.assertTrue(CoacheeAgent.from_dict({**saved, "state": "EXPERIENCE"}).contract_done)

    def test_a_stage_with_its_own_question_is_not_skipped(self):
        agent = self._practice_turns(("今天这次谈话，你希望有什么收获？", "GOAL"), ("为什么你会觉得他不服你？", "REALITY"))
        self.assertEqual(agent.current_state, CoachingState.EXPERIENCE)
        self.assertEqual(agent.skipped_stages, set())

    def test_a_topic_the_ai_cant_set_up_preserves_the_practice(self):
        web_app, store, user, request = _signed_in()
        with patch.object(web_app, "_safe_key", return_value="server-key"), \
                patch("coachee_agent._build_client", return_value=self._case_client([])):
            current = web_app._open_session(user, "coachee", "llm", "en")
        before = store.get_session(current["id"])
        with patch.object(web_app, "_safe_key", return_value="server-key"), \
                patch("coachee_agent._build_client", return_value=self._case_client([], payload="not json")), \
                patch.object(web_app.logger, "exception"), patch.object(web_app.gr, "Warning") as warning:
            outputs = web_app.start_with_topic("moving abroad", "English", "AI", current, request)

        self.assertEqual(outputs, (web_app.gr.skip(),) * web_app.NEW_SESSION_OUTPUT_COUNT)
        warning.assert_called_once_with(web_app.UI["en"]["topic_failed"])
        self.assertEqual(store.get_session(current["id"]), before)
        self.assertEqual(len(store.list_sessions(user["id"])), 1)


class TestReadAloud(unittest.TestCase):
    """Read-aloud uses the voices on the person's own device. Fan found it cold and machine-like, so it now picks the best
    voice there is, keeps each voice's own pitch and reads sentence by sentence. These run the real script in Node."""

    APPLE_COMPACT = {"name": "Tingting", "lang": "zh-CN", "voiceURI": "com.apple.voice.compact.zh-CN.Tingting", "localService": True}
    APPLE_ENHANCED = {"name": "Tingting", "lang": "zh-CN", "voiceURI": "com.apple.voice.enhanced.zh-CN.Tingting", "localService": True}
    LIMU = {"name": "Li-mu", "lang": "zh-CN", "voiceURI": "com.apple.voice.compact.zh-CN.Li-mu", "localService": True}
    SINJI = {"name": "Sinji", "lang": "zh-HK", "voiceURI": "com.apple.voice.enhanced.zh-HK.Sinji", "localService": True}
    GOOGLE_ZH = {"name": "Google 普通话（中国大陆）", "lang": "zh-CN", "voiceURI": "Google 普通话（中国大陆）", "localService": False}
    XIAOXIAO = {"name": "Microsoft Xiaoxiao Online (Natural) - Chinese (Mainland)", "lang": "zh-CN",
                "voiceURI": "Microsoft Xiaoxiao Online (Natural) - Chinese (Mainland)", "localService": False}
    YUNXI = {"name": "Microsoft Yunxi Online (Natural) - Chinese (Mainland)", "lang": "zh-CN",
             "voiceURI": "Microsoft Yunxi Online (Natural) - Chinese (Mainland)", "localService": False}
    BELLS = {"name": "Bells", "lang": "en-US", "voiceURI": "com.apple.speech.synthesis.voice.Bells", "localService": True}
    SAMANTHA = {"name": "Samantha", "lang": "en-US", "voiceURI": "com.apple.voice.enhanced.en-US.Samantha", "localService": True}
    ALEX = {"name": "Alex", "lang": "en-US", "voiceURI": "com.apple.speech.synthesis.voice.Alex", "localService": True}

    HARNESS = """
const voices = %(voices)s;
const spoken = [];
global.window = {__ttsFallbackMs: 60, sessionStorage: {getItem: () => null, setItem: () => {}}};
global.SpeechSynthesisUtterance = function (text) { this.text = text; };
window.speechSynthesis = {
  getVoices: () => voices,
  cancel: () => spoken.push("cancel"),
  resume: () => {},
  speak: (u) => {
    spoken.push({text: u.text, voice: u.voice ? u.voice.voiceURI : null, pitch: u.pitch, rate: u.rate});
    if (u.voice && (u.voice.localService || %(online_works)s)) setTimeout(() => u.onstart && u.onstart(), 1);
  },
};
const tts = (%(script)s);
tts("1|||" + %(text)s, true, %(preference)s, %(language)s);
setTimeout(() => console.log(JSON.stringify(spoken)), 300);
"""

    def _speak(self, voices, text="今天这次谈话，你希望有什么收获？", preference="女声", language="中文", online_works=True):
        import shutil
        import subprocess
        import web_assets

        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        source = self.HARNESS % dict(voices=json.dumps(voices, ensure_ascii=False), script=web_assets.tts_js,
                                     online_works="true" if online_works else "false",
                                     text=json.dumps(text, ensure_ascii=False),
                                     preference=json.dumps(preference, ensure_ascii=False), language=json.dumps(language))
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "tts.js"
            script.write_text(source, encoding="utf-8")
            result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def _voices_used(self, spoken):
        return [item["voice"] for item in spoken if item != "cancel"]

    def test_the_best_voice_on_the_device_is_chosen(self):
        everything = [self.APPLE_COMPACT, self.APPLE_ENHANCED, self.SINJI, self.GOOGLE_ZH, self.XIAOXIAO]
        self.assertEqual(set(self._voices_used(self._speak(everything))), {self.XIAOXIAO["voiceURI"]})  # Edge's neural voice
        # On an iPhone: the Enhanced voice over the basic one, never Cantonese Sinji for Mandarin text.
        iphone = [self.APPLE_COMPACT, self.APPLE_ENHANCED, self.SINJI]
        self.assertEqual(set(self._voices_used(self._speak(iphone))), {self.APPLE_ENHANCED["voiceURI"]})

    def test_chrome_on_a_mac_prefers_googles_voice_and_falls_back_in_mainland_china(self):
        # Fan uses Chrome and Safari. Chrome lists Google's online voices next to the Mac's own.
        tingting = {"name": "Tingting", "lang": "zh-CN", "voiceURI": "Tingting", "localService": True}
        cantonese = {"name": "Google 粤語（香港）", "lang": "zh-HK", "voiceURI": "Google 粤語（香港）", "localService": False}
        chrome = [tingting, self.GOOGLE_ZH, cantonese]
        self.assertEqual(set(self._voices_used(self._speak(chrome))), {self.GOOGLE_ZH["voiceURI"]})
        self.assertEqual(set(self._voices_used(self._speak(chrome, preference="男声"))), {self.GOOGLE_ZH["voiceURI"]})
        blocked = self._speak(chrome, online_works=False)
        self.assertEqual(set(self._voices_used(blocked[blocked.index("cancel", 1):])), {"Tingting"})
        english = [{"name": "Samantha", "lang": "en-US", "voiceURI": "Samantha", "localService": True},
                   {"name": "Google US English", "lang": "en-US", "voiceURI": "Google US English", "localService": False},
                   {"name": "Google UK English Male", "lang": "en-GB", "voiceURI": "Google UK English Male", "localService": False}]
        self.assertEqual(set(self._voices_used(self._speak(english, language="English"))), {"Google US English"})
        self.assertEqual(set(self._voices_used(self._speak(english, preference="Male", language="English"))),
                         {"Google UK English Male"})

    def test_male_voices_keep_their_own_pitch(self):
        spoken = self._speak([self.APPLE_ENHANCED, self.LIMU], preference="男声")
        self.assertEqual(set(self._voices_used(spoken)), {self.LIMU["voiceURI"]})
        self.assertEqual({item["pitch"] for item in spoken if item != "cancel"}, {1})  # no more lowered "male" pitch
        edge = self._speak([self.XIAOXIAO, self.YUNXI], preference="男声")
        self.assertEqual(set(self._voices_used(edge)), {self.YUNXI["voiceURI"]})

    def test_replies_are_read_sentence_by_sentence_without_markdown(self):
        spoken = self._speak([self.APPLE_ENHANCED], text="**行动卡**\n目标：每周两晚早点睡。\n下一步：今晚十一点前关灯！你觉得怎么样？")
        texts = [item["text"] for item in spoken if item != "cancel"]
        self.assertGreaterEqual(len(texts), 3)
        self.assertFalse(any("*" in text for text in texts))
        english = self._speak([self.SAMANTHA], language="English",
                              text="That sounds draining. What would you like from today? We have 2.5 hours.")
        self.assertEqual([item["text"] for item in english if item != "cancel"],
                         ["That sounds draining.", "What would you like from today?", "We have 2.5 hours."])

    def test_an_online_voice_that_never_starts_is_replaced_by_one_on_the_device(self):
        # Google's voices need Google's servers, which mainland China blocks. An Android phone's own Chinese voice:
        android = {"name": "中文（中国）", "lang": "zh-CN", "voiceURI": "zh-CN-language", "localService": True}
        spoken = self._speak([self.GOOGLE_ZH, android], online_works=False)
        self.assertEqual(spoken[1]["voice"], self.GOOGLE_ZH["voiceURI"])  # tried first: it ranks higher
        self.assertIn("cancel", spoken[1:])
        after_fallback = self._voices_used(spoken[spoken.index("cancel", 1):])
        self.assertEqual(set(after_fallback), {android["voiceURI"]})
        # Where Google's voice works, it is kept.
        self.assertEqual(set(self._voices_used(self._speak([self.GOOGLE_ZH, android]))), {self.GOOGLE_ZH["voiceURI"]})

    def test_robotic_voices_come_last_even_for_a_male_preference(self):
        # A Mac's real list (2026-10-16) has Apple's older voices next to Tingting; the old code chose "Reed" for a male
        # voice and lowered its pitch, which was the most machine-like sound of all.
        mac = [{"name": f"{name} (Chinese (China mainland))", "lang": "zh-CN", "voiceURI": f"{name} (Chinese (China mainland))",
                "localService": True} for name in ("Eddy", "Flo", "Grandma", "Grandpa", "Reed", "Rocko", "Sandy", "Shelley")]
        tingting = {"name": "Tingting", "lang": "zh-CN", "voiceURI": "Tingting", "localService": True}
        self.assertEqual(set(self._voices_used(self._speak(mac + [tingting], preference="男声"))), {"Tingting"})
        self.assertEqual(set(self._voices_used(self._speak(mac + [tingting, self.LIMU], preference="男声"))), {self.LIMU["voiceURI"]})
        only_old = self._voices_used(self._speak(mac))  # nothing better on the device: an older voice, never Grandma/Grandpa
        self.assertTrue(only_old and not any(name.startswith(("Grandma", "Grandpa")) for name in only_old))

    NOTE_HARNESS = """
const voices = %(voices)s;
const note = {textContent: "unset"};
global.document = {getElementById: (id) => (id === "voice-note-text" ? note : null)};
global.window = {speechSynthesis: {getVoices: () => voices}};
const run = (%(script)s);
run(%(preference)s, %(language)s);
setTimeout(() => console.log(JSON.stringify(note.textContent)), 50);
"""

    def _note(self, voices, preference, language="中文"):
        import shutil
        import subprocess
        import web_assets

        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        source = self.NOTE_HARNESS % dict(voices=json.dumps(voices, ensure_ascii=False), script=web_assets.voice_note_js,
                                          preference=json.dumps(preference, ensure_ascii=False),
                                          language=json.dumps(language))
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "note.js"
            script.write_text(source, encoding="utf-8")
            result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_settings_note_says_when_a_device_has_no_natural_male_voice(self):
        # Fan's iPhone (2026-10-16): websites get only super-compact voices, and no male Chinese one.
        iphone = [{"name": "Tingting", "lang": "zh-CN", "voiceURI": "com.apple.voice.super-compact.zh-CN.Tingting",
                   "localService": True},
                  {"name": "Daniel", "lang": "en-GB", "voiceURI": "com.apple.voice.super-compact.en-GB.Daniel",
                   "localService": True},
                  {"name": "Albert", "lang": "en-US", "voiceURI": "com.apple.speech.synthesis.voice.Albert", "localService": True}]
        self.assertEqual(self._note(iphone, "男声"), "这台设备没有自然的中文男声，会用女声朗读。")
        self.assertEqual(self._note(iphone, "女声"), "")
        self.assertEqual(self._note(iphone, "Male", "English"), "")  # Daniel
        self.assertEqual(self._note(iphone + [self.LIMU], "男声"), "")
        reed = {"name": "Reed (Chinese (China mainland))", "lang": "zh-CN", "voiceURI": "Reed (Chinese (China mainland))",
                "localService": True}
        self.assertEqual(self._note(iphone + [reed], "男声"), "这台设备没有自然的中文男声，会用女声朗读。")  # robotic only
        english_only_women = [{"name": "Samantha", "lang": "en-US", "voiceURI": "Samantha", "localService": True}]
        self.assertEqual(self._note(english_only_women, "Male", "English"),
                         "This device has no natural male English voice, so a female voice is used.")

    def test_novelty_voices_are_never_used(self):
        self.assertEqual(set(self._voices_used(self._speak([self.BELLS, self.SAMANTHA, self.ALEX], language="English"))),
                         {self.SAMANTHA["voiceURI"]})
        self.assertEqual(set(self._voices_used(self._speak([self.BELLS, self.ALEX], preference="Male", language="English"))),
                         {self.ALEX["voiceURI"]})


class TestIndependentBranding(unittest.TestCase):
    def _visible_text(self, path):
        return (Path(__file__).parent / path).read_text(encoding="utf-8")

    def test_no_coaching_school_name_in_what_users_see_or_the_ai_is_told(self):
        from studio_config import LEGACY_NAME

        for path in ("web_assets.py", "account_pages.py", "web_app.py", "coach_agent.py", "coachee_agent.py",
                     "coach_data.py", "coachee_data.py", "coaching_core.py", "safety.py", "site.webmanifest", "cli_app.py"):
            text = self._visible_text(path)
            for term in (LEGACY_NAME, "埃里克森", "arrow model"):
                self.assertNotIn(term, text.lower(), f"{term!r} in {path}")

    def test_no_certification_bodys_competency_names_in_what_the_ai_is_told(self):
        # The practice review once listed a certification body's competencies by name; the skills are described in
        # plain words instead.
        for path in ("coach_agent.py", "coachee_agent.py", "coaching_core.py", "web_assets.py", "account_pages.py"):
            text = self._visible_text(path).lower()
            for term in ("creating presence", "powerful questioning", "designing actions", "establishing the contract",
                         "core competenc"):
                self.assertNotIn(term, text, f"{term!r} in {path}")

    def test_app_name_and_independence_note(self):
        import account_pages
        from web_assets import UI

        self.assertEqual((UI["en"]["coach_name"], UI["zh"]["coach_name"]), ("Coaching Practice Studio", "教练练习室"))
        self.assertIn("Not affiliated", account_pages.T["en"]["independent"])
        self.assertIn("无关联", account_pages.T["zh"]["independent"])


class TestHelpPage(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        import web_app

        self.store = db.Store("sqlite://")
        self.client = TestClient(web_app.create_app(store=self.store, env={"STUDIO_SECRET_KEY": "test-secret"}))

    def test_help_is_public_and_bilingual(self):
        english = self.client.get("/help?lang=en")
        chinese = self.client.get("/help?lang=zh")

        self.assertEqual((english.status_code, chinese.status_code), (200, 200))
        self.assertIn("How Coaching Practice Studio works", english.text)
        self.assertIn("教练练习室怎么用", chinese.text)
        self.assertIn("http://testserver", english.text)
        self.assertIn('href="/login"', english.text)

    def test_help_shows_the_current_allowances(self):
        import quota

        quota.save_role_limits(self.store, "user", 4, 6, 400_000)
        page = self.client.get("/help?lang=en").text

        self.assertIn("you have 4 AI Coach sessions and 6 AI Coachee Lab sessions", page)

    def test_help_promises_no_canned_replies_after_the_allowance(self):
        # Over the allowance no session starts (there are no built-in stand-in questions any more).
        english = self.client.get("/help?lang=en").text
        chinese = self.client.get("/help?lang=zh").text

        self.assertNotIn("built-in questions", english)
        self.assertNotIn("内置问题", chinese)
        self.assertIn("tells you roughly when you can start again", english)
        self.assertIn("大约多久之后可以再开始", chinese)

    def test_help_explains_the_message_limit_of_a_conversation(self):
        self.assertIn("One conversation can have up to 100 of your messages; when 5 are left, the app counts them down",
                      self.client.get("/help?lang=en").text)
        self.assertIn("每次对话最多可以发 100 条消息；还剩 5 条时，应用会提醒你还剩几条", self.client.get("/help?lang=zh").text)

    def test_help_says_iphone_websites_get_only_basic_voices(self):
        # Fan downloaded "Lilian" on an iPhone; it never reached the browser's voice list, so Help no longer suggests it.
        english = self.client.get("/help?lang=en").text
        chinese = self.client.get("/help?lang=zh").text
        self.assertIn("browsers only let websites use Apple&#x27;s basic voices", english)
        self.assertIn("浏览器只允许网页使用苹果的基础声音", chinese)
        self.assertNotIn("download an Enhanced or Premium voice", english)

    def test_voice_page_runs_the_apps_own_read_aloud_code(self):
        # Built after Fan heard no change on an iPhone: the voice the app uses for each setting, with a Listen button.
        import web_assets

        english = self.client.get("/voices?lang=en")
        chinese = self.client.get("/voices?lang=zh")
        self.assertEqual((english.status_code, chinese.status_code), (200, 200))
        self.assertIn("Read-aloud voices", english.text)
        self.assertIn("朗读声音", chinese.text)
        self.assertIn("网页只能使用苹果的基础声音", chinese.text)
        self.assertIn(web_assets.tts_js.strip()[:60], english.text)
        self.assertIn('href="/voices"', self.client.get("/help?lang=zh").text)

    def test_voice_page_lists_every_voice_only_when_asked(self):
        # Fan: the full list of voices confused more than it helped, since nobody can change them. It stays for troubleshooting.
        self.assertNotIn('id="voice-list"', self.client.get("/voices?lang=zh").text)
        self.assertIn('id="voice-list"', self.client.get("/voices?lang=zh&details=1").text)

    def test_help_says_whom_to_contact_when_the_owner_sets_it(self):
        from fastapi.testclient import TestClient
        import web_app

        self.assertNotIn("Get in touch", self.client.get("/help?lang=en").text)
        client = TestClient(web_app.create_app(store=self.store, env={"STUDIO_SECRET_KEY": "test-secret",
                                                                       "STUDIO_CONTACT": "Fan, WeChat ID fan-coach"}))
        self.assertIn("Get in touch: Fan, WeChat ID fan-coach.", client.get("/help?lang=en").text)
        self.assertIn("请联系：Fan, WeChat ID fan-coach。", client.get("/help?lang=zh").text)

    def test_every_page_links_to_help(self):
        self.assertIn('href="/help"', self.client.get("/privacy").text)


if __name__ == "__main__":
    unittest.main()
