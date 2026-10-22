# -*- coding: utf-8 -*-
"""秀米编辑器自动化核心脚本

用法：
  python xiumi_auto.py --title "标题" --text "正文段落1\\n正文段落2"
  python xiumi_auto.py --title "标题" --html-file layout.html
  python xiumi_auto.py --title "标题" --html-file layout.html --no-save
"""
import argparse
import random
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_cfg import LAUNCH_OPTS, browser_hint, check_available

BASE_DIR = Path(__file__).resolve().parent.parent
AUTH_FILE = BASE_DIR / "xiumi_auth.json"
EDITOR_URL = "https://xiumi.us/studio/v5/paper"

TITLE_INPUT = "input[placeholder='请输入图文的标题']"
CONTENT_AREA = "div[contenteditable='true']"


def human_delay(a=0.3, b=1.2):
    time.sleep(random.uniform(a, b))


class XiumiEditor:
    def __init__(self, page):
        self.page = page

    def fill_title(self, title):
        self.page.locator(TITLE_INPUT).fill(title)

    def type_paragraphs(self, paragraphs):
        """逐段输入纯文本（逐字输入，避免格式丢失）。"""
        area = self.page.locator(CONTENT_AREA).first
        area.click()
        human_delay()
        for i, para in enumerate(paragraphs):
            if not para:
                continue
            self.page.keyboard.type(para, delay=random.randint(40, 90))
            if i < len(paragraphs) - 1:
                self.page.keyboard.press("Enter")
            human_delay(0.3, 0.6)

    def inject_html(self, html):
        """注入带内联样式的 HTML + SVG 排版内容。"""
        area = self.page.locator(CONTENT_AREA).first
        area.click()
        human_delay()
        area.evaluate("(el, h) => { el.innerHTML = h; }", html)
        area.evaluate("el => el.dispatchEvent(new Event('input', {bubbles:true}))")
        human_delay(0.5, 1.0)

    def save(self):
        """点击可见的保存按钮。"""
        btns = self.page.get_by_text("保存", exact=False)
        for i in range(btns.count()):
            if btns.nth(i).is_visible():
                btns.nth(i).click()
                return True
        return False


def main():
    ap = argparse.ArgumentParser(description="秀米编辑器自动化")
    ap.add_argument("--title", required=True, help="图文标题")
    ap.add_argument("--text", help="正文，多段用字面反斜杠 n 分隔（示例: --text \"第一段\\n第二段\"）")
    ap.add_argument("--html-file", help="要注入的 HTML 文件路径")
    ap.add_argument("--no-save", action="store_true", help="只注入不保存")
    ap.add_argument("--keep", type=int, default=180,
                    help="注入后保持浏览器打开的秒数（默认180，0=立即关闭）")
    args = ap.parse_args()

    if not AUTH_FILE.exists():
        print(f"[ERROR] 未找到登录态，请先运行：python {Path(__file__).parent / 'collect_login.py'}")
        return

    html = None
    if args.html_file:
        html = Path(args.html_file).read_text(encoding="utf-8")

    with sync_playwright() as p:
        if not check_available():
            sys.exit(1)
        print(browser_hint(), flush=True)
        browser = p.chromium.launch(headless=False, **LAUNCH_OPTS)
        ctx = browser.new_context(storage_state=str(AUTH_FILE))
        page = ctx.new_page()
        page.goto(EDITOR_URL, wait_until="commit", timeout=30000)
        time.sleep(6)  # 等编辑器完全加载
        # 登录态校验：编辑器标题输入框可见才算登录成功（Cookie 过期时会停留在登录页）
        try:
            page.locator(TITLE_INPUT).wait_for(state="visible", timeout=15000)
        except Exception:
            print("[ERROR] 登录态已失效（未进入编辑器）。请重新运行 collect_login.py 采集登录态。", flush=True)
            browser.close()
            sys.exit(1)
        editor = XiumiEditor(page)
        editor.fill_title(args.title)

        if html:
            editor.inject_html(html)
            print("[OK] HTML 排版已注入", flush=True)
        elif args.text:
            editor.type_paragraphs(args.text.replace("\\n", "\n").split("\n"))
            print("[OK] 正文已输入", flush=True)

        if not args.no_save:
            ok = editor.save()
            if ok:
                print("[OK] 已保存", flush=True)
            else:
                print("[ERROR] 未找到保存按钮，保存失败（页面结构变化或登录态失效），未完成发布。", flush=True)
                browser.close()
                sys.exit(1)

        print(f"浏览器保持打开 {args.keep} 秒，可人工查看效果（Ctrl+C 可提前结束）。", flush=True)
        time.sleep(max(0, args.keep))
        browser.close()


if __name__ == "__main__":
    main()
