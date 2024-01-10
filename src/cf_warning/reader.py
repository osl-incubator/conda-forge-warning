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
from datetime import datetime, timezone



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
        """Search all feedstock repos and add days since last reply."""
        search = """
        query SearchRepos {
          search(
            query: "org:conda-forge feedstock- in:name",
            type: REPOSITORY,
            first: 100{{after}}
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
                  pullRequests(states: OPEN, first: 1, orderBy: {field: UPDATED_AT, direction: DESC}) {
                    totalCount
                    nodes {
                      updatedAt
                      comments(last: 1) {
                        nodes {
                          updatedAt
                        }
                      }
                    }
                  }
                  issues(states: OPEN, first: 1, orderBy: {field: UPDATED_AT, direction: DESC}) {
                    totalCount
                    nodes {
                      updatedAt
                      comments(last: 1) {
                        nodes {
                          updatedAt
                        }
                      }
                    }
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
            node = line["node"]
            name = node["name"]
            url = node["url"]
            open_prs = node["pullRequests"]["totalCount"]
            open_issues = node["issues"]["totalCount"]

            prs_updated_at = node["pullRequests"]["nodes"][0]["updatedAt"] if node["pullRequests"]["nodes"] else None
            issues_updated_at = node["issues"]["nodes"][0]["updatedAt"] if node["issues"]["nodes"] else None
            
            prs_comment_updated_at = node["pullRequests"]["nodes"][0]["comments"]["nodes"][0]["updatedAt"] if node["pullRequests"]["nodes"] and node["pullRequests"]["nodes"][0]["comments"]["nodes"] else None
            issues_comment_updated_at = node["issues"]["nodes"][0]["comments"]["nodes"][0]["updatedAt"] if node["issues"]["nodes"] and node["issues"]["nodes"][0]["comments"]["nodes"] else None
            
            last_reply_dates = [date for date in [prs_updated_at, issues_updated_at, prs_comment_updated_at, issues_comment_updated_at] if date is not None]
            last_reply_date = max(last_reply_dates, default=None)

            if last_reply_date:
                last_reply_date_parsed = datetime.strptime(last_reply_date, '%Y-%m-%dT%H:%M:%SZ')
                last_reply_date_parsed = last_reply_date_parsed.replace(tzinfo=timezone.utc)
                days_since_last_reply = (datetime.now(timezone.utc) - last_reply_date_parsed).days
            else:
                days_since_last_reply = None

            repo_data = {
                "name": name,
                "url": url,
                "open_prs": open_prs,
                "open_issues": open_issues,
                "days_since_last_reply": days_since_last_reply,
            }

            repos.append(repo_data)

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
