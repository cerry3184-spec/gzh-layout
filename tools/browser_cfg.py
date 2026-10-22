# -*- coding: utf-8 -*-
"""浏览器启动配置：优先借用系统 Edge，免下载 Chromium 内核。

原理：
  Playwright 的 channel="msedge" 会直接调用本机已安装的 Microsoft Edge，
  不需要额外下载 ~150MB 的 Chromium。这样既省空间，也更贴近用户真实浏览器。

可选覆盖：
  环境变量 GZH_BROWSER_CHANNEL = msedge | chrome | chromium
  留空则默认 msedge（Edge）。设为 chromium 则回退到 Playwright 自带内核
  （需先执行：python -m playwright install chromium）
"""
import os
import sys

# 默认用系统 Edge；可通过环境变量切换
_CHANNEL = (os.environ.get("GZH_BROWSER_CHANNEL") or "msedge").strip()

# channel -> launch() kwargs。msedge/chrome 有值时用系统浏览器；
# "chromium" 是 Playwright 内置内核的合法 channel 值。
LAUNCH_OPTS = {"channel": _CHANNEL}


def browser_hint():
    """给用户看的提示文案。"""
    if _CHANNEL == "chromium":
        return ("[INFO] 使用 Playwright 内置 Chromium 内核。"
                "若未安装请先执行：python -m playwright install chromium")
    return f"[INFO] 使用系统浏览器：{_CHANNEL}（无需额外下载内核）"


def check_available():
    """检查目标浏览器是否可用，不可用时打印提示并返回 False。

    返回 True 表示可以尝试启动。
    """
    if _CHANNEL == "chromium":
        # 内置内核没法简单探测是否存在，交给 Playwright 报错
        return True

    import os.path as _osp
    if sys.platform.startswith("win"):
        candidates = {
            "msedge": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ],
            "chrome": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ],
        }.get(_CHANNEL, [])
    else:
        candidates = {
            "msedge": ["/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable"],
            "chrome": ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"],
        }.get(_CHANNEL, [])

    for c in candidates:
        if _osp.exists(c):
            return True

    print(f"[ERROR] 未找到浏览器可执行文件：{_CHANNEL}")
    if _CHANNEL == "msedge":
        print("       请确认已安装 Microsoft Edge；或设置环境变量 "
              "GZH_BROWSER_CHANNEL=chrome 使用 Chrome。")
    else:
        print("       可改用 msedge：set GZH_BROWSER_CHANNEL=msedge")
    return False
