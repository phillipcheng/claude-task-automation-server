import subprocess
import os
from pathlib import Path
from typing import Optional, Tuple
import shutil


class GitWorktreeManager:
    """Manages git worktrees for parallel task execution."""

    def __init__(self, base_repo_path: str):
        """
        Initialize worktree manager for a repository.

        Args:
            base_repo_path: Path to the main git repository
        """
        self.base_repo_path = base_repo_path
        self.worktrees_dir = os.path.join(base_repo_path, ".claude_worktrees")

    def create_worktree(
        self, task_name: str, branch_name: Optional[str] = None, base_branch: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        Create a git worktree for a task.

        Args:
            task_name: Name of the task (used for worktree directory name)
            branch_name: Branch to checkout (creates new branch if doesn't exist)
            base_branch: Branch to branch off from (e.g., main, develop, master)

        Returns:
            Tuple of (success, worktree_path, message)
        """
        if not self._is_git_repo(self.base_repo_path):
            return False, "", "Not a git repository"

        # Create worktrees directory if it doesn't exist
        os.makedirs(self.worktrees_dir, exist_ok=True)

        # Sanitize task name for directory
        safe_task_name = task_name.replace("/", "_").replace(" ", "_")
        worktree_path = os.path.join(self.worktrees_dir, safe_task_name)

        # Check if worktree already exists
        if os.path.exists(worktree_path):
            return False, worktree_path, f"Worktree already exists at {worktree_path}"

        try:
            if branch_name:
                # Create worktree with specific branch
                # Determine the starting point for the new branch
                start_point = base_branch if base_branch else "HEAD"

                # Try to create new branch from base_branch
                result = subprocess.run(
                    ["git", "worktree", "add", "-b", branch_name, worktree_path, start_point],
                    cwd=self.base_repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    # Branch might already exist, try without -b
                    result = subprocess.run(
                        ["git", "worktree", "add", worktree_path, branch_name],
                        cwd=self.base_repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )

                if result.returncode != 0:
                    return False, "", f"Failed to create worktree: {result.stderr}"
            else:
                # Create worktree on current branch or base_branch
                if not base_branch:
                    base_branch = self._get_current_branch(self.base_repo_path)
                    if not base_branch:
                        base_branch = "main"

                # Create new branch for this task from base_branch
                task_branch = f"task/{safe_task_name}"
                result = subprocess.run(
                    ["git", "worktree", "add", "-b", task_branch, worktree_path, base_branch],
                    cwd=self.base_repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    return False, "", f"Failed to create worktree: {result.stderr}"

                branch_name = task_branch

            return True, worktree_path, f"Created worktree for branch '{branch_name}' from '{base_branch or 'HEAD'}'"

        except subprocess.TimeoutExpired:
            return False, "", "Git worktree command timed out"
        except Exception as e:
            return False, "", f"Error creating worktree: {str(e)}"

    def remove_worktree(self, task_name: str, force: bool = False) -> Tuple[bool, str]:
        """
        Remove a git worktree.

        Args:
            task_name: Name of the task
            force: Force removal even if worktree has uncommitted changes

        Returns:
            Tuple of (success, message)
        """
        safe_task_name = task_name.replace("/", "_").replace(" ", "_")
        worktree_path = os.path.join(self.worktrees_dir, safe_task_name)

        if not os.path.exists(worktree_path):
            return False, f"Worktree not found at {worktree_path}"

        try:
            cmd = ["git", "worktree", "remove", worktree_path]
            if force:
                cmd.append("--force")

            result = subprocess.run(
                cmd,
                cwd=self.base_repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                # Try to remove directory manually if git command fails
                if force:
                    shutil.rmtree(worktree_path, ignore_errors=True)
                    # Prune worktree list
                    subprocess.run(
                        ["git", "worktree", "prune"],
                        cwd=self.base_repo_path,
                        capture_output=True,
                        timeout=10
                    )
                    return True, f"Force removed worktree at {worktree_path}"
                return False, f"Failed to remove worktree: {result.stderr}"

            return True, f"Removed worktree at {worktree_path}"

        except Exception as e:
            return False, f"Error removing worktree: {str(e)}"

    def list_worktrees(self) -> list[dict]:
        """
        List all git worktrees.

        Returns:
            List of worktree info dicts
        """
        if not self._is_git_repo(self.base_repo_path):
            return []

        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.base_repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return []

            worktrees = []
            current_worktree = {}

            for line in result.stdout.split("\n"):
                line = line.strip()
                if not line:
                    if current_worktree:
                        worktrees.append(current_worktree)
                        current_worktree = {}
                    continue

                if line.startswith("worktree "):
                    current_worktree["path"] = line.split("worktree ", 1)[1]
                elif line.startswith("branch "):
                    current_worktree["branch"] = line.split("branch ", 1)[1]
                elif line.startswith("HEAD "):
                    current_worktree["commit"] = line.split("HEAD ", 1)[1]

            if current_worktree:
                worktrees.append(current_worktree)

            return worktrees

        except Exception:
            return []

    def cleanup_worktrees(self) -> Tuple[int, str]:
        """
        Clean up stale worktrees.

        Returns:
            Tuple of (count_cleaned, message)
        """
        try:
            result = subprocess.run(
                ["git", "worktree", "prune", "-v"],
                cwd=self.base_repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Count lines in output
                lines = [l for l in result.stdout.split("\n") if l.strip()]
                return len(lines), f"Cleaned up {len(lines)} stale worktrees"
            else:
                return 0, "No worktrees to clean up"

        except Exception as e:
            return 0, f"Error during cleanup: {str(e)}"

    def get_worktree_path(self, task_name: str) -> Optional[str]:
        """
        Get the path to a worktree for a task.

        Args:
            task_name: Name of the task

        Returns:
            Path to worktree or None if not found
        """
        safe_task_name = task_name.replace("/", "_").replace(" ", "_")
        worktree_path = os.path.join(self.worktrees_dir, safe_task_name)

        if os.path.exists(worktree_path):
            return worktree_path
        return None

    def _is_git_repo(self, path: str) -> bool:
        """Check if path is a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=path,
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _get_current_branch(self, path: str) -> Optional[str]:
        """Get current branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    @staticmethod
    def is_worktree_supported(repo_path: str) -> bool:
        """
        Check if git worktree is supported (git version >= 2.5).

        Returns:
            True if worktree is supported
        """
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                version_str = result.stdout.strip()
                # Extract version number (e.g., "git version 2.30.1" -> "2.30.1")
                parts = version_str.split()
                if len(parts) >= 3:
                    version = parts[2].split(".")
                    major = int(version[0])
                    minor = int(version[1]) if len(version) > 1 else 0

                    # Worktree introduced in git 2.5
                    return major > 2 or (major == 2 and minor >= 5)

        except Exception:
            pass

        return False
