"""Read information from Github API using GraphQL GitHubAPI."""
from public import public

from cf_warning.report import CondaForgeWarning


@public
def main() -> None:
    """Generate the Conda-Forge Warning report."""
    report = CondaForgeWarning()
    report.run()


if __name__ == "__main__":
    main()
