## Evidence Report — T7 CI + append-only guard (Tier 2)

- Spec approval: obtained from user（2026-08-01）
- Source state: 仓 `cds-callbook` main，merge commit `aa8baef`
- Toolchain: 公开仓零第三方运行时依赖；dev: pytest==8.3.5 / ruff==0.11.8 / hypothesis==6.131.0 / pytest-randomly==3.16.0
- Entry point: `bash tools/gauntlet.sh`

### 失败模型 → 关卡映射

| 失败模式 | 关卡 | 结果 |
|---|---|---|
| predictions/ 历史行被修改 | guard-append-only CI（红→绿演练） | pass |
| predictions/ 文件被删除/改名 | guard-append-only CI（MDR 检测） | pass |
| JSONL schema 违规进入仓库 | test.yml → `lib_ledger.py --validate-all public-ledger/` | pass |
| pytest 回归 | test.yml → `pytest tests/ -v` | pass |

### Spec → Test / CI 映射

| Spec | 验证方式 | 状态 |
|---|---|---|
| pytest 全绿 | `.github/workflows/test.yml` Step "Run tests" | pass (43 passed) |
| validate-all 全绿 | `.github/workflows/test.yml` Step "Validate all ledger jsonl" | pass (0 invalid) |
| predictions/ 只增不改 | `.github/workflows/guard-append-only.yml` | pass |
| 浅历史健壮 | guard base ref 回退逻辑（PR→origin/main，push→event.before→origin/main~1→origin/main→skip） | pass |

### Gauntlet（final fresh run：2026-08-02，`bash tools/gauntlet.sh`）

| Layer | Command | Result |
|---|---|---|
| Tests | `pytest -q` | **43 passed, 0 failed** |
| Lint | `ruff check scripts/ tests/` | **0 errors** |
| Format | `ruff format --check` | **5 files already formatted** |
| Schema validate-all | `python scripts/lib_ledger.py --validate-all public-ledger/` | **0 invalid line(s)** |

### 红→绿演练记录

- PR: https://github.com/zwtang119/cds-callbook/pull/1
- 合并 commit: `aa8baefee89074001b8bc87bbae86319380be7ac`
- 基线行 commit（main）: `87216a5323fa3cb46602a17282e0562d0d007bb2`
- 故意篡改 commit: `300df39d749a25ed6ea0e9f825b7ac3916eb8b6c`
  - 改动：`public-ledger/predictions/2026-08-02.jsonl` 的 `"call": "YES"` → `"NO"`
  - guard 结果：**fail**，run https://github.com/zwtang119/cds-callbook/actions/runs/30709535457
  - 日志输出：`M	public-ledger/predictions/2026-08-02.jsonl` + `predictions/ is append-only`
- revert commit: `8c15d92045cbdc81e841003b81c9069eef117ca5`
  - guard 结果：**pass**，run https://github.com/zwtang119/cds-callbook/actions/runs/30709565942
- test.yml 结果：**pass**，run https://github.com/zwtang119/cds-callbook/actions/runs/30709565951
- 合并后 main 状态：无残留篡改行，基线行保持 `"call": "YES"`

### cds4polymarket 侧变更

- 既有 CI 文件 `.github/workflows/ci.yml` 已存在，按任务要求把 `experiments/call-test/tests/` 纳入。
- 新增 `call-test` job：安装 `experiments/call-test/requirements-dev.txt` 后运行 `pytest experiments/call-test/tests/ -v`。
- Commit: `5db2287` on branch `feat/call-test-v0`。

### Skipped layers

- coverage / diff-cover / mutmut / pip-audit：T7 本身只交付 CI 骨架；gauntlet 以当前已固定层（tests + lint + format + validate-all）为 pass 标准，与 T1–T6 证据一致。

### Honest notes

- 为在 PR 中真实演练“修改历史行”，先在 main 上提交了一条 synthetic 基线预测行（`mk_t7_baseline`），作为 guard 的 M 检测目标。该行在合并后仍保留于 main，**未被篡改**。
- guard 对浅历史的回退逻辑在 PR 事件中测试通过（base = `origin/main`）；push 事件回退链尚未在真实新分支 push 上触发，逻辑通过本地 `git rev-parse` 验证。
- cds4polymarket 的 `call-test` CI job 尚未在 GitHub Actions 上实际运行（feat/call-test-v0 未合入 main），但依赖集与本地测试路径一致。
