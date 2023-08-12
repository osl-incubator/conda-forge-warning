"""
Reader class reads data from GitHub using GraphQL.

Note: **dict approach is not working properly with mypy for dataclass:
  https://github.com/python/mypy/issues/5382
"""
from __future__ import annotations

from typing import Dict

import pandas as pd
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from jinja2 import Template
from public import public


class GitHubGraphQL:
    """Store token and the query transport for GitHubGraphQL."""

    token: str
    transport: AIOHTTPTransport

    def __init__(self, token):
        """Instantiate GitHubGraphQL."""
        self.token = token
        self.transport = AIOHTTPTransport(
            headers={"Authorization": f"bearer {self.token}"},
            url="https://api.github.com/graphql",
        )


class CondaForgeGitHubSearch:
    """Conda-Forge GitHub Search class."""

    ghgql: GitHubGraphQL

    def __init__(self, token: str) -> None:
        """Instantiate CondaForgeGitHubSearch."""
        self.ghgql = GitHubGraphQL(token)

    async def pagination(
        self, gql_tmpl: str, variables: Dict[str, str]
    ) -> pd.DataFrame:
        """Paginate the GitHub GraphQL search."""
        has_next_page = True
        pagination_after = ""
        results = []
        has_result = False

        tmpl = Template(gql_tmpl)

        async with Client(
            transport=self.ghgql.transport,
            fetch_schema_from_transport=True,
        ) as session:
            while has_next_page:
                _variables = dict(variables)
                _variables.update(
                    after=""
                    if not pagination_after
                    else f', after: "{pagination_after}"'
                )

                gql_stmt = tmpl.render(**_variables)

                query = gql(gql_stmt)
                # todo: variable_values={"first": limit}
                result = await session.execute(query)

                try:
                    page_info = result["search"]["pageInfo"]
                    has_next_page = page_info["hasNextPage"]
                    pagination_after = page_info["endCursor"]
                    has_result = True
                except (KeyError, IndexError):
                    has_next_page = False
                    has_result = False

                if not has_result:
                    break

                results += result["search"]["edges"]

        return results

    async def search_all_repos_feedstock(self) -> pd.DataFrame:
        """Search all feedstock repos."""
        search = """
        query {
            search(
                query: "{{search_query}}",
                type: REPOSITORY,
                first: 100 {{after}}
            ) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        ... on Repository {
                            name
                            url
                            pullRequests(states: OPEN) {
                                totalCount
                            }
                            issues(states: OPEN) {
                                totalCount
                            }
                        }
                    }
                }
            }
        }
        """

        variables = {
            "search_query": "org:conda-forge feedstock- in:name",
        }

        results = await self.pagination(search, variables)

        repos = []
        for line in results:
            repos.append(
                {
                    "name": line["node"]["name"],
                    "url": line["node"]["url"],
                    "open_prs": line["node"]["pullRequests"]["totalCount"],
                    "open_issues": line["node"]["issues"]["totalCount"],
                }
            )

        return pd.DataFrame(repos)


@public
class CondaForgeGitHubReader:
    """CondaForgeGitHubReader."""

    token: str

    def __init__(self, token: str) -> None:
        """Instantiate CondaForgeGitHubReader."""
        self.token = token

    async def get_data(self) -> pd.DataFrame:
        """Return all the data used for the report."""
        token = self.token
        if not token:
            raise Exception("Invalid GitHub token.")

        gh_searcher = CondaForgeGitHubSearch(token)

        repos = await gh_searcher.search_all_repos_feedstock()

        # remove packages with no open issues or prs
        repos = repos[
            (repos.open_prs > 0) & (repos.open_issues > 0)
        ].reset_index(drop=True)

        return repos.sort_values(
            by=["open_prs", "open_issues", "name"],
            ascending=[False, False, True],
            ignore_index=True,
        )
