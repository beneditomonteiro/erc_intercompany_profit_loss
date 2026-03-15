# -*- coding: utf-8 -*-
# License OPL-1 (Odoo Proprietary License v1.0) - (c) 2026 ERC Implementors LTDA

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WizardGenerateElimination(models.TransientModel):
    """Batch wizard: select period and configs → generate elimination entries."""

    _name = "wizard.generate.elimination"
    _description = "Generate Intercompany P&L Eliminations"

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
        help="Leave empty to process all active configs involving the selected company.",
    )

    @api.onchange("company_id")
    def _onchange_company_id(self):
        self.config_ids = False

    def action_generate(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("Date From must be before or equal to Date To."))
        domain = [
            ("state", "in", ("draft", "pending")),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]
        # Filter by company (seller or buyer)
        company_domain = [
            "|",
            ("seller_company_id", "=", self.company_id.id),
            ("buyer_company_id", "=", self.company_id.id),
        ]
        domain += company_domain
        if self.config_ids:
            domain += [("config_id", "in", self.config_ids.ids)]
        logs = self.env["erc.intercompany.profit.log"].search(domain)
        if not logs:
            raise UserError(
                _(
                    "No draft/pending P&L logs found for the selected period and filters."
                )
            )
        generated_moves = self.env["account.move"]
        skipped = 0
        for log in logs:
            try:
                log._validate_before_generate()
                move = log._create_elimination_move()
                log.write(
                    {
                        "state": "pending",
                        "elimination_move_id": move.id,
                    }
                )
                generated_moves |= move
            except Exception as exc:
                _logger.warning(
                    "Could not generate elimination for log %s: %s", log.name, exc
                )
                skipped += 1
        if not generated_moves:
            raise UserError(
                _(
                    "No elimination entries were generated. "
                    "%(skipped)s log(s) were skipped (already posted or missing accounts).",
                    skipped=skipped,
                )
            )
        msg = _(
            "%(count)s elimination journal entry(ies) generated.",
            count=len(generated_moves),
        )
        if skipped:
            msg += " " + _("%(skipped)s log(s) skipped.", skipped=skipped)
        return {
            "type": "ir.actions.act_window",
            "name": _("Elimination Entries"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", generated_moves.ids)],
            "context": {"create": False},
        }
