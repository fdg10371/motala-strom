"""A small, lumped daily snow-and-soil water-balance model."""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, TextIO


@dataclass(frozen=True)
class DailyForcing:
    day: date
    precipitation_mm: float
    mean_temp_c: float
    pet_mm: float

    def __post_init__(self) -> None:
        for name in ("precipitation_mm", "mean_temp_c", "pet_mm"):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.precipitation_mm < 0:
            raise ValueError("precipitation_mm cannot be negative")
        if self.pet_mm < 0:
            raise ValueError("pet_mm cannot be negative")


@dataclass(frozen=True)
class ModelParameters:
    snow_threshold_c: float = 0.0
    rain_threshold_c: float = 2.0
    melt_threshold_c: float = 0.0
    degree_day_factor_mm_c_day: float = 3.0
    soil_capacity_mm: float = 150.0
    quickflow_fraction: float = 0.35
    runoff_exponent: float = 2.0
    percolation_rate_mm_day: float = 2.0
    baseflow_fraction_day: float = 0.03

    def __post_init__(self) -> None:
        for name in (
            "snow_threshold_c",
            "rain_threshold_c",
            "melt_threshold_c",
            "degree_day_factor_mm_c_day",
            "soil_capacity_mm",
            "quickflow_fraction",
            "runoff_exponent",
            "percolation_rate_mm_day",
            "baseflow_fraction_day",
        ):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        if self.snow_threshold_c >= self.rain_threshold_c:
            raise ValueError("snow_threshold_c must be below rain_threshold_c")
        if self.degree_day_factor_mm_c_day < 0:
            raise ValueError("degree_day_factor_mm_c_day cannot be negative")
        if self.soil_capacity_mm <= 0:
            raise ValueError("soil_capacity_mm must be positive")
        if not 0 <= self.quickflow_fraction <= 1:
            raise ValueError("quickflow_fraction must be between 0 and 1")
        if self.runoff_exponent <= 0:
            raise ValueError("runoff_exponent must be positive")
        if self.percolation_rate_mm_day < 0:
            raise ValueError("percolation_rate_mm_day cannot be negative")
        if not 0 <= self.baseflow_fraction_day <= 1:
            raise ValueError("baseflow_fraction_day must be between 0 and 1")


@dataclass(frozen=True)
class DailyResult:
    day: date
    precipitation_mm: float
    snowfall_mm: float
    snowmelt_mm: float
    actual_et_mm: float
    quickflow_mm: float
    baseflow_mm: float
    discharge_mm: float
    discharge_m3_s: float
    snow_storage_mm: float
    soil_storage_mm: float
    groundwater_storage_mm: float
    water_balance_error_mm: float


@dataclass
class _State:
    snow_mm: float = 0.0
    soil_mm: float = 0.0
    groundwater_mm: float = 0.0


def _snow_fraction(temp_c: float, parameters: ModelParameters) -> float:
    if temp_c <= parameters.snow_threshold_c:
        return 1.0
    if temp_c >= parameters.rain_threshold_c:
        return 0.0
    return (parameters.rain_threshold_c - temp_c) / (
        parameters.rain_threshold_c - parameters.snow_threshold_c
    )


