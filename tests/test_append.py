"""test_append.py — 公开仓 append-only 门行为测试（Tier 3）。

含 G.2 失败模型覆盖：同 id 改写、第 7 字段、敌意输入、commit message 审计格式。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from lib_ledger import (
    DupPrediction,
    LedgerReject,
    append_jsonl,
    load_jsonl,
    validate_public_call,
)  # noqa: E402
from append_prediction import append_call  # noqa: E402

GOOD = {
    "id": "mk_test_ok",
    "question": "Will this market resolve YES by test day?",
    "call": "YES",
    "commit_ts_utc": "2026-08-01T14:00:00Z",
    "status": "open",
}


@pytest.fixture
def repo(tmp_path):
    """临时 git 仓（含 predictions 目录），模拟 cds-callbook。"""
    (tmp_path / "public-ledger" / "predictions").mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, capture_output=True
    )
    return tmp_path


# ---------- validate_public_call（白名单手写校验） ----------


def test_good_passes():
    validate_public_call(GOOD)


@pytest.mark.parametrize(
    "bad", ["confidence", "odds", "ticker", "agent", "pnl", "source", "signal_summary"]
)
def test_seventh_field_rejected(bad):
    with pytest.raises(LedgerReject):
        validate_public_call({**GOOD, bad: "x"})


@pytest.mark.parametrize(
    "patch",
    [
        {"id": "KXBTC-26JAN"},
        {"call": "MAYBE"},
        {"status": "closed"},
        {"question": "short"},
        {"question": "x" * 301},
        {"commit_ts_utc": "not-a-date"},
        {"version": 0},
    ],
)
def test_domain_violations_rejected(patch):
    with pytest.raises(LedgerReject):
        validate_public_call({**GOOD, **patch})


def test_missing_required_rejected():
    with pytest.raises(LedgerReject):
        validate_public_call({"id": "mk_x"})


# ---------- append-only 门 ----------


def test_append_creates_line_and_commit(repo):
    code = append_call(GOOD, repo, date="2026-08-01", push=False)
    assert code == 0
    lines = load_jsonl(repo / "public-ledger" / "predictions" / "2026-08-01.jsonl")
    assert lines == [GOOD]
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert "call: mk_test_ok" in log  # 审计：commit message 必含 id


def test_same_id_rejected(repo):
    append_call(GOOD, repo, date="2026-08-01", push=False)
    with pytest.raises(DupPrediction):
        append_call(GOOD, repo, date="2026-08-01", push=False)


def test_same_id_different_question_rejected(repo):
    """失败模型：同 id 改写 question = 篡改，必须拒绝。"""
    append_call(GOOD, repo, date="2026-08-01", push=False)
    with pytest.raises(DupPrediction):
        append_call(
            {**GOOD, "question": "Will a DIFFERENT question resolve YES?"},
            repo,
            date="2026-08-01",
            push=False,
        )


def test_version2_with_new_id_allowed(repo):
    """修正 = 新 id 新行，不是改行。"""
    append_call(GOOD, repo, date="2026-08-01", push=False)
    v2 = {**GOOD, "id": "mk_test_ok_v2", "version": 2}
    code = append_call(v2, repo, date="2026-08-01", push=False)
    assert code == 0
    lines = load_jsonl(repo / "public-ledger" / "predictions" / "2026-08-01.jsonl")
    assert len(lines) == 2 and lines[1]["version"] == 2
    assert lines[0] == GOOD  # 原行纹丝不动


def test_rejection_leaves_file_untouched(repo):
    append_call(GOOD, repo, date="2026-08-01", push=False)
    before = (repo / "public-ledger" / "predictions" / "2026-08-01.jsonl").read_text()
    with pytest.raises(LedgerReject):
        append_call(
            {**GOOD, "id": "mk_evil", "confidence": 0.9},
            repo,
            date="2026-08-01",
            push=False,
        )
    after = (repo / "public-ledger" / "predictions" / "2026-08-01.jsonl").read_text()
    assert before == after


# ---------- 敌意输入（对抗性自查的测试化部分） ----------


@pytest.mark.parametrize(
    "attack",
    [
        {
            "question": 'x"}\n{"id":"mk_inject","question":"fake question!!","call":"NO","commit_ts_utc":"2026-01-01T00:00:00Z","status":"open"'
        },
        {"question": "line1\u2028line2 合法长度填充"},
        {"question": "emoji 🚀🚀🚀 question ok?"},
    ],
)
def test_hostile_inputs(repo, attack):
    q = attack["question"]
    q = q + "x" * max(0, 10 - len(q))  # 保证长度合法，专注攻击面
    call = {**GOOD, "question": q}
    code = append_call(call, repo, date="2026-08-01", push=False)
    assert code == 0  # 合法内容可写，但必须作为单行安全落盘
    lines = (
        (repo / "public-ledger" / "predictions" / "2026-08-01.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(lines) == 1  # \u2028/引号不构成新行/注入
    assert json.loads(lines[0])["id"] == "mk_test_ok"


# ---------- 往返属性（G.4，手写循环版：公开仓零依赖不引 hypothesis） ----------


def test_roundtrip_append_load(tmp_path):
    f = tmp_path / "r.jsonl"
    recs = [{**GOOD, "id": f"mk_rt_{i:03d}"} for i in range(20)]
    for r in recs:
        append_jsonl(f, r, key="id")
    assert load_jsonl(f) == recs
