import subprocess
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, List
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
            # Verify it's actually a valid worktree
            existing_worktrees = self.list_worktrees()
            is_valid_worktree = any(wt.get("path") == worktree_path for wt in existing_worktrees)

            if is_valid_worktree:
                return False, worktree_path, f"Worktree already exists at {worktree_path}"
            else:
                # Stale directory exists, remove it
                print(f"🔧 Removing stale directory at {worktree_path} (not a valid worktree)")
                shutil.rmtree(worktree_path, ignore_errors=True)
                # Continue with worktree creation...

        try:
            if branch_name:
                # Check if branch is already checked out in another worktree
                existing_worktrees = self.list_worktrees()
                for wt in existing_worktrees:
                    if wt.get("branch", "").endswith(f"/{branch_name}") or wt.get("branch") == f"refs/heads/{branch_name}":
                        # Branch is already checked out in another worktree, reuse it
                        existing_path = wt.get("path")
                        if existing_path and os.path.exists(existing_path):
                            return True, existing_path, f"Reusing existing worktree at {existing_path} for branch '{branch_name}'"

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

    def create_multi_project_worktrees(
        self,
        task_name: str,
        projects: List[Dict[str, str]],
        base_branch: Optional[str] = None
    ) -> Tuple[bool, Dict[str, str], str]:
        """
        Create multiple worktrees for multi-project tasks.

        Args:
            task_name: Name of the task (used for worktree directory naming)
            projects: List of project configs, e.g.:
                [
                    {"path": "/path/to/project1", "access": "write", "context": "Main service", "branch_name": "feature-branch"},
                    {"path": "/path/to/project2", "access": "write", "context": "SDK project"}
                ]
            base_branch: Branch to branch off from (e.g., main, develop, master)

        Returns:
            Tuple of (success, project_worktree_paths, message)
            where project_worktree_paths is a dict: {"project_path": "worktree_path"}
        """
        project_worktree_paths = {}
        messages = []
        overall_success = True

        # Only create worktrees for projects with "write" access
        write_projects = [p for p in projects if p.get("access") == "write"]

        if not write_projects:
            return True, {}, "No projects require worktree isolation (no write access projects)"

        for project in write_projects:
            project_path = project.get("path")
            project_branch = project.get("branch_name")
            project_type = project.get("project_type", "other")

            if not project_path:
                messages.append(f"Skipping project with missing path")
                continue

            # Skip worktree creation for IDL projects - use default branch directly
            if project_type == "idl":
                messages.append(f"Skipping worktree for IDL project: {project_path} (using default branch)")
                project_worktree_paths[project_path] = project_path
                continue

            if not self._is_git_repo(project_path):
                messages.append(f"Skipping non-git project: {project_path}")
                # For non-git projects with write access, use original path directly
                project_worktree_paths[project_path] = project_path
                continue

            # Create a GitWorktreeManager for this project
            project_wt_manager = GitWorktreeManager(project_path)

            # Generate a unique branch name for this task if not specified
            if not project_branch:
                safe_task_name = task_name.replace("/", "_").replace(" ", "_")
                project_branch = f"task/{safe_task_name}"

            # Use project-specific base_branch if available, otherwise fall back to global base_branch
            project_base_branch = project.get("base_branch", base_branch)

            # Create worktree for this project
            success, worktree_path, message = project_wt_manager.create_worktree(
                task_name=task_name,
                branch_name=project_branch,
                base_branch=project_base_branch
            )

            if success:
                project_worktree_paths[project_path] = worktree_path
                messages.append(f"Project {project_path}: {message}")
            else:
                overall_success = False
                messages.append(f"Project {project_path}: FAILED - {message}")
                # If worktree creation fails, fall back to original project path
                project_worktree_paths[project_path] = project_path

        # For read-only projects, use their original paths
        read_projects = [p for p in projects if p.get("access") == "read"]
        for project in read_projects:
            project_path = project.get("path")
            if project_path:
                project_worktree_paths[project_path] = project_path

        combined_message = "; ".join(messages) if messages else "No worktrees needed"
        return overall_success, project_worktree_paths, combined_message

    def _commit_worktree_changes(self, worktree_path: str, task_name: str) -> Tuple[bool, str]:
        """
        Commit any uncommitted changes in a worktree before removal to prevent data loss.

        Args:
            worktree_path: Path to the worktree directory
            task_name: Name of the task for commit message

        Returns:
            Tuple of (success, message)
        """
        if not os.path.exists(worktree_path):
            return True, "Worktree path does not exist"

        try:
            # Check if there are any changes to commit
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if status_result.returncode != 0:
                return False, f"Failed to check git status: {status_result.stderr}"

            # If no changes, nothing to commit
            if not status_result.stdout.strip():
                return True, "No changes to commit"

            # Add all changes
            add_result = subprocess.run(
                ["git", "add", "."],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if add_result.returncode != 0:
                return False, f"Failed to add changes: {add_result.stderr}"

            # Create commit message
            commit_msg = f"Auto-commit changes before worktree cleanup for task: {task_name}\n\nThis commit preserves work done in the task worktree before removal."

            # Commit changes
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if commit_result.returncode != 0:
                # Check if it's just "nothing to commit" after git add
                if "nothing to commit" in commit_result.stdout:
                    return True, "No changes to commit after git add"
                return False, f"Failed to commit changes: {commit_result.stderr}"

            return True, f"Successfully committed changes: {commit_result.stdout.strip()}"

        except subprocess.TimeoutExpired:
            return False, "Git command timed out while committing changes"
        except Exception as e:
            return False, f"Error committing changes: {str(e)}"

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
            return True, f"Worktree already removed (not found at {worktree_path})"

        # First, commit any uncommitted changes to prevent data loss
        commit_success, commit_msg = self._commit_worktree_changes(worktree_path, task_name)
        commit_messages = []
        if not commit_success:
            # If commit fails, warn but don't fail the removal unless force=False
            commit_messages.append(f"Warning: Failed to commit changes: {commit_msg}")
            if not force:
                return False, f"Cannot remove worktree with uncommitted changes. {commit_msg}. Use force=True to override."
        elif "Successfully committed" in commit_msg:
            commit_messages.append(f"Committed changes: {commit_msg}")

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
                # Check if the error is about worktree not found
                if "not a working tree" in result.stderr or "No such file or directory" in result.stderr:
                    # Directory exists but is not a valid worktree - remove it manually if force is enabled
                    if os.path.exists(worktree_path) and force:
                        print(f"🔧 Removing stale directory at {worktree_path} (git reported not a working tree)")
                        shutil.rmtree(worktree_path, ignore_errors=True)
                        # Prune worktree list to clean up references
                        subprocess.run(
                            ["git", "worktree", "prune"],
                            cwd=self.base_repo_path,
                            capture_output=True,
                            timeout=10
                        )
                        final_msg = f"Removed stale directory at {worktree_path}"
                        if commit_messages:
                            final_msg = f"{'; '.join(commit_messages)}; {final_msg}"
                        return True, final_msg
                    return True, f"Worktree already removed (git reported not found)"

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
                    final_msg = f"Force removed worktree at {worktree_path}"
                    if commit_messages:
                        final_msg = f"{'; '.join(commit_messages)}; {final_msg}"
                    return True, final_msg
                return False, f"Failed to remove worktree: {result.stderr}"

            final_msg = f"Removed worktree at {worktree_path}"
            if commit_messages:
                final_msg = f"{'; '.join(commit_messages)}; {final_msg}"
            return True, final_msg

        except Exception as e:
            return False, f"Error removing worktree: {str(e)}"

    def delete_branch(self, branch_name: str, force: bool = False) -> Tuple[bool, str]:
        """
        Delete a git branch.

        Args:
            branch_name: Name of the branch to delete
            force: Force deletion even if branch has unmerged changes

        Returns:
            Tuple of (success, message)
        """
        try:
            cmd = ["git", "branch", "-d", branch_name]
            if force:
                cmd[2] = "-D"  # Force delete

            result = subprocess.run(
                cmd,
                cwd=self.base_repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                # Check if the error is about branch not found - this is not an error
                if "not found" in result.stderr or "does not exist" in result.stderr:
                    return True, f"Branch '{branch_name}' already removed (not found)"
                return False, f"Failed to delete branch '{branch_name}': {result.stderr}"

            return True, f"Deleted branch '{branch_name}'"

        except Exception as e:
            return False, f"Error deleting branch: {str(e)}"

    def cleanup_task_worktree_and_branch(self, task_name: str, force: bool = True) -> Tuple[bool, str]:
        """
        Clean up both worktree and branch for a task.

        Args:
            task_name: Name of the task
            force: Force cleanup even if there are uncommitted changes

        Returns:
            Tuple of (success, message)
        """
        messages = []
        overall_success = True

        # Remove worktree first
        worktree_success, worktree_msg = self.remove_worktree(task_name, force=force)
        messages.append(f"Worktree: {worktree_msg}")
        if not worktree_success:
            overall_success = False

        # Delete the task branch (follows pattern task/{safe_task_name})
        safe_task_name = task_name.replace("/", "_").replace(" ", "_")
        branch_name = f"task/{safe_task_name}"

        branch_success, branch_msg = self.delete_branch(branch_name, force=force)
        messages.append(f"Branch: {branch_msg}")
        if not branch_success:
            overall_success = False

        return overall_success, "; ".join(messages)

    def cleanup_multi_project_worktrees(
        self,
        task_name: str,
        projects: List[Dict[str, str]],
        force: bool = True
    ) -> Tuple[bool, str]:
        """
        Clean up multiple worktrees and branches for multi-project tasks.

        Args:
            task_name: Name of the task
            projects: List of project configs with write access projects
            force: Force cleanup even if there are uncommitted changes

        Returns:
            Tuple of (success, message)
        """
        messages = []
        overall_success = True

        # Only clean up worktrees for projects with "write" access
        write_projects = [p for p in projects if p.get("access") == "write"]

        if not write_projects:
            return True, "No worktrees to clean up (no write access projects)"

        for project in write_projects:
            project_path = project.get("path")
            project_type = project.get("project_type", "other")

            if not project_path or not self._is_git_repo(project_path):
                continue

            # Skip cleanup for IDL projects - they don't have worktrees
            if project_type == "idl":
                messages.append(f"Skipping cleanup for IDL project: {project_path} (no worktree)")
                continue

            # Create a GitWorktreeManager for this project
            project_wt_manager = GitWorktreeManager(project_path)

            # Clean up worktree and branch for this project
            success, message = project_wt_manager.cleanup_task_worktree_and_branch(task_name, force=force)

            if success:
                messages.append(f"Project {project_path}: {message}")
            else:
                overall_success = False
                messages.append(f"Project {project_path}: FAILED - {message}")

        combined_message = "; ".join(messages) if messages else "No worktrees to clean up"
        return overall_success, combined_message

    def list_worktrees(self) -> List[Dict]:
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
