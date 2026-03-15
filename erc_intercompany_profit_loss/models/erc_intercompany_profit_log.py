# -*- coding: utf-8 -*-
# License OPL-1 (Odoo Proprietary License v1.0) - (c) 2026 ERC Implementors LTDA

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

_logger = logging.getLogger(__name__)

PROFIT_TYPE_SELECTION = [
    ("goods_unsold", "Goods — Unsold Inventory"),
    ("goods_sold", "Goods — Sold to External"),
    ("service", "Service / Expense"),
]

LOG_STATE = [
    ("draft", "Draft"),
    ("pending", "Pending Elimination"),
    ("posted", "Posted"),
    ("reversed", "Reversed"),
]


class ErcIntercompanyProfitLog(models.Model):
    """One profit log per intercompany invoice."""

    _name = "erc.intercompany.profit.log"
    _description = "Intercompany P&L Profit Log"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "invoice_date desc, id desc"

    name = fields.Char(
        string="Reference",
        compute="_compute_name",
        store=True,
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Source Invoice",
        required=True,
        ondelete="cascade",
        index=True,
    )
    config_id = fields.Many2one(
        "erc.intercompany.plc",
        string="Elimination Config",
        required=True,
        ondelete="restrict",
    )
    seller_company_id = fields.Many2one(
        "res.company",
        string="Seller Company",
        related="invoice_id.company_id",
        store=True,
    )
    buyer_company_id = fields.Many2one(
        "res.company",
        string="Buyer Company",
        related="config_id.buyer_company_id",
        store=True,
    )
    invoice_date = fields.Date(
        related="invoice_id.invoice_date",
        store=True,
        string="Invoice Date",
    )
    state = fields.Selection(
        LOG_STATE,
        string="Status",
        default="draft",
        required=True,
        copy=False,
        tracking=True,
    )
    elimination_move_id = fields.Many2one(
        "account.move",
        string="Elimination Journal Entry",
        copy=False,
        readonly=True,
    )
    line_ids = fields.One2many(
        "erc.intercompany.profit.line",
        "profit_log_id",
        string="Profit Lines",
    )

    # Computed totals
    total_intercompany_amount = fields.Float(
        string="Total IC Amount",
        compute="_compute_totals",
        store=True,
        digits=(16, 2),
    )
    total_margin_amount = fields.Float(
        string="Total Margin",
        compute="_compute_totals",
        store=True,
        digits=(16, 2),
    )
    total_unrealized_profit = fields.Float(
        string="Total Unrealized Profit",
        compute="_compute_totals",
        store=True,
        digits=(16, 2),
    )

    @api.depends("invoice_id", "invoice_id.name")
    def _compute_name(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.name:
                rec.name = f"PLC/{rec.invoice_id.name}"
            elif rec.invoice_id:
                rec.name = f"PLC/{rec.invoice_id.id}"
            else:
                rec.name = _("New")

    @api.depends(
        "line_ids.seller_margin_amount",
        "line_ids.unrealized_profit",
        "line_ids.qty_invoiced",
        "line_ids.seller_unit_price",
    )
    def _compute_totals(self):
        for rec in self:
            rec.total_intercompany_amount = sum(
                l.qty_invoiced * l.seller_unit_price for l in rec.line_ids
            )
            rec.total_margin_amount = sum(
                l.seller_margin_amount for l in rec.line_ids
            )
            rec.total_unrealized_profit = sum(
                l.unrealized_profit for l in rec.line_ids
            )

    def _validate_before_generate(self):
        """Validate preconditions before generating an elimination entry."""
        self.ensure_one()
        errors = []
        # 1. Journal configured
        if not self.env.company.interco_plc_journal_id:
            errors.append(
                _(
                    "No P&L Elimination Journal configured for company %(company)s.",
                    company=self.env.company.name,
                )
            )
        # 2. At least one line with unrealized profit
        if not any(l.unrealized_profit > 0 for l in self.line_ids):
            errors.append(_("No profit lines have unrealized profit > 0."))
        # 3. No already-posted elimination
        if self.elimination_move_id and self.elimination_move_id.state == "posted":
            errors.append(_("An elimination entry is already posted for this log."))
        # 4. GL accounts not archived
        config = self.config_id
        account_fields = [
            "buyer_ap_account_id",
            "buyer_inventory_account_id",
            "buyer_sales_account_id",
            "buyer_cogs_account_id",
            "buyer_expense_account_id",
            "seller_ar_account_id",
            "seller_service_revenue_account_id",
        ]
        for fname in account_fields:
            acc = getattr(config, fname)
            if acc and not acc.active:
                errors.append(
                    _(
                        "GL account '%(code)s %(name)s' is archived on elimination config.",
                        code=acc.code,
                        name=acc.name,
                    )
                )
        if errors:
            raise UserError("\n".join(errors))

    def action_generate_elimination(self):
        """Generate a single draft elimination journal entry for this log."""
        self.ensure_one()
        if self.state not in ("draft", "pending"):
            raise UserError(
                _("Elimination can only be generated for logs in Draft or Pending state.")
            )
        self._validate_before_generate()
        move = self._create_elimination_move()
        self.write(
            {
                "state": "pending",
                "elimination_move_id": move.id,
            }
        )
        move_ref = move.name if move.name and move.name != "/" else f"(id={move.id})"
        self.message_post(
            body=_("Elimination entry %s generated.", move_ref)
        )
        move.message_post(
            body=_("Generated from P&L Profit Log %s.", self.name)
        )
        self._attach_pdf_to_move(move)
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
        }

    def action_reverse_log(self):
        """Reverse the elimination entry (if posted) and mark this log as reversed."""
        self.ensure_one()
        if self.state not in ("draft", "pending", "posted"):
            return
        if self.elimination_move_id and self.elimination_move_id.state == "posted":
            # Create a reverse journal entry
            reverse_wizard = (
                self.env["account.move.reversal"]
                .with_context(active_ids=[self.elimination_move_id.id], active_model="account.move")
                .create(
                    {
                        "reason": _(
                            "Reversal of intercompany P&L elimination for %s", self.name
                        ),
                        "journal_id": self.elimination_move_id.journal_id.id,
                        "date": fields.Date.context_today(self),
                    }
                )
            )
            reverse_wizard.reverse_moves()
        self.write({"state": "reversed"})
        self.message_post(body=_("Profit log reversed."))

    def _create_elimination_move(self):
        """Build and return a draft account.move with elimination lines."""
        self.ensure_one()
        config = self.config_id
        journal = self.env.company.interco_plc_journal_id
        if not journal:
            raise UserError(
                _(
                    "No P&L Elimination Journal configured for company %(company)s. "
                    "Please set one in Accounting > Settings > Intercompany P&L Elimination.",
                    company=self.env.company.name,
                )
            )
        line_vals = []
        for line in self.line_ids:
            line_vals.extend(line._get_elimination_move_lines())
        if not line_vals:
            raise UserError(
                _("No elimination lines to generate. Check profit lines have amounts.")
            )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "date": fields.Date.context_today(self),
                "ref": f"IC P&L Elimination — {self.name}",
                "line_ids": [Command.create(v) for v in line_vals],
            }
        )
        return move

    def _attach_pdf_to_move(self, move):
        """Render this log as PDF and attach to the elimination move."""
        try:
            report = self.env.ref(
                "erc_intercompany_profit_loss.action_report_plc_profit_log"
            )
            pdf_content, _ = report._render_qweb_pdf(self.ids)
            self.env["ir.attachment"].create(
                {
                    "name": f"{self.name}.pdf",
                    "type": "binary",
                    "datas": pdf_content,
                    "res_model": "account.move",
                    "res_id": move.id,
                    "mimetype": "application/pdf",
                }
            )
        except Exception:
            _logger.warning(
                "Could not attach PDF for profit log %s to move %s",
                self.name,
                move.id,
                exc_info=True,
            )


