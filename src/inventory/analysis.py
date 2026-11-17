"""Analyze stock availability, turnover, excess inventory, and stockout risk."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.analysis.common import load_clean_datasets


def calculate_inventory_metrics(
    frames: dict[str, pd.DataFrame],
    trailing_days: int = 90,
    excess_cover_days: int = 180,
    slow_turnover_threshold: float = 1.0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Calculate product-level inventory metrics and a summary."""
    if trailing_days <= 0 or excess_cover_days <= 0 or slow_turnover_threshold < 0:
        raise ValueError("Analysis thresholds must be positive")

    inventory = frames["inventory"]
    as_of_date = inventory["snapshot_date"].max()
    latest = (
        inventory.loc[inventory["snapshot_date"] <= as_of_date]
        .sort_values("snapshot_date")
        .drop_duplicates(["product_id", "warehouse_id"], keep="last")
        .assign(available_stock=lambda frame: frame["quantity_on_hand"] - frame["quantity_reserved"])
    )
    stock = latest.groupby("product_id", as_index=False).agg(
        quantity_on_hand=("quantity_on_hand", "sum"),
        quantity_reserved=("quantity_reserved", "sum"),
        available_stock=("available_stock", "sum"),
        reorder_point=("reorder_point", "sum"),
        safety_stock=("safety_stock", "sum"),
    )

    products = frames["products"].merge(
        frames["suppliers"][["supplier_id", "lead_time_days"]],
        on="supplier_id",
        how="left",
        validate="many_to_one",
    )
    sales = frames["sales"].loc[frames["sales"]["sale_date"] <= as_of_date].copy()
    observed_start = sales["sale_date"].min()
    observed_days = max(int((as_of_date - observed_start).days) + 1, 1)
    trailing_start = as_of_date - pd.Timedelta(days=trailing_days - 1)

    demand = sales.groupby("product_id", as_index=False).agg(
        observed_net_demand=("quantity", "sum"),
        last_sale_date=("sale_date", "max"),
    )
    trailing = (
        sales.loc[sales["sale_date"].between(trailing_start, as_of_date)]
        .groupby("product_id", as_index=False)
        .agg(trailing_net_demand=("quantity", "sum"))
    )

    result = (
        products[["product_id", "sku", "product_name", "category", "supplier_id", "unit_cost", "lead_time_days"]]
        .merge(stock, on="product_id", how="left", validate="one_to_one")
        .merge(demand, on="product_id", how="left", validate="one_to_one")
        .merge(trailing, on="product_id", how="left", validate="one_to_one")
    )
    numeric_zero = [
        "quantity_on_hand", "quantity_reserved", "available_stock", "reorder_point",
        "safety_stock", "observed_net_demand", "trailing_net_demand",
    ]
    result[numeric_zero] = result[numeric_zero].fillna(0)
    result["annualized_demand"] = result["observed_net_demand"].clip(lower=0) * 365.0 / observed_days
    result["average_daily_demand"] = result["annualized_demand"] / 365.0
    result["inventory_turnover_proxy"] = result["annualized_demand"].div(
        result["quantity_on_hand"].replace(0, pd.NA)
    )
    result["days_of_supply"] = result["available_stock"].div(
        result["average_daily_demand"].replace(0, pd.NA)
    )
    result["lead_time_demand"] = result["average_daily_demand"] * result["lead_time_days"]
    result["recommended_reorder_quantity"] = (
        result["reorder_point"] + result["safety_stock"] - result["available_stock"]
    ).clip(lower=0).round().astype("Int64")

    result["low_stock"] = result["available_stock"] <= result["reorder_point"]
    result["slow_moving"] = (
        (result["inventory_turnover_proxy"].fillna(0) < slow_turnover_threshold)
        | (result["trailing_net_demand"] <= 0)
    )
    result["excess_target_stock"] = pd.concat(
        [
            result["reorder_point"] + result["safety_stock"],
            result["average_daily_demand"] * excess_cover_days,
        ],
        axis=1,
    ).max(axis=1)
    result["excess_inventory"] = result["available_stock"] > result["excess_target_stock"]
    result["excess_units"] = (result["available_stock"] - result["excess_target_stock"]).clip(lower=0).round().astype("Int64")
    result["excess_inventory_value"] = result["excess_units"] * result["unit_cost"]

    result["stockout_risk"] = "LOW"
    medium = (
        (result["available_stock"] <= result["reorder_point"] + result["safety_stock"])
        | (result["days_of_supply"] <= result["lead_time_days"] * 2)
    )
    high = result["low_stock"] | (
        result["available_stock"] <= result["lead_time_demand"] + result["safety_stock"]
    )
    result.loc[medium.fillna(False), "stockout_risk"] = "MEDIUM"
    result.loc[high.fillna(False), "stockout_risk"] = "HIGH"
    result.loc[result["available_stock"] <= 0, "stockout_risk"] = "OUT_OF_STOCK"

    risk_order = pd.CategoricalDtype(["OUT_OF_STOCK", "HIGH", "MEDIUM", "LOW"], ordered=True)
    result["stockout_risk"] = result["stockout_risk"].astype(risk_order)
    result = result.sort_values(
        ["stockout_risk", "available_stock", "inventory_turnover_proxy"],
        ascending=[True, True, True],
        na_position="first",
    ).reset_index(drop=True)

    summary = {
        "as_of_date": as_of_date.strftime("%Y-%m-%d"),
        "observed_demand_days": observed_days,
        "total_on_hand": int(result["quantity_on_hand"].sum()),
        "total_reserved": int(result["quantity_reserved"].sum()),
        "total_available": int(result["available_stock"].sum()),
        "low_stock_products": int(result["low_stock"].sum()),
        "slow_moving_products": int(result["slow_moving"].sum()),
        "excess_inventory_products": int(result["excess_inventory"].sum()),
        "high_or_out_stockout_risk": int(result["stockout_risk"].isin(["HIGH", "OUT_OF_STOCK"]).sum()),
        "excess_inventory_value": round(float(result["excess_inventory_value"].sum()), 2),
        "trailing_days": trailing_days,
        "excess_cover_days": excess_cover_days,
        "slow_turnover_threshold": slow_turnover_threshold,
    }
    return result, summary


