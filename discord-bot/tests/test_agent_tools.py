"""Tests for the agent tools module."""

import json
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent_tools import process_and_filter_messages, retrieve_messages


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def sample_messages():
    """Create sample message dicts with image attachments."""
    return [
        {
            "message_id": 1,
            "attachments": [
                {
                    "id": 1001,
                    "filename": "img1.png",
                    "url": "http://example.com/img1.png",
                    "content_type": "image/png",
                }
            ],
        },
        {
            "message_id": 2,
            "attachments": [
                {
                    "id": 1002,
                    "filename": "img2.png",
                    "url": "http://example.com/img2.png",
                    "content_type": "image/png",
                },
                {
                    "id": 1003,
                    "filename": "img3.png",
                    "url": "http://example.com/img3.png",
                    "content_type": "image/png",
                },
            ],
        },
        {
            "message_id": 3,
            "attachments": [],
        },
    ]


@pytest.mark.asyncio
async def test_retrieve_messages_writes_file(temp_dir):
    """retrieve_messages writes stripped messages to a file and returns file_path."""
    # Create mock messages
    mock_msg1 = MagicMock()
    mock_msg1.id = 1
    mock_att1 = MagicMock()
    mock_att1.id = 1001
    mock_att1.filename = "img1.png"
    mock_att1.url = "http://example.com/img1.png"
    mock_att1.content_type = "image/png"
    mock_msg1.attachments = [mock_att1]

    mock_msg2 = MagicMock()
    mock_msg2.id = 2
    mock_msg2.attachments = []

    mock_channel = MagicMock()

    with patch("app.agent_tools.fetch_messages_in_range", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [mock_msg1, mock_msg2]
        with patch("app.agent_tools.gmt7_to_utc_range", return_value=(None, None)):
            result = await retrieve_messages(
                date(2026, 6, 10),
                date(2026, 6, 10),
                mock_channel,
                temp_dir,
            )

    assert "file_path" in result
    assert "message_count" in result
    assert result["message_count"] == 2

    # Verify file was written
    file_path = temp_dir / result["file_path"]
    assert file_path.exists()

    # Verify stripped content (no author, content, timestamp)
    with open(file_path, "r") as f:
        data = json.load(f)
    assert len(data) == 2
    assert "message_id" in data[0]
    assert "attachments" in data[0]
    assert "author" not in data[0]
    assert "content" not in data[0]
    assert "timestamp" not in data[0]


@pytest.mark.asyncio
async def test_process_and_filter_messages_reads_from_file(temp_dir, sample_messages):
    """process_and_filter_messages reads messages from file paths."""
    from app.image_metadata_extractor import NormalizedImageMetadata

    # Write sample messages to a file
    file_path = temp_dir / "messages_2026-06-10_2026-06-10.json"
    with open(file_path, "w") as f:
        json.dump(sample_messages, f)

    fake_paths = [str(temp_dir / f"fake_{i}.png") for i in range(3)]
    for fp in fake_paths:
        Path(fp).write_bytes(b"fake")

    async def fake_download(msg, td):
        if msg.id == 1:
            return [fake_paths[0]]
        elif msg.id == 2:
            return [fake_paths[1], fake_paths[2]]
        return []

    metadata_map = {
        fake_paths[0]: NormalizedImageMetadata(
            tower_id="Tower 123",
            sub_id="Section atas",
            report_date=date(2026, 6, 10),
            roadway="Jalur Jakarta - Bandung",
            raw_text="",
        ),
        fake_paths[1]: NormalizedImageMetadata(
            tower_id="Tower 123",
            sub_id="Section bawah",
            report_date=date(2026, 6, 10),
            roadway="Jalur Jakarta - Bandung",
            raw_text="",
        ),
        fake_paths[2]: NormalizedImageMetadata(
            tower_id="Tower 345",
            sub_id="Section tengah",
            report_date=date(2026, 6, 11),
            roadway="Jalur Jakarta - Surabaya",
            raw_text="",
        ),
    }

    async def fake_extract(img_path):
        return metadata_map.get(str(img_path))

    with patch("app.agent_tools.download_message_images", side_effect=fake_download):
        with patch("app.agent_tools.extract_image_metadata", side_effect=fake_extract):
            result = await process_and_filter_messages(
                json.dumps(["messages_2026-06-10_2026-06-10.json"]),
                tower_numbers=None,
                roadways=None,
                temp_dir=temp_dir,
            )

    assert len(result) == 3
    tower_ids = {r["tower_id"] for r in result}
    assert tower_ids == {"Tower 123", "Tower 345"}


@pytest.mark.asyncio
async def test_process_and_filter_messages_filter_by_tower(temp_dir, sample_messages):
    """Filter results by tower number."""
    from app.image_metadata_extractor import NormalizedImageMetadata

    file_path = temp_dir / "messages_2026-06-10_2026-06-10.json"
    with open(file_path, "w") as f:
        json.dump(sample_messages, f)

    fake_paths = [str(temp_dir / f"fake_{i}.png") for i in range(3)]
    for fp in fake_paths:
        Path(fp).write_bytes(b"fake")

    async def fake_download(msg, td):
        if msg.id == 1:
            return [fake_paths[0]]
        elif msg.id == 2:
            return [fake_paths[1], fake_paths[2]]
        return []

    metadata_map = {
        fake_paths[0]: NormalizedImageMetadata(
            tower_id="Tower 123",
            sub_id="Section atas",
            report_date=date(2026, 6, 10),
            raw_text="",
        ),
        fake_paths[1]: NormalizedImageMetadata(
            tower_id="Tower 123",
            sub_id="Section bawah",
            report_date=date(2026, 6, 10),
            raw_text="",
        ),
        fake_paths[2]: NormalizedImageMetadata(
            tower_id="Tower 345",
            sub_id="Section tengah",
            report_date=date(2026, 6, 11),
            raw_text="",
        ),
    }

    async def fake_extract(img_path):
        return metadata_map.get(str(img_path))

    with patch("app.agent_tools.download_message_images", side_effect=fake_download):
        with patch("app.agent_tools.extract_image_metadata", side_effect=fake_extract):
            result = await process_and_filter_messages(
                json.dumps(["messages_2026-06-10_2026-06-10.json"]),
                tower_numbers=["Tower 123"],
                roadways=None,
                temp_dir=temp_dir,
            )

    assert len(result) == 2
    assert all(r["tower_id"] == "Tower 123" for r in result)


@pytest.mark.asyncio
async def test_process_and_filter_messages_filter_by_roadway(temp_dir, sample_messages):
    """Filter results by roadway."""
    from app.image_metadata_extractor import NormalizedImageMetadata

    file_path = temp_dir / "messages_2026-06-10_2026-06-10.json"
    with open(file_path, "w") as f:
        json.dump(sample_messages, f)

    fake_paths = [str(temp_dir / f"fake_{i}.png") for i in range(3)]
    for fp in fake_paths:
        Path(fp).write_bytes(b"fake")

    async def fake_download(msg, td):
        if msg.id == 1:
            return [fake_paths[0]]
        elif msg.id == 2:
            return [fake_paths[1], fake_paths[2]]
        return []

    metadata_map = {
        fake_paths[0]: NormalizedImageMetadata(
            tower_id="Tower 123",
            sub_id="Section atas",
            report_date=date(2026, 6, 10),
            roadway="Jalur Jakarta - Bandung",
            raw_text="",
        ),
        fake_paths[1]: NormalizedImageMetadata(
            tower_id="Tower 123",
            sub_id="Section bawah",
            report_date=date(2026, 6, 10),
            roadway="Jalur Jakarta - Bandung",
            raw_text="",
        ),
        fake_paths[2]: NormalizedImageMetadata(
            tower_id="Tower 345",
            sub_id="Section tengah",
            report_date=date(2026, 6, 11),
            roadway="Jalur Jakarta - Surabaya",
            raw_text="",
        ),
    }

    async def fake_extract(img_path):
        return metadata_map.get(str(img_path))

    with patch("app.agent_tools.download_message_images", side_effect=fake_download):
        with patch("app.agent_tools.extract_image_metadata", side_effect=fake_extract):
            result = await process_and_filter_messages(
                json.dumps(["messages_2026-06-10_2026-06-10.json"]),
                tower_numbers=None,
                roadways=["Jalur Jakarta - Bandung"],
                temp_dir=temp_dir,
            )

    assert len(result) == 2
    assert all(r["roadway"] == "Jalur Jakarta - Bandung" for r in result)


@pytest.mark.asyncio
async def test_process_and_filter_messages_skip_no_roadway_when_filtering(temp_dir, sample_messages):
    """Images without roadway metadata are skipped when roadway filter is active."""
    from app.image_metadata_extractor import NormalizedImageMetadata

    file_path = temp_dir / "messages_2026-06-10_2026-06-10.json"
    with open(file_path, "w") as f:
        json.dump(sample_messages[:2], f)

    fake_paths = [str(temp_dir / f"fake_{i}.png") for i in range(2)]
    for fp in fake_paths:
        Path(fp).write_bytes(b"fake")

    async def fake_download(msg, td):
        if msg.id == 1:
            return [fake_paths[0]]
        elif msg.id == 2:
            return [fake_paths[1]]
        return []

    metadata_map = {
        fake_paths[0]: NormalizedImageMetadata(
            tower_id="Tower 123",
            sub_id="Section atas",
            report_date=date(2026, 6, 10),
            roadway=None,
            raw_text="",
        ),
        fake_paths[1]: NormalizedImageMetadata(
            tower_id="Tower 123",
            sub_id="Section bawah",
            report_date=date(2026, 6, 10),
            roadway="Jalur Jakarta - Bandung",
            raw_text="",
        ),
    }

    async def fake_extract(img_path):
        return metadata_map.get(str(img_path))

    with patch("app.agent_tools.download_message_images", side_effect=fake_download):
        with patch("app.agent_tools.extract_image_metadata", side_effect=fake_extract):
            result = await process_and_filter_messages(
                json.dumps(["messages_2026-06-10_2026-06-10.json"]),
                tower_numbers=None,
                roadways=["Jalur Jakarta - Bandung"],
                temp_dir=temp_dir,
            )

    assert len(result) == 1
    assert result[0]["roadway"] == "Jalur Jakarta - Bandung"


@pytest.mark.asyncio
async def test_process_and_filter_messages_empty_messages(temp_dir):
    """Empty message list returns empty results."""
    result = await process_and_filter_messages(
        json.dumps([]),
        tower_numbers=None,
        roadways=None,
        temp_dir=temp_dir,
    )
    assert result == []


@pytest.mark.asyncio
async def test_process_and_filter_messages_no_valid_images(temp_dir, sample_messages):
    """When all images fail metadata extraction, return empty results."""
    file_path = temp_dir / "messages_2026-06-10_2026-06-10.json"
    with open(file_path, "w") as f:
        json.dump(sample_messages, f)

    fake_paths = [str(temp_dir / f"fake_{i}.png") for i in range(3)]
    for fp in fake_paths:
        Path(fp).write_bytes(b"fake")

    async def fake_download(msg, td):
        if msg.id == 1:
            return [fake_paths[0]]
        elif msg.id == 2:
            return [fake_paths[1], fake_paths[2]]
        return []

    async def fake_extract(img_path):
        return None

    with patch("app.agent_tools.download_message_images", side_effect=fake_download):
        with patch("app.agent_tools.extract_image_metadata", side_effect=fake_extract):
            result = await process_and_filter_messages(
                json.dumps(["messages_2026-06-10_2026-06-10.json"]),
                tower_numbers=None,
                roadways=None,
                temp_dir=temp_dir,
            )

    assert result == []


@pytest.mark.asyncio
async def test_process_and_filter_messages_handles_missing_file(temp_dir):
    """Missing files are skipped gracefully."""
    result = await process_and_filter_messages(
        json.dumps(["nonexistent_file.json"]),
        tower_numbers=None,
        roadways=None,
        temp_dir=temp_dir,
    )
    assert result == []


@pytest.mark.asyncio
async def test_process_and_filter_messages_batches_correctly(temp_dir):
    """Messages are processed in batches of 50."""
    from app.image_metadata_extractor import NormalizedImageMetadata

    # Create 120 messages (should be 3 batches: 50 + 50 + 20)
    messages = []
    for i in range(120):
        messages.append({
            "message_id": i + 1,
            "attachments": [
                {
                    "id": 1000 + i,
                    "filename": f"img{i}.png",
                    "url": f"http://example.com/img{i}.png",
                    "content_type": "image/png",
                }
            ],
        })

    file_path = temp_dir / "messages_2026-06-10_2026-06-10.json"
    with open(file_path, "w") as f:
        json.dump(messages, f)

    # Create fake image files
    fake_paths = [str(temp_dir / f"fake_{i}.png") for i in range(120)]
    for fp in fake_paths:
        Path(fp).write_bytes(b"fake")

    async def fake_download(msg, td):
        idx = msg.id - 1
        return [fake_paths[idx]]

    async def fake_extract(img_path):
        idx = int(Path(img_path).stem.split("_")[1])
        return NormalizedImageMetadata(
            tower_id=f"Tower {idx % 5 + 100}",
            sub_id="Section atas",
            report_date=date(2026, 6, 10),
            raw_text="",
        )

    with patch("app.agent_tools.download_message_images", side_effect=fake_download):
        with patch("app.agent_tools.extract_image_metadata", side_effect=fake_extract):
            result = await process_and_filter_messages(
                json.dumps(["messages_2026-06-10_2026-06-10.json"]),
                tower_numbers=None,
                roadways=None,
                temp_dir=temp_dir,
            )

    assert len(result) == 120
