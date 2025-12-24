"""
Workflow Validator Module

System-internal validation to ensure workflow produces identical outputs.
"""

import subprocess
import tempfile
import shutil
import re
import ast
from pathlib import Path
from typing import Dict, List, Optional
import hashlib


class WorkflowValidator:
    """Validates that saved workflow produces identical outputs to Agent execution."""
    
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
        for input_file in input_files:
            src = Path(input_file)
            if src.exists():
                dst = exec_dir / src.name
                shutil.copy2(src, dst)
                copied_input_files.append(str(dst))
        
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
                timeout=300  # 5 minute timeout
            )
            
            # Collect output files from execution directory
            output_files = {}
            for file_path in exec_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix in ['.csv', '.xlsx', '.json', '.txt', '.png', '.jpg', '.jpeg', '.pkl']:
                    # Skip input files
                    if file_path.name not in [Path(f).name for f in input_files]:
                        try:
                            with open(file_path, 'rb') as f:
                                output_files[str(file_path)] = f.read()
                        except Exception:
                            pass
            
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
        Compare two files byte-by-byte.
        
        Args:
            file1_path: Path to first file
            file2_path: Path to second file
        
        Returns:
            True if files are identical, False otherwise
        """
        try:
            with open(file1_path, 'rb') as f1, open(file2_path, 'rb') as f2:
                return f1.read() == f2.read()
        except Exception:
            return False
    
    def compare_outputs(
        self,
        actual: Dict[str, bytes],
        expected: Dict[str, bytes]
    ) -> Dict:
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
                # Compare content byte-by-byte
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
        
        # Find first differing byte
        for i, (a, e) in enumerate(zip(actual, expected)):
            if a != e:
                return f"First difference at byte {i}: actual=0x{a:02x}, expected=0x{e:02x}"
        
        return "Files differ but same size"
    
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
                if input_arg and input_files:
                    args.append(f"{input_arg}")
                    args.append(input_files[0])  # Use first input file
                
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
                            return [common_input_arg, input_files[0]]
                    # Last resort: use --input
                    return ['--input', input_files[0]]
            
            # If no argparse detected, check for sys.argv usage
            if 'sys.argv' in script_content:
                # Simple sys.argv: just pass file paths
                return input_files
            
            # Default: try common argparse patterns
            if input_files:
                return ['--input', input_files[0]]
            
        except Exception as e:
            print(f"Warning: Could not determine script arguments: {e}")
        
        # Fallback: return input files as positional arguments
        return input_files
    
    def _cleanup_temp_dir(self) -> None:
        """Clean up temporary directory."""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass  # Ignore cleanup errors

