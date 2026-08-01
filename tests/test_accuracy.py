"""test_accuracy.py — accuracy.json 重算 + resolution 校验测试（Tier 2）。

覆盖 G.4 属性：同一 ledger 跑两次，accuracy.json 字节相同（updated_ts_utc 除外）。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from lib_ledger import (  # noqa: E402
    ResolutionReject,
    append_jsonl,
    validate_resolution,
)
from rebuild_accuracy import classify, rebuild, write_accuracy  # noqa: E402

GOOD_RESOLUTION = {
    "id": "mk_test_ok",
    "actual": "YES",
    "correct": True,
    "resolved_ts_utc": "2026-08-01T16:00:00Z",
    "resolution_source": "official_manual",
}


@pytest.fixture
def ledger(tmp_path):
    """临时 public-ledger 目录（含 predictions/resolutions）。"""
    (tmp_path / "predictions").mkdir()
    (tmp_path / "resolutions").mkdir()
    return tmp_path


def _append_pred(root, rec):
    date = rec["commit_ts_utc"][:10]
    append_jsonl(root / "predictions" / f"{date}.jsonl", rec, key="id")


def _append_res(root, rec):
    date = rec["resolved_ts_utc"][:10]
    append_jsonl(root / "resolutions" / f"{date}.jsonl", rec, key="id")


# ---------- validate_resolution（A.2） ----------


def test_resolution_good_passes():
    validate_resolution(GOOD_RESOLUTION)


@pytest.mark.parametrize(
    "patch",
    [
        {"actual": "MAYBE"},
        {"correct": "yes"},
        {"resolution_source": "twitter"},
        {"resolved_ts_utc": "not-a-date"},
        {"id": "KXBTC-1"},
        {"extra": 1},
    ],
)
def test_resolution_violations_rejected(patch):
    with pytest.raises(ResolutionReject):
        validate_resolution({**GOOD_RESOLUTION, **patch})


def test_resolution_missing_required_rejected():
    with pytest.raises(ResolutionReject):
        validate_resolution({"id": "mk_x", "actual": "YES"})


# ---------- accuracy 计算 ----------


def test_three_predictions_two_resolutions(ledger):
    preds = [
        {
            "id": "mk_a",
            "question": "Will the president win re-election in 2026?",
            "call": "YES",
            "commit_ts_utc": "2026-08-01T10:00:00Z",
            "status": "open",
        },
        {
            "id": "mk_b",
            "question": "Will the Fed raise interest rates this month?",
            "call": "NO",
            "commit_ts_utc": "2026-08-01T10:00:00Z",
            "status": "open",
        },
        {
            "id": "mk_c",
            "question": "Will AI achieve a major breakthrough by year end?",
            "call": "YES",
            "commit_ts_utc": "2026-08-01T10:00:00Z",
            "status": "open",
        },
    ]
    for p in preds:
        _append_pred(ledger, p)

    _append_res(
        ledger, {**GOOD_RESOLUTION, "id": "mk_a", "actual": "YES", "correct": True}
    )
    _append_res(
        ledger, {**GOOD_RESOLUTION, "id": "mk_b", "actual": "YES", "correct": False}
    )
    # mk_c 未结算

    acc = rebuild(ledger)
    assert acc["total"] == 2
    assert acc["correct"] == 1
    assert acc["rate"] == 0.5
    assert acc["by_category"]["politics"] == {"total": 1, "correct": 1, "rate": 1.0}
    assert acc["by_category"]["economy"] == {"total": 1, "correct": 0, "rate": 0.0}
    assert "tech" not in acc["by_category"]


def test_unresolved_not_counted(ledger):
    _append_pred(
        ledger,
        {
            "id": "mk_unres",
            "question": "Will a sports team win the world cup?",
            "call": "YES",
            "commit_ts_utc": "2026-08-01T10:00:00Z",
            "status": "open",
        },
    )
    acc = rebuild(ledger)
    assert acc["total"] == 0
    assert acc["correct"] == 0
    assert acc["rate"] is None
    assert acc["by_category"] == {}


def test_zero_total_rate_null(ledger):
    acc = rebuild(ledger)
    assert acc["total"] == 0
    assert acc["rate"] is None


# ---------- 属性：幂等/稳定输出 ----------


def test_rebuild_idempotent_except_timestamp(ledger):
    _append_pred(
        ledger,
        {
            "id": "mk_idem",
            "question": "Will tech stocks outperform this quarter?",
            "call": "YES",
            "commit_ts_utc": "2026-08-01T10:00:00Z",
            "status": "open",
        },
    )
    _append_res(
        ledger,
        {
            "id": "mk_idem",
            "actual": "YES",
            "correct": True,
            "resolved_ts_utc": "2026-08-02T10:00:00Z",
            "resolution_source": "kalshi_api",
        },
    )
    acc1 = rebuild(ledger)
    acc2 = rebuild(ledger)
    # 除了 updated_ts_utc，其余内容应完全相同
    assert {k: v for k, v in acc1.items() if k != "updated_ts_utc"} == {
        k: v for k, v in acc2.items() if k != "updated_ts_utc"
    }

    write_accuracy(ledger, acc1)
    bytes1 = (ledger / "accuracy.json").read_bytes()
    write_accuracy(ledger, acc2)
    bytes2 = (ledger / "accuracy.json").read_bytes()

    # 抹掉 updated_ts_utc 所在行后，文件其余字节应相同
    def strip(b: bytes) -> bytes:
        return b"\n".join(
            line for line in b.splitlines() if b'"updated_ts_utc"' not in line
        )

    assert strip(bytes1) == strip(bytes2)


# ---------- 分类器 ----------


@pytest.mark.parametrize(
    "q, cat",
    [
        ("Who will win the presidential election?", "politics"),
        ("Will inflation exceed 3%?", "economy"),
        ("Will AI replace programmers?", "tech"),
        ("Will the team win the world cup?", "sports"),
        ("Will it rain tomorrow?", "other"),
    ],
)
def test_classify(q, cat):
    assert classify(q) == cat


# ---------- CLI ----------


def test_cli_rebuild_writes_accuracy_json(ledger):
    _append_pred(
        ledger,
        {
            "id": "mk_cli",
            "question": "Will the Fed cut rates?",
            "call": "NO",
            "commit_ts_utc": "2026-08-01T10:00:00Z",
            "status": "open",
        },
    )
    _append_res(
        ledger,
        {
            "id": "mk_cli",
            "actual": "NO",
            "correct": True,
            "resolved_ts_utc": "2026-08-02T10:00:00Z",
            "resolution_source": "official_manual",
        },
    )
    script = Path(__file__).resolve().parent.parent / "scripts" / "rebuild_accuracy.py"
    r = subprocess.run(
        [sys.executable, str(script), "--root", str(ledger)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    acc = json.loads((ledger / "accuracy.json").read_text(encoding="utf-8"))
    assert acc["total"] == 1 and acc["correct"] == 1 and acc["rate"] == 1.0
