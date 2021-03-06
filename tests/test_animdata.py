"""Unit tests for loading and saving AnimData.D2 files."""

import unittest
from io import BytesIO
from typing import Iterable, List

import d2animdata
from d2animdata import AnimDataError, Record

from .valid_data import VALID_ANIMDATA, VALID_RECORDS

# Invalid AnimData.D2 with a record whose hash does not match the block index
ANIMDATA_BAD_HASH = (
    # Start of block 0
    b"\x01\x00\x00\x00"  # # of records in block
    # start of record 0 in block 0
    + b"AXS1HTH\x00"  # COF name (hash value == 1)
    + b"\x09\x00\x00\x00"  # frames_per_direction
    + b"\x07\x00\x00\x00"  # animation_speed
    + b"\x00" * 144  # No trigger codes in any frames
    # End of record 0 in block 0
    # End of block 0
    # All other blocks are empty
    + b"\x00\x00\x00\x00" * 255
)

# Invalid AnimData.D2 with a block that has the wrong record count
ANIMDATA_BAD_RECORD_COUNT = (
    # Start of block 0
    b"\x02\x00\x00\x00"  # # of records in block (intentionally wrong)
    # start of record 0 in block 0
    + b"AWS1HTH\x00"  # COF name (hash value == 0)
    + b"\x09\x00\x00\x00"  # frames_per_direction
    + b"\x07\x00\x00\x00"  # animation_speed
    + b"\x00" * 144  # No trigger codes in any frames
    # End of record 0 in block 0
    # End of block 0
    # All other blocks are empty
    + b"\x00\x00\x00\x00" * 255
)

# Well-formatted AnimData.D2 with unexpected extra data
ANIMDATA_EXTRA_DATA = VALID_ANIMDATA + b"\x00"


class TestLoadAnimData(unittest.TestCase):
    """Test case for loading raw AnimData.D2 data with loads()."""

    maxDiff = 1200

    # Use inheritance to avoid duplicating test code for load() and loads()
    @staticmethod
    def loads(data: bytes) -> List[Record]:
        """Wrapper for d2animdata.loads()."""
        return d2animdata.loads(data)

    def test_valid(self) -> None:
        """Tests if a valid AnimData.D2 file can be loaded correctly."""
        records = self.loads(VALID_ANIMDATA)
        self.assertEqual(records, VALID_RECORDS)

    def test_empty(self) -> None:
        """Tests if loading an empty file fails."""
        with self.assertRaises(AnimDataError):
            self.loads(b"")

    def test_hash_mismatch(self) -> None:
        """Tests if loading fails when a record's hash does not match the index
        of its containing block."""
        with self.assertRaises(AnimDataError):
            self.loads(ANIMDATA_BAD_HASH)

    def test_bad_record_count(self) -> None:
        """Tests if loading fails when a block's record count is invalid."""
        with self.assertRaises(AnimDataError):
            self.loads(ANIMDATA_BAD_RECORD_COUNT)

    def test_extra_data(self) -> None:
        """Tests if loading fails when the file contains extra bytes."""
        with self.assertRaises(AnimDataError):
            self.loads(ANIMDATA_EXTRA_DATA)


class TestLoadFile(TestLoadAnimData):
    """Test case for loading an AnimData.D2 file with load()."""

    @staticmethod
    def loads(data: bytes) -> bytes:
        """Wrapper for d2animdata.load()."""
        animdata_file = BytesIO(data)
        return d2animdata.load(animdata_file)


class TestDumpAnimData(unittest.TestCase):
    """Test case for dumping AnimData.D2 data with dumps()."""

    maxDiff = 1200

    # Use inheritance to avoid duplicating test code for dump() and dumps()
    @staticmethod
    def dumps(records: Iterable[Record]) -> bytes:
        """Wrapper for d2animdata.dumps()."""
        return bytes(d2animdata.dumps(records))

    def test_dump(self):
        """Tests if valid Records can be correctly dumped to an AnimData.D2 file."""
        animdata_raw = self.dumps(VALID_RECORDS)
        self.assertEqual(animdata_raw, VALID_ANIMDATA)

    # No need to test dumping invalid values, since Record() takes care of basic
    # value checks.


class TestDumpFile(unittest.TestCase):
    """Test case for dumping an AnimData.D2 file with dump()."""

    @staticmethod
    def dumps(records: Iterable[Record]) -> bytes:
        """Wrapper for d2animdata.dump()."""
        animdata_file = BytesIO()
        d2animdata.dump(records, animdata_file)
        return animdata_file.getvalue()
