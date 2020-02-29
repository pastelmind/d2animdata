#!/usr/bin/env python
"""Extracts and saves AnimData.D2"""

import struct
from typing import BinaryIO, Iterable, List, NamedTuple, Tuple


def hash_cof_name(cof_name: bytes) -> int:
    """Returns the block hash for the given COF name."""
    # Based on:
    #   https://d2mods.info/forum/viewtopic.php?p=24163#p24163
    #   https://d2mods.info/forum/viewtopic.php?p=24295#p24295
    return sum(cof_name[: cof_name.index(b"\0")].upper()) % 256


class ActionTrigger(NamedTuple):
    """Represents a single action trigger frame in an AnimData record."""

    frame: int
    code: int


class Record(NamedTuple):
    """Represents an AnimData record entry."""

    cof_name: bytes
    frames_per_direction: int
    animation_speed: int
    triggers: Tuple[ActionTrigger, ...]


RECORD_FORMAT = "<8sLL144B"


def unpack_record(buffer: bytes, offset: int = 0) -> Tuple[Record, int]:
    """Unpacks a single AnimData record from the `buffer` at `offset`."""
    (cof_name, frames_per_direction, animation_speed, *frame_data) = struct.unpack_from(
        RECORD_FORMAT, buffer, offset=offset
    )

    assert all(
        ch == 0 for ch in cof_name[cof_name.index(b"\0") :]
    ), f"{cof_name} has non-null character after null terminator"

    triggers = []
    for frame_index, frame_code in enumerate(frame_data):
        if frame_code:
            assert frame_index < frames_per_direction, (
                f"Trigger frame {frame_index}={frame_code} "
                f"appears after end of animation (length={frames_per_direction})"
            )
            triggers.append(ActionTrigger(frame=frame_index, code=frame_code))

    return (
        Record(
            cof_name=cof_name,
            frames_per_direction=frames_per_direction,
            animation_speed=animation_speed,
            triggers=tuple(triggers),
        ),
        struct.calcsize(RECORD_FORMAT),
    )


DWORD_MAX = 0xFFFFFFFF


def pack_record(record: Record) -> bytes:
    """Packs a single AnimData record."""
    cof_name = record.cof_name
    if len(cof_name) != 8:
        raise ValueError(
            f"COF name must be 8 bytes, including the null terminator."
            f" ({cof_name!r} is {len(cof_name)} bytes long)"
        )
    if cof_name[-1] != 0:
        raise ValueError(
            f"COF name must be terminated with a null byte. "
            f"(found {cof_name[-1]!r} at end of {cof_name!r})"
        )

    frames_per_direction = record.frames_per_direction
    if not 0 <= frames_per_direction <= DWORD_MAX:
        raise ValueError(
            f"frames_per_direction must be between 0 and {DWORD_MAX}."
            f"(current value is {frames_per_direction!r})"
        )

    animation_speed = record.animation_speed
    if not 0 <= animation_speed <= DWORD_MAX:
        raise ValueError(
            f"animation_speed must be between 0 and {DWORD_MAX}."
            f"(current value is {animation_speed!r})"
        )

    frame_data = [0] * 144
    for trigger in record.triggers:
        if not 1 <= trigger.code <= 3:
            raise ValueError(f"Invalid trigger code {trigger.code!r} in {record!r}")
        if trigger.frame >= frames_per_direction:
            raise ValueError(
                f"Trigger frame must be less than or equal to frames_per_direction "
                f" (got trigger frame={trigger.frame!r}, "
                f"frames_per_direction={frames_per_direction} "
                f"in {record!r})"
            )
        try:
            if frame_data[trigger.frame] != 0:
                raise ValueError(
                    f"Cannot assign a trigger {trigger!r} "
                    f"to a frame already in use, in {record!r}"
                )
            frame_data[trigger.frame] = trigger.code
        except IndexError:
            raise ValueError(
                f"Trigger frame must be between 0 and {len(frame_data)} "
                f"(got {trigger.frame!r} in {record!r}"
            ) from None

    return struct.pack(
        RECORD_FORMAT, cof_name, frames_per_direction, animation_speed, *frame_data
    )


RECORD_COUNT_FORMAT = "<L"


def unpack_block(buffer: bytes, offset: int = 0) -> Tuple[List[Record], int]:
    """Unpacks a block of AnimData records from the `buffer` at `offset`."""
    (record_count,) = struct.unpack_from(RECORD_COUNT_FORMAT, buffer, offset=offset)
    record_offset = offset + struct.calcsize(RECORD_COUNT_FORMAT)

    records = []
    for _ in range(record_count):
        record, record_size = unpack_record(buffer, offset=record_offset)
        records.append(record)
        record_offset += record_size

    return records, record_offset - offset


def unpack_hash_table(buffer: bytes, offset: int = 0) -> Tuple[List[List[Record]], int]:
    """Unpacks a hash table of AnimData records from the `buffer` at `offset`."""
    blocks = []
    block_offset = offset
    for block_index in range(256):
        block, block_size = unpack_block(buffer, offset=block_offset)
        for record in block:
            hash_value = hash_cof_name(record.cof_name)
            assert block_index == hash_value, (
                f"Incorrect hash (COF name={record.cof_name}): "
                f"expected {block_index} but got {hash_value}"
            )
        blocks.append(block)
        block_offset += block_size
    return blocks, block_offset - offset


def sort_records_by_cof_name(blocks: List[List[Record]]) -> List[Record]:
    """Extracts a list of records from hash table blocks, sorted alphabetically
    by COF name.

    Note: This does NOT preserve the original record order in the hash table!
    """
    return sorted(
        (record for records in blocks for record in records),
        key=lambda record: record.cof_name,
    )


def loads(data: bytes) -> List[Record]:
    """Loads the contents of AnimData.D2 from the a bytes object.

    Args:
        file:
            Contents of AnimData.D2 in binary format.

    Returns:
        List of Record objects, sorted alphabetically by COF name.
    """
    (blocks, all_blocks_size) = unpack_hash_table(data)
    data_size = len(data)
    assert all_blocks_size == data_size, (
        f"File size mismatch: "
        f"Blocks use {all_blocks_size} bytes, but binary size is {data_size} bytes"
    )
    return sort_records_by_cof_name(blocks)


def load(file: BinaryIO) -> List[Record]:
    """Loads the contents of AnimData.D2 from the a binary file.

    Args:
        file:
            Readable file object opened in binary mode.

    Returns:
        List of Record objects.
    """
    return loads(file.read())


def dumps(records: Iterable[Record]) -> bytearray:
    """Packs AnimData records into AnimData.D2 hash table format."""
    hash_table = [[] for _ in range(256)]
    for record in records:
        hash_value = hash_cof_name(record.cof_name)
        hash_table[hash_value].append(record)

    packed_data = bytearray()
    for block in hash_table:
        packed_data += struct.pack(RECORD_COUNT_FORMAT, len(block))
        for record in block:
            packed_data += pack_record(record)

    return packed_data


def dump(records: Iterable[Record], file: BinaryIO) -> None:
    """Packs AnimData records into binary format and writes them to a file."""
    file.write(dumps(records))


def main() -> None:
    """Entrypoint for the CLI script."""
    ANIMDATA_D2_PATH = "AnimData-from-game.D2"
    with open(ANIMDATA_D2_PATH, mode="rb") as animdata_d2_file:
        records = load(animdata_d2_file)

    print(f"Opened {ANIMDATA_D2_PATH}, size is {animdata_d2_file.tell()} byte(s)")
    print(f"Unpacked {len(records)} records")


if __name__ == "__main__":
    main()
