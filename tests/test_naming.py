from pathlib import Path

from src.utils.naming import output_name


def test_output_name_keeps_original_stem_and_index():
    assert output_name(Path("51.tif"), 3) == "51-3.tif"


def test_output_name_uses_forced_extension():
    assert output_name(Path("51.tif"), 1, "png") == "51-1.png"
