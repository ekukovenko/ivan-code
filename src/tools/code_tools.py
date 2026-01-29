"""Tools for Code Agent - file operations and code generation."""

from agno.tools import tool

from src.github.client import GitHubClient


def create_code_tools(github_client: GitHubClient, branch: str):
    """Create tools for Code Agent with GitHub context."""

    @tool
    def read_file(path: str) -> str:
        """Read file content from the repository.

        Args:
            path: Path to the file in the repository
        """
        content = github_client.get_file_content(path, ref=branch)
        if content is None:
            return f"Error: File '{path}' not found"
        return content

    @tool
    def write_file(path: str, content: str, message: str) -> str:
        """Create or update a file in the repository.

        Args:
            path: Path to the file
            content: New content for the file
            message: Commit message
        """
        try:
            github_client.create_or_update_file(path, content, message, branch)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    @tool
    def delete_file(path: str, message: str) -> str:
        """Delete a file from the repository.

        Args:
            path: Path to the file to delete
            message: Commit message
        """
        try:
            github_client.delete_file(path, message, branch)
            return f"Successfully deleted {path}"
        except Exception as e:
            return f"Error deleting file: {e}"

    @tool
    def list_files(directory: str = "") -> str:
        """List all files in a directory.

        Args:
            directory: Directory path (empty for root)
        """
        try:
            files = github_client.list_files(directory, ref=branch)
            if not files:
                return "No files found"
            return "\n".join(files)
        except Exception as e:
            return f"Error listing files: {e}"

    @tool
    def search_in_files(query: str, file_pattern: str = "") -> str:
        """Search for a string in repository files.

        Args:
            query: String to search for
            file_pattern: Optional file extension filter (e.g., '.py')
        """
        try:
            files = github_client.list_files(ref=branch)
            results = []

            for file_path in files:
                if file_pattern and not file_path.endswith(file_pattern):
                    continue

                content = github_client.get_file_content(file_path, ref=branch)
                if content and query.lower() in content.lower():
                    # Find matching lines
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        if query.lower() in line.lower():
                            results.append(f"{file_path}:{i}: {line.strip()}")

            if not results:
                return f"No matches found for '{query}'"
            return "\n".join(results[:50])  # Limit results
        except Exception as e:
            return f"Error searching: {e}"

    return [read_file, write_file, delete_file, list_files, search_in_files]
