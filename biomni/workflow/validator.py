"""
Workflow Validator Module

System-internal validation to ensure workflow produces identical outputs.
"""

import subprocess
import shutil
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Union
import hashlib


class WorkflowValidator:
    """Validates that saved workflow produces identical outputs to Agent execution."""
    
    # Constants
    DEFAULT_TIMEOUT = 300  # 5 minutes in seconds
    RESULT_TRUNCATE_LENGTH = 10000  # Maximum result length to save
    
    # Common output file extensions
    COMMON_OUTPUT_EXTENSIONS = {
        '.csv', '.tsv', '.xlsx', '.xls', '.json', '.txt', '.tsv.gz',
        '.png', '.jpg', '.jpeg', '.pdf', '.svg',
        '.pkl', '.pickle', '.h5', '.hdf5', '.parquet', '.feather'
    }
    
    # Maximum file size for in-memory comparison (100MB)
    MAX_IN_MEMORY_SIZE = 100 * 1024 * 1024
    
    def __init__(self, work_dir: str):
        """
        Initialize with work directory.
        
        Args:
            work_dir: Working directory path
        """
        self.work_dir = Path(work_dir)
        self.temp_dir = self.work_dir / "workflow_validation_temp"
    
    def validate_workflow(
        self,
        workflow_path: str,
        original_input_files: List[str],
        expected_output_files: Dict[str, bytes]
    ) -> Dict:
        """
        Execute workflow and verify output files are identical to expected.
        
        Args:
            workflow_path: Path to saved workflow script
            original_input_files: List of input file paths used in Agent execution
            expected_output_files: Dict mapping output file paths to their content (bytes)
        
        Returns:
            {
                "valid": bool,
                "output_files_match": dict,  # {file_path: bool}
                "differences": list,  # List of differences if any
                "error": str | None
            }
        """
        # Create temporary directory for validation
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Run workflow script
            result = self.run_workflow_script(workflow_path, original_input_files, expected_output_files)
            
            if not result["success"]:
                error_msg = result.get('error', 'Unknown error')
                return {
                    "valid": False,
                    "output_files_match": {},
                    "differences": [f"Workflow execution failed: {error_msg}"],
                    "summary": f"Workflow execution failed: {error_msg}",
                    "error": result.get("error"),
                    "stderr": result.get("stderr", ""),
                    "stdout": result.get("stdout", "")
                }
            
            # Compare outputs
            comparison = self.compare_outputs(result["output_files"], expected_output_files)
            
            return {
                "valid": comparison["all_match"],
                "output_files_match": comparison["file_comparisons"],
                "differences": comparison["differences"],
                "summary": comparison["summary"],
                "error": None,
                "stderr": result.get("stderr", ""),
                "stdout": result.get("stdout", "")
            }
        
        except Exception as e:
            error_str = str(e)
            return {
                "valid": False,
                "output_files_match": {},
                "differences": [f"Validation error: {error_str}"],
                "summary": f"Validation error: {error_str}",
                "error": error_str
            }
        
        finally:
            # Clean up temporary directory
            self._cleanup_temp_dir()
    
    def run_workflow_script(
        self,
        script_path: str,
        input_files: List[str],
        expected_output_files: Optional[Dict[str, bytes]] = None
    ) -> Dict:
        """
        Execute saved workflow script with given inputs.
        
        Args:
            script_path: Path to workflow script
            input_files: List of input file paths
            expected_output_files: Optional dict of expected output files (for determining output paths)
        
        Returns:
            {
                "success": bool,
                "output_files": dict,  # {file_path: file_content_bytes}
                "stdout": str,
                "stderr": str,
                "error": str | None
            }
        """
        # Create temporary directory for execution
        exec_dir = self.temp_dir / "execution"
        exec_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy input files to execution directory
        copied_input_files = []
        copied_input_filenames = set()  # Track copied filenames for filtering outputs
        for input_file in input_files:
            src = Path(input_file)
            if src.exists():
                dst = exec_dir / src.name
                shutil.copy2(src, dst)
                copied_input_files.append(str(dst))
                copied_input_filenames.add(src.name)
        
        # Analyze script to determine argument format
        script_args = self._determine_script_arguments(script_path, copied_input_files, expected_output_files)
        
        # Prepare command
        script_path_resolved = Path(script_path).resolve()
        cmd = ["python", str(script_path_resolved)] + script_args
        
        try:
            # Run script
            result = subprocess.run(
                cmd,
                cwd=str(exec_dir),
                capture_output=True,
                text=True,
                timeout=self.DEFAULT_TIMEOUT
            )
            
            # Collect output files from execution directory
            # Determine allowed extensions from expected outputs or use common extensions
            allowed_extensions = self._get_allowed_extensions(expected_output_files)
            
            output_files = {}
            for file_path in exec_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                
                # Check if file extension is allowed
                if file_path.suffix.lower() not in allowed_extensions:
                    continue
                
                # Skip input files (use copied_input_filenames for accurate comparison)
                if file_path.name in copied_input_filenames:
                    continue
                
                try:
                    # Use hash-based comparison for large files
                    file_size = file_path.stat().st_size
                    if file_size > self.MAX_IN_MEMORY_SIZE:
                        # For large files, store hash instead of full content
                        file_hash = self._compute_file_hash(file_path)
                        output_files[str(file_path)] = file_hash
                    else:
                        # For smaller files, load into memory
                        with open(file_path, 'rb') as f:
                            output_files[str(file_path)] = f.read()
                except Exception as e:
                    # Log error but continue processing other files
                    print(f"Warning: Could not read output file {file_path}: {e}")
                    continue
            
            return {
                "success": result.returncode == 0,
                "output_files": output_files,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": result.stderr if result.returncode != 0 else None
            }
        
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output_files": {},
                "stdout": "",
                "stderr": "Workflow execution timed out",
                "error": "Timeout"
            }
        
        except Exception as e:
            return {
                "success": False,
                "output_files": {},
                "stdout": "",
                "stderr": str(e),
                "error": str(e)
            }
    
    def compare_files(self, file1_path: str, file2_path: str) -> bool:
        """
        Compare two files using hash-based comparison for large files.
        
        Args:
            file1_path: Path to first file
            file2_path: Path to second file
            
        Returns:
            True if files are identical, False otherwise
        """
        try:
            file1 = Path(file1_path)
            file2 = Path(file2_path)
            
            if not file1.exists() or not file2.exists():
                return False
            
            # Check file sizes first (quick check)
            if file1.stat().st_size != file2.stat().st_size:
                return False
            
            # For large files, use hash comparison
            if file1.stat().st_size > self.MAX_IN_MEMORY_SIZE:
                return self._compute_file_hash(file1) == self._compute_file_hash(file2)
            
            # For smaller files, use byte-by-byte comparison
            with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
                return f1.read() == f2.read()
        except (OSError, IOError) as e:
            print(f"Error comparing files {file1_path} and {file2_path}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error comparing files: {e}")
            return False
    
    def compare_outputs(
        self,
        actual: Dict[str, Union[bytes, str]],
        expected: Dict[str, bytes]
    ) -> Dict:
        """
        Compare actual and expected output files.
        
        Supports both bytes and hash (string) values in actual dict for large file handling.
        
        Args:
            actual: Dictionary of actual output files {path: content_bytes or hash_string}
            expected: Dictionary of expected output files {path: content_bytes}
            
        Returns:
            {
                "all_match": bool,
                "file_comparisons": dict,  # {file_path: {"match": bool, "diff": str}}
                "differences": list,
                "summary": str
            }
        """
        """
        Compare actual and expected output files.
        
        Args:
            actual: Dictionary of actual output files {path: content_bytes}
            expected: Dictionary of expected output files {path: content_bytes}
        
        Returns:
            {
                "all_match": bool,
                "file_comparisons": dict,  # {file_path: {"match": bool, "diff": str}}
                "differences": list,
                "summary": str
            }
        """
        file_comparisons = {}
        differences = []
        all_match = True
        
        # Compare each expected file
        for expected_path, expected_content in expected.items():
            expected_filename = Path(expected_path).name
            
            # Find matching file in actual outputs
            actual_match = None
            for actual_path, actual_content in actual.items():
                if Path(actual_path).name == expected_filename:
                    actual_match = actual_content
                    break
            
            if actual_match is None:
                # File not found in actual outputs
                file_comparisons[expected_path] = {
                    "match": False,
                    "diff": "File not generated by workflow"
                }
                differences.append(f"Missing file: {expected_filename}")
                all_match = False
            else:
                # Compare content
                # Handle both bytes and hash (for large files)
                if isinstance(actual_match, bytes) and isinstance(expected_content, bytes):
                    # Both are bytes - compare directly
                    if len(expected_content) > self.MAX_IN_MEMORY_SIZE:
                        # Expected file is large - use hash comparison
                        expected_hash = hashlib.sha256(expected_content).hexdigest()
                        actual_hash = hashlib.sha256(actual_match).hexdigest()
                        if expected_hash == actual_hash:
                            file_comparisons[expected_path] = {
                                "match": True,
                                "diff": None
                            }
                        else:
                            file_comparisons[expected_path] = {
                                "match": False,
                                "diff": "File hash differs (large file comparison)"
                            }
                            differences.append(f"File differs: {expected_filename}")
                            all_match = False
                    else:
                        # Both are small - compare directly
                        if actual_match == expected_content:
                            file_comparisons[expected_path] = {
                                "match": True,
                                "diff": None
                            }
                        else:
                            # Files differ
                            file_comparisons[expected_path] = {
                                "match": False,
                                "diff": self._compute_diff(actual_match, expected_content)
                            }
                            differences.append(f"File differs: {expected_filename}")
                            all_match = False
                elif isinstance(actual_match, str) and isinstance(expected_content, bytes):
                    # Actual is hash, expected is bytes - convert expected to hash
                    if len(expected_content) > self.MAX_IN_MEMORY_SIZE:
                        expected_hash = hashlib.sha256(expected_content).hexdigest()
                    else:
                        expected_hash = hashlib.sha256(expected_content).hexdigest()
                    
                    if actual_match == expected_hash:
                        file_comparisons[expected_path] = {
                            "match": True,
                            "diff": None
                        }
                    else:
                        file_comparisons[expected_path] = {
                            "match": False,
                            "diff": "File hash differs (large file comparison)"
                        }
                        differences.append(f"File differs: {expected_filename}")
                        all_match = False
                elif isinstance(actual_match, str) and isinstance(expected_content, str):
                    # Both are hashes - compare hashes
                    if actual_match == expected_content:
                        file_comparisons[expected_path] = {
                            "match": True,
                            "diff": None
                        }
                    else:
                        file_comparisons[expected_path] = {
                            "match": False,
                            "diff": "File hash differs (large file comparison)"
                        }
                        differences.append(f"File differs: {expected_filename}")
                        all_match = False
                else:
                    # Type mismatch - cannot compare
                    file_comparisons[expected_path] = {
                        "match": False,
                        "diff": f"Type mismatch in comparison (actual: {type(actual_match).__name__}, expected: {type(expected_content).__name__})"
                    }
                    differences.append(f"File comparison error: {expected_filename}")
                    all_match = False
        
        # Check for extra files in actual outputs
        expected_filenames = {Path(p).name for p in expected.keys()}
        for actual_path in actual.keys():
            actual_filename = Path(actual_path).name
            if actual_filename not in expected_filenames:
                differences.append(f"Extra file generated: {actual_filename}")
        
        summary = "All files match" if all_match else f"{len(differences)} difference(s) found"
        
        return {
            "all_match": all_match,
            "file_comparisons": file_comparisons,
            "differences": differences,
            "summary": summary
        }
    
    def _compute_diff(self, actual: bytes, expected: bytes) -> str:
        """
        Compute difference between two byte sequences.
        
        Args:
            actual: Actual content
            expected: Expected content
            
        Returns:
            Description of difference
        """
        if len(actual) != len(expected):
            return f"Size difference: actual={len(actual)} bytes, expected={len(expected)} bytes"
        
        # For large files, just report size difference (detailed comparison is expensive)
        if len(actual) > self.MAX_IN_MEMORY_SIZE:
            return f"Large file differs (size: {len(actual)} bytes). Use hash comparison for details."
        
        # Find first differing byte (only for smaller files)
        for i, (a, e) in enumerate(zip(actual, expected)):
            if a != e:
                return f"First difference at byte {i}: actual=0x{a:02x}, expected=0x{e:02x}"
        
        return "Files differ but same size"
    
    def _get_allowed_extensions(self, expected_output_files: Optional[Dict[str, bytes]]) -> Set[str]:
        """
        Get allowed file extensions from expected outputs or use common extensions.
        
        Args:
            expected_output_files: Optional dict of expected output files
            
        Returns:
            Set of allowed file extensions (lowercase, with dot)
        """
        if expected_output_files:
            # Extract extensions from expected output file paths
            extensions = set()
            for output_path in expected_output_files.keys():
                ext = Path(output_path).suffix.lower()
                if ext:
                    extensions.add(ext)
            # Also include common extensions
            extensions.update(self.COMMON_OUTPUT_EXTENSIONS)
            return extensions
        
        # Default to common extensions
        return self.COMMON_OUTPUT_EXTENSIONS
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """
        Compute SHA256 hash of a file for large file comparison.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hexadecimal hash string
        """
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                # Read in chunks to handle large files
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            print(f"Error computing hash for {file_path}: {e}")
            return ""
    
    def _determine_script_arguments(
        self,
        script_path: str,
        input_files: List[str],
        expected_output_files: Optional[Dict[str, bytes]] = None
    ) -> List[str]:
        """
        Determine command-line arguments for workflow script.
        
        Tries to detect if script uses argparse or sys.argv, and formats arguments accordingly.
        
        Args:
            script_path: Path to workflow script
            input_files: List of input file paths
            expected_output_files: Optional dict of expected output files
            
        Returns:
            List of command-line arguments
        """
        try:
            # Read script to analyze argument format
            with open(script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # Check if script uses argparse
            if 'argparse' in script_content or 'ArgumentParser' in script_content:
                # Try to extract argument names from script
                args = []
                
                # Look for common argparse patterns
                # Pattern: add_argument('--input_file', ...) or add_argument("--input_file", ...)
                arg_patterns = re.findall(
                    r'add_argument\(["\']([^"\']+)["\']',
                    script_content
                )
                
                # Map common argument names
                input_arg = None
                output_csv_arg = None
                output_plot_arg = None
                
                for arg in arg_patterns:
                    arg_lower = arg.lower()
                    # Match input arguments: --input, --input_file, --input_path, etc.
                    if 'input' in arg_lower and input_arg is None:
                        input_arg = arg
                    # Match CSV output arguments: --output_csv, --output, --csv, etc.
                    elif 'output' in arg_lower and ('csv' in arg_lower or 'result' in arg_lower):
                        output_csv_arg = arg
                    # Match plot output arguments: --output_plot, --plot, --figure, etc.
                    elif 'output' in arg_lower and ('plot' in arg_lower or 'png' in arg_lower or 'figure' in arg_lower):
                        output_plot_arg = arg
                
                # Build command arguments
                # Support multiple input files
                if input_arg and input_files:
                    # If multiple input files, check if argument supports multiple values
                    # For now, pass all input files (some scripts may accept multiple)
                    for input_file in input_files:
                        args.append(f"{input_arg}")
                        args.append(input_file)
                
                # Determine output paths from expected outputs
                if expected_output_files:
                    for output_path in expected_output_files.keys():
                        output_filename = Path(output_path).name
                        if output_filename.endswith('.csv') and output_csv_arg:
                            args.append(f"{output_csv_arg}")
                            args.append(output_filename)
                        elif output_filename.endswith(('.png', '.jpg', '.jpeg')) and output_plot_arg:
                            args.append(f"{output_plot_arg}")
                            args.append(output_filename)
                
                if args:
                    return args
                
                # If we found argparse but couldn't match arguments, try common patterns
                if input_files:
                    # Try common input argument names
                    for common_input_arg in ['--input', '--input_file', '--input_path', '--file']:
                        # Check if this argument exists in the script
                        if common_input_arg in script_content or common_input_arg.replace('--', '') in script_content:
                            # Pass all input files
                            result = []
                            for input_file in input_files:
                                result.extend([common_input_arg, input_file])
                            return result
                    # Last resort: use --input with all files
                    result = []
                    for input_file in input_files:
                        result.extend(['--input', input_file])
                    return result
            
            # If no argparse detected, check for sys.argv usage
            if 'sys.argv' in script_content:
                # Simple sys.argv: just pass all file paths
                return input_files
            
            # Default: try common argparse patterns with all input files
            if input_files:
                result = []
                for input_file in input_files:
                    result.extend(['--input', input_file])
                return result
            
        except Exception as e:
            print(f"Warning: Could not determine script arguments: {e}")
        
        # Fallback: return all input files as positional arguments
        return input_files if input_files else []
    
    def _cleanup_temp_dir(self) -> None:
        """Clean up temporary directory."""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            # Cleanup 실패는 치명적이지 않지만 로깅은 필요
            print(f"Warning: Failed to cleanup temp directory {self.temp_dir}: {e}")

