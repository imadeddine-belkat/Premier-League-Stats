"""Unattended daily update, run by Windows Task Scheduler: pull, scrape the
current season with a fresh cache, then commit and push pl_stats/ if changed.

Output goes to logs/pl_update.log (last run only).
"""
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG = REPO / "logs" / "pl_update.log"
# pythonw.exe has no console; stop child processes from opening their own.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ENV = {
    **os.environ,
    "PL_CLEAR_CACHE": "1",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUNBUFFERED": "1",
    # Fail instead of hanging on a login prompt nobody will see.
    "GIT_TERMINAL_PROMPT": "0",
    "GCM_INTERACTIVE": "never",
}


def run(log, *cmd: str, check: bool = True) -> int:
    log.write(f"\n$ {' '.join(cmd)}\n")
    log.flush()
    code = subprocess.run(
        cmd, cwd=REPO, env=ENV, stdout=log, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
    ).returncode
    if check and code != 0:
        raise SystemExit(f"command failed with exit code {code}: {' '.join(cmd)}")
    return code


def pull(log) -> None:
    if run(log, "git", "pull", "--rebase", "--autostash", "origin", "main", check=False):
        run(log, "git", "rebase", "--abort", check=False)
        raise SystemExit("git pull failed; resolve it by hand")


def update(log) -> None:
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=REPO, capture_output=True,
        text=True, creationflags=NO_WINDOW,
    ).stdout.strip()
    if branch != "main":
        raise SystemExit(f"on branch '{branch}', not main; skipping")

    pull(log)
    # python.exe rather than pythonw.exe, so the scraper's output reaches the log.
    python = str(Path(sys.executable).with_name("python.exe"))
    run(log, python, "pl_scraper/main.py")

    run(log, "git", "add", "pl_stats")
    if run(log, "git", "diff", "--cached", "--quiet", "--", "pl_stats", check=False):
        message = f"Auto-update PL data for {date.today():%Y-%m-%d}"
        run(log, "git", "commit", "-m", message, "--", "pl_stats")
    else:
        log.write("No PL changes.\n")

    # Always push, so a commit left over from a failed push still goes out.
    pull(log)
    run(log, "git", "push", "origin", "main")


def main() -> None:
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("w", encoding="utf-8") as log:
        try:
            update(log)
        except BaseException as e:
            log.write(f"\nFAILED: {e}\n")
            raise
        log.write("\nDONE\n")


if __name__ == "__main__":
    main()
