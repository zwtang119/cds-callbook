"""rebuild_accuracy.py — 根据公开 ledger 重算 accuracy.json。

输入：public-ledger/predictions/*.jsonl、public-ledger/resolutions/*.jsonl
输出：public-ledger/accuracy.json

命中率规则（A.2）：
- 只统计已有 resolution 的 prediction；未结算不计入
- total=0 时 rate=null
- 按 question 内容分类统计 by_category
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_ledger import load_jsonl  # noqa: E402

import re

# 与私有侧 categories.py 语义一致：词边界匹配、先命中者胜、无命中→other
_CATEGORIES = [
    ("politics", ("election", "president", "senate", "congress", "prime minister")),
    (
        "economy",
        ("fed", "inflation", "gdp", "interest rate", "recession", "unemployment"),
    ),
    ("tech", ("ai", "spacex", "apple", "google", "nvidia", "openai", "tesla", "chip")),
    ("sports", ("world cup", "nba", "super bowl", "nfl", "premier league", "olympics")),
]


def classify(question: str) -> str:
    """按问题内容归类（与私有侧 categories.py 语义一致，公开仓零依赖复刻）。"""
    q = question.lower()
    for cat, words in _CATEGORIES:
        if any(re.search(r"\b" + re.escape(w) + r"\b", q) for w in words):
            return cat
    return "other"


def _rate(correct: int, total: int) -> float | None:
    return correct / total if total > 0 else None


def rebuild(root: Path) -> dict:
    """核心计算：返回 accuracy dict（不写盘）。"""
    predictions: dict[str, dict] = {}
    for f in sorted((root / "predictions").glob("*.jsonl")):
        for rec in load_jsonl(f):
            predictions[rec["id"]] = rec

    resolutions: dict[str, dict] = {}
    for f in sorted((root / "resolutions").glob("*.jsonl")):
        for rec in load_jsonl(f):
            resolutions[rec["id"]] = rec

    total = correct = 0
    by_category: dict[str, dict[str, int]] = {}

    for rid, res in resolutions.items():
        pred = predictions.get(rid)
        if pred is None:
            continue
        cat = classify(pred["question"])
        cat_bucket = by_category.setdefault(cat, {"total": 0, "correct": 0})
        total += 1
        cat_bucket["total"] += 1
        if res["correct"]:
            correct += 1
            cat_bucket["correct"] += 1

    # 稳定输出：按类别名排序
    sorted_by_cat = {k: by_category[k] for k in sorted(by_category)}
    for bucket in sorted_by_cat.values():
        bucket["rate"] = _rate(bucket["correct"], bucket["total"])

    return {
        "total": total,
        "correct": correct,
        "rate": _rate(correct, total),
        "by_category": sorted_by_cat,
        "updated_ts_utc": datetime.now(timezone.utc).isoformat(),
    }


def write_accuracy(root: Path, accuracy: dict) -> Path:
    """原子写 accuracy.json（同目录 tmp + rename）。"""
    target = root / "accuracy.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(accuracy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return target


def main() -> int:
    ap = argparse.ArgumentParser(description="根据公开 ledger 重算 accuracy.json")
    ap.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent / "public-ledger"),
        help="public-ledger 目录路径",
    )
    args = ap.parse_args()
    root = Path(args.root)
    try:
        (root / "predictions").mkdir(parents=True, exist_ok=True)
        (root / "resolutions").mkdir(parents=True, exist_ok=True)
        acc = rebuild(root)
        write_accuracy(root, acc)
    except Exception as e:
        print(f"REBUILD_ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
