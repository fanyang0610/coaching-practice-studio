import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coach_agent import EricksonCoachingAgent
from coachee_agent import EricksonCoacheeAgent
from coaching_core import CoachingState, _clean_response_language, _response_text
from memory import MemoryManager


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
        with patch.object(web_app.demo, "launch") as launch:
            web_app.launch_demo()
        self.assertEqual(web_app.head, launch.call_args.kwargs["head"])

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
        self.assertIn('src="/gradio_api/file=assets/icons/erickson-icon-192.png"', header_html)
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
        import web_app

        session = web_app._new_session(module="coach", mode="template", language="zh")

        result = list(web_app.respond("", [], session, "coach", "模板", "中文"))[-1]

        self.assertEqual(web_app.RESPOND_OUTPUT_COUNT, len(result))

    def test_blocked_next_stage_returns_all_outputs(self):
        import web_app

        session = web_app._new_session(module="coachee", mode="template", language="zh")

        result = web_app.next_stage([], session, "coachee", "模板", "中文")

        self.assertEqual(web_app.NEXT_STAGE_OUTPUT_COUNT, len(result))

    def test_coachee_manual_advance_to_closing_ends_session_and_disables_input(self):
        import web_app
        from coaching_core import CoachingSubPhase

        session = web_app._new_session(module="coachee", mode="template", language="en")
        agent = session["agent"]
        agent.current_state = CoachingState.VALUE
        agent.current_sub_phase = CoachingSubPhase.BRIDGE
        agent.metrics.stage_questions[CoachingState.VALUE] = 1

        result = web_app.next_stage([], session, "coachee", "Template", "English")

        self.assertEqual(web_app.NEXT_STAGE_OUTPUT_COUNT, len(result))
        self.assertTrue(agent.is_session_ended())
        self.assertEqual(agent.current_state, CoachingState.CLOSING)
        self.assertEqual(result[0]["interactive"], False)

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

    def test_hosted_space_memory_is_session_only(self):
        import web_app

        with patch.dict(os.environ, {"SPACE_ID": "fanyang0610/Erickson-Coach-App"}, clear=True):
            with patch.object(web_app, "_load_dotenv", return_value=None):
                with patch("web_app.MemoryManager") as manager:
                    web_app._get_memory()

        manager.assert_called_once_with(api_key="", local_path=None)


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
    def test_memory_can_be_session_only_without_local_file_io(self):
        manager = MemoryManager(api_key="server-key", local_path=None)
        self.assertEqual(manager.local_path, None)

        with patch("memory.open") as file_open:
            manager.load_local()
            manager.save_local()

        file_open.assert_not_called()

    def test_remote_sync_is_opt_in(self):
        manager = MemoryManager(api_key="server-key")

        self.assertFalse(manager.sync_pull())
        self.assertFalse(manager.sync_push())

    def test_memory_module_has_no_remote_network_dependency(self):
        import memory

        self.assertFalse(hasattr(memory, "requests"))
        self.assertFalse(hasattr(memory, "Fernet"))

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


