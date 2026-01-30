"""Tools for Code Agent - file operations and code generation."""

import re
from agno.tools import tool

from src.github.client import GitHubClient


# Security vulnerability patterns (OWASP-based)
SECURITY_PATTERNS = {
    "hardcoded_secret": [
        (r'(?i)(password|passwd|pwd|secret|api_key|apikey|token|auth_token)\s*=\s*["\'][^"\']{4,}["\']', "Hardcoded secret"),
        (r'(?i)(aws_access_key|aws_secret|private_key)\s*=\s*["\'][^"\']+["\']', "Hardcoded AWS/private key"),
    ],
    "sql_injection": [
        (r'execute\s*\(\s*f["\']', "SQL injection via f-string"),
        (r'execute\s*\([^)]*\s*%\s*', "SQL injection via % formatting"),
        (r'execute\s*\([^)]*\+', "SQL injection via concatenation"),
    ],
    "command_injection": [
        (r'os\.system\s*\(', "Command injection via os.system"),
        (r'subprocess\.[a-z]+\s*\([^)]*shell\s*=\s*True', "Command injection via shell=True"),
        (r'eval\s*\([^)]*input\s*\(', "Code injection via eval(input())"),
        (r'exec\s*\([^)]*input\s*\(', "Code injection via exec(input())"),
    ],
    "path_traversal": [
        (r'open\s*\(\s*[^)]*\+[^)]*\)', "Path traversal via concatenation in open()"),
        (r'open\s*\(\s*f["\']', "Path traversal via f-string in open()"),
    ],
    "unsafe_deserialization": [
        (r'pickle\.loads?\s*\(', "Unsafe deserialization via pickle"),
        (r'yaml\.load\s*\([^)]*\)(?!.*Loader\s*=)', "Unsafe YAML load without Loader"),
        (r'yaml\.unsafe_load\s*\(', "Unsafe YAML load"),
    ],
    "weak_crypto": [
        (r'hashlib\.md5\s*\(', "Weak hash: MD5"),
        (r'hashlib\.sha1\s*\(', "Weak hash: SHA1"),
    ],
}


def normalize_python_code(content: str) -> str:
    """Format Python code using ruff for CI compatibility."""
    import subprocess
    import tempfile
    import os

    # Ensure trailing newline first
    if content and not content.endswith('\n'):
        content = content + '\n'

    try:
        # Write to temp file, format with ruff, read back
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_path = f.name

        # Run ruff format
        subprocess.run(
            ['ruff', 'format', temp_path],
            capture_output=True,
            timeout=10
        )

        # Read formatted content
        with open(temp_path, 'r') as f:
            formatted = f.read()

        os.unlink(temp_path)
        return formatted

    except Exception:
        # Fallback: basic normalization if ruff fails
        lines = content.split('\n')
        normalized = [line.rstrip() for line in lines]
        result = '\n'.join(normalized)
        return result.rstrip('\n') + '\n'


def check_security_issues(content: str, filename: str = "") -> list[dict]:
    """Check content for security vulnerabilities."""
    issues = []
    lines = content.split('\n')

    for category, patterns in SECURITY_PATTERNS.items():
        for pattern, description in patterns:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    # Skip if it's a comment or in a string that looks like docs
                    stripped = line.strip()
                    if stripped.startswith('#'):
                        continue
                    issues.append({
                        "line": i,
                        "category": category,
                        "description": description,
                        "code": line.strip()[:80],
                        "severity": "HIGH" if category in ["sql_injection", "command_injection", "hardcoded_secret"] else "MEDIUM",
                    })
    return issues