def write_inventory_outputs(analysis: pd.DataFrame, summary: dict[str, Any], report_path: Path | str) -> None:
    """Write the detailed analysis table and Markdown business report."""
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    table_dir = report.parent / "inventory_tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    analysis.to_csv(table_dir / "inventory_analysis.csv", index=False, date_format="%Y-%m-%d")

    attention = analysis.loc[
        analysis["low_stock"] | analysis["excess_inventory"] | analysis["slow_moving"]
    ].head(15)
    lines = [
        "# Day 7 Inventory Analysis",
        "",
        "## Scope and definitions",
        "",
        f"The analysis uses the latest warehouse snapshot as of {summary['as_of_date']}. Available stock equals on-hand less reserved units.",
        f"Turnover is an annualized unit-demand/current on-hand proxy over {summary['observed_demand_days']} observed days. Average inventory is unavailable, so this is not the standard cost-of-goods-sold/average-inventory ratio.",
        f"Slow-moving means turnover below {summary['slow_turnover_threshold']:.1f} or no net demand in the last {summary['trailing_days']} days. Excess inventory exceeds both reorder plus safety stock and {summary['excess_cover_days']} days of demand cover.",
        "",
        "## Inventory position",
        "",
        f"- On-hand inventory: {summary['total_on_hand']:,} units.",
        f"- Reserved inventory: {summary['total_reserved']:,} units.",
        f"- Available inventory: {summary['total_available']:,} units.",
        f"- Low-stock products: {summary['low_stock_products']}.",
        f"- High or out-of-stock risk products: {summary['high_or_out_stockout_risk']}.",
        f"- Slow-moving products: {summary['slow_moving_products']}.",
        f"- Excess-inventory products: {summary['excess_inventory_products']}, representing ${summary['excess_inventory_value']:,.2f} of estimated excess cost.",
        "",
        "## Products requiring review",
        "",
        "| Product | Available | Turnover proxy | Days of supply | Low stock | Slow moving | Excess units | Stockout risk |",
        "|---|---:|---:|---:|---|---|---:|---|",
    ]
    for row in attention.itertuples():
        turnover = "n.a." if pd.isna(row.inventory_turnover_proxy) else f"{row.inventory_turnover_proxy:.2f}"
        cover = "n.a." if pd.isna(row.days_of_supply) else f"{row.days_of_supply:.0f}"
        lines.append(
            f"| {row.product_name} ({row.product_id}) | {int(row.available_stock):,} | {turnover} | {cover} | "
            f"{'Yes' if row.low_stock else 'No'} | {'Yes' if row.slow_moving else 'No'} | "
            f"{int(row.excess_units):,} | {row.stockout_risk} |"
        )
    lines.extend([
        "",
        "## Recommended actions",
        "",
        "1. Review purchase orders and expedite replenishment for high-risk products.",
        "2. Reduce or defer orders for excess and slow-moving products before adding new stock.",
        "3. Add periodic inventory snapshots so future turnover uses average inventory rather than the current-stock proxy.",
        "",
    ])
    report.write_text("\n".join(lines), encoding="utf-8")


def run_inventory_analysis(
    data_dir: Path | str,
    report_path: Path | str,
    trailing_days: int = 90,
    excess_cover_days: int = 180,
    slow_turnover_threshold: float = 1.0,
) -> dict[str, Any]:
    """Run the complete inventory analysis workflow."""
    frames = load_clean_datasets(data_dir)
    analysis, summary = calculate_inventory_metrics(
        frames, trailing_days, excess_cover_days, slow_turnover_threshold
    )
    write_inventory_outputs(analysis, summary, report_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--report", type=Path, default=Path("reports/day7_inventory_analysis.md"))
    parser.add_argument("--trailing-days", type=int, default=90)
    parser.add_argument("--excess-cover-days", type=int, default=180)
    parser.add_argument("--slow-turnover-threshold", type=float, default=1.0)
    args = parser.parse_args()
    summary = run_inventory_analysis(
        args.data_dir,
        args.report,
        args.trailing_days,
        args.excess_cover_days,
        args.slow_turnover_threshold,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
