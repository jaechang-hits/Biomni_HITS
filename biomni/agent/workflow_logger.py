"""
Workflow Logger Module

Enhanced logging system for workflow generation process.
Provides detailed logging for debugging and quality assurance.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime


class WorkflowLogger:
    """
    Enhanced logger for workflow generation process.
    
    Provides structured logging with different log levels and
    saves logs to files for later analysis.
    """
    
    def __init__(self, log_dir: Optional[Path] = None, log_to_file: bool = True):
        """
        Initialize workflow logger.
        
        Args:
            log_dir: Directory to save log files (default: workflows/logs)
            log_to_file: Whether to save logs to file
        """
        self.log_to_file = log_to_file
        self.log_dir = log_dir
        
        if log_to_file and log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.log_file = self.log_dir / f"workflow_generation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        else:
            self.log_file = None
        
        # Create logger
        self.logger = logging.getLogger('workflow_generation')
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (if enabled)
        if log_to_file and self.log_file:
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def log_workflow_start(self, workflow_name: str, num_executions: int):
        """Log workflow generation start."""
        self.logger.info("="*80)
        self.logger.info(f"WORKFLOW GENERATION STARTED: {workflow_name}")
        self.logger.info(f"  Total executions: {num_executions}")
        self.logger.info("="*80)
    
    def log_execution_summary(self, executions: List[Dict]):
        """Log summary of executions."""
        self.logger.debug("Execution Summary:")
        for idx, exec_entry in enumerate(executions, 1):
            code_preview = exec_entry.get("code", "")[:100].replace('\n', ' ')
            success = exec_entry.get("success", False)
            output_files = exec_entry.get("output_files", [])
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
        """Log filtering results."""
        self.logger.info(f"Filtering: {total_executions} → {filtered_executions} executions")
        if filter_reasons:
            self.logger.debug(f"Filter reasons: {filter_reasons}")
    
    def log_preprocessing_results(self, preprocessed_data: Dict):
        """Log preprocessing results."""
        self.logger.info("Preprocessing Results:")
        self.logger.info(f"  - Imports: {len(preprocessed_data.get('imports', []))}")
        self.logger.info(f"  - Output files mapped: {len(preprocessed_data.get('output_file_mapping', {}))}")
        self.logger.info(f"  - Hardcoded paths: {len(preprocessed_data.get('hardcoded_paths', []))}")
        self.logger.info(f"  - Functions extracted: {len(preprocessed_data.get('functions', []))}")
        
        # Log output file mapping details
        output_mapping = preprocessed_data.get('output_file_mapping', {})
        if output_mapping:
            self.logger.debug("Output file mapping:")
            for file_name, exec_indices in output_mapping.items():
                self.logger.debug(f"  - {file_name}: executions {exec_indices}")
    
    def log_llm_request(self, prompt_length: int, has_preprocessed_data: bool):
        """Log LLM request details."""
        self.logger.info(f"LLM Request: prompt_length={prompt_length}, has_preprocessed_data={has_preprocessed_data}")
    
    def log_llm_response(self, response_length: int, code_length: int):
        """Log LLM response details."""
        self.logger.info(f"LLM Response: response_length={response_length}, code_length={code_length}")
    
    def log_postprocessing_results(self, validation_report: Dict):
        """Log postprocessing results."""
        self.logger.info("Postprocessing Results:")
        if validation_report.get("import_issues"):
            self.logger.info(f"  - Import issues fixed: {len(validation_report['import_issues'])}")
            for issue in validation_report['import_issues'][:3]:
                self.logger.debug(f"    {issue}")
        if validation_report.get("output_file_issues"):
            self.logger.warning(f"  - Output file issues: {len(validation_report['output_file_issues'])}")
            for issue in validation_report['output_file_issues'][:3]:
                self.logger.warning(f"    {issue}")
        if validation_report.get("syntax_errors"):
            self.logger.error(f"  - Syntax errors: {len(validation_report['syntax_errors'])}")
            for error in validation_report['syntax_errors']:
                self.logger.error(f"    {error}")
        if validation_report.get("fixes_applied"):
            self.logger.info(f"  - Auto-fixes applied: {len(validation_report['fixes_applied'])}")
            for fix in validation_report['fixes_applied'][:3]:
                self.logger.debug(f"    {fix}")
    
    def log_workflow_quality(
        self,
        workflow_code: str,
        expected_output_files: List[str],
        generated_output_files: List[str]
    ):
        """Log workflow quality metrics."""
        self.logger.info("Workflow Quality Assessment:")
        
        # Code metrics
        num_functions = workflow_code.count('def ')
        num_classes = workflow_code.count('class ')
        num_lines = len(workflow_code.split('\n'))
        
        self.logger.info(f"  - Code size: {num_lines} lines, {num_functions} functions, {num_classes} classes")
        
        # Output file coverage
        missing_outputs = set(expected_output_files) - set(generated_output_files)
        if missing_outputs:
            self.logger.warning(f"  - Missing output files: {missing_outputs}")
        else:
            self.logger.info(f"  - All {len(expected_output_files)} output files are generated")
    
    def log_workflow_complete(self, workflow_path: str, description_path: Optional[str] = None):
        """Log workflow generation completion."""
        self.logger.info("="*80)
        self.logger.info(f"WORKFLOW GENERATION COMPLETED")
        self.logger.info(f"  Workflow file: {workflow_path}")
        if description_path:
            self.logger.info(f"  Description file: {description_path}")
        self.logger.info("="*80)
    
    def log_error(self, error_message: str, exception: Optional[Exception] = None):
        """Log error with full traceback."""
        self.logger.error(f"ERROR: {error_message}")
        if exception:
            import traceback
            self.logger.error(traceback.format_exc())
    
    def log_warning(self, warning_message: str):
        """Log warning."""
        self.logger.warning(f"WARNING: {warning_message}")
    
    def get_log_file_path(self) -> Optional[str]:
        """Get path to log file."""
        return str(self.log_file) if self.log_file else None


