"""
Workflow Tracker Module

Tracks code execution history during Agent execution for workflow saving functionality.
Saves execute blocks to files for debugging and workflow reconstruction.
"""

import re
import json
from datetime import datetime
from typing import List, Dict, Optional, Set
from pathlib import Path


class WorkflowTracker:
    """Tracks code execution history for workflow extraction."""
    
    # Constants
    RESULT_TRUNCATE_LENGTH = 10000  # Maximum result length to save in execute blocks
    
    def __init__(self, work_dir: Optional[str] = None):
        """
        Initialize the workflow tracker.
        
        Args:
            work_dir: Working directory path for saving execute blocks
        """
        self.execution_history: List[Dict] = []
        self.all_input_files: Set[str] = set()
        self.all_output_files: Set[str] = set()
        self.work_dir = Path(work_dir) if work_dir else None
        self.execute_blocks_dir = None
        
        # Track session start time to filter execute blocks by session
        self.session_start_time = datetime.now()
        
        # Create directory for saving execute blocks
        # Use workflows/execute_blocks instead of work_dir/execute_blocks
        if self.work_dir:
            # Get project root (parent of work_dir) or use work_dir's parent
            workflows_root = Path(self.work_dir).parent / "workflows"
            self.execute_blocks_dir = workflows_root / "execute_blocks"
            self.execute_blocks_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 Execute blocks save location: {self.execute_blocks_dir}")
            print(f"📅 Session start time: {self.session_start_time.isoformat()}")
    
    def track_execution(
        self,
        code: str,
        result: str,
        success: bool,
        input_files: Optional[List[str]] = None,
        output_files: Optional[List[str]] = None,
        error_type: Optional[str] = None
    ) -> Optional[str]:
        """
        Track code execution with result and file information.
        Also saves execute block to file for debugging and workflow reconstruction.
        
        Args:
            code: Executed code
            result: Execution result
            success: Whether execution was successful
            input_files: List of input file paths used
            output_files: List of output file paths created
            error_type: Type of error if execution failed
        
        Returns:
            Path to saved execute block file, or None if not saved
        """
        timestamp = datetime.now()
        execution_entry = {
            "code": code,
            "result": result,
            "success": success,
            "timestamp": timestamp.isoformat(),
            "error_type": error_type,
            "input_files": input_files or [],
            "output_files": output_files or []
        }
        
        self.execution_history.append(execution_entry)
        
        # Track all input and output files
        if input_files:
            self.all_input_files.update(input_files)
        if output_files:
            self.all_output_files.update(output_files)
        
        # Save execute block to file
        saved_file_path = self._save_execute_block(execution_entry, timestamp)
        
        return saved_file_path
    
    def _save_execute_block(self, execution_entry: Dict, timestamp: datetime) -> Optional[str]:
        """
        Save execute block to file for debugging and workflow reconstruction.
        
        Args:
            execution_entry: Execution entry dictionary
            timestamp: Timestamp of execution
            
        Returns:
            Path to saved file, or None if saving failed
        """
        if not self.execute_blocks_dir:
            return None
        
        try:
            # Create filename with timestamp and index
            index = len(self.execution_history)
            timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")
            filename = f"execute_{timestamp_str}_{index:04d}.json"
            file_path = self.execute_blocks_dir / filename
            
            # Prepare data to save
            save_data = {
                "execution_index": index,
                "timestamp": execution_entry["timestamp"],
                "success": execution_entry["success"],
                "error_type": execution_entry.get("error_type"),
                "code": execution_entry["code"],
                "result": execution_entry["result"][:self.RESULT_TRUNCATE_LENGTH],  # Truncate long results
                "result_length": len(execution_entry["result"]),
                "input_files": execution_entry["input_files"],
                "output_files": execution_entry["output_files"],
                "metadata": {
                    "code_length": len(execution_entry["code"]),
                    "has_error": not execution_entry["success"],
                    "num_input_files": len(execution_entry["input_files"]),
                    "num_output_files": len(execution_entry["output_files"])
                }
            }
            
            # Save as JSON
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            
            # Also save code as separate .py file for easy viewing
            code_file_path = self.execute_blocks_dir / f"execute_{timestamp_str}_{index:04d}.py"
            with open(code_file_path, 'w', encoding='utf-8') as f:
                f.write(f"# Execute block #{index}\n")
                f.write(f"# Timestamp: {execution_entry['timestamp']}\n")
                f.write(f"# Success: {execution_entry['success']}\n")
                if execution_entry.get("error_type"):
                    f.write(f"# Error Type: {execution_entry['error_type']}\n")
                f.write(f"# Input files: {', '.join(execution_entry['input_files']) or 'None'}\n")
                f.write(f"# Output files: {', '.join(execution_entry['output_files']) or 'None'}\n")
                f.write("\n" + "="*80 + "\n\n")
                f.write(execution_entry["code"])
            
            return str(file_path)
        except Exception as e:
            print(f"⚠️  Failed to save execute block: {e}")
            return None
    
    def get_successful_executions(self) -> List[Dict]:
        """
        Get list of successfully executed code blocks.
        
        Returns:
            List of execution entries that were successful
        """
        return [
            entry for entry in self.execution_history
            if entry["success"]
        ]
    
    def get_execution_history(self) -> List[Dict]:
        """
        Get complete execution history.
        
        Returns:
            Complete list of all execution entries
        """
        return self.execution_history.copy()
    
    def get_output_files(self) -> List[str]:
        """
        Get all output files generated during execution.
        
        Returns:
            List of all output file paths
        """
        return list(self.all_output_files)
    
    def get_input_files(self) -> List[str]:
        """
        Get all input files used during execution.
        
        Returns:
            List of all input file paths (resolved to absolute paths)
        """
        resolved_files = []
        for input_file in self.all_input_files:
            file_path = Path(input_file)
            if not file_path.is_absolute() and self.work_dir:
                file_path = self.work_dir / file_path
            resolved_path = file_path.resolve()
            if resolved_path.exists():
                resolved_files.append(str(resolved_path))
        return resolved_files if resolved_files else list(self.all_input_files)
    
    def get_expected_output_files(self) -> Dict[str, bytes]:
        """
        Get expected output files with their content.
        
        This is used for validation - returns a dictionary mapping
        file paths to their content (as bytes).
        
        Returns:
            Dictionary mapping file paths to file content
        """
        output_files_dict = {}
        
        for output_file in self.all_output_files:
            # Resolve path (handle both absolute and relative paths)
            file_path = Path(output_file)
            if not file_path.is_absolute() and self.work_dir:
                file_path = self.work_dir / file_path
            file_path = file_path.resolve()
            
            if file_path.exists() and file_path.is_file():
                try:
                    with open(file_path, 'rb') as f:
                        # Use relative path as key if possible, otherwise absolute
                        key = str(output_file) if output_file in self.all_output_files else str(file_path)
                        output_files_dict[key] = f.read()
                except Exception as e:
                    # Skip files that can't be read
                    print(f"⚠️  Warning: Could not read output file for validation: {file_path} - {e}")
                    continue
        
        return output_files_dict
    
    def extract_input_files_from_code(self, code: str, work_dir: Path) -> List[str]:
        """
        Extract input file paths from code using pattern matching.
        
        Args:
            code: Code string to analyze
            work_dir: Working directory path
            
        Returns:
            List of input file paths found in code
        """
        input_files = []
        
        # Common patterns for file reading operations
        patterns = [
            r'pd\.read_csv\(["\']([^"\']+)["\']',  # pandas read_csv
            r'pd\.read_excel\(["\']([^"\']+)["\']',  # pandas read_excel
            r'open\(["\']([^"\']+)["\']',  # open()
            r'with open\(["\']([^"\']+)["\']',  # with open()
            r'np\.load\(["\']([^"\']+)["\']',  # numpy load
            r'pickle\.load\(open\(["\']([^"\']+)["\']',  # pickle load
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, code)
            for match in matches:
                # Resolve relative paths
                file_path = Path(match)
                if not file_path.is_absolute():
                    file_path = work_dir / file_path
                # If absolute, file_path is already correct, no need to reassign
                
                if file_path.exists():
                    input_files.append(str(file_path.resolve()))
        
        return list(set(input_files))  # Remove duplicates
    
    def extract_output_files_from_result(
        self,
        result: str,
        files_before: Set[Path],
        files_after: Set[Path],
        work_dir: Path
    ) -> List[str]:
        """
        Extract output file paths from execution result and file system changes.
        
        Args:
            result: Execution result string
            files_before: Set of files before execution
            files_after: Set of files after execution
            work_dir: Working directory path
            
        Returns:
            List of output file paths created during execution
        """
        output_files = []
        
        # Get newly created files
        new_files = files_after - files_before
        
        # Filter out directories and common temporary files
        excluded_patterns = [
            r'__pycache__',
            r'\.pyc$',
            r'\.pyo$',
            r'\.pytest_cache',
            r'\.ipynb_checkpoints',
        ]
        
        for file_path in new_files:
            if not file_path.is_file():
                continue
            
            # Check if file matches excluded patterns
            file_str = str(file_path)
            if any(re.search(pattern, file_str) for pattern in excluded_patterns):
                continue
            
            # Only include files in work directory
            try:
                resolved_path = file_path.resolve()
                if str(resolved_path).startswith(str(work_dir.resolve())):
                    output_files.append(str(resolved_path))
            except Exception:
                continue
        
        return list(set(output_files))  # Remove duplicates
    
    def clear(self) -> None:
        """Clear all tracked execution history."""
        self.execution_history.clear()
        self.all_input_files.clear()
        self.all_output_files.clear()
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about tracked executions.
        
        Returns:
            Dictionary with execution statistics
        """
        total = len(self.execution_history)
        successful = len(self.get_successful_executions())
        failed = total - successful
        
        # Count files in current session
        session_file_count = 0
        if self.execute_blocks_dir and self.execute_blocks_dir.exists():
            session_start_str = self.session_start_time.strftime("%Y%m%d_%H%M%S")
            session_files = [
                f for f in self.execute_blocks_dir.glob("execute_*.json")
                if self._is_file_from_current_session(f, session_start_str)
            ]
            session_file_count = len(session_files)
        
        return {
            "total_executions": total,
            "successful_executions": successful,
            "failed_executions": failed,
            "total_input_files": len(self.all_input_files),
            "total_output_files": len(self.all_output_files),
            "execute_blocks_dir": str(self.execute_blocks_dir) if self.execute_blocks_dir else None,
            "session_start_time": self.session_start_time.isoformat(),
            "session_file_count": session_file_count
        }
    
    def load_execute_blocks_from_files(self, filter_by_session: bool = True) -> List[Dict]:
        """
        Load execute blocks from saved files.
        Useful for reconstructing execution history from previous runs.
        
        Args:
            filter_by_session: If True, only load files from current session (default: True)
        
        Returns:
            List of execution entries loaded from files
        """
        if not self.execute_blocks_dir or not self.execute_blocks_dir.exists():
            return []
        
        loaded_blocks = []
        
        # Find all JSON files
        json_files = sorted(self.execute_blocks_dir.glob("execute_*.json"))
        
        # Filter by session start time if requested
        if filter_by_session:
            session_start_str = self.session_start_time.strftime("%Y%m%d_%H%M%S")
            # Only load files created after session start
            json_files = [
                f for f in json_files
                if self._is_file_from_current_session(f, session_start_str)
            ]
        
        if not json_files:
            if filter_by_session:
                print(f"ℹ️  No execute block files found for current session (started at {self.session_start_time.isoformat()})")
            return []
        
        print(f"📂 Loading {len(json_files)} execute block file(s) from {'current session' if filter_by_session else 'all sessions'}")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Reconstruct execution entry
                execution_entry = {
                    "code": data["code"],
                    "result": data["result"],
                    "success": data["success"],
                    "timestamp": data["timestamp"],
                    "error_type": data.get("error_type"),
                    "input_files": data["input_files"],
                    "output_files": data["output_files"]
                }
                
                loaded_blocks.append(execution_entry)
            except Exception as e:
                print(f"⚠️  Failed to load execute block from {json_file}: {e}")
        
        # Sort by timestamp to maintain execution order
        loaded_blocks.sort(key=lambda x: x["timestamp"])
        
        return loaded_blocks
    
    def _is_file_from_current_session(self, file_path: Path, session_start_str: str) -> bool:
        """
        Check if file belongs to current session based on filename timestamp.
        
        Args:
            file_path: Path to execute block file
            session_start_str: Session start time string (YYYYMMDD_HHMMSS format)
        
        Returns:
            True if file belongs to current session
        """
        try:
            # Extract timestamp from filename: execute_YYYYMMDD_HHMMSS_microseconds_index.json
            filename = file_path.name
            # Pattern: execute_20251222_170618_536103_0001.json
            parts = filename.replace('execute_', '').replace('.json', '').split('_')
            if len(parts) >= 2:
                file_date_time = f"{parts[0]}_{parts[1]}"  # YYYYMMDD_HHMMSS
                # Compare date and time strings
                return file_date_time >= session_start_str
        except Exception:
            # If parsing fails, include the file to be safe
            return True
        return True

