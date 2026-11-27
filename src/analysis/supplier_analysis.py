"""Analyze supplier delivery performance and inbound purchase-order status."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.analysis.common import load_clean_datasets


def identify_delayed_shipments(
    shipments: pd.DataFrame, as_of_date: pd.Timestamp
) -> pd.DataFrame:
    """Return delivered-late and open-overdue inbound shipment lines."""
    detail = shipments.copy()
    detail["promised_lead_time_days"] = (
        detail["expected_date"] - detail["order_date"]
    ).dt.days
    detail["actual_lead_time_days"] = (
        detail["arrival_date"] - detail["order_date"]
    ).dt.days
    detail["delivery_variance_days"] = (
        detail["arrival_date"] - detail["expected_date"]
    ).dt.days
    detail["days_overdue"] = np.where(
        detail["arrival_date"].notna(),
        detail["delivery_variance_days"].clip(lower=0),
        (as_of_date - detail["expected_date"]).dt.days.clip(lower=0),
    ).astype("int64")
    delivered_late = detail["arrival_date"].notna() & (
        detail["arrival_date"] > detail["expected_date"]
    )
    open_overdue = detail["arrival_date"].isna() & (
        detail["expected_date"] < as_of_date
    )
    marked_delayed = detail["status"].eq("delayed")
    detail["delay_reason"] = pd.NA
    detail.loc[delivered_late, "delay_reason"] = "DELIVERED_LATE"
    detail.loc[open_overdue, "delay_reason"] = "OPEN_OVERDUE"
    detail.loc[marked_delayed & ~open_overdue, "delay_reason"] = "MARKED_DELAYED"
    delayed = detail.loc[delivered_late | open_overdue | marked_delayed].copy()
    return delayed.sort_values(
        ["days_overdue", "expected_date", "shipment_id"],
        ascending=[False, True, True],
    ).reset_index(drop=True)


def calculate_supplier_performance(
    frames: dict[str, pd.DataFrame],
    on_time_target: float = 0.90,
    reliability_threshold: float = 0.90,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Calculate supplier delivery, lead-time, status, and reliability metrics."""
    if not 0 < on_time_target <= 1 or not 0 < reliability_threshold <= 1:
        raise ValueError("Performance thresholds must be greater than zero and at most one")
    shipments = frames["shipments"].copy()
    if shipments.empty:
        raise ValueError("Shipment data is empty")
    as_of_date = pd.Timestamp(frames["inventory"]["snapshot_date"].max())
    shipments["promised_lead_time_days"] = (
        shipments["expected_date"] - shipments["order_date"]
    ).dt.days
    shipments["actual_lead_time_days"] = (
        shipments["arrival_date"] - shipments["order_date"]
    ).dt.days
    shipments["delivery_variance_days"] = (
        shipments["arrival_date"] - shipments["expected_date"]
    ).dt.days
    shipments["is_delivered"] = shipments["arrival_date"].notna()
    shipments["is_on_time"] = shipments["is_delivered"] & (
        shipments["arrival_date"] <= shipments["expected_date"]
    )
    shipments["is_late_delivery"] = shipments["is_delivered"] & ~shipments["is_on_time"]
    shipments["is_open"] = ~shipments["is_delivered"]
    shipments["is_open_overdue"] = shipments["is_open"] & (
        shipments["expected_date"] < as_of_date
    )

    status = (
        shipments.groupby(["supplier_id", "status"], as_index=False)
        .agg(
            purchase_order_lines=("shipment_id", "count"),
            purchase_order_units=("quantity", "sum"),
        )
        .merge(
            frames["suppliers"][["supplier_id", "supplier_name"]],
            on="supplier_id",
            how="left",
            validate="many_to_one",
        )
    )
    supplier_totals = status.groupby("supplier_id")["purchase_order_lines"].transform("sum")
    status["status_share"] = status["purchase_order_lines"] / supplier_totals
    status = status[
        [
            "supplier_id",
            "supplier_name",
            "status",
            "purchase_order_lines",
            "purchase_order_units",
            "status_share",
        ]
    ].sort_values(["supplier_id", "status"]).reset_index(drop=True)

    aggregates = shipments.groupby("supplier_id", as_index=False).agg(
        shipment_count=("shipment_id", "count"),
        shipment_units=("quantity", "sum"),
        delivered_shipments=("is_delivered", "sum"),
        on_time_deliveries=("is_on_time", "sum"),
        late_deliveries=("is_late_delivery", "sum"),
        open_shipments=("is_open", "sum"),
        open_overdue_shipments=("is_open_overdue", "sum"),
        average_promised_lead_time_days=("promised_lead_time_days", "mean"),
        average_actual_lead_time_days=("actual_lead_time_days", "mean"),
        average_delivery_variance_days=("delivery_variance_days", "mean"),
    )
    performance = frames["suppliers"].merge(
        aggregates, on="supplier_id", how="left", validate="one_to_one"
    )
    count_columns = [
        "shipment_count",
        "shipment_units",
        "delivered_shipments",
        "on_time_deliveries",
        "late_deliveries",
        "open_shipments",
        "open_overdue_shipments",
    ]
    performance[count_columns] = performance[count_columns].fillna(0).astype("int64")
    performance["on_time_delivery_rate"] = performance["on_time_deliveries"].div(
        performance["delivered_shipments"].replace(0, pd.NA)
    )
    performance["late_delivery_rate"] = performance["late_deliveries"].div(
        performance["delivered_shipments"].replace(0, pd.NA)
    )
    performance["open_overdue_rate"] = performance["open_overdue_shipments"].div(
        performance["open_shipments"].replace(0, pd.NA)
    )
    performance["lead_time_variance_days"] = (
        performance["average_actual_lead_time_days"] - performance["lead_time_days"]
    )

    performance["on_time_below_target"] = (
        performance["on_time_delivery_rate"].fillna(0) < on_time_target
    )
    performance["configured_reliability_below_target"] = (
        performance["reliability_score"] < reliability_threshold
    )
    performance["actual_lead_time_above_configured"] = (
        performance["average_actual_lead_time_days"]
        > performance["lead_time_days"] * 1.25
    ).fillna(False)
    performance["has_open_overdue_shipments"] = performance["open_overdue_shipments"] > 0
    risk_columns = [
        "on_time_below_target",
        "configured_reliability_below_target",
        "actual_lead_time_above_configured",
        "has_open_overdue_shipments",
    ]
    performance["reliability_risk_count"] = performance[risk_columns].sum(axis=1)
    performance["supplier_status"] = "RELIABLE"
    performance.loc[
        performance["reliability_risk_count"] == 1, "supplier_status"
    ] = "REVIEW"
    performance.loc[
        (performance["reliability_risk_count"] >= 2)
        | (performance["on_time_delivery_rate"].fillna(0) < 0.80),
        "supplier_status",
    ] = "UNRELIABLE"

    delayed = identify_delayed_shipments(shipments, as_of_date).merge(
        frames["suppliers"][["supplier_id", "supplier_name"]],
        on="supplier_id",
        how="left",
        validate="many_to_one",
    )
    delayed_counts = delayed.groupby("supplier_id").size()
    performance["identified_delayed_shipments"] = (
        performance["supplier_id"].map(delayed_counts).fillna(0).astype("int64")
    )
    status_order = pd.CategoricalDtype(
        ["UNRELIABLE", "REVIEW", "RELIABLE"], ordered=True
    )
    performance["supplier_status"] = performance["supplier_status"].astype(status_order)
    performance = performance.sort_values(
        ["supplier_status", "reliability_risk_count", "on_time_delivery_rate", "supplier_id"],
        ascending=[True, False, True, True],
        na_position="first",
    ).reset_index(drop=True)

    summary = {
        "as_of_date": as_of_date.strftime("%Y-%m-%d"),
        "supplier_count": int(len(performance)),
        "shipment_count": int(len(shipments)),
        "shipment_units": int(shipments["quantity"].sum()),
        "delivered_shipments": int(shipments["is_delivered"].sum()),
        "identified_delayed_shipments": int(len(delayed)),
        "open_overdue_shipments": int(shipments["is_open_overdue"].sum()),
        "unreliable_suppliers": int(
            (performance["supplier_status"] == "UNRELIABLE").sum()
        ),
        "suppliers_for_review": int(
            (performance["supplier_status"] == "REVIEW").sum()
        ),
        "overall_on_time_delivery_rate": round(
            float(shipments["is_on_time"].sum() / max(shipments["is_delivered"].sum(), 1)),
            6,
        ),
        "average_actual_lead_time_days": round(
            float(shipments["actual_lead_time_days"].mean()), 2
        ),
        "on_time_target": on_time_target,
        "reliability_threshold": reliability_threshold,
    }
    return performance, delayed, status, summary


