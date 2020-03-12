# d2animdata
![Build status](https://github.com/pastelmind/d2animdata/workflows/Build/badge.svg)

d2animdata is a command-line program for editing **AnimData.D2**. AnimData.D2 is a propriety file format used by [Diablo 2] to store animation metadata for characters and monsters.

d2animdata can *decompile* AnimData.D2 to text-based file formats, such as [tabbed text] and [JSON] (see [Supported File Formats] for more info). Modders can edit these files to add new animations or modify existing ones. After editing, d2animdata can *compile* it back to a new AnimData.D2 file.

d2animdata is written in Python. It supports Python 3.6 and above, and has been tested on Windows 10 and Ubuntu Linux.

⚠ This project is very much in Alpha. There may be several bugs. Always back up your AnimData.D2 file before using d2animdata.

[mod]: https://en.wikipedia.org/wiki/Mod_(video_games)
[Diablo 2]: https://en.wikipedia.org/wiki/Diablo_II
[tabbed text]: https://en.wikipedia.org/wiki/Tab-separated_values
[JSON]: https://en.wikipedia.org/wiki/JSON

## Installing

To use d2animdata, you must install [Python 3](https://www.python.org/). Then, open a command-line shell (e.g. `cmd.exe`) and enter:

```console
pip install d2animdata
```

This will install d2animdata on your computer.

## Commands

To view help for a command, enter:

```
d2animdata <command> --help
```

### decompile

Decompiles an AnimData.D2 file to tabbed text or JSON file.

```console
$ d2animdata decompile --help
usage: d2animdata decompile [-h] [--sort] (--json | --txt) animdata_d2 target

positional arguments:
  animdata_d2  AnimData.D2 file to decompile
  target       JSON or tabbed text file to save to

optional arguments:
  -h, --help   show this help message and exit
  --sort       Sort the records alphabetically before saving
  --json       Decompile to JSON
  --txt        Decompile to tabbed text (TXT)
```

Example: Decompile `path/to/AnimData.D2` to a JSON file.
```
d2animdata decompile --json path/to/AnimData.D2 path/to/my-animdata.json
```

Example: Decompile `path/to/AnimData.D2` to a tabbed text file.
```
d2animdata decompile --txt path/to/AnimData.D2 path/to/my-animdata.txt
```

### compile

Compiles a tabbed text or JSON file to AnimData.D2 file.

```console
$ d2animdata compile --help
usage: d2animdata compile [-h] [--sort] (--json | --txt) source animdata_d2

positional arguments:
  source       JSON or tabbed text file to compile
  animdata_d2  AnimData.D2 file to save to

optional arguments:
  -h, --help   show this help message and exit
  --sort       Sort the records alphabetically before saving
  --json       Compile JSON
  --txt        Compile tabbed text (TXT)
```

Example: Compile a JSON file to `path/to/AnimData-result.D2`.
```
d2animdata compile --json path/to/my-animdata.json path/to/AnimData-result.D2
```

Example: Compile a tabbed text file to `path/to/AnimData-result.D2`.
```
d2animdata compile --txt path/to/my-animdata.txt path/to/AnimData-result.D2
```

## Supported File Formats
[Supported File Formats]: #file-formats

d2animdata supports two file formats: [tabbed text] (`.txt`) and JSON (`.json`).

### Tabbed text
Tabbed text files (`.txt`) can be edited with a spreadsheet program (e.g. Excel, AFJ Sheet Edit). Diablo 2 modders should already be familiar with these files, as Diablo 2 uses tabbed text files extensively to control various aspects of the game.

d2animdata is compatible with Paul Siramy's excellent `animdata_edit` program, which is another popular tool for (de)compiling AnimData.D2 to tabbed text.

### JSON
JSON files (`.json`) can be edited with any text editor (e.g. Notepad), though I recommend using one with syntax highlighting support (e.g. Notepad++, Visual Studio Code).

JSON has several advantages over tabbed text:

* JSON files can be added to a [version control system] (VCS), such as Git. This allows you to keep track of changes made to a file. You can compare changes across time and revert unwanted changes.

    Tabbed text files and AnimData.D2 can also be added to a VCS. However, tabbed text files are tricky to deal with, because they don't produce nice-looking diff logs when compared. Binary files, such as AnimData.D2, cannot be compared at all. On the other hand, JSON files create diff logs that are easy to read.
* JSON files are easier to handle in several programming languages.
* Unlike tabbed text, JSON does not suffer from tricky whitespace issues.

[version control system]: https://en.wikipedia.org/wiki/Version_control

## API Usage

d2animdata can also be imported from a Python script to load, edit, and save AnimData.D2.

Example:

```python
from d2animdata import load, dump

# Load an AnimData.D2 file
with open('AnimData.D2', mode='rb') as animdata_file:
    animdata = load(animdata_file)
# animdata now contains a list of Record objects.

# Iterate through each record, printing its information
for record in animdata:
    print('COF name:', record.cof_name)
    print('Frames per direction:', record.frames_per_direction)
    print('Animation speed:', record.animation_speed)
    print('Trigger frames:', record.triggers)

# Let's find a record named '0DNUHTH' and edit it
for record in animdata:
    if record.cof_name == '0DNUHTH':
        record.animation_speed = 192
        # Erase all trigger frames previously set on this record.
        record.triggers.clear()
        # Set the trigger code of frame #10 to 1
        # Since frame indices begin at 0, we're actually modifying the 11th frame.
        record.triggers[10] = 1
        break

# Save the records to AnimData.D2
with open('AnimData.D2', mode='wb') as animdata_file:
    dump(animdata, animdata_file)
```

See the [API docs](./api.md) for a complete reference of available functions and classes.

## Development

To develop d2animdata, you will want a good Python editor. I recommend [Visual Studio Code] with the [Microsoft Python extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python).

To develop d2animdata, clone this repository and create a [virtual environment]. Then run the following command to install development dependencies:

```sh
# For Windows
python -m pip install -r requirements-dev.txt
# For non-Windows
pip install -r requirements-dev.txt
```

d2animdata uses:

* [Flit] to build source distributions and wheels.
* [Tox] to run tests.
* [Black] and [isort] to format code.
* [Pylint] to check code.
* [pydocmd] to generate API documentation from source code.
    * Run `pydocmd generate` to generate `api.md`.

[Black]: https://github.com/psf/black
[Flit]: https://flit.readthedocs.io/
[isort]: https://timothycrosley.github.io/isort/
[pydocmd]: https://niklasrosenstein.github.io/pydoc-markdown/
[Pylint]: https://www.pylint.org/
[Tox]: https://tox.readthedocs.io/
[virtual environment]: https://packaging.python.org/tutorials/installing-packages/#creating-virtual-environments
[Visual Studio Code]: https://code.visualstudio.com/
