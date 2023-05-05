"""Git operations for autogpt"""
from git.repo import Repo
from github import Github

from autogpt.commands.command import command
from autogpt.config import Config
from autogpt.url_utils.validators import validate_url

CFG = Config()


@command(
    "clone_repository",
    "Clone Repository",
    '"url": "<repository_url>", "clone_path": "<clone_path>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
@validate_url
def clone_repository(url: str, clone_path: str) -> str:
    """Clone a GitHub repository locally.

    Args:
        url (str): The URL of the repository to clone.
        clone_path (str): The path to clone the repository to.

    Returns:
        str: The result of the clone operation.
    """
    split_url = url.split("//")
    auth_repo_url = f"//{CFG.github_username}:{CFG.github_api_key}@".join(split_url)
    try:
        Repo.clone_from(url=auth_repo_url, to_path=clone_path)
        return f"""Cloned {url} to {clone_path}"""
    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "git_add",
    "Add files to the staging area",
    '"repo_path": "<repo_path>", "file_path": "<file_path>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def git_add(repo_path: str, file_path: str) -> str:
    """Add a file to the git staging area.
    Args:
        repo_path (str): The path to the repository.
        file_path (str): The path to the file to add.
    Returns:
        str: The result of the add operation.
    """
    try:
        repo = Repo(repo_path)
        repo.index.add([file_path])
        return f"""Added {file_path} to the staging area"""
    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "git_remove",
    "Remove a file from the git staging area",
    '"repo_path": "<repo_path>", "file_path": "<file_path>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def git_remove(repo_path: str, file_path: str) -> str:
    """Remove a file from the git staging area.
    Args:
        repo_path (str): The path to the repository.
        file_path (str): The path to the file to remove.
    Returns:
        str: The result of the remove operation.
    """
    try:
        repo = Repo(repo_path)
        repo.index.remove([file_path], cached=True)
        return f"Removed {file_path} from the staging area"
    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "git_commit",
    "Commit changes to the repository",
    '"repo_path": "<repo_path>", "message": "<message>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def git_commit(repo_path: str, message: str) -> str:
    """Commit changes to the git repository.
    Args:
        repo_path (str): The path to the repository.
        message (str): The commit message.
    Returns:
        str: The result of the commit operation.
    """
    try:
        repo = Repo(repo_path)
        repo.index.commit(message)
        return f"""Committed changes with message: {message}"""
    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "git_push",
    "Push changes to a remote repository",
    '"repo_path": "<repo_path>", "remote_name": "<remote_name>", "branch_name": "<branch_name>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def git_push(repo_path: str, remote_name: str, branch_name: str) -> str:
    """Push changes to a remote git repository.
    Args:
        repo_path (str): The path to the repository.
        remote_name (str): The name of the remote repository.
        branch_name (str): The name of the branch to push to.
    Returns:
        str: The result of the push operation.
    """
    try:
        repo = Repo(repo_path)
        origin = repo.remote(name=remote_name)
        origin.push(refspec=f"HEAD:{branch_name}")
        return f"""Pushed changes to {remote_name}/{branch_name}"""
    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "git_pull",
    "Pull changes from a remote repository",
    '"repo_path": "<repo_path>", "remote_name": "<remote_name>", "branch_name": "<branch_name>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def git_pull(repo_path: str, remote_name: str, branch_name: str) -> str:
    """Pull changes from a remote git repository.
    Args:
        repo_path (str): The path to the repository.
        remote_name (str): The name of the remote repository.
        branch_name (str): The name of the branch to pull from.
    Returns:
        str: The result of the pull operation.
    """
    try:
        repo = Repo(repo_path)
        origin = repo.remote(name=remote_name)
        origin.pull(branch_name)
        return f"""Pulled changes from {remote_name}/{branch_name}"""
    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "init_repository",
    "Initialize a new git repository",
    '"repo_path": "<repo_path>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def init_repository(repo_path: str) -> str:
    """Initialize a new git repository.
    Args:
        repo_path (str): The path to initialize the repository at.
    Returns:
        str: The result of the init operation.
    """
    try:
        Repo.init(path=repo_path)
        return f"""Initialized a new git repository at {repo_path}"""
    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "checkout_branch",
    "Checkout / create & switch to a git branch",
    '"repo_path": "<repo_path>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def checkout_branch(repo_path: str, branch_name: str) -> str:
    """Switch to the desired git branch or create one if it does not exist.
    Args:
        repo_path (str): The path to the repository.
        branch_name (str): The name of the branch to switch to.
    Returns:
        str: The result of the checkout operation.
    """
    try:
        repo = Repo(repo_path)

        if branch_name not in repo.heads:
            # Create the new branch
            new_branch = repo.create_head(branch_name)
            return f"Created a new branch '{branch_name}' and switched to it."
        else:
            # Switch to the existing branch
            repo.heads[branch_name].checkout()
            return f"Switched to the branch '{branch_name}'."

    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "merge_branch",
    "Merge a git branch into the current branch",
    '"repo_path": "<repo_path>", "branch_name": "<branch_name>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def merge_branch(repo_path: str, branch_name: str) -> str:
    """Merge a git branch into the current branch.
    Args:
        repo_path (str): The path to the repository.
        branch_name (str): The name of the branch to merge.
    Returns:
        str: The result of the merge operation.
    """
    try:
        repo = Repo(repo_path)

        if branch_name not in repo.heads:
            return f"Error: Branch '{branch_name}' not found."

        # Get the current branch
        current_branch = repo.active_branch

        # Merge the specified branch into the current branch
        merge_base = repo.merge_base(current_branch, repo.heads[branch_name])
        repo.index.merge_tree(repo.heads[branch_name], base=merge_base)
        repo.index.commit(
            f"Merged branch '{branch_name}' into '{current_branch.name}'",
            parent_commits=(current_branch.commit, repo.heads[branch_name].commit)
        )

        return f"Successfully merged branch '{branch_name}' into '{current_branch.name}'."

    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "git_status",
    "Check the git status of the repository",
    '"repo_path": "<repo_path>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def git_status(repo_path: str) -> str:
    """Check the git status of the repository.
    Args:
        repo_path (str): The path to the repository.
    Returns:
        str: The git status including the current branch, changed files, and untracked files.
    """
    try:
        repo = Repo(repo_path)

        # Get the current branch
        current_branch = repo.active_branch.name

        # Get the changed files
        changed_files = [item.a_path for item in repo.index.diff(None)]

        # Get the untracked files
        untracked_files = repo.untracked_files

        # Format the result
        result = f"Current branch: {current_branch}\n"
        result += "Changed files:\n"
        result += "\n".join(changed_files) if changed_files else "No changed files\n"
        result += "Untracked files:\n"
        result += "\n".join(untracked_files) if untracked_files else "No untracked files"

        return result

    except Exception as e:
        return f"Error: {str(e)}"

@command(
    "git_log",
    "Get the git log of the last 25 commits",
    '"repo_path": "<repo_path>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def git_log(repo_path: str) -> str:
    """Get the git log of the last 25 commits.
    Args:
        repo_path (str): The path to the repository.
    Returns:
        str: The git log including commit hashes, dates, authors, and commit messages.
    """
    try:
        repo = Repo(repo_path)

        # Get the last 25 commits
        commits = list(repo.iter_commits('HEAD', max_count=25))

        # Format the result
        result = ""
        for commit in commits:
            result += f"Commit: {commit.hexsha}\n"
            result += f"Author: {commit.author.name} <{commit.author.email}>\n"
            result += f"Date: {commit.committed_datetime}\n"
            result += f"Message: {commit.message}\n\n"

        return result.strip()

    except Exception as e:
        return f"Error: {str(e)}"


@command(
    "create_pull_request",
    "Create a pull request on GitHub",
    '"repo_path": "<repo_path>", "base_branch": "<base_branch>", "head_branch": "<head_branch>", "title": "<title>", "body": "<body>"',
    CFG.github_username and CFG.github_api_key,
    "Configure github_username and github_api_key.",
)
def create_pull_request(repo_path: str, base_branch: str, head_branch: str, title: str, body: str) -> str:
    """Create a pull request on GitHub.
    Args:
        repo_path (str): The path to the repository.
        base_branch (str): The target branch of the pull request.
        head_branch (str): The branch that contains the changes to be merged.
        title (str): The title of the pull request.
        body (str): The description of the pull request.
    Returns:
        str: The result of the pull request creation.
    """
    try:
        # Authenticate with the GitHub API
        g = Github(CFG.github_api_key)

        # Get the remote repository
        repo = Repo(repo_path)
        remote_url = repo.remotes.origin.url
        remote_repo = g.get_repo(remote_url.replace("https://github.com/", "").replace(".git", ""))

        # Create the pull request
        pull_request = remote_repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)

        return f"Pull request created: {pull_request.html_url}"

    except Exception as e:
        return f"Error: {str(e)}"
