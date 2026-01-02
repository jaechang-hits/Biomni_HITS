"""
E2B Code Interpreter Executor

Implementation of CodeExecutor using E2B's Code Interpreter sandbox.
"""

import threading
from typing import List, Dict, Optional
from .base import CodeExecutor


class E2BCodeInterpreterExecutor(CodeExecutor):
    """
    Code executor using E2B Code Interpreter sandbox.

    The sandbox instance must be created and managed externally.
    This class is just a wrapper that implements the CodeExecutor interface.

    Supports full interrupt functionality - can stop running code mid-execution
    by killing the Jupyter kernel.

    By default, all code execution:
    - Activates pixi environment from /app
    - Runs in /workdir directory

    Example:
        ```python
        from e2b_code_interpreter import Sandbox
        from biomni.sandbox import E2BCodeInterpreterExecutor

        # Create sandbox externally
        sandbox = Sandbox(timeout=300)

        # Create executor
        executor = E2BCodeInterpreterExecutor(sandbox)

        # Use executor
        result = executor.run_python("print('hello')")

        # Interrupt running code (from another thread)
        executor.interrupt()

        # Cleanup (external responsibility)
        sandbox.kill()
        ```
    """

    # Default environment settings
    PIXI_PATH = "/app"
    WORKDIR = "/home/user/"
    PIXI_RSCRIPT = "/app/.pixi/envs/default/bin/Rscript"
    DEFAULT_TIMEOUT = 600

    def __init__(
        self,
        sandbox,
        pixi_path: Optional[str] = None,
        workdir: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Initialize E2B executor with an externally created sandbox.

        Args:
            sandbox: E2B Sandbox instance (from e2b_code_interpreter)
            pixi_path: Path to pixi installation (default: /app)
            workdir: Working directory for code execution (default: /workdir)
            timeout: Timeout in seconds for code execution (default: 600)
        """
        super().__init__()  # Initialize interrupt support from base class
        self.sandbox = sandbox
        self.pixi_path = pixi_path or self.PIXI_PATH
        self.workdir = workdir or self.WORKDIR
        self.timeout = timeout
        # Pixi's .pixi directory contains all packages
        self.pixi_env_path = f"{self.pixi_path}/.pixi"

        # Track current command process for interruption
        self._current_process = None
        self._process_lock = threading.Lock()

        # Setup Python sys.path once during init
        self._setup_python_path()

    def interrupt(self) -> bool:
        """
        Interrupt currently running code by restarting the Jupyter kernel.

        This will immediately stop any running Python code. For bash/R commands,
        it will attempt to kill the running process.

        Returns:
            True if interrupt was successful, False otherwise
        """
        if not self._is_executing.is_set():
            return False

        self._interrupt_event.set()

        try:
            # Restart the Jupyter kernel to stop Python execution
            # This is the most reliable way to interrupt run_code()
            if hasattr(self.sandbox, 'notebook') and hasattr(self.sandbox.notebook, 'restart_kernel'):
                self.sandbox.notebook.restart_kernel()
                # Re-setup Python path after kernel restart
                self._setup_python_path()
                return True

            # For command execution, try to kill running processes
            # Kill any running user processes (excluding system processes)
            try:
                self.sandbox.commands.run(
                    "pkill -u user -f 'python|Rscript' 2>/dev/null || true",
                    timeout=5
                )
            except Exception:
                pass

            return True
        except Exception as e:
            print(f"Warning: Failed to interrupt execution: {e}")
            return False

    def _setup_python_path(self) -> None:
        """
        Set up Python sys.path with Pixi site-packages once during initialization.
        This is executed via run_code to add Pixi packages to the Jupyter kernel's sys.path.
        """
        try:
            setup_code = f"""
import sys
import glob
import os

# Add Pixi site-packages to sys.path
for sp in glob.glob("{self.pixi_env_path}/envs/*/lib/python*/site-packages"):
    if sp not in sys.path:
        sys.path.insert(0, sp)

# Set working directory
os.chdir("{self.workdir}")
"""
            self.sandbox.run_code(setup_code.strip(), timeout=self.timeout)
        except Exception as e:
            print(f"Warning: Failed to setup Python path: {e}")

    def run_python(self, code: str) -> str:
        """
        Execute Python code in the E2B sandbox.

        Uses Jupyter kernel (run_code) to maintain state between executions.
        Pixi packages are available via sys.path injection done during init.

        Can be interrupted by calling interrupt() from another thread.

        Args:
            code: Python code to execute

        Returns:
            Formatted execution output
        """
        # Check for interrupt before starting
        if self.is_interrupted():
            self.reset_interrupt()
            return "Execution interrupted by user before starting."

        try:
            self._mark_executing()
            result = self.sandbox.run_code(code, timeout=self.timeout)

            # Check if interrupted during execution
            if self.is_interrupted():
                self.reset_interrupt()
                return "Execution interrupted by user."

            return self._format_code_result(result)
        except Exception as e:
            if self.is_interrupted():
                self.reset_interrupt()
                return "Execution interrupted by user."
            return f"Error Type: {type(e).__name__}\nError Message: {str(e)}"
        finally:
            self._mark_idle()

    def run_bash(self, script: str) -> str:
        """
        Execute Bash script in the E2B sandbox.

        Script is executed with pixi environment activated and in /workdir.

        Args:
            script: Bash script or command to execute

        Returns:
            Formatted execution output
        """
        # Check for interrupt before starting
        if self.is_interrupted():
            self.reset_interrupt()
            return "Execution interrupted by user before starting."

        try:
            self._mark_executing()
            # Execute with pixi (same pattern as test.py)
            result = self.sandbox.commands.run(
                f"cd {self.pixi_path} && pixi run bash -c 'cd {self.workdir} && {script}'",
                timeout=self.timeout,
            )

            if self.is_interrupted():
                self.reset_interrupt()
                return "Execution interrupted by user."

            return self._format_command_result(result)
        except Exception as e:
            if self.is_interrupted():
                self.reset_interrupt()
                return "Execution interrupted by user."
            return f"Error Type: {type(e).__name__}\nError Message: {str(e)}"
        finally:
            self._mark_idle()

    def run_r(self, code: str) -> str:
        """
        Execute R code in the E2B sandbox using Rscript.

        R code is executed in /workdir using the pre-configured Rscript path.

        Args:
            code: R code to execute

        Returns:
            Formatted execution output
        """
        # Check for interrupt before starting
        if self.is_interrupted():
            self.reset_interrupt()
            return "Execution interrupted by user before starting."

        try:
            self._mark_executing()
            # Prepend workdir setup to the code
            setup_code = f'setwd("{self.workdir}")\n'
            full_code = setup_code + code

            # Escape quotes for shell
            escaped_code = full_code.replace("\\", "\\\\").replace("'", "'\"'\"'")

            # Use the pre-configured Rscript path directly
            result = self.sandbox.commands.run(
                f"{self.PIXI_RSCRIPT} -e '{escaped_code}'",
                timeout=self.timeout,
            )

            if self.is_interrupted():
                self.reset_interrupt()
                return "Execution interrupted by user."

            return self._format_command_result(result)
        except Exception as e:
            if self.is_interrupted():
                self.reset_interrupt()
                return "Execution interrupted by user."
            return f"Error Type: {type(e).__name__}\nError Message: {str(e)}"
        finally:
            self._mark_idle()

    def list_files(self, directory: str = ".") -> List[str]:
        """
        List files in the specified directory within the sandbox.

        Args:
            directory: Directory path (default: workdir)

        Returns:
            List of file paths
        """
        try:
            # If relative path, make it relative to workdir
            if directory == "." or not directory.startswith("/"):
                target_dir = (
                    f"{self.workdir}/{directory}" if directory != "." else self.workdir
                )
            else:
                target_dir = directory

            result = self.sandbox.commands.run(
                f"find {target_dir} -maxdepth 1 -type f 2>/dev/null",
                timeout=self.timeout,
            )
            files = [f.strip() for f in result.stdout.split("\n") if f.strip()]
            return files
        except Exception:
            return []

    # Binary file extensions that need to be read with format='bytes'
    BINARY_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",  # Images
        ".pdf",  # PDF
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".7z",
        ".rar",  # Archives
        ".bin",
        ".exe",
        ".dll",
        ".so",
        ".dylib",  # Binaries
        ".pkl",
        ".pickle",
        ".npy",
        ".npz",  # Python data files
        ".h5",
        ".hdf5",  # HDF5 files
        ".parquet",
        ".feather",  # Data formats
        ".xlsx",
        ".xls",
        ".docx",
        ".doc",
        ".pptx",
        ".ppt",  # Office files
    }

    def download_file(self, remote_path: str, local_path: str) -> None:
        """
        Download a file from the sandbox to local filesystem.

        Args:
            remote_path: Path to file in the sandbox
            local_path: Local path where file will be saved
        """
        import os

        # Check if file is binary based on extension
        ext = os.path.splitext(remote_path)[1].lower()
        is_binary = ext in self.BINARY_EXTENSIONS

        if is_binary:
            # Read as bytes for binary files
            content = self.sandbox.files.read(remote_path, format="bytes")
            with open(local_path, "wb") as f:
                f.write(content)
        else:
            # Read as text for other files
            content = self.sandbox.files.read(remote_path)
            with open(local_path, "w") as f:
                f.write(content)

    def upload_file(self, local_path: str, remote_path: str = None) -> None:
        """
        Upload a file from local filesystem to the sandbox.

        If remote_path is not provided, the file will be placed in workdir with
        the same basename as the local file.
        If remote_path is provided, the file will be placed at that exact path.

        Args:
            local_path: Local file path
            remote_path: Path in the sandbox (optional, defaults to workdir/basename)
        """
        import os

        # If remote_path is not provided, use basename in workdir
        if remote_path is None:
            remote_path = f"{self.workdir}/{os.path.basename(local_path)}"

        with open(local_path, "rb") as f:
            content = f.read()
        self.sandbox.files.write(remote_path, content)

    def upload_files(self, files: Dict[str, str]) -> None:
        """
        Upload multiple files to the sandbox.

        Args:
            files: Dictionary mapping local paths to remote paths
        """
        for local_path, remote_path in files.items():
            self.upload_file(local_path, remote_path)

    def _format_code_result(self, result) -> str:
        """
        Format the result from sandbox.run_code().

        Args:
            result: Execution result object from E2B

        Returns:
            Formatted string output
        """
        output_parts = []

        # Handle logs (stdout/stderr) - logs.stdout and logs.stderr are lists
        if hasattr(result, "logs") and result.logs:
            if hasattr(result.logs, "stdout") and result.logs.stdout:
                output_parts.append("".join(result.logs.stdout))
            if hasattr(result.logs, "stderr") and result.logs.stderr:
                output_parts.append(f"stderr: {''.join(result.logs.stderr)}")

        # Handle text output
        if hasattr(result, "text") and result.text:
            output_parts.append(result.text)

        # Handle results (for expressions that return values)
        if hasattr(result, "results") and result.results:
            for r in result.results:
                if hasattr(r, "text") and r.text:
                    output_parts.append(r.text)

        # Handle errors
        if hasattr(result, "error") and result.error:
            error_parts = []
            if hasattr(result.error, "name"):
                error_parts.append(f"Error Type: {result.error.name}")
            if hasattr(result.error, "value"):
                error_parts.append(f"Error Message: {result.error.value}")
            if hasattr(result.error, "traceback"):
                error_parts.append(f"Traceback:\n{result.error.traceback}")
            output_parts.extend(error_parts)

        return "\n".join(output_parts) if output_parts else ""

    def _format_command_result(self, result) -> str:
        """
        Format the result from sandbox.commands.run().

        Args:
            result: Command result object from E2B

        Returns:
            Formatted string output
        """
        output_parts = []

        if hasattr(result, "stdout") and result.stdout:
            output_parts.append(result.stdout)

        if hasattr(result, "stderr") and result.stderr:
            output_parts.append(f"stderr: {result.stderr}")

        if hasattr(result, "exit_code") and result.exit_code != 0:
            output_parts.append(f"Exit code: {result.exit_code}")

        return "\n".join(output_parts) if output_parts else ""
