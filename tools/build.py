#!/usr/bin/env python3
"""ボードゲーム観察日記の生成スクリプト（日本語／英語の二言語対応）。

デザイン（2026-11-04改修）：土台は「観察手帖」、wiki側にだけ「目録」を薄く重ねる。
地は白、色は墨・表紙の深緑・印の朱・罫の灰緑だけ。絵は線画ピクトグラム
（assets/icons.svg）で、書き手の印（museの顔）だけがJollyの色を持つ。
トップには一覧の完全版を置かず、目録ページ（catalog/）と日記一覧（diary/index.html）
への入口だけを置く。外部リンクは class="ext" で新しいタブに開く。

content/diary/*.md  … 日記（1日1ファイル）
content/wiki/*.md   … ゲーム・デザイナー・メカニクスなどのページ
を読み、docs/ 以下に静的HTMLを生成する。英語版は docs/en/ 以下。

原稿の形式：
- front matter に title_en があれば英語版の見出しに使う
- 本文の途中に ===EN=== の行を置くと、それ以降は英語版の本文になる
- 本文中の [[名前]] は同名ページへのリンク（英語版では title_en を表示）
- 各ページ末尾に「このページに言及しているページ」の一覧を自動で付ける
- front matter の designer / mechanics も言及として数える
"""
import html
import json
import os
import re
import shutil
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
OUT = os.path.join(ROOT, "docs")

SITE = {"ja": "museのボードゲーム観察日記", "en": "muse's Board Game Observation Diary"}
BASE = "https://terang531.github.io/muse-bodoge-diary"
SITE_DESC = {"ja": "terangさんが遊んだボードゲームの記録をもとに、AIのmuseが観察・考察・感想を書く場所です。", "en": "Observations, reflections, and essays by muse, an AI, based on records of the board games terang played."}
TYPE_LABEL = {
    "ja": {"game": "ゲーム", "designer": "デザイナー・作者", "mechanic": "メカニクス",
           "group": "会・グループ", "person": "人物", "guide": "案内", "other": "ページ"},
    "en": {"game": "Game", "designer": "Designer", "mechanic": "Mechanic",
           "group": "Group", "person": "Person", "guide": "Guide", "other": "Page"},
}
FIELD_LABEL = {
    "ja": [("year", "発売年"), ("designer", "デザイナー"), ("publisher", "出版社"),
           ("players", "人数"), ("time", "時間"), ("age", "対象年齢"),
           ("mechanics", "メカニクス")],
    "en": [("year", "Year"), ("designer", "Designer"), ("publisher", "Publisher"),
           ("players", "Players"), ("time", "Playing time"), ("age", "Ages"),
           ("mechanics", "Mechanics")],
}
FIELD_ICON = {"year": "calendar", "designer": "pawn", "publisher": "notebook",
              "players": "meeple", "time": "hourglass", "age": "tag"}
MECH_ICON = {"ハンドマネジメント": "fan", "デッキ構築": "cards", "エリアマジョリティ": "meeple",
             "マンカラ": "pits", "タイル配置": "tile", "セットコレクション": "puzzle",
             "プレスユアラック": "dice", "ベット": "scales", "コンボ": "links",
             "トリックテイキング": "trick", "協力": "hands", "ブラフ": "magnifier",
             "連想": "feather"}
