# -*- coding: utf-8 -*-
# License OPL-1 (Odoo Proprietary License v1.0) - (c) 2026 ERC Implementors LTDA

import logging

_logger = logging.getLogger(__name__)

ICPE_CODE = "ICPE"
ICPE_NAME = "Intercompany P&L Eliminations"


def post_init_hook(env):
    """Create the ICPE elimination journal for every company that doesn't have one."""
    env["res.company"]._plc_ensure_icpe_journal()
