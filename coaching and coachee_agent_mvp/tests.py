import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

# Tests must never reach the real model: blank the key before web_app loads .env (which won't override it).
os.environ["OPENAI_API_KEY"] = ""

import accounts  # noqa: E402
import db  # noqa: E402

from coach_agent import EricksonCoachingAgent
from coachee_agent import EricksonCoacheeAgent
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

    def test_hfignore_excludes_local_secrets_and_runtime_artifacts(self):
        root = Path(__file__).resolve().parent
        ignore_text = (root / ".hfignore").read_text(encoding="utf-8")

        for pattern in (
            ".env",
            ".DS_Store",
            "__pycache__/",
            "*.pyc",
            "user_profile.json",
            "Erickson Coach.app/",
        ):
            self.assertIn(pattern, ignore_text)

    def test_hf_deploy_helper_stages_web_app_as_remote_app(self):
        root = Path(__file__).resolve().parent
        helper_path = root / "scripts" / "deploy_hf_space.py"
        spec = importlib.util.spec_from_file_location("deploy_hf_space", helper_path)
        deploy_hf_space = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deploy_hf_space)

        with tempfile.TemporaryDirectory() as temp_dir:
            staged_files = deploy_hf_space.stage_space(root, Path(temp_dir))
            staged_root = Path(temp_dir)

            self.assertIn(Path("app.py"), staged_files)
            self.assertNotIn(Path("web_app.py"), staged_files)
            self.assertNotIn(Path(".env"), staged_files)
            self.assertNotIn(Path("user_profile.json"), staged_files)
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

        decision = needs_hf_upload.decide_upload_need(
            root,
            [Path("manual_ui_probe.py"), Path("tests.py")],
        )

        self.assertFalse(decision.needs_upload)
        self.assertEqual(decision.deploy_worthy, [])
        self.assertEqual([item.path for item in decision.local_only], [Path("manual_ui_probe.py"), Path("tests.py")])
        self.assertTrue(all("local verification" in item.reason for item in decision.local_only))

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

        decision = needs_hf_upload.decide_upload_need(root, [Path("web_app.py"), Path("app.py")])

        self.assertTrue(decision.needs_upload)
        self.assertEqual(len(decision.deploy_worthy), 1)
        self.assertEqual(decision.deploy_worthy[0].path, Path("web_app.py"))
        self.assertEqual(decision.deploy_worthy[0].remote_path, Path(deploy_hf_space.REMOTE_ENTRYPOINT))
        self.assertIn("Space entrypoint", decision.deploy_worthy[0].reason)
        self.assertEqual(decision.local_only[0].path, Path("app.py"))
        self.assertIn("local wrapper", decision.local_only[0].reason)

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
                f"R  {prefix}assets/new.css",
                f"{prefix}assets/old.css",
                " M README.md",
                "",
            ]
        )

        changed_paths = needs_hf_upload._parse_git_status(status_output, prefix)
        decision = needs_hf_upload.decide_upload_need(root, changed_paths)

        self.assertEqual(
            changed_paths,
            [Path("web_app.py"), Path("tests.py"), Path("assets/new.css"), Path("assets/old.css")],
        )
        self.assertTrue(decision.needs_upload)
        self.assertIn(Path("web_app.py"), [item.path for item in decision.deploy_worthy])
        self.assertNotIn(Path("README.md"), [item.path for item in decision.deploy_worthy])
        self.assertEqual([item.path for item in decision.local_only], [Path("tests.py")])

    def test_macos_launcher_disables_default_browser_auto_open(self):
        root = Path(__file__).resolve().parent
        launcher_text = (root / "Erickson Coach Launcher.applescript").read_text(encoding="utf-8")

        self.assertIn("ERICKSON_INBROWSER=0", launcher_text)

    def test_macos_launcher_opens_ui_through_project_launcher(self):
        root = Path(__file__).resolve().parent
        launcher_text = (root / "Erickson Coach Launcher.applescript").read_text(encoding="utf-8")

        self.assertIn("python3 mac_launcher.py", launcher_text)

    def test_mac_launcher_uses_isolated_chrome_profile(self):
        import mac_launcher

        cmd = mac_launcher.chrome_command("http://127.0.0.1:7860")

        self.assertIn("--user-data-dir=/private/tmp/erickson-coach-chrome-profile", cmd)
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
            root / "assets" / "icons" / "EricksonCoach.icns",
        )
        self.assertTrue(check_project.LAUNCHER_ICON_SOURCE.exists())
        self.assertEqual(
            check_project.LAUNCHER_ICON_TARGET,
            root / "Erickson Coach.app" / "Contents" / "Resources" / "applet.icns",
        )
        self.assertTrue(callable(check_project.compile_launcher))


