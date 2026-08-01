"""lib_ledger.py — 公开账本共享库（零第三方运行时依赖，cds-callbook 侧）。

不变式：
- predictions/ append-only：同 id 拒绝（DupPrediction）；修正 = 新 id（如 *_v2）新行
- 白名单 6 键手写校验（与私有侧 A.1 schema 语义一致），第 7 个键即拒
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

ID_PATTERN = re.compile(r"^mk_[a-z0-9_]{3,40}$")
REQUIRED_KEYS = {"id", "question", "call", "commit_ts_utc", "status"}
WHITELIST_KEYS = REQUIRED_KEYS | {"version"}


class DupPrediction(Exception):
    """同 id 已存在于 predictions/（append-only 拒绝）。"""


class LedgerReject(Exception):
    """记录违反公开账本格式（白名单/取值域/时间格式）。"""


def validate_public_call(d: dict) -> None:
    """手写白名单校验（零依赖）。失败抛 LedgerReject。"""
    if not isinstance(d, dict):
        raise LedgerReject("记录必须是 JSON object")
    extra = set(d) - WHITELIST_KEYS
    if extra:
        raise LedgerReject(f"白名单外字段: {sorted(extra)}")
    missing = REQUIRED_KEYS - set(d)
    if missing:
        raise LedgerReject(f"缺必填字段: {sorted(missing)}")
    if not ID_PATTERN.match(str(d["id"])):
        raise LedgerReject(f"id 不匹配 {ID_PATTERN.pattern}: {d['id']!r}")
    q = d["question"]
    if not isinstance(q, str) or not (10 <= len(q) <= 300):
        raise LedgerReject("question 长度须在 10..300")
    if d["call"] not in ("YES", "NO"):
        raise LedgerReject(f"call 取值非法: {d['call']!r}")
    if d["status"] != "open":
        raise LedgerReject(f"status 必须为 'open': {d['status']!r}")
    try:
        datetime.fromisoformat(str(d["commit_ts_utc"]).replace("Z", "+00:00"))
    except ValueError as e:
        raise LedgerReject(f"commit_ts_utc 非 ISO 8601: {e}") from e
    if "version" in d and not (isinstance(d["version"], int) and d["version"] >= 1):
        raise LedgerReject("version 必须为 ≥1 的整数")


def load_jsonl(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise LedgerReject(f"{path.name}:{i} 非法 JSON 行: {e}") from e
    return out


def _dump_line(record: dict) -> str:
    """单行安全序列化：JSONL 物理行不得含 U+2028/U+2029（Python splitlines 等
    工具会把它当换行，造成'一行变两行'注入）。json.loads 会还原原字符。"""
    return (
        json.dumps(record, ensure_ascii=False)
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
        + "\n"
    )


def append_jsonl(path: str | Path, record: dict, key: str) -> None:
    """append-only 写入：key 字段值重复即 DupPrediction。单行写入 + fsync。"""
    path = Path(path)
    existing = load_jsonl(path)
    if any(r.get(key) == record.get(key) for r in existing):
        raise DupPrediction(f"{key}={record.get(key)!r} 已存在于 {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(_dump_line(record))
        f.flush()
        os.fsync(f.fileno())


def _validate_all(root: Path) -> int:
    """逐行校验 public-ledger/ 下所有 jsonl（CI 入口：任一不合格 exit 1）。"""
    bad = 0
    for f in sorted(Path(root).rglob("*.jsonl")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                if "predictions" in f.parts:
                    validate_public_call(rec)
            except (json.JSONDecodeError, LedgerReject) as e:
                print(f"INVALID {f}:{i}: {e}")
                bad += 1
    print(f"validate-all: {bad} invalid line(s) under {root}")
    return 1 if bad else 0


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 3 and sys.argv[1] == "--validate-all":
        sys.exit(_validate_all(Path(sys.argv[2])))
