import unittest

from PIL import Image, ImageDraw

from pdf_img_tool.crop_core import auto_trim_bbox, rotate_crop_box
from pdf_img_tool.models import CropBox


class AutoTrimBBoxTests(unittest.TestCase):
    def test_returns_none_for_blank_page(self) -> None:
        image = Image.new("RGB", (120, 80), "white")
        bbox = auto_trim_bbox(image, threshold=245, padding=10)
        self.assertIsNone(bbox)

    def test_detects_content_with_padding(self) -> None:
        image = Image.new("RGB", (100, 100), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 30, 79, 89), fill="black")

        bbox = auto_trim_bbox(image, threshold=245, padding=5)
        self.assertIsNotNone(bbox)
        assert bbox is not None
        self.assertEqual((bbox.left, bbox.top, bbox.right, bbox.bottom), (15, 25, 85, 95))


class RotateCropBoxTests(unittest.TestCase):
    def test_rotate_left_uses_old_size(self) -> None:
        box = CropBox(left=10, top=20, right=30, bottom=50)
        rotated = rotate_crop_box(box, width=100, height=80, rotation="left")
        self.assertEqual(
            (rotated.left, rotated.top, rotated.right, rotated.bottom), (20, 70, 50, 90)
        )

    def test_rotate_right_uses_old_size(self) -> None:
        box = CropBox(left=10, top=20, right=30, bottom=50)
        rotated = rotate_crop_box(box, width=100, height=80, rotation="right")
        self.assertEqual(
            (rotated.left, rotated.top, rotated.right, rotated.bottom), (30, 10, 60, 30)
        )

    def test_rotate_half(self) -> None:
        box = CropBox(left=10, top=20, right=30, bottom=50)
        rotated = rotate_crop_box(box, width=100, height=80, rotation="half")
        self.assertEqual(
            (rotated.left, rotated.top, rotated.right, rotated.bottom), (70, 30, 90, 60)
        )


if __name__ == "__main__":
    unittest.main()