class TestEricksonCoachingAgent(unittest.TestCase):
    def setUp(self):
        self.agent = EricksonCoachingAgent(mode="template")

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

        agent = EricksonCoachingAgent(mode="llm", language="en")
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
        agent = EricksonCoachingAgent(mode="template", language="zh")
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
        agent = EricksonCoachingAgent(mode="llm")
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

    def test_llm_empty_content_falls_back_to_template_response(self):
        agent = EricksonCoachingAgent(mode="llm", language="en")

        with patch.object(agent, "_get_llm_response", side_effect=ValueError("Model returned no text content.")):
            response = agent.generate_response("I want to make a career decision.", api_key="server-key")

        self.assertTrue(response)
        self.assertEqual(agent.mode, "llm")
        self.assertEqual(agent.context[-1], {"role": "coach", "content": response})
        self.assertNotIn("Model returned no text content", response)

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
            web_app.create_app(store=db.Store("sqlite://"), env={"ERICKSON_SECRET_KEY": "test-secret"})
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

        self.assertIn("AI教练\n来访者", web_app._module_button_text("coach", "zh", "coach"))
        self.assertIn("AI学员\n练提问", web_app._module_button_text("coachee", "zh", "coach"))
        self.assertIn("AI Coach\nClient", web_app._module_button_text("coach", "en", "coach"))
        self.assertIn("AI Coachee\nPractice", web_app._module_button_text("coachee", "en", "coach"))

    def test_transformational_studio_contract(self):
        root = Path(__file__).resolve().parent
        source = (root / "web_app.py").read_text(encoding="utf-8")
        import web_app

        header_html = web_app._header_markdown({"agent": web_app._new_session()["agent"], "module": "coach"})
        mode_html = web_app._mode_context_html({"agent": web_app._new_session()["agent"], "module": "coach"})

        self.assertIn("studio-header", header_html)
        self.assertIn('src="/icons/erickson-icon-192.png"', header_html)
        self.assertIn('href="/account"', header_html)
        self.assertNotIn("base64", header_html)
        self.assertIn("埃里克森教练", header_html)
        self.assertNotIn("transformation-hero", header_html)
        self.assertIn("mode-context-card", mode_html)
        self.assertIn("来访者模式", mode_html)
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

    def test_mode_context_note_wraps_instead_of_single_line_ellipsis(self):
        from web_app import UI, css

        self.assertLessEqual(len(UI["en"]["coachee_module_note"]), 58)
        note_block = css[css.index(".mode-context-card p {"): css.index("#settings-sheet", css.index(".mode-context-card p {"))]
        self.assertIn("white-space: normal", note_block)
        self.assertIn("-webkit-line-clamp: 2", note_block)
        self.assertNotIn("text-overflow: ellipsis", note_block)

    def test_row_level_surfaces_share_one_alignment_contract(self):
        from web_app import css

        contract = css[css.index("/* Erickson row alignment contract */"):]
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
            root / "assets" / "icons" / "erickson-icon-source.png": 1024,
            root / "assets" / "icons" / "erickson-icon.svg": None,
            root / "assets" / "icons" / "erickson-icon-180.png": 180,
            root / "assets" / "icons" / "erickson-icon-192.png": 192,
            root / "assets" / "icons" / "erickson-icon-512.png": 512,
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

        self.assertTrue((root / "Erickson Coach.app" / "Contents" / "Resources" / "applet.icns").exists())

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

        self.assertFalse(_launch_inbrowser({"ERICKSON_INBROWSER": "0"}))
        self.assertFalse(_launch_inbrowser({"ERICKSON_INBROWSER": "false"}))
        self.assertFalse(_launch_inbrowser({"CODEX_SANDBOX": "seatbelt"}))
        self.assertFalse(_launch_inbrowser({"CODEX_CI": "1"}))
        self.assertTrue(_launch_inbrowser({"CODEX_SANDBOX": "seatbelt", "ERICKSON_INBROWSER": "1"}))
        self.assertTrue(_launch_inbrowser({"ERICKSON_INBROWSER": "1"}))
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

    def test_ai_opening_reports_model_error_without_template_fallback(self):
        import web_app

        session = web_app._new_session(module="coach", mode="llm", language="zh")
        agent = session["agent"]

        with patch.object(web_app, "_load_dotenv", return_value=None):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}, clear=True):
                with patch.object(agent, "_get_llm_opening_response", side_effect=ValueError("Model returned no text content.")):
                    with patch.object(web_app.logger, "exception"):
                        prompt = web_app._append_opening_prompt(agent)

        self.assertIn("AI", prompt)
        self.assertIn("没有返回有效开场", prompt)
        self.assertNotIn("你现在最关注的话题是什么？", prompt)
        self.assertEqual(agent.mode, "llm")
        self.assertEqual(agent.context[-1]["content"], prompt)

    def test_one_page_erickson_ui_contract_is_present(self):
        root = Path(__file__).parent
        import web_app

        self.assertTrue((root / "DESIGN.erickson-edu.md").exists())
        self.assertIn(".module-tabs", web_app.css)
        self.assertIn("height: 100dvh", web_app.css)
        self.assertIn("overflow: hidden", web_app.css)

