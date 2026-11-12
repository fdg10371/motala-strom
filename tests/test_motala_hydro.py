import io
import unittest
from datetime import date, timedelta

from motala_hydro import DailyForcing, ModelParameters, read_forcing_csv, simulate


class HydrologyModelTests(unittest.TestCase):
    def test_snow_accumulates_and_melts(self) -> None:
        start = date(2026, 2, 1)
        results = simulate(
            [
                DailyForcing(start, 10.0, -1.0, 0.0),
                DailyForcing(start + timedelta(days=1), 0.0, 2.0, 0.0),
            ],
            area_km2=10.0,
        )

        self.assertAlmostEqual(results[0].snow_storage_mm, 10.0)
        self.assertAlmostEqual(results[1].snowmelt_mm, 6.0)
        self.assertAlmostEqual(results[1].snow_storage_mm, 4.0)

    def test_water_balance_closes(self) -> None:
        start = date(2026, 4, 1)
        forcings = [
            DailyForcing(start + timedelta(days=i), p, t, pet)
            for i, (p, t, pet) in enumerate(
                [(12.0, 4.0, 1.0), (0.0, 6.0, 2.0), (7.0, -2.0, 0.0), (3.0, 3.0, 1.0)]
            )
        ]

        results = simulate(forcings, area_km2=8.5)

        for row in results:
            self.assertAlmostEqual(row.water_balance_error_mm, 0.0, places=10)
            self.assertGreaterEqual(row.snow_storage_mm, 0.0)
            self.assertGreaterEqual(row.soil_storage_mm, 0.0)
            self.assertGreaterEqual(row.groundwater_storage_mm, 0.0)
        self.assertAlmostEqual(
            results[0].discharge_m3_s,
            results[0].discharge_mm * 8.5 * 1000.0 / 86400.0,
        )

    def test_rejects_nonconsecutive_days(self) -> None:
        with self.assertRaisesRegex(ValueError, "consecutive"):
            simulate(
                [
                    DailyForcing(date(2026, 1, 1), 1.0, 2.0, 0.0),
                    DailyForcing(date(2026, 1, 3), 1.0, 2.0, 0.0),
                ],
                area_km2=1.0,
            )

    def test_rejects_invalid_parameters_and_forcing(self) -> None:
        with self.assertRaisesRegex(ValueError, "soil_capacity"):
            ModelParameters(soil_capacity_mm=0.0)
        with self.assertRaisesRegex(ValueError, "runoff_exponent"):
            ModelParameters(runoff_exponent=float("nan"))
        with self.assertRaisesRegex(ValueError, "precipitation"):
            DailyForcing(date(2026, 1, 1), -1.0, 2.0, 0.0)

    def test_reads_csv_forcing(self) -> None:
        forcing = read_forcing_csv(
            io.StringIO(
                "date,precipitation_mm,mean_temp_c,pet_mm\n"
                "2026-01-01,2.5,-1,0\n"
            )
        )
        self.assertEqual(forcing[0].day, date(2026, 1, 1))
        self.assertAlmostEqual(forcing[0].precipitation_mm, 2.5)


if __name__ == "__main__":
    unittest.main()
