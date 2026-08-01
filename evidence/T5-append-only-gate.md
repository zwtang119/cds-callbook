## Evidence Report — T5 公开仓 append-only 门 (Tier 3)

- Spec approval: obtained from user（2026-08-01）
- Source state: 仓 `cds-callbook` main（SHA 见 git log）
- Toolchain: 公开仓零第三方运行时依赖（拍板）；dev: pytest==8.3.5 / ruff==0.11.8
- Entry point: `bash tools/gauntlet.sh`

### 失败模型 → 关卡映射（G.2）

| 失败模式 | 关卡 | 结果 |
|---|---|---|
| 已存在行被修改（同 id 改写 question） | test_same_id_different_question_rejected + T7 guard CI（待建） + 变异 invert-dup-check | pass / killed |
| JSONL 半行/注入（引号、U+2028） | test_hostile_inputs ×3（**抓到真漏洞**，见诚实记录） | pass |
| 第 7 字段（方法痕迹） | test_seventh_field_rejected ×7 + 变异 drop-whitelist-reject | pass / killed |
| commit message 审计断链 | test_append_creates_line_and_commit 断言 `call: <id>` | pass |
| 超长 question / 非法 call/status/id/时间 | test_domain_violations_rejected ×7 | pass |
| push 失败 | append_call 返回 7 + 本地 commit 保留提示（e2e 于 T4 演练） | T4 验证 |

### Spec → Test mapping

25 tests 全 pass（2026-08-01 final fresh run）：白名单校验 ×9、append-only 门 ×5、敌意输入 ×3、往返 ×1、CLI 集成 ×5、版本修正 ×1、文件不可变 ×1。

### Gauntlet（final fresh run：2026-08-01，`bash tools/gauntlet.sh`）

| Layer | Command | Result |
|---|---|---|
| Tests | `python3 -m pytest -q` | **25 passed, 0 failed** |
| Lint | `ruff check scripts/ tests/` | **0 errors** |
| Format | `ruff format --check` | **3 files already formatted** |
| Schema validate-all | `python3 scripts/lib_ledger.py --validate-all public-ledger/` | **0 invalid line(s)** |
| Mutation（证明性手动 ×3） | 临时变异脚本（drop-whitelist / invert-dup / drop-u2028-escape） | **3/3 killed**，恢复后复绿 |
| Supply chain | 运行时零依赖（stdlib only） | 无新增包；dev 仅 pytest/ruff（pin） |

### Skipped layers

- hypothesis：公开仓零第三方运行时依赖拍板 → 属性测试用手写循环版（test_roundtrip_append_load 20 记录往返）。置信度影响：生成例少于 hypothesis，被 25 个具象用例 + 3 个敌意输入对冲。
- mypy / mutmut（工具版）/ pip-audit：无 CI 环境前（T7）以手动层替代；mutmut 在私有侧已证超时，公开仓模块小（2 文件），3 个手动 mutant 覆盖关键分支。

### Honest notes

- **过程偏差（如实记录）**：lib_ledger.py 初版实现先于测试写出（违反 TDD 次序）。补救按 old-coder 规程：3 个证明性变异全部被杀（含专杀 u2028 转义的 mutant），测试有效性被证明而非宣称。
- **对抗性自查抓到真漏洞**：U+2028 经 `json.dumps(ensure_ascii=False)` 不转义，落盘后被 splitlines 当换行 → JSONL "一行变两行"。修复：`_dump_line` 显式转义 U+2028/U+2029（`json.loads` 还原原字符），并有回归测试驻守。这是 Tier 3 对抗性自查的直接产出。
- 编辑事故一次（Edit 误删 fsync 行），经测试与人工复读发现即修，最终文件逐行复核无误。
- git push 失败路径（退出码 7）在 T4 端到端演练中真实验证，本报告不提前宣称。
