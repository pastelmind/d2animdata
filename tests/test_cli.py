"""Integration tests for the command-line interface."""

import unittest
from io import BytesIO, StringIO
from unittest import mock

from d2animdata import main

# Valid AnimData.D2 with 1 hash record each in the first and second blocks.
VALID_ANIMDATA = (
    # Start of block 0
    b"\x01\x00\x00\x00"  # # of records in block
    # start of record 0 in block 0
    + b"AWS1HTH\x00"  # COF name (hash value == 0)
    + b"\x09\x00\x00\x00"  # frames_per_direction
    + b"\x07\x00\x00\x00"  # animation_speed
    + b"\x03\x02\x01"  # First three frames have trigger codes 3, 2, 1
    + b"\x00" * 141  # All other frames have no trigger code
    # End of record 0 in block 0
    # End of block 0
    # Start of block 1
    + b"\x01\x00\x00\x00"  # # of records in block
    # start of record 0 in block 1
    + b"AXS1HTH\x00"  # COF name (hash value == 1)
    + b"\x00\x01\x00\x00"  # frames_per_direction
    + b"\x00\x01\x00\x00"  # animation_speed
    + b"\x00" * 141  # All other frames have no trigger code
    + b"\x01\x02\x03"  # Last three frames have trigger codes 1, 2, 3
    # End of record 0 in block 1
    # End of block 1
    # All other blocks are empty
    + b"\x00\x00\x00\x00" * 254
)

# Expected result of decompiling VALID_ANIMDATA.
VALID_JSON = """[
  {
    "cof_name": "AWS1HTH",
    "frames_per_direction": 9,
    "animation_speed": 7,
    "triggers": {
      "0": 3,
      "1": 2,
      "2": 1
    }
  },
  {
    "cof_name": "AXS1HTH",
    "frames_per_direction": 256,
    "animation_speed": 256,
    "triggers": {
      "141": 1,
      "142": 2,
      "143": 3
    }
  }
]"""

# Expected result of decompiling VALID_ANIMDATA.
VALID_TXT = (
    # Header row
    "CofName\tFramesPerDirection\tAnimationSpeed\t"
    + "\t".join(f"FrameData{i:03}" for i in range(144))
    + "\r\n"
    # Record 0
    + ("AWS1HTH\t9\t7\t3\t2\t1" + "\t0" * 141 + "\r\n")
    # Record 1
    + ("AXS1HTH\t256\t256" + "\t0" * 141 + "\t1\t2\t3\r\n")
)


class TestCompile(unittest.TestCase):
    """Test case for the `compile` command."""

    @mock.patch("builtins.open", autospec=True)
    def test_compile_txt(self, mock_open: mock.Mock) -> None:
        """Tests compiling tabbed text to AnimData.D2."""
        self.maxDiff = 5000  # pylint: disable=invalid-name

        txt_file = StringIO(VALID_TXT, newline="")
        animdata_d2_file = BytesIO()
        animdata_d2_file.close = mock.Mock(spec=animdata_d2_file.close)
        mock_open.side_effect = [txt_file, animdata_d2_file]

        main("compile --txt AnimData.txt-file-name AnimData.D2-file-name".split())

        mock_open.assert_has_calls(
            [
                mock.call("AnimData.txt-file-name", newline=""),
                mock.call("AnimData.D2-file-name", mode="wb"),
            ]
        )
        animdata_d2_file.close.assert_called_once_with()
        self.assertEqual(animdata_d2_file.getvalue(), VALID_ANIMDATA)

    @mock.patch("builtins.open", autospec=True)
    def test_compile_json(self, mock_open: mock.Mock) -> None:
        """Tests compiling JSON to AnimData.D2."""
        self.maxDiff = 1000

        json_file = StringIO(VALID_JSON)
        animdata_d2_file = BytesIO()
        animdata_d2_file.close = mock.Mock(spec=animdata_d2_file.close)
        mock_open.side_effect = [json_file, animdata_d2_file]

        main("compile --json AnimData.json-file-name AnimData.D2-file-name".split())

        mock_open.assert_has_calls(
            [
                mock.call("AnimData.json-file-name"),
                mock.call("AnimData.D2-file-name", mode="wb"),
            ]
        )
        animdata_d2_file.close.assert_called_once_with()
        self.assertEqual(animdata_d2_file.getvalue(), VALID_ANIMDATA)


class TestDecompile(unittest.TestCase):
    """Test case for the `decompile` command."""

    @mock.patch("builtins.open", autospec=True)
    def test_decompile_txt(self, mock_open: mock.Mock) -> None:
        """Tests decompiling AnimData.D2 to tabbed text."""
        self.maxDiff = 5000  # pylint: disable=invalid-name

        animdata_d2_file = BytesIO(VALID_ANIMDATA)
        txt_file = StringIO()
        txt_file.close = mock.Mock(spec=txt_file.close)
        mock_open.side_effect = [animdata_d2_file, txt_file]

        main("decompile --txt AnimData.D2-file-name AnimData.txt-file-name".split())

        mock_open.assert_has_calls(
            [
                mock.call("AnimData.D2-file-name", mode="rb"),
                mock.call("AnimData.txt-file-name", mode="w", newline=""),
            ]
        )
        txt_file.close.assert_called_once_with()
        self.assertEqual(txt_file.getvalue(), VALID_TXT)

    @mock.patch("builtins.open", autospec=True)
    def test_decompile_json(self, mock_open: mock.Mock) -> None:
        """Tests decompiling AnimData.D2 to JSON."""
        self.maxDiff = 1000

        animdata_d2_file = BytesIO(VALID_ANIMDATA)
        json_file = StringIO()
        json_file.close = mock.Mock(spec=json_file.close)
        mock_open.side_effect = [animdata_d2_file, json_file]

        main("decompile --json AnimData.D2-file-name AnimData.json-file-name".split())

        mock_open.assert_has_calls(
            [
                mock.call("AnimData.D2-file-name", mode="rb"),
                mock.call("AnimData.json-file-name", mode="w"),
            ]
        )
        json_file.close.assert_called_once_with()
        self.assertEqual(json_file.getvalue(), VALID_JSON)
