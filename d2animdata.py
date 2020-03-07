#!/usr/bin/env python
"""Extracts and saves AnimData.D2"""

__version__ = "0.0.1a0"

import argparse
import csv
import dataclasses
import itertools
import json
import logging
import struct
from collections import UserDict
from operator import attrgetter
from typing import (
    BinaryIO,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    TextIO,
    Tuple,
    Union,
)

# Logger used by the CLI program
logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Error(Exception):
    """Base class for all errors thrown by this module."""


class LoadTxtError(Error):
    """Raised when loading a TXT file fails.

    Attributes:
        row: Row index that caused the failure (starts at 0).
    """

    def __init__(self, message: str, row: Optional[int] = None) -> None:
        super().__init__(message + ("" if row is None else f" (at row index {row})"))
        self.row = row


def hash_cof_name(cof_name: str) -> int:
    """Returns the block hash for the given COF name."""
    # Based on:
    #   https://d2mods.info/forum/viewtopic.php?p=24163#p24163
    #   https://d2mods.info/forum/viewtopic.php?p=24295#p24295
    return sum(map(ord, cof_name.upper())) % 256


# Loosely inspired by:
#   https://florimond.dev/blog/articles/2018/10/reconciling-dataclasses-and-properties-in-python/
class ManagedProperty(property):
    """Managed, required property for use with dataclasses."""

    def __set_name__(self, owner, property_name: str) -> None:
        # pylint: disable=attribute-defined-outside-init
        self.property_name = property_name

    def __set__(self, obj, value) -> None:
        # Check if the __init__() of a dataclass is passing the property
        # itself as the "default" value.
        # This occurs when a dataclass is instantiated without providing a value
        # for this property.
        if value is self:
            raise TypeError(f"Missing value for property {self.property_name!r}")
        super().__set__(obj, value)


FRAME_MAX = 144


class ActionTriggers(UserDict):
    """Mapping of trigger frames to trigger codes.

    Iteration is guaranteed to be sorted by frame index in ascending order.
    """

    # pylint: disable=too-many-ancestors

    def __setitem__(self, frame, code) -> None:
        if not isinstance(frame, int):
            raise TypeError(f"frame must be an integer (got {frame!r})")
        if not 0 <= frame < FRAME_MAX:
            raise ValueError(
                f"frame must be between 0 and {FRAME_MAX - 1} (got {frame!r})"
            )

        if not isinstance(code, int):
            raise TypeError(f"code must be an integer (got {code!r})")
        if not 1 <= code <= 3:
            raise ValueError(f"code must be between 1 and 3 (got {code!r})")

        self.data[frame] = code

    def __iter__(self) -> Iterator[int]:
        return iter(sorted(self.data))

    def to_codes(self) -> Iterable[int]:
        """Yields a frame codes for each frame in order."""
        for frame in range(FRAME_MAX):
            yield self.get(frame, 0)

    @classmethod
    def from_codes(cls, frame_codes: Iterable[int]) -> "ActionTriggers":
        """Creates an ActionTriggers object from an iterable of codes for each
        frame."""
        obj = cls()
        for frame, code in enumerate(frame_codes):
            if frame >= FRAME_MAX:
                break
            if code:
                obj[frame] = code
        return obj


DWORD_MAX = 0xFFFFFFFF


