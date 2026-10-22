# -*- coding: utf-8 -*-
"""南邮学生会/学代会通稿排版生成器（秀米路径）

风格来源：https://mp.weixin.qq.com/s/Xedtvq5OK8SzU_x8-HRvSQ （南邮计软网安学代会）
风格代号：nanyou-gongshanghui-hong

日常用法（不带参数就走 gonggao_data.json）：
    python build_gonggao.py              # 生成 layout_final.html
    python build_gonggao.py --check      # 只检查待填占位与图片
    python build_gonggao.py --inject     # 生成后注入秀米（演练，不保存）
    python build_gonggao.py --inject --save   # 生成后注入并保存

Windows 用户可直接双击同目录下的 1~4 号 .bat。
秀米路径说明：秀米不清洗 SVG，可用矢量装饰；
若改走微信后台，需调用 wechat=True 分支（纯 CSS 卡片版）。
"""
import argparse
import json
import re
import subprocess
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _find_xiumi_script():
    """注入脚本查找顺序：本机已装的 skill 优先，其次仓库自带的 tools/。

    两者都认自己上一级目录的 xiumi_auth.json，所以不能混用。
    """
    for c in (Path(r"C:\Users\weitian\.workbuddy\skills\gzh-content\scripts\xiumi_auto.py"),
              HERE / "tools" / "xiumi_auto.py"):
        if c.exists():
            return c
    return HERE / "tools" / "xiumi_auto.py"


XIUMI_SCRIPT = _find_xiumi_script()

# ---------- 设计 token（来自参考推文实测） ----------
RED = "rgb(181, 16, 17)"          # 主色 深红
RED_HEX = "#B51011"
RED2 = "rgb(154, 67, 53)"         # 深棕红
CREAM = "rgb(245, 221, 201)"      # 米杏 描边
CARD_BG = "rgb(254, 253, 252)"    # 暖白卡片底
ALT_BG = "rgb(254, 250, 248)"     # 交替段底
BROWN = "rgb(86, 24, 14)"         # 深棕文字
TEXT = "rgb(62, 62, 62)"          # 正文
RED_BRIGHT = "rgb(232, 33, 36)"   # 亮红点缀
GOLD = "rgb(255, 199, 90)"        # 金黄

FONT = ("&quot;Noto Sans CJK SC&quot;, -apple-system-font, BlinkMacSystemFont, "
        "&quot;Helvetica Neue&quot;, &quot;PingFang SC&quot;, &quot;Hiragino Sans GB&quot;, "
        "&quot;Microsoft YaHei UI&quot;, &quot;Microsoft YaHei&quot;, Arial, sans-serif")

BOX = "box-sizing:border-box;"


def _t(s):
    return s if s is not None else ""


# ---------- 基础组件 ----------

def deco_arrow(color=RED, w=9, h=14):
    """三角箭头装饰（参考推文字面还原）。

    必须是 span 而非 section —— 它要放进 <p> 里，
    块级元素会触发浏览器隐式闭合 <p>，把后面的 DOM 结构冲散。
    """
    return (f'<span style="display:inline-block;width:{w}px;height:{h}px;'
            f'vertical-align:middle;overflow:hidden;'
            f'border-style:solid;border-width:{w}px 0px {w}px 7px;'
            f'border-color:transparent transparent transparent {color};{BOX}"></span>')


def deco_dot(color=RED, size=7):
    """7x7 实心方块点缀（同样用 span，避免在 <p> 内破坏结构）。"""
    return (f'<span style="display:inline-block;width:{size}px;height:{size}px;'
            f'vertical-align:middle;overflow:hidden;background-color:{color};{BOX}"></span>')


def title_bar(text, color=RED, fg="#ffffff", size=16, sub=False):
    """分段标题条：红底白字（参考推文的「大会选举结果」样式）。

    用 inline-block + 箭头 inline 排布，长标题可正常换行/撑开，
    不依赖 flex，避免宽标题被压缩。
    """
    col = RED2 if sub else color
    return (f'<section style="text-align:center;margin:26px 0 16px 0;{BOX}">'
            f'<section style="display:inline-block;background:{col};'
            f'border-radius:4px;padding:7px 16px;{BOX}">'
            f'<p style="color:{fg};font-size:{size}px;font-weight:bold;'
            f'margin:0;line-height:1.4;{BOX}">'
            f'<span style="display:inline-block;vertical-align:middle;">'
            f'{deco_arrow(fg, 7, 12)}</span>'
            f'<span style="display:inline-block;vertical-align:middle;padding:0 8px;">'
            f'{escape(_t(text))}</span>'
            f'<span style="display:inline-block;vertical-align:middle;">'
            f'{deco_arrow(fg, 7, 12)}</span>'
            f'</p></section></section>')


def card(inner, bg=CARD_BG, padding=20, dotted=True, align="left"):
    """官方感内容卡片：暖白底 + 米杏点线框 + 同色外发光（参考推文核心容器）。"""
    border = (f'border:1px dotted {CREAM};border-radius:5px;' if dotted else '')
    shadow = f'box-shadow:{CREAM} 0px 0px 2px 1px;'
    return (f'<section style="text-align:center;margin:18px 0;{BOX}">'
            f'<section style="display:inline-block;width:92%;vertical-align:top;'
            f'align-self:flex-start;background:{bg};padding:2px;{shadow}{BOX}">'
            f'<section style="width:100%;{border}overflow:hidden;padding:{padding}px;'
            f'text-align:{align};{BOX}">'
            f'{inner}</section></section></section>')


def para(text, indent=True, color=TEXT, size=14, align="justify", line=1.85, margin="0 0 14px"):
    ind = "text-indent:2.1429em;" if indent else "text-indent:0em;"
    return (f'<p style="color:{color};font-size:{size}px;line-height:{line};'
            f'text-align:{align};{ind}margin:{margin};{BOX}">{_t(text)}</p>')


