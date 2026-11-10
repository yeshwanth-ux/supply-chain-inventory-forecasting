"""Tests for synthetic collection and ingestion."""

import tempfile
import unittest
from pathlib import Path

from src.data.generate_synthetic import generate_datasets
from src.data.ingestion import load_datasets


class DataCollectionTests(unittest.TestCase):
    def test_generation_is_complete_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts = generate_datasets(directory, seed=42)
            datasets = load_datasets(Path(directory))
            self.assertEqual(counts["products"], 30)
            self.assertEqual(counts["orders"], 1000)
            self.assertEqual(set(counts), set(datasets))

    def test_fixed_seed_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            generate_datasets(first, seed=7)
            generate_datasets(second, seed=7)
            self.assertEqual((Path(first) / "orders.csv").read_bytes(), (Path(second) / "orders.csv").read_bytes())


if __name__ == "__main__":
    unittest.main()
