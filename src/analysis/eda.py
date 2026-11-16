"""Exploratory analysis for sales, demand, product, and inventory data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.cleaning import DATA_CONTRACTS, clean_datasets


def _read_csv_datasets(data_dir: Path | str) -> dict[str, pd.DataFrame]:
    root = Path(data_dir)
    frames: dict[str, pd.DataFrame] = {}
    for name in DATA_CONTRACTS:
        path = root / f"{name}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"Required input file not found: {path}")
        frames[name] = pd.read_csv(path, dtype="string", keep_default_na=True)
    return frames


def prepare_analysis(data_dir: Path | str) -> dict[str, Any]:
    """Load, clean, join, and aggregate the source datasets."""
    frames, _ = clean_datasets(_read_csv_datasets(data_dir))
    products = frames["products"]
    sales = frames["sales"].merge(
        products[["product_id", "product_name", "category"]],
        on="product_id",
        how="left",
        validate="many_to_one",
    )

    sales["sales_month"] = sales["sale_date"].dt.to_period("M").dt.to_timestamp()
    monthly = (
        sales.groupby("sales_month", as_index=False)
        .agg(
            total_sales=("revenue", "sum"),
            net_units_sold=("quantity", "sum"),
            sales_transactions=("sale_id", "count"),
        )
        .sort_values("sales_month")
    )
    maximum_sale_date = sales["sale_date"].max()
    final_period = maximum_sale_date.to_period("M")
    monthly["is_complete_month"] = monthly["sales_month"].dt.to_period("M") < final_period
    if maximum_sale_date.is_month_end:
        monthly.loc[monthly["sales_month"].dt.to_period("M") == final_period, "is_complete_month"] = True

    complete_months = monthly.loc[monthly["is_complete_month"]].copy()
    complete_months["month_number"] = complete_months["sales_month"].dt.month
    seasonality = (
        complete_months.groupby("month_number", as_index=False)
        .agg(
            average_demand=("net_units_sold", "mean"),
            average_sales=("total_sales", "mean"),
            years_observed=("sales_month", "count"),
        )
        .sort_values("month_number")
    )
    seasonality["month"] = pd.to_datetime(seasonality["month_number"], format="%m").dt.strftime("%b")

    product_sales = (
        sales.groupby("product_id", as_index=False)
        .agg(
            net_units_sold=("quantity", "sum"),
            total_sales=("revenue", "sum"),
            sales_transactions=("sale_id", "count"),
            last_sale_date=("sale_date", "max"),
        )
    )
    product_performance = products[["product_id", "sku", "product_name", "category"]].merge(
        product_sales, on="product_id", how="left", validate="one_to_one"
    )
    product_performance[["net_units_sold", "total_sales", "sales_transactions"]] = product_performance[
        ["net_units_sold", "total_sales", "sales_transactions"]
    ].fillna(0)
    product_performance = product_performance.sort_values(
        ["net_units_sold", "total_sales"], ascending=False
    ).reset_index(drop=True)

    latest_inventory = (
        frames["inventory"]
        .sort_values("snapshot_date")
        .drop_duplicates(["product_id", "warehouse_id"], keep="last")
    )
    latest_inventory = latest_inventory.assign(
        available_quantity=latest_inventory["quantity_on_hand"] - latest_inventory["quantity_reserved"]
    )
    inventory = (
        latest_inventory.groupby("product_id", as_index=False)
        .agg(
            quantity_on_hand=("quantity_on_hand", "sum"),
            quantity_reserved=("quantity_reserved", "sum"),
            available_quantity=("available_quantity", "sum"),
            reorder_point=("reorder_point", "sum"),
        )
        .merge(products[["product_id", "product_name", "category"]], on="product_id", validate="one_to_one")
    )
    inventory["stock_status"] = "IN_STOCK"
    inventory.loc[inventory["available_quantity"] <= inventory["reorder_point"], "stock_status"] = "LOW_STOCK"
    inventory.loc[inventory["available_quantity"] <= 0, "stock_status"] = "OUT_OF_STOCK"

    category_sales = (
        sales.groupby("category", as_index=False)
        .agg(total_sales=("revenue", "sum"), net_units_sold=("quantity", "sum"))
        .sort_values("total_sales", ascending=False)
    )
    return {
        "sales": sales,
        "monthly": monthly,
        "seasonality": seasonality,
        "product_performance": product_performance,
        "inventory": inventory,
        "category_sales": category_sales,
    }


def calculate_insights(analysis: dict[str, Any]) -> dict[str, Any]:
    """Calculate headline metrics from prepared analysis tables."""
    monthly = analysis["monthly"]
    complete = monthly.loc[monthly["is_complete_month"]]
    products = analysis["product_performance"]
    inventory = analysis["inventory"]
    peak = complete.loc[complete["net_units_sold"].idxmax()]
    low = complete.loc[complete["net_units_sold"].idxmin()]
    top_five_share = products.head(5)["net_units_sold"].sum() / products["net_units_sold"].sum()
    return {
        "total_sales": round(float(products["total_sales"].sum()), 2),
        "net_units_sold": int(products["net_units_sold"].sum()),
        "peak_complete_month": peak["sales_month"].strftime("%Y-%m"),
        "peak_month_units": int(peak["net_units_sold"]),
        "lowest_complete_month": low["sales_month"].strftime("%Y-%m"),
        "lowest_month_units": int(low["net_units_sold"]),
        "monthly_demand_variation": round(float(complete["net_units_sold"].std(ddof=0) / complete["net_units_sold"].mean()), 4),
        "top_product_id": str(products.iloc[0]["product_id"]),
        "top_product_name": str(products.iloc[0]["product_name"]),
        "top_product_units": int(products.iloc[0]["net_units_sold"]),
        "top_five_unit_share": round(float(top_five_share), 4),
        "low_stock_products": int((inventory["stock_status"] == "LOW_STOCK").sum()),
        "out_of_stock_products": int((inventory["stock_status"] == "OUT_OF_STOCK").sum()),
        "complete_months_observed": int(len(complete)),
    }


def _create_pillow_figures(analysis: dict[str, Any], output: Path) -> list[Path]:
    """Create PNG charts with Pillow when Matplotlib is unavailable."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1200, 650
    navy, blue, green, orange, grid, ink = "#17365D", "#5B9BD5", "#70AD47", "#ED7D31", "#D9E2F3", "#243447"

    def font(size: int, bold: bool = False):
        filename = "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"
        try:
            return ImageFont.truetype(filename, size)
        except OSError:
            return ImageFont.load_default()

    def canvas(title: str):
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        draw.text((55, 28), title, fill=navy, font=font(28, True))
        return image, draw

    def vertical_bars(draw, labels, values, box, color, y_label):
        left, top, right, bottom = box
        maximum = max(values) if values else 1
        draw.line((left, top, left, bottom), fill=ink, width=2)
        draw.line((left, bottom, right, bottom), fill=ink, width=2)
        for step in range(5):
            y = bottom - (bottom - top) * step / 4
            draw.line((left, y, right, y), fill=grid, width=1)
            draw.text((left - 48, y - 9), f"{maximum * step / 4:,.0f}", fill=ink, font=font(13))
        slot = (right - left) / max(len(values), 1)
        for index, (label, value) in enumerate(zip(labels, values)):
            x1 = left + slot * index + slot * 0.18
            x2 = left + slot * (index + 1) - slot * 0.18
            y = bottom - (bottom - top) * value / maximum
            draw.rectangle((x1, y, x2, bottom), fill=color)
            draw.text((x1, bottom + 9), str(label), fill=ink, font=font(12))
        draw.text((left, top - 30), y_label, fill=ink, font=font(14, True))

    created: list[Path] = []
    monthly = analysis["monthly"]
    image, draw = canvas("Monthly sales and demand")
    month_labels = monthly["sales_month"].dt.strftime("%b%y").tolist()
    vertical_bars(draw, month_labels, monthly["net_units_sold"].tolist(), (80, 110, 570, 550), blue, "Net units")
    vertical_bars(draw, month_labels, monthly["total_sales"].tolist(), (680, 110, 1170, 550), green, "Net sales")
    path = output / "sales_demand_trends.png"
    image.save(path)
    created.append(path)

    seasonality = analysis["seasonality"]
    image, draw = canvas("Average demand by calendar month")
    vertical_bars(draw, seasonality["month"].tolist(), seasonality["average_demand"].tolist(), (85, 105, 1160, 550), blue, "Average units")
    path = output / "seasonal_demand.png"
    image.save(path)
    created.append(path)

    top = analysis["product_performance"].head(10).sort_values("net_units_sold")
    image, draw = canvas("Top products by net units sold")
    left, top_y, right, bottom = 220, 105, 1160, 565
    maximum = max(top["net_units_sold"].tolist())
    slot = (bottom - top_y) / len(top)
    for index, row in enumerate(top.itertuples()):
        y1, y2 = top_y + index * slot + 6, top_y + (index + 1) * slot - 6
        x2 = left + (right - left) * row.net_units_sold / maximum
        draw.text((35, y1 + 5), row.product_name, fill=ink, font=font(15))
        draw.rectangle((left, y1, x2, y2), fill=green)
        draw.text((x2 + 8, y1 + 5), f"{int(row.net_units_sold):,}", fill=ink, font=font(14, True))
    path = output / "product_performance.png"
    image.save(path)
    created.append(path)

    def histogram(draw, values, box, color, label):
        bins = 10
        low, high = min(values), max(values)
        width_value = (high - low) / bins or 1
        counts = [0] * bins
        for value in values:
            counts[min(int((value - low) / width_value), bins - 1)] += 1
        vertical_bars(draw, [str(i + 1) for i in range(bins)], counts, box, color, label)

    image, draw = canvas("Sales and inventory distributions")
    histogram(draw, analysis["product_performance"]["total_sales"].tolist(), (80, 120, 570, 550), orange, "Products by sales bin")
    histogram(draw, analysis["inventory"]["available_quantity"].tolist(), (680, 120, 1170, 550), blue, "Products by stock bin")
    path = output / "sales_inventory_distributions.png"
    image.save(path)
    created.append(path)
    return created


