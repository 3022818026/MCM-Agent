from __future__ import annotations

import unittest

from flowchart_geometry import display_label, node_dimensions, prepare_layout, serpentine_positions


class FlowchartGeometryTests(unittest.TestCase):
    def test_three_column_serpentine_order(self) -> None:
        labels = [f"步骤{i}" for i in range(1, 11)]
        positions = serpentine_positions(labels)
        self.assertLess(positions[labels[0]][0], positions[labels[1]][0])
        self.assertLess(positions[labels[1]][0], positions[labels[2]][0])
        self.assertEqual(positions[labels[2]][0], positions[labels[3]][0])
        self.assertGreater(positions[labels[3]][0], positions[labels[4]][0])
        self.assertGreater(positions[labels[4]][0], positions[labels[5]][0])
        self.assertEqual(positions[labels[5]][0], positions[labels[6]][0])
        self.assertLess(positions[labels[6]][0], positions[labels[7]][0])
        self.assertLess(positions[labels[7]][0], positions[labels[8]][0])
        self.assertEqual(positions[labels[8]][0], positions[labels[9]][0])

    def test_long_label_wraps_to_two_lines_and_sizes_are_uniform(self) -> None:
        wrapped = display_label("建立多目标优化约束条件")
        self.assertEqual(len(wrapped.splitlines()), 2)
        width, height = node_dimensions({"A": wrapped, "B": "读取数据"})
        self.assertGreaterEqual(width, 0.18)
        self.assertEqual(height, 0.15)

    def test_default_layout_requires_linear_edges(self) -> None:
        labels = ["A", "B", "C"]
        width, height = node_dimensions({label: label for label in labels})
        with self.assertRaisesRegex(ValueError, "线性流程"):
            prepare_layout(labels, [("A", "B"), ("A", "C")], None, width, height)

    def test_default_segments_are_horizontal_or_vertical(self) -> None:
        labels = [f"N{i}" for i in range(7)]
        width, height = node_dimensions({label: label for label in labels})
        _, rows, segments = prepare_layout(labels, list(zip(labels, labels[1:])), None, width, height)
        self.assertEqual(rows, 3)
        self.assertTrue(all(orientation in {"horizontal", "vertical"} for _, _, orientation in segments))

    def test_diagonal_explicit_edge_is_rejected(self) -> None:
        labels = ["A", "B"]
        width, height = node_dimensions({label: label for label in labels})
        with self.assertRaisesRegex(ValueError, "水平或垂直对齐"):
            prepare_layout(labels, [("A", "B")], {"A": (0.2, 0.2), "B": (0.8, 0.8)}, width, height)

    def test_crossing_edges_are_rejected(self) -> None:
        labels = ["A", "B", "C", "D"]
        width, height = node_dimensions({label: label for label in labels})
        positions = {"A": (0.2, 0.5), "B": (0.8, 0.5), "C": (0.5, 0.8), "D": (0.5, 0.2)}
        with self.assertRaisesRegex(ValueError, "交叉或重叠"):
            prepare_layout(labels, [("A", "B"), ("C", "D")], positions, width, height)

    def test_arrow_through_node_is_rejected(self) -> None:
        labels = ["A", "B", "C"]
        width, height = node_dimensions({label: label for label in labels})
        positions = {"A": (0.2, 0.5), "B": (0.8, 0.5), "C": (0.5, 0.5)}
        with self.assertRaisesRegex(ValueError, "穿过节点"):
            prepare_layout(labels, [("A", "B")], positions, width, height)


if __name__ == "__main__":
    unittest.main()
