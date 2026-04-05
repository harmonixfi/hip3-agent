# When you log a deposit or withdrawal — what actually happens?

This note is for **humans** (operators, future you). For tables, formulas, and code paths, see [`cashflow.md`](./cashflow.md).

---

## The one-sentence version

**Moving money on or off the exchange** is what changes your **balance** in snapshots. **Logging a DEPOSIT or WITHDRAW** in the app is what stops the **APR number** from treating that balance move as “trading skill” (or a fake blow-up).

Those are two different things.

---

## Two pipes of data (keep them straight)

**Pipe A — “What does the exchange say I have?”**  
Scripts like `pull_positions_v3.py` read Hyperliquid and write **account snapshots**. Your **total equity** on the dashboard comes from here. It updates when the pull runs and sees a new balance.

**Pipe B — “Did I move cash in or out for accounting?”**  
When you call **`POST /api/cashflows/manual`** with a **DEPOSIT** or **WITHDRAW**, you add a row to **`pm_cashflows`**. That row does **not** move dollars in Pipe A. It only tells the **APR math** how much of the equity change was **capital in/out** (deposits positive, withdrawals **negative** in storage — same convention as the API).

So: **ledger row ≠ funds moving on-chain.** The row is the **label** for the APR formula.

---

## A tiny story with round numbers

Imagine yesterday the system thought you had **$50,000** across wallets. Today you bridge **$10,000** USDC in. After the next data pull, the venue shows **$60,000** total.

- **Your equity on screen** moves **$50k → $60k** because **the pull saw real money**, not because you typed into the API.
- If you **also** log a **$10,000 DEPOSIT** for that wallet in **`pm_cashflows`**, the portfolio logic can say: “Equity went up $10k, and we know $10k was a deposit → **the ‘organic’ piece of that move is about $0** for this window.” So **cashflow-adjusted APR** does not skyrocket.

If you **forget** to log the deposit but equity still jumped to $60k, the system only sees “+$10k on the books” and may treat that like **huge return** — **misleading APR** until you add the row or fix the ledger.

### Withdrawal (mirror story)

You had **$60,000** and withdraw **$10,000** to your bank. After the next pull, equity shows **$50,000**.

- If you log **`WITHDRAW`** with the signed amount the API expects (**negative** **$10,000** in **`pm_cashflows`**), **`net_deposits_24h`** includes **−10,000**. Raw change is **−10,000**, so **organic** change is about **$0** and APR does not look like a giant **loss** from trading.
- If you **forget** to log it, the same **−$10k** move can look like **terrible performance** in **cashflow-adjusted APR** until the ledger is fixed.

---

## With the log vs without (plain comparison)

**You logged the $10,000 DEPOSIT (and it falls in the last 24h window the code uses)**

- The system can subtract that **$10,000** from the **raw** equity change when it builds **cashflow-adjusted APR**.
- Intuition: “We’re not counting the bridge as alpha.”

**You did not log it**

- Raw equity change still shows **+$10,000** if the money really arrived.
- **Cashflow-adjusted APR** has nothing to subtract → can look **way too good**.

**Withdraw — you logged the $10,000 WITHDRAW**

- **`net_deposits_24h`** includes **−10,000** (withdrawals count negative).
- Organic change stays near **$0** when the equity drop matches the withdrawal.

**Withdraw — you did not log it**

- The **−$10,000** move can look like a **sharp negative** organic return.

---

## What these manual rows do *not* touch

None of these rely on **`DEPOSIT` / `WITHDRAW`** rows in **`pm_cashflows`** for their main math:

- **Per-position “realized funding APR”** (the windowed 1d/3d/7d/14d columns) — those use **funding** payments only.
- **Funding earned / fees** rollups — those sum **FUNDING** and **FEE** rows, not deposits.

**Vault-level strategy accounting** uses a **different** table (**`vault_cashflows`**). Manual **`pm_cashflows`** lines do **not** replace vault-level entries if you track the vault separately.

---

## Vault flows (different book)

If your goal is **multi-strategy vault APR** (lending / delta-neutral / depeg splits), you record capital in **`vault_cashflows`** via **`vault.py`** or **`POST /api/vault/cashflows`**. That path feeds **`tracking/vault/snapshot.py`**, not the same line as the portfolio **`apr_daily`** above.

Use the ledger that matches what you’re measuring.

---

## Verify your row landed (quick check)

After **`POST /api/cashflows/manual`**, you should get a **`cashflow_id`** back. You can confirm in SQLite (adjust DB path for your env):

```bash
source .arbit_env
sqlite3 "${HARMONIX_DB_PATH:-tracking/db/arbit_v3.db}" \
  "SELECT cashflow_id, cf_type, amount, datetime(ts/1000,'unixepoch'), meta_json
   FROM pm_cashflows
   WHERE cf_type IN ('DEPOSIT','WITHDRAW')
   ORDER BY cashflow_id DESC LIMIT 10;"
```

You want **`meta_json`** to include **`"source":"manual"`** for API/operator entries. **WITHDRAW** amounts are stored **negative**.

---

## Automated checks (unit tests)

Round-number scenarios live in **`tests/test_manual_deposit_portfolio_apr.py`**:

| Case | Idea |
|------|------|
| **Deposit logged** | Adjusted change ≈ **0**, APR ≈ **0** (50k→60k + $10k DEPOSIT). |
| **Deposit missing** | Adjusted = full **$10k**, APR spikes (**73** in toy numbers). |
| **Withdraw logged** | Adjusted ≈ **0**, APR ≈ **0** (60k→50k + **−$10k** WITHDRAW). |
| **Withdraw missing** | Adjusted = **−$10k**, APR shows a large **negative** (toy formula). |
| **Huge up or down, no row** | Circuit breaker **clears** APR (likely unlogged flow). |

Run: `source .arbit_env && .venv/bin/python -m pytest tests/test_manual_deposit_portfolio_apr.py -v`

---

## Where to read more

| Topic | Doc |
|--------|-----|
| Full cashflow model, APR formulas, variable glossary | [`docs/cashflow.md`](./cashflow.md) |
| Pipeline (pulls → snapshots) | [`docs/data-pipeline-and-metrics.md`](./data-pipeline-and-metrics.md) |
