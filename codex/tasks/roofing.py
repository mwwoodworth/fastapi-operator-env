"""Roofing utilities for EagleView parsing and estimate generation."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, Optional

from pydantic import BaseModel

from codex.brainops_operator import register_task


class EagleViewParseRequest(BaseModel):
    """Request payload for :func:`parse_eagleview_report`."""

    report: Any


class EagleViewParseResponse(BaseModel):
    """Response from :func:`parse_eagleview_report`."""

    quantities: Dict[str, float]
    csv: str


class RoofEstimateRequest(BaseModel):
    """Input for :func:`generate_roof_estimate`."""

    quantities: Dict[str, float]
    pricing: Optional[Dict[str, Dict[str, float]]] = None


class RoofEstimateResponse(BaseModel):
    """Cost estimate result."""

    total: float
    material: float
    labor: float
    line_items: Dict[str, Dict[str, float]]


DEFAULT_PRICING = {
    "shingles_per_square": {"material": 120.0, "labor": 200.0},
    "ridge_per_ft": {"material": 2.0, "labor": 4.0},
    "hip_per_ft": {"material": 2.0, "labor": 4.0},
    "valley_per_ft": {"material": 3.0, "labor": 5.0},
    "perimeter_per_ft": {"material": 1.0, "labor": 2.0},
}


def _parse_report(data: Dict[str, Any]) -> Dict[str, float]:
    """Internal helper to normalize measurement fields."""

    measurements = data.get("measurements") or data.get("Measurements") or {}
    roof_areas = measurements.get("roofAreas") or {}

    area = (
        roof_areas.get("totalArea")
        or measurements.get("totalArea")
        or measurements.get("area")
        or 0
    )
    squares = (
        roof_areas.get("totalSquares")
        or measurements.get("totalSquares")
        or measurements.get("squares")
        or 0
    )
    perimeter = measurements.get("perimeter") or measurements.get("perimeterLength") or 0
    ridge = measurements.get("ridges") or measurements.get("ridgeLength") or 0
    hip = measurements.get("hips") or measurements.get("hipLength") or 0
    valley = measurements.get("valleys") or measurements.get("valleyLength") or 0
    if not squares and area:
        squares = area / 100.0

    return {
        "total_area_sqft": float(area),
        "total_squares": float(squares),
        "perimeter_ft": float(perimeter),
        "ridge_ft": float(ridge),
        "hip_ft": float(hip),
        "valley_ft": float(valley),
    }


def parse_eagleview_report(context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract roof quantities from an EagleView JSON report."""

    payload = context.get("report")
    if payload is None:
        return {"error": "missing_report"}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {"error": "invalid_json"}

    quantities = _parse_report(payload)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["quantity", "value"])
    for key, value in quantities.items():
        writer.writerow([key, value])
    csv_output = buffer.getvalue()

    return {"quantities": quantities, "csv": csv_output}


def generate_roof_estimate(context: Dict[str, Any]) -> Dict[str, Any]:
    """Create a basic cost estimate using roof quantities and pricing."""

    quantities = context.get("quantities")
    if not isinstance(quantities, dict):
        return {"error": "missing_quantities"}
    pricing: Dict[str, Dict[str, float]] = context.get("pricing") or DEFAULT_PRICING

    total_material = 0.0
    total_labor = 0.0
    line_items: Dict[str, Dict[str, float]] = {}

    def add_item(name: str, qty: float, price_key: str) -> None:
        nonlocal total_material, total_labor
        price = pricing.get(price_key, {"material": 0.0, "labor": 0.0})
        mat = qty * price.get("material", 0.0)
        lab = qty * price.get("labor", 0.0)
        total_material += mat
        total_labor += lab
        line_items[name] = {"material": mat, "labor": lab, "total": mat + lab}

    add_item("shingles", float(quantities.get("total_squares", 0.0)), "shingles_per_square")
    add_item("ridge", float(quantities.get("ridge_ft", 0.0)), "ridge_per_ft")
    add_item("hip", float(quantities.get("hip_ft", 0.0)), "hip_per_ft")
    add_item("valley", float(quantities.get("valley_ft", 0.0)), "valley_per_ft")
    add_item("perimeter", float(quantities.get("perimeter_ft", 0.0)), "perimeter_per_ft")

    total = total_material + total_labor
    return {
        "total": total,
        "material": total_material,
        "labor": total_labor,
        "line_items": line_items,
    }


register_task(
    "parse_eagleview_report",
    parse_eagleview_report,
    "Parse EagleView JSON report to CSV quantities",
    ["report"],
)
register_task(
    "generate_roof_estimate",
    generate_roof_estimate,
    "Generate roof estimate from quantities and pricing",
    ["quantities"],
)
