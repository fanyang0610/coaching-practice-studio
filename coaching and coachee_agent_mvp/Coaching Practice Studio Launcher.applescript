-- The app bundle lives in the project folder, so launch whichever copy of the project it sits in.
set workspace_path_value to POSIX path of ((path to me as text) & "::")
set launch_command to "cd " & (quoted form of workspace_path_value) & " && export STUDIO_INBROWSER=0 && if [ -x .venv/bin/python ]; then .venv/bin/python mac_launcher.py; else python3 mac_launcher.py; fi"

tell application "Terminal.app"
	activate
	«event coredosc» launch_command
end tell