def write_supplier_outputs(
    performance: pd.DataFrame,
    delayed: pd.DataFrame,
    status: pd.DataFrame,
    summary: dict[str, Any],
    output_dir: Path | str,
    report_path: Path | str,
) -> None:
    """Write analysis tables, summary metadata, and a Markdown report."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    performance.to_csv(output / "supplier_performance.csv", index=False)
    delayed.to_csv(
        output / "delayed_shipments.csv", index=False, date_format="%Y-%m-%d"
    )
    status.to_csv(output / "purchase_order_status.csv", index=False)
    (output / "supplier_analysis_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    attention = performance.loc[
        performance["supplier_status"].isin(["UNRELIABLE", "REVIEW"])
    ]
    lines = [
        "# Day 14 Supplier and Order Analysis",
        "",
        "## Scope",
        "",
        f"The analysis covers {summary['shipment_count']:,} inbound shipment lines through {summary['as_of_date']}. Each shipment line represents an inbound purchase-order line because the available dataset does not include a separate purchase-order header identifier.",
        "",
        "A shipment is delayed when it arrived after its expected date, remains open after its expected date, or carries a delayed status. Supplier reliability uses four transparent checks: on-time delivery below target, configured reliability below target, actual lead time more than 25% above configured lead time, and open overdue shipments. Unreliable means at least two checks or an on-time rate below 80%; review means one check.",
        "",
        "## Overall performance",
        "",
        f"- Suppliers: {summary['supplier_count']}.",
        f"- Delivered shipments: {summary['delivered_shipments']:,}.",
        f"- Identified delayed shipments: {summary['identified_delayed_shipments']:,}, including {summary['open_overdue_shipments']:,} open overdue shipments.",
        f"- Overall on-time delivery rate: {summary['overall_on_time_delivery_rate']:.1%}.",
        f"- Average actual lead time: {summary['average_actual_lead_time_days']:.2f} days.",
        f"- Unreliable suppliers: {summary['unreliable_suppliers']}; suppliers requiring review: {summary['suppliers_for_review']}.",
        "",
        "## Suppliers requiring action",
        "",
        "| Status | Supplier | Shipments | On-time rate | Avg actual lead time | Open overdue | Risk flags |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in attention.itertuples(index=False):
        on_time = "n.a." if pd.isna(row.on_time_delivery_rate) else f"{row.on_time_delivery_rate:.1%}"
        actual_lead = (
            "n.a."
            if pd.isna(row.average_actual_lead_time_days)
            else f"{row.average_actual_lead_time_days:.2f}"
        )
        lines.append(
            f"| {row.supplier_status} | {row.supplier_name} ({row.supplier_id}) | {row.shipment_count:,} | {on_time} | {actual_lead} | {row.open_overdue_shipments:,} | {row.reliability_risk_count} |"
        )
    if attention.empty:
        lines.append("| RELIABLE | No suppliers require action |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Recommended actions",
            "",
            "1. Escalate open overdue shipments and confirm revised arrival dates.",
            "2. Review unreliable suppliers before assigning new purchase orders.",
            "3. Compare actual lead times with configured lead times during supplier reviews.",
            "4. Recalculate performance after shipment status or arrival-date updates.",
            "",
        ]
    )
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")


def run_supplier_analysis(
    data_dir: Path | str,
    output_dir: Path | str,
    report_path: Path | str,
    on_time_target: float = 0.90,
    reliability_threshold: float = 0.90,
) -> dict[str, Any]:
    """Run the complete supplier and inbound-order analysis workflow."""
    performance, delayed, status, summary = calculate_supplier_performance(
        load_clean_datasets(data_dir), on_time_target, reliability_threshold
    )
    write_supplier_outputs(performance, delayed, status, summary, output_dir, report_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/supplier_analysis")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("reports/day14_supplier_analysis.md")
    )
    parser.add_argument("--on-time-target", type=float, default=0.90)
    parser.add_argument("--reliability-threshold", type=float, default=0.90)
    args = parser.parse_args()
    print(
        json.dumps(
            run_supplier_analysis(
                args.data_dir,
                args.output_dir,
                args.report,
                args.on_time_target,
                args.reliability_threshold,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
