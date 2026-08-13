from __future__ import annotations

import sys
import unittest
from pathlib import Path


STAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE))

try:
    import matplotlib
except ModuleNotFoundError:
    matplotlib = None

if matplotlib is not None:
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, Rectangle

    from extended_templates import process_flowchart


@unittest.skipIf(matplotlib is None, "需要安装requirements.txt中的Matplotlib才能执行渲染集成测试。")
class ProcessFlowchartTests(unittest.TestCase):
    def tearDown(self) -> None:
        plt.close("all")

    def test_default_layout_is_three_column_serpentine(self) -> None:
        nodes = [f"步骤{i}" for i in range(1, 8)]
        edges = list(zip(nodes, nodes[1:]))
        _, ax = process_flowchart(nodes, edges)
        rectangles = [patch for patch in ax.patches if isinstance(patch, Rectangle)]
        arrows = [patch for patch in ax.patches if isinstance(patch, FancyArrowPatch)]
        self.assertEqual(len(rectangles), 7)
        self.assertEqual(len(arrows), 6)

        centers = [
            (rectangle.get_x() + rectangle.get_width() / 2, rectangle.get_y() + rectangle.get_height() / 2)
            for rectangle in rectangles
        ]
        self.assertLess(centers[0][0], centers[1][0])
        self.assertLess(centers[1][0], centers[2][0])
        self.assertAlmostEqual(centers[2][0], centers[3][0])
        self.assertGreater(centers[3][0], centers[4][0])
        self.assertGreater(centers[4][0], centers[5][0])
        self.assertAlmostEqual(centers[5][0], centers[6][0])
        self.assertTrue(all(rectangle.get_edgecolor()[:3] == (0.0, 0.0, 0.0) for rectangle in rectangles))
        self.assertTrue(all(rectangle.get_facecolor()[:3] == (1.0, 1.0, 1.0) for rectangle in rectangles))

    def test_default_layout_rejects_non_linear_edges(self) -> None:
        with self.assertRaisesRegex(ValueError, "线性流程"):
            process_flowchart(["A", "B", "C"], [("A", "B"), ("A", "C")])

    def test_explicit_positions_require_axis_alignment(self) -> None:
        with self.assertRaisesRegex(ValueError, "水平或垂直对齐"):
            process_flowchart(["A", "B"], [("A", "B")], positions={"A": (0.2, 0.2), "B": (0.8, 0.8)})

    def test_crossing_arrows_are_rejected(self) -> None:
        positions = {"A": (0.2, 0.5), "B": (0.8, 0.5), "C": (0.5, 0.8), "D": (0.5, 0.2)}
        with self.assertRaisesRegex(ValueError, "交叉或重叠"):
            process_flowchart(["A", "B", "C", "D"], [("A", "B"), ("C", "D")], positions=positions)

    def test_arrow_through_node_is_rejected(self) -> None:
        positions = {"A": (0.2, 0.5), "B": (0.8, 0.5), "C": (0.5, 0.5)}
        with self.assertRaisesRegex(ValueError, "穿过节点"):
            process_flowchart(["A", "B", "C"], [("A", "B")], positions=positions)


if __name__ == "__main__":
    unittest.main()