@dataclasses.dataclass
class Record:
    """Represents an AnimData record entry."""

    cof_name: str = ManagedProperty(attrgetter("_cof_name"))

    @cof_name.setter
    def cof_name(self, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"cof_name must be a string (got {value!r})")
        if len(value) != 7:
            raise ValueError(
                f"COF name must have exactly 7 characters. "
                f"({value!r} has {len(value)})"
            )
        if "\0" in value:
            raise ValueError(
                f"COF name must not contain a null character. (found in {value!r})"
            )
        self._cof_name = value

    frames_per_direction: int = ManagedProperty(attrgetter("_frames_per_direction"))

    @frames_per_direction.setter
    def frames_per_direction(self, value: int) -> int:
        if not isinstance(value, int):
            raise TypeError(f"frames_per_direction must be an integer (got {value!r})")
        if not 0 <= value <= DWORD_MAX:
            raise ValueError(
                f"frames_per_direction must be between 0 and {DWORD_MAX}."
                f"(got {value!r})"
            )
        try:
            triggers = self.triggers
        except AttributeError:
            pass
        else:
            self._check_frames(value, triggers)
        self._frames_per_direction = value

    animation_speed: int = ManagedProperty(attrgetter("_animation_speed"))

    @animation_speed.setter
    def animation_speed(self, value: int) -> int:
        if not isinstance(value, int):
            raise TypeError(f"animation_speed must be an integer (got {value!r})")
        if not 0 <= value <= DWORD_MAX:
            raise ValueError(
                f"animation_speed must be between 0 and {DWORD_MAX}. (got {value!r})"
            )
        self._animation_speed = value

    triggers: ActionTriggers = ManagedProperty(attrgetter("_triggers"))

    @triggers.setter
    def triggers(
        self, value: Union[Iterable[Tuple[int, int]], Mapping[int, int]]
    ) -> ActionTriggers:
        triggers = ActionTriggers(value)

        try:
            frames_per_direction = self.frames_per_direction
        except AttributeError:
            pass
        else:
            self._check_frames(frames_per_direction, triggers)
        self._triggers = triggers

    def _check_frames(
        self, frames_per_direction: int, triggers: ActionTriggers
    ) -> None:
        """Checks if all trigger frames are no greater than frames_per_direction."""
        for frame, code in triggers.items():
            if frame > frames_per_direction:
                raise ValueError(
                    f"Trigger frame must be no greater than than frames_per_direction "
                    f"(got trigger frame={frame!r}, code={code!r}, "
                    f"frames_per_direction={frames_per_direction} "
                    f"for {self.cof_name!r})"
                )

    def make_dict(self) -> dict:
        """Returns a plain dict that can be serialized to another format."""
        self_dict = dataclasses.asdict(self)
        self_dict["triggers"] = dict(self_dict["triggers"])
        return self_dict

    @classmethod
    def from_dict(cls, obj: dict) -> "Record":
        """Creates a new record from a dict unserialized from another format.

        Trigger frame indices are automatically converted to integers in order
        to support data formats that do not support integer mapping keys
        (e.g. JSON).
        """
        return cls(
            cof_name=obj["cof_name"],
            frames_per_direction=obj["frames_per_direction"],
            animation_speed=obj["animation_speed"],
            triggers={int(frame): code for frame, code in obj["triggers"].items()},
        )


RECORD_FORMAT = f"<8sLL{FRAME_MAX}B"


def unpack_record(buffer: bytes, offset: int = 0) -> Tuple[Record, int]:
    """Unpacks a single AnimData record from the `buffer` at `offset`."""
    (cof_name, frames_per_direction, animation_speed, *frame_data) = struct.unpack_from(
        RECORD_FORMAT, buffer, offset=offset
    )

    return (
        Record(
            cof_name=str(cof_name.split(b"\0", maxsplit=1)[0], encoding="ascii"),
            frames_per_direction=frames_per_direction,
            animation_speed=animation_speed,
            triggers=ActionTriggers.from_codes(frame_data),
        ),
        struct.calcsize(RECORD_FORMAT),
    )


def pack_record(record: Record) -> bytes:
    """Packs a single AnimData record."""
    return struct.pack(
        RECORD_FORMAT,
        bytes(record.cof_name, encoding="ascii"),
        record.frames_per_direction,
        record.animation_speed,
        *record.triggers.to_codes(),
    )


def sort_records_by_cof_name(records: List[Record]) -> None:
    """Sorts a list of Records in place by COF name."""
    records.sort(key=lambda record: record.cof_name)


def check_duplicate_cof_names(records: Iterable[Record]) -> None:
    """Checks if the list of AnimData records contains duplicate COF names."""
    cof_names_seen = set()
    for record in records:
        if record.cof_name in cof_names_seen:
            logger.warning(f"Duplicate entry found: {record.cof_name}")
        else:
            cof_names_seen.add(record.cof_name)


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


