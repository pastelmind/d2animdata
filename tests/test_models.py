"""Unit tests for model classes."""

import unittest

from d2animdata import ActionTriggers, Record


class TestRecord(unittest.TestCase):
    """Test case for the d2animdata.Record class."""

    def setUp(self) -> None:
        """Setup for tests that manipulate already-created objects."""
        # This will fail if the constructor fails to accept valid values.
        self.record = Record(
            cof_name="AAA1HTH",
            frames_per_direction=100,
            animation_speed=256,
            triggers={5: 1, 6: 2},
        )

    def test_valid_init(self) -> None:
        """Tests if a Record object accepts valid attribute values."""
        self.record.cof_name = "T2A2HTH"
        # Large numbers are OK if they fit within unsigned 32-bit
        self.record.frames_per_direction = 0xFFFFFFFF
        self.record.animation_speed = 0xFFFFFFFF
        self.record.triggers = {0: 1, 1: 2}

    def test_invalid_cof_name_type(self) -> None:
        """Tests if cof_name rejects invalid types."""
        for bad_value in [None, 1, b"bytestr"]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(TypeError, msg="Must accept only strings"):
                    self.record.cof_name = bad_value

    def test_invalid_cof_name_too_short(self) -> None:
        """Tests if cof_name rejects strings shorter than 7 characters."""
        with self.assertRaises(ValueError):
            self.record.cof_name = "SHORTY"

    def test_invalid_cof_name_too_long(self) -> None:
        """Tests if cof_name rejects strings longer than 7 characters."""
        with self.assertRaises(ValueError):
            self.record.cof_name = "TOOLONG1"

    def test_invalid_cof_name_has_null(self) -> None:
        """Tests if cof_name rejects strings with null characters."""
        with self.assertRaises(ValueError):
            self.record.cof_name = "BADCHR\0"

    def test_invalid_frames_per_direction_type(self) -> None:
        """Tests if frames_per_direction rejects invalid types."""
        for bad_value in [None, 1.1, "1"]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(TypeError, msg="Must accept only integers"):
                    self.record.frames_per_direction = bad_value

    def test_invalid_frames_per_direction_negative(self) -> None:
        """Tests if frames_per_direction rejects negative values."""
        with self.assertRaises(ValueError):
            self.record.frames_per_direction = -1

    def test_invalid_frames_per_direction_too_large(self) -> None:
        """Tests if frames_per_direction rejects values too large to fit within
        an unsigned 32-bit integer."""
        with self.assertRaises(ValueError):
            self.record.frames_per_direction = 0xFFFFFFFF + 1

    def test_invalid_animation_speed_type(self) -> None:
        """Tests if animation_speed rejects invalid types."""
        for bad_value in [None, 1.1, "1"]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(TypeError, msg="Must accept only integers"):
                    self.record.animation_speed = bad_value

    def test_invalid_animation_speed_negative(self) -> None:
        """Tests if animation_speed rejects negative values."""
        with self.assertRaises(ValueError):
            self.record.animation_speed = -1

    def test_invalid_animation_speed_too_large(self) -> None:
        """Tests if animation_speed rejects values too large to fit within an
        unsigned 32-bit integer."""
        with self.assertRaises(ValueError):
            self.record.animation_speed = 0xFFFFFFFF + 1

    def test_invalid_triggers_type(self) -> None:
        """Tests if triggers rejects values that are not valid mappings."""
        for bad_value in [1, "string", [0]]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises((TypeError, ValueError)):
                    self.record.triggers = bad_value

    def test_invalid_triggers_greater_than_trigger_frame(self) -> None:
        """Tests if triggers rejects when a trigger's frame is greater than
        frames_per_direction"""
        self.record.triggers = []
        self.record.frames_per_direction = 0
        with self.assertRaises(ValueError):
            self.record.triggers = {1000: 1}

    def test_make_dict(self) -> None:
        """Tests if a valid Record can be converted to a plain dict."""
        self.assertEqual(
            self.record.make_dict(),
            {
                "cof_name": "AAA1HTH",
                "frames_per_direction": 100,
                "animation_speed": 256,
                "triggers": {5: 1, 6: 2},
            },
        )

    def test_from_dict(self) -> None:
        """Tests iv a valid dict can be converted to a Record."""
        self.assertEqual(
            Record.from_dict(
                {
                    "cof_name": "AAA1HTH",
                    "frames_per_direction": 100,
                    "animation_speed": 256,
                    "triggers": {5: 1, "6": 2},
                }
            ),
            self.record,
        )


class TestActionTriggers(unittest.TestCase):
    """Test case for the d2animdata.ActionTriggers class."""

    def test_valid_init(self) -> None:
        """Tests if an ActionTriggers object accepts valid frames and codes."""
        # pylint: disable=no-self-use
        ActionTriggers({5: 1, 6: 2, 7: 3})

    def test_invalid_frame_type(self) -> None:
        """Tests if ActionTriggers rejects invalid frame types."""
        for bad_value in [None, 1.1, "1"]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(TypeError, msg="Must accept only integers"):
                    ActionTriggers({bad_value: 1})

    def test_invalid_frame_negative(self) -> None:
        """Tests if ActionTriggers rejects negative frame values."""
        with self.assertRaises(ValueError):
            ActionTriggers({-1: 1})

    def test_invalid_frame_too_big(self) -> None:
        """Tests if ActionTriggers rejects frame values bigger than the allowed
        maximum."""
        with self.assertRaises(ValueError):
            ActionTriggers({144: 1})

    def test_invalid_code_type(self) -> None:
        """Tests if ActionTriggers rejects invalid code types."""
        for bad_value in [None, 1.1, "1"]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(TypeError, msg="Must accept only integers"):
                    ActionTriggers({0: bad_value})

    def test_invalid_code_value(self) -> None:
        """Tests if ActionTriggers rejects code values outside the allowed range
        (1 <= code <= 3)."""
        for bad_value in [-1, -100, 4, 5, 1000]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(ValueError):
                    ActionTriggers({0: bad_value})
