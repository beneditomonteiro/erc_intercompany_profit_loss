# -*- coding: utf-8 -*-
# License OPL-1 (Odoo Proprietary License v1.0) - (c) 2026 ERC Implementors LTDA

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

_ICPE_CODE = "ICPE"
_ICPE_NAME = "Intercompany P&L Eliminations"


class ResCompany(models.Model):
    _inherit = "res.company"

    interco_plc_journal_id = fields.Many2one(
        "account.journal",
        string="P&L Intercompany Elimination Journal",
        domain="[('type', '=', 'general'), ('company_id', '=', active_id)]",
        help=(
            "Default general journal used for intercompany P&L elimination entries. "
            "Typically code 'ICPE'. Can be overridden per seller→buyer config."
        ),
    )
    interco_plc_auto_log_on_post = fields.Boolean(
        string="Auto-log P&L on IC Invoice Post",
        default=True,
        help=(
            "When enabled, posting an intercompany customer invoice automatically "
            "creates a P&L profit log with lines for margin tracking."
        ),
    )

    plc_pending_log_count = fields.Integer(
        string="Pending P&L Logs",
        compute="_compute_plc_dashboard",
    )
    plc_total_unrealized = fields.Float(
        string="Total Unrealized Profit",
        compute="_compute_plc_dashboard",
        digits=(16, 2),
    )
    plc_last_elimination_date = fields.Date(
        string="Last Elimination Date",
        compute="_compute_plc_dashboard",
    )

    def _compute_plc_dashboard(self):
        ProfitLog = self.env["erc.intercompany.profit.log"]
        AccountMove = self.env["account.move"]
        for company in self:
            logs = ProfitLog.search(
                [
                    ("state", "in", ("draft", "pending")),
                    "|",
                    ("seller_company_id", "=", company.id),
                    ("buyer_company_id", "=", company.id),
                ]
            )
            company.plc_pending_log_count = len(logs)
            company.plc_total_unrealized = sum(logs.mapped("total_unrealized_profit"))
            # Last posted elimination move date
            last_move = AccountMove.search(
                [
                    ("journal_id", "=", company.interco_plc_journal_id.id),
                    ("state", "=", "posted"),
                ],
                limit=1,
                order="date desc",
            )
            company.plc_last_elimination_date = last_move.date if last_move else False

    def action_view_pending_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pending P&L Profit Logs"),
            "res_model": "erc.intercompany.profit.log",
            "view_mode": "list,form",
            "domain": [
                ("state", "in", ("draft", "pending")),
                "|",
                ("seller_company_id", "=", self.id),
                ("buyer_company_id", "=", self.id),
            ],
            "context": {"create": False},
        }

    @api.model
    def _plc_ensure_icpe_journal(self):
        """Create ICPE journal for any company that doesn't have one yet.

        Called both from post_init_hook (fresh install) and from the XML
        data file with noupdate="0" (every upgrade).
        """
        for company in self.search([]):
            if company.interco_plc_journal_id:
                continue
            journal = self.env["account.journal"].search(
                [
                    ("code", "=", _ICPE_CODE),
                    ("type", "=", "general"),
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )
            if not journal:
                journal = self.env["account.journal"].create(
                    {
                        "name": _ICPE_NAME,
                        "code": _ICPE_CODE,
                        "type": "general",
                        "company_id": company.id,
                        "show_on_dashboard": False,
                    }
                )
                _logger.info(
                    "erc_intercompany_profit_loss: Created ICPE journal for company '%s'",
                    company.name,
                )
            company.interco_plc_journal_id = journal
            _logger.info(
                "erc_intercompany_profit_loss: Linked ICPE journal to company '%s'",
                company.name,
            )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    interco_plc_journal_id = fields.Many2one(
        related="company_id.interco_plc_journal_id",
        readonly=False,
        string="P&L Elimination Journal",
    )
    interco_plc_auto_log_on_post = fields.Boolean(
        related="company_id.interco_plc_auto_log_on_post",
        readonly=False,
        string="Auto-log P&L on IC Invoice Post",
    )
    plc_pending_log_count = fields.Integer(
        related="company_id.plc_pending_log_count",
        string="Pending P&L Logs",
    )
    plc_total_unrealized = fields.Float(
        related="company_id.plc_total_unrealized",
        string="Total Unrealized Profit",
        digits=(16, 2),
    )
    plc_last_elimination_date = fields.Date(
        related="company_id.plc_last_elimination_date",
        string="Last Elimination Date",
    )
