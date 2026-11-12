# motala-strom

A tiny, dependency-free Python model for exploring daily water balance in a
small Swedish catchment. It is an educational lumped model inspired by the
processes represented in HYPE; it is **not HYPE**, is not calibrated to a real
catchment, and is not intended for operational forecasts.

Requires Python 3.10 or later.

## Model

The model has three stores: snow water equivalent, soil water, and
groundwater. Each daily step:

1. Partitions precipitation between snow and rain using a linear temperature
   transition from 0 to 2 °C.
2. Melts snow above 0 °C using a degree-day factor.
3. Sends rain and meltwater to the soil bucket. A saturation-dependent share
   becomes quickflow; water above soil capacity also becomes quickflow.
4. Removes actual evapotranspiration, limited by soil moisture and potential
   evapotranspiration.
5. Drains soil water to groundwater, then releases a fraction of groundwater
   as baseflow.

The defaults are intentionally generic starting values, not Swedish regional
calibration values. The reported water-balance error checks that precipitation
equals evapotranspiration, discharge, and the change in all three stores.

## Run

Input is one row per consecutive day, with precipitation and PET in mm/day
and mean temperature in °C:

```csv
date,precipitation_mm,mean_temp_c,pet_mm
2026-03-01,4.0,-3.0,0.0
2026-03-02,0.0,-2.0,0.0
```

Run the included illustrative (synthetic) data with a 10 km² catchment:

```sh
python motala_hydro.py data/example_daily.csv --area-km2 10 --output simulation.csv
```

The output includes daily snowmelt, evapotranspiration, quickflow, baseflow,
storage levels, discharge in mm/day and m³/s, and the water-balance error.
Dates must be consecutive; missing forcing days should be filled before
running the model.

Run the tests with Python's standard library:

```sh
python -m unittest discover -s tests
```

## Interactive hydrograph notebook

Install the optional notebook dependencies and launch Jupyter:

```sh
python -m pip install -r requirements-notebook.txt
jupyter notebook notebooks/hydrograph_demo.ipynb
```

Generate the included, clearly labeled synthetic 90-day spring forcing file
with `python scripts/generate_synthetic_forcing.py`. The notebook reads that
CSV and plots precipitation, temperature, snow storage, and the simulated
hydrograph.

## Limitations

This is a single-bucket catchment-average model: it omits spatial variation,
river routing, detailed snow physics, and nutrient or water-quality processes.
Use measured forcing and calibrate parameters against observations before
interpreting it for a real catchment.
