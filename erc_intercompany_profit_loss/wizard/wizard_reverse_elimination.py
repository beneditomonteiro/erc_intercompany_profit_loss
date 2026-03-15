# -*- coding: utf-8 -*-
# License OPL-1 (Odoo Proprietary License v1.0) - (c) 2026 ERC Implementors LTDA

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WizardReverseElimination(models.TransientModel):
    """Batch wizard: select period → reverse elimination entries."""

    _name = "wizard.reverse.elimination"
    _description = "Reverse Intercompany P&L Eliminations"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    date_from = fields.Date(string="Date From", required=True)
    date_to = fields.Date(string="Date To", required=True)
    config_ids = fields.Many2many(
        "erc.intercompany.plc",
        string="Limit to Configs",
        help="Leave empty to process all configs involving the selected company.",
    )
    log_ids = fields.Many2many(
        "erc.intercompany.profit.log",
        string="Logs to Reverse",
        compute="_compute_log_ids",
    )

    @api.depends("company_id", "date_from", "date_to", "config_ids")
    def _compute_log_ids(self):
        for wizard in self:
            if not wizard.company_id or not wizard.date_from or not wizard.date_to:
                wizard.log_ids = False
                continue
            domain = [
                ("state", "in", ("draft", "pending", "posted")),
                ("invoice_date", ">=", wizard.date_from),
                ("invoice_date", "<=", wizard.date_to),
                "|",
                ("seller_company_id", "=", wizard.company_id.id),
                ("buyer_company_id", "=", wizard.company_id.id),
            ]
            if wizard.config_ids:
                domain += [("config_id", "in", wizard.config_ids.ids)]
            wizard.log_ids = self.env["erc.intercompany.profit.log"].search(domain)

    @api.onchange("company_id")
    def _onchange_company_id(self):
        self.config_ids = False

    def action_reverse(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("Date From must be before or equal to Date To."))
        domain = [
            ("state", "in", ("draft", "pending", "posted")),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
            "|",
            ("seller_company_id", "=", self.company_id.id),
            ("buyer_company_id", "=", self.company_id.id),
        ]
        if self.config_ids:
            domain += [("config_id", "in", self.config_ids.ids)]
        logs = self.env["erc.intercompany.profit.log"].search(domain)
        if not logs:
            raise UserError(
                _(
                    "No pending/posted P&L logs found for the selected period and filters."
                )
            )
        reversed_logs = self.env["erc.intercompany.profit.log"]
        skipped = 0
        for log in logs:
            try:
                log.action_reverse_log()
                reversed_logs |= log
            except Exception as exc:
                _logger.warning(
                    "Could not reverse log %s: %s", log.name, exc
                )
                skipped += 1
        if not reversed_logs:
            raise UserError(
                _(
                    "No logs were reversed. %(skipped)s log(s) skipped.",
                    skipped=skipped,
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Reversed Profit Logs"),
            "res_model": "erc.intercompany.profit.log",
            "view_mode": "list,form",
            "domain": [("id", "in", reversed_logs.ids)],
            "context": {"create": False},
        }
