"""Calculate automated product-level replenishment recommendations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from src.analysis.common import load_clean_datasets


OPEN_SHIPMENT_STATUSES = {"in_transit", "delayed"}


def _latest_inventory(inventory: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Aggregate the most recent warehouse inventory snapshot by product."""
    if inventory.empty:
        raise ValueError("Inventory data is empty")
    as_of_date = pd.Timestamp(inventory["snapshot_date"].max())
    latest = (
        inventory.loc[inventory["snapshot_date"] <= as_of_date]
        .sort_values("snapshot_date")
        .drop_duplicates(["product_id", "warehouse_id"], keep="last")
    )
    stock = latest.groupby("product_id", as_index=False).agg(
        quantity_on_hand=("quantity_on_hand", "sum"),
        quantity_reserved=("quantity_reserved", "sum"),
    )
    stock["available_stock"] = stock["quantity_on_hand"] - stock["quantity_reserved"]
    return stock, as_of_date


def _daily_demand_statistics(
    orders: pd.DataFrame,
    product_ids: pd.Series,
    as_of_date: pd.Timestamp,
    demand_window_days: int,
) -> pd.DataFrame:
    """Calculate zero-filled daily demand mean and sample deviation by product."""
    start_date = as_of_date - pd.Timedelta(days=demand_window_days - 1)
    eligible = orders.loc[
        (orders["status"] != "cancelled")
        & orders["order_date"].between(start_date, as_of_date)
    ]
    dates = pd.date_range(start_date, as_of_date, freq="D")
    panel = pd.MultiIndex.from_product(
        [sorted(product_ids.unique()), dates], names=["product_id", "date"]
    )
    daily = (
        eligible.groupby(["product_id", "order_date"])["quantity"]
        .sum()
        .rename_axis(["product_id", "date"])
        .reindex(panel, fill_value=0)
        .rename("demand")
        .reset_index()
    )
    return daily.groupby("product_id", as_index=False).agg(
        average_daily_demand=("demand", "mean"),
        daily_demand_std=("demand", "std"),
        demand_window_units=("demand", "sum"),
    )


def _incoming_shipments(
    shipments: pd.DataFrame, as_of_date: pd.Timestamp
) -> pd.DataFrame:
    """Aggregate undelivered inbound units and flag quantities past expected date."""
    open_shipments = shipments.loc[
        shipments["status"].isin(OPEN_SHIPMENT_STATUSES)
        & shipments["arrival_date"].isna()
    ].copy()
    if open_shipments.empty:
        return pd.DataFrame(
            columns=["product_id", "incoming_quantity", "overdue_incoming_quantity"]
        )
    open_shipments["overdue_quantity"] = open_shipments["quantity"].where(
        open_shipments["expected_date"] < as_of_date, 0
    )
    return open_shipments.groupby("product_id", as_index=False).agg(
        incoming_quantity=("quantity", "sum"),
        overdue_incoming_quantity=("overdue_quantity", "sum"),
    )


