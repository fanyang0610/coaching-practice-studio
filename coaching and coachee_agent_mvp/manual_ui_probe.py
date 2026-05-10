import argparse
import asyncio
import base64
import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import websockets


CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

READY_JS = """
(() => {
    const text = document.body ? document.body.innerText : "";
    const lowerText = text.toLowerCase();
    const hasInput = !!document.querySelector("#chat-input-msg textarea");
    const hasMic = !!document.querySelector("#custom-mic-btn");
    const hasSend = Array.from(document.querySelectorAll("button")).some((button) =>
        ["发送", "send"].includes((button.innerText || "").trim().toLowerCase())
    );
    const hasTracker = text.includes("当前阶段") || text.includes("Current stage");
    const processing = lowerText.includes("processing |");
    const scrollWidth = document.documentElement ? document.documentElement.scrollWidth : 0;
    const clientWidth = document.documentElement ? document.documentElement.clientWidth : 0;
    const noHorizontalOverflow = clientWidth > 0 && scrollWidth <= clientWidth + 1;
    const rowSelectors = [
        ".intro-md",
        "#topbar.module-tabs",
        ".mode-context-md",
        "#settings-sheet",
        ".tracker-shell",
        "#chat-stage",
        "#composer-shell",
    ];
    const rows = rowSelectors
        .map((selector) => ({ selector, element: document.querySelector(selector) }))
        .filter((row) => row.element && row.element.getBoundingClientRect().width > 0)
        .map((row) => {
            const rect = row.element.getBoundingClientRect();
            return {
                selector: row.selector,
                left: Math.round(rect.left),
                right: Math.round(rect.right),
                width: Math.round(rect.width),
            };
        });
    const rowLefts = rows.map((row) => row.left);
    const rowRights = rows.map((row) => row.right);
    const rowAlignmentOk = rows.length >= 6
        && Math.max(...rowLefts) - Math.min(...rowLefts) <= 2
        && Math.max(...rowRights) - Math.min(...rowRights) <= 2;
    const reasons = [];

    if (!hasInput) reasons.push("missing chat input");
    if (!hasMic) reasons.push("missing mic button");
    if (!hasSend) reasons.push("missing send button");
    if (!hasTracker) reasons.push("missing tracker text");
    if (processing) reasons.push("page still processing");
    if (!noHorizontalOverflow) reasons.push(`horizontal overflow ${scrollWidth}/${clientWidth}`);
    if (!rowAlignmentOk) reasons.push(`row alignment failed ${JSON.stringify(rows)}`);

    return {
        ready: hasInput && hasMic && hasSend && hasTracker && !processing && noHorizontalOverflow && rowAlignmentOk,
        reasons,
        scrollWidth,
        clientWidth,
        rows,
    };
})()
"""


def capture(url: str, output: Path, width: int, height: int, mobile: bool = False):
    if mobile:
        _capture_mobile(url, output, width, height)
        return

    _capture_desktop(url, output, width, height)


def _chrome_base_cmd(profile: str):
    return [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--disable-crash-reporter",
        f"--user-data-dir={profile}",
    ]


def _capture_desktop(url: str, output: Path, width: int, height: int):
    output.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_capture_chrome_async(url, output, width, height, mobile=False))

    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError(f"Screenshot was not created: {output}")


def _capture_mobile(url: str, output: Path, width: int, height: int):
    output.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_capture_mobile_async(url, output, width, height))

    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError(f"Screenshot was not created: {output}")


async def _capture_mobile_async(url: str, output: Path, width: int, height: int):
    await _capture_chrome_async(url, output, width, height, mobile=True)


async def _capture_chrome_async(url: str, output: Path, width: int, height: int, mobile: bool):
    with tempfile.TemporaryDirectory(prefix="erickson-chrome-") as profile:
        cmd = _chrome_base_cmd(profile) + [
            "--remote-debugging-port=0",
            "about:blank",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            port_file = Path(profile) / "DevToolsActivePort"
            for _ in range(100):
                if port_file.exists():
                    break
                await asyncio.sleep(0.1)
            if not port_file.exists():
                raise RuntimeError("Chrome DevTools port was not created.")

            port = port_file.read_text().splitlines()[0]
            tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2))
            page = next(tab for tab in tabs if tab.get("type") == "page")

            async with websockets.connect(page["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
                counter = 0

                async def call(method: str, params: dict | None = None):
                    nonlocal counter
                    counter += 1
                    await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
                    while True:
                        message = json.loads(await ws.recv())
                        if message.get("id") == counter:
                            if "error" in message:
                                raise RuntimeError(message["error"])
                            return message.get("result", {})

                await call("Page.enable")
                await call(
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": width,
                        "height": height,
                        "deviceScaleFactor": 1,
                        "mobile": mobile,
                    },
                )
                if mobile:
                    await call(
                        "Emulation.setUserAgentOverride",
                        {
                            "userAgent": IPHONE_UA,
                            "platform": "iPhone",
                        },
                    )
                last_error = None
                for attempt in range(2):
                    if attempt == 0:
                        await call("Page.navigate", {"url": url})
                    else:
                        await call("Page.reload", {"ignoreCache": True})
                    try:
                        await _wait_for_ready(call)
                        last_error = None
                        break
                    except RuntimeError as exc:
                        last_error = exc
                if last_error:
                    raise last_error
                result = await call("Page.captureScreenshot", {"format": "png", "fromSurface": True})
                output.write_bytes(base64.b64decode(result["data"]))
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


async def _wait_for_ready(call, timeout_seconds: float = 45.0):
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_status = None

    while asyncio.get_running_loop().time() < deadline:
        result = await call(
            "Runtime.evaluate",
            {
                "expression": READY_JS,
                "returnByValue": True,
            },
        )
        last_status = result.get("result", {}).get("value")
        if isinstance(last_status, dict) and last_status.get("ready"):
            return
        await asyncio.sleep(0.25)

    reasons = []
    if isinstance(last_status, dict):
        reasons = last_status.get("reasons") or []
    details = ", ".join(reasons) if reasons else "unknown readiness state"
    raise RuntimeError(f"Page did not become screenshot-ready: {details}")


def main():
    parser = argparse.ArgumentParser(description="Capture isolated desktop and mobile screenshots for Erickson Coach.")
    parser.add_argument("--url", default="http://127.0.0.1:8787")
    parser.add_argument("--out-dir", default="/private/tmp")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    capture(args.url, out_dir / "erickson-desktop.png", 1440, 1200)
    capture(args.url, out_dir / "erickson-mobile.png", 390, 844, mobile=True)
    print(out_dir / "erickson-desktop.png")
    print(out_dir / "erickson-mobile.png")


if __name__ == "__main__":
    main()
