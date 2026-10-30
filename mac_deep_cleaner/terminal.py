"""Optional terminal interface and reports."""

from dataclasses import dataclass, asdict
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import zlib
from .applications import AppAnalyzer, app_items
from .catalog import CATS, CAT_DESC, CAT_NAMES, TOOLCHAIN_NAMES, group_name, toolchain
from .cleanup import eligible, esc_as, execute, select_level
from .common import CAUTION, COL, DAY, HOME, IS_MAC, NOW, RISKY, SAFE, c, fmt, run
from .scanner import Scanner
from .settings import SETTINGS_FILE, full_disk_access, open_fda_settings, reveal, save_settings

try:                                    # optional UI libraries
    from rich import box
    from rich.columns import Columns
    from rich.console import Console, Group
    from rich.live import Live
    from rich.padding import Padding
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text
    HAVE_RICH = True
except ImportError:
    HAVE_RICH = False


try:
    import questionary
    HAVE_Q = True
except ImportError:
    HAVE_Q = False


def rel_time(ts):
    if not ts:
        return "never"
    d = int((NOW - ts) / DAY)
    if d < 1:
        return "today"
    if d < 14:
        return f"{d}d ago"
    if d < 60:
        return f"{d // 7}w ago"
    if d < 700:
        return f"{d // 30}mo ago"
    return f"{d // 365}y ago"


CAT_COL = ["34", "32", "33", "92", "35", "31", "95", "91", "36", "94", "92", "93", "90"]


def totals(items):
    t = {"all": 0, SAFE: 0, CAUTION: 0, RISKY: 0, "managed": 0, "oneclick": 0, "manual_safe": 0}
    for it in items:
        if it.managed:
            t["managed"] += it.size
            continue
        if it.protected:
            continue
        t["all"] += it.size
        t[it.safety] += it.size
        if it.safety == SAFE:
            if it.manual or it.action == "root":
                t["manual_safe"] += it.size
            else:
                t["oneclick"] += it.size
    return t


def print_report_plain(items, min_mb=10, top=8, show_all=False):
    t = totals(items)
    w = 74
    print()
    print(c(f"  {fmt(t['all'])}", "1;97"), "you can free up")
    print(f"  {c('●', '32')} {fmt(t[SAFE])} safe   ({fmt(t['oneclick'])} in one click, {fmt(t['manual_safe'])} in active projects / root items picked by hand)")
    print(f"  {c('●', '33')} {fmt(t[CAUTION])} caution")
    print(f"  {c('●', '31')} {fmt(t[RISKY])} risky")
    if t["managed"]:
        print(c(f"  + {fmt(t['managed'])} that macOS and your apps manage themselves (shown, never deleted).", "2"))
    # stacked bar
    per = {}
    for it in items:
        if eligible(it):
            per[it.category] = per.get(it.category, 0) + it.size
    tot = sum(per.values()) or 1
    bar = ""
    for i, cat in enumerate(CAT_NAMES):
        n = int(round(per.get(cat, 0) / tot * w))
        bar += c("█" * n, CAT_COL[i % len(CAT_COL)])
    print("\n  " + bar)
    legend = [f"{c('■', CAT_COL[i % len(CAT_COL)])} {cat} {fmt(per[cat])}" for i, cat in enumerate(CAT_NAMES) if per.get(cat)]
    print("  " + "   ".join(legend))
    # categories
    cut = min_mb * 1_000_000
    for i, (cat, desc) in enumerate(CATS):
        rows = [it for it in items if it.category == cat]
        if not rows:
            continue
        total = sum(r.size for r in rows if not r.managed)
        print("\n" + c(f"  [{i + 1:>2}] {cat}", "1") + c(f"  {fmt(total)}  ·  {len(rows)} items", "2"))
        print(c(f"       {desc}", "2"))
        shown = [r for r in rows if r.size >= cut or r.size == 0 or show_all]
        for r in (shown if show_all else shown[:top]):
            tag = c(f"{r.safety:<7}", COL[r.safety])
            flags = (" PROTECTED" if r.protected else "") + (" ACTIVE-PROJECT" if r.active_project else "") + \
                    (" sudo" if r.action == "root" else "") + (" read-only" if r.readonly else "")
            print(f"       #{r.id:<4} {fmt(r.size):>10}  {tag} {r.name[:44]}{c(flags, '36')}")
            print(c(f"              why: {r.reason}", "2"))
            if r.regen:
                print(c(f"              back: {r.regen}", "2"))
        hidden = len(rows) - len(shown[:top] if not show_all else shown)
        if hidden > 0:
            print(c(f"       … {hidden} more (use 'l {i + 1}' to list all, or --min-mb 0)", "2"))
    print()


