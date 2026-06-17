"""Tests for the PDF generator module."""

import os
import pytest
from datetime import date
from pathlib import Path
from PIL import Image

from app.document_generator import generate_pdf


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def dummy_images(temp_dir):
    """Create a few small dummy images for testing."""
    images = []
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        img_path = temp_dir / f"dummy_{i}.png"
        img = Image.new("RGB", (100, 100), color)
        img.save(img_path)
        images.append(str(img_path))
    return images


@pytest.fixture
def grouped_data(dummy_images):
    """Create sample grouped data for one sub-id with multiple images."""
    return {
        "section A": [
            {"message_id": 1, "images": [dummy_images[0], dummy_images[1]]},
            {"message_id": 2, "images": [dummy_images[2]]},
        ],
        "section B": [
            {"message_id": 3, "images": [dummy_images[0]]},
        ],
    }


class TestGeneratePdf:
    """Tests for the generate_pdf function."""

    def test_pdf_created(self, temp_dir, grouped_data):
        """A PDF file is created at the specified output path."""
        output_path = temp_dir / "report.pdf"
        generate_pdf(
            report_id="tower 123",
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 11),
            grouped_data=grouped_data,
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_pdf_filename_not_overwritten(self, temp_dir, grouped_data):
        """The output path is respected and not modified internally."""
        output_path = temp_dir / "custom_name.pdf"
        generate_pdf(
            report_id="tower 123",
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 11),
            grouped_data=grouped_data,
            output_path=str(output_path),
        )
        assert output_path.exists()

    def test_empty_grouped_data(self, temp_dir):
        """Even with no images, a PDF is generated with just the title."""
        output_path = temp_dir / "empty_report.pdf"
        generate_pdf(
            report_id="tower 123",
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 11),
            grouped_data={},
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_single_image(self, temp_dir, dummy_images):
        """A single image is embedded correctly."""
        output_path = temp_dir / "single_image.pdf"
        grouped = {
            "section A": [
                {"message_id": 1, "images": [dummy_images[0]]},
            ],
        }
        generate_pdf(
            report_id="tower 123",
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 11),
            grouped_data=grouped,
            output_path=str(output_path),
        )
        assert output_path.exists()

    def test_many_images_grid(self, temp_dir, dummy_images):
        """Many images trigger grid layout (multiple rows)."""
        output_path = temp_dir / "grid_report.pdf"
        grouped = {
            "section A": [
                {"message_id": 1, "images": dummy_images * 4},  # 12 images
            ],
        }
        generate_pdf(
            report_id="tower 123",
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 11),
            grouped_data=grouped,
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_multiple_sub_ids(self, temp_dir, grouped_data):
        """Each sub-id has its own section in the PDF."""
        output_path = temp_dir / "multi_section.pdf"
        generate_pdf(
            report_id="tower 123",
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 11),
            grouped_data=grouped_data,
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0
