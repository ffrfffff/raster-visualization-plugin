#!/usr/bin/env python3
"""Block Claude from stopping after project changes without changelog/push reminder."""
import subprocess
import sys

TRACKED_PROJECT_FILES = (
    "main.py",
    "requirements.txt",
    "src/",
    ".claude/",
)


def run_git(args):
    return subprocess.run(
        ["git", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout.strip()


def main():
    status = run_git(["status", "--short"])
    if not status:
        return 0

    changed_paths = []
    for line in status.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ")[-1]
        changed_paths.append(path)

    has_project_change = any(
        path == prefix or path.startswith(prefix)
        for path in changed_paths
        for prefix in TRACKED_PROJECT_FILES
    )
    readme_changed = "README.md" in changed_paths

    if has_project_change and not readme_changed:
        print(
            "项目有代码/配置改动，但 README.md 版本日志还没同步更新。"
            "请先更新 README 版本日志，总结本次改动，然后按用户要求提交并 git push。",
            file=sys.stderr,
        )
        return 2

    unpushed = run_git(["log", "@{u}..HEAD", "--oneline"])
    if unpushed:
        print(
            "当前分支有未推送提交。请先 git push，并在最终回复中总结改动。",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
