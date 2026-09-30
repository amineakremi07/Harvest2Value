"""CBC runs on this machine (non-ASCII user path) and exposes LP duals / reduced costs."""

import pulp
import pytest


def test_cbc_is_available() -> None:
    assert pulp.PULP_CBC_CMD(msg=False).available()


def test_integer_program() -> None:
    prob = pulp.LpProblem("mip", pulp.LpMaximize)
    x = pulp.LpVariable("x", lowBound=0, cat="Integer")
    y = pulp.LpVariable("y", lowBound=0, cat="Integer")
    prob += 3 * x + 2 * y
    prob += x + y <= 4, "cap"
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    assert pulp.LpStatus[prob.status] == "Optimal"
    assert (x.varValue, y.varValue, pulp.value(prob.objective)) == (4.0, 0.0, 12.0)


def test_lp_duals_and_reduced_costs() -> None:
    # max 3a + 2b  s.t. a + b <= 4 (c1), a + 3b <= 6 (c2)  ->  a=4, b=0, obj=12
    prob = pulp.LpProblem("lp", pulp.LpMaximize)
    a = pulp.LpVariable("a", lowBound=0)
    b = pulp.LpVariable("b", lowBound=0)
    prob += 3 * a + 2 * b
    prob += a + b <= 4, "c1"
    prob += a + 3 * b <= 6, "c2"
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    assert pulp.value(prob.objective) == pytest.approx(12.0)
    assert prob.constraints["c1"].pi == pytest.approx(3.0)  # binding: +1 unit of c1 is worth 3
    assert prob.constraints["c2"].pi == pytest.approx(0.0)  # slack of 2, worthless at the margin
    assert prob.constraints["c2"].slack == pytest.approx(2.0)
    assert b.dj == pytest.approx(-1.0)  # forcing one unit of b costs 1
