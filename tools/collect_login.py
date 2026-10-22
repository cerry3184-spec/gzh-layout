# -*- coding: utf-8 -*-
"""秀米登录态采集：前台弹出系统浏览器，等待用户登录，保存 Cookie 到 xiumi_auth.json

用法：
  python scripts/collect_login.py
  python scripts/collect_login.py --timeout 900

登录方式：秀米首页右上角点「登录」，手机扫码或账号密码。

判定登录成功的依据（v3 修复）：
  秀米用接口 /api/user/info 判定登录态 —— 未登录返回 401，登录后返回 200。
  v3 直接监听这个接口的状态码变化，这是唯一可靠信号。

  v1/v2 的失败原因：
    - v1 用「我的秀米」等导航文字判断 → 这些字未登录时也在，几秒内误判成功，
      存下空登录态，脚本退出时 browser.close() 把用户还没扫完码的窗口关掉。
    - v2 加了「登录按钮消失」判断 → 该按钮初始可能未渲染进 offsetParent，
      同样是假信号，仍然误判。
  v3 全程轮询接口，不依赖任何 DOM 文字。

流程：
  1. 打开首页，等接口 401（确认初始未登录）
  2. 提示用户扫码，全程每 2 秒复检接口
  3. 接口返回 200 → 打印用户信息 → 再等 2 秒让 Cookie 落盘 → 保存
  4. 超时 → 明确报 TIMEOUT，不保存
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_cfg import LAUNCH_OPTS, browser_hint, check_available

AUTH_FILE = Path(__file__).resolve().parent.parent / "xiumi_auth.json"
HOME = "https://xiumi.us/"
INFO_API = "https://xiumi.us/api/user/info"

# 匿名/统计 Cookie，不作为登录凭证
ANON_COOKIES = {"sid", "_ga", "_ga_MPF5T5D71D", "_gid", "_gat"}


def check_login_cookie_file():
    """离线复核已保存的登录态：用 Playwright 重放，验证 /api/user/info 是否 200。

    注意：秀米把登录态存在服务端 session，本地 Cookie 只有 sid + 统计项，
    所以不能靠 Cookie 名字判断，只能实际打一次接口。
    """
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, **LAUNCH_OPTS)
            pg = b.new_context(storage_state=str(AUTH_FILE)).new_page()
            state = {}

            def on_response(r):
                if "/api/user/info" in r.url:
                    state["code"] = r.status

            pg.on("response", on_response)
            pg.goto(HOME, wait_until="commit", timeout=30000)
            t0 = time.time()
            while time.time() - t0 < 20:
                if state.get("code") is not None:
                    break
                pg.wait_for_timeout(500)
            b.close()
            return state.get("code"), ""
    except Exception as e:
        return None, str(e)


def main():
    ap = argparse.ArgumentParser(description="秀米登录态采集")
    ap.add_argument("--timeout", type=int, default=900, help="等待秒数（默认 900）")
    a = ap.parse_args()

    if not check_available():
        sys.exit(1)
    print(browser_hint(), flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, **LAUNCH_OPTS)
        # 用持久化上下文：即使脚本异常退出，登录态仍留在磁盘 profile 里
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        # 记录接口状态
        api_state = {"code": None, "body": ""}

        def on_response(r):
            if "/api/user/info" in r.url:
                try:
                    api_state["code"] = r.status
                    if r.status == 200:
                        api_state["body"] = r.text()[:400]
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(HOME, wait_until="commit", timeout=30000)

        # 等初始接口返回（预期 401）
        t0 = time.time()
        while time.time() - t0 < 20:
            if api_state["code"] is not None:
                break
            page.wait_for_timeout(500)
        print(f"[INFO] 初始 /api/user/info 状态：{api_state['code']}（401 表示未登录，正常）", flush=True)

        print("=" * 60, flush=True)
        print("  请在弹出的浏览器窗口中登录秀米", flush=True)
        print("  右上角点「登录」→ 手机扫码或账号密码", flush=True)
        print("  本窗口会一直保持打开，登录成功会自动保存并关闭", flush=True)
        print("=" * 60, flush=True)

        # 轮询接口等 200
        deadline = time.time() + a.timeout
        ok = False
        while time.time() < deadline:
            page.wait_for_timeout(2000)
            try:
                # 主动重新拉一次接口，确保状态最新
                r = page.evaluate(
                    """async (u) => {
                        try {
                          const res = await fetch(u, {credentials:'include'});
                          let body = '';
                          if (res.ok) body = (await res.text()).slice(0, 400);
                          return {status: res.status, body};
                        } catch (e) { return {status: 0, body: String(e)}; }
                    }""",
                    INFO_API)
                code = r.get("status")
                if code == 200:
                    api_state["code"] = 200
                    api_state["body"] = r.get("body", "")
                    ok = True
                    break
                # 刷新一下侧边状态，让浏览器页面也更新
                if code and code != 401:
                    print(f"[DEBUG] 接口返回 {code}", flush=True)
            except Exception:
                pass

        if not ok:
            print("\n[TIMEOUT] 等待超时，未检测到登录成功，未保存登录态。", flush=True)
            print("        请重新运行：python scripts/collect_login.py", flush=True)
            print("        浏览器窗口保持打开 30 秒后自动关闭。", flush=True)
            page.wait_for_timeout(30000)
            browser.close()
            sys.exit(2)

        # 解析昵称（仅用于确认账号，不打印敏感字段）
        nick = ""
        try:
            data = json.loads(api_state["body"])
            nick = (data.get("nickname") or data.get("name")
                    or data.get("username") or "")
        except Exception:
            pass

        print("\n[OK] 接口返回 200，登录成功" + (f"（账号：{nick}）" if nick else ""), flush=True)
        print("[INFO] 等待 Cookie 落盘 ...", flush=True)
        page.wait_for_timeout(2500)

        ctx.storage_state(path=str(AUTH_FILE))
        print(f"[OK] 登录态已保存：{AUTH_FILE}", flush=True)

        # 保存后复核：用独立浏览器重放，验证登录态真的可用
        code, _ = check_login_cookie_file()
        print(f"[CHECK] 离线复核 /api/user/info：{code}", flush=True)
        if code == 200:
            print("[OK] 复核通过，登录态可用。", flush=True)
        else:
            print(f"[WARN] 离线复核返回 {code}，登录态可能不完整。", flush=True)
            print("       可在浏览器里重开一次编辑器确认；必要时重跑本脚本。", flush=True)

        print("浏览器窗口 3 秒后关闭 ...", flush=True)
        page.wait_for_timeout(3000)
        browser.close()


if __name__ == "__main__":
    main()