def load_txt(file: Iterable[str]) -> List[Record]:
    """Loads AnimData records from a tabbed text file."""
    reader = csv.reader(file, dialect="excel-tab")
    headers = {header: index for index, header in enumerate(next(reader))}
    cof_name_index = headers["CofName"]
    frames_per_direction_index = headers["FramesPerDirection"]
    animation_speed_index = headers["AnimationSpeed"]
    frame_data_indices = [headers[f"FrameData{frame:03}"] for frame in range(FRAME_MAX)]

    records = []
    for row_num, row in enumerate(reader):
        try:
            records.append(
                Record(
                    cof_name=row[cof_name_index],
                    frames_per_direction=int(row[frames_per_direction_index]),
                    animation_speed=int(row[animation_speed_index]),
                    triggers=ActionTriggers.from_codes(
                        int(row[index]) for index in frame_data_indices
                    ),
                )
            )
        except (KeyError, TypeError, ValueError, csv.Error) as err:
            raise LoadTxtError("Failed to parse TXT file", row=row_num) from err
    return records


def dump_txt(records: Iterable[Record], file: TextIO) -> None:
    """Saves AnimData records to a tabbed text file."""
    writer = csv.writer(file, dialect="excel-tab")
    writer.writerow(
        [
            "CofName",
            "FramesPerDirection",
            "AnimationSpeed",
            *(f"FrameData{frame:03}" for frame in range(FRAME_MAX)),
        ]
    )

    for record in records:
        writer.writerow(
            [
                record.cof_name,
                record.frames_per_direction,
                record.animation_speed,
                *record.triggers.to_codes(),
            ]
        )


def main(argv: List[str] = None) -> None:
    """Entrypoint for the CLI script."""
    logging.basicConfig(format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command")

    parser_compile = subparsers.add_parser(
        "compile", help="Compiles JSON to AnimData.D2"
    )
    parser_compile.add_argument("source", help="JSON or tabbed text file to compile")
    parser_compile.add_argument("animdata_d2", help="AnimData.D2 file to save to")
    parser_compile.add_argument(
        "--sort",
        action="store_true",
        help="Sort the records alphabetically before saving",
    )

    format_group = parser_compile.add_mutually_exclusive_group(required=True)
    format_group.add_argument("--json", action="store_true", help="Compile JSON")
    format_group.add_argument(
        "--txt", action="store_true", help="Compile tabbed text (TXT)"
    )

    parser_decompile = subparsers.add_parser(
        "decompile", help="Deompiles AnimData.D2 to JSON"
    )
    parser_decompile.add_argument("animdata_d2", help="AnimData.D2 file to decompile")
    parser_decompile.add_argument("target", help="JSON or tabbed text file to save to")
    parser_decompile.add_argument(
        "--sort",
        action="store_true",
        help="Sort the records alphabetically before saving",
    )

    format_group = parser_decompile.add_mutually_exclusive_group(required=True)
    format_group.add_argument("--json", action="store_true", help="Decompile to JSON")
    format_group.add_argument(
        "--txt", action="store_true", help="Decompile to tabbed text (TXT)"
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
    elif args.command == "compile":
        if args.txt:
            with open(args.source, newline="") as source_file:
                records = load_txt(source_file)
        elif args.json:
            with open(args.source) as source_file:
                json_data = json.load(source_file)
            records = list(map(Record.from_dict, json_data))
        else:
            raise ValueError("No file format specified")

        check_duplicate_cof_names(records)
        if args.sort:
            sort_records_by_cof_name(records)

        with open(args.animdata_d2, mode="wb") as animdata_d2_file:
            dump(records, animdata_d2_file)
    elif args.command == "decompile":
        with open(args.animdata_d2, mode="rb") as animdata_d2_file:
            records = load(animdata_d2_file)

        check_duplicate_cof_names(records)
        if args.sort:
            sort_records_by_cof_name(records)

        if args.txt:
            with open(args.target, mode="w", newline="") as target_file:
                dump_txt(records, target_file)
        elif args.json:
            json_data = [record.make_dict() for record in records]
            with open(args.target, mode="w") as target_file:
                json.dump(json_data, target_file, indent=2)
        else:
            raise ValueError("No file format specified")
    else:
        raise ValueError(f"Unexpected command: {args.command!r}")


if __name__ == "__main__":
    main()
