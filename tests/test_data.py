"""Testes da conversão numérica tolerante a locale (pt-BR do Google Sheets)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.data import _to_number  # noqa: E402


def test_virgula_decimal_pt_br():
    s = pd.Series(["94,7", "92,5", "88,5"])
    assert _to_number(s).tolist() == [94.7, 92.5, 88.5]


def test_ponto_decimal_us():
    s = pd.Series(["94.7", "90", "0"])
    assert _to_number(s).tolist() == [94.7, 90.0, 0.0]


def test_ponto_milhar_e_virgula():
    s = pd.Series(["1.097,8", "249,2"])
    assert _to_number(s).tolist() == [1097.8, 249.2]


def test_vazio_vira_zero():
    s = pd.Series(["", None, "abc"])
    assert _to_number(s).tolist() == [0.0, 0.0, 0.0]
