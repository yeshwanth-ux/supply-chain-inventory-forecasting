"""Static contract tests for reporting SQL in both supported databases."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VIEWS = {
    "vw_product_sales",
    "vw_inventory_availability",
    "vw_monthly_sales",
    "vw_product_performance",
    "vw_supplier_performance",
}


class SqlAnalysisTests(unittest.TestCase):
    def test_each_database_defines_all_reporting_views(self) -> None:
        for filename in ("postgres_views.sql", "sqlserver_views.sql"):
            sql = (ROOT / "sql" / "views" / filename).read_text(encoding="utf-8").lower()
            for view in EXPECTED_VIEWS:
                self.assertRegex(sql, rf"create\s+(?:or\s+(?:replace|alter)\s+)?view\s+(?:supply_chain\.)?{view}\b")

    def test_latest_inventory_snapshot_is_ranked_per_warehouse(self) -> None:
        for filename in ("postgres_views.sql", "sqlserver_views.sql"):
            sql = (ROOT / "sql" / "views" / filename).read_text(encoding="utf-8").lower()
            self.assertIn("partition by i.product_id, i.warehouse_id", sql)
            self.assertIn("order by i.snapshot_date desc", sql)

    def test_analysis_files_cover_required_metrics(self) -> None:
        for filename in ("postgres_analysis.sql", "sqlserver_analysis.sql"):
            sql = (ROOT / "sql" / "queries" / filename).read_text(encoding="utf-8").lower()
            for term in ("total_sales", "total_ordered_demand", "stock_status", "net_units_sold", "inventory_cost_value"):
                self.assertIn(term, sql)
            self.assertIsNone(re.search(r"\bdelete\b|\btruncate\b|\bdrop\b", sql))


if __name__ == "__main__":
    unittest.main()
