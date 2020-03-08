"""Integration tests for the command-line interface."""

import unittest
from io import BytesIO, StringIO
from unittest import mock

from d2animdata import main

from .valid_data import VALID_ANIMDATA, VALID_JSON, VALID_TXT


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
