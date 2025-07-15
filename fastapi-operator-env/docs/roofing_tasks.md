# Roofing Tasks

This project includes simple helpers for the roofing vertical.

## parse_eagleview_report

Provide an EagleView JSON payload and receive a CSV quantity take‑off. Example:

```python
from codex import run_task
report = {"measurements": {"roofAreas": {"totalArea": 2500, "totalSquares": 25}}}
result = run_task("parse_eagleview_report", {"report": report})
print(result["csv"])
```

## generate_roof_estimate

Given roof quantities and an optional pricing sheet, compute material and labor totals.

```python
quantities = result["quantities"]
estimate = run_task("generate_roof_estimate", {"quantities": quantities})
print(estimate["total"])
```

See `tests/test_roofing_tasks.py` for sample fixtures.
