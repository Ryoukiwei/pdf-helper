import tempfile
import unittest
from pathlib import Path

from pdf_img_tool.crop import (
    OutputRules,
    build_output_path,
    plan_crop_jobs_from_manifest_payload,
    pre_crop_skip_reason,
)


class CropPlanningTests(unittest.TestCase):
    def test_build_output_path_applies_format_and_subdir(self) -> None:
        rules = OutputRules(
            output_format="png",
            jpeg_quality=90,
            overwrite=False,
            out_subdir="cropped",
        )
        output_path = build_output_path(Path("/tmp/input/photo.jpg"), Path("/tmp/out"), rules)
        self.assertEqual(output_path, Path("/tmp/out/cropped/photo__crop.png"))

    def test_skip_reason_checks_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            input_path = tmp_dir / "page.png"
            output_path = tmp_dir / "page__crop.png"
            input_path.write_bytes(b"x")
            output_path.write_bytes(b"y")
            reason = pre_crop_skip_reason(input_path, output_path, overwrite=False)
            self.assertEqual(reason, "output exists and --no-overwrite is active")

    def test_manifest_source_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            extracted_path = tmp_dir / "a.png"
            rendered_path = tmp_dir / "b.png"
            extracted_path.write_bytes(b"x")
            rendered_path.write_bytes(b"x")

            payload: dict[str, object] = {
                "out_dir": str(tmp_dir),
                "items": [
                    {
                        "extracted_images": ["a.png"],
                        "rendered": "b.png",
                    }
                ],
            }

            rules = OutputRules(
                output_format=None,
                jpeg_quality=90,
                overwrite=False,
                out_subdir="",
            )

            extracted_jobs = plan_crop_jobs_from_manifest_payload(
                payload,
                manifest_path=tmp_dir / "manifest.json",
                out_dir=tmp_dir,
                source="extracted",
                output_rules=rules,
            )
            self.assertEqual(len(extracted_jobs), 1)
            self.assertEqual(extracted_jobs[0].input_path, extracted_path.resolve())

            rendered_jobs = plan_crop_jobs_from_manifest_payload(
                payload,
                manifest_path=tmp_dir / "manifest.json",
                out_dir=tmp_dir,
                source="rendered",
                output_rules=rules,
            )
            self.assertEqual(len(rendered_jobs), 1)
            self.assertEqual(rendered_jobs[0].input_path, rendered_path.resolve())


if __name__ == "__main__":
    unittest.main()
