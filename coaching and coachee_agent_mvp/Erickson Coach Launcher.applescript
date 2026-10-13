-- The app bundle lives in the project folder, so launch whichever copy of the project it sits in.
set workspace_path_value to POSIX path of ((path to me as text) & "::")
set launch_command to "cd " & (quoted form of workspace_path_value) & " && ERICKSON_INBROWSER=0 python3 mac_launcher.py"

tell application "Terminal.app"
	activate
	«event coredosc» launch_command
end tell
