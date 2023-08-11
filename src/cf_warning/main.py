#!/usr/bin/env python
"""
Read information from Github API using GraphQL GitHubAPI.
"""
import asyncio

from public import public

from cf_warning.report import CondaForgeWarning
from cf_warning.cli import parse_cli
from cf_warning.config import ArgsCLI


def main() -> None:
    report = CondaForgeWarning()
    report.run()


if __name__ == "__main__":
    main()