def name_grid(names, per_row=5, size=14, color=TEXT):
    """名单区块：居中、全角空格分隔、每行 N 人（参考推文选举名单样式）。"""
    if not names:
        return ""
    rows, cur = [], []
    for n in names:
        cur.append(n)
        if len(cur) == per_row:
            rows.append(cur)
            cur = []
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        line = "　".join(escape(str(x)) for x in r)
        out.append(f'<p style="color:{color};font-size:{size}px;line-height:1.9;'
                   f'text-align:center;margin:0 0 6px;{BOX}">{line}</p>')
    return "".join(out)


def sort_note(text="（按姓氏笔画排序）："):
    return (f'<p style="color:{RED2};font-size:13px;text-align:center;'
            f'margin:0 0 10px;{BOX}">{escape(text)}</p>')


def divider(color="rgba(255,108,83,0.40)", style="dashed"):
    return (f'<section style="margin:22px 0;{BOX}">'
            f'<section style="border-top:1px {style} {color};height:0;{BOX}"></section></section>')


def section_label(text, bg="rgba(255,108,83,0.23)", color=RED2, size=13):
    """浅橙底分类标签 chip。"""
    return (f'<section style="text-align:center;margin:12px 0;{BOX}">'
            f'<section style="display:inline-block;background:{bg};border-radius:12px;'
            f'padding:3px 14px;{BOX}">'
            f'<p style="color:{color};font-size:{size}px;margin:0;line-height:1.6;{BOX}">'
            f'{escape(_t(text))}</p></section></section>')


def four_points(points):
    """领导期望四条：红色序号块 + 四字格短句排比。"""
    out = []
    for i, p in enumerate(points, 1):
        out.append(
            f'<section style="display:table;width:100%;table-layout:fixed;'
            f'margin:0 0 12px;{BOX}">'
            f'<section style="display:table-cell;width:32px;vertical-align:top;{BOX}">'
            f'<section style="width:22px;height:22px;background:{RED};'
            f'border-radius:4px;{BOX}">'
            f'<p style="color:#ffffff;font-size:13px;font-weight:bold;text-align:center;'
            f'line-height:22px;margin:0;{BOX}">{i}</p></section></section>'
            f'<section style="display:table-cell;vertical-align:top;padding-left:10px;{BOX}">'
            f'<p style="color:{BROWN};font-size:14px;line-height:1.8;margin:0;'
            f'text-align:justify;{BOX}">{escape(_t(p))}</p></section></section>')
    return "".join(out)


# ============ 扩展组件库（文字排版多样化） ============

def banner_hero(text, sub="", bg=None, size=22, pad=30):
    """整幅渐变大横幅：主视觉开场，压得住。"""
    g = bg or f"linear-gradient(135deg,{RED} 0%,{RED2} 100%)"
    s = (f'<p style="color:#ffffff;font-size:12px;margin:6px 0 0;'
         f'letter-spacing:3px;opacity:0.9;{BOX}">{escape(_t(sub))}</p>') if sub else ""
    return (f'<section style="text-align:center;margin:0 0 22px 0;{BOX}">'
            f'<section style="background:{g};border-radius:8px;padding:{pad}px 16px;{BOX}">'
            f'<p style="color:#ffffff;font-size:{size}px;font-weight:bold;line-height:1.5;'
            f'margin:0;letter-spacing:1px;{BOX}">{escape(_t(text))}</p>{s}</section></section>')


def section_no(no, text, sub=""):
    """大号序号章节头：01 + 标题 + 细线，适合多段落长文。

    注意：序号用固定宽度独立块 + 禁止收缩（flex-shrink:0），
    否则大字号数字会被右侧标题挤压导致重叠。
    """
    s = (f'<p style="color:{RED2};font-size:12px;margin:3px 0 0;line-height:1.2;'
         f'letter-spacing:0.5px;{BOX}">{escape(_t(sub))}</p>') if sub else ""
    return (f'<section style="margin:32px 0 16px 0;{BOX}">'
            f'<section style="display:table;width:100%;table-layout:fixed;{BOX}">'
            f'<section style="display:table-cell;width:62px;vertical-align:bottom;{BOX}">'
            f'<p style="color:{RED};font-size:32px;font-weight:bold;line-height:1;'
            f'margin:0;letter-spacing:0;white-space:nowrap;{BOX}">{escape(_t(no))}</p></section>'
            f'<section style="display:table-cell;vertical-align:bottom;padding-left:10px;{BOX}">'
            f'<p style="color:{BROWN};font-size:17px;font-weight:bold;margin:0;'
            f'line-height:1.3;{BOX}">{escape(_t(text))}</p>{s}</section></section>'
            f'<section style="border-bottom:2px solid {CREAM};margin-top:8px;{BOX}"></section>'
            f'</section>')


def quote_block(text, source=""):
    """金句/引文块：深红左边框 + 浅底 + 斜体，强化核心表述。"""
    s = (f'<p style="color:{RED2};font-size:12px;margin:8px 0 0;text-align:right;{BOX}">'
         f'—— {escape(_t(source))}</p>') if source else ""
    return (f'<section style="margin:18px 0;{BOX}">'
            f'<section style="border-left:4px solid {RED};background:{ALT_BG};'
            f'padding:14px 16px;border-radius:0 6px 6px 0;{BOX}">'
            f'<p style="color:{BROWN};font-size:14.5px;line-height:1.85;margin:0;'
            f'text-align:justify;{BOX}">{escape(_t(text))}</p>{s}</section></section>')


def highlight(text, label="要点"):
    """荧光笔式重点段：整段浅黄底 + 左侧标签。"""
    return (f'<section style="margin:16px 0;{BOX}">'
            f'<section style="background:rgba(255,199,90,0.22);border-radius:6px;'
            f'padding:12px 14px;display:table;width:100%;{BOX}">'
            f'<section style="display:table-cell;width:1%;white-space:nowrap;'
            f'vertical-align:top;{BOX}">'
            f'<section style="background:{GOLD};border-radius:3px;padding:2px 0;'
            f'text-align:center;{BOX}">'
            f'<p style="color:#5a3a00;font-size:12px;font-weight:bold;margin:0;{BOX}">'
            f'{escape(_t(label))}</p></section></section>'
            f'<section style="display:table-cell;vertical-align:top;padding-left:10px;{BOX}">'
            f'<p style="color:{BROWN};font-size:14px;line-height:1.8;margin:0;'
            f'text-align:justify;{BOX}">{escape(_t(text))}</p>'
            f'</section></section></section>')


