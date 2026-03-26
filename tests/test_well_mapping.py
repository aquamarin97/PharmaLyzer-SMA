# tests\test_well_mapping.py
from __future__ import annotations

import unittest

from app.utils import well_mapping


class WellMappingTests(unittest.TestCase):
    def test_round_trip_patient_no(self) -> None:
        for pn in (1, 12, 48, 96):
            well_id = well_mapping.patient_no_to_well_id(pn)
            self.assertEqual(well_mapping.well_id_to_patient_no(well_id), pn)

    def test_invalid_patient_no_raises(self) -> None:
        with self.assertRaises(ValueError):
            well_mapping.patient_no_to_well_id(0)
        with self.assertRaises(ValueError):
            well_mapping.patient_no_to_well_id(97)

    def test_table_index_translation(self) -> None:
        self.assertEqual(well_mapping.table_index_to_well_id(1, 1), "A01")
        self.assertIsNone(well_mapping.table_index_to_well_id(0, 0))
        self.assertEqual(well_mapping.wells_for_header(0, 0), well_mapping.all_well_ids())


if __name__ == "__main__":
    unittest.main()