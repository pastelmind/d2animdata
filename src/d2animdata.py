#!/usr/bin/env python
"""Read, write, and convert AnimData.D2 to JSON & tabbed TXT (and vice versa)."""

__version__ = "0.1.0"

# MIT License

# Copyright (c) 2020 pastelmind

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
import csv
import dataclasses
import itertools
import json
import logging
import struct
from collections import UserDict
from typing import (
    Any,
    BinaryIO,
    Callable,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    TextIO,
    Tuple,
    TypeVar,
    Union,
)

# Logger used by the CLI program
logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


@dataclasses.dataclass(eq=False)
class Error(Exception):
    """Base class for all exceptions raised by this module.

    ### Attributes:
    - `message`: Explanation of the error.
    """

    message: str

    def __str__(self) -> str:
        fields = ", ".join(
            f"{name}={value!r}"
            for name, value in vars(self).items()
            if value is not None and name != "message"
        )
        return self.message + (f" ({fields})" if fields else "")


@dataclasses.dataclass(eq=False)
class AnimDataError(Error):
    """Raised when an operation on a binary AnimData.D2 file fails.

    ### Attributes:
    - `message`: Explanation of the error.
    - `offset`: Offset of the byte that caused the failure.
    """

    offset: Optional[int] = None


@dataclasses.dataclass(eq=False)
class TabbedTextError(Error):
    """Raised when an operation on a tabbed text file fails.

    ### Attributes:
    - `message`: Explanation of the error.
    - `row`: Row index that caused the failure (starts at 0).
    - `column`: Column index that caused the failure (starts at 0).
    - `column_name`: Name of the column that caused the failure.
    """

    row: Optional[int] = None
    column: Optional[int] = None
    column_name: Optional[str] = None


def hash_cof_name(cof_name: str) -> int:
    """Computes the block hash for the given COF name.

    :param cof_name: COF name as an ASCII string.
    :return: Hash value as integer between 0 and 255, inclusive.
    """
    # Based on:
    #   https://d2mods.info/forum/viewtopic.php?p=24163#p24163
    #   https://d2mods.info/forum/viewtopic.php?p=24295#p24295
    return sum(map(ord, cof_name.upper())) % 256


_T = TypeVar("_T")
_V = TypeVar("_V")


# Based on https://docs.python.org/3/howto/descriptor.html#properties
class _ManagedProperty:
    """Managed, required property for use with dataclasses."""

    def __init__(
        self, class_: type, name: str, validator: Optional[Callable[..., _V]] = None
    ) -> None:
        setattr(class_, name, self)
        self._name = name
        self._validator = validator
        # Prevent pydocmd from generating a subsection for managed properties
        self.__doc__ = None

    def __get__(self, obj: _T, owner: Optional[type] = None) -> _V:
        # If accessed as Class.property, return myself (the property object)
        if obj is None:
            return self
        # If accessed as obj.property, return the actual value
        # Bypass __getattribute__() to prevent infinite loop
        return obj.__dict__[self._name]

    def __set__(self, obj: _T, value: Any) -> None:
        # pylint: disable=attribute-defined-outside-init
        # Bypass __getattribute__() to prevent infinite loop
        obj.__dict__[self._name] = self._validator(value)

    def __call__(self, validator: Callable[..., _V]) -> Callable[..., _V]:
        # Make this instance usable as a decorator
        self._validator = validator


FRAME_MAX = 144