def stat_row(stats):
    """数据亮点条：等宽数字卡。stats = [(数字, 说明), ...]"""
    n = len(stats) or 1
    w = f"{100/n:.1f}"
    cells = []
    for num, desc in stats:
        cells.append(
            f'<section style="display:inline-block;width:{w}%;vertical-align:top;'
            f'padding:0 4px;box-sizing:border-box;{BOX}">'
            f'<section style="background:{CARD_BG};border:1px dotted {CREAM};'
            f'border-radius:6px;padding:14px 4px;{BOX}">'
            f'<p style="color:{RED};font-size:24px;font-weight:bold;line-height:1.2;'
            f'margin:0;{BOX}">{escape(_t(num))}</p>'
            f'<p style="color:{TEXT};font-size:12px;margin:4px 0 0;line-height:1.5;{BOX}">'
            f'{escape(_t(desc))}</p></section></section>')
    return (f'<section style="margin:18px 0;{BOX}">'
            f'<section style="font-size:0;text-align:center;{BOX}">'
            f'{"".join(cells)}</section></section>')


def timeline(items):
    """时间/流程轴：左侧竖线 + 圆点节点。items = [(时间/环节, 内容), ...]"""
    rows = []
    for i, (k, v) in enumerate(items):
        dot = (f'<section style="flex:0 0 auto;width:9px;height:9px;border-radius:50%;'
               f'background:{RED};margin-top:6px;{BOX}"></section>'
               f'<section style="flex:0 0 auto;width:2px;background:{CREAM};'
               f'margin:0 0 0 3.5px;{BOX}"></section>')
        if i == len(items) - 1:
            dot = (f'<section style="flex:0 0 auto;width:9px;height:9px;border-radius:50%;'
                   f'background:{RED};margin-top:6px;{BOX}"></section>'
                   f'<section style="flex:0 0 auto;width:2px;{BOX}"></section>')
        rows.append(
            f'<section style="display:flex;align-items:stretch;{BOX}">{dot}'
            f'<section style="flex:1 1 auto;padding:0 0 16px 12px;text-align:left;{BOX}">'
            f'<p style="color:{RED};font-size:13px;font-weight:bold;margin:0 0 2px;'
            f'text-align:left;{BOX}">{escape(_t(k))}</p>'
            f'<p style="color:{TEXT};font-size:13.5px;line-height:1.75;margin:0;'
            f'text-align:justify;{BOX}">{escape(_t(v))}</p></section></section>')
    return (f'<section style="margin:18px 0;padding-left:4px;text-align:left;{BOX}">'
            f'{"".join(rows)}</section>')


def _to_src(img):
    """把图片引用转成可用的 src。

    - http(s) 开头：原样返回（秀米图库 CDN 地址）
    - 本地路径：转 base64 data URI（内联进 HTML，避免秀米拒绝加载本地文件）
    """
    if not img:
        return ""
    if img.startswith("http"):
        return img
    p = Path(img)
    if not p.exists():
        return ""
    import base64
    ext = p.suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif"}.get(ext, "png")
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:image/{mime};base64,{b64}"


def photo_wide(caption="", ratio="16:9", img=""):
    """单图通栏 + 图注。给了 img 就渲染真图，否则出占位框。"""
    h = {"16:9": 168, "4:3": 200, "3:4": 240, "1:1": 240}.get(ratio, 168)
    src = _to_src(img)
    if src:
        inner = (f'<img src="{src}" style="max-width:100%;width:100%;'
                 f'display:block;{BOX}"/>')
    else:
        inner = (f'<section style="display:flex;align-items:center;justify-content:center;'
                 f'height:{h}px;{BOX}">'
                 f'<p style="color:#b9a99a;font-size:13px;margin:0;{BOX}">'
                 f'【配图：{escape(_t(caption) or "待上传")}】</p></section>')
    return (f'<section style="text-align:center;margin:16px 0;{BOX}">'
            f'<section style="background:{ALT_BG};border:1px dotted {CREAM};'
            f'border-radius:6px;overflow:hidden;{BOX}">{inner}'
            f'<section style="padding:8px;{BOX}">'
            f'<p style="color:{RED2};font-size:12px;text-align:center;margin:0;'
            f'line-height:1.6;{BOX}">{escape(_t(caption))}</p></section></section></section>')


def photo_grid(captions, per_row=3, imgs=None):
    """图片网格 + 图注。imgs 与 captions 按序对应，不足处出占位框。"""
    n = len(captions) or 1
    w = f"{100/per_row:.1f}"
    imgs = imgs or []
    cells = []
    for i, cap in enumerate(captions):
        src = _to_src(imgs[i]) if i < len(imgs) else ""
        if src:
            body = (f'<img src="{src}" style="max-width:100%;width:100%;'
                    f'display:block;{BOX}"/>')
        else:
            body = (f'<section style="display:flex;align-items:center;justify-content:center;'
                    f'height:88px;{BOX}">'
                    f'<p style="color:#b9a99a;font-size:12px;margin:0;{BOX}">图片</p></section>')
        cells.append(
            f'<section style="display:inline-block;width:{w}%;vertical-align:top;'
            f'padding:0 4px 8px 4px;box-sizing:border-box;{BOX}">'
            f'<section style="width:100%;background:{ALT_BG};border:1px dotted {CREAM};'
            f'border-radius:5px;overflow:hidden;{BOX}">{body}'
            f'<section style="padding:6px 4px;{BOX}">'
            f'<p style="color:{TEXT};font-size:11.5px;line-height:1.5;text-align:center;'
            f'margin:0;{BOX}">{escape(_t(cap))}</p></section></section></section>')
    return (f'<section style="margin:16px 0;{BOX}">'
            f'<section style="font-size:0;{BOX}">{"".join(cells)}</section></section>')


