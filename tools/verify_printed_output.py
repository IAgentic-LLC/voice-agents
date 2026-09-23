"""Re-run every offline report command the book prints, and diff.

Handles: multi-command blocks, backslash continuations, and the
book's disclosed line-wrapping (a wrapped line is an indented
continuation of the one above). Anything that places a call or needs
a key is skipped and counted.
"""
import glob
import io
import os
import re
import subprocess

REPO = r"C:\Users\HomePC\Desktop\Project\voice-agents"
CHAPTERS = (r"C:\Users\HomePC\Desktop\Project\voice-agents-book"
            r"\chapters")

SKIP = ("caller.py", "cascaded_agent.py", "realtime_agent.py",
        "tools_agent.py", "memory_agent.py", "rag_agent.py",
        "talker_agent.py", "echo_agent.py", "reconnect.py", "say.py",
        "web_server.py", "browser_caller.py", "alternate", "docker",
        "audio_lab.py", "transcribe_variants.py", "pauses.py",
        "splice.py", "--group", "uv sync", "uv add", "pytest",
        "dtmf.py make", "dtmf.py phone", "for ", "$Q", "$C", "$q",
        # A real dial appends to the run directory it's given, even
        # when the guards refuse it, so re-running one here would
        # keep corrupting the exact recorded run the chapter prints.
        "outbound.py dial", "launch.py apply", "provision.py apply",
        "buy_number.py", "credentials.py create", "credentials.py attach")


def unwrap(text: str) -> str:
    """Join a wrapped continuation line back onto its predecessor."""
    out = []
    for line in text.split("\n"):
        if (out and line.startswith("    ") and out[-1].strip()
                and not out[-1].startswith("   ")):
            out[-1] = out[-1].rstrip() + " " + line.strip()
        else:
            out.append(line)
    return "\n".join(out)


def norm(text: str) -> str:
    return "\n".join(l.rstrip() for l in text.strip().split("\n"))


ok = bad = skipped = 0
problems = []
for path in sorted(glob.glob(os.path.join(CHAPTERS, "*.qmd"))):
    lines = io.open(path, encoding="utf8").read().split("\n")
    i = 0
    while i < len(lines):
        if not lines[i].startswith("```bash"):
            i += 1
            continue
        cmd, i = [], i + 1
        while i < len(lines) and not lines[i].startswith("```"):
            cmd.append(lines[i])
            i += 1
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines) or lines[i] != "```":
            continue
        out, i = [], i + 1
        while i < len(lines) and not lines[i].startswith("```"):
            out.append(lines[i])
            i += 1
        printed = "\n".join(out)
        block = "\n".join(cmd).replace("\\\n", " ")
        if any(s in block for s in SKIP):
            skipped += 1
            continue
        cmds = [c for c in block.split("\n") if c.strip().startswith("uv run")]
        if not cmds:
            skipped += 1
            continue
        real = ""
        for one in cmds:
            r = subprocess.run(re.split(r"\s+", one.strip()),
                               capture_output=True, text=True, cwd=REPO)
            real += r.stdout
        name = os.path.basename(path)[:30]
        if norm(unwrap(printed)) == norm(real):
            ok += 1
        elif norm(printed) == norm(real):
            ok += 1
        else:
            bad += 1
            problems.append((name, cmds[0][:65],
                             norm(unwrap(printed)), norm(real)))

for name, c, p, r in problems:
    print(f"DIFF {name}: {c}")
    pl, rl = p.split("\n"), r.split("\n")
    shown = 0
    for a, b in zip(pl, rl):
        if a != b and shown < 2:
            print(f"   printed: {a!r}")
            print(f"   real   : {b!r}")
            shown += 1
    if len(pl) != len(rl):
        print(f"   lines printed={len(pl)} real={len(rl)}")

print(f"\nmatched {ok}, mismatched {bad}, skipped {skipped}")
