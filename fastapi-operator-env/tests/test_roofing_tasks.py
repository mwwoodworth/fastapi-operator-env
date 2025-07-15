import importlib

from codex import run_task

SAMPLE_REPORT = {
    "measurements": {
        "roofAreas": {"totalArea": 2500, "totalSquares": 25},
        "perimeter": 200,
        "ridges": 80,
        "hips": 60,
        "valleys": 40,
    }
}


def test_parse_eagleview_report():
    res = run_task("parse_eagleview_report", {"report": SAMPLE_REPORT})
    assert "csv" in res
    csv_text = res["csv"]
    assert "total_area_sqft" in csv_text
    quantities = res["quantities"]
    assert quantities["total_squares"] == 25


def test_generate_roof_estimate():
    parse_res = run_task("parse_eagleview_report", {"report": SAMPLE_REPORT})
    quantities = parse_res["quantities"]
    est = run_task("generate_roof_estimate", {"quantities": quantities})
    assert est["total"] > 0
    assert est["material"] > 0
    assert est["labor"] > 0
    assert est["line_items"]["shingles"]["total"] > 0
