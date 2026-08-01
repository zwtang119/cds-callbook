## Evidence Report — T6 公开仓 accuracy rebuild + resolution validation (Tier 2)

- Spec approval: `docs/plans/cds-callbook-execution-plan-2026-08-01.md` T6 Step 1–2
- Source state: `cds-callbook` main @ `dd7b1b3`
- Toolchain: pytest==8.3.5 / ruff==0.11.8 / 零第三方运行时依赖
- Entry point: `bash tools/gauntlet.sh`

### Spec → Test 映射

| Spec | Test | 状态 |
|---|---|---|
| A.2 resolution 字段校验（id/actual/correct/resolved_ts_utc/resolution_source，additionalProperties:false） | `test_resolution_good_passes`, `test_resolution_violations_rejected[6 cases]`, `test_resolution_missing_required_rejected` | pass |
| 3 predictions + 2 resolutions → total=2/correct=1/rate=0.5 | `test_three_predictions_two_resolutions` | pass |
| 未结算 prediction 不计入 | `test_unresolved_not_counted` | pass |
| total=0 → rate=null | `test_zero_total_rate_null` | pass |
| by_category 按问题内容分组 | `test_three_predictions_two_resolutions` | pass |
| 同一 ledger 跑两次输出字节相同（updated_ts_utc 除外） | `test_rebuild_idempotent_except_timestamp` | pass |
| `--validate-all` 覆盖 resolutions/ | gauntlet 第 3 层 | pass |

### Gauntlet（final fresh run: 2026-08-02）

| Layer | Command | Result |
|---|---|---|
| Tests | `python3 -m pytest -q` | **43 passed, 0 failed** |
| Lint | `ruff check scripts/ tests/` | **0 errors** |
| Format | `ruff format --check scripts/ tests/` | **5 files already formatted** |
| Schema validate-all | `python3 scripts/lib_ledger.py --validate-all public-ledger/` | **0 invalid line(s)** |
| Manual mutation (T6 cross-repo) | `python3 tools/mutants_t6.py`（含 rebuild_accuracy 2 个 mutant） | **5/5 killed** |

### Skipped layers

- `mutmut`：未安装且 root venv 无 pip，按 G.5 降级为手动变异，由 `tools/mutants_t6.py` 覆盖。
- `hypothesis`：公开仓保持零第三方运行时依赖，属性测试用手写循环版 `test_rebuild_idempotent_except_timestamp` 替代。

### Honest notes

- 分类器复刻私有侧 `categories.py` 的词边界匹配，避免 "bitcoin" 中的子串 "it" 把无关问题误判为 tech。
- `accuracy.json` 使用同目录 `tmp + rename` 原子写；输出键按类别名排序以保证字节级稳定。
- 新增 `requirements-dev.txt` 与 venv-aware `tools/gauntlet.sh`，解决本机 ruff 未在全局 PATH 的问题。
