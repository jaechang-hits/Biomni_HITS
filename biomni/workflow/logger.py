"""
Workflow Logger Module

Enhanced logging system for workflow generation process.
Provides detailed logging for debugging and quality assurance.
"""

import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime


class WorkflowLogger:
    """
    Enhanced logger for workflow generation process.
    
    Provides structured logging with different log levels and
    saves logs to files for later analysis.
    """
    
    # Constants
    SEPARATOR_LENGTH = 80
    CODE_PREVIEW_LENGTH = 100
    MAX_ISSUES_TO_LOG = 3
    
    def __init__(self, log_dir: Optional[Path] = None, log_to_file: bool = True):
        """
        Initialize workflow logger.
        
        Args:
            log_dir: Directory to save log files (can be Path or string)
            log_to_file: Whether to save logs to file
        """
        self.log_to_file = log_to_file
        
        # Convert log_dir to Path if needed
        if log_dir is not None:
            if isinstance(log_dir, str):
                self.log_dir = Path(log_dir)
            elif isinstance(log_dir, Path):
                self.log_dir = log_dir
            else:
                self.log_dir = None
                self.log_to_file = False
        else:
            self.log_dir = None
        
        self.log_file = None
        self.file_handler = None
        
        # Create logger with unique name to avoid handler accumulation
        logger_name = f'workflow_generation_{uuid.uuid4().hex[:8]}'
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers and close them properly
        for handler in self.logger.handlers[:]:
            try:
                handler.close()
            except Exception:
                pass
        self.logger.handlers.clear()
        
        # Console handler
        try:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
        except Exception as e:
            # Fallback: use basic logging if console handler fails
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(logger_name)
        
        # File handler (if enabled)
        if self.log_to_file and self.log_dir:
            try:
                # Create directory if it doesn't exist
                self.log_dir.mkdir(parents=True, exist_ok=True)
                
                # Create log file path
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                self.log_file = self.log_dir / f"workflow_generation_{timestamp}.log"
                
                # Create file handler
                self.file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
                self.file_handler.setLevel(logging.DEBUG)
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                self.file_handler.setFormatter(file_formatter)
                self.logger.addHandler(self.file_handler)
            except (OSError, PermissionError, IOError) as e:
                # Log error but don't crash - continue without file logging
                self.log_to_file = False
                self.log_file = None
                self.logger.warning(f"Failed to create log file: {e}")
            except Exception as e:
                # Catch any other unexpected errors
                self.log_to_file = False
                self.log_file = None
                self.logger.warning(f"Unexpected error creating log file: {e}")
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def log_workflow_start(self, workflow_name: str, num_executions: int):
        """
        Log workflow generation start.
        
        Args:
            workflow_name: Name of the workflow
            num_executions: Number of executions
        """
        # Input validation
        if not isinstance(workflow_name, str):
            workflow_name = str(workflow_name) if workflow_name is not None else "Unknown"
        
        if not isinstance(num_executions, int):
            try:
                num_executions = int(num_executions) if num_executions is not None else 0
            except (ValueError, TypeError):
                num_executions = 0
        
        separator = "=" * self.SEPARATOR_LENGTH
        self.logger.info(separator)
        self.logger.info(f"WORKFLOW GENERATION STARTED: {workflow_name}")
        self.logger.info(f"  Total executions: {num_executions}")
        self.logger.info(separator)
    
    def log_execution_summary(self, executions: List[Dict]):
        """
        Log summary of executions.
        
        Args:
            executions: List of execution dictionaries
        """
        # Input validation
        if not isinstance(executions, list):
            return
        
        self.logger.debug("Execution Summary:")
        for idx, exec_entry in enumerate(executions, 1):
            if not isinstance(exec_entry, dict):
                continue
            
            # Safely get code preview
            code = exec_entry.get("code", "")
            if isinstance(code, str):
                # Limit length before replace for efficiency
                if len(code) > self.CODE_PREVIEW_LENGTH:
                    code_preview = code[:self.CODE_PREVIEW_LENGTH].replace('\n', ' ')
                else:
                    code_preview = code.replace('\n', ' ')
            else:
                code_preview = str(code)[:self.CODE_PREVIEW_LENGTH] if code is not None else ""
            
            success = exec_entry.get("success", False)
            
            # Safely get output files
            output_files = exec_entry.get("output_files", [])
            if not isinstance(output_files, list):
                output_files = []
            
            self.logger.debug(
                f"  [{idx}] Success: {success}, "
                f"Output files: {len(output_files)}, "
                f"Code preview: {code_preview}..."
            )
    
    def log_filtering_results(
        self, 
        total_executions: int, 
        filtered_executions: int,
        filter_reasons: Optional[Dict] = None
    ):
        """
        Log filtering results.
        
        Args:
            total_executions: Total number of executions
            filtered_executions: Number of executions after filtering
            filter_reasons: Optional dictionary of filter reasons
        """
        # Input validation
        if not isinstance(total_executions, int):
            try:
                total_executions = int(total_executions) if total_executions is not None else 0
            except (ValueError, TypeError):
                total_executions = 0
        
        if not isinstance(filtered_executions, int):
            try:
                filtered_executions = int(filtered_executions) if filtered_executions is not None else 0
            except (ValueError, TypeError):
                filtered_executions = 0
        
        self.logger.info(f"Filtering: {total_executions} → {filtered_executions} executions")
        if filter_reasons and isinstance(filter_reasons, dict):
            self.logger.debug(f"Filter reasons: {filter_reasons}")
    
    def log_preprocessing_results(self, preprocessed_data: Dict):
        """
        Log preprocessing results.
        
        Args:
            preprocessed_data: Dictionary with preprocessing results
        """
        # Input validation
        if not isinstance(preprocessed_data, dict):
            return
        
        self.logger.info("Preprocessing Results:")
        
        # Safely get and log imports
        imports = preprocessed_data.get('imports', [])
        if isinstance(imports, list):
            self.logger.info(f"  - Imports: {len(imports)}")
        else:
            self.logger.info(f"  - Imports: 0 (invalid data)")
        
        # Safely get and log output file mapping
        output_mapping = preprocessed_data.get('output_file_mapping', {})
        if isinstance(output_mapping, dict):
            self.logger.info(f"  - Output files mapped: {len(output_mapping)}")
        else:
            self.logger.info(f"  - Output files mapped: 0 (invalid data)")
        
        # Safely get and log hardcoded paths
        hardcoded_paths = preprocessed_data.get('hardcoded_paths', [])
        if isinstance(hardcoded_paths, list):
            self.logger.info(f"  - Hardcoded paths: {len(hardcoded_paths)}")
        else:
            self.logger.info(f"  - Hardcoded paths: 0 (invalid data)")
        
        # Safely get and log functions
        functions = preprocessed_data.get('functions', [])
        if isinstance(functions, list):
            self.logger.info(f"  - Functions extracted: {len(functions)}")
        else:
            self.logger.info(f"  - Functions extracted: 0 (invalid data)")
        
        # Log output file mapping details
        if isinstance(output_mapping, dict) and output_mapping:
            self.logger.debug("Output file mapping:")
            for file_name, exec_indices in output_mapping.items():
                if isinstance(exec_indices, list):
                    self.logger.debug(f"  - {file_name}: executions {exec_indices}")
                else:
                    self.logger.debug(f"  - {file_name}: executions (invalid data)")
    
    def log_llm_request(self, prompt_length: int, has_preprocessed_data: bool):
        """
        Log LLM request details.
        
        Args:
            prompt_length: Length of the prompt
            has_preprocessed_data: Whether preprocessed data is included
        """
        # Input validation
        if not isinstance(prompt_length, int):
            try:
                prompt_length = int(prompt_length) if prompt_length is not None else 0
            except (ValueError, TypeError):
                prompt_length = 0
        
        if not isinstance(has_preprocessed_data, bool):
            has_preprocessed_data = bool(has_preprocessed_data)
        
        self.logger.info(f"LLM Request: prompt_length={prompt_length}, has_preprocessed_data={has_preprocessed_data}")
    
    def log_llm_response(self, response_length: int, code_length: int):
        """
        Log LLM response details.
        
        Args:
            response_length: Length of the response
            code_length: Length of the extracted code
        """
        # Input validation
        if not isinstance(response_length, int):
            try:
                response_length = int(response_length) if response_length is not None else 0
            except (ValueError, TypeError):
                response_length = 0
        
        if not isinstance(code_length, int):
            try:
                code_length = int(code_length) if code_length is not None else 0
            except (ValueError, TypeError):
                code_length = 0
        
        self.logger.info(f"LLM Response: response_length={response_length}, code_length={code_length}")
    
    def log_postprocessing_results(self, validation_report: Dict):
        """
        Log postprocessing results.
        
        Args:
            validation_report: Dictionary with validation results
        """
        # Input validation
        if not isinstance(validation_report, dict):
            return
        
        self.logger.info("Postprocessing Results:")
        
        # Safely get and log import issues
        import_issues = validation_report.get("import_issues", [])
        if isinstance(import_issues, list) and import_issues:
            self.logger.info(f"  - Import issues fixed: {len(import_issues)}")
            for issue in import_issues[:self.MAX_ISSUES_TO_LOG]:
                if isinstance(issue, str):
                    self.logger.debug(f"    {issue}")
        
        # Safely get and log output file issues
        output_file_issues = validation_report.get("output_file_issues", [])
        if isinstance(output_file_issues, list) and output_file_issues:
            self.logger.warning(f"  - Output file issues: {len(output_file_issues)}")
            for issue in output_file_issues[:self.MAX_ISSUES_TO_LOG]:
                if isinstance(issue, str):
                    self.logger.warning(f"    {issue}")
        
        # Safely get and log syntax errors
        syntax_errors = validation_report.get("syntax_errors", [])
        if isinstance(syntax_errors, list) and syntax_errors:
            self.logger.error(f"  - Syntax errors: {len(syntax_errors)}")
            for error in syntax_errors:
                if isinstance(error, str):
                    self.logger.error(f"    {error}")
        
        # Safely get and log fixes applied
        fixes_applied = validation_report.get("fixes_applied", [])
        if isinstance(fixes_applied, list) and fixes_applied:
            self.logger.info(f"  - Auto-fixes applied: {len(fixes_applied)}")
            for fix in fixes_applied[:self.MAX_ISSUES_TO_LOG]:
                if isinstance(fix, str):
                    self.logger.debug(f"    {fix}")
    
    def log_workflow_quality(
        self,
        workflow_code: str,
        expected_output_files: List[str],
        generated_output_files: List[str]
    ):
        """
        Log workflow quality metrics.
        
        Args:
            workflow_code: Generated workflow code
            expected_output_files: List of expected output file names
            generated_output_files: List of generated output file names
        """
        # Input validation
        if not isinstance(workflow_code, str):
            workflow_code = str(workflow_code) if workflow_code is not None else ""
        
        if not isinstance(expected_output_files, list):
            expected_output_files = []
        
        if not isinstance(generated_output_files, list):
            generated_output_files = []
        
        self.logger.info("Workflow Quality Assessment:")
        
        # Code metrics (optimized: use count instead of split for line count)
        num_functions = workflow_code.count('def ')
        num_classes = workflow_code.count('class ')
        num_lines = workflow_code.count('\n') + 1 if workflow_code else 0
        
        self.logger.info(f"  - Code size: {num_lines} lines, {num_functions} functions, {num_classes} classes")
        
        # Output file coverage
        expected_set = set(expected_output_files)
        generated_set = set(generated_output_files)
        missing_outputs = expected_set - generated_set
        
        if missing_outputs:
            self.logger.warning(f"  - Missing output files: {missing_outputs}")
        else:
            self.logger.info(f"  - All {len(expected_output_files)} output files are generated")
    
    def log_workflow_complete(self, workflow_path: str, description_path: Optional[str] = None):
        """
        Log workflow generation completion.
        
        Args:
            workflow_path: Path to the generated workflow file
            description_path: Optional path to the description file
        """
        # Input validation
        if not isinstance(workflow_path, str):
            workflow_path = str(workflow_path) if workflow_path is not None else "Unknown"
        
        separator = "=" * self.SEPARATOR_LENGTH
        self.logger.info(separator)
        self.logger.info(f"WORKFLOW GENERATION COMPLETED")
        self.logger.info(f"  Workflow file: {workflow_path}")
        if description_path and isinstance(description_path, str):
            self.logger.info(f"  Description file: {description_path}")
        self.logger.info(separator)
    
    def log_error(self, error_message: str, exception: Optional[Exception] = None):
        """
        Log error with full traceback.
        
        Args:
            error_message: Error message string
            exception: Optional exception object
        """
        # Input validation
        if not isinstance(error_message, str):
            error_message = str(error_message) if error_message is not None else "Unknown error"
        
        self.logger.error(f"ERROR: {error_message}")
        if exception:
            import traceback
            try:
                self.logger.error(traceback.format_exc())
            except Exception:
                # Fallback if traceback fails
                self.logger.error(f"Exception: {type(exception).__name__}: {str(exception)}")
    
    def log_warning(self, warning_message: str):
        """
        Log warning.
        
        Args:
            warning_message: Warning message string
        """
        # Input validation
        if not isinstance(warning_message, str):
            warning_message = str(warning_message) if warning_message is not None else "Unknown warning"
        
        self.logger.warning(f"WARNING: {warning_message}")
    
    def get_log_file_path(self) -> Optional[str]:
        """
        Get path to log file.
        
        Returns:
            Path to log file as string, or None if not available
        """
        return str(self.log_file) if self.log_file else None
    
    def close(self):
        """
        Close file handlers and clean up resources.
        
        Should be called when logger is no longer needed to ensure
        file handles are properly closed.
        """
        if self.file_handler:
            try:
                self.file_handler.close()
            except Exception:
                pass
            self.file_handler = None
        
        # Close all handlers
        for handler in self.logger.handlers[:]:
            try:
                handler.close()
            except Exception:
                pass
        
        self.logger.handlers.clear()


