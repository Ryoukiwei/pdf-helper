import unittest

from pdf_img_tool.crop_core import rotate_crop_box
from pdf_img_tool.models import CropBox


class SelectionRotationMathTests(unittest.TestCase):
    def test_ccw_90_formula(self) -> None:
        # old size (W,H) = (100,80), bbox=(10,20,30,50)
        # ccw: (y0, W-x1, y1, W-x0)
        box = CropBox(left=10, top=20, right=30, bottom=50)
        rotated = rotate_crop_box(box, width=100, height=80, rotation="left")
        self.assertEqual(
            (rotated.left, rotated.top, rotated.right, rotated.bottom), (20, 70, 50, 90)
        )

    def test_cw_90_formula(self) -> None:
        # old size (W,H) = (100,80), bbox=(10,20,30,50)
        # cw: (H-y1, x0, H-y0, x1)
        box = CropBox(left=10, top=20, right=30, bottom=50)
        rotated = rotate_crop_box(box, width=100, height=80, rotation="right")
        self.assertEqual(
            (rotated.left, rotated.top, rotated.right, rotated.bottom), (30, 10, 60, 30)
        )

    def test_rotate_180_formula(self) -> None:
        # old size (W,H) = (100,80), bbox=(10,20,30,50)
        # 180: (W-x1, H-y1, W-x0, H-y0)
        box = CropBox(left=10, top=20, right=30, bottom=50)
        rotated = rotate_crop_box(box, width=100, height=80, rotation="half")
        self.assertEqual(
            (rotated.left, rotated.top, rotated.right, rotated.bottom), (70, 30, 90, 60)
        )

    def test_four_ccw_rotations_return_original(self) -> None:
        original = CropBox(left=7, top=11, right=44, bottom=65)
        w, h = 90, 140

        current = original
        for _ in range(4):
            current = rotate_crop_box(current, width=w, height=h, rotation="left")
            w, h = h, w

        self.assertEqual(current.normalized(), original.normalized())

    def test_four_cw_rotations_return_original(self) -> None:
        original = CropBox(left=3, top=5, right=20, bottom=41)
        w, h = 60, 70

        current = original
        for _ in range(4):
            current = rotate_crop_box(current, width=w, height=h, rotation="right")
            w, h = h, w

        self.assertEqual(current.normalized(), original.normalized())

    def test_border_aligned_box_stays_in_bounds_after_ccw(self) -> None:
        # touches left/top borders on old image
        box = CropBox(left=0, top=0, right=25, bottom=40)
        old_w, old_h = 120, 80

        rotated = rotate_crop_box(box, width=old_w, height=old_h, rotation="left")
        new_w, new_h = old_h, old_w

        self.assertGreaterEqual(rotated.left, 0)
        self.assertGreaterEqual(rotated.top, 0)
        self.assertLessEqual(rotated.right, new_w)
        self.assertLessEqual(rotated.bottom, new_h)
        self.assertTrue(rotated.is_valid())

    def test_border_aligned_box_stays_in_bounds_after_cw(self) -> None:
        # touches right/bottom borders on old image
        box = CropBox(left=30, top=10, right=120, bottom=80)
        old_w, old_h = 120, 80

        rotated = rotate_crop_box(box, width=old_w, height=old_h, rotation="right")
        new_w, new_h = old_h, old_w

        self.assertGreaterEqual(rotated.left, 0)
        self.assertGreaterEqual(rotated.top, 0)
        self.assertLessEqual(rotated.right, new_w)
        self.assertLessEqual(rotated.bottom, new_h)
        self.assertTrue(rotated.is_valid())


if __name__ == "__main__":
    unittest.main()