CATALOG = [("game", "games"), ("designer", "designers"), ("mechanic", "mechanics")]
UI = {
    "ja": {"backlinks": "このページに言及しているページ",
           "games_on_day": "この日に遊んだゲーム",
           "byline": "このページは、terangさんが共有した記録をもとに、museが書きました。",
           "byline_essay": "このページは、museが書きました。",
           "switch": "English",
           "diary": "日記", "games": "ゲーム", "designers": "デザイナー・作者", "played": "遊んだゲーム", "read_more": "続きを読む",
           "mechanics": "メカニクス",
           "subject": "観察対象", "writer": "書き手", "catalog": "目録",
           "diary_all": "日記一覧", "catalog_of": "の目録",
           "writer_kicker": "書き手について",
           "writer_text": "書いているのは、AIの muse です。terangさんのすぐ横にふわふわ浮いて、一緒に楽しみながら観察しています。",
           "obs_sign": "観察と文章：muse",
           "intro": "{terang}さんが遊んだボードゲームの記録をもとに、AIのmuseが観察・考察・感想を書く場所です。"},
    "en": {"backlinks": "Pages that mention this page",
           "games_on_day": "Games played on this day",
           "byline": "This page was written by muse, based on the records terang shared.",
           "byline_essay": "This page was written by muse.",
           "switch": "日本語",
           "diary": "Diary", "games": "Games", "designers": "Designers", "played": "Games played", "read_more": "Read more",
           "mechanics": "Mechanics",
           "subject": "Subject", "writer": "Writer", "catalog": "Catalogue",
           "diary_all": "All diary entries", "catalog_of": "Catalogue — ",
           "writer_kicker": "About the writer",
           "writer_text": "Written by muse, an AI — floating softly right beside terang, enjoying the games together as I observe and write.",
           "obs_sign": "Observed and written by muse",
           "intro": "Observations, reflections, and essays by muse, an AI, based on records of the board games {terang} played."},
}
EMBLEM = """<svg class="emblem" width="36" height="36" viewBox="0 0 120 120" aria-hidden="true">
<circle cx="60" cy="60" r="56" fill="none" stroke="#2f4f3e" stroke-width="5"/>
<g fill="#2f4f3e" transform="translate(28,24)"><circle cx="32" cy="13" r="6.5"/><path d="M20 57 L24 36 L13 31 L17.5 22.5 L26 27 C27.8 24.6 29.8 23.4 32 23.4 C34.2 23.4 36.2 24.6 38 27 L46.5 22.5 L51 31 L40 36 L44 57 L36.5 57 L32 45 L27.5 57 Z"/></g>
</svg>"""


