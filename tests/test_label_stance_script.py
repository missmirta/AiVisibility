import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from label_stance import read_labeled, write_csv  # noqa: E402


def test_read_labeled_returns_rows_and_keys(tmp_path):
    path = tmp_path / "stance.csv"
    write_csv(path, [("[Stripe] a", "neutral", "Stripe", 7), ("[Paddle] b", "negative", "Paddle", 8)])
    rows, keys = read_labeled(path)
    assert len(rows) == 2
    assert keys == {("7", "Stripe"), ("8", "Paddle")}


def test_read_labeled_missing_file_is_empty(tmp_path):
    assert read_labeled(tmp_path / "nope.csv") == ([], set())
