"""Predefined valid input & output samples for use in tests."""

from d2animdata import Record


# Valid AnimData.D2 with 1 hash record each in the first and second blocks.
# This decompiles to VALID_JSON and VALID_TXT without warnings.
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

# Expected result of loading VALID_ANIMDATA.
# Dumping this results in VALID_ANIMDATA.
VALID_RECORDS = [
    Record(
        cof_name="AWS1HTH",
        frames_per_direction=9,
        animation_speed=7,
        triggers={0: 3, 1: 2, 2: 1},
    ),
    Record(
        cof_name="AXS1HTH",
        frames_per_direction=256,
        animation_speed=256,
        triggers={141: 1, 142: 2, 143: 3},
    ),
]

# Expected result of decompiling VALID_ANIMDATA.
# This compiles to VALID_ANIMDATA without warnings.
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
# This compiles to VALID_ANIMDATA without warnings.
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
