## Evidence Report — T8 README + Pages (Tier 1)

- Spec approval: obtained from user（2026-08-01）
- Source state: 仓 `cds-callbook` main，commit `93c4d07`
- Toolchain: 公开仓零第三方运行时依赖；dev: pytest==8.3.5 / ruff==0.11.8
- Entry point: `bash tools/gauntlet.sh`

### 失败模型 → 关卡映射

| 失败模式 | 关卡 | 结果 |
|---|---|---|
| README 点名私有信号源 predictionarena.ai | `grep -ci predictionarena README.md` | pass（=0） |
| README 缺失模拟盘声明 | 人工逐条勾 + grep 关键词 | pass |
| README 出现金额/PnL 暗示 | 人工审查 + grep 金额相关词 | pass |
| Pages 未部署或 404 | `curl -s https://zwtang119.github.io/cds-callbook/` | pass（HTTP 200） |
| total=0 时不显示样本不足 | 页面关键字 grep + 本地渲染验证 | pass |

### Spec → Test / 验证映射

| Spec | 验证方式 | 状态 |
|---|---|---|
| README 含上游 §5 全文 | 人工核对 §5.2 prose、§5.1 结构、§5.3 边界 | pass |
| README 置顶 `[!IMPORTANT]` 模拟盘声明 | 行 3–6 含 `模拟账本` + `不涉及一分钱` | pass |
| README 不点名 predictionarena | `grep -ci predictionarena README.md` = 0 | pass |
| README 不点名 agent/模型 | `grep -iE 'claude\|gpt\|gemini\|grok\|glm\|model\|agent'` 无命中 | pass |
| README 无金额/PnL 字段暗示 | 人工审查；未出现 amount/pnl/收益/盈亏/下注额 | pass |
| Pages 使用 actions/deploy-pages@v4 | `.github/workflows/pages.yml` 第 50 行 | pass |
| 页面 fetch `public-ledger/accuracy.json` | `site/index.html` JS | pass |
| total<30 显示 N=<n> 与样本不足 | `site/index.html` 渲染逻辑 + curl 命中 `样本不足` | pass |
| 页面含 `命中率` 字样 | curl 命中 `命中率` 2 次 | pass |
| GitHub Pages 设为 workflow 构建 | `gh api POST /repos/zwtang119/cds-callbook/pages` | pass |

### Gauntlet（final fresh run：2026-08-02，`bash tools/gauntlet.sh`）

| Layer | Command | Result |
|---|---|---|
| Tests | `pytest -q` | **43 passed, 0 failed** |
| Lint | `ruff check scripts/ tests/` | **0 errors** |
| Format | `ruff format --check` | **5 files already formatted** |
| Schema validate-all | `python scripts/lib_ledger.py --validate-all public-ledger/` | **0 invalid line(s)** |
| README compliance | `grep -ci predictionarena README.md` | **0** |
| Pages live | `curl -s https://zwtang119.github.io/cds-callbook/` | **HTTP 200，含 `命中率` 与 `样本不足`** |

### 部署验证

- Pages enable API: `gh api --method POST /repos/zwtang119/cds-callbook/pages -f build_type=workflow`
- Pages settings response: `build_type: workflow`, `html_url: https://zwtang119.github.io/cds-callbook/`
- Deploy workflow run: https://github.com/zwtang119/cds-callbook/actions/runs/30710004397
- Deploy status: success（build 8s + deploy 10s）
- Live URL check:
  - `curl -s -w '%{http_code}' https://zwtang119.github.io/cds-callbook/` → **200**
  - `grep -c '命中率' /tmp/cds-callbook-page.html` → **2**
  - `grep -c '样本不足' /tmp/cds-callbook-page.html` → **1**

### Skipped layers

- coverage / diff-cover / mutmut / pip-audit：T8 为 Tier 1（文档 + 静态页），按 `docs/plans/cds-callbook-execution-plan-2026-08-01.md` §G.1 裁剪为全套件 + lint + 声明理由；不强制变异/覆盖率。

### Honest notes

- `gh api --method PATCH /repos/zwtang119/cds-callbook/pages` 与 `PUT` 均返回 404，因 Pages 站点尚未创建；改用 `POST` 成功启用并设置 `build_type=workflow`。
- `actions/upload-pages-artifact@v3` 内部使用 `actions/upload-artifact@v4`；GitHub 提示 Node.js 20 deprecation 但工作流仍成功完成，属托管 runner 的强制兼容行为，不影响部署。
- 当前 `public-ledger/predictions/` 仅含 `.gitkeep`，`accuracy.json` total=0；页面正确显示 `N=0，样本不足，不具统计意义`。

### Commit

- `feat: README + ledger pages`
- SHA: `93c4d07f8fbeffe0a356a73c68fb508295966a060b0db4`
- Files added: `README.md`, `.github/workflows/pages.yml`, `site/index.html`