def create_code_tools(github_client: GitHubClient, branch: str):
    """Create tools for Code Agent with GitHub context."""

    @tool
    def check_python_style(path: str) -> str:
        """Check a Python file for common style issues BEFORE committing.

        IMPORTANT: Always run this on Python files after writing them!

        Checks for:
        - Missing trailing newline (W292)
        - Import sorting issues (I001)
        - Basic syntax issues

        Args:
            path: Path to the Python file to check
        """
        content = github_client.get_file_content(path, ref=branch)
        if content is None:
            return f"Error: File '{path}' not found"

        issues = []

        # Check trailing newline (W292)
        if content and not content.endswith('\n'):
            issues.append(f"W292: No newline at end of file - add empty line at the end")

        # Check import sorting (I001) - basic check
        lines = content.split('\n')
        import_lines = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                import_lines.append((i, stripped))
            elif stripped and not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith("'''"):
                if import_lines:
                    break  # End of import block

        if import_lines:
            # Check import order: stdlib -> third-party -> local
            stdlib_imports = []
            third_party_imports = []
            local_imports = []

            STDLIB_MODULES = {'os', 'sys', 're', 'json', 'logging', 'typing', 'enum',
                           'datetime', 'collections', 'functools', 'pathlib', 'unittest',
                           'asyncio', 'contextlib', 'dataclasses', 'abc', 'io', 'time'}

            for line_num, imp in import_lines:
                # Extract module name
                if imp.startswith('from '):
                    module = imp.split()[1].split('.')[0]
                else:
                    module = imp.split()[1].split('.')[0]

                if module in STDLIB_MODULES:
                    stdlib_imports.append((line_num, imp, 'stdlib'))
                elif module.startswith('app') or module.startswith('src') or module.startswith('.'):
                    local_imports.append((line_num, imp, 'local'))
                else:
                    third_party_imports.append((line_num, imp, 'third-party'))

            # Check order
            all_imports = stdlib_imports + third_party_imports + local_imports
            actual_order = [imp[0] for imp in import_lines]
            expected_order = [imp[0] for imp in all_imports]

            if actual_order != sorted(actual_order) or actual_order != expected_order:
                issues.append(f"I001: Import block may be un-sorted. Correct order: stdlib -> third-party -> local")
                if stdlib_imports:
                    issues.append(f"  Stdlib imports: {[i[1] for i in stdlib_imports]}")
                if third_party_imports:
                    issues.append(f"  Third-party imports: {[i[1] for i in third_party_imports]}")
                if local_imports:
                    issues.append(f"  Local imports: {[i[1] for i in local_imports]}")

        # Check for basic Python syntax issues
        try:
            compile(content, path, 'exec')
        except SyntaxError as e:
            issues.append(f"SyntaxError at line {e.lineno}: {e.msg}")

        if issues:
            return "Style issues found:\n" + "\n".join(issues)
        return f"OK: {path} passes style checks"

    @tool
    def validate_all_python_files() -> str:
        """Check ALL Python files in the repository for style issues.

        Run this before considering your work complete!
        """
        try:
            files = github_client.list_files(ref=branch)
            python_files = [f for f in files if f.endswith('.py')]

            all_issues = []
            for path in python_files:
                content = github_client.get_file_content(path, ref=branch)
                if content is None:
                    continue

                file_issues = []

                # Check trailing newline
                if content and not content.endswith('\n'):
                    file_issues.append("W292: No newline at end of file")

                # Check syntax
                try:
                    compile(content, path, 'exec')
                except SyntaxError as e:
                    file_issues.append(f"SyntaxError: line {e.lineno}: {e.msg}")

                if file_issues:
                    all_issues.append(f"{path}:\n  " + "\n  ".join(file_issues))

            if all_issues:
                return "Issues found:\n\n" + "\n\n".join(all_issues)
            return f"OK: All {len(python_files)} Python files pass basic checks"
        except Exception as e:
            return f"Error: {e}"

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
            # Auto-fix Python files for ruff format compatibility
            if path.endswith('.py'):
                content = normalize_python_code(content)
            # Ensure trailing newline for other text files
            elif path.endswith(('.txt', '.md', '.json', '.yaml', '.yml', '.toml')):
                if content and not content.endswith('\n'):
                    content = content + '\n'

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

    @tool
    def security_check(path: str) -> str:
        """Проверить файл на уязвимости безопасности (OWASP).

        Проверяет:
        - Hardcoded secrets (пароли, API ключи, токены)
        - SQL injection
        - Command injection (os.system, shell=True)
        - Path traversal
        - Unsafe deserialization (pickle, yaml)
        - Weak crypto (MD5, SHA1)

        Args:
            path: Путь к файлу для проверки
        """
        content = github_client.get_file_content(path, ref=branch)
        if content is None:
            return f"Error: File '{path}' not found"

        issues = check_security_issues(content, path)

        if not issues:
            return f"OK: {path} — уязвимостей не найдено"

        result = [f"SECURITY: {path} — найдено {len(issues)} проблем:\n"]
        for issue in issues:
            result.append(
                f"  [{issue['severity']}] Line {issue['line']}: {issue['description']}\n"
                f"    > {issue['code']}"
            )
        return "\n".join(result)

    @tool
    def security_scan_all() -> str:
        """Проверить ВСЕ файлы репозитория на уязвимости.

        Сканирует .py, .js, .ts, .java, .go, .kt файлы.
        Запусти перед завершением работы!
        """
        try:
            files = github_client.list_files(ref=branch)
            scannable = [f for f in files if f.endswith(('.py', '.js', '.ts', '.java', '.go', '.kt'))]

            all_issues = []
            for path in scannable:
                content = github_client.get_file_content(path, ref=branch)
                if content is None:
                    continue

                issues = check_security_issues(content, path)
                if issues:
                    all_issues.append((path, issues))

            if not all_issues:
                return f"OK: Проверено {len(scannable)} файлов — уязвимостей не найдено"

            result = [f"SECURITY SCAN: Найдены проблемы в {len(all_issues)} файлах:\n"]
            for path, issues in all_issues:
                result.append(f"\n{path}:")
                for issue in issues:
                    result.append(f"  [{issue['severity']}] Line {issue['line']}: {issue['description']}")

            return "\n".join(result)
        except Exception as e:
            return f"Error: {e}"

    return [
        read_file,
        write_file,
        delete_file,
        list_files,
        search_in_files,
        check_python_style,
        validate_all_python_files,
        security_check,
        security_scan_all,
    ]