class TestHostedAccessAndLimits(unittest.TestCase):
    def test_invited_logins_are_parsed_from_environment(self):
        import web_app

        users = web_app._auth_users({"ERICKSON_USERS": "amy:pw1, bo:p:w2\ncy:pw3,broken,:nouser"})

        self.assertEqual(users, {"amy": "pw1", "bo": "p:w2", "cy": "pw3"})

    def test_public_launch_without_logins_refuses_to_start(self):
        import web_app

        with patch.dict(os.environ, {"SPACE_ID": "fanyang0610/Erickson-Coach-App"}, clear=True):
            with patch.object(web_app.demo, "launch") as launch:
                with self.assertRaises(SystemExit):
                    web_app.launch_demo()

        launch.assert_not_called()
        self.assertTrue(web_app._requires_auth({"GRADIO_SERVER_NAME": "0.0.0.0"}))
        self.assertFalse(web_app._requires_auth({}))

    def test_launch_checks_invited_logins(self):
        import web_app

        with patch.dict(os.environ, {"SPACE_ID": "x", "ERICKSON_USERS": "amy:pw1"}, clear=True):
            with patch.object(web_app.demo, "launch") as launch:
                web_app.launch_demo()

        check = launch.call_args.kwargs["auth"]
        self.assertTrue(check("amy", "pw1"))
        self.assertFalse(check("amy", "wrong"))
        self.assertFalse(check("zed", "pw1"))
        self.assertNotIn("api", launch.call_args.kwargs["footer_links"])

    def test_model_events_share_one_concurrency_pool_and_stay_off_the_api_page(self):
        import web_app

        backend_fns = [fn for fn in web_app.demo.fns.values() if fn.fn is not None]

        self.assertGreaterEqual(len(backend_fns), 8)
        for fn in backend_fns:
            self.assertEqual(fn.concurrency_id, "llm", fn.name)
            self.assertEqual(fn.concurrency_limit, web_app.LLM_CONCURRENCY, fn.name)
            self.assertEqual(fn.api_visibility, "private", fn.name)

    def test_respond_streams_partial_transcripts(self):
        import web_app

        session = web_app._new_session(module="coach", mode="template", language="en")
        outputs = list(web_app.respond("I want more focus.", [], session, "coach", "Template", "English"))

        self.assertGreaterEqual(len(outputs), 2)
        self.assertTrue(all(len(output) == web_app.RESPOND_OUTPUT_COUNT for output in outputs))
        self.assertEqual(outputs[0][1], [{"role": "user", "content": "I want more focus."}])
        self.assertEqual(outputs[-1][1][-1]["role"], "assistant")

    def test_respond_rejects_overlong_messages_before_calling_the_agent(self):
        import web_app

        session = web_app._new_session(module="coach", mode="template", language="en")
        with patch.object(web_app.gr, "Warning") as warning:
            outputs = list(web_app.respond("x" * (web_app.MAX_MESSAGE_CHARS + 1), [], session, "coach", "Template", "English"))

        self.assertEqual(len(outputs), 1)
        self.assertIn(str(web_app.MAX_MESSAGE_CHARS), warning.call_args.args[0])
        self.assertEqual(session["agent"].context, [])

    def test_respond_stops_at_session_turn_limit(self):
        import web_app

        session = web_app._new_session(module="coach", mode="template", language="en")
        agent = session["agent"]
        agent.context = [{"role": agent.user_role, "content": "hi"}] * web_app.MAX_USER_TURNS_PER_SESSION
        with patch.object(web_app.gr, "Warning") as warning:
            outputs = list(web_app.respond("one more", [], session, "coach", "Template", "English"))

        self.assertEqual(warning.call_args.args[0], web_app.UI["en"]["turn_limit"])
        self.assertFalse(outputs[-1][0]["interactive"])
        self.assertEqual(len(agent.context), web_app.MAX_USER_TURNS_PER_SESSION)

    def test_respond_refuses_overlapping_sends_on_one_conversation(self):
        import web_app

        session = web_app._new_session(module="coach", mode="template", language="en")
        lock = web_app._agent_lock(session["agent"])
        lock.acquire()
        try:
            with patch.object(web_app.gr, "Warning") as warning:
                list(web_app.respond("hello", [], session, "coach", "Template", "English"))
        finally:
            lock.release()

        self.assertEqual(warning.call_args.args[0], web_app.UI["en"]["busy_warning"])
        self.assertEqual(session["agent"].context, [])

    def test_model_errors_are_logged_not_shown_to_users(self):
        import web_app

        session = web_app._new_session(module="coach", mode="llm", language="en")
        session["agent"].context = [{"role": "coach", "content": "What would you like to focus on?"}]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "server-key"}, clear=True):
            with patch.object(session["agent"], "_get_llm_response", side_effect=RuntimeError("upstream 502 from https://internal")):
                with patch.object(web_app.gr, "Warning") as warning, patch.object(web_app.logger, "exception"):
                    outputs = list(web_app.respond("hello", [], session, "coach", "AI", "English"))

        self.assertEqual(warning.call_args.args[0], web_app.UI["en"]["ai_reply_error"])
        self.assertEqual(outputs[-1][0]["value"], "hello")
        self.assertEqual(outputs[-1][1], [])


if __name__ == "__main__":
    unittest.main()
