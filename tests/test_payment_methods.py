# SPDX-License-Identifier: AGPL-3.0-or-later
from app.payment_methods import CARD, CASH, PAYMENT_METHODS, get_method


def test_get_method_cash():
    assert get_method("cash") is CASH


def test_get_method_card():
    assert get_method("card") is CARD


def test_cash_kicks_drawer():
    assert CASH.kicks_drawer is True


def test_card_does_not_kick_drawer():
    assert CARD.kicks_drawer is False


def test_get_method_unknown_returns_none():
    assert get_method("digital_euro") is None


def test_get_method_none_returns_none():
    assert get_method(None) is None


def test_payment_methods_today():
    assert len(PAYMENT_METHODS) == 2
    assert [m.value for m in PAYMENT_METHODS] == ["cash", "card"]
