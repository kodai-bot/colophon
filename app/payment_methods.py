# SPDX-License-Identifier: AGPL-3.0-or-later
"""
payment_methods.py - the single source of truth for till payment methods.

Payment *method* (cash/card, this file) is distinct from "Payments mode"
payment *type* (room hire, membership, etc. - app/ui/payments.py,
config["payment_types"]). Do not conflate the two.

A new method here is a recorded bookkeeping label, same as "card" today -
Colophon records card sales but never processes them (see AGENTS.md
section 3). This is deliberately a plain Python list, not config-driven:
a new method needs new UI buttons/bindings regardless, so a config list
would just duplicate this file for no benefit.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentMethod:
    value: str  # stored verbatim in sales.payment_method / payments.payment_method
    label: str  # display label
    key: str  # single-char shortcut for bindings/buttons
    kicks_drawer: bool  # True only for cash


CASH = PaymentMethod(value="cash", label="Cash", key="c", kicks_drawer=True)
CARD = PaymentMethod(value="card", label="Card", key="k", kicks_drawer=False)

PAYMENT_METHODS: list[PaymentMethod] = [CASH, CARD]

_BY_VALUE = {m.value: m for m in PAYMENT_METHODS}


def get_method(value: str | None) -> PaymentMethod | None:
    """Look up a PaymentMethod by its stored value. Returns None if unknown."""
    return _BY_VALUE.get(value) if value else None
