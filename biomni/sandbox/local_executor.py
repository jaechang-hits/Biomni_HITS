"""
Local Code Executor

Implementation of CodeExecutor for local execution using subprocess and Python REPL.
"""

import os
import shutil
from typing import List, Optional, Dict

from .base import CodeExecutor
from biomni.utils import run_r_code, run_bash_script, run_with_timeout
from biomni.tool.support_tools import run_python_repl


class LocalCodeExecutor(CodeExecutor):
    """
    Code executor for local execution.

    Executes Python, R, and Bash code locally using subprocess and persistent REPL.
    This is the default executor used when no external sandbox is provided.

    Example:
        ```python
        from biomni.sandbox import LocalCodeExecutor

        # Create executor
        executor = LocalCodeExecutor(timeout=600)

        # Execute code
        result = executor.run_python("print('hello')")
        print(result)

        # Execute bash
        result = executor.run_bash("ls -la")
        print(result)
        ```
    """

    DEFAULT_TIMEOUT = 600

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        workdir: Optional[str] = None,
        custom_functions: Optional[Dict] = None,
    ):
        """
        Initialize Local executor.

        Args:
            timeout: Timeout in seconds for code execution (default: 600)
            workdir: Working directory for code execution (default: current directory)
            custom_functions: Dictionary of custom functions to inject into Python REPL
        """
        self.timeout = timeout
        self.workdir = workdir or os.getcwd()
        self.custom_functions = custom_functions or {}

    def set_custom_functions(self, custom_functions: Dict) -> None:
        """
        Set custom functions to be available in the Python REPL.

        Args:
            custom_functions: Dictionary mapping function names to callable objects
        """
        self.custom_functions = custom_functions
        self._inject_custom_functions()

    def _inject_custom_functions(self) -> None:
        """Inject custom functions into the Python REPL namespace."""
        if self.custom_functions:
            from biomni.utils import inject_custom_functions_to_repl

            inject_custom_functions_to_repl(self.custom_functions)

    def run_python(self, code: str) -> str:
        """
        Execute Python code locally using persistent REPL.

        Code is executed in the workdir, then returns to the original directory.

        Args:
            code: Python code to execute

        Returns:
            Execution output as string
        """
        try:
            # Inject custom functions before execution
            self._inject_custom_functions()

            # Save current directory and change to workdir
            original_dir = os.getcwd()
            os.chdir(self.workdir)

            try:
                return run_with_timeout(run_python_repl, [code], timeout=self.timeout)
            finally:
                # Restore original directory
                os.chdir(original_dir)
        except Exception as e:
            return f"Error Type: {type(e).__name__}\nError Message: {str(e)}"

    def run_bash(self, script: str) -> str:
        """
        Execute Bash script locally.

        Args:
            script: Bash script or command to execute

        Returns:
            Execution output as string
        """
        try:
            # Save current directory
            original_dir = os.getcwd()

            # Change to workdir if different
            if self.workdir != original_dir:
                os.chdir(self.workdir)

            try:
                return run_with_timeout(run_bash_script, [script], timeout=self.timeout)
            finally:
                # Restore original directory
                os.chdir(original_dir)
        except Exception as e:
            return f"Error Type: {type(e).__name__}\nError Message: {str(e)}"

    def run_r(self, code: str) -> str:
        """
        Execute R code locally using Rscript.

        Code is executed in the workdir, then returns to the original directory.

        Args:
            code: R code to execute

        Returns:
            Execution output as string
        """
        try:
            # Save current directory and change to workdir
            original_dir = os.getcwd()
            os.chdir(self.workdir)

            try:
                return run_with_timeout(run_r_code, [code], timeout=self.timeout)
            finally:
                # Restore original directory
                os.chdir(original_dir)
        except Exception as e:
            return f"Error Type: {type(e).__name__}\nError Message: {str(e)}"

    def list_files(self, directory: str = ".") -> List[str]:
        """
        List files in the specified directory.

        Args:
            directory: Directory path (default: current directory)

        Returns:
            List of file paths
        """
        try:
            # If relative path, make it relative to workdir
            if directory == "." or not os.path.isabs(directory):
                target_dir = (
                    os.path.join(self.workdir, directory)
                    if directory != "."
                    else self.workdir
                )
            else:
                target_dir = directory

            files = []
            for entry in os.listdir(target_dir):
                full_path = os.path.join(target_dir, entry)
                if os.path.isfile(full_path):
                    files.append(full_path)
            return files
        except Exception:
            return []

    def download_file(self, remote_path: str, local_path: str) -> None:
        """
        Copy a file from one location to another locally.

        For local execution, "remote" and "local" are both local paths,
        so this simply copies the file.

        Args:
            remote_path: Source file path
            local_path: Destination file path
        """
        shutil.copy2(remote_path, local_path)

    def upload_file(self, local_path: str, remote_path: Optional[str] = None) -> None:
        """
        Copy a file from one location to another locally.

        For local execution, "remote" and "local" are both local paths,
        so this simply copies the file.

        If remote_path is not provided, the file will be placed in workdir with
        the same basename as the local file.
        If remote_path is provided, the file will be placed at that exact path.

        Args:
            local_path: Source file path
            remote_path: Destination file path (optional, defaults to workdir/basename)
        """
        # If remote_path is not provided, use basename in workdir
        if remote_path is None:
            remote_path = os.path.join(self.workdir, os.path.basename(local_path))

        # Ensure destination directory exists
        dest_dir = os.path.dirname(remote_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)

        shutil.copy2(local_path, remote_path)

    def get_working_directory(self) -> str:
        """
        Get the current working directory.

        Returns:
            Current working directory path
        """
        return self.workdir

