import asyncio
import aiohttp
import os
import subprocess
import sys
from datetime import datetime
from manifold.architect import ArchitectNode

class RepoWatcher:
    """
    Manages the 'Auto-Pull' and 'Strict Version Control' of the Manifold Architecture.
    Polls GitHub for merged PRs related to Architect issues, automatically pulls,
    increments semantic versioning, gracefully restarts the middleware, and polls for open
    issues to orchestrate autonomous AI-to-AI negotiation loops.

    Attributes:
        github_repo (str): "owner/repo" from env vars.
        github_token (str): Personal Access Token from env vars.
        poll_interval (int): How often to check for merged PRs (default 3600s / 1h).
        architect (ArchitectNode): Reference to the architect node for answering queries.
    """

    def __init__(self, poll_interval: int = 3600, architect: ArchitectNode = None):
        self.github_repo = os.environ.get("GITHUB_REPOSITORY")
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.poll_interval = poll_interval
        self.architect = architect if architect else ArchitectNode()

        self._is_running = False
        self._task: asyncio.Task | None = None
        self._last_checked = datetime.utcnow().isoformat() + "Z"
        self._bot_username = None

    def start(self):
        """Starts the background repository polling loop."""
        if not self.github_repo or not self.github_token:
            print("[RepoWatcher] Disabled: GITHUB_REPOSITORY or GITHUB_TOKEN environment variables missing.")
            return

        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._loop())
            print(f"[RepoWatcher] Started. Polling GitHub every {self.poll_interval}s.")

    def stop(self):
        """Stops the background polling loop."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            print("[RepoWatcher] Stopped.")

    async def _get_bot_username(self):
        """Fetches the authenticated user's GitHub username to prevent self-reply loops."""
        if self._bot_username:
             return

        url = "https://api.github.com/user"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._bot_username = data.get("login")
                        print(f"[RepoWatcher] Authenticated as GitHub user: {self._bot_username}")
        except Exception as e:
             print(f"[RepoWatcher] Error fetching bot username: {e}")

    async def _loop(self):
        """The continuous background loop polling for merged PRs and open issue questions."""
        await self._get_bot_username()

        while self._is_running:
            try:
                await self.check_for_updates()
                await self.check_for_questions()
            except Exception as e:
                print(f"[RepoWatcher] Polling Error: {e}")

            await asyncio.sleep(self.poll_interval)

    async def check_for_updates(self):
        """
        Polls the GitHub REST API for recently closed/merged Pull Requests.
        If a new merge is detected since last check, trigger the auto-pull sequence.
        """
        # Search for merged PRs in the repo targeting 'main' branch since last check
        url = f"https://api.github.com/repos/{self.github_repo}/pulls?state=closed&sort=updated&direction=desc"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    prs = await response.json()
                    for pr in prs:
                        merged_at = pr.get("merged_at")
                        if merged_at and merged_at > self._last_checked:
                            print(f"[RepoWatcher] New Merge Detected! PR #{pr.get('number')} '{pr.get('title')}'. Triggering Auto-Pull...")

                            # Update last checked timestamp
                            self._last_checked = datetime.utcnow().isoformat() + "Z"

                            # Execute the evolution sequence
                            success = self._execute_pull_and_version()
                            if success:
                                self._graceful_restart()

                            # We only handle one major update per poll cycle to avoid race conditions
                            break
                else:
                    print(f"[RepoWatcher] API Error {response.status}: {await response.text()}")

    async def check_for_questions(self):
        """
        Polls open GitHub Issues to detect clarifying questions from cloud agents (e.g. Jules).
        Triggers Architect autonomous replies if the last comment is not from the bot.
        """
        url = f"https://api.github.com/repos/{self.github_repo}/issues?state=open"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        issues = await response.json()
                        for issue in issues:
                            # We only care about open issues we created or are engaged with
                            # Check if the issue has comments
                            if issue.get("comments", 0) > 0:
                                comments_url = issue.get("comments_url")

                                # Fetch comments
                                async with session.get(comments_url, headers=headers) as comments_resp:
                                    if comments_resp.status == 200:
                                        comments = await comments_resp.json()
                                        if comments:
                                            last_comment = comments[-1]
                                            author = last_comment.get("user", {}).get("login")

                                            # Ensure we don't reply to our own last comment (infinite loop prevention)
                                            if author and author != self._bot_username:
                                                issue_number = issue.get("number")
                                                issue_title = issue.get("title", "")
                                                issue_body = issue.get("body", "")
                                                comment_body = last_comment.get("body", "")

                                                print(f"[RepoWatcher] Detected open question on Issue #{issue_number} from {author}. Triggering Architect...")
                                                # Dispatch the task to the Architect node
                                                asyncio.create_task(
                                                    self.architect.generate_and_post_reply(
                                                        issue_number, issue_title, issue_body, author, comment_body
                                                    )
                                                )
        except Exception as e:
            print(f"[RepoWatcher] Error checking for questions: {e}")

    def _execute_pull_and_version(self) -> bool:
        """
        Executes `git pull origin main` and manages strict semantic versioning.
        Returns True if successful, False if git pull failed.
        """
        print("[RepoWatcher] Executing `git pull origin main`...")

        try:
            # Execute pull and capture output
            result = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True, check=True)
            print(f"[RepoWatcher] Git Pull Output: {result.stdout.strip()}")

            # Increment Semantic Versioning
            version_file = "VERSION.txt"
            current_version = "V1.0"

            if os.path.exists(version_file):
                with open(version_file, "r") as f:
                    current_version = f.read().strip()
            else:
                print(f"[RepoWatcher] Warning: {version_file} missing. Starting at V1.0")

            # Parse Version (e.g. "V1.2")
            try:
                parts = current_version.replace("V", "").split(".")
                major = int(parts[0])
                minor = int(parts[1]) if len(parts) > 1 else 0

                # Increment minor by 1
                minor += 1

                # Roll over .9 to the next whole number
                if minor > 9:
                    minor = 0
                    major += 1

                new_version = f"V{major}.{minor}"

                # Write back
                with open(version_file, "w") as f:
                     f.write(new_version)

                print(f"[RepoWatcher] Evolution Complete. Version incremented from {current_version} to {new_version}.")

            except ValueError:
                print(f"[RepoWatcher] Error parsing version string '{current_version}'. Keeping current version.")

            return True

        except subprocess.CalledProcessError as e:
             print(f"[RepoWatcher] Git Pull Failed:\n{e.stderr.strip()}")
             return False

    def _graceful_restart(self):
        """
        Restarts the Python middleware process gracefully using os.execv so new code takes effect.
        """
        print("[RepoWatcher] Initiating graceful restart of the Manifold Middleware...")

        # Stop background tasks (self)
        self.stop()

        # Flush stdout to ensure logs are written before execv takes over
        sys.stdout.flush()

        # Execute the same script with the same arguments, replacing the current process
        # Start a new process and let the current one exit
        try:
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit(0)
        except Exception as e:
            print(f"[RepoWatcher] Critical Error during restart: {e}")
            sys.exit(1)
