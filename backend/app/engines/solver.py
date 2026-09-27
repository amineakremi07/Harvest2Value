"""PuLP MILP optimization engine for Harvest2Value.

Solves: given farmer's harvest, storage capacity, and multiple buyers,
allocate every kilogram to maximize net profit while respecting
storage, transport, distance, and shelf-life constraints.
"""

from pulp import (
    LpProblem,
    LpMaximize,
    LpVariable,
    LpInteger,
    LpContinuous,
    lpSum,
    LpStatus,
    value,
    PULP_CBC_CMD,
)
from typing import Any, Dict, List


def solve_optimization(data: Dict[str, Any]) -> Dict[str, Any]:
    """Solve the harvest allocation MILP and return structured JSON output.

    Decision variables:
        x[buyer_id]  -- kg allocated to buyer (integer)
        s            -- kg stored (continuous)
        w            -- kg wasted (continuous)

    Objective: maximize net profit = revenue - transport - storage - waste penalty
    """
    producer = data["producer"]
    buyers = data["buyers"]
    if not buyers:
        raise ValueError(
            "solve_optimization() requires at least one buyer; the buyers "
            "list is empty (a What-If scenario may have removed the last "
            "remaining buyer)."
        )
    harvest = float(producer["harvest_kg"])
    storage_cap = float(producer["storage_capacity_kg"])
    shelf_life = int(producer["shelf_life_days"])
    storage_cost_per_kg = float(producer.get("storage_cost_per_kg_per_day", 0.05))

    # ---- Build the problem ----
    prob = LpProblem("Harvest2Value_Optimization", LpMaximize)

    # Decision variables
    x = {
        buyer["id"]: LpVariable(
            f"x_{buyer['id']}", lowBound=0, cat="Integer"
        )
        for buyer in buyers
    }
    s = LpVariable("storage", lowBound=0, cat="LpContinuous")
    w = LpVariable("waste", lowBound=0, cat="LpContinuous")

    # ---- Objective function ----
    profit_terms = []
    for buyer in buyers:
        transport_cost = (
            float(buyer["distance_km"])
            * float(buyer["transport_cost_per_kg_per_km"])
        )
        net_price = float(buyer["price_per_kg"]) - transport_cost
        profit_terms.append(x[buyer["id"]] * net_price)

    # Storage: assume stored goods can be sold later at average price
    avg_price = sum(float(b["price_per_kg"]) for b in buyers) / len(buyers)
    profit_terms.append(s * (avg_price - storage_cost_per_kg))

    # Waste penalty: losing 50% of average value on unsold/wasted goods
    waste_penalty = avg_price * 0.5
    profit_terms.append(-w * waste_penalty)

    prob += lpSum(profit_terms), "Net_Profit"

    # ---- Constraints ----
    # 1. Supply: everything must go somewhere
    prob += (
        lpSum([x[b["id"]] for b in buyers]) + s + w == harvest,
        "Supply_Constraint",
    )

    # 2. Storage capacity
    prob += s <= storage_cap, "Storage_Capacity"

    # 3. Buyer demand
    for buyer in buyers:
        prob += (
            x[buyer["id"]] <= float(buyer["max_demand_kg"]),
            f"Demand_{buyer['id']}",
        )

    # 4. Shelf-life: waste cannot exceed what's not sold or stored
    prob += (
        w <= harvest - lpSum([x[b["id"]] for b in buyers]) - s,
        "Shelf_Life",
    )

    # 5. Vehicle capacity
    total_vehicles = int(data["logistics"]["available_vehicles"])
    vehicle_cap = float(data["logistics"]["vehicle_capacity_kg"])
    prob += (
        lpSum([x[b["id"]] for b in buyers])
        <= total_vehicles * vehicle_cap,
        "Vehicle_Capacity",
    )

    # ---- Solve ----
    prob.solve(PULP_CBC_CMD(msg=0, timeLimit=30))

    status = LpStatus[prob.status]

    # ---- Extract results ----
    allocation: Dict[str, Dict[str, Any]] = {}
    total_revenue = 0.0
    total_transport = 0.0

    for buyer in buyers:
        allocated_kg = int(round(x[buyer["id"]].varValue or 0))
        transport = (
            float(buyer["distance_km"])
            * float(buyer["transport_cost_per_kg_per_km"])
            * allocated_kg
        )
        revenue = float(buyer["price_per_kg"]) * allocated_kg
        total_revenue += revenue
        total_transport += transport
        allocation[buyer["id"]] = {
            "buyer_name": buyer["name"],
            "allocated_kg": allocated_kg,
            "unit_price": float(buyer["price_per_kg"]),
            "revenue": round(revenue, 2),
            "transport_cost": round(transport, 2),
            "net_profit": round(revenue - transport, 2),
            "distance_km": float(buyer["distance_km"]),
        }

    storage_val = float(s.varValue or 0)
    waste_val = float(w.varValue or 0)
    net_profit = float(value(prob.objective) or 0)

    return {
        "status": status,
        "total_harvest_kg": harvest,
        "allocated_kg": sum(a["allocated_kg"] for a in allocation.values()),
        "stored_kg": round(storage_val, 2),
        "wasted_kg": round(waste_val, 2),
        "total_revenue": round(total_revenue, 2),
        "total_transport_cost": round(total_transport, 2),
        "net_profit": round(net_profit, 2),
        "allocation": allocation,
        "solver_time_seconds": round(
            getattr(prob, "solutionTime", 0) or 0, 3
        ),
        "metadata": {
            "solver": "PuLP_CBC",
            "problem_type": "MILP",
            "variables": len(x) + 2,
            "constraints": len(buyers) + 4,
        },
    }


def merge_constraints(
    original_data: Dict[str, Any],
    constraints: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply a list of constraint modifications returned by the NIM layer.

    Each constraint dict has:
        type: "modify_demand" | "modify_price" | "add_storage_limit"
             | "remove_buyer" | "modify_transport_cost" | "add_time_constraint"
        target: buyer_id or field name
        field: field to modify
        new_value: replacement value
    """
    import copy

    data = copy.deepcopy(original_data)

    for c in constraints:
        ctype = c.get("type")
        target = c.get("target")
        field = c.get("field")
        new_value = c.get("new_value")

        if ctype == "remove_buyer":
            data["buyers"] = [b for b in data["buyers"] if b["id"] != target]
            continue

        if ctype == "add_buyer":
            raise ValueError(
                "Unsupported constraint type 'add_buyer': adding a buyer is "
                "not implemented by merge_constraints(). extract_constraints() "
                "must never produce this type; refusing to apply it rather "
                "than appending an unvalidated value to the buyers list."
            )

        if ctype == "modify_demand" or ctype == "modify_price" or ctype == "modify_transport_cost":
            for buyer in data["buyers"]:
                if buyer["id"] == target:
                    buyer[field] = new_value
            continue

        if ctype == "add_storage_limit":
            data["producer"][target] = new_value
            continue

        if ctype == "add_time_constraint":
            raise ValueError(
                "Unsupported constraint type 'add_time_constraint': no time/"
                "shelf-life logic exists in solve_optimization(). Refusing to "
                "apply it rather than silently storing a value that has no "
                "effect on the optimization."
            )

    return data