def calculate_replenishment_recommendations(
    frames: dict[str, pd.DataFrame],
    service_level: float = 0.95,
    demand_window_days: int = 90,
    review_period_days: int = 30,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Calculate safety stock, reorder points, and automated order actions."""
    if not 0.5 < service_level < 1:
        raise ValueError("service_level must be greater than 0.5 and less than 1")
    if demand_window_days <= 1 or review_period_days <= 0:
        raise ValueError("Demand window must exceed one day and review period must be positive")

    stock, as_of_date = _latest_inventory(frames["inventory"])
    products = frames["products"].merge(
        frames["suppliers"][
            ["supplier_id", "supplier_name", "lead_time_days", "reliability_score"]
        ],
        on="supplier_id",
        how="left",
        validate="many_to_one",
    )
    if products[["lead_time_days", "reliability_score"]].isna().any().any():
        raise ValueError("Every product requires supplier lead time and reliability data")
    demand = _daily_demand_statistics(
        frames["orders"], products["product_id"], as_of_date, demand_window_days
    )
    incoming = _incoming_shipments(frames["shipments"], as_of_date)
    recommendations = (
        products[
            [
                "product_id",
                "sku",
                "product_name",
                "category",
                "supplier_id",
                "supplier_name",
                "unit_cost",
                "lead_time_days",
                "reliability_score",
            ]
        ]
        .merge(stock, on="product_id", how="left", validate="one_to_one")
        .merge(demand, on="product_id", how="left", validate="one_to_one")
        .merge(incoming, on="product_id", how="left", validate="one_to_one")
    )
    zero_columns = [
        "quantity_on_hand",
        "quantity_reserved",
        "available_stock",
        "average_daily_demand",
        "daily_demand_std",
        "demand_window_units",
        "incoming_quantity",
        "overdue_incoming_quantity",
    ]
    recommendations[zero_columns] = recommendations[zero_columns].fillna(0)

    z_score = NormalDist().inv_cdf(service_level)
    recommendations["safety_stock"] = np.ceil(
        z_score
        * recommendations["daily_demand_std"]
        * np.sqrt(recommendations["lead_time_days"])
    ).astype("int64")
    recommendations["lead_time_demand"] = (
        recommendations["average_daily_demand"]
        * recommendations["lead_time_days"]
    )
    recommendations["reorder_point"] = np.ceil(
        recommendations["lead_time_demand"] + recommendations["safety_stock"]
    ).astype("int64")
    recommendations["inventory_position"] = (
        recommendations["available_stock"] + recommendations["incoming_quantity"]
    )
    recommendations["target_stock"] = np.ceil(
        recommendations["average_daily_demand"]
        * (recommendations["lead_time_days"] + review_period_days)
        + recommendations["safety_stock"]
    ).astype("int64")
    order_trigger = recommendations["inventory_position"] <= recommendations["reorder_point"]
    order_gap = (
        recommendations["target_stock"] - recommendations["inventory_position"]
    ).clip(lower=0)
    recommendations["recommended_reorder_quantity"] = np.where(
        order_trigger, np.ceil(order_gap), 0
    ).astype("int64")
    recommendations["recommended_order_value"] = (
        recommendations["recommended_reorder_quantity"]
        * recommendations["unit_cost"]
    ).round(2)

    recommendations["replenishment_action"] = "NO_ORDER"
    overdue_review = recommendations["overdue_incoming_quantity"] > 0
    recommendations.loc[
        overdue_review, "replenishment_action"
    ] = "REVIEW_OVERDUE_INCOMING"
    expedite = (
        (recommendations["available_stock"] <= recommendations["reorder_point"])
        & (recommendations["incoming_quantity"] > 0)
        & ~order_trigger
    )
    recommendations.loc[expedite, "replenishment_action"] = "EXPEDITE_INCOMING"
    recommendations.loc[
        order_trigger & (recommendations["recommended_reorder_quantity"] > 0),
        "replenishment_action",
    ] = "ORDER_NOW"
    recommendations.loc[
        (recommendations["available_stock"] <= 0)
        & (recommendations["incoming_quantity"] <= 0)
        & (recommendations["target_stock"] > 0),
        "replenishment_action",
    ] = "ORDER_NOW"

    recommendations["priority"] = "LOW"
    recommendations.loc[overdue_review | expedite, "priority"] = "MEDIUM"
    recommendations.loc[
        recommendations["replenishment_action"] == "ORDER_NOW", "priority"
    ] = "HIGH"
    recommendations.loc[
        (recommendations["replenishment_action"] == "ORDER_NOW")
        & (
            (recommendations["available_stock"] <= 0)
            | (
                recommendations["inventory_position"]
                < recommendations["lead_time_demand"]
            )
        ),
        "priority",
    ] = "CRITICAL"
    recommendations["recommended_order_date"] = pd.NaT
    needs_action = recommendations["replenishment_action"].isin(
        ["ORDER_NOW", "EXPEDITE_INCOMING", "REVIEW_OVERDUE_INCOMING"]
    )
    recommendations.loc[needs_action, "recommended_order_date"] = as_of_date
    recommendations["expected_replenishment_date"] = pd.NaT
    replenishment_action = recommendations["replenishment_action"].isin(
        ["ORDER_NOW", "EXPEDITE_INCOMING"]
    )
    recommendations.loc[replenishment_action, "expected_replenishment_date"] = (
        as_of_date
        + pd.to_timedelta(
            recommendations.loc[replenishment_action, "lead_time_days"], unit="D"
        )
    )

    priority_order = pd.CategoricalDtype(
        ["CRITICAL", "HIGH", "MEDIUM", "LOW"], ordered=True
    )
    recommendations["priority"] = recommendations["priority"].astype(priority_order)
    recommendations = recommendations.sort_values(
        ["priority", "recommended_reorder_quantity", "product_id"],
        ascending=[True, False, True],
    ).reset_index(drop=True)

    summary = {
        "as_of_date": as_of_date.strftime("%Y-%m-%d"),
        "service_level": service_level,
        "service_factor": round(z_score, 6),
        "demand_window_days": demand_window_days,
        "review_period_days": review_period_days,
        "product_count": int(len(recommendations)),
        "order_now_products": int(
            (recommendations["replenishment_action"] == "ORDER_NOW").sum()
        ),
        "expedite_products": int(
            (recommendations["replenishment_action"] == "EXPEDITE_INCOMING").sum()
        ),
        "overdue_review_products": int(
            (
                recommendations["replenishment_action"]
                == "REVIEW_OVERDUE_INCOMING"
            ).sum()
        ),
        "recommended_order_units": int(
            recommendations["recommended_reorder_quantity"].sum()
        ),
        "recommended_order_value": round(
            float(recommendations["recommended_order_value"].sum()), 2
        ),
        "incoming_units": int(recommendations["incoming_quantity"].sum()),
        "overdue_incoming_units": int(
            recommendations["overdue_incoming_quantity"].sum()
        ),
    }
    return recommendations, summary


def write_replenishment_outputs(
    recommendations: pd.DataFrame,
    summary: dict[str, Any],
    output_dir: Path | str,
    report_path: Path | str,
) -> None:
    """Write replenishment tables, assumptions, summary, and business report."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    recommendations.to_csv(
        output / "replenishment_recommendations.csv",
        index=False,
        date_format="%Y-%m-%d",
    )
    actions = recommendations.loc[
        recommendations["replenishment_action"] != "NO_ORDER"
    ]
    actions.to_csv(
        output / "replenishment_action_queue.csv",
        index=False,
        date_format="%Y-%m-%d",
    )
    (output / "replenishment_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    lines = [
        "# Day 13 Inventory Optimization",
        "",
        "## Method",
        "",
        f"Recommendations use the latest inventory snapshot as of {summary['as_of_date']}, a {summary['demand_window_days']}-day zero-filled daily demand history, supplier lead times, and a {summary['service_level']:.0%} target service level.",
        "",
        "Safety stock equals the service factor multiplied by daily demand deviation and the square root of lead time. Reorder point equals expected lead-time demand plus safety stock. Inventory position equals available stock plus undelivered incoming shipments. When inventory position is at or below the reorder point, the recommendation orders up to lead-time demand plus the review period and safety stock.",
        "",
        "## Replenishment summary",
        "",
        f"- Products evaluated: {summary['product_count']}.",
        f"- Order-now products: {summary['order_now_products']}.",
        f"- Products with incoming stock to expedite: {summary['expedite_products']}.",
        f"- Products with overdue incoming stock to review: {summary['overdue_review_products']}.",
        f"- Recommended order quantity: {summary['recommended_order_units']:,} units.",
        f"- Recommended order value: ${summary['recommended_order_value']:,.2f}.",
        f"- Open incoming quantity: {summary['incoming_units']:,} units, including {summary['overdue_incoming_units']:,} overdue units.",
        "",
        "## Automated action queue",
        "",
        "| Priority | Product | Available | Incoming | Safety stock | Reorder point | Inventory position | Recommended order | Action |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in actions.head(20).itertuples(index=False):
        lines.append(
            f"| {row.priority} | {row.product_name} ({row.product_id}) | {int(row.available_stock):,} | {int(row.incoming_quantity):,} | {int(row.safety_stock):,} | {int(row.reorder_point):,} | {int(row.inventory_position):,} | {int(row.recommended_reorder_quantity):,} | {row.replenishment_action} |"
        )
    if actions.empty:
        lines.append("| LOW | No products require replenishment action |  |  |  |  |  |  | NO_ORDER |")
    lines.extend(
        [
            "",
            "## Operational notes",
            "",
            "Review overdue inbound shipments before placing replacement orders. Recalculate after material demand, lead-time, reservation, or shipment-status changes. Synthetic development data should not be used for live purchasing decisions.",
            "",
        ]
    )
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")


def run_replenishment_optimization(
    data_dir: Path | str,
    output_dir: Path | str,
    report_path: Path | str,
    service_level: float = 0.95,
    demand_window_days: int = 90,
    review_period_days: int = 30,
) -> dict[str, Any]:
    """Run the complete inventory optimization workflow."""
    recommendations, summary = calculate_replenishment_recommendations(
        load_clean_datasets(data_dir),
        service_level,
        demand_window_days,
        review_period_days,
    )
    write_replenishment_outputs(recommendations, summary, output_dir, report_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/inventory_optimization")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("reports/day13_inventory_optimization.md")
    )
    parser.add_argument("--service-level", type=float, default=0.95)
    parser.add_argument("--demand-window-days", type=int, default=90)
    parser.add_argument("--review-period-days", type=int, default=30)
    args = parser.parse_args()
    print(
        json.dumps(
            run_replenishment_optimization(
                args.data_dir,
                args.output_dir,
                args.report,
                args.service_level,
                args.demand_window_days,
                args.review_period_days,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