class TestEricksonCoacheeAgent(unittest.TestCase):
    def setUp(self):
        self.agent = EricksonCoacheeAgent(mode="template", language="en")

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

        agent = EricksonCoacheeAgent(mode="llm", language="en")
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

    def test_force_next_state_advances_to_bridge_then_next_stage(self):
        opening = self.agent.get_stage_prompt()
        self.agent.context.append({"role": self.agent.assistant_role, "content": opening})

        self.assertTrue(self.agent.force_next_state())
        self.assertEqual(self.agent.current_sub_phase.name, "BRIDGE")

        self.assertTrue(self.agent.force_next_state())
        self.assertEqual(self.agent.current_state, CoachingState.EXPERIENCE)

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


class TestSingleCallStageDecisions(unittest.TestCase):
    def _deepening_coach(self):
        from coaching_core import CoachingSubPhase

        agent = EricksonCoachingAgent(mode="llm", language="en")
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

    def test_coach_reply_decides_next_stage_in_one_streamed_call(self):
        from coaching_core import CoachingSubPhase

        agent = self._deepening_coach()
        calls = []
        client = _fake_llm_client(["[[NEXT]] You have a clear goal. What is happening right now?"], calls)

        with patch("coach_agent._build_client", return_value=client):
            partials = list(agent.stream_response("I want two focused hours a day.", api_key="server-key"))

        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["stream"])
        self.assertIn("[[NEXT]]", calls[0]["messages"][0]["content"])
        self.assertTrue(all("[[" not in text for text in partials))
        self.assertEqual(partials[-1], "You have a clear goal. What is happening right now?")
        self.assertEqual(agent.current_sub_phase, CoachingSubPhase.BRIDGE)
        self.assertEqual(agent.context[-1], {"role": "coach", "content": partials[-1]})

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

    def test_coach_reply_without_marker_paces_stage_like_template_mode(self):
        from coaching_core import CoachingSubPhase

        agent = self._deepening_coach()
        agent.turns_in_current_stage = 3
        calls = []
        client = _fake_llm_client(["Let's look at where things stand now."], calls)

        with patch("coach_agent._build_client", return_value=client):
            agent.generate_response("Yes, that's the goal.", api_key="server-key")

        self.assertEqual(agent.current_sub_phase, CoachingSubPhase.BRIDGE)

    def test_reply_emptied_by_language_cleanup_falls_back_to_template(self):
        agent = EricksonCoachingAgent(mode="llm", language="zh")
        agent.context = [{"role": "coach", "content": "你今天想聚焦什么？"}]
        calls = []
        client = _fake_llm_client(["What would help most this week?"], calls)

        with patch("coach_agent._build_client", return_value=client):
            partials = list(agent.stream_response("我想更好地管理时间。", api_key="server-key"))

        self.assertTrue(partials[-1])
        self.assertEqual(agent.context[-1]["content"], partials[-1])
        self.assertNotIn("What would help", partials[-1])

    def test_coachee_end_marker_stops_reply_and_returns_review(self):
        agent = EricksonCoacheeAgent(mode="llm", language="en")
        agent._llm_scenario_ready = True
        agent.context = [{"role": "coachee", "content": agent.scenario.intro["en"]}]
        calls = []
        client = _fake_llm_client(
            ["[[END]] Thanks, I feel ready.", "Session Result: Solid start.\nScore: 70/100"],
            calls,
        )

        with patch("coachee_agent._build_client", return_value=client):
            partials = list(agent.stream_response("Goodbye and good luck!", api_key="server-key"))

        self.assertEqual(partials, ["Session Result: Solid start.\nScore: 70/100"])
        self.assertTrue(agent.is_session_ended())
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0]["stream"])
        self.assertFalse(calls[1].get("stream", False))

    def test_coachee_next_marker_moves_to_bridge_without_extra_call(self):
        from coaching_core import CoachingSubPhase

        agent = EricksonCoacheeAgent(mode="llm", language="en")
        agent._llm_scenario_ready = True
        agent.context = [{"role": "coachee", "content": agent.scenario.intro["en"]}]
        calls = []
        client = _fake_llm_client(["[[NEXT]] I want to feel calmer at work."], calls)

        with patch("coachee_agent._build_client", return_value=client):
            reply = agent.generate_response("What do you want from today?", api_key="server-key")

        self.assertEqual(reply, "I want to feel calmer at work.")
        self.assertEqual(agent.current_sub_phase, CoachingSubPhase.BRIDGE)
        self.assertEqual(len(calls), 1)

    def test_history_translation_is_one_call(self):
        agent = EricksonCoachingAgent(mode="llm", language="en")
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

        self.assertIs(first, second)
        self.assertEqual(first.timeout, coaching_core.LLM_TIMEOUT_SECONDS)
        self.assertEqual(first.max_retries, coaching_core.LLM_MAX_RETRIES)


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
                web_app.create_app(store=db.Store("sqlite://"), env={"SPACE_ID": "fanyang0610/Erickson-Coach-App"})
            mount.assert_not_called()
            web_app.create_app(store=db.Store("sqlite://"), env={"SPACE_ID": "x", "ERICKSON_SECRET_KEY": "k" * 64})

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
        env = {"SPACE_ID": "x", "ERICKSON_SECRET_KEY": "k" * 64, "ERICKSON_ADMIN_EMAIL": "Owner@Example.com",
               "ERICKSON_ADMIN_PASSWORD": "a-long-password"}
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
        model_fns = [fn for fn in backend_fns if fn.name != "record_feedback"]

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

    def test_respond_stops_at_session_turn_limit(self):
        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        agent = session["agent"]
        agent.context = [{"role": agent.user_role, "content": "hi"}] * web_app.MAX_USER_TURNS_PER_SESSION
        with patch.object(web_app.gr, "Warning") as warning:
            outputs = list(web_app.respond("one more", [], session, "coach", "Template", "English", request))

        self.assertEqual(warning.call_args.args[0], web_app.UI["en"]["turn_limit"])
        self.assertFalse(outputs[-1][0]["interactive"])
        self.assertEqual(len(agent.context), web_app.MAX_USER_TURNS_PER_SESSION)

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

    def test_turns_are_saved_after_each_reply(self):
        web_app, store, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")

        list(web_app.respond("I want more focus.", [], session, "coach", "Template", "English", request))

        row = store.get_session(session["id"])
        self.assertEqual(row["user_turns"], 1)
        self.assertEqual(json.loads(row["state"])["context"], session["agent"].context)

    def test_over_allowance_sessions_open_in_template_mode(self):
        web_app, _, user, _ = _signed_in(daily_session_limit=0)
        with patch.object(web_app.gr, "Warning") as warning:
            session = web_app._open_session(user, "coach", "llm", "en")

        self.assertEqual(session["agent"].mode, "template")
        self.assertEqual(warning.call_args.args[0], web_app.UI["en"]["quota_sessions"].format(hours=24))

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
        agent = EricksonCoachingAgent(mode="template", language="en")
        for text in ("", "I want calmer mornings.", "It matters for my family.", "I'd feel rested."):
            agent.generate_response(text)

        restored = EricksonCoachingAgent.from_dict(json.loads(json.dumps(agent.to_dict())))

        self.assertEqual(restored.to_dict(), agent.to_dict())
        self.assertTrue(restored.generate_response("Let's keep going."))

    def test_coachee_agent_round_trips_through_json(self):
        agent = EricksonCoacheeAgent(mode="template", language="en")
        agent.context.append({"role": agent.assistant_role, "content": agent.get_stage_prompt()})
        for text in ("What would you like to achieve today?", "Why does that matter now?", "How will you know it worked?"):
            agent.generate_response(text)

        restored = EricksonCoacheeAgent.from_dict(json.loads(json.dumps(agent.to_dict())))

        self.assertEqual(restored.to_dict(), agent.to_dict())
        self.assertEqual(restored.metrics.stage_questions, agent.metrics.stage_questions)
        self.assertTrue(restored.generate_response("What is happening right now?"))


