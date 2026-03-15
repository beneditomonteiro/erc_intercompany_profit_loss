# -*- coding: utf-8 -*-
# License OPL-1 (Odoo Proprietary License v1.0) - (c) 2026 ERC Implementors LTDA

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ErcIntercompanyPlc(models.Model):
    """P&L Elimination configuration per seller → buyer company pair."""

    _name = "erc.intercompany.plc"
    _description = "Intercompany P&L Elimination Config"
    _rec_name = "display_name"

    seller_company_id = fields.Many2one(
        "res.company",
        string="Seller Company",
        required=True,
        ondelete="restrict",
    )
    buyer_company_id = fields.Many2one(
        "res.company",
        string="Buyer Company",
        required=True,
        ondelete="restrict",
    )
    active = fields.Boolean(default=True)

    # Buyer-side GL accounts
    buyer_ap_account_id = fields.Many2one(
        "account.account",
        string="Buyer — AP Intercompany",
        domain="[('account_type', '=', 'liability_payable')]",
        help="Dr: AP Intercompany (unsold/service elimination)",
    )
    buyer_inventory_account_id = fields.Many2one(
        "account.account",
        string="Buyer — Inventory Account",
        domain="[('account_type', 'in', ('asset_current', 'asset_non_current'))]",
        help="Cr: Inventory (unsold goods elimination)",
    )
    buyer_sales_account_id = fields.Many2one(
        "account.account",
        string="Buyer — Product Sales Account",
        domain="[('account_type', 'in', ('income', 'income_other'))]",
        help="Dr: Product Sales (sold-to-external elimination)",
    )
    buyer_cogs_account_id = fields.Many2one(
        "account.account",
        string="Buyer — COGS Account",
        domain="[('account_type', 'in', ('expense', 'expense_other', 'expense_direct_cost'))]",
        help="Cr: COGS (sold-to-external elimination)",
    )
    buyer_expense_account_id = fields.Many2one(
        "account.account",
        string="Buyer — Expense Account",
        domain="[('account_type', 'in', ('expense', 'expense_other', 'expense_direct_cost'))]",
        help="Cr: Expense (service/expense elimination)",
    )

    # Seller-side GL accounts
    seller_ar_account_id = fields.Many2one(
        "account.account",
        string="Seller — AR Intercompany",
        domain="[('account_type', '=', 'asset_receivable')]",
        help="Cr: AR Intercompany (service elimination)",
    )
    seller_service_revenue_account_id = fields.Many2one(
        "account.account",
        string="Seller — Services Revenue Account",
        domain="[('account_type', 'in', ('income', 'income_other'))]",
        help="Dr: Services Rendered (service elimination)",
    )

    @api.depends("seller_company_id", "buyer_company_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.seller_company_id and rec.buyer_company_id:
                rec.display_name = (
                    f"{rec.seller_company_id.name} → {rec.buyer_company_id.name}"
                )
            else:
                rec.display_name = _("New Config")

    _unique_seller_buyer = models.Constraint(
        "UNIQUE(seller_company_id, buyer_company_id)",
        "A P&L elimination config already exists for this seller → buyer pair.",
    )

    @api.constrains("seller_company_id", "buyer_company_id")
    def _check_different_companies(self):
        for rec in self:
            if rec.seller_company_id == rec.buyer_company_id:
                raise ValidationError(
                    _("Seller and Buyer companies must be different.")
                )

    def action_auto_populate(self):
        """Copy default GL accounts from erc_intercompany_je company fields."""
        for rec in self:
            seller = rec.seller_company_id
            buyer = rec.buyer_company_id
            vals = {}
            # Buyer AP default
            if not rec.buyer_ap_account_id and buyer.interco_payable_account_id:
                vals["buyer_ap_account_id"] = buyer.interco_payable_account_id.id
            # Buyer COGS default
            if not rec.buyer_cogs_account_id and buyer.interco_expense_other_account_id:
                vals["buyer_cogs_account_id"] = (
                    buyer.interco_expense_other_account_id.id
                )
            # Buyer expense default
            if (
                not rec.buyer_expense_account_id
                and buyer.interco_expense_service_account_id
            ):
                vals["buyer_expense_account_id"] = (
                    buyer.interco_expense_service_account_id.id
                )
            # Seller AR default
            if not rec.seller_ar_account_id and seller.interco_receivable_account_id:
                vals["seller_ar_account_id"] = seller.interco_receivable_account_id.id
            # Seller service revenue default
            if (
                not rec.seller_service_revenue_account_id
                and seller.interco_income_service_account_id
            ):
                vals["seller_service_revenue_account_id"] = (
                    seller.interco_income_service_account_id.id
                )
            if vals:
                rec.write(vals)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Auto-Populate"),
                "message": _("Accounts populated from intercompany defaults."),
                "type": "success",
                "sticky": False,
            },
        }
