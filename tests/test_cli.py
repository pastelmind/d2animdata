"""Integration tests for the command-line interface."""

import logging
import unittest
from io import BytesIO, StringIO
from unittest import mock

import d2animdata
from d2animdata import main

from .valid_data import VALID_ANIMDATA, VALID_JSON, VALID_TXT

# AnimData.D2 with two records that have the same COF name.
# This decompiles to DUPLICATE_COF_JSON with warnings.
DUPLICATE_COF_ANIMDATA = (
    # Start of block 0
    b"\x02\x00\x00\x00"  # # of records in block
    # start of record 0 in block 0
    + b"BVS1HTH\x00"  # COF name (hash value == 0)
    + b"\x09\x00\x00\x00"  # frames_per_direction
    + b"\x07\x00\x00\x00"  # animation_speed
    + b"\x00\x03\x02\x01"  # First four frames have trigger codes 0, 3, 2, 1
    + b"\x00" * 140  # All other frames have no trigger code
    # End of record 0 in block 0
    # start of record 1 in block 0
    + b"BVS1HTH\x00"  # COF name (hash value == 0)
    + b"\x11\x00\x00\x00"  # frames_per_direction
    + b"\x20\x00\x00\x00"  # animation_speed
    + b"\x00" * 144  # All frames have no trigger code
    # End of record 1 in block 0
    # End of block 0
    # All other blocks are empty
    + b"\x00\x00\x00\x00" * 255
)

# Deduplicated version of DUPLICATE_COF_ANIMDATA.
DEDUPED_ANIMDATA = (
    # Start of block 0
    b"\x01\x00\x00\x00"  # # of records in block
    # start of record 0 in block 0
    + b"BVS1HTH\x00"  # COF name (hash value == 0)
    + b"\x09\x00\x00\x00"  # frames_per_direction
    + b"\x07\x00\x00\x00"  # animation_speed
    + b"\x00\x03\x02\x01"  # First four frames have trigger codes 0, 3, 2, 1
    + b"\x00" * 140  # All other frames have no trigger code
    # End of record 0 in block 0
    # End of block 0
    # All other blocks are empty
    + b"\x00\x00\x00\x00" * 255
)

# Expected result of decompiling DUPLICATE_COF_ANIMDATA.
# This compiles to DUPLICATE_COF_ANIMDATA with warnings.
DUPLICATE_COF_JSON = """[
  {
    "cof_name": "BVS1HTH",
    "frames_per_direction": 9,
    "animation_speed": 7,
    "triggers": {
      "1": 3,
      "2": 2,
      "3": 1
    }
  },
  {
    "cof_name": "BVS1HTH",
    "frames_per_direction": 17,
    "animation_speed": 32,
    "triggers": {}
  }
]"""

# Deduplicated version of DUPLICATE_COF_JSON.
DEDUPED_JSON = """[
  {
    "cof_name": "BVS1HTH",
    "frames_per_direction": 9,
    "animation_speed": 7,
    "triggers": {
      "1": 3,
      "2": 2,
      "3": 1
    }
  }
]"""


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

    @mock.patch("builtins.open", autospec=True)
    def test_compile_no_dedupe(self, mock_open: mock.Mock) -> None:
        """By default, records with duplicate COF names cause warnings to be
        logged, but are not deduplicated."""
        json_file = StringIO(DUPLICATE_COF_JSON)
        animdata_d2_file = BytesIO()
        animdata_d2_file.close = mock.Mock(spec=animdata_d2_file.close)
        mock_open.side_effect = [json_file, animdata_d2_file]

        with self.assertLogs(d2animdata.logger, logging.WARNING) as logs:
            main("compile --json AnimData.json-file AnimData.D2-file".split())
        self.assertEqual(
            logs.output, ["WARNING:d2animdata:Duplicate entry found: BVS1HTH"]
        )

        mock_open.assert_has_calls(
            [mock.call("AnimData.json-file"), mock.call("AnimData.D2-file", mode="wb"),]
        )
        animdata_d2_file.close.assert_called_once_with()
        self.assertEqual(animdata_d2_file.getvalue(), DUPLICATE_COF_ANIMDATA)

    @mock.patch("builtins.open", autospec=True)
    def test_compile_dedupe(self, mock_open: mock.Mock) -> None:
        """Specifying --dedupe causes records with duplicate COF names to be
        deduplicated, always favoring the first item."""
        json_file = StringIO(DUPLICATE_COF_JSON)
        animdata_d2_file = BytesIO()
        animdata_d2_file.close = mock.Mock(spec=animdata_d2_file.close)
        mock_open.side_effect = [json_file, animdata_d2_file]

        with self.assertLogs(d2animdata.logger, logging.WARNING) as logs:
            main("compile --json --dedupe AnimData.json-file AnimData.D2-file".split())
        self.assertEqual(
            logs.output, ["WARNING:d2animdata:Duplicate entry found: BVS1HTH"]
        )

        mock_open.assert_has_calls(
            [mock.call("AnimData.json-file"), mock.call("AnimData.D2-file", mode="wb"),]
        )
        animdata_d2_file.close.assert_called_once_with()
        self.assertEqual(animdata_d2_file.getvalue(), DEDUPED_ANIMDATA)


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

    @mock.patch("builtins.open", autospec=True)
    def test_compile_no_dedupe(self, mock_open: mock.Mock) -> None:
        """By default, records with duplicate COF names cause warnings to be
        logged, but are not deduplicated."""
        animdata_d2_file = BytesIO(DUPLICATE_COF_ANIMDATA)
        json_file = StringIO()
        json_file.close = mock.Mock(spec=json_file.close)
        mock_open.side_effect = [animdata_d2_file, json_file]

        with self.assertLogs(d2animdata.logger, logging.WARNING) as logs:
            main("decompile --json AnimData.D2-file AnimData.json-file".split())
        self.assertEqual(
            logs.output, ["WARNING:d2animdata:Duplicate entry found: BVS1HTH"]
        )

        mock_open.assert_has_calls(
            [
                mock.call("AnimData.D2-file", mode="rb"),
                mock.call("AnimData.json-file", mode="w"),
            ]
        )
        json_file.close.assert_called_once_with()
        self.assertEqual(json_file.getvalue(), DUPLICATE_COF_JSON)

    @mock.patch("builtins.open", autospec=True)
    def test_compile_dedupe(self, mock_open: mock.Mock) -> None:
        """Specifying --dedupe causes records with duplicate COF names to be
        deduplicated, always favoring the first item."""
        animdata_d2_file = BytesIO(DUPLICATE_COF_ANIMDATA)
        json_file = StringIO()
        json_file.close = mock.Mock(spec=json_file.close)
        mock_open.side_effect = [animdata_d2_file, json_file]

        with self.assertLogs(d2animdata.logger, logging.WARNING) as logs:
            main(
                "decompile --json --dedupe AnimData.D2-file AnimData.json-file".split()
            )
        self.assertEqual(
            logs.output, ["WARNING:d2animdata:Duplicate entry found: BVS1HTH"]
        )

        mock_open.assert_has_calls(
            [
                mock.call("AnimData.D2-file", mode="rb"),
                mock.call("AnimData.json-file", mode="w"),
            ]
        )
        json_file.close.assert_called_once_with()
        self.assertEqual(json_file.getvalue(), DEDUPED_JSON)
