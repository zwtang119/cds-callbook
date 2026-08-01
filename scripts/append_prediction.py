"""append_prediction.py — 公开仓 append-only 门（CLI）。

用法：python3 scripts/append_prediction.py --call-json '<json>' [--date YYYY-MM-DD] [--no-push]
流程：白名单校验 → append-only 写 predictions/<date>.jsonl → git commit "call: <id>" → git push
退出码（A.5）：0 正常；4 SCHEMA_REJECT；5 DUP_PREDICTION；7 GIT_PUSH_FAIL（本地 commit 保留，下次重试）
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_ledger import DupPrediction, LedgerReject, append_jsonl, validate_public_call  # noqa: E402

EXIT_SCHEMA = 4
EXIT_DUP = 5
EXIT_PUSH = 7


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def append_call(
    call: dict, repo_root: Path, date: str | None = None, push: bool = True
) -> int:
    """核心流程（可被测试直接调用）。返回退出码。"""
    repo_root = Path(repo_root)
    validate_public_call(call)  # LedgerReject
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target = repo_root / "public-ledger" / "predictions" / f"{date}.jsonl"
    append_jsonl(target, call, key="id")  # DupPrediction

    rel = target.relative_to(repo_root)
    r = _git(["add", str(rel)], repo_root)
    if r.returncode != 0:
        raise RuntimeError(f"git add 失败: {r.stderr}")
    r = _git(["commit", "-m", f"call: {call['id']}"], repo_root)
    if r.returncode != 0:
        raise RuntimeError(f"git commit 失败: {r.stderr}")

    if push:
        r = _git(["push"], repo_root)
        if r.returncode != 0:
            print(
                f"GIT_PUSH_FAIL: 本地 commit 已保留，下次运行前先推送: {r.stderr}",
                file=sys.stderr,
            )
            return EXIT_PUSH
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="append-only 写公开预测账本")
    ap.add_argument("--call-json", required=True)
    ap.add_argument("--date", default=None, help="覆盖日期（测试用），默认今日 UTC")
    ap.add_argument(
        "--no-push", action="store_true", help="只 commit 不 push（测试/离线用）"
    )
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    try:
        call = json.loads(args.call_json)
    except json.JSONDecodeError as e:
        print(f"SCHEMA_REJECT: call-json 非合法 JSON: {e}", file=sys.stderr)
        return EXIT_SCHEMA
    try:
        code = append_call(
            call, Path(args.repo_root), date=args.date, push=not args.no_push
        )
    except LedgerReject as e:
        print(f"SCHEMA_REJECT: {e}", file=sys.stderr)
        return EXIT_SCHEMA
    except DupPrediction as e:
        print(f"DUP_PREDICTION: {e}", file=sys.stderr)
        return EXIT_DUP
    if code == 0:
        print(f"appended + committed: call: {call['id']}")
    return code


if __name__ == "__main__":
    sys.exit(main())
