# -*- coding: utf-8 -*-
# License OPL-1 (Odoo Proprietary License v1.0) - (c) 2026 ERC Implementors LTDA

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    plc_log_ids = fields.One2many(
        "erc.intercompany.profit.log",
        "invoice_id",
        string="P&L Profit Logs",
        copy=False,
    )
    plc_log_count = fields.Integer(
        string="P&L Logs",
        compute="_compute_plc_log_count",
    )

    @api.depends("plc_log_ids")
    def _compute_plc_log_count(self):
        for move in self:
            move.plc_log_count = len(move.plc_log_ids)

    def action_view_plc_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("P&L Profit Logs"),
            "res_model": "erc.intercompany.profit.log",
            "view_mode": "list,form",
            "domain": [("invoice_id", "=", self.id)],
            "context": {"default_invoice_id": self.id},
        }

    def _post(self, soft=True):
        """Override: after posting, auto-create P&L profit logs for IC invoices."""
        posted = super()._post(soft=soft)
        for move in posted:
            if not move._is_intercompany_invoice_for_plc():
                continue
            if not move.company_id.interco_plc_auto_log_on_post:
                continue
            try:
                log = move._create_plc_profit_log()
                if log:
                    move.message_post(
                        body=_(
                            "P&L Profit Log <b>%s</b> created automatically.",
                            log.name,
                        )
                    )
            except Exception:
                _logger.exception(
                    "Failed to create P&L profit log for move %s", move.name
                )
        return posted

    def _reverse_moves(self, default_values_list=None, cancel=False):
        result = super()._reverse_moves(
            default_values_list=default_values_list, cancel=cancel
        )
        for move in self:
            for log in move.plc_log_ids.filtered(
                lambda l: l.state in ("draft", "pending", "posted")
            ):
                try:
                    log.action_reverse_log()
                except Exception:
                    _logger.exception(
                        "Failed to reverse P&L profit log %s for move %s",
                        log.name,
                        move.name,
                    )
        return result

    def _is_intercompany_invoice_for_plc(self):
        """Return True if this is a posted customer invoice to an IC partner."""
        self.ensure_one()
        return (
            self.move_type == "out_invoice"
            and self.state == "posted"
            and self.partner_id
            and self.partner_id.is_intercompany
        )

    def _get_plc_config(self):
        """Find P&L elimination config for this invoice's seller→buyer pair.

        The seller is the current company; the buyer is determined by looking for
        a company whose intercompany partner matches self.partner_id.
        """
        self.ensure_one()
        seller = self.company_id
        # Find buyer company — the one that has this partner linked
        buyer = self.env["res.company"].search(
            [("partner_id", "=", self.partner_id.id)], limit=1
        )
        if not buyer:
            return self.env["erc.intercompany.plc"]
        config = self.env["erc.intercompany.plc"].search(
            [
                ("seller_company_id", "=", seller.id),
                ("buyer_company_id", "=", buyer.id),
                ("active", "=", True),
            ],
            limit=1,
        )
        return config

    def _create_plc_profit_log(self):
        """Create erc.intercompany.profit.log + lines for this invoice."""
        self.ensure_one()
        # Skip if a log already exists
        if self.plc_log_ids:
            return
        config = self._get_plc_config()
        if not config:
            _logger.info(
                "No P&L elimination config found for invoice %s (company=%s, partner=%s). "
                "Skipping auto-log.",
                self.name,
                self.company_id.name,
                self.partner_id.name,
            )
            return
        product_lines = self.invoice_line_ids.filtered(
            lambda l: not l.display_type and l.product_id
        )
        if not product_lines:
            return
        log = self.env["erc.intercompany.profit.log"].create(
            {
                "invoice_id": self.id,
                "config_id": config.id,
                "state": "draft",
            }
        )
        for inv_line in product_lines:
            product = inv_line.product_id
            cost = product.standard_price
            # Determine profit type based on product type
            if product.type == "service":
                ptype = "service"
            else:
                ptype = "goods_unsold"
            self.env["erc.intercompany.profit.line"].create(
                {
                    "profit_log_id": log.id,
                    "product_id": product.id,
                    "invoice_line_id": inv_line.id,
                    "description": inv_line.name or product.name,
                    "qty_invoiced": inv_line.quantity,
                    "seller_unit_price": inv_line.price_unit,
                    "seller_cost_price": cost,
                    "profit_type": ptype,
                    "qty_sold_external": 0.0,
                }
            )
        return log
