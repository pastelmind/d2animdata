#!/usr/bin/env python
"""Extracts and saves AnimData.D2"""

import argparse
import collections.abc
import itertools
import json
import struct
import sys
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

    def make_dict(self) -> dict:
        """Returns a plain dict that can be serialized to another format."""
        return {
            "cof_name": str(self.cof_name.rstrip(b"\0"), encoding="ascii"),
            "frames_per_direction": self.frames_per_direction,
            "animation_speed": self.animation_speed,
            "triggers": [trigger._asdict() for trigger in self.triggers],
        }

    @classmethod
    def from_dict(cls, obj: dict) -> "Record":
        """Creates a new record from a dict unserialized from another format."""
        cof_name = obj["cof_name"]
        if isinstance(cof_name, str):
            cof_name = bytes(cof_name, encoding="ascii") + b"\0"
        elif not isinstance(cof_name, (collections.abc.ByteString, memoryview)):
            raise TypeError(
                f"cof_name must be a string or bytes-compatible object "
                f"(got {cof_name!r})"
            )

        frames_per_direction = obj["frames_per_direction"]
        if not isinstance(frames_per_direction, int):
            raise TypeError(
                f"frames_per_direction must be an integer "
                f"(got {frames_per_direction!r})"
            )

        animation_speed = obj["animation_speed"]
        if not isinstance(animation_speed, int):
            raise TypeError(
                f"animation_speed must be an integer (got {animation_speed!r})"
            )

        triggers = []
        for trigger_dict in obj["triggers"]:
            trigger = ActionTrigger(**trigger_dict)
            if not isinstance(trigger.frame, int):
                raise TypeError(
                    f"Trigger frame must be an integer (got {trigger.frame!r})"
                )
            if not isinstance(trigger.code, int):
                raise TypeError(
                    f"Trigger code must be an integer (got {trigger.code!r})"
                )
            triggers.append(trigger)

        return cls(
            cof_name=cof_name,
            frames_per_direction=frames_per_direction,
            animation_speed=animation_speed,
            triggers=triggers,
        )


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


def sort_records_by_cof_name(records: List[Record]) -> None:
    """Sorts a list of Records in place by COF name."""
    records.sort(key=lambda record: record.cof_name)


RECORD_COUNT_FORMAT = "<L"


def loads(data: bytes) -> List[Record]:
    """Loads the contents of AnimData.D2 from binary `data`.

    Args:
        file:
            Contents of AnimData.D2 in binary format.

    Returns:
        List of Record objects, ordered by their original order in the `data`.
    """
    blocks = []
    offset = 0
    for block_index in range(256):
        (record_count,) = struct.unpack_from(RECORD_COUNT_FORMAT, data, offset=offset)
        offset += struct.calcsize(RECORD_COUNT_FORMAT)

        records = []
        for _ in range(record_count):
            record, record_size = unpack_record(data, offset=offset)
            hash_value = hash_cof_name(record.cof_name)
            assert block_index == hash_value, (
                f"Incorrect hash (COF name={record.cof_name}): "
                f"expected {block_index} but got {hash_value}"
            )
            records.append(record)
            offset += record_size

        blocks.append(records)

    assert offset == len(data), (
        f"Data size mismatch: "
        f"Blocks use {offset} bytes, but binary size is {len(data)} bytes"
    )

    return list(itertools.chain.from_iterable(blocks))


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


def main(argv: List[str]) -> None:
    """Entrypoint for the CLI script."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command")

    parser_compile = subparsers.add_parser(
        "compile", help="Compiles JSON to AnimData.D2"
    )
    parser_compile.add_argument("source", help="JSON file to compile")
    parser_compile.add_argument("animdata_d2", help="AnimData.D2 file to save to")
    parser_compile.add_argument(
        "--sort",
        action="store_true",
        help="Sort the records alphabetically before saving",
    )

    parser_decompile = subparsers.add_parser(
        "decompile", help="Deompiles AnimData.D2 to JSON"
    )
    parser_decompile.add_argument("animdata_d2", help="AnimData.D2 file to decompile")
    parser_decompile.add_argument("target", help="JSON file to save to")
    parser_decompile.add_argument(
        "--sort",
        action="store_true",
        help="Sort the records alphabetically before saving",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
    elif args.command == "compile":
        with open(args.source) as source_file:
            json_data = json.load(source_file)

        records = list(map(Record.from_dict, json_data))
        if args.sort:
            sort_records_by_cof_name(records)

        with open(args.animdata_d2, mode="wb") as animdata_d2_file:
            dump(records, animdata_d2_file)
    elif args.command == "decompile":
        with open(args.animdata_d2, mode="rb") as animdata_d2_file:
            records = load(animdata_d2_file)

        if args.sort:
            sort_records_by_cof_name(records)
        json_data = [record.make_dict() for record in records]

        with open(args.target, mode="w") as target_file:
            json.dump(json_data, target_file, indent=2)
    else:
        raise ValueError(f"Unexpected command: {args.command!r}")


if __name__ == "__main__":
    main(sys.argv[1:])