class TestStore(unittest.TestCase):
    def setUp(self):
        self.store = db.Store("sqlite://")
        self.uid = self.store.create_user("Amy@Example.com ", "Amy", accounts.hash_password("a-long-password"))

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
        self.assertTrue(accounts.can_view_session(admin, private, owner))
        self.assertTrue(accounts.can_view_session(trainer, practice, owner))
        self.assertTrue(accounts.can_view_session(trainer, shared, owner))
        self.assertFalse(accounts.can_view_session(trainer, private, owner))
        self.assertFalse(accounts.can_view_session(other_trainer, practice, owner))
        self.assertFalse(accounts.can_view_session(stranger, practice, owner))


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
        cls.app = web_app.create_app(store=db.Store("sqlite://"), env={"ERICKSON_SECRET_KEY": cls.secret})

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

    def test_wrong_password_is_rejected_then_throttled(self):
        self._person("amy@example.com")
        for _ in range(8):
            response = self.client.post("/login", data={"email": "amy@example.com", "password": "wrong-password"})
            self.assertEqual(response.status_code, 401)

        response = self.client.post("/login", data={"email": "amy@example.com", "password": "a-long-password"})
        self.assertEqual(response.status_code, 429)

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

        learner_client.post(f"/account/sessions/{private}/share", data={"csrf": self._csrf(learner_client), "shared": "yes"})
        self.assertEqual(trainer_client.get(f"/sessions/{private}").status_code, 200)
        self.assertEqual(admin_client.get(f"/sessions/{private}").status_code, 200)

        viewers = [entry["actor_id"] for entry in self.store.audit_entries() if entry["action"] == "session_viewed"]
        self.assertCountEqual(viewers, [trainer, trainer, admin])

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

    def test_export_and_delete_my_account(self):
        learner = self._person("learner@example.com")
        self.store.create_session(learner, "coach", "en", "llm", "CONTRACT", {"context": [{"role": "coach", "content": "Hi"}]})
        client = self._sign_in("learner@example.com")

        export = client.get("/account/export")
        self.assertEqual(export.json()["sessions"][0]["transcript"][0]["content"], "Hi")

        client.post("/account/delete", data={"csrf": self._csrf(client), "confirm": "DELETE"})
        self.assertIsNone(self.store.get_user(learner))
        self.assertEqual(self.store.list_sessions(learner), [])

    def test_public_icons_and_manifest_need_no_sign_in(self):
        self.assertEqual(self.client.get("/icons/erickson-icon-180.png").status_code, 200)
        self.assertEqual(self.client.get("/site.webmanifest").status_code, 200)
        self.assertEqual(self.client.get("/privacy").status_code, 200)
        self.assertEqual(self.client.get("/healthz").json(), {"ok": True})


