# tests\test_pcr_graph_pg_geometry.py
from __future__ import annotations

import unittest

import numpy as np

from app.views.plotting.pcr_graph_pg import geometry


class GeometryPGTests(unittest.TestCase):
    def setUp(self) -> None:
        self.geoms = {
            "A01": {"fam": np.array([[0, 1], [1, 2]]), "hex": np.array([[0, 2], [1, 3]])},
            "A02": {"fam": np.array([[2, 5], [3, 6]]), "hex": np.array([[2, 6], [3, 8]])},
            "A03": {"fam": np.array([], dtype=float).reshape(0, 2), "hex": np.array([[4, 1], [5, 1.5]])},
        }

    def test_bounding_box_union_channels(self) -> None:
        index = geometry.build_spatial_index(self.geoms, fam_visible=True, hex_visible=True)
        self.assertIsNotNone(index)
        if index:
            boxes = {well: box for well, box in zip(index.wells, index.boxes.tolist())}
            self.assertEqual(boxes["A01"], [0.0, 1.0, 1.0, 3.0])
            self.assertEqual(boxes["A02"], [2.0, 3.0, 5.0, 8.0])
            self.assertEqual(boxes["A03"], [4.0, 5.0, 1.0, 1.5])

    def test_bounding_box_visibility_filter(self) -> None:
        index = geometry.build_spatial_index(self.geoms, fam_visible=False, hex_visible=True)
        self.assertIsNotNone(index)
        if index:
            self.assertEqual(index.wells, ["A01", "A02", "A03"])
            self.assertEqual(index.boxes.tolist()[0], [0.0, 1.0, 2.0, 3.0])

    def test_wells_in_rect_filters_by_visible_channels(self) -> None:
        index = geometry.build_spatial_index(self.geoms, fam_visible=True, hex_visible=False)
        wells = geometry.wells_in_rect(index, self.geoms, 0, 2.5, 0, 5, fam_visible=True, hex_visible=False)
        self.assertEqual(wells, {"A01", "A02"})

        hex_index = geometry.build_spatial_index(self.geoms, fam_visible=False, hex_visible=True)
        wells_hex_only = geometry.wells_in_rect(hex_index, self.geoms, 4, 6, 0, 2, fam_visible=False, hex_visible=True)
        self.assertEqual(wells_hex_only, {"A03"})

    def test_nearest_well_uses_tolerance(self) -> None:
        index = geometry.build_spatial_index(self.geoms, fam_visible=True, hex_visible=True)
        well = geometry.nearest_well(index, self.geoms, 0.9, 2.1, 0.5, 0.5, fam_visible=True, hex_visible=True)
        self.assertEqual(well, "A01")

        miss = geometry.nearest_well(index, self.geoms, 10, 10, 0.1, 0.1, fam_visible=True, hex_visible=True)
        self.assertIsNone(miss)


if __name__ == "__main__":
    unittest.main()