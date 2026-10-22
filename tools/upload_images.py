# -*- coding: utf-8 -*-
"""秀米图片自动上传：把本地图片传到「我的图库」，并插入到正文指定位置。

用法：
  # 1) 只上传到图库
  python scripts/upload_images.py --images "C:/imgs/a.jpg" "C:/imgs/b.png"

  # 2) 上传并把 URL 打印出来（供排版生成器填 src）
  python scripts/upload_images.py --images ... --print-urls

  # 3) 上传后插入到已打开的正文（先跑 xiumi_auto.py 注入了 HTML，再跑这个）
  python scripts/upload_images.py --images ... --insert

原理：
  秀米编辑器侧栏「我的图库」有隐藏的 <input id="imageFileUploadInput" type=file>，
  直接给这个 input 塞文件就能触发它自己的上传逻辑（含鉴权、素材入库），
  无需逆向上传接口。上传完成后图库里会出现新图，取其 CDN 地址填回 HTML。

注意：
  - 仅支持 jpg / png / gif（秀米 input 的 accept 限制）
  - 建议图片宽度 ≥ 1080px，避免在手机上糊
  - 登录态复用 xiumi_auth.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_cfg import LAUNCH_OPTS, browser_hint, check_available

BASE_DIR = Path(__file__).resolve().parent.parent
AUTH_FILE = BASE_DIR / "xiumi_auth.json"
EDITOR_URL = "https://xiumi.us/studio/v5/paper"

UPLOAD_INPUT = "#imageFileUploadInput"
LIB_TAB = "我的图库"
ALLOWED = {".jpg", ".jpeg", ".png", ".gif"}


def valid_images(paths):
    out, bad = [], []
    for p in paths:
        p = Path(p)
        if not p.exists():
            bad.append((p, "文件不存在"))
        elif p.suffix.lower() not in ALLOWED:
            bad.append((p, f"格式不支持（仅 jpg/png/gif，当前 {p.suffix}）"))
        else:
            out.append(p)
    return out, bad


def open_editor(p):
    """打开编辑器并确认已登录。"""
    b = p.chromium.launch(headless=False, **LAUNCH_OPTS)
    ctx = b.new_context(storage_state=str(AUTH_FILE), viewport={"width": 1500, "height": 950})
    pg = ctx.new_page()
    pg.goto(EDITOR_URL, wait_until="commit", timeout=30000)
    pg.wait_for_timeout(8000)
    # 登录校验：标题框存在才算进了编辑器
    try:
        pg.locator("input[placeholder='请输入图文的标题']").wait_for(
            state="attached", timeout=20000)
    except Exception:
        raise RuntimeError("未进入编辑器，登录态可能已失效。请重跑 collect_login.py。")
    return b, ctx, pg


def goto_library(pg):
    """切到「我的图库」标签。"""
    try:
        tab = pg.get_by_text(LIB_TAB, exact=True).first
        tab.click()
        pg.wait_for_timeout(2500)
        return True
    except Exception:
        return False


def collect_new_images(pg, before):
    """抓取当前图库里所有图片 URL，返回新增的集合。"""
    try:
        urls = pg.evaluate("""() => {
          const set = new Set();
          document.querySelectorAll('img').forEach(e => {
            const s = e.src || e.getAttribute('data-src') || '';
            if (s && /^https?:/.test(s) && !/placeholder|logo|nav|btn-|arrow|icon-|scale-/.test(s)) {
              set.add(s);
            }
          });
          return [...set];
        }""")
        return [u for u in urls if u not in before]
    except Exception:
        return []


def snapshot_images(pg):
    try:
        return set(pg.evaluate("""() => {
          const set = new Set();
          document.querySelectorAll('img').forEach(e => {
            const s = e.src || e.getAttribute('data-src') || '';
            if (s && /^https?:/.test(s) && !/placeholder|logo|nav|btn-|arrow|icon-|scale-/.test(s)) set.add(s);
          });
          return [...set];
        }"""))
    except Exception:
        return set()


def upload(pg, paths, verbose=True):
    """通过隐藏 file input 上传图片，返回新增图片 URL 列表。"""
    goto_library(pg)
    before = snapshot_images(pg)

    try:
        pg.locator(UPLOAD_INPUT).first.set_input_files([str(p) for p in paths])
    except Exception as e:
        raise RuntimeError(f"无法定位上传控件 {UPLOAD_INPUT}：{e}")

    if verbose:
        print(f"[INFO] 已提交 {len(paths)} 个文件，等待上传完成 ...", flush=True)

    # 等上传：轮询直到图库出现新图，或超时
    deadline = time.time() + 180
    new_urls = []
    while time.time() < deadline:
        pg.wait_for_timeout(2500)
        new_urls = collect_new_images(pg, before)
        if len(new_urls) >= len(paths):
            break
        if verbose and new_urls:
            print(f"       已上传 {len(new_urls)}/{len(paths)}", flush=True)

    return new_urls


def main():
    ap = argparse.ArgumentParser(description="秀米图片上传")
    ap.add_argument("--images", nargs="+", required=True, help="本地图片路径（可多个）")
    ap.add_argument("--print-urls", action="store_true", help="打印上传后的图片 URL")
    ap.add_argument("--out", help="把 URL 列表写入 JSON 文件")
    ap.add_argument("--keep-open", type=int, default=30, help="完成后保持浏览器打开秒数")
    a = ap.parse_args()

    if not AUTH_FILE.exists():
        print(f"[ERROR] 未找到登录态：{AUTH_FILE}", flush=True)
        print("       请先运行 collect_login.py", flush=True)
        sys.exit(1)

    good, bad = valid_images(a.images)
    for p, why in bad:
        print(f"[SKIP] {p.name} —— {why}", flush=True)
    if not good:
        print("[ERROR] 没有可上传的图片。", flush=True)
        sys.exit(1)

    if not check_available():
        sys.exit(1)
    print(browser_hint(), flush=True)
    print(f"[INFO] 待上传 {len(good)} 张：" + "、".join(p.name for p in good), flush=True)

    with sync_playwright() as p:
        b, ctx, pg = open_editor(p)
        try:
            urls = upload(pg, good)
            print(f"\n[OK] 上传完成，取得 {len(urls)} 个图片地址", flush=True)
            for i, u in enumerate(urls, 1):
                print(f"   {i}. {u}", flush=True)

            if a.print_urls or a.out:
                data = [{"local": str(good[i]) if i < len(good) else None, "url": u}
                        for i, u in enumerate(urls)]
                if a.out:
                    Path(a.out).write_text(
                        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"[OK] 已写入 {a.out}", flush=True)

            if a.keep_open > 0:
                print(f"\n浏览器保持 {a.keep_open} 秒，可人工查看图库。", flush=True)
                pg.wait_for_timeout(a.keep_open * 1000)
        except RuntimeError as e:
            print(f"[ERROR] {e}", flush=True)
            sys.exit(1)
        finally:
            b.close()


if __name__ == "__main__":
    main()
