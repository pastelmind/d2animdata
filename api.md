<a name="d2animdata"></a>
# d2animdata

Read, write, and convert AnimData.D2 to JSON & tabbed TXT (and vice versa).

<a name="d2animdata.Error"></a>
## Error Objects

```python
@dataclasses.dataclass(eq=False)
class Error(Exception)
```

Base class for all exceptions raised by this module.

### Attributes:
- `message`: Explanation of the error.

<a name="d2animdata.AnimDataError"></a>
## AnimDataError Objects

```python
@dataclasses.dataclass(eq=False)
class AnimDataError(Error)
```

Raised when an operation on a binary AnimData.D2 file fails.

### Attributes:
- `message`: Explanation of the error.
- `offset`: Offset of the byte that caused the failure.

<a name="d2animdata.TabbedTextError"></a>
## TabbedTextError Objects

```python
@dataclasses.dataclass(eq=False)
class TabbedTextError(Error)
```

Raised when an operation on a tabbed text file fails.

### Attributes:
- `message`: Explanation of the error.
- `row`: Row index that caused the failure (starts at 0).
- `column`: Column index that caused the failure (starts at 0).
- `column_name`: Name of the column that caused the failure.

<a name="d2animdata.hash_cof_name"></a>
#### hash\_cof\_name

```python
hash_cof_name(cof_name: str) -> int
```

Computes the block hash for the given COF name.

**Arguments**:

- `cof_name`: COF name as an ASCII string.

**Returns**:

Hash value as integer between 0 and 255, inclusive.

<a name="d2animdata.ActionTriggers"></a>
## ActionTriggers Objects

```python
class ActionTriggers(collections.UserDict)
```

Specialized dictionary that maps frame indices to trigger codes.

Example usage:

```python
triggers = ActionTriggers()
triggers[7] = 1     # Set trigger code 1 at frame `7`
triggers[10] = 2    # Set trigger code 2 at frame `10`
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

<a name="d2animdata.ActionTriggers.to_codes"></a>
#### to\_codes

```python
 | to_codes() -> Iterable[int]
```

Yields a nonzero frame code for each trigger frame in order.

**Returns**:

Generator that yields trigger codes for each trigger frame.

<a name="d2animdata.ActionTriggers.from_codes"></a>
#### from\_codes

```python
 | @classmethod
 | from_codes(cls, frame_codes: Iterable[int]) -> "ActionTriggers"
```

Creates an ActionTriggers from an iterable of codes for every frame.

**Arguments**:

- `frame_codes`: List of trigger codes for each frame.

**Returns**:

New ActionTriggers dictionary.

**Raises**:

- `TypeError`: If a frame code is not an integer.
- `ValueError`: If a frame code is invalid.

<a name="d2animdata.Record"></a>
## Record Objects

```python
@dataclasses.dataclass
class Record()
```

Represents an AnimData record entry.

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

<a name="d2animdata.Record.make_dict"></a>
#### make\_dict

```python
 | make_dict() -> dict
```

Converts the Record to a dict that can be serialized to another format.

**Returns**:

Plain dict created from this Record.

<a name="d2animdata.Record.from_dict"></a>
#### from\_dict

```python
 | @classmethod
 | from_dict(cls, obj: dict) -> "Record"
```

Creates a new record from a dict unserialized from another format.

Trigger frame indices are automatically converted to integers in order
to support data formats that do not support integer mapping keys
(e.g. JSON).

**Arguments**:

- `obj`: Dictionary to convert to a Record.

**Returns**:

New Record object.

<a name="d2animdata.loads"></a>
#### loads

```python
loads(data: bytes) -> List[Record]
```

Loads the contents of AnimData.D2 from binary `data`.

**Arguments**:

- `data`: Contents of AnimData.D2 in binary format.

**Returns**:

List of `Record`s, ordered by their original order in the `data`.

**Raises**:

- `AnimDataError`: If the AnimData.D2 file is malformed or corrupted.

<a name="d2animdata.load"></a>
#### load

```python
load(file: BinaryIO) -> List[Record]
```

Loads the contents of AnimData.D2 from the a binary file.

**Arguments**:

- `file`: Readable file object opened in binary mode (`mode='rb'`).

**Returns**:

List of Record objects, maintaining their original order in `file`.

**Raises**:

- `AnimDataError`: If the AnimData.D2 file is malformed or corrupted.

<a name="d2animdata.dumps"></a>
#### dumps

```python
dumps(records: Iterable[Record]) -> bytearray
```

Packs AnimData records into AnimData.D2 hash table format.

**Arguments**:

- `records`: Iterable of Record objects.

**Returns**:

`bytearray` containing the packed AnimData.D2 file.

<a name="d2animdata.dump"></a>
#### dump

```python
dump(records: Iterable[Record], file: BinaryIO) -> None
```

Packs AnimData records into AnimData.D2 format and writes them to a file.

**Arguments**:

- `records`: Iterable of Record objects to write.
- `file`: Writable file object opened in binary mode (`mode='wb'`).

<a name="d2animdata.load_txt"></a>
#### load\_txt

```python
load_txt(file: Iterable[str]) -> List[Record]
```

Loads AnimData records from a tabbed text file.

**Arguments**:

- `file`: 
    A text file object, or any object which supports the iterator protocol
    and returns a string each time its `__next__()` method is called.
    If `file` is a file object, it should be opened with `newline=''`.

**Returns**:

List of `Record`s loaded from the `file`.

**Raises**:

- `TabbedTextError`: If the tabbed text file cannot be loaded.

<a name="d2animdata.dump_txt"></a>
#### dump\_txt

```python
dump_txt(records: Iterable[Record], file: TextIO) -> None
```

Saves AnimData records to a tabbed text file.

**Arguments**:

- `records`: Iterable of `Record`s to write to the `file`.
- `file`: 
    A text file object, or any any object with a `write()` method.
    If `file` is a file object, it should be opened with `newline=''`.

<a name="d2animdata.main"></a>
#### main

```python
main(argv: List[str] = None) -> None
```

Entrypoint for the CLI script.

**Arguments**:

- `argv`: List of argument strings. If not given, `sys.argv[1:]` is used.