class ActionTriggers(UserDict):
    """Specialized dictionary that maps frame indices to trigger codes.

    Example usage:

    ```python
    triggers = ActionTriggers()
    triggers[7] = 1     # Set trigger code 1 at frame #7
    triggers[10] = 2    # Set trigger code 2 at frame #10
    ```

    The above is equivalent to:

    ```python
    triggers = ActionTriggers({ 7: 1, 10: 2 })
    ```

    Attempting to assign invalid trigger frames or values will raise an error:

    ```python
    triggers[255] = 1   # ValueError, frame index must be between 0 and 143
    triggers[3] = 4     # ValueError, trigger code must be between 1 and 3
    ```

    Iteration is guaranteed to be sorted by frame index in ascending order:

    ```python
    # Iteration order: (7, 1), (10, 2)
    for frame, code in triggers.items():
    ```
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
        """Yields a nonzero frame code for each trigger frame in order.

        :return: Generator that yields trigger codes for each trigger frame.
        """
        for frame in range(FRAME_MAX):
            yield self.get(frame, 0)

    @classmethod
    def from_codes(cls, frame_codes: Iterable[int]) -> "ActionTriggers":
        """Creates an ActionTriggers from an iterable of codes for every frame.

        :param frame_codes: List of trigger codes for each frame.
        :return: New ActionTriggers dictionary.
        :raise TypeError: If a frame code is not an integer.
        :raise ValueError: If a frame code is invalid.
        """
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
    """Represents an AnimData record entry.

    All attributes are validated on assignment, including the constructor. An
    invalid value will raise `TypeError` or `ValueError`.

    ### Attributes:
    - `cof_name`: Read/write attribute. Accepts a 7-letter ASCII string.
    - `frames_per_direction`:
        Read/write attribute. Accepts a nonnegative integer.
    - `animation_speed`: Read/write attribute. Accepts a nonnegative integer.
    - `triggers`:
        Read/write attribute. Accepts any mapping that can be converted to an
        ActionTriggers dict.
    """

    cof_name: str
    frames_per_direction: int
    animation_speed: int
    triggers: ActionTriggers

    def make_dict(self) -> dict:
        """Converts the Record to a dict that can be serialized to another format.

        :return: Plain dict created from this Record.
        """
        self_dict = dataclasses.asdict(self)
        self_dict["triggers"] = dict(self_dict["triggers"])
        return self_dict

    @classmethod
    def from_dict(cls, obj: dict) -> "Record":
        """Creates a new record from a dict unserialized from another format.

        Trigger frame indices are automatically converted to integers in order
        to support data formats that do not support integer mapping keys
        (e.g. JSON).

        :param obj: Dictionary to convert to a Record.
        :return: New Record object.
        """
        return cls(
            cof_name=obj["cof_name"],
            frames_per_direction=obj["frames_per_direction"],
            animation_speed=obj["animation_speed"],
            triggers={int(frame): code for frame, code in obj["triggers"].items()},
        )


@_ManagedProperty(Record, name="cof_name")
def _validate_cof_name(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"cof_name must be a string (got {value!r})")
    if len(value) != 7:
        raise ValueError(
            f"COF name must have exactly 7 characters. " f"({value!r} has {len(value)})"
        )
    if "\0" in value:
        raise ValueError(
            f"COF name must not contain a null character. (found in {value!r})"
        )
    return value


@_ManagedProperty(Record, name="frames_per_direction")
def _validate_frames_per_direction(value: int) -> int:
    if not isinstance(value, int):
        raise TypeError(f"frames_per_direction must be an integer (got {value!r})")
    if not 0 <= value <= DWORD_MAX:
        raise ValueError(
            f"frames_per_direction must be between 0 and {DWORD_MAX}."
            f"(got {value!r})"
        )
    return value


@_ManagedProperty(Record, name="animation_speed")
def _validate_animation_speed(value: int) -> int:
    if not isinstance(value, int):
        raise TypeError(f"animation_speed must be an integer (got {value!r})")
    if not 0 <= value <= DWORD_MAX:
        raise ValueError(
            f"animation_speed must be between 0 and {DWORD_MAX}. (got {value!r})"
        )
    return value


@_ManagedProperty(Record, name="triggers")
def _validate_triggers(
    value: Union[Iterable[Tuple[int, int]], Mapping[int, int]]
) -> ActionTriggers:
    return ActionTriggers(value)


RECORD_FORMAT = f"<8sLL{FRAME_MAX}B"


def _unpack_record(buffer: bytes, offset: int = 0) -> Tuple[Record, int]:
    """Unpacks a single Record from a buffer, optionally starting at an offset.

    :param buffer: `bytes`-like object to parse.
    :param offset: Offset of `buffer` to parse the `Record` from.
    :return: The unpacked Record object.
    """
    try:
        (
            cof_name,
            frames_per_direction,
            animation_speed,
            *frame_data,
        ) = struct.unpack_from(RECORD_FORMAT, buffer, offset=offset)
    except struct.error as error:
        raise AnimDataError(f"Cannot unpack record", offset=offset) from error

    try:
        # Assuming that RECORD_FORMAT is correct, all arguments for Record()
        # should be correctly typed. Thus, Record() will only raise ValueError.
        return (
            Record(
                cof_name=str(cof_name.split(b"\0", maxsplit=1)[0], encoding="ascii"),
                frames_per_direction=frames_per_direction,
                animation_speed=animation_speed,
                triggers=ActionTriggers.from_codes(frame_data),
            ),
            struct.calcsize(RECORD_FORMAT),
        )
    except ValueError as error:
        raise AnimDataError("Invalid record field", offset=offset) from error


def _pack_record(record: Record) -> bytes:
    """Packs a single AnimData record.

    :param record: Record object to pack.
    :return: The Record packed as a `bytes` object.
    """
    return struct.pack(
        RECORD_FORMAT,
        bytes(record.cof_name, encoding="ascii"),
        record.frames_per_direction,
        record.animation_speed,
        *record.triggers.to_codes(),
    )


def _sort_records_by_cof_name(records: List[Record]) -> None:
    """Sorts a list of Records in-place by COF name in ascending order.

    :param records: List of `Record`s to sort in-place.
    """
    records.sort(key=lambda record: record.cof_name)


def _check_duplicate_cof_names(records: Iterable[Record]) -> None:
    """Warns if a list of Record objects contains duplicate COF names.

    :param records: Iterable of Record objects to check.
    """
    cof_names_seen = set()
    for record in records:
        if record.cof_name in cof_names_seen:
            logger.warning(f"Duplicate entry found: {record.cof_name}")
        else:
            cof_names_seen.add(record.cof_name)


def _check_out_of_bounds_triggers(record: Record) -> None:
    """Warns if a Record object has any out-of-bounds trigger frames.

    :param record: A Record object to check.
    """
    for frame in record.triggers:
        if frame >= record.frames_per_direction:
            logger.warning(
                f"Record {record.cof_name}: trigger frame {frame!r} may have "
                f"no effect because it is same or greater than "
                f"frames_per_direction ({record.frames_per_direction!r})"
            )


RECORD_COUNT_FORMAT = "<L"


def loads(data: bytes) -> List[Record]:
    """Loads the contents of AnimData.D2 from binary `data`.

    :param data: Contents of AnimData.D2 in binary format.
    :return: List of `Record`s, ordered by their original order in the `data`.
    :raise AnimDataError: If the AnimData.D2 file is malformed or corrupted.
    """
    blocks = []
    offset = 0
    for block_index in range(256):
        try:
            (record_count,) = struct.unpack_from(
                RECORD_COUNT_FORMAT, data, offset=offset
            )
        except struct.error as err:
            raise AnimDataError(
                f"Cannot unpack record count for block {block_index!r}", offset=offset
            ) from err
        offset += struct.calcsize(RECORD_COUNT_FORMAT)

        records = []
        for _ in range(record_count):
            record, record_size = _unpack_record(data, offset=offset)
            hash_value = hash_cof_name(record.cof_name)
            if block_index != hash_value:
                raise AnimDataError(
                    f"Incorrect hash (COF name={record.cof_name!r}): "
                    f"expected {block_index} but got {hash_value}",
                    offset=offset,
                )
            records.append(record)
            offset += record_size

        blocks.append(records)

    if offset != len(data):
        raise AnimDataError(
            f"Data size mismatch: "
            f"Blocks use {offset} bytes, but binary size is {len(data)} bytes",
            offset=offset,
        )

    return list(itertools.chain.from_iterable(blocks))


def load(file: BinaryIO) -> List[Record]:
    """Loads the contents of AnimData.D2 from the a binary file.

    :param file: Readable file object opened in binary mode (`mode='rb'`).
    :return: List of Record objects, maintaining their original order in `file`.
    :raise AnimDataError: If the AnimData.D2 file is malformed or corrupted.
    """
    return loads(file.read())


def dumps(records: Iterable[Record]) -> bytearray:
    """Packs AnimData records into AnimData.D2 hash table format.

    :param records: Iterable of Record objects.
    :return: `bytearray` containing the packed AnimData.D2 file.
    """
    hash_table = [[] for _ in range(256)]
    for record in records:
        hash_value = hash_cof_name(record.cof_name)
        hash_table[hash_value].append(record)

    packed_data = bytearray()
    for block in hash_table:
        packed_data += struct.pack(RECORD_COUNT_FORMAT, len(block))
        for record in block:
            packed_data += _pack_record(record)

    return packed_data


def dump(records: Iterable[Record], file: BinaryIO) -> None:
    """Packs AnimData records into AnimData.D2 format and writes them to a file.

    :param records: Iterable of Record objects to write.
    :param file: Writable file object opened in binary mode (`mode='wb'`).
    """
    file.write(dumps(records))


def _get_column_index(column_indices: Mapping[int, str], column_name: str) -> int:
    """Helper that retrieves the index of a column name."""
    try:
        return column_indices[column_name]
    except KeyError:
        raise TabbedTextError("Missing column", column_name=column_name) from None


def _get_cell(row: List[str], column_index: int) -> str:
    """Helper that retrieves a value from a CSV row."""
    try:
        return row[column_index]
    except IndexError:
        raise TabbedTextError("Missing cell", column=column_index) from None


def _get_int_cell(row: List[str], column_index: int) -> int:
    """Helper that retrieves a value from a CSV row and converts it to an int."""
    try:
        return int(_get_cell(row, column_index))
    except ValueError as error:
        raise TabbedTextError(
            "Cannot convert cell value to integer", column=column_index,
        ) from error


def load_txt(file: Iterable[str]) -> List[Record]:
    """Loads AnimData records from a tabbed text file.

    :param file:
        A text file object, or any object which supports the iterator protocol
        and returns a string each time its `__next__()` method is called.
        If `file` is a file object, it should be opened with `newline=''`.
    :return: List of `Record`s loaded from the `file`.
    :raises TabbedTextError: If the tabbed text file cannot be loaded.
    """
    reader = csv.reader(file, dialect="excel-tab")
    try:
        column_names = next(reader)
    except StopIteration:  # File is empty
        return []
    except csv.Error as error:
        raise TabbedTextError("Cannot parse tabbed text file", row=0) from error

    column_indices = {header: index for index, header in enumerate(column_names)}

    cof_name_index = _get_column_index(column_indices, "CofName")
    frames_per_direction_index = _get_column_index(column_indices, "FramesPerDirection")
    animation_speed_index = _get_column_index(column_indices, "AnimationSpeed")
    frame_data_indices = [
        _get_column_index(column_indices, f"FrameData{frame:03}")
        for frame in range(FRAME_MAX)
    ]

    records = []
    try:
        for row_num, row in enumerate(reader):
            record = Record(
                cof_name=_get_cell(row, cof_name_index),
                frames_per_direction=_get_int_cell(row, frames_per_direction_index),
                animation_speed=_get_int_cell(row, animation_speed_index),
                triggers=ActionTriggers.from_codes(
                    _get_int_cell(row, index) for index in frame_data_indices
                ),
            )
            records.append(record)
    except TabbedTextError as error:
        # Add extra info for debugging
        error.row = row_num
        error.column_name = column_names[error.column]
        raise
    except ValueError as error:
        raise TabbedTextError("Invalid record field", row=row_num) from error
    except csv.Error as error:
        raise TabbedTextError("Cannot parse tabbed text file", row=row_num) from error

    return records


def dump_txt(records: Iterable[Record], file: TextIO) -> None:
    """Saves AnimData records to a tabbed text file.

    :param records: Iterable of `Record`s to write to the `file`.
    :param file:
        A text file object, or any any object with a `write()` method.
        If `file` is a file object, it should be opened with `newline=''`.
    """
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


def _init_subparser_compile(parser: argparse.ArgumentParser) -> None:
    """Initialize the argument subparser for the `compile` command."""
    parser.add_argument("source", help="JSON or tabbed text file to compile")
    parser.add_argument("animdata_d2", help="AnimData.D2 file to save to")
    parser.add_argument(
        "--sort",
        action="store_true",
        help="Sort the records alphabetically before saving",
    )

    format_group = parser.add_mutually_exclusive_group(required=True)
    format_group.add_argument("--json", action="store_true", help="Compile JSON")
    format_group.add_argument(
        "--txt", action="store_true", help="Compile tabbed text (TXT)"
    )


def _cli_compile(args: argparse.Namespace) -> None:
    """Handles the `compile` command."""
    if args.txt:
        with open(args.source, newline="") as source_file:
            records = load_txt(source_file)
    elif args.json:
        with open(args.source) as source_file:
            json_data = json.load(source_file)
        records = list(map(Record.from_dict, json_data))
    else:
        raise ValueError("No file format specified")

    _check_duplicate_cof_names(records)
    for record in records:
        _check_out_of_bounds_triggers(record)
    if args.sort:
        _sort_records_by_cof_name(records)

    with open(args.animdata_d2, mode="wb") as animdata_d2_file:
        dump(records, animdata_d2_file)


def _init_subparser_decompile(parser: argparse.ArgumentParser) -> None:
    """Initialize the argument subparser for the `decompile` command."""
    parser.add_argument("animdata_d2", help="AnimData.D2 file to decompile")
    parser.add_argument("target", help="JSON or tabbed text file to save to")
    parser.add_argument(
        "--sort",
        action="store_true",
        help="Sort the records alphabetically before saving",
    )

    format_group = parser.add_mutually_exclusive_group(required=True)
    format_group.add_argument("--json", action="store_true", help="Decompile to JSON")
    format_group.add_argument(
        "--txt", action="store_true", help="Decompile to tabbed text (TXT)"
    )


def _cli_decompile(args: argparse.Namespace):
    """Handles the `decompile` command."""
    with open(args.animdata_d2, mode="rb") as animdata_d2_file:
        records = load(animdata_d2_file)

    _check_duplicate_cof_names(records)
    for record in records:
        _check_out_of_bounds_triggers(record)
    if args.sort:
        _sort_records_by_cof_name(records)

    if args.txt:
        with open(args.target, mode="w", newline="") as target_file:
            dump_txt(records, target_file)
    elif args.json:
        json_data = [record.make_dict() for record in records]
        with open(args.target, mode="w") as target_file:
            json.dump(json_data, target_file, indent=2)
    else:
        raise ValueError("No file format specified")


def main(argv: List[str] = None) -> None:
    """Entrypoint for the CLI script.

    :param argv: List of argument strings. If not given, `sys.argv[1:]` is used.
    """
    logging.basicConfig(format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command")

    _init_subparser_compile(
        subparsers.add_parser("compile", help="Compiles JSON to AnimData.D2")
    )
    _init_subparser_decompile(
        subparsers.add_parser("decompile", help="Deompiles AnimData.D2 to JSON")
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
    elif args.command == "compile":
        _cli_compile(args)
    elif args.command == "decompile":
        _cli_decompile(args)
    else:
        raise ValueError(f"Unexpected command: {args.command!r}")


if __name__ == "__main__":
    main()
