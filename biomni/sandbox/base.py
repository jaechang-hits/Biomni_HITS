"""
Base Code Executor Interface

Defines the abstract interface for code execution that can be implemented
by different backends (E2B, Docker, local, etc.)
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import threading


class CodeExecutor(ABC):
    """
    Abstract base class for code executors.

    Implementations of this interface can execute code in different environments
    (E2B sandbox, Docker container, local subprocess, etc.)

    Supports interruption of running code via the interrupt() method.

    Example usage:
        ```python
        from e2b_code_interpreter import Sandbox
        from biomni.sandbox import E2BCodeInterpreterExecutor

        # Create executor externally
        sandbox = Sandbox()
        executor = E2BCodeInterpreterExecutor(sandbox)

        # Inject into A1_HITS
        agent = A1_HITS(executor=executor)
        agent.configure()
        result = agent.go(prompt)

        # Interrupt if needed
        executor.interrupt()

        # Cleanup externally
        sandbox.kill()
        ```
    """

    def __init__(self):
        """Initialize base executor with interrupt support."""
        self._interrupt_event = threading.Event()
        self._is_executing = threading.Event()

    def interrupt(self) -> bool:
        """
        Request interruption of currently running code.

        This sets the interrupt flag. Implementations should check this flag
        and terminate execution as soon as possible.

        Returns:
            True if interrupt was requested (code was executing), False otherwise
        """
        if self._is_executing.is_set():
            self._interrupt_event.set()
            return True
        return False

    def is_interrupted(self) -> bool:
        """Check if interrupt has been requested."""
        return self._interrupt_event.is_set()

    def reset_interrupt(self) -> None:
        """Reset the interrupt flag. Called before starting new execution."""
        self._interrupt_event.clear()

    def _mark_executing(self) -> None:
        """Mark that code execution has started."""
        self._is_executing.set()

    def _mark_idle(self) -> None:
        """Mark that code execution has finished."""
        self._is_executing.clear()

    @abstractmethod
    def run_python(self, code: str) -> str:
        """
        Execute Python code.

        Args:
            code: Python code to execute

        Returns:
            Execution output as string (stdout + stderr + errors)
        """
        pass

    @abstractmethod
    def run_bash(self, script: str) -> str:
        """
        Execute Bash script or command.

        Args:
            script: Bash script or command to execute

        Returns:
            Execution output as string (stdout + stderr)
        """
        pass

    @abstractmethod
    def run_r(self, code: str) -> str:
        """
        Execute R code.

        Args:
            code: R code to execute

        Returns:
            Execution output as string
        """
        pass

    @abstractmethod
    def list_files(self, directory: str = ".") -> List[str]:
        """
        List files in the specified directory.

        Args:
            directory: Directory path to list files from (default: current directory)

        Returns:
            List of file paths
        """
        pass

    @abstractmethod
    def download_file(self, remote_path: str, local_path: str) -> None:
        """
        Download a file from the execution environment to local filesystem.

        Args:
            remote_path: Path to file in the execution environment
            local_path: Local path where file will be saved
        """
        pass

    def upload_file(self, local_path: str, remote_path: str = None) -> None:
        """
        Upload a file from local filesystem to the execution environment.

        If remote_path is not provided, the file will be placed in workdir with
        the same basename as the local file.
        If remote_path is provided, the file will be placed at that exact path.

        Args:
            local_path: Local file path
            remote_path: Path in the execution environment (optional, defaults to workdir/basename)

        Note:
            This method is optional - implementations may choose not to support it
            if the environment doesn't require file uploads.
        """
        raise NotImplementedError("upload_file is not supported by this executor")

    def get_working_directory(self) -> str:
        """
        Get the current working directory in the execution environment.

        Returns:
            Current working directory path
        """
        result = self.run_bash("pwd")
        return result.strip()