def export_json(items, path):
    t = totals(items)
    with open(path, "w") as f:
        json.dump({"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "totals": t, "items": [asdict(i) for i in items]}, f, indent=2)
    print(f"  wrote {path}")


def confirm_risky():
    print(c("  Risky items may contain data that CANNOT be rebuilt (originals, backups, pinned SDKs).", "31"))
    return input("  Type  I UNDERSTAND  to include them: ").strip() == "I UNDERSTAND"


def parse_ids(tokens):
    ids = set()
    for tk in tokens:
        tk = tk.strip("#,")
        if re.fullmatch(r"\d+", tk):
            ids.add(int(tk))
        elif re.fullmatch(r"\d+-\d+", tk):
            a, b = map(int, tk.split("-"))
            ids.update(range(a, b + 1))
    return ids


def cat_by_token(tok):
    if tok.isdigit() and 1 <= int(tok) <= len(CAT_NAMES):
        return CAT_NAMES[int(tok) - 1]
    for n in CAT_NAMES:
        if tok.lower() in n.lower():
            return n
    return None


def selected_summary(items):
    sel = [i for i in items if i.selected]
    by = {SAFE: 0, CAUTION: 0, RISKY: 0}
    for i in sel:
        by[i.safety] += i.size
    return sel, sum(by.values()), by


HELP = """
  s            select ALL safe            c   select ALL caution       r   select ALL risky (asks to confirm)
  a            select everything eligible  x   clear selection
  cat <n|name> select a whole category    <ids>  toggle items, e.g.  3 7-12 40
  l [n|name]   list items (all of them, or one category)      f <text>   filter by name/path
  m <MB>       hide items smaller than MB                      v          show current selection
  d            clean selection (Trash)    D   clean selection PERMANENTLY    n   dry-run the selection
  j <file>     export JSON                 q   quit
"""


def interactive_plain(items, args):
    print(HELP)
    flt, min_mb = "", args.min_mb
    while True:
        sel, tot, by = selected_summary(items)
        try:
            cmd = input(c(f"[{len(sel)} selected · {fmt(tot)}] > ", "1")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not cmd:
            continue
        op, *rest = cmd.split()
        arg = " ".join(rest)
        if op == "q":
            return
        elif op == "h" or op == "?":
            print(HELP)
        elif op == "x":
            for i in items:
                i.selected = False
        elif op == "s":
            print(f"  selected {select_level(items, 'safe')} safe items")
        elif op == "c":
            print(f"  selected {select_level(items, 'caution')} caution items")
        elif op == "r":
            if confirm_risky():
                print(f"  selected {select_level(items, 'risky')} risky items")
        elif op == "a":
            if any(i.safety == RISKY and eligible(i) for i in items) and not confirm_risky():
                print(f"  selected {select_level([i for i in items if i.safety != RISKY], 'all')} non-risky items instead")
                for i in items:
                    if i.safety != RISKY and eligible(i):
                        i.selected = True
            else:
                print(f"  selected {select_level(items, 'all')} items")
        elif op == "cat":
            name = cat_by_token(arg)
            if not name:
                print("  unknown category")
                continue
            rows = [i for i in items if i.category == name and eligible(i)]
            if any(i.safety == RISKY for i in rows) and not confirm_risky():
                rows = [i for i in rows if i.safety != RISKY]
            for i in rows:
                i.selected = True
            print(f"  selected {len(rows)} items in {name}")
        elif op in ("l", "list"):
            name = cat_by_token(arg) if arg else None
            for i in items:
                if name and i.category != name:
                    continue
                if flt and flt.lower() not in (i.name + i.path).lower():
                    continue
                if i.size < min_mb * 1_000_000 and not name:
                    continue
                mark = "[x]" if i.selected else "[ ]"
                print(f"  {mark} #{i.id:<4} {fmt(i.size):>10} {c(f'{i.safety:<7}', COL[i.safety])} {i.name[:40]:40} {c(i.path[-60:], '2')}")
        elif op == "f":
            flt = arg
            print(f"  filter = '{flt}' (use with 'l')")
        elif op == "m":
            try:
                min_mb = float(arg)
            except ValueError:
                pass
        elif op == "v":
            for i in sel:
                print(f"  #{i.id:<4} {fmt(i.size):>10} {c(f'{i.safety:<7}', COL[i.safety])} {i.category}: {i.name}")
            print(f"  total {fmt(tot)}  (safe {fmt(by[SAFE])}, caution {fmt(by[CAUTION])}, risky {fmt(by[RISKY])})")
        elif op == "j":
            export_json(items, arg or "mac_cleaner_report.json")
        elif op in ("d", "D", "n"):
            if not sel:
                print("  nothing selected")
                continue
            perm = op == "D" or args.permanent
            if by[RISKY] and op != "n" and not confirm_risky():
                continue
            print(f"  {len(sel)} items, {fmt(tot)} - {'PERMANENT DELETE' if perm else 'move to Trash'}{' (dry run)' if op == 'n' else ''}")
            if op != "n" and input("  proceed? [y/N] ").strip().lower() != "y":
                continue
            freed, roots, fails = execute(items, permanent=perm, dry_run=(op == "n"))
            print(c(f"\n  {'would free' if op == 'n' else 'freed'} {fmt(freed)}" + ("" if perm or op == "n" else " (empty the Trash to reclaim it)"), "1;32"))
            if roots:
                print("\n  Run these in Terminal yourself (need admin rights):")
                for r in roots:
                    print("    " + r)
        else:
            ids = parse_ids(cmd.split())
            if not ids:
                print("  ? type h for help")
                continue
            by_id = {i.id: i for i in items}
            for n in sorted(ids):
                it = by_id.get(n)
                if it and eligible(it):
                    it.selected = not it.selected
                elif it:
                    print(f"  #{n} is protected/managed")


PAL = {"accent": "#7aa2f7", "safe": "#9ece6a", "caution": "#e0af68", "risky": "#f7768e",
       "muted": "#7a84a8", "text": "#c8d0f0", "line": "#3b4261", "hot": "#bb9af7"}


SAFETY_COLOR = {SAFE: PAL["safe"], CAUTION: PAL["caution"], RISKY: PAL["risky"]}


TILE_COLORS = ["#7aa2f7", "#9ece6a", "#e0af68", "#bb9af7", "#7dcfff", "#f7768e", "#ff9e64", "#73daca", "#c0caf5", "#e0af68"]


ICONS = {
    "System Junk": "◌", "Trash": "▥", "Large & Old Files": "◆", "Duplicate Files": "◧", "Downloads & Installers": "▽",
    "Unused Apps & Leftovers": "▣", "App Caches": "◍", "Mail & Message Attachments": "▤", "Screenshots & Podcasts": "▦",
    "Backups & Updates": "◑", "Cloud Files on This Mac": "◠", "Developer & Pro Tools": "◈", "Photos, Music & Media": "◎",
    "System Data": "▩", "dot": "●", "back": "‹", "next": "›", "ok": "✓", "no": "✕", "warn": "▲", "app": "▣",
    "bar": "█", "meter": "━", "rest": "─", "item": "◇", "lock": "▮", "search": "◎", "clean": "✦", "disk": "◉",
}


ICONS_ASCII = {"bar": "#", "meter": "=", "rest": "-", "dot": "*", "ok": "+", "no": "x", "warn": "!", "back": "<", "next": ">"}


_UTF8 = "utf" in (getattr(sys.stdout, "encoding", "") or "").lower()


def ic(name):
    if _UTF8:
        return ICONS.get(name, ICONS["item"])
    return ICONS_ASCII.get(name, "o")


def short(p, n=56):
    p = (p or "").replace(HOME, "~")
    return p if len(p) <= n else p[:n // 3] + "…" + p[-(n - n // 3 - 1):]


def trunc(s, n):
    return s if len(s) <= n else s[:n - 1] + "…"


def badge(level):
    return Text.assemble((ic("dot") + " ", SAFETY_COLOR.get(level, PAL["muted"])), (level, SAFETY_COLOR.get(level, PAL["muted"])))


def tile(name, key=""):
    """App 'icon': a coloured monogram tile, stable per app."""
    color = TILE_COLORS[zlib.crc32((key or name).encode()) % len(TILE_COLORS)]
    letter = next((ch for ch in name if ch.isalnum()), "?").upper()
    return Text(f" {letter} ", style=f"bold #15161e on {color}")


def seg_bar(parts, width=40):
    """Stacked bar. parts = [(value, hex colour)]."""
    total = sum(v for v, _ in parts) or 1
    t, used = Text(), 0
    for i, (v, col) in enumerate(parts):
        n = int(round(v / total * width)) if i < len(parts) - 1 else width - used
        n = max(0, min(n, width - used))
        used += n
        t.append(ic("bar") * n, style=col)
    t.append(ic("rest") * (width - used), style=PAL["line"])
    return t


def meter(frac, width=24, color=None):
    frac = max(0.0, min(1.0, frac))
    n = int(round(frac * width))
    return Text.assemble((ic("meter") * n, color or PAL["accent"]), (ic("rest") * (width - n), PAL["line"]))


def stat_card(title, value, sub="", color=None):
    body = Group(Text(title.upper(), style=f"bold {PAL['muted']}"),
                 Text(value, style=f"bold {color or PAL['text']}"),
                 Text(sub, style=PAL["muted"]))
    return Panel(body, box=box.ROUNDED, border_style=PAL["line"], padding=(0, 2))


def title_bar(title, subtitle=""):
    t = Text.assemble((f" {ic('clean')} ", f"bold {PAL['accent']}"), (title, f"bold {PAL['text']}"))
    if subtitle:
        t.append("  " + subtitle, style=PAL["muted"])
    return Group(Text(""), t, Rule(style=PAL["line"]))


def hint(text):
    return Text("  " + text, style=PAL["muted"])


def legend(pairs):
    t = Text("  ")
    for label, col in pairs:
        t.append(ic("dot") + " ", style=col)
        t.append(label + "   ", style=PAL["muted"])
    return t


def safety_split(rows, width=14):
    by = {SAFE: 0, CAUTION: 0, RISKY: 0}
    for r in rows:
        if eligible(r):
            by[r.safety] += r.size
    return seg_bar([(by[k], SAFETY_COLOR[k]) for k in (SAFE, CAUTION, RISKY)], width)


def groups(items, mode):
    """[(name, description, rows)] in display order. Developer mode splits 'Developer & Pro Tools' by toolchain."""
    out = []
    for cat, desc in CATS:
        rows = [i for i in items if i.category == cat]
        if not rows:
            continue
        if mode == "dev" and cat == "Developer & Pro Tools":
            by = {}
            for i in rows:
                by.setdefault(toolchain(i), []).append(i)
            for n in TOOLCHAIN_NAMES:
                if n in by:
                    out.append((n, f"{n}: caches, SDKs, models and build output.", by[n]))
        else:
            out.append((cat, desc, rows))
    return out


def gsize(rows):
    return sum(r.size for r in rows if not r.managed)


def item_title(it, dev=False):
    flags = []
    if it.active_project:
        flags.append("active")
    if it.action == "root":
        flags.append("sudo")
    if it.readonly:
        flags.append("read-only")
    where = short(it.path or it.cmd, 50)
    return [("class:size", f"{fmt(it.size):>9}  "), (f"class:{it.safety}", f"{it.safety:<8} "),
            ("", f"{trunc(it.name, 36):<36} "), ("class:muted", where + (f"  [{', '.join(flags)}]" if flags else ""))]


def build_qstyle():
    return questionary.Style([
        ("qmark", f"fg:{PAL['accent']} bold"), ("question", "bold"), ("pointer", f"fg:{PAL['accent']} bold"),
        ("highlighted", f"fg:{PAL['accent']} bold"), ("selected", f"fg:{PAL['safe']}"), ("answer", f"fg:{PAL['accent']} bold"),
        ("instruction", f"fg:{PAL['muted']}"), ("separator", f"fg:{PAL['line']}"), ("text", ""),
        ("size", f"fg:{PAL['accent']}"), ("safe", f"fg:{PAL['safe']}"), ("caution", f"fg:{PAL['caution']}"),
        ("risky", f"fg:{PAL['risky']}"), ("muted", f"fg:{PAL['muted']}")])


class Session:
    def __init__(self, sc, settings, args):
        self.sc, self.settings, self.args = sc, settings, args
        self.console = Console(highlight=False)
        self.q = build_qstyle() if HAVE_Q else None
        self.apps = None
        self.analyzer = None
        self.app_sort = "total"
        self.app_idle_only = False
        self.app_query = ""

    @property
    def items(self):
        return self.sc.items

    @property
    def mode(self):
        return self.settings["mode"]

    @property
    def dev(self):
        return self.settings["mode"] == "dev"

    def say(self, *a, **k):
        self.console.print(*a, **k)

    def ask(self, q):
        """Run a questionary prompt; Ctrl-C / Esc returns None."""
        try:
            return q.ask()
        except (KeyboardInterrupt, EOFError):
            return None

    def pause(self, msg="press Enter to continue"):
        self.ask(questionary.text(msg, qmark=ic("next"), style=self.q))

    def persist(self):
        save_settings(self.settings)


def scan_view(sc, t0, tick):
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏" if _UTF8 else "|/-\\"
    spin = frames[tick % len(frames)]
    steps = [m for _, m in sc.log]
    rows = []
    for m in steps[-7:-1]:
        rows.append(Text.assemble((f" {ic('ok')} ", PAL["safe"]), (m, PAL["muted"])))
    if steps:
        rows.append(Text.assemble((f" {spin} ", PAL["accent"]), (steps[-1], PAL["text"])))
    with sc.lock:
        n = len(sc.items)
        total = sum(i.size for i in sc.items if not i.protected and not i.managed)
    foot = Text.assemble(("  found ", PAL["muted"]), (f"{n}", f"bold {PAL['text']}"), (" items  ·  ", PAL["muted"]),
                         (fmt(total), f"bold {PAL['accent']}"), (f"  ·  {time.time() - t0:0.0f}s", PAL["muted"]))
    return Panel(Group(*rows, Text(""), foot), title=f"[bold {PAL['accent']}]Scanning[/]", border_style=PAL["line"],
                 box=box.ROUNDED, padding=(1, 2), width=min(96, 100))


def run_scan(S):
    sc = S.sc
    err = []

    def work():
        try:
            sc.run()
        except Exception as e:                         # never leave the UI hanging on a scanner bug
            err.append(e)
            sc.done = True

    t0 = time.time()
    th = threading.Thread(target=work, daemon=True)
    th.start()
    k = 0
    with Live(scan_view(sc, t0, k), console=S.console, refresh_per_second=12, transient=True) as live:
        while th.is_alive():
            k += 1
            live.update(scan_view(sc, t0, k))
            time.sleep(0.08)
    th.join()
    if err:
        S.say(Text(f"  scan stopped early: {err[0]}", style=PAL["risky"]))


def render_dashboard(S, full=True):
    items = S.items
    t = totals(items)
    out = [title_bar("Mac Cleaner", "nothing is deleted without your say-so")]
    try:
        du = shutil.disk_usage(HOME)
        used = du.total - du.free
        out.append(Text.assemble(("  ", ""), (ic("disk") + " Disk  ", PAL["muted"]), meter(used / du.total, 30, PAL["hot"]),
                                 (f"  {fmt(used)} used of {fmt(du.total)}  ·  ", PAL["muted"]), (f"{fmt(du.free)} free", f"bold {PAL['text']}")))
        out.append(Text(""))
    except OSError:
        pass
    cards = [stat_card("You can free up", fmt(t["all"]), f"{fmt(t['oneclick'])} in one click", PAL["accent"]),
             stat_card("Safe", fmt(t[SAFE]), "rebuilds itself", PAL["safe"]),
             stat_card("Caution", fmt(t[CAUTION]), "costs time or bandwidth", PAL["caution"]),
             stat_card("Risky", fmt(t[RISKY]), "may hold real data", PAL["risky"])]
    out.append(Columns(cards, equal=True, expand=True))
    if t["managed"]:
        out.append(hint(f"+ {fmt(t['managed'])} that macOS manages itself (shown, never deleted)"))
    gs = groups(items, S.mode)
    per = [(gsize([r for r in rows if eligible(r)]), TILE_COLORS[i % len(TILE_COLORS)], n) for i, (n, _, rows) in enumerate(gs)]
    per = [p for p in per if p[0] > 0]
    if per:
        out.append(Text(""))
        out.append(Text.assemble("  ", seg_bar([(v, c) for v, c, _ in per], 78)))
        lg = Text("  ")
        for v, col, n in per[:8]:
            lg.append(ic("dot") + " ", style=col)
            lg.append(f"{n} {fmt(v)}   ", style=PAL["muted"])
        out.append(lg)
    if full:
        tb = Table(box=box.SIMPLE_HEAD, border_style=PAL["line"], header_style=f"bold {PAL['muted']}", pad_edge=False, expand=False)
        tb.add_column("", width=2)
        tb.add_column("Category")
        tb.add_column("Items", justify="right")
        tb.add_column("Size", justify="right")
        tb.add_column("Safe · caution · risky")
        for i, (n, desc, rows) in enumerate(gs, 1):
            tb.add_row(Text(ic(n if n in ICONS else "item"), style=TILE_COLORS[(i - 1) % len(TILE_COLORS)]),
                       Text(f"{i:>2}  {n}", style=PAL["text"]), str(len(rows)),
                       Text(fmt(gsize(rows)), style=f"bold {PAL['text']}"), safety_split(rows))
        out.append(Text(""))
        out.append(Padding(tb, (0, 0, 0, 2)))
    sel, tot, _ = selected_summary(items)
    if sel:
        out.append(Text.assemble(("  selected  ", PAL["muted"]), (f"{len(sel)} items · {fmt(tot)}", f"bold {PAL['accent']}")))
    return Group(*out)


def show(S, renderable, clear=True):
    if clear:
        S.console.clear()
    S.say(renderable)


def prefilter(S, rows, label="Filter by name or path (Enter = show all)"):
    q = S.ask(questionary.text(label, qmark=ic("search"), style=S.q))
    if q is None:
        return None
    q = q.strip().lower()
    return [r for r in rows if q in (r.name + " " + r.path).lower()] if q else rows


def pick_items(S, rows, title="Pick items", limit=300):
    """Checkbox list (space toggles, a = all, i = invert). Updates Item.selected for the rows shown."""
    pool = [r for r in rows if eligible(r)]
    cut = S.settings["min_mb"] * 1_000_000
    shown = [r for r in pool if r.size >= cut or r.size == 0 or r.selected]
    if not shown:
        shown = pool
    shown = prefilter(S, shown)
    if shown is None:
        return
    shown = sorted(shown, key=lambda r: -r.size)[:limit]
    if not shown:
        S.say(hint("nothing matches"))
        return
    choices = [questionary.Choice(title=item_title(r, S.dev), value=r.id, checked=r.selected) for r in shown]
    res = S.ask(questionary.checkbox(title, choices=choices, style=S.q, qmark=ic("next"),
                                     instruction="(space select · a all · i invert · enter confirm)"))
    if res is None:
        return
    chosen = set(res)
    for r in shown:
        r.selected = r.id in chosen


def inspect_item(S, it):
    g = Table.grid(padding=(0, 2))
    g.add_column(style=PAL["muted"], justify="right")
    g.add_column()
    g.add_row("Size", Text(fmt(it.size), style=f"bold {PAL['accent']}"))
    g.add_row("Safety", badge(it.safety))
    g.add_row("Category", it.category)
    g.add_row("Why", Text(it.reason or "-"))
    if it.regen:
        g.add_row("Comes back", Text(it.regen))
    if it.path:
        g.add_row("Path", Text(it.path, style=PAL["text"]))
    if it.keep:
        g.add_row("Kept copy", Text(it.keep, style=PAL["safe"]))
    if it.cmd and (S.dev or it.action in ("root", "cmd")):
        g.add_row("Command", Text(it.cmd, style=PAL["hot"]))
    if it.active_project:
        g.add_row("Note", Text("Active project (touched in the last 14 days)", style=PAL["caution"]))
    S.say(Panel(g, title=f"[bold]{it.name}[/]", border_style=PAL["line"], box=box.ROUNDED, padding=(1, 2)))
    ch = [questionary.Choice("Reveal in Finder", "reveal")] if it.path and IS_MAC else []
    if it.path:
        ch.append(questionary.Choice("Keep this out of every future scan (pin)", "pin"))
    ch.append(questionary.Choice(f"{ic('back')} Back", "back"))
    a = S.ask(questionary.select("Item", choices=ch, style=S.q, qmark=ic("next")))
    if a == "reveal":
        reveal(it.path)
    elif a == "pin":
        S.settings["pinned"] = sorted(set(S.settings["pinned"]) | {it.path})
        S.sc.pinned.add(it.path)
        S.sc.items[:] = [i for i in S.sc.items if i is not it]
        S.persist()
        S.say(hint("pinned - it will not show up again"))
        S.pause()


def item_table(rows, top=8, dev=False, show_why=True):
    tb = Table(box=box.SIMPLE_HEAD, border_style=PAL["line"], header_style=f"bold {PAL['muted']}", pad_edge=False)
    tb.add_column("#", justify="right", style=PAL["muted"])
    tb.add_column("Size", justify="right")
    tb.add_column("Safety")
    tb.add_column("Item", overflow="fold")
    if show_why:
        tb.add_column("Why / how it comes back", overflow="fold", style=PAL["muted"])
    for r in rows[:top]:
        tags = (" protected" if r.protected else "") + (" managed" if r.managed else "") + (" active" if r.active_project else "") \
            + (" sudo" if r.action == "root" else "")
        name = Text.assemble((trunc(r.name, 44), PAL["text"]), (tags, PAL["hot"]))
        if show_why:
            why = r.reason + (f"  [{r.regen}]" if r.regen else "")
            if dev and r.cmd:
                why += f"\n$ {r.cmd}"
            tb.add_row(str(r.id), Text(fmt(r.size), style=f"bold {PAL['text']}"), badge(r.safety), name, why)
        else:
            tb.add_row(str(r.id), Text(fmt(r.size), style=f"bold {PAL['text']}"), badge(r.safety), name)
    return tb


def flow_category(S, name, desc, rows):
    while True:
        alive = {id(i) for i in S.items}
        rows = [r for r in rows if id(r) in alive]
        sel_here = [r for r in rows if r.selected]
        show(S, Group(title_bar(name, desc),
                      Text.assemble(("  ", ""), (fmt(gsize(rows)), f"bold {PAL['accent']}"), (f"  ·  {len(rows)} items  ·  ", PAL["muted"]),
                                    (f"{len(sel_here)} selected ({fmt(sum(r.size for r in sel_here))})", PAL["text"])),
                      Padding(safety_split(rows, 40), (0, 0, 0, 2)), Text(""),
                      Padding(item_table(sorted(rows, key=lambda r: -r.size), 8, S.dev), (0, 0, 0, 2))))
        a = S.ask(questionary.select(name, style=S.q, qmark=ic("next"), choices=[
            questionary.Choice("Pick items…", "pick"),
            questionary.Choice("Select everything safe here", "safe"),
            questionary.Choice("Select everything here (asks about risky)", "all"),
            questionary.Choice("Clear selection here", "clear"),
            questionary.Choice("Inspect one item…", "inspect"),
            questionary.Choice(f"{ic('back')} Back", "back")]))
        if a in (None, "back"):
            return
        if a == "pick":
            pick_items(S, rows, name)
        elif a == "safe":
            select_level(rows, "safe")
        elif a == "all":
            todo = [r for r in rows if eligible(r)]
            if any(r.safety == RISKY for r in todo) and not ask_risky(S):
                todo = [r for r in todo if r.safety != RISKY]
            for r in todo:
                r.selected = True
        elif a == "clear":
            for r in rows:
                r.selected = False
        elif a == "inspect":
            sub = prefilter(S, sorted(rows, key=lambda r: -r.size))
            if sub:
                ch = [questionary.Choice(title=item_title(r, S.dev), value=r.id) for r in sub[:200]]
                pick = S.ask(questionary.select("Which item?", choices=ch, style=S.q, qmark=ic("next")))
                if pick is not None:
                    inspect_item(S, next(r for r in sub if r.id == pick))


def ask_risky(S):
    S.say(Panel(Text("Risky items can hold data that cannot be rebuilt: originals, backups, pinned SDKs, virtual machines.",
                     style=PAL["risky"]), border_style=PAL["risky"], box=box.ROUNDED))
    r = S.ask(questionary.text("Type I UNDERSTAND to include them", qmark=ic("warn"), style=S.q))
    return (r or "").strip() == "I UNDERSTAND"


def flow_browse(S):
    while True:
        gs = groups(S.items, S.mode)
        show(S, render_dashboard(S))
        ch = [questionary.Choice(title=[("class:muted", f"{i:>2}  "), ("", f"{n:<30}"), ("class:size", f"{fmt(gsize(rows)):>10}"),
                                        ("class:muted", f"   {len(rows)} items")], value=i - 1) for i, (n, d, rows) in enumerate(gs, 1)]
        ch.append(questionary.Choice(f"{ic('back')} Back", "back"))
        a = S.ask(questionary.select("Open a category", choices=ch, style=S.q, qmark=ic("next")))
        if a in (None, "back"):
            return
        n, d, rows = gs[a]
        flow_category(S, n, d, rows)


def copy_clip(text):
    if IS_MAC and shutil.which("pbcopy"):
        subprocess.run(["pbcopy"], input=text.encode(), check=False)
        return True
    return False


def flow_clean(S, items=None, label="Review & clean"):
    pool = items if items is not None else S.items
    sel, tot, by = selected_summary(pool)
    if not sel:
        S.say(hint("nothing selected yet - pick items first"))
        S.pause()
        return None
    tb = Table(box=box.SIMPLE_HEAD, border_style=PAL["line"], header_style=f"bold {PAL['muted']}", pad_edge=False)
    tb.add_column("Group")
    tb.add_column("Items", justify="right")
    tb.add_column("Size", justify="right")
    agg = {}
    for r in sel:
        a = agg.setdefault(group_name(r, S.mode), [0, 0])
        a[0] += 1
        a[1] += r.size
    for n, (c, s) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
        tb.add_row(n, str(c), Text(fmt(s), style=f"bold {PAL['text']}"))
    show(S, Group(title_bar(label, f"{len(sel)} items · {fmt(tot)}"), Padding(tb, (0, 0, 0, 2)),
                  Text.assemble(("  ", ""), (f"safe {fmt(by[SAFE])}", PAL["safe"]), ("   ", ""), (f"caution {fmt(by[CAUTION])}", PAL["caution"]),
                                ("   ", ""), (f"risky {fmt(by[RISKY])}", PAL["risky"]))))
    first = "rm" if S.settings["delete"] == "rm" else "trash"
    opts = [("trash", "Move to Trash (Put Back works)"), ("rm", "Delete permanently"), ("dry", "Dry run - show what would happen")]
    opts.sort(key=lambda o: o[0] != first)
    a = S.ask(questionary.select("How should it be removed?", style=S.q, qmark=ic("next"),
                                 choices=[questionary.Choice(t, v) for v, t in opts] + [questionary.Choice(f"{ic('back')} Cancel", "no")]))
    if a in (None, "no"):
        return None
    if by[RISKY] and a != "dry" and not ask_risky(S):
        S.say(hint("cancelled - risky items need the exact phrase"))
        S.pause()
        return None
    if a != "dry" and not S.ask(questionary.confirm(
            f"{'PERMANENTLY delete' if a == 'rm' else 'Move to Trash'} {len(sel)} items ({fmt(tot)})?", default=False, style=S.q)):
        return None
    done_paths, logs = set(), []
    prog = Progress(SpinnerColumn(style=PAL["accent"]), TextColumn("{task.description}"), BarColumn(complete_style=PAL["accent"], finished_style=PAL["safe"]),
                    TaskProgressColumn(), TimeElapsedColumn(), console=S.console, transient=True)
    with prog:
        task = prog.add_task("cleaning", total=len(sel))

        def tick(it, ok, msg):
            prog.update(task, advance=1, description=trunc(it.name, 40))
            if ok:
                done_paths.add(it.path or it.cmd)

        freed, roots, fails = execute(pool, permanent=(a == "rm"), dry_run=(a == "dry"), log=logs.append, tick=tick)
    if a != "dry" and done_paths:
        gone = {id(r) for r in sel if (r.path or r.cmd) in done_paths}
        S.sc.items[:] = [i for i in S.sc.items if id(i) not in gone and (i.path or i.cmd) not in done_paths]
    verb = "would free" if a == "dry" else "freed"
    body = [Text.assemble((f"{verb} ", PAL["muted"]), (fmt(freed), f"bold {PAL['safe']}"),
                          ("" if a in ("rm", "dry") else "   (empty the Trash to reclaim the space)", PAL["muted"]))]
    if fails:
        body.append(Text(""))
        body.append(Text(f"{ic('warn')} {len(fails)} could not be removed:", style=PAL["risky"]))
        for it, msg in fails[:8]:
            body.append(Text(f"   {trunc(it.name, 40)} - {trunc(msg, 70)}", style=PAL["muted"]))
    S.say(Panel(Group(*body), title="[bold]Done[/]", border_style=PAL["safe"], box=box.ROUNDED, padding=(1, 2)))
    if roots:
        cmds = "\n".join(roots)
        S.say(Panel(Text(cmds, style=PAL["hot"]), title="Run these in Terminal yourself (they need admin rights)",
                    border_style=PAL["caution"], box=box.ROUNDED, padding=(1, 2)))
        if IS_MAC and S.ask(questionary.confirm("Copy the commands to the clipboard?", default=True, style=S.q)):
            copy_clip(cmds)
    S.pause()
    return {"freed": freed, "done_paths": done_paths}


def analyze_apps(S):
    if S.apps is not None:
        return
    an = AppAnalyzer(S.sc)
    S.analyzer = an
    th = threading.Thread(target=lambda: an.run(), daemon=True)
    th.start()
    prog = Progress(SpinnerColumn(style=PAL["accent"]), TextColumn("Analysing applications"), BarColumn(complete_style=PAL["accent"]),
                    TaskProgressColumn(), console=S.console, transient=True)
    with prog:
        task = prog.add_task("apps", total=max(1, len(S.sc.installed)))
        while th.is_alive():
            prog.update(task, completed=an.progress, total=max(1, an.total or len(S.sc.installed)))
            time.sleep(0.1)
    th.join()
    S.apps = an.apps


def sorted_apps(S):
    apps = list(S.apps)
    if S.app_idle_only:
        apps = [a for a in apps if a.idle_days > 180 and not a.running]
    if S.app_query:
        apps = [a for a in apps if S.app_query in a.name.lower() or S.app_query in a.bundle_id.lower()]
    key = {"total": lambda a: -a.total, "size": lambda a: -a.size, "data": lambda a: -a.data_size,
           "used": lambda a: a.last_used, "name": lambda a: a.name.lower()}[S.app_sort]
    return sorted(apps, key=key)


def render_apps(S):
    apps = S.apps
    big = sum(a.size for a in apps)
    data = sum(a.data_size for a in apps)
    idle = [a for a in apps if a.idle_days > 180 and not a.running and not a.apple]
    cards = [stat_card("Applications", str(len(apps)), f"{sum(1 for a in apps if a.source == 'App Store')} from the App Store", PAL["accent"]),
             stat_card("Apps on disk", fmt(big), "the .app bundles", PAL["text"]),
             stat_card("Their data", fmt(data), "caches, support, containers", PAL["hot"]),
             stat_card("Not opened in 6 months", str(len(idle)), f"{fmt(sum(a.total for a in idle))} footprint", PAL["caution"])]
    top = sorted(apps, key=lambda a: -a.total)[:8]
    rest = sum(a.total for a in apps) - sum(a.total for a in top)
    parts = [(a.total, TILE_COLORS[i % len(TILE_COLORS)]) for i, a in enumerate(top)] + [(rest, PAL["line"])]
    lg = Text("  ")
    for i, a in enumerate(top[:6]):
        lg.append(ic("dot") + " ", style=TILE_COLORS[i % len(TILE_COLORS)])
        lg.append(f"{trunc(a.name, 16)} {fmt(a.total)}   ", style=PAL["muted"])
    rows = sorted_apps(S)
    tb = Table(box=box.SIMPLE_HEAD, border_style=PAL["line"], header_style=f"bold {PAL['muted']}", pad_edge=False)
    tb.add_column("", width=3)
    tb.add_column("Application")
    tb.add_column("App", justify="right")
    tb.add_column("Data", justify="right")
    tb.add_column("Total", justify="right")
    tb.add_column("Last used", justify="right")
    tb.add_column("Share")
    mx = max((a.total for a in rows), default=1) or 1
    for a in rows[:14]:
        tag = " running" if a.running else (" idle" if a.idle_days > 180 and not a.apple else "")
        tb.add_row(tile(a.name, a.bundle_id), Text.assemble((trunc(a.name, 30), PAL["text"]), (tag, PAL["caution"])),
                   fmt(a.size), fmt(a.data_size), Text(fmt(a.total), style=f"bold {PAL['text']}"), rel_time(a.last_used),
                   meter(a.total / mx, 14, TILE_COLORS[zlib.crc32((a.bundle_id or a.name).encode()) % len(TILE_COLORS)]))
    flt = []
    if S.app_idle_only:
        flt.append("idle only")
    if S.app_query:
        flt.append(f"matching '{S.app_query}'")
    sub = f"sorted by {S.app_sort}" + (" · " + ", ".join(flt) if flt else "")
    return Group(title_bar("Applications", sub), Columns(cards, equal=True, expand=True), Text(""),
                 Text.assemble("  ", seg_bar(parts, 78)), lg, Text(""), Padding(tb, (0, 0, 0, 2)),
                 hint(f"showing {min(14, len(rows))} of {len(rows)} · open any app below for its full breakdown"))


def render_app_detail(a):
    g = Table.grid(padding=(0, 2))
    g.add_column(style=PAL["muted"], justify="right")
    g.add_column()
    g.add_row("Version", a.version or "-")
    g.add_row("Bundle id", a.bundle_id or "-")
    g.add_row("Source", a.source + (f"  ·  {a.category}" if a.category else ""))
    g.add_row("Last used", rel_time(a.last_used) + ("   (running now)" if a.running else ""))
    g.add_row("Location", short(a.path, 70))
    g.add_row("Footprint", Text(fmt(a.total), style=f"bold {PAL['accent']}"))
    head = Text.assemble(tile(a.name, a.bundle_id), (f"  {a.name}", f"bold {PAL['text']}"))
    bd = Table(box=box.SIMPLE_HEAD, border_style=PAL["line"], header_style=f"bold {PAL['muted']}", pad_edge=False)
    bd.add_column("What")
    bd.add_column("Kind")
    bd.add_column("Size", justify="right")
    bd.add_column("Share")
    bd.add_column("Where", style=PAL["muted"], overflow="fold")
    tot = a.total or 1
    bd.add_row("Application bundle", "app", Text(fmt(a.size), style=f"bold {PAL['text']}"), meter(a.size / tot, 16, PAL["accent"]), short(a.path, 40))
    kc = {"cache": PAL["safe"], "data": PAL["caution"], "prefs": PAL["hot"]}
    for p in a.parts:
        bd.add_row(p.label, Text(p.kind, style=kc[p.kind]), Text(fmt(p.size), style=f"bold {PAL['text']}"),
                   meter(p.size / tot, 16, kc[p.kind]), short(p.path, 40))
    stack = seg_bar([(a.size, PAL["accent"]), (a.cache_size, PAL["safe"]), (max(0, a.data_size - a.cache_size), PAL["caution"])], 60)
    return Group(Text(""), Padding(head, (0, 0, 0, 2)), Text(""), Padding(g, (0, 0, 0, 2)), Text(""),
                 Text.assemble("  ", stack),
                 legend([("app", PAL["accent"]), ("caches (safe)", PAL["safe"]), ("data & settings", PAL["caution"])]),
                 Padding(bd, (1, 0, 0, 2)))


def quit_app(S, a):
    if not a.running:
        return True
    if not S.ask(questionary.confirm(f"{a.name} is running. Quit it now?", default=True, style=S.q)):
        return False
    run(["osascript", "-e", f'tell application "{esc_as(os.path.basename(a.path)[:-4])}" to quit'], 10)
    time.sleep(2)
    a.running = False
    return True


def flow_app(S, a):
    while True:
        show(S, Group(title_bar("Application"), render_app_detail(a)))
        ch = []
        if a.cache_size:
            ch.append(questionary.Choice(f"Clear caches, logs & window state  ({fmt(a.cache_size)}, safe)", "caches"))
        if a.removable and not (a.apple and not a.parts):
            ch.append(questionary.Choice(f"Uninstall completely - app and all its data  ({fmt(a.total)})", "uninstall"))
        ch.append(questionary.Choice("Choose exactly what to remove…", "pick"))
        if IS_MAC:
            ch.append(questionary.Choice("Reveal in Finder", "reveal"))
        ch.append(questionary.Choice(f"{ic('back')} Back", "back"))
        act = S.ask(questionary.select(a.name, choices=ch, style=S.q, qmark=ic("next")))
        if act in (None, "back"):
            return
        if act == "reveal":
            reveal(a.path)
            continue
        picked = None
        if act == "pick":
            opts = []
            if a.removable:
                opts.append(questionary.Choice(title=[("class:size", f"{fmt(a.size):>9}  "), ("class:caution", "caution  "), ("", "Application bundle")], value=a.path))
            for p in a.parts:
                lvl = "safe" if p.kind == "cache" else "caution"
                opts.append(questionary.Choice(title=[("class:size", f"{fmt(p.size):>9}  "), (f"class:{lvl}", f"{lvl:<8} "), ("", p.label), ("class:muted", "  " + short(p.path, 46))], value=p.path))
            picked = S.ask(questionary.checkbox("Select what to remove", choices=opts, style=S.q, qmark=ic("next"),
                                                instruction="(space select · enter confirm)"))
            if not picked:
                continue
            act = "pick"
        if act in ("uninstall", "pick") and (act == "uninstall" or a.path in (picked or [])) and not quit_app(S, a):
            continue
        its = app_items(a, act, picked)
        if not its:
            S.say(hint("nothing to remove"))
            S.pause()
            continue
        res = flow_clean(S, its, f"{a.name}")
        if res and res["done_paths"]:
            a.parts = [p for p in a.parts if p.path not in res["done_paths"]]
            if a.path in res["done_paths"]:
                S.apps = [x for x in S.apps if x is not a]
                return


def flow_apps(S):
    analyze_apps(S)
    while True:
        show(S, render_apps(S))
        ch = [questionary.Choice("Open an application…", "open"),
              questionary.Choice(f"Sort by…  (now: {S.app_sort})", "sort"),
              questionary.Choice(f"Only apps not opened in 6 months: {'ON' if S.app_idle_only else 'off'}", "idle"),
              questionary.Choice("Search by name…", "search"),
              questionary.Choice(f"{ic('back')} Back", "back")]
        a = S.ask(questionary.select("Applications", choices=ch, style=S.q, qmark=ic("next")))
        if a in (None, "back"):
            return
        if a == "sort":
            s = S.ask(questionary.select("Sort by", style=S.q, qmark=ic("next"), choices=[
                questionary.Choice("Total footprint (app + data)", "total"), questionary.Choice("App size", "size"),
                questionary.Choice("Data size", "data"), questionary.Choice("Least recently used", "used"), questionary.Choice("Name", "name")]))
            S.app_sort = s or S.app_sort
        elif a == "idle":
            S.app_idle_only = not S.app_idle_only
        elif a == "search":
            S.app_query = (S.ask(questionary.text("App name or bundle id (empty clears)", qmark=ic("search"), style=S.q)) or "").strip().lower()
        elif a == "open":
            rows = sorted_apps(S)
            if not rows:
                continue
            chs = [questionary.Choice(title=[("", f"{trunc(r.name, 30):<30} "), ("class:size", f"{fmt(r.total):>10}  "),
                                              ("class:muted", f"{r.source:<9} {rel_time(r.last_used)}")], value=r.id) for r in rows]
            pick = S.ask(questionary.select("Which application?", choices=chs, style=S.q, qmark=ic("next")))
            if pick is not None:
                flow_app(S, next(r for r in S.apps if r.id == pick))


def flow_biggest(S):
    rows = S.sc.biggest(100)
    show(S, Group(title_bar("Biggest files", "largest first, across your whole home folder"),
                  Padding(item_table(rows, 25, S.dev), (0, 0, 0, 2)), hint("media libraries are shown but protected")))
    pick_items(S, rows, "Biggest files")
    if any(r.selected for r in rows):
        flow_clean(S)


def flow_duplicates(S):
    rows = [i for i in S.items if i.category == "Duplicate Files"]
    sets = {}
    for r in rows:
        sets.setdefault(r.set_id, []).append(r)
    if not sets:
        show(S, Group(title_bar("Duplicate files"), hint("no duplicates found")))
        S.pause()
        return
    ordered = sorted(sets.values(), key=lambda g: -sum(x.size for x in g))
    show(S, Group(title_bar("Duplicate files", "matched by content (size, partial hash, SHA-256) - one copy is always kept"),
                  Text.assemble(("  reclaimable  ", PAL["muted"]), (fmt(sum(r.size for r in rows)), f"bold {PAL['accent']}"),
                                (f"  ·  {len(ordered)} sets", PAL["muted"]))))
    ch = []
    for g in ordered[:200]:
        total = sum(x.size for x in g)
        ch.append(questionary.Choice(title=[("class:size", f"{fmt(total):>9}  "), ("", f"{trunc(g[0].name, 34):<34} "),
                                            ("class:muted", f"{len(g) + 1} copies · keeps {short(g[0].keep, 40)}")],
                                     value=g[0].set_id, checked=all(x.selected for x in g)))
    res = S.ask(questionary.checkbox("Select sets to remove the extra copies of", choices=ch, style=S.q, qmark=ic("next"),
                                     instruction="(space select · a all · enter confirm)"))
    if res is None:
        return
    for sid, g in sets.items():
        for x in g:
            x.selected = sid in res
    if res:
        flow_clean(S)


SYSTEM_EXPLAINED = [
    ("iOS / device support", "Xcode copies symbols from every iPhone/iPad you plug in, one per iOS version.", "safe - re-created when the device connects"),
    ("Simulators", "iOS simulators whose runtime is gone can never boot.", "safe - xcrun simctl delete unavailable"),
    ("Time Machine snapshots", "Local APFS snapshots; macOS also thins them itself.", "caution - sudo tmutil deletelocalsnapshots <date>"),
    ("Diagnostics & caches", "Crash reports, logs and system caches.", "safe / caution - some need admin rights"),
    ("macOS updates", "Downloaded update payloads in /Library/Updates.", "safe - macOS downloads them again"),
    ("Swap & Spotlight", "Virtual memory and the search index. macOS manages both.", "never deleted - a restart / mdutil handles them"),
]


def flow_system(S):
    rows = [i for i in S.items if i.category == "System Data"]
    tb = Table(box=box.SIMPLE_HEAD, border_style=PAL["line"], header_style=f"bold {PAL['muted']}", pad_edge=False)
    tb.add_column("Part of System Data")
    tb.add_column("What it is", overflow="fold")
    tb.add_column("Handling", style=PAL["muted"], overflow="fold")
    for a, b, c_ in SYSTEM_EXPLAINED:
        tb.add_row(Text(a, style=PAL["text"]), b, c_)
    show(S, Group(title_bar("System Data", "the mystery bar in macOS Storage, explained"), Padding(tb, (0, 0, 1, 2)),
                  Text("  Found on this Mac", style=f"bold {PAL['muted']}"),
                  Padding(item_table(sorted(rows, key=lambda r: -r.size), 12, S.dev), (0, 0, 0, 2))))
    if rows:
        flow_category(S, "System Data", CAT_DESC["System Data"], rows)


def flow_settings(S):
    while True:
        fda = full_disk_access()
        fda_txt = {True: "granted", False: "not granted", None: "unknown"}[fda]
        g = Table.grid(padding=(0, 2))
        g.add_column(style=PAL["muted"], justify="right")
        g.add_column()
        g.add_row("Mode", "Developer (toolchain groups, terminal commands)" if S.dev else "Normal (plain-language categories)")
        g.add_row("Removal default", "Delete permanently" if S.settings["delete"] == "rm" else "Move to Trash")
        g.add_row("Hide items below", f"{S.settings['min_mb']} MB")
        g.add_row("Full Disk Access", Text(fda_txt, style=PAL["safe"] if fda else PAL["caution"]))
        g.add_row("Pinned (kept out of scans)", str(len(S.settings["pinned"])))
        g.add_row("Settings file", short(SETTINGS_FILE, 60))
        show(S, Group(title_bar("Settings"), Padding(g, (1, 0, 0, 2))))
        a = S.ask(questionary.select("Change", style=S.q, qmark=ic("next"), choices=[
            questionary.Choice("Switch Normal / Developer mode", "mode"),
            questionary.Choice("Switch removal default Trash / permanent", "del"),
            questionary.Choice("Minimum size shown in lists…", "min"),
            questionary.Choice("Open Full Disk Access settings", "fda"),
            questionary.Choice("Manage pinned items…", "pins"),
            questionary.Choice(f"{ic('back')} Back", "back")]))
        if a in (None, "back"):
            return
        if a == "mode":
            S.settings["mode"] = "normal" if S.dev else "dev"
        elif a == "del":
            S.settings["delete"] = "trash" if S.settings["delete"] == "rm" else "rm"
        elif a == "min":
            v = S.ask(questionary.text("Minimum MB", default=str(S.settings["min_mb"]), style=S.q))
            try:
                S.settings["min_mb"] = max(0, float(v))
            except (TypeError, ValueError):
                pass
        elif a == "fda":
            open_fda_settings()
            S.say(hint("enable your terminal app in the list, then restart this tool"))
            S.pause()
        elif a == "pins" and S.settings["pinned"]:
            res = S.ask(questionary.checkbox("Untick to keep pinned, tick to un-pin", style=S.q, qmark=ic("next"),
                                             choices=[questionary.Choice(short(p, 80), p) for p in S.settings["pinned"]]))
            if res:
                S.settings["pinned"] = [p for p in S.settings["pinned"] if p not in res]
                S.sc.pinned -= set(res)
                S.say(hint("un-pinned - they show up again after the next rescan"))
                S.pause()
        S.persist()


def rescan(S):
    a = S.args
    S.sc = Scanner(a.large_mb, a.old_days, a.dup_min_mb, quiet=True, pinned=S.settings["pinned"])
    S.apps = None
    run_scan(S)


def tui(S):
    while True:
        sel, tot, _ = selected_summary(S.items)
        show(S, render_dashboard(S))
        choices = [
            questionary.Choice("Review & clean by category", "browse"),
            questionary.Choice("Quick clean - select everything safe", "quick"),
            questionary.Choice("Applications - sizes, data and cleanup", "apps"),
            questionary.Choice("Biggest files", "big"),
            questionary.Choice("Duplicate files", "dups"),
            questionary.Choice("System Data explained", "sys"),
        ]
        if sel:
            choices.append(questionary.Choice(f"Clean selection  ({len(sel)} items · {fmt(tot)})", "clean"))
        choices += [questionary.Separator(), questionary.Choice("Settings", "settings"), questionary.Choice("Export report as JSON", "json"),
                    questionary.Choice("Rescan", "rescan"), questionary.Choice("Quit", "quit")]
        a = S.ask(questionary.select("What next?", choices=choices, style=S.q, qmark=ic("next")))
        if a in (None, "quit"):
            return
        if a == "browse":
            flow_browse(S)
        elif a == "quick":
            n = select_level(S.items, "safe")
            S.say(hint(f"selected {n} safe items"))
            flow_clean(S, label="Quick clean")
        elif a == "apps":
            flow_apps(S)
        elif a == "big":
            flow_biggest(S)
        elif a == "dups":
            flow_duplicates(S)
        elif a == "sys":
            flow_system(S)
        elif a == "clean":
            flow_clean(S)
        elif a == "settings":
            flow_settings(S)
        elif a == "json":
            p = S.ask(questionary.text("Write to", default="mac_cleaner_report.json", style=S.q))
            if p:
                export_json(S.items, p)
                S.pause()
        elif a == "rescan":
            rescan(S)


def rich_report(S, top=8, show_all=False):
    """Non-interactive report (used for --report, --clean and when stdin is not a terminal)."""
    S.say(render_dashboard(S))
    cut = S.settings["min_mb"] * 1_000_000
    for i, (n, d, rows) in enumerate(groups(S.items, S.mode), 1):
        shown = [r for r in sorted(rows, key=lambda r: -r.size) if r.size >= cut or r.size == 0 or show_all]
        if not shown:
            continue
        S.say(Text.assemble(("\n  ", ""), (f"{i:>2}  {n}", f"bold {PAL['text']}"), (f"   {fmt(gsize(rows))} · {len(rows)} items", PAL["muted"])))
        S.say(Padding(item_table(shown, len(shown) if show_all else top, S.dev), (0, 0, 0, 4)))
