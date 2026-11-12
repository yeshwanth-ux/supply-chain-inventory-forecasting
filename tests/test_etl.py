"""Integration test for CSV extraction, cleaning, and processed output."""

import tempfile
import unittest
from pathlib import Path

from src.data.generate_synthetic import generate_datasets
from src.pipeline.run_etl import run_etl


class EtlTests(unittest.TestCase):
    def test_etl_writes_all_processed_files_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            generate_datasets(source, seed=42)
            result = run_etl(source, output)
            for name in ("products", "suppliers", "inventory", "orders", "sales", "shipments"):
                self.assertTrue((Path(output) / f"{name}.csv").is_file())
                self.assertGreater(result["quality"][name]["output_rows"], 0)
            self.assertTrue((Path(output) / "etl_report.json").is_file())


if __name__ == "__main__":
    unittest.main()