def create_figures(analysis: dict[str, Any], output_dir: Path | str) -> list[Path]:
    """Create and save four EDA figures, with a Pillow fallback."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        return _create_pillow_figures(analysis, output)

    sns.set_theme(style="whitegrid", context="notebook")
    created: list[Path] = []

    monthly = analysis["monthly"]
    fig, sales_axis = plt.subplots(figsize=(11, 6))
    demand_axis = sales_axis.twinx()
    sales_axis.plot(monthly["sales_month"], monthly["total_sales"], marker="o", color="#1f4e78")
    demand_axis.bar(monthly["sales_month"], monthly["net_units_sold"], width=20, color="#9dc3e6", alpha=0.35)
    sales_axis.set(title="Monthly sales and demand", xlabel="Month", ylabel="Net sales")
    demand_axis.set_ylabel("Net units sold")
    sales_axis.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    created.append(output / "sales_demand_trends.png")
    fig.savefig(created[-1], dpi=160, bbox_inches="tight")
    plt.close(fig)

    seasonality = analysis["seasonality"]
    fig, axis = plt.subplots(figsize=(10, 5))
    sns.barplot(data=seasonality, x="month", y="average_demand", color="#4472c4", ax=axis)
    axis.axhline(seasonality["average_demand"].mean(), color="#c00000", linestyle="--", label="Monthly average")
    axis.set(title="Average demand by calendar month", xlabel="Month", ylabel="Average net units sold")
    axis.legend()
    fig.tight_layout()
    created.append(output / "seasonal_demand.png")
    fig.savefig(created[-1], dpi=160, bbox_inches="tight")
    plt.close(fig)

    top_products = analysis["product_performance"].head(10).sort_values("net_units_sold")
    fig, axis = plt.subplots(figsize=(10, 6))
    sns.barplot(data=top_products, y="product_name", x="net_units_sold", color="#70ad47", ax=axis)
    axis.set(title="Top products by net units sold", xlabel="Net units sold", ylabel="Product")
    fig.tight_layout()
    created.append(output / "product_performance.png")
    fig.savefig(created[-1], dpi=160, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    sns.histplot(data=analysis["product_performance"], x="total_sales", bins=10, ax=axes[0], color="#ed7d31")
    axes[0].set(title="Sales distribution by product", xlabel="Net sales", ylabel="Products")
    sns.histplot(data=analysis["inventory"], x="available_quantity", bins=10, ax=axes[1], color="#5b9bd5")
    axes[1].set(title="Available inventory distribution", xlabel="Available units", ylabel="Products")
    fig.tight_layout()
    created.append(output / "sales_inventory_distributions.png")
    fig.savefig(created[-1], dpi=160, bbox_inches="tight")
    plt.close(fig)
    return created


def write_outputs(analysis: dict[str, Any], insights: dict[str, Any], report_path: Path | str) -> None:
    """Write summary tables and a concise Markdown business report."""
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    tables_dir = report.parent / "eda_tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for name in ("monthly", "seasonality", "product_performance", "inventory", "category_sales"):
        analysis[name].to_csv(tables_dir / f"{name}.csv", index=False, date_format="%Y-%m-%d")

    top = analysis["product_performance"].head(5)
    low_stock = analysis["inventory"].loc[analysis["inventory"]["stock_status"] != "IN_STOCK"]
    priority = low_stock.loc[low_stock["product_id"].isin(top["product_id"])]
    lines = [
        "# Day 6 Exploratory Data Analysis",
        "",
        "## Scope",
        "",
        "The analysis uses synthetic sales and inventory data. Returns reduce units and sales. The final partial month is excluded from peak, low, and seasonal comparisons.",
        "",
        "## Business insights",
        "",
        f"- Net sales total ${insights['total_sales']:,.2f} across {insights['net_units_sold']:,} net units.",
        f"- {insights['peak_complete_month']} has the highest complete-month demand at {insights['peak_month_units']:,} units. {insights['lowest_complete_month']} has the lowest at {insights['lowest_month_units']:,} units.",
        f"- Complete-month demand varies by {insights['monthly_demand_variation']:.1%} relative to its mean. Only {insights['complete_months_observed']} complete months are available, so the data does not establish a recurring seasonal pattern.",
        f"- {insights['top_product_name']} ({insights['top_product_id']}) leads demand with {insights['top_product_units']:,} net units. The top five products contribute {insights['top_five_unit_share']:.1%} of net units.",
        f"- {insights['low_stock_products']} products are below their combined reorder points and {insights['out_of_stock_products']} are out of stock.",
        "",
        "## Top products",
        "",
        "| Product | Net units | Net sales |",
        "|---|---:|---:|",
    ]
    lines.extend(f"| {row.product_name} ({row.product_id}) | {int(row.net_units_sold):,} | ${row.total_sales:,.2f} |" for row in top.itertuples())
    lines.extend(["", "## Stock attention", "", "| Product | Available units | Reorder point | Status |", "|---|---:|---:|---|"])
    if low_stock.empty:
        lines.append("| None | 0 | 0 | No stock alerts |")
    else:
        lines.extend(f"| {row.product_name} ({row.product_id}) | {int(row.available_quantity):,} | {int(row.reorder_point):,} | {row.stock_status} |" for row in low_stock.itertuples())
    if priority.empty:
        priority_text = "Review every low-stock product against current purchase orders."
    else:
        names = ", ".join(f"{row.product_name} ({row.product_id})" for row in priority.itertuples())
        priority_text = f"Prioritize replenishment for {names}, which combines top-five demand with low stock."
    lines.extend(["", "## Interpretation", "", f"{priority_text} Add at least two full years of observed demand before treating month-of-year differences as seasonality.", ""])
    report.write_text("\n".join(lines), encoding="utf-8")


def run_eda(data_dir: Path | str, figure_dir: Path | str, report_path: Path | str) -> dict[str, Any]:
    """Run the complete exploratory analysis workflow."""
    analysis = prepare_analysis(data_dir)
    insights = calculate_insights(analysis)
    create_figures(analysis, figure_dir)
    write_outputs(analysis, insights, report_path)
    return insights


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--figure-dir", type=Path, default=Path("reports/figures"))
    parser.add_argument("--report", type=Path, default=Path("reports/day6_eda.md"))
    args = parser.parse_args()
    print(json.dumps(run_eda(args.data_dir, args.figure_dir, args.report), indent=2))


if __name__ == "__main__":
    main()
