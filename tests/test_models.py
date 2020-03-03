"""Unit tests for model classes."""

import unittest

from d2animdata import ActionTrigger, Record


class TestRecord(unittest.TestCase):
    """Test case for the d2animdata.Record class."""

    def setUp(self) -> None:
        """Setup for tests that manipulate already-created objects."""
        # This will fail if the constructor fails to accept valid values.
        self.record = Record(
            cof_name="AAA1HTH",
            frames_per_direction=100,
            animation_speed=256,
            triggers=[ActionTrigger(frame=5, code=1)],
        )

    def test_valid_init(self) -> None:
        """Tests if a Record object accepts valid attribute values."""
        self.record.cof_name = "T2A2HTH"
        # Large numbers are OK if they fit within unsigned 32-bit
        self.record.frames_per_direction = 0xFFFFFFFF
        self.record.animation_speed = 0xFFFFFFFF
        self.record.triggers = [
            ActionTrigger(frame=0, code=1),
            ActionTrigger(frame=1, code=2),
        ]

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

    def test_invalid_frames_per_direction_less_than_trigger_frame(self) -> None:
        """Tests if frames_per_direction rejects values smaller than the maximum
        trigger frame."""
        self.record.triggers = [ActionTrigger(frame=20, code=1)]
        with self.assertRaises(ValueError):
            self.record.frames_per_direction = 12

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
        """Tests if triggers only accepts sequences of ActionTriggers."""
        for bad_value in [None, 1, "string", {}, []]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(
                    TypeError,
                    msg="Must accept only sequences containing ActionTriggers",
                ):
                    self.record.triggers = [bad_value]

    def test_invalid_triggers_duplicate_frame(self) -> None:
        """Tests if triggers rejects when two ActionTriggers attempt to use the
        same frame."""
        # Prevent the next code from throwing because of frames_per_direction
        self.record.frames_per_direction = 100
        with self.assertRaises(ValueError):
            self.record.triggers = [
                ActionTrigger(frame=5, code=1),
                ActionTrigger(frame=5, code=2),
            ]

    def test_invalid_triggers_greater_than_trigger_frame(self) -> None:
        """Tests if triggers rejects when a trigger's frame is greater than
        frames_per_direction"""
        self.record.triggers = []
        self.record.frames_per_direction = 0
        with self.assertRaises(ValueError):
            self.record.triggers = [ActionTrigger(frame=1000, code=1)]

    def test_make_dict(self) -> None:
        """Tests if a valid Record can be converted to a plain dict."""
        self.assertEqual(
            self.record.make_dict(),
            {
                "cof_name": "AAA1HTH",
                "frames_per_direction": 100,
                "animation_speed": 256,
                "triggers": ({"frame": 5, "code": 1},),
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
                    "triggers": ({"frame": 5, "code": 1},),
                }
            ),
            self.record,
        )


class TestActionTrigger(unittest.TestCase):
    """Test case for the d2animdata.ActionTrigger class."""

    def setUp(self) -> None:
        """Setup for tests that manipulate already-created objects."""
        # This will fail if the constructor fails to accept valid values.
        self.trigger = ActionTrigger(frame=1, code=1)

    def test_valid_init(self) -> None:
        """Tests if a ActionTrigger object accepts valid attribute values."""
        self.trigger.frame = 5
        self.trigger.code = 1
        self.trigger.code = 2
        self.trigger.code = 3

    def test_invalid_frame_type(self) -> None:
        """Tests if ActionTrigger.frame rejects invalid types."""
        for bad_value in [None, 1.1, "1"]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(TypeError, msg="Must accept only integers"):
                    self.trigger.frame = bad_value

    def test_invalid_frame_negative(self) -> None:
        """Tests if ActionTrigger.frame rejects negative values."""
        with self.assertRaises(ValueError):
            self.trigger.frame = -1

    def test_invalid_frame_too_big(self) -> None:
        """Tests if ActionTrigger.frame rejects values bigger than the allowed
        maximum."""
        with self.assertRaises(ValueError):
            self.trigger.frame = 144

    def test_invalid_code_type(self) -> None:
        """Tests if ActionTrigger.code rejects invalid types."""
        for bad_value in [None, 1.1, "1"]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(TypeError, msg="Must accept only integers"):
                    self.trigger.code = bad_value

    def test_invalid_code_value(self) -> None:
        """Tests if ActionTrigger.code rejects values outside the allowed range
        (1 <= code <= 3)."""
        for bad_value in [-1, -100, 4, 5, 1000]:
            with self.subTest(bad_value=bad_value):
                with self.assertRaises(ValueError):
                    self.trigger.code = bad_value
