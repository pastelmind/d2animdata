#!/usr/bin/env python
"""Setup script for d2animdata."""

import re

from setuptools import setup


def read(path: str) -> str:
    """Reads and returns the contents of a file."""
    with open(path, encoding="utf-8") as file:
        return file.read()


# Based on https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
def find_meta(meta: str) -> str:
    """
    Extract __*meta*__ from META_FILE.
    """
    meta_match = re.search(
        r"^__{meta}__ = ['\"]([^'\"]*)['\"]".format(meta=meta), META_FILE, re.M
    )
    if meta_match:
        return meta_match.group(1)
    raise RuntimeError("Unable to find __{meta}__ string.".format(meta=meta))


META_FILE = read("d2animdata.py")


setup(
    name="d2animdata",
    version=find_meta("version"),
    author="pastelmind",
    author_email="keepyourhonor@gmail.com",
    description="Converts AnimData.D2 to and from text-based formats.",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    url="https://github.com/pastelmind/d2animdata",
    py_modules=["d2animdata"],
    entry_points={"console_scripts": "d2animdata = d2animdata:main"},
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
)
