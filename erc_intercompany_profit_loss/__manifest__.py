# -*- coding: utf-8 -*-
# License OPL-1 (Odoo Proprietary License v1.0) - (c) 2026 ERC Implementors LTDA

{
    "name": "ERC Intercompany Profit/Loss Elimination",
    "summary": "Track and eliminate unrealized intercompany profit from consolidated statements",
    "description": """
Intercompany P&L Elimination
=============================
Companion module to erc_intercompany_je that adds:

* Profit margin tracking on intercompany invoice lines (seller side)
* Margin embedded in buyer's inventory / COGS tracking (buyer side)
* Elimination journal entry generation (draft → review → post)
* Three profit types: unsold inventory, sold to external, services/expenses

Requires erc_intercompany_je for intercompany partner detection and GL account defaults.

Phase 2 (v1.3):
* **Dashboard KPIs:** Pending count, total unrealized profit, last elimination date.
* **Chatter & Tracking:** mail.thread on profit logs with state tracking.
* **Auto-Logging on Post:** IC invoice post creates profit log automatically.
* **Stock Delivery Sync:** Sold quantities auto-update from buyer's deliveries (FIFO).
* **Inventory Tracking:** qty sold external, still in stock, auto-sold fields.
* **Batch Reverse Wizard:** Bulk-reverse eliminations by date range and config.
* **PDF Elimination Report:** Auto-attached to journal entries for audit.
* **Smart Button on Invoices:** Navigate to related profit logs.
* **Cascade Reversals:** Reverse source invoice auto-reverses profit logs.
    """,
    "version": "19.0.1.3.0",
    "category": "Accounting",
    "author": "ERC Implementors (Benedito Monteiro)",
    "website": "https://erc-implementors.com",
    "license": "OPL-1",
    "application": False,
    "auto_install": False,
    "installable": True,
    "price": 30.0,
    "currency": "USD",
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "depends": [
        "erc_intercompany_je",
        "account",
        "sale_purchase_stock",
        "stock",
        "mail",
    ],
    "post_init_hook": "post_init_hook",
    "data": [
        "security/ir.model.access.csv",
        "data/elimination_backend_params.xml",
        "views/erc_intercompany_plc_views.xml",
        "views/erc_intercompany_profit_log_views.xml",
        "views/res_company_views.xml",
        "views/wizard_reverse_elimination_views.xml",
        "views/menu.xml",
        "report/erc_intercompany_profit_log_report.xml",
        "report/erc_intercompany_profit_log_template.xml",
    ],
}
