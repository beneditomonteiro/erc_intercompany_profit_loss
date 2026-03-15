# -*- coding: utf-8 -*-
# License OPL-1 (Odoo Proprietary License v1.0) - (c) 2026 ERC Implementors LTDA

import logging
from datetime import timedelta

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

_MATCH_WINDOW_DAYS = 90


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        result = super()._action_done()
        self._plc_update_sold_quantities()
        return result

    def _plc_update_sold_quantities(self):
        """After outgoing delivery validation, update IC profit log qty_sold_external."""
        outgoing = self.filtered(
            lambda p: p.picking_type_code == "outgoing" and p.state == "done"
        )
        if not outgoing:
            return
        ProfitLine = self.env["erc.intercompany.profit.line"]
        for picking in outgoing:
            buyer_company = picking.company_id
            for move in picking.move_ids.filtered(lambda m: m.state == "done"):
                product = move.product_id
                if not product:
                    continue
                qty_done = move.quantity
                if not qty_done:
                    continue
                # Find matching profit log lines for this product, buyer company,
                # in pending/draft state, within the match window
                if picking.date_done:
                    window_date = picking.date_done.date() - timedelta(days=_MATCH_WINDOW_DAYS)
                else:
                    window_date = fields.Date.context_today(self)
                matching_lines = ProfitLine.search(
                    [
                        ("product_id", "=", product.id),
                        ("profit_log_id.buyer_company_id", "=", buyer_company.id),
                        ("profit_log_id.state", "in", ("draft", "pending")),
                        ("profit_log_id.invoice_date", ">=", window_date),
                        ("profit_type", "=", "goods_unsold"),
                    ],
                    order="profit_log_id.invoice_date asc",
                )
                remaining_qty = qty_done
                for line in matching_lines:
                    if remaining_qty <= 0:
                        break
                    available = max(0.0, line.qty_still_in_stock)
                    if available <= 0:
                        continue
                    qty_to_apply = min(remaining_qty, available)
                    new_qty_sold = line.qty_sold_external + qty_to_apply
                    # Cap at invoiced qty
                    new_qty_sold = min(new_qty_sold, line.qty_invoiced)
                    line.write({
                        "qty_sold_external": new_qty_sold,
                        "qty_auto_sold": line.qty_auto_sold + qty_to_apply,
                    })
                    line.picking_ids = [(4, picking.id)]
                    remaining_qty -= qty_to_apply
                    _logger.info(
                        "PLC stock sync: picking %s updated profit line %s qty_sold_external to %.4f",
                        picking.name,
                        line.id,
                        new_qty_sold,
                    )
