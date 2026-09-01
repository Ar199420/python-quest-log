#!/usr/bin/env python3
"""
Quest Log — RPG-style Python learning tracker.
Dibuat untuk dipakai di Termux. Tidak butuh library luar (pure stdlib).

Penggunaan cepat:
    python3 quest_log.py init            # setup pertama kali
    python3 quest_log.py list            # lihat semua quest & status
    python3 quest_log.py hint <id>       # lihat hint singkat (skill description)
    python3 quest_log.py start <id>      # mulai quest
    python3 quest_log.py complete <id>   # tandai selesai, dapat XP, auto commit
    python3 quest_log.py status          # lihat character sheet
"""

import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
QUESTS_FILE = BASE_DIR / "quests_data.json"
CHALLENGES_FILE = BASE_DIR / "challenges_data.json"
STATE_FILE = BASE_DIR / "state.json"
README_FILE = BASE_DIR / "README.md"
WORKSHOP_DIR = BASE_DIR / "workshop"

SHEET_START = "<!-- CHARACTER_SHEET_START -->"
SHEET_END = "<!-- CHARACTER_SHEET_END -->"


# ---------- data helpers ----------

def load_quests():
    with open(QUESTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["quests"]


def load_challenges():
    if not CHALLENGES_FILE.exists():
        return {}
    with open(CHALLENGES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def workshop_path(qid, challenges=None):
    challenges = challenges or load_challenges()
    mode = challenges.get(str(qid), {}).get("mode", "function")
    ext = "html" if mode == "html" else "py"
    return WORKSHOP_DIR / f"quest_{qid:02d}.{ext}"


def ensure_workshop_file(qid, challenge):
    WORKSHOP_DIR.mkdir(exist_ok=True)
    path = workshop_path(qid, {str(qid): challenge})
    if not path.exists():
        path.write_text(challenge["template"], encoding="utf-8")
    return path


def run_verification(qid):
    """
    Jalankan file latihan user beneran (bukan self-report) dan cek
    terhadap test case bertingkat. Return dict hasil per tier.

    Ada 2 mode, tergantung materi quest:
    - "script": user cukup tulis variabel biasa (tanpa def/return).
      Dipakai untuk quest yang belum mengajarkan fungsi.
    - "function": user harus tulis def dengan nama & parameter tertentu.
      Baru dipakai mulai quest yang sudah mengajarkan fungsi (Quest 7+).
    """
    challenges = load_challenges()
    challenge = challenges.get(str(qid))
    if not challenge:
        return None  # quest ini belum punya verifikasi otomatis

    path = workshop_path(qid, challenges)
    if not path.exists():
        return {"error": f"File latihan belum ada. Jalankan: workshop {qid}"}

    mode = challenge.get("mode", "function")

    if mode == "html":
        raw_text = path.read_text(encoding="utf-8")
        analyzer = SimpleHTMLAnalyzer()
        try:
            analyzer.feed(raw_text)
        except Exception as e:
            return {"error": f"HTML tidak bisa diparse: {e}"}

        tier_results = []
        for tier in challenge["tiers"]:
            cases = []
            tier_passed = True
            for rule in tier["checks"]:
                ok = check_html_rule(analyzer, raw_text, rule)
                tier_passed = tier_passed and ok
                cases.append({
                    "label": rule.get("label", str(rule)),
                    "expected": "ada / sesuai",
                    "actual": "ditemukan" if ok else "TIDAK ditemukan",
                    "ok": ok,
                })
            tier_results.append({"name": tier["name"], "passed": tier_passed, "cases": cases})
        return {"tiers": tier_results}

    spec = importlib.util.spec_from_file_location(f"quest_{qid:02d}", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        return {"error": f"File kamu error saat dijalankan: {e}"}

    mode = challenge.get("mode", "function")
    tier_results = []

    if mode == "script":
        for tier in challenge["tiers"]:
            cases = []
            tier_passed = True
            for check in tier["checks"]:
                var = check["var"]
                expected = check["expected"]
                actual = getattr(mod, var, "<variabel tidak ditemukan>")
                if isinstance(actual, set):
                    ok = sorted(actual, key=str) == sorted(expected, key=str)
                else:
                    ok = actual == expected
                tier_passed = tier_passed and ok
                cases.append({
                    "label": f"variabel '{var}'",
                    "expected": expected,
                    "actual": actual,
                    "ok": ok,
                })
            tier_results.append({"name": tier["name"], "passed": tier_passed, "cases": cases})
        return {"tiers": tier_results}

    # mode == "function" -- setiap tier boleh punya nama fungsi sendiri
    # (default ke challenge["function"] kalau tier tidak menentukan)
    for tier in challenge["tiers"]:
        func_name = tier.get("function", challenge.get("function"))
        func = getattr(mod, func_name, None)
        cases = []
        tier_passed = True
        if func is None or not callable(func):
            tier_results.append({
                "name": tier["name"],
                "passed": False,
                "cases": [{
                    "label": f"fungsi '{func_name}'",
                    "expected": "ada di file kamu",
                    "actual": "TIDAK ditemukan",
                    "ok": False,
                }],
            })
            continue
        for case in tier["tests"]:
            try:
                actual = func(*case["args"])
            except Exception as e:
                actual = f"ERROR: {e}"
            expected = case["expected"]
            if isinstance(actual, tuple) and isinstance(expected, list):
                ok = list(actual) == expected
            else:
                ok = actual == expected
            tier_passed = tier_passed and ok
            cases.append({
                "label": f"{func_name}{tuple(case['args'])}",
                "expected": case["expected"],
                "actual": actual,
                "ok": ok,
            })
        tier_results.append({"name": tier["name"], "passed": tier_passed, "cases": cases})

    return {"tiers": tier_results}



def print_verification(result):
    if "error" in result:
        print(f"Gagal verifikasi: {result['error']}")
        return False

    all_passed = True
    for tier in result["tiers"]:
        status = "LULUS" if tier["passed"] else "GAGAL"
        print(f"\n[{status}] Tier: {tier['name']}")
        for c in tier["cases"]:
            mark = "OK " if c["ok"] else "X  "
            if c["ok"]:
                print(f"  {mark} {c['label']} -> {c['actual']}")
            else:
                print(f"  {mark} {c['label']} -> hasilmu: {c['actual']}  (harusnya: {c['expected']})")
        if not tier["passed"]:
            all_passed = False
    return all_passed


class SimpleHTMLAnalyzer(HTMLParser):
    """Parser HTML minimal: kumpulkan semua tag, atributnya, dan teks di dalamnya."""

    def __init__(self):
        super().__init__()
        self.tags = []
        self._stack = []

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "text": ""}
        self.tags.append(node)
        self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.tags.append({"tag": tag, "attrs": dict(attrs), "text": ""})

    def handle_endtag(self, tag):
        if self._stack:
            self._stack.pop()

    def handle_data(self, data):
        if self._stack:
            self._stack[-1]["text"] += data


def check_html_rule(analyzer, raw_text, rule):
    rtype = rule["type"]
    if rtype == "tag_exists":
        return any(t["tag"] == rule["tag"] for t in analyzer.tags)
    if rtype == "tag_attr_exists":
        return any(t["tag"] == rule["tag"] and rule["attr"] in t["attrs"] for t in analyzer.tags)
    if rtype == "tag_attr_equals":
        return any(
            t["tag"] == rule["tag"] and (t["attrs"].get(rule["attr"]) or "").lower() == rule["value"].lower()
            for t in analyzer.tags
        )
    if rtype == "tag_count_min":
        return sum(1 for t in analyzer.tags if t["tag"] == rule["tag"]) >= rule["min"]
    if rtype == "tag_has_text":
        return any(t["tag"] == rule["tag"] and t["text"].strip() for t in analyzer.tags)
    if rtype == "css_contains":
        value = rule.get("value", "")
        props = rule.get("properties") or [rule["property"]]
        prop_pattern = "(?:" + "|".join(re.escape(p) for p in props) + ")"
        if value:
            pattern = prop_pattern + r"\s*:\s*[^;}\"']*" + re.escape(value)
        else:
            pattern = prop_pattern + r"\s*:\s*[^;}\"'\s][^;}\"']*"
        return re.search(pattern, raw_text, re.IGNORECASE) is not None
    return False


def load_state():
    if not STATE_FILE.exists():
        return {"xp": 0, "progress": {}, "log": []}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_status(quest, state):
    prog = state["progress"].get(str(quest["id"]))
    if prog == "completed":
        return "completed"
    if prog == "in_progress":
        return "in_progress"
    if quest["prereq"] is None:
        return "available"
    prereq_status = state["progress"].get(str(quest["prereq"]))
    return "available" if prereq_status == "completed" else "locked"


def level_from_xp(xp):
    # 100 XP per level, sederhana dan mudah diprediksi
    return xp // 100 + 1


def xp_to_next_level(xp):
    return 100 - (xp % 100)


# ---------- commands ----------

def cmd_init(_args):
    if STATE_FILE.exists():
        print("Quest log sudah pernah di-init. State tidak ditimpa.")
        return
    save_state({"xp": 0, "progress": {}, "log": []})
    print("Quest log berhasil dibuat. Ketik: python3 quest_log.py list")
    update_readme()


def cmd_list(_args):
    quests = load_quests()
    state = load_state()
    icon = {
        "completed": "[x]",
        "in_progress": "[~]",
        "available": "[ ]",
        "locked": "[#]",
    }
    print(f"{'ID':<3} {'':<5} {'Rank':<5} {'XP':<4} Nama Quest")
    print("-" * 50)
    for q in quests:
        st = get_status(q, state)
        tag = " (BOSS)" if q["boss"] else ""
        print(f"{q['id']:<3} {icon[st]:<5} {q['rank']:<5} {q['xp']:<4} {q['name']}{tag}")
    print("-" * 50)
    print("Legenda: [x] selesai  [~] sedang dikerjakan  [ ] tersedia  [#] terkunci")


def find_quest(quests, qid):
    for q in quests:
        if q["id"] == qid:
            return q
    return None


def cmd_hint(args):
    quests = load_quests()
    state = load_state()
    q = find_quest(quests, args.id)
    if not q:
        print(f"Quest #{args.id} tidak ditemukan.")
        return
    st = get_status(q, state)
    if st == "locked":
        print(f"Quest '{q['name']}' masih terkunci. Selesaikan prasyaratnya dulu.")
        return
    print(f"\n=== {q['name']} (Rank {q['rank']}, {q['xp']} XP) ===")
    print(q["hint"])
    print("\nCatatan: ini cuma petunjuk arah, bukan tutorial lengkap.")
    print("Coba dulu sendiri di REPL / neovim sebelum cari referensi lain.\n")


def cmd_start(args):
    quests = load_quests()
    state = load_state()
    q = find_quest(quests, args.id)
    if not q:
        print(f"Quest #{args.id} tidak ditemukan.")
        return
    st = get_status(q, state)
    if st == "locked":
        print(f"Quest '{q['name']}' masih terkunci.")
        return
    if st == "completed":
        print(f"Quest '{q['name']}' sudah selesai. Lihat lagi hint? pakai: hint {q['id']}")
        return
    state["progress"][str(q["id"])] = "in_progress"
    save_state(state)
    print(f"Quest dimulai: {q['name']}")
    cmd_hint(args)


def cmd_workshop(args):
    challenges = load_challenges()
    challenge = challenges.get(str(args.id))
    if not challenge:
        print(f"Quest #{args.id} belum punya latihan otomatis (mode manual masih berlaku).")
        return
    path = ensure_workshop_file(args.id, challenge)
    print(f"File latihan: {path}")
    print(f"Buka dengan: nvim {path}")
    if challenge.get("mode") == "html":
        print(f"Lengkapi HTML/CSS-nya, lalu jalankan: verify {args.id}")
    elif challenge.get("mode") == "script":
        print(f"Isi bagian '???' di file itu, lalu jalankan: verify {args.id}")
    else:
        print(f"Lengkapi fungsi-fungsi di file itu, lalu jalankan: verify {args.id}")


def cmd_verify(args):
    result = run_verification(args.id)
    if result is None:
        print("Quest ini belum punya verifikasi otomatis. Pakai 'complete' dengan jujur ya.")
        return
    passed = print_verification(result)
    print()
    if "error" not in result:
        if passed:
            print("Semua tier LULUS. Sekarang jalankan: complete", args.id)
        else:
            print("Belum semua tier lulus. Perbaiki dulu, lalu verify lagi.")


def cmd_complete(args):
    quests = load_quests()
    state = load_state()
    q = find_quest(quests, args.id)
    if not q:
        print(f"Quest #{args.id} tidak ditemukan.")
        return
    st = get_status(q, state)
    if st == "locked":
        print(f"Quest '{q['name']}' masih terkunci, belum bisa diselesaikan.")
        return
    if st == "completed":
        print(f"Quest '{q['name']}' sudah pernah selesai sebelumnya.")
        return

    # --- verifikasi otomatis, bukan self-report ---
    result = run_verification(args.id)
    if result is not None:
        if "error" in result:
            print(f"Belum bisa diselesaikan: {result['error']}")
            return
        all_passed = all(t["passed"] for t in result["tiers"])
        if not all_passed:
            print("Kode kamu belum lolos semua tes. Jalankan dulu untuk lihat detailnya:")
            print(f"  verify {args.id}")
            return
        print("Verifikasi otomatis: semua tier LULUS.\n")
    else:
        print("(Quest ini belum punya verifikasi otomatis — ditandai selesai berdasarkan laporanmu.)")

    state["progress"][str(q["id"])] = "completed"
    state["xp"] += q["xp"]
    state["log"].append({
        "quest_id": q["id"],
        "name": q["name"],
        "xp": q["xp"],
        "time": datetime.now().isoformat(timespec="seconds"),
    })
    save_state(state)

    new_level = level_from_xp(state["xp"])
    print(f"Quest selesai: {q['name']}  (+{q['xp']} XP)")
    print(f"Total XP: {state['xp']}  |  Level {new_level}")

    update_readme()
    git_commit(q, new_level)


def cmd_status(_args):
    quests = load_quests()
    state = load_state()
    xp = state["xp"]
    level = level_from_xp(xp)
    completed = [q for q in quests if get_status(q, state) == "completed"]
    total = len(quests)

    bar_len = 20
    filled = int(bar_len * (xp % 100) / 100)
    bar = "#" * filled + "-" * (bar_len - filled)

    print("=" * 40)
    print("        CHARACTER SHEET")
    print("=" * 40)
    print(f"Level     : {level}")
    print(f"XP        : {xp}  (butuh {xp_to_next_level(xp)} lagi ke level berikut)")
    print(f"[{bar}]")
    print(f"Quest     : {len(completed)}/{total} selesai")
    print("Skill dikuasai:")
    if completed:
        for q in completed:
            print(f"  - {q['name']} (Rank {q['rank']})")
    else:
        print("  (belum ada, mulai quest pertama: start 1)")
    print("=" * 40)


def git_commit(quest, level):
    if not (BASE_DIR / ".git").exists():
        return
    msg = f"feat(lvl{level}): unlock {quest['name']}"
    try:
        subprocess.run(["git", "add", "-A"], cwd=BASE_DIR, check=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "commit", "-m", msg], cwd=BASE_DIR, check=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Git commit dibuat: \"{msg}\"")
    except subprocess.CalledProcessError:
        print("Git commit dilewati (mungkin tidak ada perubahan file, atau belum ada quest.py yang diedit).")


def update_readme():
    quests = load_quests()
    state = load_state()
    xp = state["xp"]
    level = level_from_xp(xp)
    completed = [q for q in quests if get_status(q, state) == "completed"]
    total = len(quests)

    lines = [
        SHEET_START,
        "## Character Sheet",
        "",
        f"- **Level:** {level}",
        f"- **XP:** {xp}",
        f"- **Progress:** {len(completed)}/{total} quest selesai",
        "",
        "**Skill dikuasai:**",
    ]
    if completed:
        for q in completed:
            lines.append(f"- [x] {q['name']} (Rank {q['rank']})")
    else:
        lines.append("- _(belum ada quest yang selesai)_")
    lines.append(SHEET_END)
    sheet_block = "\n".join(lines)

    if README_FILE.exists():
        content = README_FILE.read_text(encoding="utf-8")
        if SHEET_START in content and SHEET_END in content:
            pre = content.split(SHEET_START)[0]
            post = content.split(SHEET_END)[1]
            content = pre + sheet_block + post
        else:
            content = content.rstrip() + "\n\n" + sheet_block + "\n"
    else:
        content = "# Python Quest Log\n\n" + sheet_block + "\n"

    README_FILE.write_text(content, encoding="utf-8")


# ---------- entrypoint ----------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RPG-style Python quest tracker")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init", help="Setup quest log pertama kali")
    sub.add_parser("list", help="Lihat semua quest")
    sub.add_parser("status", help="Lihat character sheet")

    p_hint = sub.add_parser("hint", help="Lihat hint quest")
    p_hint.add_argument("id", type=int)

    p_start = sub.add_parser("start", help="Mulai quest")
    p_start.add_argument("id", type=int)

    p_complete = sub.add_parser("complete", help="Selesaikan quest")
    p_complete.add_argument("id", type=int)

    p_workshop = sub.add_parser("workshop", help="Buat/buka file latihan untuk quest")
    p_workshop.add_argument("id", type=int)

    p_verify = sub.add_parser("verify", help="Jalankan tes otomatis pada file latihanmu")
    p_verify.add_argument("id", type=int)

    args = parser.parse_args()
    if args.cmd is None:
        parser.print_help()
        sys.exit(0)

    if not STATE_FILE.exists() and args.cmd != "init":
        print("Belum di-init. Jalankan dulu: python3 quest_log.py init")
        sys.exit(1)

    commands = {
        "init": cmd_init,
        "list": cmd_list,
        "hint": cmd_hint,
        "start": cmd_start,
        "complete": cmd_complete,
        "status": cmd_status,
        "workshop": cmd_workshop,
        "verify": cmd_verify,
    }
    commands[args.cmd](args)


if __name__ == "__main__":
    main()
