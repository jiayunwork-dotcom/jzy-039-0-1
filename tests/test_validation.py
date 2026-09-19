"""Validation tests: illegal input is rejected before any solving."""

from __future__ import annotations

import math

import pytest

from app import errors
from app.services import evaluator
from app.services.registry import CaseRegistry


def test_subsonic_mach_rejected():
    with pytest.raises(errors.MachNotSupersonic):
        evaluator.evaluate(0.8, 1.4)


def test_mach_exactly_one_rejected():
    with pytest.raises(errors.MachNotSupersonic):
        evaluator.evaluate(1.0, 1.4)


def test_gamma_below_one_rejected():
    with pytest.raises(errors.GammaInvalid):
        evaluator.evaluate(2.0, 1.0)
    with pytest.raises(errors.GammaInvalid):
        evaluator.evaluate(2.0, 0.9)


def test_missing_mach_rejected():
    with pytest.raises(errors.MachMissing):
        evaluator.evaluate(None, 1.4)


def test_missing_gamma_rejected():
    with pytest.raises(errors.GammaInvalid):
        evaluator.evaluate(2.0, None)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_numbers_rejected(bad):
    with pytest.raises(errors.ServiceError):
        evaluator.evaluate(bad, 1.4)
    with pytest.raises(errors.ServiceError):
        evaluator.evaluate(2.0, bad)


def test_non_positive_dimensional_inputs_rejected():
    with pytest.raises(errors.DimensionalInputInvalid):
        evaluator.evaluate(2.0, 1.4, p1=0.0, t1=288.15)
    with pytest.raises(errors.DimensionalInputInvalid):
        evaluator.evaluate(2.0, 1.4, p1=-101_325.0, t1=288.15)
    with pytest.raises(errors.DimensionalInputInvalid):
        evaluator.evaluate(2.0, 1.4, p1=101_325.0, t1=0.0)
    with pytest.raises(errors.DimensionalInputInvalid):
        evaluator.evaluate(2.0, 1.4, p1=101_325.0, t1=-288.15)
    with pytest.raises(errors.DimensionalInputInvalid):
        evaluator.evaluate(2.0, 1.4, p1=1.0, t1=1.0, gas_constant=0.0)


def test_unknown_case_name_rejected():
    reg = CaseRegistry()
    with pytest.raises(errors.CaseNotFound):
        reg.get("never-registered")


def test_empty_and_duplicate_case_name_rejected():
    reg = CaseRegistry()
    with pytest.raises(errors.CaseNameInvalid):
        reg.register("  ", 2.0, 1.4)
    reg.register("dup", 2.0, 1.4)
    with pytest.raises(errors.CaseAlreadyExists):
        reg.register("dup", 3.0, 1.4)