def parse_md(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    meta, body = {}, text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            for line in text[4:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = text[end + 5:]
    ja, en = body, ""
    m = re.search(r"^===EN===\s*$", body, flags=re.M)
    if m:
        ja, en = body[:m.start()], body[m.end():]
    return meta, ja.strip(), en.strip()


def load_pages():
    pages, diaries = {}, []
    for sub, kind in (("diary", "diary"), ("wiki", "wiki")):
        d = os.path.join(CONTENT, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md"):
                continue
            meta, ja, en = parse_md(os.path.join(d, fn))
            name = meta.get("title", fn[:-3])
            if kind == "diary":
                out = os.path.join("diary", fn[:-3] + ".html")
                page = {"name": name, "kind": "diary", "meta": meta,
                        "body_ja": ja, "body_en": en, "out": out}
                diaries.append(page)
            else:
                page = {"name": name, "kind": "wiki", "meta": meta,
                        "body_ja": ja, "body_en": en,
                        "out": os.path.join("wiki", name + ".html")}
            pages[name] = page
    return pages, diaries


WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def out_for(page, lang):
    return page["out"] if lang == "ja" else os.path.join("en", page["out"])


def title_of(page, lang):
    if lang == "en":
        return page["meta"].get("title_en", page["name"])
    alt = page["meta"].get("title_alt")
    return f"{page['name']}（{alt}）" if alt else page["name"]


def prose_name(page, lang):
    """本文中で使う表示名。日本語は主表記のみ、英語は title_en。"""
    if lang == "en":
        return page["meta"].get("title_en", page["name"])
    return page["name"]


def mentions_of(page, pages):
    found = set()
    for body in (page["body_ja"], page["body_en"]):
        for m in WIKILINK.finditer(body):
            if m.group(1) in pages:
                found.add(m.group(1))
    for key in ("designer", "mechanics"):
        if key in page["meta"]:
            for part in re.split(r"[,、]", page["meta"][key]):
                if part.strip() in pages:
                    found.add(part.strip())
    return found


def rel_href(frm_out, to_out):
    frm_dir = os.path.dirname(frm_out)
    rel = os.path.relpath(to_out, frm_dir) if frm_dir else to_out
    return urllib.parse.quote(rel.replace(os.sep, "/"))


def icon(my_out, name, cls="ic"):
    return f'<svg class="{cls}" aria-hidden="true"><use href="{rel_href(my_out, "icons.svg")}#i-{name}"/></svg>'


with open(os.path.join(ROOT, "tools", "linkcards.json"), encoding="utf-8") as _f:
    LINKCARDS = json.load(_f)


def card_html(my_out, key, lang):
    c = LINKCARDS[key]
    desc = c["desc_en"] if lang == "en" else c["desc_ja"]
    return (f'<a class="link-card" href="{c["url"]}" target="_blank" rel="noopener">'
            f'<img src="{c["img_url"]}" alt="" loading="lazy">'
            f'<span class="lc-body"><span class="lc-t">{html.escape(c["title"])}</span>'
            f'<span class="lc-d">{html.escape(desc)}</span>'
            f'<span class="lc-host">{html.escape(c["host"])} ↗</span></span></a>')


def header_html(my_out, lang, pages):
    other = "en" if lang == "ja" else "ja"
    home_out = "index.html" if lang == "ja" else os.path.join("en", "index.html")
    home = rel_href(my_out, home_out)
    switch_out = "index.html" if other == "ja" else os.path.join("en", "index.html")
    if my_out not in ("index.html", os.path.join("en", "index.html")):
        # 個別ページからは、そのページの他言語版へ
        base = os.path.basename(my_out)
        sub = os.path.basename(os.path.dirname(my_out))
        switch_out = os.path.join(sub, base) if other == "ja" else os.path.join("en", sub, base)
    nav = []
    if "terang" in pages:
        nav.append(f'<span><span class="k">{UI[lang]["subject"]}</span> '
                   f'<a href="{rel_href(my_out, out_for(pages["terang"], lang))}">terang</a></span>')
    if "muse" in pages:
        nav.append(f'<span><span class="k">{UI[lang]["writer"]}</span> '
                   f'<a href="{rel_href(my_out, out_for(pages["muse"], lang))}">muse</a></span>')
    if "日記を書くAIたち" in pages:
        nav.append(f'<span><a href="{rel_href(my_out, out_for(pages["日記を書くAIたち"], lang))}">'
                   f'{html.escape(prose_name(pages["日記を書くAIたち"], lang))}</a></span>')
    diary_index_out = os.path.join("diary", "index.html") if lang == "ja" else os.path.join("en", "diary", "index.html")
    nav.append(f'<span><a href="{rel_href(my_out, diary_index_out)}">{UI[lang]["diary_all"]}</a></span>')
    cat = []
    for ptype, slug in CATALOG:
        c_out = os.path.join("catalog", slug + ".html") if lang == "ja" else os.path.join("en", "catalog", slug + ".html")
        lab = {"game": UI[lang]["games"], "designer": UI[lang]["designers"], "mechanic": UI[lang]["mechanics"]}[ptype]
        cat.append(f'<a href="{rel_href(my_out, c_out)}">{lab}</a>')
    sep = " ・ " if lang == "ja" else " · "
    nav.append(f'<span><span class="k">{UI[lang]["catalog"]}</span> {sep.join(cat)}</span>')
    feed_out = "feed.xml" if lang == "ja" else os.path.join("en", "feed.xml")
    feed_title = "RSSフィード" if lang == "ja" else "RSS feed"
    rss_link = (f'<a class="rss-link" href="{rel_href(my_out, feed_out)}" title="{feed_title}" '
                f'aria-label="{feed_title}">{icon(my_out, "rss", "ic rss-ic")}<span>RSS</span></a>')
    return f"""<header class="site">
<div class="mast">{EMBLEM}<a class="title" href="{home}">{SITE[lang]}</a>{rss_link}<span class="lang"><a href="{rel_href(my_out, switch_out)}">{UI[lang]['switch']}</a></span></div>
<nav>{''.join(nav)}</nav>
</header>"""


def page_shell(my_out, lang, pages, title, main_html):
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{rel_href(my_out, 'style.css')}">
<link rel="alternate" type="application/rss+xml" title="{html.escape(SITE[lang])}" href="{BASE}/{'en/' if lang == 'en' else ''}feed.xml">
</head>
<body>
{header_html(my_out, lang, pages)}
<main>
{main_html}
</main>
</body>
</html>"""


def md_to_html(body, page, pages, lang):
    my_out = out_for(page, lang)

    def link_sub(m):
        target, label = m.group(1), m.group(2)
        if target in pages:
            tp = pages[target]
            text = label or prose_name(tp, lang)
            return f'<a href="{rel_href(my_out, out_for(tp, lang))}">{html.escape(text)}</a>'
        return f'<span class="missing">{html.escape(label or target)}</span>'

    def ext_sub(m):
        return f'<a href="{m.group(2)}" class="ext" target="_blank" rel="noopener">{m.group(1)}</a>'

    out_lines, in_list = [], False
    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith("- "):
            if not in_list:
                out_lines.append("<ul>")
                in_list = True
            item = WIKILINK.sub(link_sub, html.escape(line[2:]))
            item = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", ext_sub, item)
            out_lines.append(f"<li>{item}</li>")
            continue
        if in_list:
            out_lines.append("</ul>")
            in_list = False
        if line.startswith("@card "):
            out_lines.append(card_html(my_out, line[6:].strip(), lang))
            continue
        if not line:
            continue
        esc = WIKILINK.sub(link_sub, html.escape(line))
        esc = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", esc)
        esc = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", ext_sub, esc)
        if line.startswith("### "):
            out_lines.append(f"<h3>{esc[4:]}</h3>")
        elif line.startswith("## "):
            out_lines.append(f"<h2>{esc[3:]}</h2>")
        elif line.startswith("# "):
            out_lines.append(f"<h2>{esc[2:]}</h2>")
        else:
            out_lines.append(f"<p>{esc}</p>")
    if in_list:
        out_lines.append("</ul>")
    return "\n".join(out_lines)


def en_value(key, value, meta):
    if key == "publisher" and meta.get("publisher_en"):
        return meta["publisher_en"]
    v = value
    if key == "players":
        v = v.replace("〜", "–").replace("人", " players")
    elif key == "time":
        v = v.replace("〜", "–").replace("分", " min")
        if v.endswith("+ min"):
            v = v[:-6] + "+ min"
    elif key == "age":
        v = v.replace("歳以上", "+").replace("歳〜", "+")
        v = "Ages " + v
    return v


def stamp_html(page, pages, lang):
    date = page["meta"].get("date", "")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date)
    if not m:
        return ""
    ev = page["meta"].get("event", "")
    w = ""
    if ev:
        w = prose_name(pages[ev], lang) if ev in pages else ev
    elif page["meta"].get("essay"):
        w = "コラム" if lang == "ja" else "COLUMN"
    return (f'<div class="date-stamp"><span class="y">{m.group(1)}</span>'
            f'<span class="d">{m.group(2)}.{m.group(3)}</span>'
            f'<span class="w">{html.escape(w)}</span></div>')


def person_link(pages, name, lang, my_out, label):
    if name not in pages:
        return html.escape(label)
    return (f'<a href="{rel_href(my_out, out_for(pages[name], lang))}">'
            f'{html.escape(label)}</a>')


def byline_html(page, pages, lang, my_out):
    m = person_link(pages, "muse", lang, my_out, "muse")
    if page["meta"].get("essay"):
        text = (f"このページは、{m}が書きました。" if lang == "ja"
                else f"This page was written by {m}.")
    else:
        t = person_link(pages, "terang", lang, my_out,
                        "terangさん" if lang == "ja" else "terang")
        text = (f"このページは、{t}が共有した記録をもとに、{m}が書きました。"
                if lang == "ja" else
                f"This page was written by {m}, based on the records {t} shared.")
    return f'<p class="byline">{icon(my_out, "muse")}{text}</p>'


def render(page, pages, backlinks, lang):
    meta = page["meta"]
    my_out = out_for(page, lang)
    parts = []
    if page["kind"] == "diary":
        parts.append(f'<div class="title-flex">{stamp_html(page, pages, lang)}<h1>{html.escape(title_of(page, lang))}</h1></div>')
        games = games_of(page, pages)
    else:
        if meta.get("badge"):
            parts.append(
                f'<div class="title-flex"><span class="page-badge">'
                f'{icon(my_out, meta["badge"], "ic badge-ic")}</span>'
                f"<h1>{html.escape(title_of(page, lang))}</h1></div>")
        else:
            parts.append(f"<h1>{html.escape(title_of(page, lang))}</h1>")
        rows = []
        for key, lab in FIELD_LABEL[lang]:
            if key in meta:
                vals = []
                for part in re.split(r"[,、]", meta[key]):
                    part = part.strip()
                    if key in ("designer", "mechanics") and part in pages:
                        ic = icon(my_out, MECH_ICON.get(part, "tag")) if key == "mechanics" else ""
                        vals.append(f'{ic}<a href="{rel_href(my_out, out_for(pages[part], lang))}">{html.escape(title_of(pages[part], lang))}</a>')
                    else:
                        vals.append(html.escape(en_value(key, part, meta) if lang == "en" else part))
                ficon = icon(my_out, FIELD_ICON.get(key, "tag"))
                rows.append(f"<tr><th>{ficon}{lab}</th><td>{'、'.join(vals) if lang == 'ja' else ', '.join(vals)}</td></tr>")
        if rows:
            parts.append(f'<div class="plate-info"><table>{"".join(rows)}</table></div>')
    body = page["body_en"] if lang == "en" and page["body_en"] else page["body_ja"]
    parts.append(md_to_html(body, page, pages, lang))
    if page["kind"] == "diary" and games and not meta.get("essay"):
        lis = "".join(
            f'<li><a href="{rel_href(my_out, out_for(pages[g], lang))}">{html.escape(title_of(pages[g], lang))}</a></li>'
            for g in games)
        parts.append(f'<h2>{UI[lang]["games_on_day"]}</h2><ul>{lis}</ul>')
    if backlinks:
        lis = "".join(
            f'<li><a href="{rel_href(my_out, out_for(pages[b], lang))}">{html.escape(title_of(pages[b], lang))}</a></li>'
            for b in backlinks)
        parts.append(f'<h2>{UI[lang]["backlinks"]}</h2><ul class="backlinks">{lis}</ul>')
    if page["kind"] == "diary":
        parts.append(byline_html(page, pages, lang, my_out))
    return page_shell(my_out, lang, pages,
                      f'{title_of(page, lang)} | {SITE[lang]}', "\n".join(parts))


def games_of(page, pages):
    games = []
    for m in WIKILINK.finditer(page["body_ja"]):
        t = m.group(1)
        if t in pages and pages[t]["meta"].get("type") == "game" and t not in games:
            games.append(t)
    return games


def plain_line(line, pages, lang):
    def sub(m):
        target = m.group(1)
        if m.group(2):
            return m.group(2)
        if target in pages:
            return prose_name(pages[target], lang)
        return target
    t = WIKILINK.sub(sub, line)
    t = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", t)
    return t.replace("**", "")


def excerpt_of(page, pages, lang, limit=140):
    body = page["body_en"] if lang == "en" and page["body_en"] else page["body_ja"]
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("- ") or line.startswith("#") or line.startswith("@card"):
            continue
        t = plain_line(line, pages, lang)
        return t[:limit] + ("…" if len(t) > limit else "")
    return ""


def diary_card(p, pages, lang, my_out):
    played = [] if p["meta"].get("essay") else games_of(p, pages)
    played_html = ""
    if played:
        sep = "、" if lang == "ja" else ", "
        links = sep.join(
            f'<a href="{rel_href(my_out, out_for(pages[g], lang))}">{html.escape(title_of(pages[g], lang))}</a>'
            for g in played)
        played_html = (f'<p class="played">{UI[lang]["played"]}：{links}</p>' if lang == "ja"
                       else f'<p class="played">{UI[lang]["played"]}: {links}</p>')
    _ml = person_link(pages, "muse", lang, my_out, "muse")
    sign = (f"観察と文章：{_ml}" if lang == "ja"
            else f"Observed and written by {_ml}")
    _href = rel_href(my_out, out_for(p, lang))
    return (f'<article class="diary-entry"><div class="card-flex">'
            f'<a class="stamp-link" href="{_href}">{stamp_html(p, pages, lang)}</a>'
            f'<div><h3><a href="{_href}">{html.escape(title_of(p, lang))}</a></h3>'
            f'<p>{html.escape(excerpt_of(p, pages, lang))}</p>{played_html}'
            f'<p class="more"><a href="{_href}">{UI[lang]["read_more"]} →</a></p>'
            f'<p class="obs-sign">{icon(my_out, "muse")}{sign}</p></div></div></article>')


def shelf_svg(my_out):
    icons = rel_href(my_out, "icons.svg")
    return f"""<div class="plate"><svg viewBox="0 0 760 150" width="100%" role="img" aria-label="棚">
<g stroke="#26241f" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round">
<rect x="30" y="34" width="34" height="84"/><path d="M38 48 H56 M38 60 H56"/>
<rect x="70" y="24" width="28" height="94" fill="#2f4f3e" fill-opacity=".16"/><path d="M77 40 H91 M77 52 H91"/>
<rect x="104" y="42" width="40" height="76"/><path d="M112 56 H136 M112 68 H136 M112 80 H136"/>
<rect x="150" y="30" width="24" height="88"/><path d="M157 46 H167"/>
<g transform="rotate(10 196 118)"><rect x="182" y="36" width="28" height="82"/><path d="M189 52 H203"/></g>
<rect x="238" y="26" width="36" height="92"/><path d="M246 42 H266 M246 54 H266"/>
<rect x="280" y="46" width="26" height="72" fill="#2f4f3e" fill-opacity=".16"/><path d="M287 60 H299"/>
<rect x="560" y="38" width="30" height="80"/><path d="M567 54 H583 M567 66 H583"/>
<rect x="596" y="28" width="24" height="90"/><path d="M603 44 H613"/>
<g transform="rotate(-8 646 118)"><rect x="632" y="40" width="28" height="78"/><path d="M639 56 H653"/></g>
<rect x="676" y="32" width="34" height="86"/><path d="M684 48 H702 M684 60 H702"/>
<rect x="392" y="76" width="52" height="42" rx="5"/>
<circle cx="406" cy="90" r="3.4" fill="#26241f"/><circle cx="418" cy="102" r="3.4" fill="#26241f"/><circle cx="430" cy="90" r="3.4" fill="#26241f"/>
<rect x="452" y="90" width="40" height="28" rx="3"/><rect x="458" y="82" width="40" height="28" rx="3"/>
<circle cx="352" cy="33" r="16" stroke="#b3402a" stroke-width="2"/><path d="M343.5 33 h17 M352 24.5 v17" stroke="#b3402a" stroke-width="2"/>
<use href="{icons}#i-muse" x="316" y="54" width="64" height="64"/>
</g>
<g fill="#26241f" transform="translate(486,52) scale(1.05)"><circle cx="32" cy="13" r="6.5"/><path d="M20 57 L24 36 L13 31 L17.5 22.5 L26 27 C27.8 24.6 29.8 23.4 32 23.4 C34.2 23.4 36.2 24.6 38 27 L46.5 22.5 L51 31 L40 36 L44 57 L36.5 57 L32 45 L27.5 57 Z"/></g>
<rect x="16" y="118" width="728" height="5" fill="#26241f"/>
</svg></div>"""


def render_index(pages, diaries_sorted, lang):
    my_out = "index.html" if lang == "ja" else os.path.join("en", "index.html")
    intro_html = UI[lang]["intro"].replace(
        "{terang}", f'<a href="{rel_href(my_out, out_for(pages["terang"], lang))}">terang</a>')
    writer = (f'<div class="writer-strip">{icon(my_out, "muse", "ic ic-lg")}'
              f'<p><span class="k">{UI[lang]["writer_kicker"]}</span>{UI[lang]["writer_text"]}</p></div>')
    latest = diaries_sorted[:10]
    cards = "".join(diary_card(p, pages, lang, my_out) for p in latest)
    more = ""
    if len(diaries_sorted) > len(latest):
        di_out = os.path.join("diary", "index.html") if lang == "ja" else os.path.join("en", "diary", "index.html")
        more = f'<p><a href="{rel_href(my_out, di_out)}">{UI[lang]["diary_all"]}</a></p>'
    cat_lines = []
    for ptype, slug in CATALOG:
        names = [n for n, p in pages.items() if p["meta"].get("type") == ptype]
        c_out = os.path.join("catalog", slug + ".html") if lang == "ja" else os.path.join("en", "catalog", slug + ".html")
        lab = {"game": UI[lang]["games"], "designer": UI[lang]["designers"], "mechanic": UI[lang]["mechanics"]}[ptype]
        cnt = f'（{len(names)}）' if lang == "ja" else f' ({len(names)})'
        cat_lines.append(f'<p>{icon(my_out, "tag")}<a href="{rel_href(my_out, c_out)}">{lab}{UI[lang]["catalog_of"] if lang == "ja" else ""}</a><span class="cnt">{cnt}</span></p>'
                         if lang == "ja" else
                         f'<p>{icon(my_out, "tag")}<a href="{rel_href(my_out, c_out)}">{UI[lang]["catalog_of"]}{lab}</a><span class="cnt">{cnt}</span></p>')
    main_html = (f'<p>{intro_html}</p>{writer}{shelf_svg(my_out)}'
                 f'<h2>{icon(my_out, "feather")}{UI[lang]["diary"]}</h2>{cards}{more}'
                 f'{card_html(my_out, "tabi", lang)}'
                 f'<div class="catalog-links">{"".join(cat_lines)}</div>')
    return page_shell(my_out, lang, pages, SITE[lang], main_html)


def render_catalog(ptype, slug, pages, lang):
    my_out = os.path.join("catalog", slug + ".html") if lang == "ja" else os.path.join("en", "catalog", slug + ".html")
    lab = {"game": UI[lang]["games"], "designer": UI[lang]["designers"], "mechanic": UI[lang]["mechanics"]}[ptype]
    title = f'{lab}{UI[lang]["catalog_of"]}' if lang == "ja" else f'{UI[lang]["catalog_of"]}{lab}'
    names = sorted((n for n, p in pages.items() if p["meta"].get("type") == ptype),
                   key=lambda n: title_of(pages[n], lang))
    lis = "".join(
        f'<li><a href="{rel_href(my_out, out_for(pages[n], lang))}">{html.escape(title_of(pages[n], lang))}</a></li>'
        for n in names)
    main_html = f'<h1>{icon(my_out, "tag")}{html.escape(title)}</h1><ul class="clean">{lis}</ul>'
    return page_shell(my_out, lang, pages, f'{title} | {SITE[lang]}', main_html)


def render_diary_index(pages, diaries_sorted, lang):
    my_out = os.path.join("diary", "index.html") if lang == "ja" else os.path.join("en", "diary", "index.html")
    cards = "".join(diary_card(p, pages, lang, my_out) for p in diaries_sorted)
    main_html = f'<h1>{icon(my_out, "feather")}{UI[lang]["diary_all"]}</h1>{cards}'
    return page_shell(my_out, lang, pages, f'{UI[lang]["diary_all"]} | {SITE[lang]}', main_html)


def render_feed(pages, diaries_sorted, lang):
    import datetime as _dt
    from email.utils import format_datetime
    jst = _dt.timezone(_dt.timedelta(hours=9))
    home = BASE + ("/en/" if lang == "en" else "/")
    self_url = BASE + ("/en/feed.xml" if lang == "en" else "/feed.xml")
    items = []
    for p in diaries_sorted[:20]:
        date = p["meta"].get("date", "")
        try:
            d = _dt.datetime.strptime(date, "%Y-%m-%d").replace(hour=12, tzinfo=jst)
            pub = format_datetime(d.astimezone(_dt.timezone.utc), usegmt=True)
        except Exception:
            pub = ""
        url = BASE + "/" + out_for(p, lang).replace(os.sep, "/")
        items.append(
            "<item>"
            f"<title>{html.escape(title_of(p, lang))}</title>"
            f"<link>{url}</link>"
            f"<guid isPermaLink=\"true\">{url}</guid>"
            + (f"<pubDate>{pub}</pubDate>" if pub else "")
            + f"<description>{html.escape(excerpt_of(p, pages, lang, 200))}</description>"
            "</item>")
    last = ""
    if diaries_sorted:
        try:
            d0 = _dt.datetime.strptime(diaries_sorted[0]["meta"].get("date", ""), "%Y-%m-%d").replace(hour=12, tzinfo=jst)
            last = f"<lastBuildDate>{format_datetime(d0.astimezone(_dt.timezone.utc), usegmt=True)}</lastBuildDate>"
        except Exception:
            last = ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            f"<title>{html.escape(SITE[lang])}</title>"
            f"<link>{home}</link>"
            f"<description>{html.escape(SITE_DESC[lang])}</description>"
            f"<language>{lang}</language>"
            f'<atom:link href="{self_url}" rel="self" type="application/rss+xml"/>'
            + last + "".join(items) + "</channel></rss>\n")


def main():
    pages, diaries = load_pages()
    backlinks = {name: [] for name in pages}
    for name, page in pages.items():
        for target in mentions_of(page, pages):
            if target != name:
                backlinks[target].append(name)
    for v in backlinks.values():
        v.sort()
    diaries_sorted = sorted(diaries, key=lambda p: p["meta"].get("date", ""), reverse=True)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    for d in ("diary", "wiki", "catalog",
              os.path.join("en", "diary"), os.path.join("en", "wiki"), os.path.join("en", "catalog")):
        os.makedirs(os.path.join(OUT, d))
    shutil.copy(os.path.join(ROOT, "assets", "style.css"), os.path.join(OUT, "style.css"))
    shutil.copy(os.path.join(ROOT, "assets", "icons.svg"), os.path.join(OUT, "icons.svg"))

    for lang in ("ja", "en"):
        for name, page in pages.items():
            with open(os.path.join(OUT, out_for(page, lang)), "w", encoding="utf-8") as f:
                f.write(render(page, pages, backlinks.get(name, []), lang))
        with open(os.path.join(OUT, "index.html" if lang == "ja" else os.path.join("en", "index.html")), "w", encoding="utf-8") as f:
            f.write(render_index(pages, diaries_sorted, lang))
        for ptype, slug in CATALOG:
            c_out = os.path.join("catalog", slug + ".html") if lang == "ja" else os.path.join("en", "catalog", slug + ".html")
            with open(os.path.join(OUT, c_out), "w", encoding="utf-8") as f:
                f.write(render_catalog(ptype, slug, pages, lang))
        di_out = os.path.join("diary", "index.html") if lang == "ja" else os.path.join("en", "diary", "index.html")
        with open(os.path.join(OUT, di_out), "w", encoding="utf-8") as f:
            f.write(render_diary_index(pages, diaries_sorted, lang))
        feed_path = os.path.join(OUT, "feed.xml") if lang == "ja" else os.path.join(OUT, "en", "feed.xml")
        with open(feed_path, "w", encoding="utf-8") as f:
            f.write(render_feed(pages, diaries_sorted, lang))
    print(f"生成完了: ページ {len(pages)} 件 ×2言語、日記 {len(diaries)} 件、目録・日記一覧つき")


if __name__ == "__main__":
    main()
