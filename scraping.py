import requests
import pandas as pd
import time
import logging
from typing import List, Dict, Any, Optional


class GitHubScraper:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.setup_logger()

    @staticmethod
    def setup_logger():
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        return logging.getLogger(__name__)

    def make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict]:
        url = f"{self.BASE_URL}/{endpoint}"
        while True:
            try:
                response = requests.get(
                    url, headers=self.headers, params=params, timeout=10
                )
                logging.info(
                    f"Requesting: {url}, Params: {params}, Status: {response.status_code}"
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 403:
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    sleep_duration = max(reset_time - time.time(), 0) + 1
                    logging.warning(
                        f"Rate limit exceeded, retrying in {sleep_duration} seconds..."
                    )
                    time.sleep(sleep_duration)
                else:
                    response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logging.error(f"Request failed: {e}")
                time.sleep(5)

    def search_users(self, location: str, min_followers: int) -> List[Dict]:
        users, page = [], 1
        query = f"location:{location} followers:>={min_followers}"

        while True:
            params = {"q": query, "per_page": 100, "page": page}
            data = self.make_request("search/users", params=params)
            items = data.get("items", []) if data else []

            if not items:
                break

            for user_info in items:
                user_data = self.make_request(f"users/{user_info['login']}")
                if user_data:
                    users.append(self.extract_user_data(user_data))

            page += 1

        logging.info(f"Found {len(users)} users")
        return users

    @staticmethod
    def extract_user_data(data: Dict) -> Dict:
        return {
            "login": data["login"],
            "name": data.get("name", ""),
            "company": GitHubScraper.clean_company_name(data.get("company")),
            "location": data.get("location", ""),
            "email": data.get("email", ""),
            "hireable": data.get("hireable", False),
            "bio": data.get("bio", ""),
            "public_repos": data.get("public_repos", 0),
            "followers": data.get("followers", 0),
            "following": data.get("following", 0),
            "created_at": data.get("created_at", ""),
        }

    @staticmethod
    def clean_company_name(company: Optional[str]) -> str:
        return company.strip().lstrip("@").upper() if company else ""

    def get_user_repositories(self, username: str, max_repos: int = 500) -> List[Dict]:
        repos, page = [], 1

        while len(repos) < max_repos:
            params = {
                "sort": "pushed",
                "direction": "desc",
                "per_page": 100,
                "page": page,
            }
            user_repos = self.make_request(f"users/{username}/repos", params=params)

            if not user_repos:
                break

            for repo in user_repos:
                repos.append(self.extract_repo_data(username, repo))

            if len(user_repos) < 100:
                break
            page += 1

        return repos[:max_repos]

    @staticmethod
    def extract_repo_data(username: str, repo_data: Dict) -> Dict:
        return {
            "login": username,
            "full_name": repo_data["full_name"],
            "created_at": repo_data["created_at"],
            "stargazers_count": repo_data["stargazers_count"],
            "watchers_count": repo_data["watchers_count"],
            "language": repo_data.get("language", ""),
            "has_projects": repo_data.get("has_projects", False),
            "has_wiki": repo_data.get("has_wiki", False),
            "license_name": repo_data.get("license", {}).get("key", ""),
        }

    def save_to_csv(self, filename: str, data: List[Dict]) -> None:
        pd.DataFrame(data).to_csv(filename, index=False)
        logging.info(f"Data saved to {filename}")


def main():
    token = input("Enter your GitHub token: ").strip()
    if not token:
        print("Token is required. Exiting...")
        return

    scraper = GitHubScraper(token)
    users = scraper.search_users(location="Sydney", min_followers=100)

    if users:
        scraper.save_to_csv("users.csv", users)

        all_repos = []
        for user in users:
            repos = scraper.get_user_repositories(user["login"])
            all_repos.extend(repos)

        scraper.save_to_csv("repositories.csv", all_repos)
        logging.info(f"Scraped {len(users)} users and {len(all_repos)} repositories")

    else:
        logging.warning("No users found matching the criteria.")


if __name__ == "__main__":
    main()