def simulate(
    forcings: Iterable[DailyForcing],
    area_km2: float,
    parameters: ModelParameters = ModelParameters(),
) -> list[DailyResult]:
    """Simulate consecutive daily forcings and return catchment-average flows."""
    if not math.isfinite(area_km2) or area_km2 <= 0:
        raise ValueError("area_km2 must be a positive finite number")

    state = _State()
    results: list[DailyResult] = []
    previous_day: date | None = None

    for forcing in forcings:
        if previous_day is not None and forcing.day != previous_day + timedelta(days=1):
            raise ValueError("forcing dates must be consecutive daily dates")
        previous_day = forcing.day
        initial_storage = state.snow_mm + state.soil_mm + state.groundwater_mm

        snowfall = forcing.precipitation_mm * _snow_fraction(
            forcing.mean_temp_c, parameters
        )
        rainfall = forcing.precipitation_mm - snowfall
        state.snow_mm += snowfall

        snowmelt = min(
            state.snow_mm,
            parameters.degree_day_factor_mm_c_day
            * max(forcing.mean_temp_c - parameters.melt_threshold_c, 0.0),
        )
        state.snow_mm -= snowmelt

        soil_wetness = min(state.soil_mm / parameters.soil_capacity_mm, 1.0)
        quickflow = (
            (rainfall + snowmelt)
            * parameters.quickflow_fraction
            * soil_wetness**parameters.runoff_exponent
        )
        state.soil_mm += rainfall + snowmelt - quickflow

        soil_wetness = min(state.soil_mm / parameters.soil_capacity_mm, 1.0)
        actual_et = min(forcing.pet_mm * soil_wetness, state.soil_mm)
        state.soil_mm -= actual_et

        overflow = max(state.soil_mm - parameters.soil_capacity_mm, 0.0)
        state.soil_mm -= overflow
        quickflow += overflow

        percolation = min(
            state.soil_mm,
            parameters.percolation_rate_mm_day
            * state.soil_mm
            / parameters.soil_capacity_mm,
        )
        state.soil_mm -= percolation
        state.groundwater_mm += percolation

        baseflow = min(
            state.groundwater_mm,
            parameters.baseflow_fraction_day * state.groundwater_mm,
        )
        state.groundwater_mm -= baseflow

        discharge = quickflow + baseflow
        final_storage = state.snow_mm + state.soil_mm + state.groundwater_mm
        balance_error = (
            forcing.precipitation_mm
            - actual_et
            - discharge
            - (final_storage - initial_storage)
        )
        discharge_m3_s = discharge * area_km2 * 1000.0 / 86400.0

        results.append(
            DailyResult(
                day=forcing.day,
                precipitation_mm=forcing.precipitation_mm,
                snowfall_mm=snowfall,
                snowmelt_mm=snowmelt,
                actual_et_mm=actual_et,
                quickflow_mm=quickflow,
                baseflow_mm=baseflow,
                discharge_mm=discharge,
                discharge_m3_s=discharge_m3_s,
                snow_storage_mm=state.snow_mm,
                soil_storage_mm=state.soil_mm,
                groundwater_storage_mm=state.groundwater_mm,
                water_balance_error_mm=balance_error,
            )
        )

    return results


def read_forcing_csv(stream: TextIO) -> list[DailyForcing]:
    reader = csv.DictReader(stream)
    required = {"date", "precipitation_mm", "mean_temp_c", "pet_mm"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError(
            "input CSV must contain columns: date, precipitation_mm, "
            "mean_temp_c, pet_mm"
        )

    forcings: list[DailyForcing] = []
    for line_number, row in enumerate(reader, start=2):
        try:
            forcings.append(
                DailyForcing(
                    day=date.fromisoformat(row["date"]),
                    precipitation_mm=float(row["precipitation_mm"]),
                    mean_temp_c=float(row["mean_temp_c"]),
                    pet_mm=float(row["pet_mm"]),
                )
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid forcing at CSV line {line_number}: {error}") from error

    if not forcings:
        raise ValueError("input CSV contains no forcing rows")
    return forcings


def write_results_csv(results: Iterable[DailyResult], stream: TextIO) -> None:
    fields = list(DailyResult.__dataclass_fields__)
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for result in results:
        row = {field: getattr(result, field) for field in fields}
        row["day"] = result.day.isoformat()
        writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the simplified daily snow-and-soil catchment model."
    )
    parser.add_argument("forcing_csv", type=Path, help="daily forcing CSV")
    parser.add_argument(
        "--area-km2", type=float, required=True, help="catchment area in km^2"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("simulation.csv"),
        help="output CSV path (default: simulation.csv)",
    )
    args = parser.parse_args()

    with args.forcing_csv.open(newline="", encoding="utf-8") as forcing_file:
        forcings = read_forcing_csv(forcing_file)
    results = simulate(forcings, args.area_km2)
    with args.output.open("w", newline="", encoding="utf-8") as output_file:
        write_results_csv(results, output_file)

    max_balance_error = max(abs(row.water_balance_error_mm) for row in results)
    print(
        f"Wrote {len(results)} daily results to {args.output} "
        f"(maximum absolute water-balance error: {max_balance_error:.3g} mm)."
    )


if __name__ == "__main__":
    main()
