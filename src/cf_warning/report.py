"""Report module."""
import asyncio
import os
from pathlib import Path
from typing import cast

import dotenv
import pandas as pd

from cf_warning.reader import CondaForgeGitHubReader


class CondaForgeWarning:
    """Conda Forge Warning class."""

    reader: CondaForgeGitHubReader

    def __init__(self) -> None:
        """Instantiate the CondaForgeWarning."""
        self.token = ""
        self._load_token()
        self.reader = CondaForgeGitHubReader(self.token)

    def _load_token(self) -> None:
        """Load the GitHub token."""
        env_file = ".env"

        if not env_file:
            gh_token = os.getenv("GITHUB_TOKEN", "")

            if gh_token:
                raise Exception(
                    "`GITHUB_TOKEN` environment variable not found"
                )

            self.token = gh_token
            return

        if not env_file.startswith("/"):
            # use makim file as reference for the working directory
            # for the .env file
            env_file = str(Path(os.getcwd()) / env_file)

        if not Path(env_file).exists():
            raise Exception(
                f"[EE] The given env-file ({env_file}) was not found."
            )

        envs = dotenv.dotenv_values(env_file)
        gh_token = cast(str, envs.get("GITHUB_TOKEN", ""))

        if not gh_token:
            raise Exception("`GITHUB_TOKEN` environment variable not found")

        self.token = gh_token

    def run(self) -> None:
        """Generate the report."""
        asyncio.run(self.run_async())

    def apply_criteria(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
        """Apply criteria to prepare the groups of data for the report."""
        criteria = {
            "critical": (lambda data: data[data["open_prs"] >= 10]),
            "danger": (
                lambda data: data[
                    (5 <= data["open_prs"]) & (data["open_prs"] < 10)
                ]
            ),
            "warning": (
                lambda data: data[
                    (data["open_prs"] < 5) | (data["open_issues"] < 5)
                ]
            ),
        }

        return {level: fn_filter(df) for level, fn_filter in criteria.items()}

    async def run_async(self):
        """Generate the report in async mode."""
        data = await self.reader.get_data()
        index_path = Path(__file__).parent.parent.parent / "docs" / "index.md"

        data_segmented = self.apply_criteria(data)
        content = "# Conda-Forge Warning Panel\n\n"

        for level, df in data_segmented.items():
            table = df.reset_index(drop=True).to_markdown()
            content += f"\n## {level.upper()}\n\n{table}\n"

        with open(index_path, "w") as f:
            f.write(content)
