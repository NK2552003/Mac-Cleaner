from pathlib import Path

from utils import bytes_human, derive_display_name


def test_bytes_human_units() -> None:
    assert bytes_human(0) == "0.0 B"
    assert bytes_human(1024) == "1.0 KB"
    assert bytes_human(1024 * 1024) == "1.0 MB"


def test_derive_display_name() -> None:
    assert derive_display_name("com.example.my-app") == "My App"