def kv_list(pairs, label_color=None):
    """双列信息表：左标签右内容，行间点线分隔。"""
    lc = label_color or RED2
    rows = []
    for k, v in pairs:
        rows.append(
            f'<section style="display:table;width:100%;table-layout:fixed;'
            f'border-bottom:1px dotted {CREAM};padding:8px 0;{BOX}">'
            f'<section style="display:table-cell;width:84px;vertical-align:top;{BOX}">'
            f'<p style="color:{lc};font-size:13px;font-weight:bold;margin:0;{BOX}">'
            f'{escape(_t(k))}</p></section>'
            f'<section style="display:table-cell;vertical-align:top;padding-left:10px;{BOX}">'
            f'<p style="color:{TEXT};font-size:13.5px;line-height:1.7;margin:0;'
            f'text-align:justify;{BOX}">{escape(_t(v))}</p></section></section>')
    return (f'<section style="margin:16px 0;{BOX}">' + "".join(rows) + '</section>')


def tag_row(tags):
    """标签行：浅橙底圆角 chip 若干。"""
    t = "".join(
        f'<section style="display:inline-block;background:rgba(255,108,83,0.23);'
        f'border-radius:12px;padding:4px 14px;margin:0 6px 8px 0;{BOX}">'
        f'<p style="color:{RED2};font-size:12.5px;margin:0;{BOX}">{escape(_t(x))}</p></section>'
        for x in tags)
    return f'<section style="margin:14px 0;font-size:0;{BOX}">{t}</section>'


def badge_num(text, color=None):
    """红色斜角徽标：用于「重要」「必看」类提示。"""
    c = color or RED
    return (f'<section style="text-align:center;margin:14px 0;{BOX}">'
            f'<section style="display:inline-block;background:{c};border-radius:4px;'
            f'padding:5px 22px;transform:skewX(-12deg);{BOX}">'
            f'<p style="color:#ffffff;font-size:13px;font-weight:bold;margin:0;'
            f'letter-spacing:2px;transform:skewX(12deg);{BOX}">{escape(_t(text))}</p>'
            f'</section></section>')


def closing_quote(text):
    """结尾大金句：居中 + 上下双线框。"""
    return (f'<section style="margin:26px 0;{BOX}">'
            f'<section style="border-top:1px solid {CREAM};margin-bottom:16px;{BOX}"></section>'
            f'<p style="color:{RED};font-size:16px;font-weight:bold;line-height:1.8;'
            f'text-align:center;margin:0 0 16px;padding:0 12px;{BOX}">{escape(_t(text))}</p>'
            f'<section style="border-top:1px solid {CREAM};{BOX}"></section></section>')


def svg_corner(w=64, h=64, color=RED):
    """SVG 折角装饰：秀米路径可用矢量。"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" style="display:block;">'
            f'<path d="M0,0 L{w},0 L0,{h} Z" fill="{color}" opacity="0.10"/></svg>')


def wave_sep(color=CREAM, height=14):
    """波浪分隔（SVG）：秀米专用，微信会清洗。"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 {height}" '
            f'width="100%" style="display:block;margin:18px 0;">'
            f'<path d="M0,7 Q12.5,1 25,7 T50,7 T75,7 T100,7 T125,7 T150,7 T175,7 '
            f'T200,7 T225,7 T250,7 T275,7 T300,7" fill="none" stroke="{color}" '
            f'stroke-width="1.5"/></svg>')


def table_grid(header, rows, widths=None):
    """正式表格：红底白字表头 + 点线行分隔。"""
    n = len(header) or 1
    ws = widths or [f"{100/n:.1f}"] * n
    th = "".join(
        f'<section style="display:inline-block;width:{w}%;vertical-align:top;{BOX}">'
        f'<section style="background:{RED};padding:8px 4px;{BOX}">'
        f'<p style="color:#ffffff;font-size:13px;font-weight:bold;text-align:center;'
        f'margin:0;{BOX}">{escape(_t(h))}</p></section>'
        f'<section style="border-bottom:1px dotted {CREAM};padding:8px 4px;{BOX}">'
        f'<p style="color:{TEXT};font-size:12.5px;text-align:center;line-height:1.6;'
        f'margin:0;{BOX}"></p></section></section>'
        for h, w in zip(header, ws))
    body = []
    for r in rows:
        cells = "".join(
            f'<section style="display:inline-block;width:{w}%;vertical-align:top;{BOX}">'
            f'<section style="border-bottom:1px dotted {CREAM};padding:8px 4px;{BOX}">'
            f'<p style="color:{TEXT};font-size:12.5px;text-align:center;line-height:1.6;'
            f'margin:0;{BOX}">{escape(_t(c))}</p></section></section>'
            for c, w in zip(r, ws))
        body.append(f'<section style="font-size:0;{BOX}">{cells}</section>')
    return (f'<section style="margin:18px 0;{BOX}">'
            f'<section style="font-size:0;{BOX}">{th}</section>'
            f'{"".join(body)}</section>')


def end_block(editor, first, second, third, org="学生会"):
    """结尾：End + 编辑/一审/二审/三审 署名。"""
    rows = [("编辑", editor), ("一审", first), ("二审", second), ("三审", third)]
    body = []
    for k, v in rows:
        body.append(
            f'<p style="color:{TEXT};font-size:13px;line-height:1.9;margin:0;{BOX}">'
            f'{escape(k)}&nbsp;&nbsp;|&nbsp;&nbsp;{escape(_t(v) if v else "【待填】")}</p>')
    return (f'<section style="margin:20px 0 8px 0;{BOX}">'
            f'<p style="color:{RED};font-size:14px;font-weight:bold;text-align:center;'
            f'margin:0 0 14px;letter-spacing:2px;{BOX}">End</p>'
            f'<section style="text-align:right;{BOX}">' + "".join(body) + '</section></section>')


