# ERC Intercompany Profit/Loss Elimination (v19)
**Track and Eliminate Unrealized Intercompany Profit from Consolidated Statements**

**Version:** 19.0.1.3.0 | **License:** OPL-1 (Odoo Proprietary License) | **Price:** $99 USD

---

## Overview
The **ERC Intercompany P&L Elimination** module is the companion to `erc_intercompany_je`, adding profit margin tracking and elimination journal entry generation for intercompany transactions. It ensures that unrealized profit embedded in inventory, COGS, and services is identified, quantified, and eliminated from consolidated financial statements.

## Key Features

### Profit Margin Tracking
Automatically calculates margin on intercompany invoice lines — on both the seller and buyer side:
- **Seller side:** Revenue minus cost on IC customer invoices
- **Buyer side:** Markup embedded in inventory valuation and COGS

### Three Profit Types

| Profit Type | Description | When to Eliminate |
|-------------|-------------|-------------------|
| **Goods — Unsold** | Margin on inventory still held by the buyer | Eliminate in full |
| **Goods — Sold** | Margin on goods the buyer has sold to external parties | Reverse prior elimination |
| **Services** | Full margin on intercompany service invoices | Eliminate in full |

### Elimination Configs (PLC)
Define seller → buyer company pairs with their elimination GL accounts:
- Unrealized Profit Account (balance sheet)
- Elimination Revenue Account
- Elimination Cost Account
- Dedicated ICPE journal per company (auto-created on install)

### 4-State Profit Log Workflow
Each IC invoice generates a profit log that progresses through:

```
Draft → Pending → Posted → Reversed
```

- **Draft:** Profit lines created, margin calculated
- **Pending:** Elimination journal entry generated (review before posting)
- **Posted:** Elimination entry posted to GL
- **Reversed:** Entry reversed (e.g., when goods are sold externally)

### Auto-Logging on Invoice Post
Post an IC customer invoice and a profit log is created automatically in draft with all profit lines pre-populated. Toggle on/off per company via `Settings > Accounting`.

### Stock Delivery Sync
When the buyer ships goods to external customers, sold quantities update automatically on matching profit lines. FIFO matching within a 90-day window. Full picking traceability.

### Dashboard KPIs
Three live KPIs in Settings:
- **Pending Logs:** Count of draft/pending profit logs
- **Total Unrealized:** Sum of all unrealized profit amounts
- **Last Elimination:** Date of most recently posted elimination entry

### Batch Reverse Wizard
Reverse elimination entries for an entire period from a single wizard. Filter by date range and seller/buyer config. Live preview before execution.

### PDF Elimination Report
Comprehensive QWeb PDF report with product-level detail: qty, seller price, cost, margin %, profit type, unrealized amount. Auto-attached to elimination journal entries.

### Smart Button on Invoices
IC invoices show a smart button with the count of related profit logs. One click navigates to the filtered log list.

### Cascade Reversals
Reverse a source IC invoice and all related profit logs are automatically reversed. No orphaned elimination entries.

### Chatter & Audit Trail
Profit logs inherit `mail.thread` with state tracking. Every generation, reversal, and status change is posted to chatter for full team visibility and audit compliance.

## Installation & Usage
1. Install `erc_intercompany_je` first (this module depends on it).
2. Install this module — the ICPE elimination journal is created automatically.
3. Go to **Accounting > Intercompany P&L > Elimination Configs** and create seller → buyer pairs.
4. Assign GL accounts for unrealized profit, elimination revenue, and elimination cost.
5. Post IC invoices — profit logs are created automatically (or manually via the wizard).
6. Review and post elimination entries from **Accounting > Intercompany P&L > Profit Logs**.

## Live Demo

Try the module on our demo instance — no installation required.

- **URL:** [erc-implementors.me/web/database/selector](https://erc-implementors.me/web/database/selector)
- **Database:** `erc_intercompany_us`
- **Login:** `ERC_ME`
- **Password:** `demo`

### Demo User Access Rights

The demo user has read-only access with limited write permissions for testing the P&L elimination workflow:

| Odoo Group | Access Level | What You Can Do |
|------------|-------------|-----------------|
| Internal User | Base access | Navigate all menus |
| Accounting Manager | Full accounting config | View journals, accounts, elimination configs |
| Sales User | Own documents | Create draft Sale Orders to IC partners |
| Purchase User | Standard | Create draft Purchase Orders from IC partners |

**What you CAN do:**
- View elimination configs (Accounting > Intercompany P&L > Elimination Configs)
- View profit logs and profit lines with margin calculations
- View the ICPE elimination journal and its entries
- View the smart button on IC invoices linking to profit logs
- View dashboard KPIs in Settings
- Create draft Sale Orders to test auto-logging

**What you CANNOT do:**
- Access Settings (no admin/system access)
- Install or uninstall modules
- Post or reverse elimination entries
- Delete or modify master data

## Dependencies
- `erc_intercompany_je` (required — intercompany partner detection and GL account defaults)
- `account`
- `sale_purchase_stock`, `stock`
- `mail`

## Corporate Governance
Developed and maintained by **ERC IMPLEMENTORS LTDA**, specialized in high-performance Odoo localizations and architectural governance.

*   **CNPJ:** 12.353.398/0001-29
*   **Location:** Rua Professora Gioconda Mussolini, 239. Jd Rizzo, Sao Paulo - SP, Brazil
*   **Owner:** Benedito Monteiro
*   **Website:** [www.erc-implementors.com](https://www.erc-implementors.com)

## Support & Inquiries
*   **WhatsApp:** [+55 11 92207 9570](https://wa.me/5511922079570)
*   **Email:** admin@erc-implementors.com

---
### License
Licensed under **OPL-1** (Odoo Proprietary License v1.0). (c) 2026 ERC Implementors LTDA. All Rights Reserved.
