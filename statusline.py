#!/usr/bin/env python3
"""Claude Code status line. Reads session JSON on stdin, prints one line.
No external deps (stdlib only). Safe: never raises -> always prints something."""
import json, os, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")   # Windows: cp1250 can't render │ █
except Exception:
    pass

SEP = " │ "
BAR_W = 10
FULL, EMPTY = "█", "░"


def sh(args, cwd=None):
    try:
        out = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=0.25)
        return out.stdout.strip()
    except Exception:
        return ""


def context_limit(model_id, data):
    mid = (model_id or "").lower()
    if "[1m]" in mid or data.get("exceeds_200k_tokens"):
        return 1_000_000
    return 200_000


def tokens_used(transcript_path):
    if not transcript_path or not os.path.exists(transcript_path):
        return 0
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines):
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            u = (obj.get("message") or {}).get("usage") or obj.get("usage")
            if u:
                return (u.get("input_tokens", 0)
                        + u.get("cache_read_input_tokens", 0)
                        + u.get("cache_creation_input_tokens", 0))
    except Exception:
        pass
    return 0


def human(n):
    if n >= 1_000_000:
        v = n / 1_000_000
        return f"{v:.0f}M" if v == int(v) else f"{v:.1f}M"
    if n >= 1_000:
        return f"{round(n / 1_000)}k"
    return str(n)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("Claude Code")
        return

    model = (data.get("model") or {}).get("display_name", "Claude")
    model_id = (data.get("model") or {}).get("id", "")
    ws = data.get("workspace") or {}
    cwd = ws.get("current_dir") or os.getcwd()
    proj_dir = ws.get("project_dir") or cwd
    cost = data.get("cost") or {}

    limit = context_limit(model_id, data)
    used = tokens_used(data.get("transcript_path"))
    frac_free = max(0.0, 1 - (used / limit)) if limit else 1.0
    pct_free = round(100 * frac_free)
    filled = int(frac_free * BAR_W)
    bar = FULL * filled + EMPTY * (BAR_W - filled)

    branch = sh(["git", "branch", "--show-current"], cwd=cwd)
    dirty = "*" if branch and sh(["git", "status", "--porcelain"], cwd=cwd) else ""

    added = cost.get("total_lines_added", 0)
    removed = cost.get("total_lines_removed", 0)

    parts = [model, f"{bar} {pct_free}% free"]
    if branch:
        parts.append(f"⎇ {branch}{dirty}")
    parts.append(f"+{added} -{removed}")
    parts.append(f"{human(used)}/{human(limit)}")
    parts.append(os.path.basename(proj_dir.rstrip("/\\")))

    print(SEP.join(parts))


if __name__ == "__main__":
    main()