def header_banner(img_url="", height=None):
    """页头固定横幅位：填入 img_url 即出图，留空则出红色占位条。"""
    if img_url:
        h = f'height:{height}px;' if height else ''
        return (f'<section style="text-align:center;margin:0 0 20px 0;{BOX}">'
                f'<img src="{escape(img_url)}" style="max-width:100%;width:100%;{h}{BOX}"/></section>')
    return (f'<section style="text-align:center;margin:0 0 20px 0;{BOX}">'
            f'<section style="display:inline-block;width:92%;background:linear-gradient(135deg,{RED},{RED2});'
            f'border-radius:6px;padding:18px 12px;{BOX}">'
            f'<p style="color:#ffffff;font-size:13px;margin:0;letter-spacing:1px;{BOX}">'
            f'【此处放学院/学校固定页头图】</p></section></section>')


def footer_card(qr_text="【落款与二维码】", note=""):
    """页尾暖白落款卡：落款名 + 二维码占位框。

    署名（编辑/一审…）不在这里，由 end_block 在页面最底部统一输出，避免重复。
    """
    name = (f'<p style="color:{RED2};font-size:14px;font-weight:bold;margin:0 0 10px;'
            f'letter-spacing:2px;text-align:center;{BOX}">{escape(_t(qr_text))}</p>'
            if qr_text else "")
    inner = (f'<section style="text-align:center;{BOX}">{name}'
             f'<section style="display:inline-block;width:96px;height:96px;'
             f'background:{ALT_BG};border:1px dotted {CREAM};border-radius:6px;{BOX}">'
             f'<p style="color:#b9a99a;font-size:11px;line-height:96px;margin:0;{BOX}">'
             f'二维码</p></section>')
    if note:
        inner += (f'<section style="margin-top:10px;{BOX}">'
                  f'<p style="color:{RED2};font-size:12px;margin:0;{BOX}">{escape(note)}</p></section>')
    inner += "</section>"
    return card(inner, padding=18)


# ---------- 内容自检 ----------

PLACEHOLDER_RE = re.compile(r"【[^】]*】")