class TestLanguageAndLocalisation(unittest.TestCase):
    def test_language_preference_cookie_then_browser(self):
        import account_pages

        self.assertEqual(account_pages.preferred_language({"erickson_lang": "zh"}, {"accept-language": "en-US"}), "zh")
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

    def test_reopened_session_follows_the_chosen_language(self):
        import gradio as gr

        web_app, _, user, request = _signed_in()
        session = web_app._open_session(user, "coach", "template", "en")
        chinese_choice = gr.Request(username=str(user["id"]), headers={"accept-language": "en-US"}, cookies={"erickson_lang": "zh"})

        outputs = web_app.initial_load(None, "coach", "AI", "English", chinese_choice)

        self.assertEqual(outputs[-1]["id"], session["id"])
        self.assertEqual(outputs[-1]["agent"].language, "zh")
        self.assertEqual(outputs[12]["value"], "中文")
        self.assertIn("埃里克森教练", outputs[2])

    def test_switching_language_in_the_app_is_remembered_for_the_pages(self):
        import web_app

        self.assertIn("erickson_lang=", web_app.remember_lang_js)
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
            app = web_app.create_app(store=self.store, env={"ERICKSON_SECRET_KEY": "test-secret", "SMTP_HOST": "smtp.example.com"})
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

        without_email = TestClient(web_app.create_app(store=self.store, env={"ERICKSON_SECRET_KEY": "test-secret"}))
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

    def test_account_page_shows_each_modules_allowance(self):
        self._person("amy@example.com")
        self.client.post("/login", data={"email": "amy@example.com", "password": "a-long-password"})

        page = self.client.get("/account?lang=en").text

        self.assertIn("AI Coach: 3 of 3 AI sessions left today", page)
        self.assertIn("Coachee Lab: 5 of 5 AI sessions left today", page)

    def test_local_runs_keep_their_signing_key_between_restarts(self):
        import web_app

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(web_app, "LOCAL_SECRET_FILE", Path(folder) / ".erickson_secret"):
                first = web_app._secret_key({})
                second = web_app._secret_key({})
                mode = (Path(folder) / ".erickson_secret").stat().st_mode & 0o777

        self.assertEqual(first, second)
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