class ErcIntercompanyProfitLine(models.Model):
    """One profit tracking line per intercompany invoice line."""

    _name = "erc.intercompany.profit.line"
    _description = "Intercompany P&L Profit Line"
    _rec_name = "description"

    profit_log_id = fields.Many2one(
        "erc.intercompany.profit.log",
        string="Profit Log",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    invoice_line_id = fields.Many2one(
        "account.move.line",
        string="Invoice Line",
        readonly=True,
        ondelete="set null",
    )
    description = fields.Char(string="Description")

    # Seller-side (captured at invoice post time)
    qty_invoiced = fields.Float(string="Qty Invoiced", digits=(16, 4), readonly=True)
    seller_unit_price = fields.Float(
        string="Seller Unit Price",
        digits=(16, 4),
        readonly=True,
    )
    seller_cost_price = fields.Float(
        string="Seller Cost Price",
        digits=(16, 4),
        readonly=True,
        help="standard_price at the time the invoice was posted.",
    )
    seller_margin_amount = fields.Float(
        string="Seller Margin Amount",
        compute="_compute_seller_margin",
        store=True,
        digits=(16, 2),
    )
    seller_margin_pct = fields.Float(
        string="Seller Margin %",
        compute="_compute_seller_margin",
        store=True,
        digits=(16, 4),
    )

    # Buyer-side tracking (editable)
    qty_sold_external = fields.Float(
        string="Qty Sold Externally",
        digits=(16, 4),
        default=0.0,
        help="Quantity of this IC purchase that has been sold to external parties.",
    )
    qty_still_in_stock = fields.Float(
        string="Qty Still In Stock",
        compute="_compute_qty_in_stock",
        store=True,
        digits=(16, 4),
    )

    # Stock picking sync fields
    picking_ids = fields.Many2many(
        "stock.picking",
        "erc_profit_line_picking_rel",
        "line_id",
        "picking_id",
        string="Related Deliveries",
        help="Stock pickings that automatically updated qty_sold_external for this line.",
    )
    qty_auto_sold = fields.Float(
        string="Auto-Sold Qty",
        digits=(16, 4),
        default=0.0,
        help="Cumulative quantity auto-updated from stock delivery validation.",
    )

    # Profit type
    profit_type = fields.Selection(
        PROFIT_TYPE_SELECTION,
        string="Profit Type",
        default="goods_unsold",
        required=True,
    )

    # Unrealized profit
    unrealized_profit = fields.Float(
        string="Unrealized Profit",
        compute="_compute_unrealized_profit",
        store=True,
        digits=(16, 2),
        help=(
            "For goods_unsold: (qty_still_in_stock × unit_price) × margin% / (100 + margin%)\n"
            "For goods_sold: (qty_sold_external × cost_price) × margin% / 100\n"
            "For service: full margin amount"
        ),
    )

    @api.depends("qty_invoiced", "seller_unit_price", "seller_cost_price")
    def _compute_seller_margin(self):
        for line in self:
            qty = line.qty_invoiced
            unit = line.seller_unit_price
            cost = line.seller_cost_price
            margin_amt = qty * (unit - cost)
            line.seller_margin_amount = margin_amt
            revenue = qty * unit
            line.seller_margin_pct = (margin_amt / revenue * 100.0) if revenue else 0.0

    @api.depends("qty_invoiced", "qty_sold_external")
    def _compute_qty_in_stock(self):
        for line in self:
            line.qty_still_in_stock = max(
                0.0, line.qty_invoiced - line.qty_sold_external
            )

    @api.depends(
        "profit_type",
        "qty_still_in_stock",
        "qty_sold_external",
        "seller_unit_price",
        "seller_cost_price",
        "seller_margin_pct",
        "seller_margin_amount",
    )
    def _compute_unrealized_profit(self):
        for line in self:
            ptype = line.profit_type
            if ptype == "goods_unsold":
                # Markup fraction of the IC price still held in inventory
                unit = line.seller_unit_price
                stock_value = line.qty_still_in_stock * unit
                margin_pct = line.seller_margin_pct
                # unrealized = stock_value × margin% / (100 + margin%)
                line.unrealized_profit = (
                    stock_value * margin_pct / (100.0 + margin_pct)
                    if margin_pct
                    else 0.0
                )
            elif ptype == "goods_sold":
                # Margin embedded in the cost of sold goods
                cost = line.seller_cost_price
                sold_cost = line.qty_sold_external * cost
                margin_pct = line.seller_margin_pct
                line.unrealized_profit = (
                    sold_cost * margin_pct / 100.0 if margin_pct else 0.0
                )
            else:
                # Service: the full margin is to be eliminated
                line.unrealized_profit = line.seller_margin_amount

    def _get_elimination_move_lines(self):
        """Return a list of dict values for account.move.line creation."""
        self.ensure_one()
        config = self.profit_log_id.config_id
        amount = abs(self.unrealized_profit)
        if not amount:
            return []
        lines = []
        ptype = self.profit_type
        label = f"IC P&L Elim — {self.description or self.product_id.name or ''}"

        if ptype == "goods_unsold":
            # Dr AP Intercompany / Cr Inventory
            ap_acc = config.buyer_ap_account_id
            inv_acc = config.buyer_inventory_account_id
            if not ap_acc or not inv_acc:
                _logger.warning(
                    "Missing buyer AP or Inventory account on config %s — "
                    "skipping goods_unsold line for %s",
                    config.display_name,
                    self.description,
                )
                return []
            lines = [
                {"account_id": ap_acc.id, "name": label, "debit": amount, "credit": 0},
                {"account_id": inv_acc.id, "name": label, "debit": 0, "credit": amount},
            ]

        elif ptype == "goods_sold":
            # Dr Product Sales / Cr COGS
            sales_acc = config.buyer_sales_account_id
            cogs_acc = config.buyer_cogs_account_id
            if not sales_acc or not cogs_acc:
                _logger.warning(
                    "Missing buyer Sales or COGS account on config %s — "
                    "skipping goods_sold line for %s",
                    config.display_name,
                    self.description,
                )
                return []
            lines = [
                {
                    "account_id": sales_acc.id,
                    "name": label,
                    "debit": amount,
                    "credit": 0,
                },
                {
                    "account_id": cogs_acc.id,
                    "name": label,
                    "debit": 0,
                    "credit": amount,
                },
            ]

        elif ptype == "service":
            # Buyer side: Dr AP / Cr Expense
            ap_acc = config.buyer_ap_account_id
            exp_acc = config.buyer_expense_account_id
            # Seller side: Dr Services Rendered / Cr AR
            srv_acc = config.seller_service_revenue_account_id
            ar_acc = config.seller_ar_account_id
            if ap_acc and exp_acc:
                lines.extend(
                    [
                        {
                            "account_id": ap_acc.id,
                            "name": label,
                            "debit": amount,
                            "credit": 0,
                        },
                        {
                            "account_id": exp_acc.id,
                            "name": label,
                            "debit": 0,
                            "credit": amount,
                        },
                    ]
                )
            if srv_acc and ar_acc:
                lines.extend(
                    [
                        {
                            "account_id": srv_acc.id,
                            "name": label,
                            "debit": amount,
                            "credit": 0,
                        },
                        {
                            "account_id": ar_acc.id,
                            "name": label,
                            "debit": 0,
                            "credit": amount,
                        },
                    ]
                )
        return lines