def _walk_strings(obj, path="", out=None):
    """递归收集 (路径, 字符串)。跳过 _ 开头的说明键。"""
    if out is None:
        out = []
    if isinstance(obj, str):
        out.append((path or "(根)", obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue
            _walk_strings(v, f"{path}.{k}" if path else str(k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_strings(v, f"{path}[{i}]", out)
    return out


def _collect_images(obj, path="", out=None):
    """递归收集图片引用 (路径, 值)。"""
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue
            cur = f"{path}.{k}" if path else str(k)
            if k == "img" and isinstance(v, str) and v.strip():
                out.append((cur, v.strip()))
            elif k == "imgs" and isinstance(v, list):
                for i, x in enumerate(v):
                    if isinstance(x, str) and x.strip():
                        out.append((f"{cur}[{i}]", x.strip()))
            else:
                _collect_images(v, cur, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _collect_images(v, f"{path}[{i}]", out)
    return out


def lint_html(html):
    """结构自检：揪出属性引号未闭合。

    这类错误不会报错，但浏览器会把后续整段 HTML 当成属性值吞掉，
    表现为「名单只显示一半」「后面的块莫名嵌进上一个卡片」。
    """
    return re.findall(r'<[a-zA-Z][^>]*?\s(?:style|class|id|src|href)="[^">]*>', html)


def check_content(d, base_dir=HERE):
    """返回 (待填项列表, 图片问题列表)。待填项 = (位置, 占位符, 所在原文)。"""
    todo = []
    for path, s in _walk_strings(d):
        for m in PLACEHOLDER_RE.finditer(s):
            todo.append((path, m.group(), s))
    img_bad = []
    for path, ref in _collect_images(d):
        if ref.startswith(("http://", "https://", "data:")):
            continue
        p = Path(ref)
        if not p.is_absolute():
            p = base_dir / ref
        if not p.exists():
            img_bad.append((path, ref))
    return todo, img_bad


def print_check(d, detailed=False, base_dir=HERE):
    """打印自检结果，返回待填数量。detailed=False 时只给一行汇总。"""
    todo, img_bad = check_content(d, base_dir)

    if not todo:
        print("\n[待填] 无，内容已填完 ✓")
    elif not detailed:
        print(f"\n[待填] 还有 {len(todo)} 处占位（跑 --check 看具体在哪）")
    else:
        groups = {}
        for path, ph, s in todo:
            groups.setdefault(path, []).append((ph, s))
        print(f"\n[待填] {len(todo)} 处占位，{len(groups)} 个位置：")
        for path, items in groups.items():
            print(f"  · {path}  （{len(items)} 处）")
            seen = []
            for ph, s in items:
                if s in seen:
                    continue
                seen.append(s)
                t = s if len(s) <= 70 else s[:68] + "…"
                print(f"      {t}")

    if img_bad:
        print(f"\n[图片] {len(img_bad)} 处引用找不到文件（会渲染成占位框）：")
        for path, ref in img_bad:
            print(f"  · {path:<22} {ref}")
    elif _collect_images(d):
        print("[图片] 全部存在 ✓")
    return len(todo)


# ---------- 通用块渲染 ----------

def render_block(b):
    """把一个块字典渲染成 HTML。未知 type 或缺 type 时按段落处理。"""
    if isinstance(b, str):
        return para(b)
    t = b.get("type")
    if t == "p":
        return para(b.get("text", ""), indent=b.get("indent", True),
                    color=b.get("color", TEXT), size=b.get("size", 14))
    if t == "quote":
        return quote_block(b.get("text", ""), b.get("source", ""))
    if t == "highlight":
        return highlight(b.get("text", ""), b.get("label", "要点"))
    if t == "image":
        return photo_wide(b.get("caption", ""), b.get("ratio", "16:9"), b.get("img", ""))
    if t == "photos":
        return photo_grid(b.get("captions", []), b.get("per_row", 3), b.get("imgs"))
    if t == "table":
        return table_grid(b.get("header", []), b.get("rows", []), b.get("widths"))
    if t == "kv":
        return kv_list([tuple(x) for x in b.get("pairs", [])])
    if t == "stats":
        return stat_row([tuple(x) for x in b.get("items", [])])
    if t == "points":
        return card(four_points(b.get("items", [])))
    if t == "tags":
        return tag_row(b.get("items", []))
    if t == "bar":
        return title_bar(b.get("text", ""), sub=b.get("sub", False))
    if t == "badge":
        return badge_num(b.get("text", ""))
    if t == "names":
        g = b
        out = title_bar(g.get("title", "【待填】"))
        if g.get("sub"):
            out += (f'<p style="color:{RED2};font-size:15px;text-align:center;'
                    f'margin:0 0 4px 0;{BOX}">{escape(g["sub"])}</p>')
        if g.get("sub2"):
            out += (f'<p style="color:{RED2};font-size:14px;text-align:center;'
                    f'margin:0 0 8px 0;{BOX}">{escape(g["sub2"])}</p>')
        out += card(sort_note() + name_grid(g.get("names", []), per_row=g.get("per_row", 5)))
        return out
    if t == "divider":
        return divider()
    if t == "wave":
        return wave_sep()
    if t == "closing":
        return closing_quote(b.get("text", ""))
    if t == "raw":
        return b.get("html", "")
    return para(str(b.get("text", b)))


# ---------- 整页组装 ----------

def build_page(d):
    """d 为内容字典。

    可用键（全部可选，缺失即跳过）：
      title / header_img / footer_qr
      hero              开场渐变横幅 {"text","sub"}
      paragraphs        正文段落列表
      stats             数据亮点 [("33名","学生代表")]
      quote             金句引文 {"text","source"}
      highlight         荧光重点段 [{"text","label"}]
      timeline          时间流程轴 [("环节一","内容")]
      sections          序号章节 [{"no":"01","title","sub","blocks":[...]}]
      dims              工作报告四维度
      points            领导寄语四条
      table             正式表格 {"header":[...],"rows":[[...]]}
      kv                双列信息表 [("时间","...")]
      tags              标签行
      name_groups       名单区块
      badge             斜角徽标文字
      photos            三图网格 ["图注",...]
      photo             通栏图 {"caption","ratio"}
      closing           结尾金句
      ending            结尾升华段
      editor/first/second/third  署名
    """
    P = parts = []

    # ---- 页头 ----
    if d.get("header_img"):
        P.append(header_banner(d["header_img"]))

    # ---- 开场渐变横幅（可选）----
    if d.get("hero"):
        h = d["hero"]
        P.append(banner_hero(h.get("text", d.get("title", "")), h.get("sub", "")))

    # ---- 主标题区 ----
    if d.get("title") and not d.get("hero"):
        P.append(
            f'<section style="text-align:center;margin:22px 0 6px 0;{BOX}">'
            f'<p style="color:{RED};font-size:19px;font-weight:bold;line-height:1.6;'
            f'margin:0;letter-spacing:0.5px;{BOX}">{escape(_t(d["title"]))}</p></section>')
        P.append(
            f'<section style="text-align:center;margin:0 0 22px 0;{BOX}">'
            f'<section style="display:inline-block;{BOX}">{deco_dot(RED, 7)}</section>'
            f'<section style="display:inline-block;margin:0 8px;{BOX}">'
            f'<section style="border-top:2px solid {RED};width:36px;height:0;{BOX}"></section></section>'
            f'<section style="display:inline-block;{BOX}">{deco_dot(RED, 7)}</section></section>')

    # ---- 徽标 ----
    if d.get("badge"):
        P.append(badge_num(d["badge"]))

    # ---- 标签行 ----
    if d.get("tags"):
        P.append(tag_row(d["tags"]))

    # ---- 数据亮点 ----
    if d.get("stats"):
        P.append(stat_row([tuple(x) for x in d["stats"]]))

    # ---- 正文段落 ----
    for p in d.get("paragraphs", []):
        P.append(para(p))

    # ---- 金句引文 ----
    if d.get("quote"):
        q = d["quote"]
        P.append(quote_block(q.get("text", q) if isinstance(q, dict) else q,
                             q.get("source", "") if isinstance(q, dict) else ""))

    # ---- 荧光重点 ----
    for hl in d.get("highlight", []):
        if isinstance(hl, dict):
            P.append(highlight(hl.get("text", ""), hl.get("label", "要点")))
        else:
            P.append(highlight(hl))

    # ---- 时间流程轴 ----
    if d.get("timeline"):
        P.append(title_bar("活动流程"))
        P.append(card(timeline([tuple(x) for x in d["timeline"]])))

    # ---- 序号章节 ----
    for sec in d.get("sections", []):
        P.append(section_no(sec.get("no", "01"), sec.get("title", ""), sec.get("sub", "")))
        for b in sec.get("blocks", []):
            P.append(render_block(b))

    # ---- 领导致辞四点 ----
    if d.get("points"):
        P.append(title_bar("领导寄语"))
        P.append(card(four_points(d["points"])))

    # ---- 报告四维度 ----
    if d.get("dims"):
        P.append(title_bar("工作报告"))
        P.append(card(
            "".join(f'<p style="color:{BROWN};font-size:14px;line-height:1.9;'
                    f'margin:0 0 8px;text-align:justify;{BOX}">{escape(x)}</p>'
                    for x in d["dims"])))

    # ---- 正式表格 ----
    if d.get("table"):
        t = d["table"]
        P.append(title_bar(t.get("title", "名单")))
        P.append(card(table_grid(t.get("header", []), t.get("rows", []), t.get("widths"))))

    # ---- 双列信息表 ----
    if d.get("kv"):
        P.append(title_bar("活动信息"))
        P.append(card(kv_list([tuple(x) for x in d["kv"]])))

    # ---- 通栏图 ----
    if d.get("photo"):
        ph = d["photo"]
        P.append(photo_wide(ph.get("caption", ""), ph.get("ratio", "16:9")))

    # ---- 三图网格 ----
    if d.get("photos"):
        P.append(photo_grid(d["photos"], d.get("per_row", 3)))

    # ---- 名单区块 ----
    for grp in d.get("name_groups", []):
        P.append(title_bar(grp.get("title", "【待填】")))
        if grp.get("sub"):
            P.append(f'<p style="color:{RED2};font-size:15px;text-align:center;'
                     f'margin:0 0 4px 0;{BOX}">{escape(grp["sub"])}</p>')
        if grp.get("sub2"):
            P.append(f'<p style="color:{RED2};font-size:14px;text-align:center;'
                     f'margin:0 0 8px 0;{BOX}">{escape(grp["sub2"])}</p>')
        # sort 可自定义排序说明；传空字符串则不显示该行（集体名单常不需要）
        note = grp.get("sort", "（按姓氏笔画排序）：")
        head = sort_note(note) if note else ""
        P.append(card(head + name_grid(grp.get("names", []),
                                       per_row=grp.get("per_row", 5))))

    # ---- 结尾 ----
    if d.get("ending"):
        P.append(wave_sep())
        P.append(para(d["ending"], color=BROWN))

    # ---- 自定义尾块（可自由编排，顺序即渲染顺序）----
    for b in d.get("tail_blocks", []):
        P.append(render_block(b))

    # 金句放在最后收尾
    if d.get("closing"):
        P.append(closing_quote(d["closing"]))

    # ---- 页尾 ----
    P.append(footer_card(d.get("footer_qr", "【此处放落款文字与官方二维码】")))
    P.append(end_block(d.get("editor"), d.get("first"), d.get("second"), d.get("third")))

    body = "".join(parts)
    html = (f'<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(_t(d.get("title", "公众号图文")))}</title></head>\n'
            f'<body style="margin:0;padding:16px;background:#ffffff;">\n'
            f'<section id="output" style="max-width:677px;margin:0 auto;font-family:{FONT};'
            f'{BOX}">{body}</section>\n</body></html>')

    # 字号缩放：面向中老年读者的稿子通常要 1.15~1.25 倍
    try:
        k = float(d.get("font_scale") or 1)
    except (TypeError, ValueError):
        k = 1.0
    if abs(k - 1.0) > 0.001:
        k = max(0.8, min(2.0, k))
        html = scale_fonts(html, k)
    return html


def scale_fonts(html, k):
    """把所有 font-size:Npx 按比例放大，用于中老年受众等大字号场景。"""
    def rep(m):
        v = round(float(m.group(1)) * k, 1)
        return f"font-size:{v:g}px"
    return re.sub(r"font-size:([\d.]+)px", rep, html)


DEMO = {
    "title": "计算机学院、软件学院、网络空间安全学院第六次学生代表大会顺利召开",
    "header_img": "",
    "badge": "全 员 出 席",
    "tags": ["思想引领", "服务同学", "校园文化", "自身建设"],
    "stats": [["33名", "学生代表"], ["4名", "常任代表候选人"], ["3名", "主席团成员"]],
    "paragraphs": [
        "2025年10月15日下午，南京邮电大学计算机学院、软件学院、网络空间安全学院第六次学生代表大会在庄严的国歌声中拉开序幕，全体参会人员肃立合唱。全院各级本科学生代表悉数到场。学院党委副书记、副院长【待填】，辅导员【待填】应邀出席大会。",
        "大会伊始，【待填】书记发表致辞。他带领全体与会人员回顾了我院过去一年在科技竞赛、文体活动等多方面取得的卓越成绩与突出贡献，同时对同学们的辛勤付出给予高度认可与充分肯定。",
        "总结过往之余，【待填】书记立足当下、展望未来，向全体同学提出四点殷切期望。",
    ],
    "quote": {
        "text": "同学们要坚定理想信念，矢志不渝跟党走，把青春奋斗融入党和国家事业之中，在服务同学、服务集体的过程中实现人生价值。",
        "source": "【待填】书记在大会上的致辞",
    },
    "points": [
        "坚定理想信念，矢志不渝跟党走、筑牢思想根基。",
        "勤奋学习钻研，深耕专业、勤学实践，练硬过硬本领。",
        "竭诚服务同学，主动担当作为，做好师生之间的桥梁纽带。",
        "加强自我修养，锤炼品德操守，涵养高尚情操。",
    ],
    "highlight": [
        {"label": "本次大会", "text": "通过无记名差额选举的方式，选举产生了出席南京邮电大学第二十二次学生代表大会的33名代表、4名常任代表候选人，以及学院新一届学生会主席团3名成员。"}
    ],
    "timeline": [
        ["大会开幕", "全体肃立，合唱国歌，大会正式开始。"],
        ["领导致辞", "【待填】书记回顾成绩、提出四点期望。"],
        ["审议报告", "听取并审议学院学生会工作报告。"],
        ["差额选举", "无记名差额选举产生各级代表与主席团。"],
    ],
    "sections": [
        {
            "no": "01", "title": "大会背景与意义", "sub": "BACKGROUND",
            "blocks": [
                {"type": "p", "text": "学生代表大会是全院学生员工共商学生会建设的重要平台，是学生会履行职能、凝聚共识的关键环节。本次大会的顺利召开，为学院学生工作明确了方向、凝聚了力量。"},
                {"type": "highlight", "label": "意义", "text": "大会充分彰显民主精神、凝聚集体智慧，为学院学生工作注入全新活力与发展动力。"},
                {"type": "image", "caption": "图：大会现场", "ratio": "16:9"},
            ],
        },
        {
            "no": "02", "title": "主要议程", "sub": "AGENDA",
            "blocks": [
                {"type": "kv", "pairs": [
                    ["时间地点", "【待填】"],
                    ["主持人", "【待填】"],
                    ["参会人员", "全院各级本科学生代表"],
                    ["出席嘉宾", "学院党委副书记、副院长【待填】"],
                ]},
                {"type": "table", "header": ["议程", "内容", "负责人"],
                 "widths": ["25", "45", "30"],
                 "rows": [["开幕", "合唱国歌、领导致辞", "【待填】"],
                          ["报告", "审议学生会工作报告", "【待填】"],
                          ["选举", "选举各级代表", "【待填】"]]},
                {"type": "photos", "captions": ["大会现场", "交流发言", "表决环节"]},
            ],
        },
    ],
    "dims": [
        "思想引领：持续深化理论学习，推动思想建设走深走实。",
        "服务同学：聚焦同学诉求，丰富服务供给，提升响应效率。",
        "校园文化：打造特色品牌活动，营造浓厚校园文化氛围。",
        "自身建设：健全规章制度，加强队伍管理，优化工作机制。",
    ],
    "name_groups": [
        {"title": "大会选举结果", "sub": "南京邮电大学", "sub2": "第二十二次学生代表大会代表（共33名）",
         "names": ["【待填】"], "per_row": 5},
        {"title": "常任代表候选人", "sub": "南京邮电大学", "sub2": "第二十二次学生代表大会常任代表候选人（共4名）",
         "names": ["【待填】"], "per_row": 5},
        {"title": "主席团成员", "sub": "南京邮电大学计算机学院、软件学院、网络空间安全学院",
         "sub2": "新一届学生会主席团成员（共3名）",
         "names": ["【待填】"], "per_row": 5},
    ],
    "ending": "本次大会充分彰显民主精神、凝聚集体智慧，为学院学生工作注入全新活力与发展动力。全院学子将以此次大会为新起点，承前启后、锐意进取，在持续助力学院高质量发展的实践中，以蓬勃朝气与实干担当，充分展现学院学子的青春风采。",
    "closing": "承前启新程  实干谱新篇",
    "editor": "", "first": "", "second": "", "third": "",
    "footer_qr": "【此处放落款文字与官方二维码】",
}


def main():
    ap = argparse.ArgumentParser(
        description="学代会通稿排版生成器（秀米路径）。不带参数时默认读 gonggao_data.json。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""常用示例：
  python build_gonggao.py                     生成 layout_final.html
  python build_gonggao.py --check             只检查待填和图片，不生成
  python build_gonggao.py --inject            生成后注入秀米（只看不存）
  python build_gonggao.py --inject --save     生成后注入并保存
""")
    ap.add_argument("--data", help="内容 JSON（默认 gonggao_data.json）")
    ap.add_argument("--out", default="layout_final.html", help="输出 HTML（默认 layout_final.html）")
    ap.add_argument("--check", action="store_true", help="只检查待填占位与图片，不生成")
    ap.add_argument("--strict", action="store_true", help="仍有待填时以非零码退出")
    ap.add_argument("--inject", action="store_true", help="生成后注入秀米编辑器")
    ap.add_argument("--save", action="store_true", help="注入时同时保存（默认只演练不保存）")
    ap.add_argument("--title", help="注入用的标题（默认取 JSON 的 title）")
    ap.add_argument("--print-data", action="store_true", help="打印内置示例 JSON")
    ap.add_argument("--merge-demo", action="store_true",
                    help="与内置示例合并（默认：完全替换，避免旧内容残留）")
    a = ap.parse_args()

    if a.print_data:
        print(json.dumps(DEMO, ensure_ascii=False, indent=2))
        return

    # 默认数据文件：当前稿件 → 示例（给刚 clone 下来的人用）
    if a.data:
        data_path = Path(a.data)
    else:
        data_path = next((p for p in (HERE / "gonggao_data.json",
                                      HERE / "示例-养老服务驿站.json",
                                      HERE / "示例-年度表彰大会.json") if p.exists()),
                         HERE / "gonggao_data.json")
    if a.data or data_path.exists():
        if not data_path.exists():
            print(f"[ERR] 找不到内容文件：{data_path}")
            return 2
        try:
            given = json.loads(data_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[ERR] JSON 格式错误（第 {e.lineno} 行，第 {e.colno} 列）：{e.msg}")
            print("      常见原因：多了/少了逗号、引号没闭合、用了中文引号。")
            return 2
        d = {**DEMO, **given} if a.merge_demo else given
        print(f"[读取] {data_path}")
    else:
        d = DEMO
        print("[读取] 内置示例（未找到 gonggao_data.json）")

    # 自检
    remaining = print_check(d, detailed=a.check, base_dir=data_path.parent)

    if a.check:
        return 1 if (a.strict and remaining) else 0

    html = build_page(d)
    problems = lint_html(html)
    if problems:
        print(f"\n[WARN] 检出 {len(problems)} 处属性引号未闭合，页面结构会错乱：")
        for x in problems[:3]:
            print("   ", x[:110])
        print("       这是生成器的 bug，请把上面这行发给我。")

    out = Path(a.out)
    if not out.is_absolute():
        out = (data_path.parent / out) if a.data else (HERE / out)
    out.write_text(html, encoding="utf-8")
    size_kb = out.stat().st_size / 1024
    print(f"\n[OK] 已生成 {out}")
    print(f"     体积 {size_kb:.0f} KB")

    if a.inject:
        if not XIUMI_SCRIPT.exists():
            print(f"[ERR] 找不到秀米注入脚本：{XIUMI_SCRIPT}")
            return 2
        title = a.title or d.get("title", "")
        cmd = [sys.executable, str(XIUMI_SCRIPT),
               "--title", title, "--html-file", str(out)]
        if not a.save:
            cmd.append("--no-save")
        print(f"\n[注入] {'保存模式' if a.save else '演练模式（不保存）'}：{title[:40]}…")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print("[ERR] 注入失败，检查秀米登录态是否过期。")
            return r.returncode

    return 1 if (a.strict and remaining) else 0


if __name__ == "__main__":
    main()
