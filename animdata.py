#!/usr/bin/env python
import struct
from functools import lru_cache
from itertools import chain
from pprint import pprint
from typing import Iterable, List, NamedTuple, Tuple
from warnings import warn


def hash_cof_name(cof_name: bytes) -> int:
    """Returns the block hash for the given COF name."""
    # Based on:
    #   https://d2mods.info/forum/viewtopic.php?p=24163#p24163
    #   https://d2mods.info/forum/viewtopic.php?p=24295#p24295
    return sum(cof_name[: cof_name.index(b"\0")].upper()) % 256


class Record(NamedTuple):
    """Represents an AnimData record entry."""

    cof_name: str
    frames_per_direction: int
    animation_speed: int
    action_frames: Tuple[Tuple[int, int], ...]

    @property
    def token(self) -> str:
        """Returns the animation token portion of the COF name."""
        return self.cof_name[:2]


RECORD_FORMAT = "<8sLL144B"


def unpack_record(buffer: bytes, offset: int = 0) -> Tuple[Record, int]:
    """Unpacks a single AnimData record from the `buffer` at `offset`."""
    (cof_name, frames_per_direction, animation_speed, *frame_data) = struct.unpack_from(
        RECORD_FORMAT, buffer, offset=offset
    )

    assert all(
        ch == 0 for ch in cof_name[cof_name.index(b"\0") :]
    ), f"{cof_name} has non-null character after null terminator"

    action_frames = []
    for frame_index, frame_code in enumerate(frame_data):
        if frame_code:
            assert frame_index < frames_per_direction, (
                f"Action frame {frame_index}={frame_code} "
                f"appears after end of animation (length={frames_per_direction})"
            )
            action_frames.append((frame_index, frame_code))

    return (
        Record(
            cof_name=cof_name,
            frames_per_direction=frames_per_direction,
            animation_speed=animation_speed,
            action_frames=tuple(action_frames),
        ),
        struct.calcsize(RECORD_FORMAT),
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


def build_hash_table(records: Iterable[Record]) -> List[List[Record]]:
    """Creates a 'hash' table of records from that can be packed later."""
    hash_table = [[] for _ in range(256)]
    for record in records:
        hash_value = hash_cof_name(record.cof_name)
        hash_table[hash_value].append(record)
    return hash_table


def sorted_records_join(blocks: List[List[Record]]) -> List[Record]:
    """Extracts a list of records from hash table blocks, joining each list
    sequentially to preserve the original record order in the hash table."""
    return list(chain.from_iterable(blocks))


def sorted_records_alphabetically(blocks: List[List[Record]]) -> List[Record]:
    """Extracts a list of records from hash table blocks, sorted alphabetically
    by COF name.

    Note: This does NOT preserve the original record order in the hash table!
    """
    return sorted(
        (record for records in blocks for record in records),
        key=lambda record: record.cof_name,
    )


def sort_tokens(all_tokens: Iterable[Iterable[str]]) -> List[str]:
    # Represents a directed, possibly-acyclic graph
    token_to_preceding_tokens = {}
    for tokens in all_tokens:
        for index, token in enumerate(tokens):
            preceding_tokens = token_to_preceding_tokens.setdefault(token, set())
            if index > 0:
                preceding_tokens.add(tokens[index - 1])

    # Perform a topological sort using depth-first search
    sorted_tokens = []
    is_visiting = {}

    def visit(token):
        preceding_tokens = token_to_preceding_tokens.get(token)
        if preceding_tokens is None:
            return

        if is_visiting.get(token):
            warn(f"Cycle detected, cannot sort token {token} reliably")
            return

        is_visiting[token] = True
        for preceding_token in token_to_preceding_tokens.get(token, []):
            visit(preceding_token)
        del is_visiting[token]

        sorted_tokens.append(token)
        del token_to_preceding_tokens[token]

    while token_to_preceding_tokens:
        visit(next(iter(token_to_preceding_tokens)))

    return sorted_tokens


def sorted_records_preserve(blocks: List[List[Record]]) -> List[Record]:
    """Extracts a list of records from hash table blocks, preserving the order
    of tokens as much as possible.

    Note: This does NOT preserve the original record order in the hash table!
    """
    all_tokens = [
        list(dict.fromkeys(record.token for record in block)) for block in blocks
    ]
    all_tokens = sort_tokens(all_tokens)

    token_to_index = {token: index for index, token in enumerate(all_tokens)}
    return sorted(
        chain.from_iterable(blocks), key=lambda record: token_to_index[record.token],
    )


def main() -> None:
    """Entrypoint for the CLI script."""
    ANIMDATA_D2_PATH = "AnimData-from-game.D2"
    with open(ANIMDATA_D2_PATH, mode="rb") as animdata_d2_file:
        animdata_raw = animdata_d2_file.read()

    print(f"Opened {ANIMDATA_D2_PATH}, size is {len(animdata_raw)} byte(s)...")

    (blocks, all_blocks_size) = unpack_hash_table(animdata_raw)
    assert all_blocks_size == len(
        animdata_raw
    ), f"Blocks use {all_blocks_size} bytes, but file size is {len(animdata_raw)} bytes"

    print(f"{sum(len(records) for records in blocks)} records in total")

    with open("animdata_dump.txt", mode="w") as dump_file:
        pprint(blocks, stream=dump_file)

    records_preserved = sorted_records_preserve(blocks)
    repacked_preserved = build_hash_table(records_preserved)
    with open("animdata_dump_preserved.txt", mode="w") as dump_file_2:
        pprint(records_preserved, stream=dump_file_2)
    with open("animdata_dump_preserved_repacked.txt", mode="w") as dump_file_3:
        pprint(repacked_preserved, stream=dump_file_3)


if __name__ == "__main__":
    main()
    # print(sort_tokens(["abcd", "zafd"]))
