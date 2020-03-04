"""Unit tests for loading and saving tabbed text files."""

import unittest
from io import StringIO

from d2animdata import ActionTrigger, LoadTxtError, Record, dump_txt, load_txt


# NOTE: csv.writer() always uses '\r\n' as the line separator if the dialect is
# set to 'excel' or 'excel-tab'. See:
#   https://github.com/python/cpython/blob/v3.8.2/Lib/csv.py#L60)
# Thus, we shouldn't try to manually normalize line separators in order to make
# the tests work in different platforms. Just use '\r\n'.


# Valid tabbed text file with 2 AnimData records.
TXT_VALID = (
    # Header row
    "CofName\tFramesPerDirection\tAnimationSpeed\t"
    + "\t".join(f"FrameData{i:03}" for i in range(144))
    + "\r\n"
    # Record 0
    + ("00A1HTH\t5\t256\t0\t1\t2\t3" + "\t0" * 140 + "\r\n")
    # Record 1
    + ("ZZS2HTH\t150\t192" + "\t0" * 141 + "\t3\t2\t1\r\n")
)

# Expected result of load()-ing TXT_VALID. Also, dump()-ing this should
# return a value identical to TXT_VALID.
RECORDS_VALID = [
    Record(
        cof_name="00A1HTH",
        frames_per_direction=5,
        animation_speed=256,
        triggers=[
            ActionTrigger(frame=1, code=1),
            ActionTrigger(frame=2, code=2),
            ActionTrigger(frame=3, code=3),
        ],
    ),
    Record(
        cof_name="ZZS2HTH",
        frames_per_direction=150,
        animation_speed=192,
        triggers=[
            ActionTrigger(frame=141, code=3),
            ActionTrigger(frame=142, code=2),
            ActionTrigger(frame=143, code=1),
        ],
    ),
]


class TestLoadTabbedText(unittest.TestCase):
    """Test case for loading AnimData records from a tabbed text file."""

    def test_valid(self) -> None:
        """Tests if a valid tabbed text file can be loaded correctly."""
        tabbed_txt = StringIO(TXT_VALID, newline="")
        records = load_txt(tabbed_txt)
        self.assertEqual(records, RECORDS_VALID)

    @unittest.expectedFailure
    def test_bad_records(self) -> None:
        """Tests if loading a tabbed text file containing bad records causes an
        error.

        The exception should be a plain Python error, since the text file itself
        is well-formed.
        """
        tabbed_txt_content = (
            # Header row
            "CofName\tFramesPerDirection\tAnimationSpeed\t"
            + "\t".join(f"FrameData{i:03}" for i in range(144))
            + "\r\n"
            # Record 0
            + ("BAD COF NAME\t1\t256\t0\t1\t2\t3" + "\t0" * 140 + "\r\n")
        )
        with self.assertRaises(
            ValueError, msg="Must raise ValueError if COF name is invalid"
        ):
            load_txt(StringIO(tabbed_txt_content, newline=""))

        tabbed_txt_content = (
            # Header row
            "CofName\tFramesPerDirection\tAnimationSpeed\t"
            + "\t".join(f"FrameData{i:03}" for i in range(144))
            + "\r\n"
            # Record 0
            + ("00A1HTH\t-1\t256\t0\t1\t2\t3" + "\t0" * 140 + "\r\n")
        )
        with self.assertRaises(
            ValueError, msg="Must raise ValueError if frames_per_direction is invalid"
        ):
            load_txt(StringIO(tabbed_txt_content, newline=""))

    @unittest.expectedFailure
    def test_missing_columns(self) -> None:
        """Tests if loading fails when a tabbed text file has missing columns."""
        tabbed_txt_content = (
            # Header row
            "CofName\tFramesPerDirection\tAnimationSpeed\t"
            + "\t".join(f"FrameData{i:03}" for i in range(143))
            + "\r\n"
            # Record 0
            + ("00A1HTH\t1\t256\t0\t1\t2\t3" + "\t0" * 140 + "\r\n")
        )
        with self.assertRaises(LoadTxtError):
            load_txt(StringIO(tabbed_txt_content, newline=""))

    @unittest.expectedFailure
    def test_missing_fields(self) -> None:
        """Tests if loading fails when a tabbed text file has missing fields."""
        tabbed_txt_content = (
            # Header row
            "CofName\tFramesPerDirection\tAnimationSpeed\t"
            + "\t".join(f"FrameData{i:03}" for i in range(144))
            + "\r\n"
            # Record 0
            + ("00A1HTH\t1\t256\t0\t1\t2\t3\r\n")
        )
        with self.assertRaises(LoadTxtError):
            load_txt(StringIO(tabbed_txt_content, newline=""))

    @unittest.expectedFailure
    def test_invalid_format(self) -> None:
        """Tests if loading fails when a tabbed text file cannot be parsed."""
        tabbed_txt = StringIO("This isn't a tabbed text file!", newline="")
        with self.assertRaises(LoadTxtError):
            load_txt(tabbed_txt)


class TestDumpTabbedText(unittest.TestCase):
    """Test case for saving AnimData records to a tabbed text file."""

    def test_valid(self) -> None:
        """Tests if records can be correctly dumped to a tabbed text file."""
        tabbed_txt = StringIO(newline="")
        dump_txt(RECORDS_VALID, tabbed_txt)
        self.assertEqual(tabbed_txt.getvalue(), TXT_VALID)

    # No need to test dumping invalid values, since Record() takes care of basic
    # value checks.
