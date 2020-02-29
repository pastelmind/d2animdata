#!/usr/bin/env python
"""Extracts and saves AnimData.D2"""

import struct
from functools import cmp_to_key
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

    cof_name: bytes
    frames_per_direction: int
    animation_speed: int
    action_frames: Tuple[Tuple[int, int], ...]

    @property
    def token(self) -> bytes:
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


def make_token_order_keys(all_tokens: Iterable[Iterable[bytes]]) -> List[bytes]:
    # Represents a directed, possibly-acyclic graph
    token_to_prev_tokens = {}
    for tokens in map(list, all_tokens):
        for index, token in enumerate(tokens):
            prev_tokens = token_to_prev_tokens.setdefault(token, set())
            if index > 0:
                prev_tokens.add(tokens[index - 1])

    # Use depth-first search to visit each node (token)
    token_order_keys = {}
    is_visiting = {}

    def compute_order_key(token: bytes) -> None:
        try:
            return token_order_keys[token]
        except KeyError:
            pass

        if is_visiting.get(token):
            warn(f"Cycle detected, cannot sort token {token} reliably")
            return 0

        token_order_key = 0
        prev_tokens = token_to_prev_tokens[token]
        if prev_tokens:
            is_visiting[token] = True
            token_order_key = max(map(compute_order_key, prev_tokens)) + 1
            is_visiting[token] = False

        del token_to_prev_tokens[token]
        token_order_keys[token] = token_order_key
        return token_order_key

    while token_to_prev_tokens:
        compute_order_key(next(iter(token_to_prev_tokens)))

    return token_order_keys


def sorted_records_preserve(blocks: List[List[Record]]) -> List[Record]:
    """Extracts a list of records from hash table blocks, preserving the order
    of tokens as much as possible.

    Note: This does NOT preserve the original record order in the hash table!
    """
    # First, sort using the ordering of tokens (not very accurate)
    token_order_keys = make_token_order_keys(
        dict.fromkeys(record.token for record in block).keys() for block in blocks
    )
    sorted_records = sorted(
        chain.from_iterable(blocks), key=lambda record: token_order_keys[record.token]
    )

    # Next, sort using the ordering of COF names
    cof_comparisons = {}
    for block in blocks:
        for index, record in enumerate(block):
            if index == 0:
                continue
            prev_record = block[index - 1]

            cof_name = record.cof_name
            prev_cof_name = prev_record.cof_name
            if cof_comparisons.get((prev_cof_name, cof_name)) == -1:
                warn(
                    f"COF name pair {cof_name}, {prev_cof_name} already exists "
                    f"in reverse direction!"
                )
            else:
                cof_comparisons[cof_name, prev_cof_name] = -1
                cof_comparisons[prev_cof_name, cof_name] = 1

    sorted_records.sort(
        key=cmp_to_key(lambda a, b: cof_comparisons.get((a.cof_name, b.cof_name), 0))
    )
    return sorted_records


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
