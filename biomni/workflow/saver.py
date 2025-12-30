"""
Workflow Saver Module

Saves workflow code as standalone Python scripts with metadata.
"""

import os
import re
import ast
import json
from pathlib import Path
from typing import Optional, Dict, List, Set
from datetime import datetime

from biomni.workflow.tracker import WorkflowTracker
from biomni.workflow.utils.code_filter import CodeFilter
from biomni.workflow.utils.code_extractor import CodeExtractor
from biomni.workflow.llm_processor import WorkflowLLMProcessor
from biomni.workflow.validator import WorkflowValidator
from biomni.workflow.preprocessor import WorkflowPreprocessor
from biomni.workflow.postprocessor import WorkflowPostprocessor
from biomni.workflow.logger import WorkflowLogger


class WorkflowSaver:
    """Saves workflow code as standalone Python scripts."""
    
    # Constants
    MAX_FILENAME_LENGTH = 50
    DEFAULT_MAX_FIX_ATTEMPTS = 2
    DEFAULT_MAX_RETRIES = 5
    MAX_ERRORS_TO_SHOW = 5
    MAX_DIFFERENCES_TO_SHOW = 10
    MAX_STDERR_LENGTH = 1000
    
    # Common intermediate file patterns (files that should be read from output_dir)
    COMMON_INTERMEDIATE_PATTERNS = [
        r'metadata\.csv', r'filtered.*\.csv', r'deg_results\.csv', 
        r'results\.csv', r'pca.*\.csv', r'enrichment.*\.csv'
    ]
    
    # Pre-compiled regex patterns for performance
    _READ_CSV_PATTERN = re.compile(r'pd\.read_csv\(["\']([^"\']+)["\']')
    _READ_PARQUET_PATTERN = re.compile(r'pd\.read_parquet\(["\']([^"\']+)["\']')
    _TO_CSV_PATTERN = re.compile(r'\.to_csv\(["\']([^"\']+)["\']([^)]*)\)')
    _SAVEFIG_PATTERN = re.compile(r'(?:plt\.)?\.savefig\(["\']([^"\']+)["\']([^)]*)\)')
    _PLT_SAVEFIG_PATTERN = re.compile(r'plt\.savefig\(["\']([^"\']+)["\']([^)]*)\)')
    _FILE_PATH_ASSIGN_PATTERN = re.compile(r'^(\s*)file_path\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
    _READ_CSV_FULL_PATTERN = re.compile(r'pd\.read_csv\(["\']([^"\']+)["\']([^)]*)\)')
    _READ_PARQUET_FULL_PATTERN = re.compile(r'pd\.read_parquet\(["\']([^"\']+)["\']([^)]*)\)')
    
    # Pre-compiled regex patterns for undefined name checking
    _PD_PATTERN = re.compile(r'\bpd\.')
    _NP_PATTERN = re.compile(r'\bnp\.')
    _PLT_PATTERN = re.compile(r'\bplt\.')
    _SNS_PATTERN = re.compile(r'\bsns\.')
    
    def __init__(self, llm, work_dir: str, validator: Optional['WorkflowValidator'] = None):
        """
        Initialize with LLM and work directory.
        
        Args:
            llm: LLM instance for processing
            work_dir: Working directory path
            validator: Optional WorkflowValidator instance for validation
        """
        self.llm = llm
        self.work_dir = Path(work_dir)
        # Use workflows/workflows instead of work_dir/workflows
        workflows_root = self.work_dir.parent / "workflows"
        self.workflows_dir = workflows_root / "workflows"
        
        # Ensure workflows directory exists
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize logger
        log_dir = workflows_root / "logs"
        self.logger = WorkflowLogger(log_dir=log_dir, log_to_file=True)
        
        # Initialize processors
        self.code_filter = CodeFilter()
        self.code_extractor = CodeExtractor()
        self.preprocessor = WorkflowPreprocessor()
        self.postprocessor = WorkflowPostprocessor()
        self.llm_processor = WorkflowLLMProcessor(llm)
        self.validator = validator
    
    def save_workflow(
        self,
        tracker: WorkflowTracker,
        workflow_name: Optional[str] = None,
        save_mode: str = "notebook"  # "llm", "simple", or "notebook"
    ) -> Optional[str]:
        """
        Save workflow automatically at session end.
        First tries to load from saved execute block files, then falls back to in-memory history.
        
        Args:
            tracker: WorkflowTracker instance with execution history
            workflow_name: Optional workflow name (auto-extracted if not provided)
            save_mode: Save mode - "llm", "simple", or "notebook" (default: "notebook")
            
        Returns:
            Path to saved workflow file, or None if saving failed
        """
        # Input validation
        if not isinstance(tracker, WorkflowTracker):
            self.logger.log_error("Invalid tracker: must be WorkflowTracker instance")
            return None
        
        if workflow_name is not None and not isinstance(workflow_name, str):
            workflow_name = str(workflow_name) if workflow_name else None
        
        if not isinstance(save_mode, str) or save_mode not in ["llm", "simple", "notebook"]:
            save_mode = "notebook"
        
        # Get in-memory history first (most up-to-date)
        try:
            in_memory_history = tracker.get_execution_history()
        except Exception as e:
            self.logger.log_error(f"Failed to get execution history: {e}")
            return None
        
        # Try to load execute blocks from files (for debugging and reconstruction)
        # Only load files from current session to avoid mixing with previous runs
        try:
            file_history = tracker.load_execute_blocks_from_files(filter_by_session=True)
        except Exception as e:
            self.logger.logger.warning(f"Failed to load execute blocks from files: {e}")
            file_history = []
        
        # Decide which history to use
        if in_memory_history:
            # Prefer in-memory history as it's always current
            execution_history = in_memory_history
            if file_history:
                # Verify file history matches memory history (for debugging)
                memory_count = len(in_memory_history)
                file_count = len(file_history)
                if memory_count != file_count:
                    print(f"ℹ️  Using in-memory history ({memory_count} blocks). File history has {file_count} blocks.")
                else:
                    print(f"ℹ️  Using in-memory history ({memory_count} blocks). File history matches.")
            else:
                print(f"ℹ️  Using in-memory execution history ({len(in_memory_history)} blocks)")
        elif file_history:
            # Fallback to file history if memory is empty
            execution_history = file_history
            print(f"ℹ️  Using execute block files from current session ({len(file_history)} blocks)")
        else:
            # No history available
            execution_history = []
        
        if not execution_history:
            print("ℹ️  No execution history to save.")
            print(f"   Execute blocks directory: {tracker.execute_blocks_dir}")
            if tracker.execute_blocks_dir and tracker.execute_blocks_dir.exists():
                # Show both current session and all files for debugging
                session_files = list(tracker.execute_blocks_dir.glob("execute_*.json"))
                all_files = list(tracker.execute_blocks_dir.glob("execute_*.json"))
                print(f"   Found {len(session_files)} execute block file(s) in current session")
                print(f"   Found {len(all_files)} execute block file(s) total in directory")
            return None
        
        # Choose save mode
        if save_mode == "simple":
            return self._save_workflow_simple(execution_history, workflow_name)
        elif save_mode == "notebook":
            return self._save_workflow_notebook(execution_history, workflow_name)
        else:  # "llm"
            return self._save_workflow_llm(execution_history, workflow_name)
    
    def _save_workflow_llm(
        self,
        execution_history: List[Dict],
        workflow_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Save workflow using LLM-based approach (original method).
        
        Args:
            execution_history: List of execution dictionaries
            workflow_name: Optional workflow name
            
        Returns:
            Path to saved workflow file, or None if saving failed
        """
        # Input validation
        if not isinstance(execution_history, list):
            self.logger.log_error("Invalid execution_history: must be a list")
            return None
        
        if workflow_name is not None and not isinstance(workflow_name, str):
            workflow_name = str(workflow_name) if workflow_name else None
        
        # Log workflow generation start
        if not workflow_name:
            temp_name = "unnamed"
        else:
            temp_name = workflow_name
        self.logger.log_workflow_start(temp_name, len(execution_history))
        
        # Log execution summary
        self.logger.log_execution_summary(execution_history)
        
        # Filter to data processing code (with validation)
        try:
            filtered_executions = self.code_filter.filter_executions(execution_history)
            if not isinstance(filtered_executions, list):
                filtered_executions = []
        except Exception as e:
            self.logger.log_error(f"Failed to filter executions: {e}")
            filtered_executions = []
        
        # Log filtering results
        filter_reasons = {
            "total": len(execution_history),
            "filtered": len(filtered_executions),
            "removed": len(execution_history) - len(filtered_executions)
        }
        self.logger.log_filtering_results(
            len(execution_history),
            len(filtered_executions),
            filter_reasons
        )
        
        if not filtered_executions:
            self.logger.log_warning("No data processing code found in execution history.")
            print("No data processing code found in execution history.")
            return None
        
        # Extract workflow name if not provided
        if not workflow_name:
            workflow_name = self.get_workflow_name(filtered_executions)
            self.logger.logger.info(f"Auto-extracted workflow name: {workflow_name}")
        
        # Preprocess executions using rule-based methods (Phase 1: Hybrid approach)
        print("🔧 Preprocessing executions using rule-based methods...")
        self.logger.logger.info("Preprocessing executions using rule-based methods...")
        try:
            preprocessed_data = self.preprocessor.preprocess(filtered_executions)
            if not isinstance(preprocessed_data, dict):
                preprocessed_data = {}
        except Exception as e:
            self.logger.log_error(f"Failed to preprocess executions: {e}")
            preprocessed_data = {}
        
        # Log preprocessing results
        self.logger.log_preprocessing_results(preprocessed_data)
        
        print(f"   ✓ Extracted {len(preprocessed_data['imports'])} imports")
        print(f"   ✓ Mapped {len(preprocessed_data['output_file_mapping'])} output files")
        print(f"   ✓ Identified {len(preprocessed_data['hardcoded_paths'])} hardcoded paths")
        print(f"   ✓ Extracted {len(preprocessed_data['functions'])} functions")
        
        # Generate workflow code using LLM with retry logic (Phase 2: Auto-retry)
        expected_output_files = list(preprocessed_data.get('output_file_mapping', {}).keys())
        max_retries = self.DEFAULT_MAX_RETRIES
        workflow_code = None
        missing_outputs = []
        all_missing_outputs_history = []  # Track all missing outputs across attempts
        
        for attempt in range(max_retries):
            self.logger.logger.info(f"Generating workflow code using LLM... (Attempt {attempt + 1}/{max_retries})")
            prompt_length = len(str(preprocessed_data)) if preprocessed_data else 0
            self.logger.log_llm_request(prompt_length, preprocessed_data is not None)
            
            # Build cumulative missing outputs list (all files that were missing in any previous attempt)
            cumulative_missing = list(set(missing_outputs + [f for prev_missing in all_missing_outputs_history for f in prev_missing]))
            
            # Pass cumulative missing outputs and previous attempt code for retry attempts
            workflow_code = self.llm_processor.extract_workflow_code(
                filtered_executions, 
                preprocessed_data=preprocessed_data,
                missing_outputs=cumulative_missing if attempt > 0 else None,
                retry_attempt=attempt,
                previous_attempt_code=workflow_code if attempt > 0 else None
            )
            
            if not workflow_code:
                self.logger.log_error("Failed to generate workflow code from LLM.")
                print("Failed to generate workflow code from LLM.")
                return None
            
            # Log LLM response
            self.logger.log_llm_response(len(workflow_code), len(workflow_code))
            self.logger.logger.debug(f"Generated workflow code preview: {workflow_code[:200]}...")
            
            # Apply rule-based fixes immediately after LLM generation
            print("🔧 Applying rule-based fixes to LLM-generated code...")
            self.logger.logger.info("Applying rule-based fixes to LLM-generated code...")
            workflow_code = self._apply_rule_based_fixes(workflow_code)
            
            # Postprocess LLM-generated code using rule-based methods (Phase 3: Hybrid approach)
            print("🔧 Postprocessing workflow code (minimal fixes only - LLM does most work)...")
            self.logger.logger.info("Postprocessing workflow code (minimal fixes only - LLM does most work)...")
            workflow_code, validation_report = self.postprocessor.postprocess(
                workflow_code, 
                preprocessed_data
            )
            
            # Check for missing output files
            generated_output_files = self._extract_output_files_from_code(workflow_code)
            missing_outputs = list(set(expected_output_files) - set(generated_output_files))
            
            if not missing_outputs:
                # All output files are present
                self.logger.logger.info(f"✓ All {len(expected_output_files)} output files are present in workflow")
                break
            
            # Some output files are missing
            self.logger.log_warning(f"Missing {len(missing_outputs)} output files: {missing_outputs}")
            print(f"⚠️  Missing {len(missing_outputs)} output files: {', '.join(missing_outputs[:3])}{'...' if len(missing_outputs) > 3 else ''}")
            
            # Track missing outputs for this attempt
            all_missing_outputs_history.append(missing_outputs.copy())
            
            if attempt < max_retries - 1:
                # Show cumulative missing files
                cumulative_missing = list(set([f for prev_missing in all_missing_outputs_history for f in prev_missing]))
                print(f"🔄 Retrying workflow generation...")
                print(f"   Previous attempts missed: {len(cumulative_missing)} unique file(s)")
                print(f"   Current attempt missed: {len(missing_outputs)} file(s)")
                self.logger.logger.info(f"Retrying workflow generation (attempt {attempt + 2}/{max_retries})")
                self.logger.logger.info(f"Cumulative missing files across all attempts: {cumulative_missing}")
            else:
                self.logger.log_warning(f"Max retries reached. {len(missing_outputs)} output files still missing.")
                print(f"⚠️  Max retries reached. {len(missing_outputs)} output files still missing.")
                # Apply forced inclusion mechanism for missing output files
                print(f"🔧 Applying forced inclusion mechanism for {len(missing_outputs)} missing output files...")
                workflow_code = self._enforce_output_file_inclusion(
                    workflow_code,
                    missing_outputs,
                    filtered_executions,
                    preprocessed_data
                )
        
        # Log postprocessing results
        self.logger.log_postprocessing_results(validation_report)
        
        # Report validation results
        if validation_report.get("import_issues"):
            print(f"   ✓ Fixed {len(validation_report['import_issues'])} import issues")
        if validation_report.get("output_file_issues"):
            print(f"   ⚠️  Found {len(validation_report['output_file_issues'])} output file issues")
        if validation_report.get("syntax_errors"):
            print(f"   ⚠️  Found {len(validation_report['syntax_errors'])} syntax errors")
        if validation_report.get("fixes_applied"):
            print(f"   ✓ Applied {len(validation_report['fixes_applied'])} auto-fixes")
        
        # Extract metadata
        metadata = self.llm_processor.extract_metadata(filtered_executions)
        metadata["workflow_name"] = workflow_name
        
        # Generate complete workflow file
        complete_workflow = self.generate_workflow_file(workflow_code, metadata, workflow_name)
        
        # Validate generated workflow code before saving
        validation_errors = self._validate_workflow_code(complete_workflow)
        if validation_errors:
            self.logger.log_warning(f"Workflow code validation warnings: {len(validation_errors)}")
            print(f"⚠️  Workflow code validation warnings:")
            for error in validation_errors[:self.MAX_ERRORS_TO_SHOW]:
                print(f"   - {error}")
                self.logger.logger.debug(f"Validation error: {error}")
        
        # Log workflow quality
        expected_output_files = list(preprocessed_data.get('output_file_mapping', {}).keys())
        # Extract generated output files from code
        generated_output_files = self._extract_output_files_from_code(complete_workflow)
        self.logger.log_workflow_quality(
            complete_workflow,
            expected_output_files,
            generated_output_files
        )
        
        # Generate timestamp once for both files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save to temporary file first (will be moved to final location after validation)
        temp_file_path = self._save_workflow_file(complete_workflow, workflow_name, timestamp=timestamp, temp=True)
        
        # Generate and save workflow description (txt file) with same timestamp
        description_path = self._generate_and_save_workflow_description(
            complete_workflow, 
            workflow_name, 
            filtered_executions,
            preprocessed_data,
            timestamp=timestamp
        )
        
        if description_path:
            print(f"Workflow description saved to: {description_path}")
        
        # Note: Validation is now handled in save_and_validate_workflow()
        # This method only generates and saves the workflow file
        # Return temporary file path (will be finalized in save_and_validate_workflow)
        return temp_file_path
    
    def _extract_output_files_from_code(self, code: str) -> List[str]:
        """Extract output file names from workflow code."""
        return self.code_extractor.extract_output_files(code)
    
    def generate_workflow_file(
        self,
        code_blocks: str,
        metadata: Dict,
        workflow_name: str
    ) -> str:
        """
        Generate complete standalone Python script with metadata.
        
        Args:
            code_blocks: Workflow code (can be single string or list)
            metadata: Metadata dictionary
            workflow_name: Name of the workflow
            
        Returns:
            Complete workflow file content
        """
        # Input validation
        if not isinstance(metadata, dict):
            metadata = {}
        
        if not isinstance(workflow_name, str):
            workflow_name = str(workflow_name) if workflow_name else "unnamed"
        
        # If code_blocks is a string, use it directly
        if isinstance(code_blocks, str):
            workflow_code = code_blocks
        elif isinstance(code_blocks, list):
            # If it's a list, join them (filter out non-strings)
            valid_blocks = [str(block) for block in code_blocks if block is not None]
            workflow_code = "\n\n".join(valid_blocks) if valid_blocks else ""
        else:
            workflow_code = str(code_blocks) if code_blocks is not None else ""
        
        # Generate header
        header = self._generate_header(metadata, workflow_name)
        
        # Extract imports from code
        imports = self.code_extractor.extract_imports(workflow_code)
        import_section = "\n".join(imports) if imports else ""
        
        # Remove existing imports from code (to avoid duplication)
        workflow_code_clean = self._remove_imports_from_code(workflow_code)
        
        # Check if main block already exists
        if 'if __name__ == "__main__":' not in workflow_code_clean:
            main_block = self._generate_main_block()
        else:
            main_block = ""
        
        # Combine everything (use list join for better performance with large files)
        parts = [header]
        if import_section:
            parts.append("")
            parts.append(import_section)
        parts.append("")
        parts.append(workflow_code_clean)
        if main_block:
            parts.append("")
            parts.append(main_block)
        
        complete_file = "\n".join(parts)
        
        return complete_file
    
    def get_workflow_name(self, execution_history: List[Dict]) -> str:
        """
        Extract workflow name from execution history.
        
        Args:
            execution_history: List of execution entries
            
        Returns:
            Workflow name
        """
        # Input validation
        if not isinstance(execution_history, list):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"workflow_{timestamp}"
        
        # Try to extract from code patterns
        for execution in execution_history:
            if not isinstance(execution, dict):
                continue
            
            code = execution.get("code", "")
            if not isinstance(code, str):
                continue
            
            # Look for common patterns
            # Pattern 1: Function definitions
            func_match = re.search(r'def\s+(\w+)', code)
            if func_match:
                func_name = func_match.group(1)
                if func_name not in ['main', 'process', 'run']:
                    return func_name.replace('_', ' ').title()
            
            # Pattern 2: Comments with workflow name
            comment_match = re.search(r'#\s*workflow[:\s]+(\w+)', code, re.IGNORECASE)
            if comment_match:
                return comment_match.group(1).replace('_', ' ').title()
        
        # Default: use timestamp-based name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"workflow_{timestamp}"
    
    def _save_workflow_file(
        self, 
        workflow_content: str, 
        workflow_name: str,
        timestamp: Optional[str] = None,
        temp: bool = False
    ) -> str:
        """
        Save workflow content to file.
        
        Args:
            workflow_content: Complete workflow file content
            workflow_name: Name of the workflow
            timestamp: Optional timestamp (if None, generates new one)
            temp: If True, save as temporary file (will be finalized after validation)
            
        Returns:
            Path to saved file
        """
        # Input validation
        if not isinstance(workflow_content, str):
            workflow_content = str(workflow_content) if workflow_content is not None else ""
        
        if not isinstance(workflow_name, str):
            workflow_name = str(workflow_name) if workflow_name else "unnamed"
        
        if timestamp is not None and not isinstance(timestamp, str):
            timestamp = None
        
        # Sanitize workflow name for filename
        safe_name = self._sanitize_filename(workflow_name)
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if temp:
            filename = f"workflow_{safe_name}_{timestamp}.tmp.py"
        else:
            filename = f"workflow_{safe_name}_{timestamp}.py"
        
        file_path = self.workflows_dir / filename
        
        # Write file with error handling
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(workflow_content)
            
            if temp:
                print(f"Workflow saved to temporary file: {file_path}")
            else:
                print(f"Workflow saved to: {file_path}")
            return str(file_path)
        except (OSError, IOError, PermissionError) as e:
            self.logger.log_error(f"Failed to save workflow file: {e}")
            raise
        except Exception as e:
            self.logger.log_error(f"Unexpected error saving workflow file: {e}")
            raise
    
    def _generate_and_save_workflow_description(
        self,
        workflow_code: str,
        workflow_name: str,
        execution_history: List[Dict],
        preprocessed_data: Optional[Dict] = None,
        timestamp: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate and save workflow description as txt file.
        
        Args:
            workflow_code: Complete workflow code
            workflow_name: Name of the workflow
            execution_history: List of execution entries
            preprocessed_data: Optional preprocessed data
            timestamp: Optional timestamp (should match workflow file timestamp)
            
        Returns:
            Path to saved description file, or None if failed
        """
        try:
            # Generate description using LLM
            description = self.llm_processor.generate_workflow_description(
                workflow_code,
                execution_history,
                preprocessed_data
            )
            
            if not description:
                print("⚠️  Failed to generate workflow description")
                return None
            
            # Save to txt file with same timestamp as workflow file
            safe_name = self._sanitize_filename(workflow_name)
            if timestamp is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"workflow_{safe_name}_{timestamp}.txt"
            
            file_path = self.workflows_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(description)
            
            return str(file_path)
        except Exception as e:
            print(f"⚠️  Error generating workflow description: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize workflow name for use in filename."""
        # Replace spaces and special characters
        safe_name = re.sub(r'[^\w\s-]', '', name)
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        safe_name = safe_name.strip('_')
        
        # Limit length
        if len(safe_name) > self.MAX_FILENAME_LENGTH:
            safe_name = safe_name[:self.MAX_FILENAME_LENGTH]
        
        return safe_name or "unnamed"
    
    def _generate_header(self, metadata: Dict, workflow_name: str) -> str:
        """Generate script header with metadata."""
        date = metadata.get("generated_date", metadata.get("generated", datetime.now().isoformat()))
        description = metadata.get("description", "")
        
        # Handle input_formats - can be list or string
        input_formats_val = metadata.get("input_formats", "N/A")
        if isinstance(input_formats_val, list):
            input_formats = ", ".join(input_formats_val) or "N/A"
        else:
            input_formats = input_formats_val or "N/A"
        
        # Handle output_formats - can be list or string
        output_formats_val = metadata.get("output_formats", "N/A")
        if isinstance(output_formats_val, list):
            output_formats = ", ".join(output_formats_val) or "N/A"
        else:
            output_formats = output_formats_val or "N/A"
        
        # Handle tools - can be list or string
        tools_val = metadata.get("tools_used", metadata.get("tools_libraries", "N/A"))
        if isinstance(tools_val, list):
            tools = ", ".join(tools_val) or "N/A"
        else:
            tools = tools_val or "N/A"
        
        # Handle environment - can be dict or string
        env = metadata.get("environment", {})
        if isinstance(env, dict):
            python_version = env.get("python_version", "Unknown")
            os_name = env.get("os", "Unknown")
            env_str = f"Python {python_version}, {os_name}"
        else:
            # If it's already a string, use it directly
            env_str = str(env) if env else "Unknown"
        
        return f'''"""
Workflow: {workflow_name}
Generated: {date}
Description: {description}

Metadata:
- Input formats: {input_formats}
- Output formats: {output_formats}
- Tools/Libraries: {tools}
- Environment: {env_str}
"""'''
    
    def _generate_main_block(self) -> str:
        """Generate main execution block."""
        return '''
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python workflow.py <input_file1> [input_file2] ... [output_file]")
        print("Example: python workflow.py data.csv output.csv")
        sys.exit(1)
    
    # Get input files (all but last argument if it looks like output)
    args = sys.argv[1:]
    
    # Try to detect output file (last argument that looks like output)
    input_files = args
    output_file = None
    
    if len(args) > 1:
        last_arg = args[-1]
        # Check if last argument looks like an output file
        if any(last_arg.endswith(ext) for ext in ['.csv', '.xlsx', '.json', '.txt', '.png', '.jpg']):
            output_file = last_arg
            input_files = args[:-1]
    
    # Execute workflow
    try:
        # If there's a main function, call it
        if 'process_data' in globals():
            process_data(input_files, output_file)
        elif 'main' in globals():
            main(input_files, output_file)
        else:
            print("No main function found. Please define process_data() or main() function.")
            sys.exit(1)
        
        print("Workflow completed successfully.")
    except Exception as e:
        print(f"Error executing workflow: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
'''
    
    def _remove_imports_from_code(self, code: str) -> str:
        """
        Remove import statements from code to avoid duplication.
        
        Args:
            code: Code string
            
        Returns:
            Code without import statements
        """
        # Input validation
        if not isinstance(code, str):
            return ""
        
        # Cache split result (performance optimization)
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Skip import lines
            if stripped.startswith('import ') or stripped.startswith('from '):
                continue
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _validate_workflow_code(self, workflow_code: str) -> List[str]:
        """
        Validate workflow code for common issues.
        
        Args:
            workflow_code: Complete workflow code to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        try:
            # 1. Syntax validation
            try:
                ast.parse(workflow_code)
            except SyntaxError as e:
                errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
                return errors  # Can't continue if syntax is invalid
            
            # 2. Import alias validation
            import_issues = self._validate_import_aliases(workflow_code)
            errors.extend(import_issues)
            
            # 3. Check for undefined names (basic check)
            undefined_issues = self._check_undefined_names(workflow_code)
            errors.extend(undefined_issues)
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        return errors
    
    def _validate_import_aliases(self, code: str) -> List[str]:
        """
        Validate that import aliases match their usage in code.
        
        Args:
            code: Code string to validate
            
        Returns:
            List of import-related error messages
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return []
        
        errors = []
        
        try:
            tree = ast.parse(code)
            
            # Extract all imports and their aliases
            imports = {}  # {alias: module}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.asname:
                            imports[alias.asname] = alias.name
                        else:
                            # No alias, use module name
                            module_name = alias.name.split('.')[-1]
                            imports[module_name] = alias.name
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        if alias.asname:
                            imports[alias.asname] = f"{module}.{alias.name}" if module else alias.name
                        else:
                            imports[alias.name] = f"{module}.{alias.name}" if module else alias.name
            
            # Check for common alias patterns used in code (use pre-compiled patterns)
            common_patterns = {
                'pd': ('pandas', 'import pandas as pd', self._PD_PATTERN),
                'np': ('numpy', 'import numpy as np', self._NP_PATTERN),
                'plt': ('matplotlib.pyplot', 'import matplotlib.pyplot as plt', self._PLT_PATTERN),
                'sns': ('seaborn', 'import seaborn as sns', self._SNS_PATTERN),
            }
            
            for alias, (module, expected_import, pattern) in common_patterns.items():
                # Check if alias is used in code (use pre-compiled pattern)
                if pattern.search(code):
                    # Check if import exists with correct alias
                    if alias not in imports:
                        errors.append(f"Code uses '{alias}.' but missing import: {expected_import}")
                    elif imports[alias] != module and not imports[alias].endswith(module.split('.')[-1]):
                        errors.append(f"Code uses '{alias}.' but import mismatch: found '{imports[alias]}', expected '{module}'")
        
        except SyntaxError as e:
            errors.append(f"Syntax error in import validation: {e}")
        except Exception as e:
            errors.append(f"Import validation error: {str(e)}")
        
        return errors
    
    def _check_undefined_names(self, code: str) -> List[str]:
        """
        Basic check for potentially undefined names.
        
        Args:
            code: Code string to check
            
        Returns:
            List of undefined name warnings
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return []
        
        errors = []
        
        try:
            tree = ast.parse(code)
            
            # Collect all defined names
            defined_names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    defined_names.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    defined_names.add(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.asname:
                            defined_names.add(alias.asname)
                        else:
                            defined_names.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.asname:
                            defined_names.add(alias.asname)
                        else:
                            defined_names.add(alias.name)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    defined_names.add(node.id)
            
            # Check for common undefined patterns (cache split result and use pre-compiled patterns)
            code_lines = code.split('\n')
            for i, line in enumerate(code_lines, 1):
                # Skip comments and empty lines
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                
                # Check for common undefined patterns (use pre-compiled patterns for performance)
                if self._PD_PATTERN.search(line) and 'pd' not in defined_names:
                    errors.append(f"Line {i}: 'pd' may be undefined (use 'import pandas as pd')")
                if self._NP_PATTERN.search(line) and 'np' not in defined_names:
                    errors.append(f"Line {i}: 'np' may be undefined (use 'import numpy as np')")
                if self._PLT_PATTERN.search(line) and 'plt' not in defined_names:
                    errors.append(f"Line {i}: 'plt' may be undefined (use 'import matplotlib.pyplot as plt')")
                if self._SNS_PATTERN.search(line) and 'sns' not in defined_names:
                    errors.append(f"Line {i}: 'sns' may be undefined (use 'import seaborn as sns')")
        
        except Exception as e:
            # Ignore errors in undefined name checking (it's a best-effort check)
            pass
        
        return errors
    
    def _apply_rule_based_fixes(self, code: str) -> str:
        """
        Apply rule-based fixes for common import issues before LLM fixing.
        
        Uses AST to dynamically detect alias usage and fix import mismatches.
        
        Args:
            code: Workflow code to fix
            
        Returns:
            Fixed code
        """
        try:
            # Use AST to detect alias usage and imports
            alias_fixes = self._detect_alias_mismatches_ast(code)
            
            if not alias_fixes:
                return code
            
            lines = code.split('\n')
            import_section_end = None
            
            # Find import section
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(('import ', 'from ')):
                    if import_section_end is None:
                        import_section_end = i
                elif import_section_end is not None and stripped and not stripped.startswith('#'):
                    import_section_end = i
                    break
            
            if import_section_end is None:
                import_section_end = len(lines)
            
            changes_made = False
            
            # Apply fixes
            for correct_import, wrong_import_line_idx in alias_fixes:
                if wrong_import_line_idx >= 0:
                    # Replace wrong import
                    lines[wrong_import_line_idx] = correct_import
                    changes_made = True
                else:
                    # Add missing import
                    insert_pos = import_section_end
                    for i in range(import_section_end - 1, -1, -1):
                        if lines[i].strip().startswith(('import ', 'from ')):
                            insert_pos = i + 1
                            break
                    lines.insert(insert_pos, correct_import)
                    import_section_end += 1
                    changes_made = True
            
            if changes_made:
                return '\n'.join(lines)
        
        except (SyntaxError, Exception):
            # If AST parsing fails, fall back to regex-based detection
            pass
        
        return code
    
    def _detect_alias_mismatches_ast(self, code: str) -> List[tuple]:
        """
        Use AST to dynamically detect alias usage, module usage, and class usage, and import mismatches.
        
        Detects:
        - Alias patterns: pd.read_csv, np.array, plt.figure, etc.
        - Direct module usage: argparse.ArgumentParser, glob.glob, os.makedirs, etc.
        - Class instantiation: StandardScaler(), PCA(), multipletests(), etc.
        
        Args:
            code: Code string to analyze
            
        Returns:
            List of (correct_import, wrong_import_line_idx) tuples
            wrong_import_line_idx is -1 if import doesn't exist
        """
        fixes = []
        
        try:
            tree = ast.parse(code)
            lines = code.split('\n')
            
            # Single pass: Extract imports and detect usage patterns simultaneously
            # This replaces 2 separate AST walks with 1 consolidated walk
            imports_by_alias = {}  # {alias: (module, import_line, full_import_stmt)}
            imports_by_module = {}  # {module: (alias, import_line, full_import_stmt)}
            used_aliases = set()  # For alias patterns like pd., np., plt.
            used_modules = set()  # For direct module usage like argparse., glob., os.
            used_classes = set()  # For class instantiation like StandardScaler(), PCA()
            
            for node in ast.walk(tree):
                # Extract imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name
                        alias_name = alias.asname if alias.asname else module.split('.')[-1]
                        import_stmt = f"import {module}" + (f" as {alias_name}" if alias.asname else "")
                        line_no = node.lineno - 1 if hasattr(node, 'lineno') else -1
                        imports_by_alias[alias_name] = (module, line_no, import_stmt)
                        imports_by_module[module] = (alias_name, line_no, import_stmt)
                
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        name = alias.name
                        alias_name = alias.asname if alias.asname else name
                        full_module = f"{module}.{name}" if module else name
                        import_stmt = f"from {module} import {name}" + (f" as {alias_name}" if alias.asname else "") if module else f"import {name}" + (f" as {alias_name}" if alias.asname else "")
                        line_no = node.lineno - 1 if hasattr(node, 'lineno') else -1
                        imports_by_alias[alias_name] = (full_module, line_no, import_stmt)
                        imports_by_module[full_module] = (alias_name, line_no, import_stmt)
                
                # Detect usage patterns (in the same pass)
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        module_or_alias = node.value.id
                        # Check if it's a known module name or alias
                        used_modules.add(module_or_alias)
                        used_aliases.add(module_or_alias)
                
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        class_name = node.func.id
                        used_classes.add(class_name)
            
            # Step 3: Common mappings
            # Alias-to-module mappings (for alias patterns)
            alias_mappings = {
                'pd': ('pandas', 'import pandas as pd'),
                'np': ('numpy', 'import numpy as np'),
                'plt': ('matplotlib.pyplot', 'import matplotlib.pyplot as plt'),
                'sns': ('seaborn', 'import seaborn as sns'),
                'stats': ('scipy.stats', 'from scipy import stats'),
                'gp': ('gseapy', 'import gseapy as gp'),
            }
            
            # Direct module-to-import mappings (for module.attribute patterns)
            module_mappings = {
                'argparse': 'import argparse',
                'glob': 'import glob',
                'os': 'import os',
                'sys': 'import sys',
                'json': 'import json',
                'csv': 'import csv',
                're': 'import re',
                'datetime': 'import datetime',
                'pathlib': 'from pathlib import Path',
            }
            
            # Class-to-import mappings (for ClassName() patterns)
            class_mappings = {
                'StandardScaler': 'from sklearn.preprocessing import StandardScaler',
                'PCA': 'from sklearn.decomposition import PCA',
                'multipletests': 'from statsmodels.stats.multitest import multipletests',
                'ttest_ind': 'from scipy.stats import ttest_ind',
                'ttest_rel': 'from scipy.stats import ttest_rel',
                'ttest_1samp': 'from scipy.stats import ttest_1samp',
                'Path': 'from pathlib import Path',
            }
            
            common_mappings = {**alias_mappings, **{k: (k, v) for k, v in module_mappings.items()}}
            
            # Step 4: Check for missing imports (modules used directly)
            for used_module in used_modules:
                if used_module in module_mappings:
                    correct_import = module_mappings[used_module]
                    # Check if module is imported
                    if used_module not in imports_by_alias and used_module not in imports_by_module:
                        # Module not imported at all
                        fixes.append((correct_import, -1))
                    elif used_module in imports_by_alias:
                        # Module imported with alias, but we need direct import
                        imported_module, import_line, import_stmt = imports_by_alias[used_module]
                        if imported_module != used_module:
                            # Wrong import, replace it
                            if import_line >= 0:
                                fixes.append((correct_import, import_line))
            
            # Step 5: Check for alias mismatches
            for used_alias in used_aliases:
                if used_alias in alias_mappings:
                    expected_module, correct_import = alias_mappings[used_alias]
                    
                    # Check if alias is imported correctly
                    if used_alias in imports_by_alias:
                        imported_module, import_line, import_stmt = imports_by_alias[used_alias]
                        # Check if it matches expected module
                        if expected_module not in imported_module and imported_module not in expected_module:
                            # Mismatch: alias exists but for wrong module
                            if import_line >= 0:
                                fixes.append((correct_import, import_line))
                    else:
                        # Alias is used but not imported
                        # Check if module is imported without alias
                        if expected_module in imports_by_module:
                            module_alias, import_line, import_stmt = imports_by_module[expected_module]
                            if module_alias != used_alias and import_line >= 0:
                                # Module imported with wrong/no alias
                                fixes.append((correct_import, import_line))
                            else:
                                # Module not imported at all
                                fixes.append((correct_import, -1))
                        else:
                            # Module not imported at all
                            fixes.append((correct_import, -1))
            
            # Step 6: Check for missing class imports
            for used_class in used_classes:
                if used_class in class_mappings:
                    correct_import = class_mappings[used_class]
                    # Check if class is imported
                    if used_class not in imports_by_alias:
                        # Check if it's imported from the expected module
                        # Extract module from import statement
                        expected_module = correct_import.split()[-1]  # Last word is the class name
                        if expected_module == used_class:
                            # Class not imported, add it
                            fixes.append((correct_import, -1))
        
        except SyntaxError as e:
            # If AST parsing fails, log and return empty list (fallback to regex)
            self.logger.logger.warning(f"Syntax error in AST parsing for alias detection: {e}")
            return []
        except Exception as e:
            # Unexpected errors should be logged
            self.logger.logger.error(f"Unexpected error in AST parsing for alias detection: {e}")
            return []
        
        return fixes
    
    def save_and_validate_workflow(
        self,
        tracker: WorkflowTracker,
        workflow_name: Optional[str] = None,
        max_fix_attempts: int = DEFAULT_MAX_FIX_ATTEMPTS,
        save_mode: str = "notebook"  # "llm", "simple", or "notebook"
    ) -> Optional[str]:
        """
        Save workflow and validate it. If validation fails, attempt to fix using LLM (up to max_fix_attempts times).
        
        This is the main entry point that handles both generation and validation.
        Validation failures will prevent the workflow from being saved in final location.
        
        Args:
            tracker: WorkflowTracker instance with execution history
            workflow_name: Optional workflow name (auto-extracted if not provided)
            max_fix_attempts: Maximum number of fix attempts (default: DEFAULT_MAX_FIX_ATTEMPTS, only used in LLM mode)
            save_mode: Save mode - "llm" for LLM-based generation, "simple" for concatenation, "notebook" for Jupyter notebook (default: "notebook")
            
        Returns:
            Path to saved workflow file, or None if saving/validation failed
        """
        # Input validation
        if not isinstance(tracker, WorkflowTracker):
            self.logger.log_error("Invalid tracker: must be WorkflowTracker instance")
            return None
        
        if workflow_name is not None and not isinstance(workflow_name, str):
            workflow_name = str(workflow_name) if workflow_name else None
        
        if not isinstance(max_fix_attempts, int) or max_fix_attempts < 0:
            max_fix_attempts = self.DEFAULT_MAX_FIX_ATTEMPTS
        
        if not isinstance(save_mode, str) or save_mode not in ["llm", "simple", "notebook"]:
            save_mode = "notebook"
        
        # Save initial workflow (returns temporary file path)
        temp_workflow_path = self.save_workflow(tracker, workflow_name, save_mode=save_mode)
        
        if not temp_workflow_path:
            return None
        
        # If validator is not available, finalize the temporary file and return
        if not self.validator:
            final_path = self._finalize_workflow_file(temp_workflow_path)
            
            # Log completion
            description_path = self._get_description_path_for_workflow(final_path)
            self.logger.log_workflow_complete(final_path, description_path)
            log_file_path = self.logger.get_log_file_path()
            if log_file_path:
                print(f"📋 Detailed log saved to: {log_file_path}")
            
            return final_path
        
        # Skip validation for notebook mode (notebooks cannot be directly executed as Python scripts)
        if save_mode == "notebook":
            print("ℹ️  Skipping validation for notebook mode (notebooks require manual execution or nbconvert)")
            final_path = self._finalize_workflow_file(temp_workflow_path)
            
            # Log completion
            description_path = self._get_description_path_for_workflow(final_path)
            self.logger.log_workflow_complete(final_path, description_path)
            log_file_path = self.logger.get_log_file_path()
            if log_file_path:
                print(f"📋 Detailed log saved to: {log_file_path}")
            
            return final_path
        
        # Get input/output files for validation
        try:
            expected_outputs = tracker.get_expected_output_files()
            if not isinstance(expected_outputs, dict):
                expected_outputs = {}
        except Exception as e:
            self.logger.log_error(f"Failed to get expected output files: {e}")
            expected_outputs = {}
        
        try:
            input_files = tracker.get_input_files()
            if not isinstance(input_files, list):
                input_files = []
        except Exception as e:
            self.logger.log_error(f"Failed to get input files: {e}")
            input_files = []
        
        # Validation requires output files, but input files are optional
        # (some workflows may not have explicit input files, or they may be hardcoded)
        if not expected_outputs:
            print("⚠️  Cannot validate workflow: missing output files")
            print("   (Output files may have been deleted or moved)")
            print("   Saving workflow without validation...")
            final_path = self._finalize_workflow_file(temp_workflow_path)
            
            # Log completion
            description_path = self._get_description_path_for_workflow(final_path)
            self.logger.log_workflow_complete(final_path, description_path)
            log_file_path = self.logger.get_log_file_path()
            if log_file_path:
                print(f"📋 Detailed log saved to: {log_file_path}")
            
            return final_path
        
        # If no input files tracked, use empty list
        # (validation can still proceed with output files only)
        if not input_files:
            print("ℹ️  No input files tracked - validation will proceed with output files only")
            input_files = []  # Use empty list for validation
        
        # Read current workflow code
        try:
            with open(temp_workflow_path, 'r', encoding='utf-8') as f:
                current_workflow = f.read()
            if not isinstance(current_workflow, str):
                current_workflow = ""
        except (FileNotFoundError, IOError, OSError) as e:
            self.logger.log_error(f"Failed to read workflow file: {e}")
            return None
        except Exception as e:
            self.logger.log_error(f"Unexpected error reading workflow file: {e}")
            return None
        
        # Validate workflow
        print(f"🔍 Validating workflow...")
        validation_result = self.validator.validate_workflow(
            temp_workflow_path,
            input_files,
            expected_outputs
        )
        
        if validation_result["valid"]:
            print(f"✅ Workflow validated successfully - all output files match")
            self.logger.logger.info("Workflow validation passed")
            # Finalize the temporary file
            final_path = self._finalize_workflow_file(temp_workflow_path)
            
            # Log completion
            description_path = self._get_description_path_for_workflow(final_path)
            self.logger.log_workflow_complete(final_path, description_path)
            log_file_path = self.logger.get_log_file_path()
            if log_file_path:
                print(f"📋 Detailed log saved to: {log_file_path}")
            
            return final_path
        
        # Validation failed - attempt to fix
        # Build comprehensive error message with all available information
        error_msg = self._build_comprehensive_error_message(validation_result)
        print(f"⚠️  Workflow validation failed: {error_msg[:200]}...")
        self.logger.log_warning(f"Workflow validation failed: {error_msg[:200]}...")
        
        # Log differences
        differences = validation_result.get("differences", [])
        for diff in differences[:5]:
            self.logger.logger.debug(f"Validation difference: {diff}")
        
        # Try rule-based fixes first (fast, no LLM call)
        print(f"🔧 Attempting rule-based fixes...")
        fixed_workflow = self._apply_rule_based_fixes(current_workflow)
        if fixed_workflow != current_workflow:
            print(f"✓ Applied rule-based fixes, re-validating...")
            # Save fixed workflow
            try:
                with open(temp_workflow_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_workflow)
                
                # Validate fixed workflow
                validation_result = self.validator.validate_workflow(
                    temp_workflow_path,
                    input_files,
                    expected_outputs
                )
                
                if validation_result.get("valid", False):
                    print(f"✅ Workflow fixed with rule-based approach and validated!")
                    self.logger.logger.info("Workflow fixed and validated after rule-based fixes")
                    final_path = self._finalize_workflow_file(temp_workflow_path)
                    
                    # Log completion
                    description_path = self._get_description_path_for_workflow(final_path)
                    self.logger.log_workflow_complete(final_path, description_path)
                    log_file_path = self.logger.get_log_file_path()
                    if log_file_path:
                        print(f"📋 Detailed log saved to: {log_file_path}")
                    
                    return final_path
                
                # Validation still failed
                current_workflow = fixed_workflow
                error_msg = self._build_comprehensive_error_message(validation_result)
                print(f"⚠️  Rule-based fixes were not sufficient")
                
            except (OSError, IOError, PermissionError) as e:
                self.logger.log_error(f"Failed to save rule-based fixed workflow: {e}")
                current_workflow = fixed_workflow
                error_msg = "Failed to save fixed workflow"
            except Exception as e:
                self.logger.log_error(f"Unexpected error saving rule-based fixed workflow: {e}")
                current_workflow = fixed_workflow
                error_msg = "Failed to save fixed workflow"
        
        # Skip LLM-based fixes in simple mode (just concatenate code blocks, no LLM processing)
        if save_mode == "simple":
            print(f"ℹ️  Simple mode: Skipping LLM-based fixes. Saving workflow as-is.")
            final_path = self._finalize_workflow_file(temp_workflow_path)
            
            # Log completion
            description_path = self._get_description_path_for_workflow(final_path)
            self.logger.log_workflow_complete(final_path, description_path)
            log_file_path = self.logger.get_log_file_path()
            if log_file_path:
                print(f"📋 Detailed log saved to: {log_file_path}")
            
            return final_path
        
        # Attempt LLM-based fixes (only in LLM mode)
        for attempt in range(1, max_fix_attempts + 1):
            print(f"🔧 Attempting LLM-based fix (attempt {attempt}/{max_fix_attempts})...")
            
            # Use LLM to fix the entire workflow file
            fixed_workflow = self.llm_processor.fix_workflow_code(current_workflow, error_msg, attempt)
            
            if not fixed_workflow or fixed_workflow == current_workflow:
                print(f"⚠️  LLM did not produce a fix (attempt {attempt})")
                continue
            
            # Apply rule-based fixes to LLM-fixed code
            fixed_workflow = self._apply_rule_based_fixes(fixed_workflow)
            
            # Save fixed workflow
            with open(temp_workflow_path, 'w', encoding='utf-8') as f:
                f.write(fixed_workflow)
            
            print(f"💾 Fixed workflow saved, re-validating...")
            
            # Validate fixed workflow
            validation_result = self.validator.validate_workflow(
                temp_workflow_path,
                input_files,
                expected_outputs
            )
            
            if validation_result["valid"]:
                print(f"✅ Workflow fixed and validated successfully!")
                self.logger.logger.info(f"Workflow fixed and validated after {attempt} LLM fix attempt(s)")
                final_path = self._finalize_workflow_file(temp_workflow_path)
                
                # Log completion
                description_path = self._get_description_path_for_workflow(final_path)
                self.logger.log_workflow_complete(final_path, description_path)
                log_file_path = self.logger.get_log_file_path()
                if log_file_path:
                    print(f"📋 Detailed log saved to: {log_file_path}")
                
                return final_path
            
            # Still failing - update error message for next attempt with comprehensive info
            error_msg = self._build_comprehensive_error_message(validation_result, attempt)
            print(f"⚠️  Fix attempt {attempt} failed: {error_msg[:200]}...")
            self.logger.logger.debug(f"Fix attempt {attempt} failed: {error_msg}")
            
            # Update current_workflow for next attempt
            current_workflow = fixed_workflow
        
        # All fix attempts failed
        print(f"❌ Failed to fix workflow after {max_fix_attempts} attempts")
        print(f"⚠️  Workflow saved to temporary file but validation failed: {temp_workflow_path}")
        self.logger.log_warning(f"Workflow validation failed after {max_fix_attempts} fix attempts")
        
        # Log completion (even though validation failed)
        description_path = self._get_description_path_for_workflow(temp_workflow_path)
        self.logger.log_workflow_complete(temp_workflow_path, description_path)
        log_file_path = self.logger.get_log_file_path()
        if log_file_path:
            print(f"📋 Detailed log saved to: {log_file_path}")
        
        # Don't finalize - keep as temporary file to indicate validation failure
        # User can manually review and fix if needed
        return None
    
    def _enforce_output_file_inclusion(
        self,
        workflow_code: str,
        missing_output_files: List[str],
        executions: List[Dict],
        preprocessed_data: Dict
    ) -> str:
        """
        Force inclusion of code blocks that generate missing output files.
        
        This method extracts code from original executions that generate
        the missing output files and inserts them into the workflow.
        
        Args:
            workflow_code: Current workflow code
            missing_output_files: List of missing output file names
            executions: Original execution history
            preprocessed_data: Preprocessed data with output file mapping
            
        Returns:
            Workflow code with missing output file generation code added
        """
        # Input validation
        if not isinstance(workflow_code, str):
            workflow_code = str(workflow_code) if workflow_code is not None else ""
        
        if not isinstance(missing_output_files, list):
            missing_output_files = []
        
        if not isinstance(executions, list):
            executions = []
        
        if not isinstance(preprocessed_data, dict):
            preprocessed_data = {}
        
        output_file_mapping = preprocessed_data.get("output_file_mapping", {})
        if not isinstance(output_file_mapping, dict):
            output_file_mapping = {}
        
        code_blocks_to_add = []
        
        for missing_file in missing_output_files:
            if not isinstance(missing_file, str):
                continue
            
            # Find which executions generate this file
            exec_indices = output_file_mapping.get(missing_file, [])
            if not isinstance(exec_indices, list):
                exec_indices = []
            
            if not exec_indices:
                # Try to find by filename pattern matching
                for exec_idx, execution in enumerate(executions, 1):
                    if not isinstance(execution, dict):
                        continue
                    
                    output_files = execution.get("output_files", [])
                    if not isinstance(output_files, list):
                        continue
                    
                    for output_file in output_files:
                        if isinstance(output_file, str) and Path(output_file).name == missing_file:
                            exec_indices = [exec_idx]
                            break
                    if exec_indices:
                        break
            
            if exec_indices:
                # Extract code from these executions
                for exec_idx in exec_indices:
                    # Validate exec_idx: must be positive and within bounds
                    if not isinstance(exec_idx, int) or exec_idx < 1:
                        continue
                    
                    if exec_idx <= len(executions):
                        execution = executions[exec_idx - 1]
                        if not isinstance(execution, dict):
                            continue
                        
                        code = execution.get("code", "")
                        if isinstance(code, str) and code:
                            # Clean and prepare code block
                            code_block = self._prepare_code_block_for_insertion(
                                code, missing_file
                            )
                            if code_block:
                                code_blocks_to_add.append({
                                    "file": missing_file,
                                    "code": code_block,
                                    "execution_index": exec_idx
                                })
                                self.logger.logger.info(
                                    f"Extracted code for {missing_file} from execution {exec_idx}"
                                )
                                break  # Use first matching execution
        
        # Insert code blocks into workflow
        if code_blocks_to_add:
            workflow_code = self._insert_output_file_code_blocks(
                workflow_code, code_blocks_to_add
            )
            print(f"✓ Added {len(code_blocks_to_add)} code block(s) for missing output files")
            self.logger.logger.info(
                f"Force-included {len(code_blocks_to_add)} code blocks for missing output files"
            )
            
            # After inserting code blocks, extract and add missing imports
            print(f"🔧 Analyzing and adding missing imports for inserted code blocks...")
            workflow_code = self._add_missing_imports_for_inserted_code(
                workflow_code, code_blocks_to_add
            )
        
        return workflow_code
    
    def _prepare_code_block_for_insertion(
        self, code: str, output_file: str
    ) -> Optional[str]:
        """
        Prepare a code block for insertion into workflow.
        
        Removes unnecessary parts and ensures it's parameterized.
        
        Args:
            code: Original code block
            output_file: Output file name this code generates
            
        Returns:
            Prepared code block, or None if preparation failed
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return None
        
        if not isinstance(output_file, str):
            output_file = str(output_file) if output_file else ""
        
        # Remove comments that are too specific
        # Cache split result (performance optimization)
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip very specific debug comments
            stripped = line.strip()
            if stripped.startswith('#') and any(
                keyword in stripped.lower() for keyword in ['debug', 'test', 'check', 'verify']
            ):
                continue
            cleaned_lines.append(line)
        
        code = '\n'.join(cleaned_lines)
        
        # Try to parameterize hardcoded paths
        # Replace absolute paths with relative or parameterized paths
        # Pattern for absolute paths (pre-compiled for performance)
        abs_path_pattern = re.compile(r'["\'](/[^"\']+)["\']')
        
        def replace_path(match):
            path_str = match.group(1)
            try:
                path_obj = Path(path_str)
                # If it's the output file, use parameterized name
                if path_obj.name == output_file:
                    return f'"{output_file}"'
                # Otherwise, try to make it relative
                return f'"{path_obj.name}"'
            except (ValueError, TypeError):
                # Invalid path, keep original
                return match.group(0)
        
        code = abs_path_pattern.sub(replace_path, code)
        
        return code.strip() if code.strip() else None
    
    def _insert_output_file_code_blocks(
        self, workflow_code: str, code_blocks: List[Dict]
    ) -> str:
        """
        Insert code blocks that generate output files into workflow.
        
        Args:
            workflow_code: Current workflow code
            code_blocks: List of code blocks to insert with metadata
            
        Returns:
            Workflow code with inserted code blocks
        """
        # Input validation
        if not isinstance(workflow_code, str):
            workflow_code = str(workflow_code) if workflow_code is not None else ""
        
        if not isinstance(code_blocks, list):
            return workflow_code
        
        # Find the best insertion point (before main block or at end of process_data)
        # Cache split result (performance optimization)
        lines = workflow_code.split('\n')
        
        # Try to find process_data function or main block
        insertion_point = len(lines)
        
        # Look for 'if __name__ == "__main__":' or end of process_data function
        for i, line in enumerate(lines):
            if 'if __name__ == "__main__":' in line:
                insertion_point = i
                break
            # Check for end of process_data function (empty line after function)
            if 'def process_data' in line:
                # Find the end of this function
                for j in range(i + 1, len(lines)):
                    # Validate index bounds
                    if j >= len(lines):
                        break
                    
                    line_j = lines[j]
                    stripped_j = line_j.strip()
                    if stripped_j and not line_j.startswith(' ') and not line_j.startswith('\t'):
                        if not stripped_j.startswith('def ') and not stripped_j.startswith('class '):
                            insertion_point = j
                            break
                if insertion_point < len(lines):
                    break
        
        # Prepare code blocks to insert
        insertion_code = []
        insertion_code.append("\n# ============================================================================")
        insertion_code.append("# MISSING OUTPUT FILE GENERATION CODE (AUTO-INSERTED)")
        insertion_code.append("# ============================================================================")
        
        for block_info in code_blocks:
            if not isinstance(block_info, dict):
                continue
            
            file_name = block_info.get("file", "unknown")
            code = block_info.get("code", "")
            exec_idx = block_info.get("execution_index", "?")
            
            if isinstance(file_name, str) and isinstance(code, str) and code:
                insertion_code.append(f"\n# Generate {file_name} (from execution {exec_idx})")
                insertion_code.append(code)
                insertion_code.append("")  # Empty line between blocks
        
        insertion_code.append("# ============================================================================\n")
        
        # Insert code blocks
        lines.insert(insertion_point, '\n'.join(insertion_code))
        
        return '\n'.join(lines)
    
    def _add_missing_imports_for_inserted_code(
        self, workflow_code: str, code_blocks: List[Dict]
    ) -> str:
        """
        Analyze inserted code blocks and add missing imports to workflow.
        
        Args:
            workflow_code: Current workflow code
            code_blocks: List of inserted code blocks with metadata
            
        Returns:
            Workflow code with missing imports added
        """
        # Input validation
        if not isinstance(workflow_code, str):
            workflow_code = str(workflow_code) if workflow_code is not None else ""
        
        if not isinstance(code_blocks, list):
            return workflow_code
        
        # Extract imports from all inserted code blocks
        all_required_imports = set()
        
        # Pre-compiled regex patterns for performance
        import_patterns = {
            re.compile(r'\bpd\.'): 'import pandas as pd',
            re.compile(r'\bnp\.'): 'import numpy as np',
            re.compile(r'\bplt\.'): 'import matplotlib.pyplot as plt',
            re.compile(r'\bsns\.'): 'import seaborn as sns',
            re.compile(r'\bstats\.'): 'from scipy import stats',
            re.compile(r'\bgp\.'): 'import gseapy as gp',
        }
        
        for block_info in code_blocks:
            if not isinstance(block_info, dict):
                continue
            
            code = block_info.get("code", "")
            if not isinstance(code, str) or not code.strip():
                continue
            
            # Extract imports from this code block
            try:
                imports = self.code_extractor.extract_imports(code)
                if isinstance(imports, list):
                    all_required_imports.update(imports)
            except Exception:
                # Skip if extraction fails
                pass
            
            # Also check for common import patterns used in code
            for pattern, import_stmt in import_patterns.items():
                if pattern.search(code):
                    all_required_imports.add(import_stmt)
        
        # Extract current imports from workflow
        current_imports = self.code_extractor.extract_imports(workflow_code)
        current_imports_set = set(current_imports)
        
        # Find missing imports
        missing_imports = []
        for required_import in all_required_imports:
            if not isinstance(required_import, str):
                continue
            
            # Check if this import or a similar one exists
            import_exists = False
            for current_import in current_imports_set:
                if not isinstance(current_import, str):
                    continue
                
                # Check if modules match (handle aliases)
                required_module = self._extract_module_name(required_import)
                current_module = self._extract_module_name(current_import)
                if required_module == current_module:
                    import_exists = True
                    break
            
            if not import_exists:
                missing_imports.append(required_import)
        
        # Add missing imports to workflow
        if missing_imports:
            # Find import section
            try:
                import_section = self.code_extractor.find_import_section(workflow_code, return_char_positions=False)
                if import_section and isinstance(import_section, dict):
                    # Insert after import section
                    new_imports = "\n".join(missing_imports)
                    # Cache split result (performance optimization)
                    lines = workflow_code.split('\n')
                    insert_pos = import_section.get("end_line", 0)
                    if 0 <= insert_pos <= len(lines):
                        lines.insert(insert_pos, new_imports)
                        workflow_code = '\n'.join(lines)
                    else:
                        # Invalid position, add at beginning
                        workflow_code = new_imports + "\n\n" + workflow_code
                else:
                    # No import section found, add at beginning
                    new_imports = "\n".join(missing_imports)
                    workflow_code = new_imports + "\n\n" + workflow_code
            except Exception as e:
                # Fallback: add at beginning
                self.logger.logger.warning(f"Failed to find import section: {e}")
                new_imports = "\n".join(missing_imports)
                workflow_code = new_imports + "\n\n" + workflow_code
                print(f"✓ Added {len(missing_imports)} missing import(s) for inserted code blocks")
                self.logger.logger.info(
                    f"Added {len(missing_imports)} missing imports: {missing_imports}"
                )
            else:
                # Add at the beginning (after docstring if exists)
                new_imports = "\n".join(missing_imports)
                # Find end of docstring
                if '"""' in workflow_code:
                    docstring_end = workflow_code.find('"""', workflow_code.find('"""') + 3) + 3
                    workflow_code = workflow_code[:docstring_end] + "\n\n" + new_imports + "\n" + workflow_code[docstring_end:]
                else:
                    workflow_code = new_imports + "\n\n" + workflow_code
                print(f"✓ Added {len(missing_imports)} missing import(s) at the beginning")
        
        return workflow_code
    
    def _extract_module_name(self, import_stmt: str) -> str:
        """Extract module name from import statement."""
        if import_stmt.startswith('import '):
            module = import_stmt.replace('import ', '').split(' as ')[0].strip()
        elif import_stmt.startswith('from '):
            module = import_stmt.replace('from ', '').split(' import ')[0].strip()
        else:
            module = import_stmt
        return module
    
    
    def _finalize_workflow_file(self, temp_file_path: str) -> str:
        """
        Finalize temporary workflow file by renaming it to final name.
        
        Args:
            temp_file_path: Path to temporary workflow file (.tmp.py)
            
        Returns:
            Path to finalized workflow file
        """
        # Input validation
        if not isinstance(temp_file_path, str):
            return str(temp_file_path) if temp_file_path is not None else ""
        
        try:
            temp_path = Path(temp_file_path)
            if not temp_path.exists():
                self.logger.log_warning(f"Temporary file does not exist: {temp_file_path}")
                return temp_file_path
            
            # Remove .tmp from filename
            final_filename = temp_path.name.replace('.tmp.py', '.py')
            final_path = temp_path.parent / final_filename
            
            # Rename file with error handling
            try:
                temp_path.rename(final_path)
                print(f"✅ Workflow finalized: {final_path}")
                return str(final_path)
            except (OSError, PermissionError) as e:
                self.logger.log_error(f"Failed to rename temporary file: {e}")
                # Return original path if rename fails
                return temp_file_path
        except Exception as e:
            self.logger.log_error(f"Unexpected error finalizing workflow file: {e}")
            return temp_file_path
    
    def _build_comprehensive_error_message(
        self, 
        validation_result: Dict, 
        attempt_number: Optional[int] = None
    ) -> str:
        """
        Build comprehensive error message for LLM fix attempts.
        
        Includes:
        - Full error traceback
        - All differences
        - File comparison details
        - Previous attempt context
        
        Args:
            validation_result: Validation result dictionary
            attempt_number: Optional attempt number for context
            
        Returns:
            Comprehensive error message string
        """
        error_parts = []
        
        # Add attempt context
        if attempt_number:
            error_parts.append(f"=== FIX ATTEMPT {attempt_number} FAILED ===")
        
        # Add main error
        error = validation_result.get("error")
        if error:
            error_parts.append(f"\nERROR:\n{error}")
        
        # Add summary
        summary = validation_result.get("summary")
        if summary and summary != error:
            error_parts.append(f"\nSUMMARY:\n{summary}")
        
        # Add all differences
        differences = validation_result.get("differences", [])
        if isinstance(differences, list) and differences:
            error_parts.append(f"\nDETAILED DIFFERENCES ({len(differences)} total):")
            for i, diff in enumerate(differences[:self.MAX_DIFFERENCES_TO_SHOW], 1):
                if isinstance(diff, str):
                    error_parts.append(f"  {i}. {diff}")
            if len(differences) > self.MAX_DIFFERENCES_TO_SHOW:
                error_parts.append(f"  ... and {len(differences) - self.MAX_DIFFERENCES_TO_SHOW} more differences")
        
        # Add file comparison details
        file_comparisons = validation_result.get("output_files_match", {})
        if file_comparisons:
            error_parts.append(f"\nFILE COMPARISON RESULTS:")
            for file_path, comparison in list(file_comparisons.items())[:5]:
                match = comparison.get("match", False) if isinstance(comparison, dict) else comparison
                if not match:
                    diff_info = comparison.get("diff", "File differs") if isinstance(comparison, dict) else "File differs"
                    error_parts.append(f"  - {Path(file_path).name}: {diff_info}")
        
        # Add stderr if available (from workflow execution)
        stderr = validation_result.get("stderr")
        if isinstance(stderr, str) and stderr:
            error_parts.append(f"\nEXECUTION STDERR:\n{stderr[:self.MAX_STDERR_LENGTH]}")
        
        # Add stdout if available (might contain useful info)
        stdout = validation_result.get("stdout")
        if stdout and len(stdout) < 500:
            error_parts.append(f"\nEXECUTION STDOUT:\n{stdout}")
        
        return "\n".join(error_parts)
    
    def _get_description_path_for_workflow(self, workflow_path: str) -> Optional[str]:
        """
        Get description file path for a workflow file.
        
        Args:
            workflow_path: Path to workflow file
            
        Returns:
            Path to description file, or None if not found
        """
        workflow_path_obj = Path(workflow_path)
        # Description file has same name but .txt extension
        description_path = workflow_path_obj.with_suffix('.txt')
        if description_path.exists():
            return str(description_path)
        return None
    
    def _extract_code_from_workflow(self, workflow_content: str) -> str:
        """
        Extract code portion from complete workflow file (remove header and main block).
        
        Args:
            workflow_content: Complete workflow file content
            
        Returns:
            Code portion without header and main block
        """
        lines = workflow_content.split('\n')
        code_start = None
        code_end = None
        
        # Find where code starts (after header docstring)
        in_header = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if in_header:
                    # End of header
                    code_start = i + 1
                    break
                else:
                    # Start of header
                    in_header = True
                    continue
        
        if code_start is None:
            code_start = 0
        
        # Find where code ends (before main block)
        for i in range(len(lines) - 1, code_start - 1, -1):
            stripped = lines[i].strip()
            if stripped == 'if __name__ == "__main__":':
                code_end = i
                break
        
        if code_end is None:
            code_end = len(lines)
        
        # Extract code and clean up empty lines
        code_lines = lines[code_start:code_end]
        # Remove leading/trailing empty lines
        while code_lines and not code_lines[0].strip():
            code_lines.pop(0)
        while code_lines and not code_lines[-1].strip():
            code_lines.pop()
        
        return '\n'.join(code_lines)
    
    def _save_workflow_simple(
        self,
        execution_history: List[Dict],
        workflow_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Save workflow by simply concatenating successful execute blocks.
        Only parameterizes file paths, keeping code structure intact.
        
        Includes variable dependency analysis to extract variable definitions
        from failed executions if they are used in successful executions.
        
        Args:
            execution_history: List of execution dictionaries
            workflow_name: Optional workflow name
            
        Returns:
            Path to saved workflow file, or None if saving failed
        """
        # Input validation
        if not isinstance(execution_history, list):
            self.logger.log_error("Invalid execution_history: must be a list")
            return None
        
        if workflow_name is not None and not isinstance(workflow_name, str):
            workflow_name = str(workflow_name) if workflow_name else None
        
        # Step 0: Analyze output file dependencies
        # Identify which output files are generated by failed executions but used by successful ones
        failed_executions_with_outputs = []
        for exec_entry in execution_history:
            if isinstance(exec_entry, dict) and not exec_entry.get("success", False):
                output_files = exec_entry.get("output_files", [])
                if isinstance(output_files, list) and len(output_files) > 0:
                    failed_executions_with_outputs.append(exec_entry)
        
        # Extract output file names (just filenames, not full paths) from failed executions
        failed_output_files = set()
        for exec_entry in failed_executions_with_outputs:
            output_files = exec_entry.get("output_files", [])
            if isinstance(output_files, list):
                for output_file in output_files:
                    if isinstance(output_file, str):
                        # Extract just the filename
                        from pathlib import Path
                        filename = Path(output_file).name
                        failed_output_files.add(filename)
        
        # Check if any successful execution uses files generated by failed executions
        # OPTIMIZATION: Use lightweight regex matching instead of full AST parsing
        # This is much faster for simple file reference detection
        required_failed_executions = []
        if failed_output_files:
            # Pre-compile regex patterns for all failed output files (performance optimization)
            # Build a single regex pattern that matches any failed file
            escaped_files = [re.escape(f) for f in failed_output_files]
            file_pattern = '|'.join(escaped_files)
            
            # Compile patterns once (reused for all executions)
            read_csv_pattern = re.compile(rf'read_csv\([^)]*["\']({file_pattern})["\']', re.IGNORECASE)
            read_excel_pattern = re.compile(rf'read_excel\([^)]*["\']({file_pattern})["\']', re.IGNORECASE)
            read_parquet_pattern = re.compile(rf'read_parquet\([^)]*["\']({file_pattern})["\']', re.IGNORECASE)
            open_pattern = re.compile(rf'open\([^)]*["\']({file_pattern})["\']', re.IGNORECASE)
            quote_pattern = re.compile(rf'["\']({file_pattern})["\']', re.IGNORECASE)
            
            # Build a reverse lookup map: filename -> list of failed executions that generate it
            filename_to_executions = {}  # {filename: [failed_exec, ...]}
            for failed_exec in failed_executions_with_outputs:
                failed_outputs = failed_exec.get("output_files", [])
                if isinstance(failed_outputs, list):
                    for failed_output in failed_outputs:
                        if isinstance(failed_output, str):
                            filename = Path(failed_output).name
                            if filename not in filename_to_executions:
                                filename_to_executions[filename] = []
                            if failed_exec not in filename_to_executions[filename]:
                                filename_to_executions[filename].append(failed_exec)
            
            for exec_entry in execution_history:
                if isinstance(exec_entry, dict) and exec_entry.get("success", False):
                    code = exec_entry.get("code", "")
                    if not isinstance(code, str) or not code.strip():
                        continue
                    
                    # Use lightweight regex matching instead of AST parsing
                    # Check for file references using pre-compiled patterns
                    found_files = set()
                    
                    # Check all patterns
                    for pattern in [read_csv_pattern, read_excel_pattern, read_parquet_pattern, open_pattern, quote_pattern]:
                        matches = pattern.findall(code)
                        if isinstance(matches, list):
                            for match in matches:
                                if isinstance(match, str):
                                    found_files.add(match)
                        elif isinstance(matches, str):
                            found_files.add(matches)
                    
                    # For each found file, add the corresponding failed executions
                    for found_file in found_files:
                        if found_file in filename_to_executions:
                            for failed_exec in filename_to_executions[found_file]:
                                if failed_exec not in required_failed_executions:
                                    required_failed_executions.append(failed_exec)
        
        # Filter to successful executions + required failed executions
        successful_executions = []
        for exec_entry in execution_history:
            if isinstance(exec_entry, dict) and exec_entry.get("success", False):
                successful_executions.append(exec_entry)
        
        # Add required failed executions (those that generate files used by successful executions)
        if required_failed_executions:
            print(f"📦 Including {len(required_failed_executions)} failed execution(s) that generate required output files...")
            for failed_exec in required_failed_executions:
                output_files = failed_exec.get("output_files", [])
                output_names = [Path(f).name for f in output_files if isinstance(f, str)]
                print(f"   - Including failed execution generating: {', '.join(output_names[:3])}{'...' if len(output_names) > 3 else ''}")
            successful_executions.extend(required_failed_executions)
            # Sort by timestamp to maintain execution order
            successful_executions.sort(key=lambda x: x.get("timestamp", ""))
        
        if not successful_executions:
            print("⚠️  No successful executions found to save workflow.")
            return None
        
        print(f"📝 Saving workflow in simple mode (concatenating {len(successful_executions)} execution(s))...")
        
        # Extract workflow name if not provided
        if not workflow_name:
            workflow_name = self.get_workflow_name(successful_executions)
        
        # Step 1: Analyze variable dependencies
        # Extract variables used in successful executions
        used_variables = set()
        for exec_entry in successful_executions:
            if not isinstance(exec_entry, dict):
                continue
            
            code = exec_entry.get("code", "")
            if isinstance(code, str) and code.strip():
                try:
                    used_variables.update(self._extract_variable_usage(code))
                except Exception:
                    # Skip if extraction fails
                    pass
        
        # Step 2: Extract variable definitions from successful executions
        defined_variables = set()
        for exec_entry in successful_executions:
            if not isinstance(exec_entry, dict):
                continue
            
            code = exec_entry.get("code", "")
            if isinstance(code, str) and code.strip():
                try:
                    defined_variables.update(self._extract_variable_definitions(code))
                except Exception:
                    # Skip if extraction fails
                    pass
        
        # Step 3: Find missing variable definitions
        # Also recursively find dependencies of missing variables
        missing_variables = used_variables - defined_variables
        
        # Step 3.5: Recursively find all dependencies of missing variables
        # This ensures we extract the full dependency chain (e.g., if tumor_counts is missing,
        # we also need counts_df and tumor_samples)
        all_failed_executions = [
            exec_entry for exec_entry in execution_history
            if not exec_entry.get("success", False)
        ]
        
        # Build a map of all variable definitions in failed executions
        failed_var_definitions = {}  # {var_name: (code, dependencies)}
        for exec_entry in all_failed_executions:
            if not isinstance(exec_entry, dict):
                continue
            
            code = exec_entry.get("code", "")
            if not isinstance(code, str) or not code.strip():
                continue
            
            try:
                tree = ast.parse(code)
                lines = code.split('\n')
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                var_name = target.id
                                dependencies = self._extract_variable_dependencies(node.value)
                                start_line = node.lineno - 1
                                end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                                assignment_code = '\n'.join(lines[start_line:end_line])
                                
                                if var_name not in failed_var_definitions:
                                    failed_var_definitions[var_name] = (assignment_code, dependencies)
            except Exception:
                # Skip if parsing fails
                pass
        
        # Recursively expand missing_variables to include all dependencies
        expanded_missing = missing_variables.copy()
        to_check = list(missing_variables)
        checked = set()
        
        while to_check:
            var_name = to_check.pop(0)
            if var_name in checked:
                continue
            checked.add(var_name)
            
            # If this variable is defined in a failed execution, add its dependencies
            if var_name in failed_var_definitions:
                _, dependencies = failed_var_definitions[var_name]
                for dep in dependencies:
                    # Only add if not already defined in successful executions
                    if dep not in defined_variables and dep not in expanded_missing:
                        expanded_missing.add(dep)
                        to_check.append(dep)
        
        missing_variables = expanded_missing
        
        # Step 4: Extract variable definitions from failed executions
        dependency_code_blocks = []
        if missing_variables:
            print(f"🔍 Analyzing variable dependencies: {len(missing_variables)} missing variable(s) found")
            failed_executions = [
                exec_entry for exec_entry in execution_history
                if not exec_entry.get("success", False)
            ]
            
            # OPTIMIZATION: Pre-parse all failed execution code blocks once
            # Build a lookup map: {var_name: [(exec_idx, code, dependencies, node), ...]}
            # This avoids repeated AST parsing in the loop
            var_lookup_map = {}  # {var_name: list of (exec_idx, code, dependencies, node, line_range)}
            
            for exec_idx, exec_entry in enumerate(failed_executions):
                if not isinstance(exec_entry, dict):
                    continue
                
                code = exec_entry.get("code", "")
                if not isinstance(code, str) or not code.strip():
                    continue
                
                try:
                    # Parse once per execution block
                    tree = ast.parse(code)
                    lines = code.split('\n')
                    
                    # Extract all variable definitions from this block
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    var_name = target.id
                                    dependencies = self._extract_variable_dependencies(node.value)
                                    start_line = node.lineno - 1
                                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                                    
                                    if var_name not in var_lookup_map:
                                        var_lookup_map[var_name] = []
                                    var_lookup_map[var_name].append((
                                        exec_idx, code, dependencies, node, (start_line, end_line)
                                    ))
                except Exception:
                    # Skip if parsing fails
                    continue
            
            # Extract variable definitions using the lookup map
            # Process multiple times to handle dependencies between failed blocks
            max_iterations = len(failed_executions) * 2  # Prevent infinite loops
            iteration = 0
            remaining_missing = missing_variables.copy()
            
            while remaining_missing and iteration < max_iterations:
                iteration += 1
                newly_extracted = False
                
                # Use lookup map for O(1) access instead of O(n) iteration
                for var_name in list(remaining_missing):
                    if var_name not in var_lookup_map:
                        continue
                    
                    # Find first definition whose dependencies are satisfied
                    for exec_idx, code, dependencies, node, (start_line, end_line) in var_lookup_map[var_name]:
                        # Check if all dependencies are satisfied
                        missing_deps = dependencies - defined_variables
                        
                        if not missing_deps:
                            # All dependencies satisfied, extract this definition
                            try:
                                lines = code.split('\n')
                                assignment_code = '\n'.join(lines[start_line:end_line])
                                
                                # Format as extracted code block
                                header = f"# Variable definitions extracted from failed execution (required by successful code)"
                                var_def_code = f"{header}\n{assignment_code}"
                                
                                dependency_code_blocks.append(var_def_code)
                                
                                # Update defined variables
                                defined_variables.add(var_name)
                                remaining_missing.discard(var_name)
                                newly_extracted = True
                                
                                # Remove from lookup map to avoid duplicates
                                var_lookup_map[var_name].remove((exec_idx, code, dependencies, node, (start_line, end_line)))
                                if not var_lookup_map[var_name]:
                                    del var_lookup_map[var_name]
                                
                                break  # Use first matching definition
                            except Exception as e:
                                self.logger.logger.debug(f"Failed to extract variable definition for {var_name}: {e}")
                                continue
                
                # If no new variables were extracted in this iteration, break
                if not newly_extracted:
                    break
            
            # Update missing_variables to reflect what we actually extracted
            missing_variables = remaining_missing
        
        # Step 5: Concatenate code blocks (dependencies first, then successful executions)
        code_blocks = []
        
        # Add dependency code blocks first (variable definitions from failed executions)
        code_blocks.extend(dependency_code_blocks)
        
        # Add successful execution code blocks
        for exec_entry in successful_executions:
            if not isinstance(exec_entry, dict):
                continue
            
            code = exec_entry.get("code", "")
            if isinstance(code, str) and code.strip():
                code_blocks.append(code)
        
        if not code_blocks:
            print("⚠️  No code found in successful executions.")
            return None
        
        # Join code blocks with double newlines
        concatenated_code = "\n\n".join(code_blocks)
        
        # Parameterize file paths
        parameterized_code = self._parameterize_file_paths(concatenated_code)
        
        # Apply rule-based import fixes BEFORE removing imports (AST needs full code with imports)
        fixed_code = self._fix_import_aliases_simple(parameterized_code, "")
        
        # Extract imports from fixed code
        imports = self.code_extractor.extract_imports(fixed_code)
        import_section = "\n".join(imports) if imports else ""
        
        # Remove duplicate imports from code
        code_without_imports = self._remove_imports_from_code(fixed_code)
        
        # Generate header
        metadata = {
            "workflow_name": workflow_name,
            "generated": datetime.now().isoformat(),
            "description": f"Workflow extracted from {len(successful_executions)} execution(s) (simple concatenation mode)",
            "input_formats": "N/A",
            "output_formats": "N/A",
            "tools_libraries": ", ".join([imp.split()[1] if " as " in imp else imp.split()[-1] for imp in imports[:10]]),
            "environment": f"Python {os.sys.version.split()[0]}, {os.name}"
        }
        header = self._generate_header(metadata, workflow_name)
        
        # In simple mode, argparse is already added in _parameterize_file_paths
        # So we don't need a separate main block - code runs directly
        
        # Combine everything
        complete_workflow = f"""{header}

{import_section}

{code_without_imports}
"""
        
        # Save workflow file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self._save_workflow_file(complete_workflow, workflow_name, timestamp=timestamp, temp=False)
        
        if file_path:
            print(f"✅ Workflow saved (simple mode): {file_path}")
            self.logger.log_workflow_complete(file_path, None)
        
        return file_path
    
    def _save_workflow_notebook(
        self,
        execution_history: List[Dict],
        workflow_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Save workflow as Jupyter notebook with each execute block as a cell.
        
        This approach is simpler than simple mode because:
        - No complex variable dependency analysis needed
        - Notebook handles cell-to-cell state automatically
        - Errors in one cell don't break the entire workflow
        
        Args:
            execution_history: List of execution dictionaries
            workflow_name: Optional workflow name
            
        Returns:
            Path to saved notebook file, or None if saving failed
        """
        # Input validation
        if not isinstance(execution_history, list):
            self.logger.log_error("Invalid execution_history: must be a list")
            return None
        
        if workflow_name is not None and not isinstance(workflow_name, str):
            workflow_name = str(workflow_name) if workflow_name else None
        
        # Step 1: Include ALL executions in order (success or failure doesn't matter)
        # Notebook mode can handle errors gracefully with --allow-errors flag
        # Failed blocks may contain important imports or code that's needed later
        all_executions = []
        
        for exec_entry in execution_history:
            if not isinstance(exec_entry, dict):
                continue
            
            # Include all executions regardless of success status
            # Just ensure they have code
            code = exec_entry.get("code", "")
            if isinstance(code, str) and code.strip():
                all_executions.append(exec_entry)
        
        # Sort by timestamp to maintain execution order
        all_executions.sort(key=lambda x: x.get("timestamp", ""))
        
        if not all_executions:
            print("⚠️  No executions found to save workflow.")
            return None
        
        print(f"📝 Saving workflow as notebook ({len(all_executions)} cell(s))...")
        
        # Step 2: Extract workflow name if not provided
        if not workflow_name:
            workflow_name = self.get_workflow_name(all_executions)
        
        # Step 3: Convert each execution to a notebook cell
        cells = []
        all_imports = set()
        
        for exec_entry in all_executions:
            code = exec_entry.get("code", "")
            if not isinstance(code, str) or not code.strip():
                continue
            
            # Simple file path replacement (no complex AST parsing)
            # Replace common input file patterns with placeholders
            code = self._replace_file_paths_simple(code)
            
            # Extract imports (simple regex-based, no AST parsing)
            imports = self._extract_imports_simple(code)
            all_imports.update(imports)
            
            # Create cell
            cell = {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {
                    "original_timestamp": exec_entry.get("timestamp", ""),
                    "success": exec_entry.get("success", False),
                    "execution_index": exec_entry.get("execution_index", -1)
                },
                "outputs": [],
                "source": code.splitlines(keepends=True)
            }
            cells.append(cell)
        
        # Step 4: Create first cell with all imports
        if all_imports:
            import_cell = {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": "\n".join(sorted(all_imports)).splitlines(keepends=True) + ["\n"]
            }
            cells.insert(0, import_cell)
        
        # Step 4.5: Add argparse setup cell if needed (after imports, before code cells)
        # Check if any cell uses argparse variables
        needs_argparse = False
        for cell in cells:
            cell_code = ''.join(cell.get("source", []))
            if any(var in cell_code for var in ["input_clinical", "input_survival", "input_star_counts", "output_dir"]):
                needs_argparse = True
                break
        
        if needs_argparse:
            argparse_cell = {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Parse command-line arguments\n",
                    "# This cell works both in Jupyter notebook and command-line execution\n",
                    "import argparse\n",
                    "import sys\n",
                    "import os\n",
                    "\n",
                    "# Check if running in Jupyter notebook environment\n",
                    "is_jupyter = 'ipykernel' in sys.modules or 'IPython' in sys.modules\n",
                    "\n",
                    "if is_jupyter:\n",
                    "    # Jupyter environment: use default values (no argparse)\n",
                    "    input_clinical = None\n",
                    "    input_star_counts = None\n",
                    "    input_survival = None\n",
                    "    output_dir = '.'\n",
                    "    print(\"Running in Jupyter notebook - using default file paths\")\n",
                    "    print(\"To use custom paths, modify the variables above or run via command-line\")\n",
                    "else:\n",
                    "    # Command-line environment: parse arguments\n",
                    "    parser = argparse.ArgumentParser(description='Workflow script')\n",
                    "    parser.add_argument('--input-clinical', type=str, help='Input clinical file path', default=None)\n",
                    "    parser.add_argument('--input-star-counts', type=str, help='Input star_counts file path', default=None)\n",
                    "    parser.add_argument('--input-survival', type=str, help='Input survival file path', default=None)\n",
                    "    parser.add_argument('--output-dir', type=str, help='Output directory', default='.')\n",
                    "    args = parser.parse_args()\n",
                    "    \n",
                    "    # Set input file paths\n",
                    "    input_clinical = args.input_clinical\n",
                    "    input_star_counts = args.input_star_counts\n",
                    "    input_survival = args.input_survival\n",
                    "    output_dir = args.output_dir\n",
                    "\n",
                    "# Create output directory\n",
                    "os.makedirs(output_dir, exist_ok=True)\n"
                ]
            }
            # Insert after import cell (index 1 if import cell exists, else 0)
            insert_idx = 1 if all_imports else 0
            cells.insert(insert_idx, argparse_cell)
        
        # Step 5: Create notebook structure
        notebook = {
            "cells": cells,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {
                    "name": "python",
                    "version": os.sys.version.split()[0]
                },
                "workflow_info": {
                    "workflow_name": workflow_name,
                    "generated": datetime.now().isoformat(),
                    "description": f"Workflow extracted from {len(all_executions)} execution(s) (notebook mode)",
                    "num_cells": len(cells)
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }
        
        # Step 6: Save notebook file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-_]', '_', workflow_name)[:self.MAX_FILENAME_LENGTH] if workflow_name else "workflow"
        notebook_filename = f"workflow_{safe_name}_{timestamp}.ipynb"
        notebook_path = self.workflows_dir / notebook_filename
        
        try:
            with open(notebook_path, 'w', encoding='utf-8') as f:
                json.dump(notebook, f, indent=1, ensure_ascii=False)
            
            print(f"✅ Workflow saved as notebook: {notebook_path}")
            self.logger.log_workflow_complete(str(notebook_path), None)
            
            return str(notebook_path)
        except Exception as e:
            self.logger.log_error(f"Failed to save notebook: {e}")
            return None
    
    def _replace_file_paths_simple(self, code: str) -> str:
        """
        Simple file path replacement for notebook mode.
        Replaces hardcoded file paths with argparse-style variables or placeholders.
        
        This is much simpler than _parameterize_file_paths() - just basic string replacement.
        
        Args:
            code: Code string with hardcoded paths
            
        Returns:
            Code with replaced paths
        """
        # For notebook mode, we can use simpler replacement
        # Just replace common patterns with variables that can be set at the top
        
        # Common intermediate file patterns (files generated by workflow, should be read from output_dir)
        intermediate_patterns = [
            r'all_deg_results\.csv',
            r'significant_degs\.csv',
            r'prognostic_genes\.csv',
            r'model_coefficients\.csv',
            r'risk_scores.*\.csv',
            r'enrichment.*\.csv',
            r'deg_results\.csv',
            r'results\.csv'
        ]
        
        # Pattern 1: pd.read_csv() - match entire function call to preserve existing parameters
        def replace_read_csv_full(match):
            full_call = match.group(0)
            filepath = match.group(1)
            existing_params = match.group(2) if len(match.groups()) > 1 else ""
            filename = Path(filepath).name
            
            # Check if it's an intermediate file (should be read from output_dir)
            is_intermediate = any(re.search(pattern, filename, re.IGNORECASE) for pattern in intermediate_patterns)
            
            if is_intermediate:
                # Intermediate file: read from output_dir
                return f"pd.read_csv(os.path.join(output_dir, \"{filename}\"){existing_params})"
            elif 'clinical' in filename.lower():
                # Input file: use argparse variable (preserve existing params)
                return f"pd.read_csv(input_clinical if input_clinical else \"{filename}\"{existing_params})"
            elif 'survival' in filename.lower():
                return f"pd.read_csv(input_survival if input_survival else \"{filename}\"{existing_params})"
            elif 'counts' in filename.lower() or 'star' in filename.lower():
                return f"pd.read_csv(input_star_counts if input_star_counts else \"{filename}\"{existing_params})"
            else:
                # Generic: keep relative path with existing params
                return f"pd.read_csv(\"{filename}\"{existing_params})"
        
        # Pattern 2: .to_csv() with hardcoded paths - replace with output_dir
        def replace_to_csv(match):
            filepath = match.group(1)
            filename = Path(filepath).name
            rest = match.group(2) if len(match.groups()) > 1 else ""
            return f".to_csv(os.path.join(output_dir, \"{filename}\"){rest})"
        
        # Pattern 3: plt.savefig() with hardcoded paths
        def replace_savefig(match):
            filepath = match.group(1)
            filename = Path(filepath).name
            rest = match.group(2) if len(match.groups()) > 1 else ""
            return f"plt.savefig(os.path.join(output_dir, \"{filename}\"){rest})"
        
        # Apply replacements - match entire function call including parameters
        # Pattern: pd.read_csv("path", param1=val1, param2=val2)
        code = re.sub(
            r'pd\.read_csv\(["\']([^"\']+)["\']([^)]*)\)',
            replace_read_csv_full,
            code
        )
        code = re.sub(r'\.to_csv\(["\']([^"\']+)["\']([^)]*)\)', replace_to_csv, code)
        code = re.sub(r'plt\.savefig\(["\']([^"\']+)["\']([^)]*)\)', replace_savefig, code)
        
        # Remove argparse setup from individual cells (will be added at notebook level)
        # Remove argparse parser creation and args parsing blocks
        code = re.sub(
            r'# Parse command-line arguments\s*\nimport argparse\s*\nparser = argparse\.ArgumentParser\([^)]+\)\s*\n(?:parser\.add_argument\([^)]+\)\s*\n)*args = parser\.parse_args\(\)\s*\n\s*# Set input file paths\s*\n(?:input_\w+ = args\.\w+\s*\n)*output_dir = args\.output_dir\s*\nos\.makedirs\(output_dir, exist_ok=True\)\s*\n',
            '',
            code,
            flags=re.MULTILINE
        )
        
        # Ensure os is imported if os.path.join or os.makedirs is used
        if ("os.path.join" in code or "os.makedirs" in code) and "import os" not in code:
            # Add import os after other imports
            lines = code.split('\n')
            import_end = 0
            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')):
                    import_end = i + 1
                elif import_end > 0 and line.strip() and not line.strip().startswith('#'):
                    break
            if import_end > 0:
                lines.insert(import_end, "import os")
                code = '\n'.join(lines)
        
        # Don't add argparse setup here - it will be added at notebook level
        if False:  # Disabled - argparse handled at notebook level
            argparse_setup = """
# Parse command-line arguments
import argparse
parser = argparse.ArgumentParser(description='Workflow script')
parser.add_argument('--input-clinical', type=str, help='Input clinical file path', default=None)
parser.add_argument('--input-star-counts', type=str, help='Input star_counts file path', default=None)
parser.add_argument('--input-survival', type=str, help='Input survival file path', default=None)
parser.add_argument('--output-dir', type=str, help='Output directory', default='.')
args = parser.parse_args()

# Set input file paths
input_clinical = args.input_clinical
input_star_counts = args.input_star_counts
input_survival = args.input_survival
output_dir = args.output_dir
os.makedirs(output_dir, exist_ok=True)
"""
            # Insert after imports
            lines = code.split('\n')
            import_end = 0
            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')):
                    import_end = i + 1
                elif import_end > 0 and line.strip() and not line.strip().startswith('#'):
                    break
            lines.insert(import_end, argparse_setup.strip())
            code = '\n'.join(lines)
        
        return code
    
    def _extract_imports_simple(self, code: str) -> Set[str]:
        """
        Simple import extraction using regex (no AST parsing).
        Preserves import statements with aliases.
        
        Args:
            code: Code string
            
        Returns:
            Set of import statements
        """
        imports = set()
        
        # Pattern for import statements (with or without alias)
        import_pattern = re.compile(r'^(import\s+\S+|from\s+\S+\s+import\s+[^\n]+)', re.MULTILINE)
        
        for match in import_pattern.finditer(code):
            import_stmt = match.group(1).strip()
            if import_stmt:
                # Normalize common imports to use standard aliases
                # This ensures consistency across cells
                normalized = self._normalize_import(import_stmt)
                imports.add(normalized)
        
        return imports
    
    def _normalize_import(self, import_stmt: str) -> str:
        """
        Normalize import statements to use standard aliases.
        
        Args:
            import_stmt: Import statement string
            
        Returns:
            Normalized import statement
        """
        # Standard alias mappings
        alias_mappings = {
            r'^import pandas$': 'import pandas as pd',
            r'^import numpy$': 'import numpy as np',
            r'^import matplotlib\.pyplot$': 'import matplotlib.pyplot as plt',
            r'^import seaborn$': 'import seaborn as sns',
        }
        
        # Check if already has alias
        if ' as ' in import_stmt:
            return import_stmt
        
        # Try to normalize
        for pattern, replacement in alias_mappings.items():
            if re.match(pattern, import_stmt):
                return replacement
        
        return import_stmt
    
    def _parameterize_file_paths(self, code: str) -> str:
        """
        Parameterize hardcoded file paths in code.
        
        Replaces hardcoded file paths with argparse parameters:
        - Input files: Use --input parameter
        - Output files: Use --output-dir parameter (relative paths)
        
        Args:
            code: Code string with hardcoded paths
            
        Returns:
            Code with parameterized paths
        """
        # Cache string split result at the start (performance optimization)
        # This avoids multiple split() calls throughout the method
        lines = code.split('\n')
        
        # Add argparse import if not present
        if "import argparse" not in code and "argparse" not in code:
            # Find first import line
            import_end = 0
            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')):
                    import_end = i + 1
                elif import_end > 0 and line.strip() and not line.strip().startswith('#'):
                    break
            
            # Insert argparse import
            lines.insert(import_end, "import argparse")
            code = '\n'.join(lines)
            # Update cached lines after modification
            lines = code.split('\n')
        
        # Add argparse setup at the beginning (after imports, before main code)
        # (lines already cached above)
        
        # Find where imports end
        import_end = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                import_end = i + 1
            elif import_end > 0 and line.strip() and not line.strip().startswith('#'):
                break
        
        # Identify intermediate output files (files saved by .to_csv() in the workflow)
        # These should be read from output_dir, not input_file
        # Call once and cache result (performance optimization)
        intermediate_files = self._identify_intermediate_files(code)
        
        # Detect multiple input file patterns in code
        # Find all unique file paths that are read (not intermediate files)
        input_file_patterns = set()
        
        # Find pd.read_csv() calls with hardcoded paths (use pre-compiled patterns)
        read_csv_matches = self._READ_CSV_PATTERN.findall(code)
        read_parquet_matches = self._READ_PARQUET_PATTERN.findall(code)
        
        # Combine all file paths
        all_file_paths = set(read_csv_matches + read_parquet_matches)
        
        # Pre-compile intermediate patterns for performance
        intermediate_patterns_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in self.COMMON_INTERMEDIATE_PATTERNS]
        
        # Filter out intermediate files and absolute paths
        for file_path in all_file_paths:
            if not isinstance(file_path, str):
                continue
            
            try:
                file_name = Path(file_path).name
            except (ValueError, TypeError):
                continue
            
            # Skip intermediate files (use compiled patterns for performance)
            is_intermediate = (
                file_path in intermediate_files or
                any(pattern.search(file_path) for pattern in intermediate_patterns_compiled)
            )
            
            if not is_intermediate:
                # Skip absolute paths (these are usually system files)
                if not Path(file_path).is_absolute():
                    # Extract file type/pattern from filename
                    # e.g., "TCGA-LUAD.star_counts.tsv.gz" -> "star_counts"
                    # e.g., "TCGA-LUAD.clinical.tsv.gz" -> "clinical"
                    # e.g., "TCGA-LUAD.survival.tsv.gz" -> "survival"
                    parts = file_name.split('.')
                    if len(parts) >= 2:
                        # Try to extract meaningful identifier
                        # Pattern: prefix.type.ext or type.ext
                        if len(parts) >= 3:
                            # e.g., "TCGA-LUAD.star_counts.tsv.gz" -> "star_counts"
                            file_type = parts[-3] if parts[-2] in ['tsv', 'csv'] else parts[-2]
                        else:
                            file_type = parts[0]
                        input_file_patterns.add((file_type, file_path))
        
        # Group by file type pattern
        file_type_map = {}
        for file_type, file_path in input_file_patterns:
            if file_type not in file_type_map:
                file_type_map[file_type] = []
            file_type_map[file_type].append(file_path)
        
        # Build argparse setup based on detected file patterns
        if len(input_file_patterns) > 1:
            # Multiple input files detected - create specific arguments for each type
            argparse_args = []
            input_file_vars = []
            
            for file_type, file_paths in sorted(file_type_map.items()):
                # Use the first file path as default
                default_path = file_paths[0]
                arg_name = f'--input-{file_type.replace("_", "-")}'
                var_name = f'input_{file_type}'
                
                argparse_args.append(f"parser.add_argument('{arg_name}', type=str, help='Input {file_type} file path', default=None)")
                try:
                    default_file_name = Path(default_path).name
                    # Sanitize file_type and default_file_name for glob pattern (security: prevent pattern injection)
                    safe_file_type = file_type.replace('[', '\\[').replace(']', '\\]').replace('*', '\\*').replace('?', '\\?')
                    safe_default_file_name = default_file_name.replace('[', '\\[').replace(']', '\\]').replace('*', '\\*').replace('?', '\\?')
                    
                    input_file_vars.append(f"""# Set {file_type} input file path
if args.{var_name}:
    {var_name} = args.{var_name}
else:
    # Default: try to find matching file in current directory
    import glob
    matching_files = glob.glob('*{safe_file_type}*') + glob.glob('*{safe_default_file_name}*')
    if matching_files:
        {var_name} = matching_files[0]
    else:
        {var_name} = "{default_path}"
""")
                except (ValueError, TypeError):
                    # Invalid path, skip this file type
                    continue
            
            argparse_setup = f"""
# Parse command-line arguments
parser = argparse.ArgumentParser(description='Workflow script')
{chr(10).join(argparse_args)}
parser.add_argument('--output-dir', type=str, help='Output directory', default='.')
args = parser.parse_args()

{chr(10).join(input_file_vars)}

# Set output directory
output_dir = args.output_dir
import os
os.makedirs(output_dir, exist_ok=True)
"""
        else:
            # Single input file - use original simple approach
            argparse_setup = """
# Parse command-line arguments
parser = argparse.ArgumentParser(description='Workflow script')
parser.add_argument('--input', type=str, help='Input file path', default=None)
parser.add_argument('--output-dir', type=str, help='Output directory', default='.')
args = parser.parse_args()

# Set input file path if provided
if args.input:
    input_file = args.input
else:
    # Default: try to find input file in current directory
    import glob
    input_files = glob.glob('*.tsv.gz') + glob.glob('*.csv') + glob.glob('*.tsv')
    if input_files:
        input_file = input_files[0]
    else:
        input_file = None

# Set output directory
output_dir = args.output_dir
import os
os.makedirs(output_dir, exist_ok=True)
"""
        
        lines.insert(import_end, argparse_setup)
        code = '\n'.join(lines)
        
        # Re-identify intermediate files from regenerated code (after argparse_setup insertion)
        # This is necessary because code was regenerated and may have different file paths
        # Cache result to avoid duplicate work (performance optimization)
        intermediate_files_updated = self._identify_intermediate_files(code)
        intermediate_files = intermediate_files_updated
        
        # Replace common input file patterns
        # Pattern: pd.read_csv("file.csv", ...) - need to match the entire call
        # But skip intermediate files (they should use output_dir)
        # Use pre-compiled intermediate patterns (performance optimization)
        def replace_read_csv(match):
            file_path = match.group(1)
            rest = match.group(2) if len(match.groups()) > 1 else ""
            
            if not isinstance(file_path, str):
                return match.group(0)
            
            # Check if this is an intermediate file (saved in this workflow)
            is_intermediate = (
                file_path in intermediate_files or
                any(pattern.search(file_path) for pattern in intermediate_patterns_compiled)
            )
            
            if is_intermediate:
                # Use output_dir for intermediate files
                file_name = Path(file_path).name
                return f'pd.read_csv(os.path.join(output_dir, "{file_name}"){rest})'
            elif Path(file_path).is_absolute():
                # Absolute paths (like system files) - keep as is
                return f'pd.read_csv("{file_path}"{rest})'
            else:
                # Determine which input variable to use based on file pattern
                file_name = Path(file_path).name
                # Extract file type from filename
                parts = file_name.split('.')
                if len(parts) >= 2:
                    if len(parts) >= 3:
                        file_type = parts[-3] if parts[-2] in ['tsv', 'csv'] else parts[-2]
                    else:
                        file_type = parts[0]
                    
                    # Check if we have a specific input variable for this file type
                    if file_type in file_type_map:
                        var_name = f'input_{file_type}'
                        return f'pd.read_csv({var_name} if {var_name} else "{file_path}"{rest})'
                
                # Fallback to generic input_file (for single input file case)
                return f'pd.read_csv(input_file if input_file else "{file_path}"{rest})'
        
        # Match pd.read_csv("file.csv") or pd.read_csv("file.csv", ...)
        # Use pre-compiled pattern (performance optimization)
        code = self._READ_CSV_FULL_PATTERN.sub(replace_read_csv, code)
        
        # Also handle pd.read_parquet with same logic
        def replace_read_parquet(match):
            file_path = match.group(1)
            rest = match.group(2) if len(match.groups()) > 1 else ""
            
            if not isinstance(file_path, str):
                return match.group(0)
            
            is_intermediate = (
                file_path in intermediate_files or
                any(pattern.search(file_path) for pattern in intermediate_patterns_compiled)
            )
            
            if is_intermediate:
                file_name = Path(file_path).name
                return f'pd.read_parquet(os.path.join(output_dir, "{file_name}"){rest})'
            elif Path(file_path).is_absolute():
                return f'pd.read_parquet("{file_path}"{rest})'
            else:
                file_name = Path(file_path).name
                parts = file_name.split('.')
                if len(parts) >= 2:
                    if len(parts) >= 3:
                        file_type = parts[-3] if parts[-2] in ['tsv', 'csv', 'parquet'] else parts[-2]
                    else:
                        file_type = parts[0]
                    
                    if file_type in file_type_map:
                        var_name = f'input_{file_type}'
                        return f'pd.read_parquet({var_name} if {var_name} else "{file_path}"{rest})'
                
                return f'pd.read_parquet(input_file if input_file else "{file_path}"{rest})'
        
        # Use pre-compiled pattern (performance optimization)
        code = self._READ_PARQUET_FULL_PATTERN.sub(replace_read_parquet, code)
        
        # Pattern: file_path = "file.csv" (but only if it's a simple assignment, not already using input_file)
        # Don't replace if file_path is already set from input_file
        if 'file_path = input_file' not in code:
            def replace_file_path_assign(match):
                indent = match.group(1)
                file_path = match.group(2)
                return f'{indent}file_path = input_file if input_file else "{file_path}"'
            
            code = self._FILE_PATH_ASSIGN_PATTERN.sub(replace_file_path_assign, code)
        
        # Replace output file patterns (use pre-compiled patterns for performance)
        def replace_to_csv(match):
            file_path = match.group(1)
            rest = match.group(2) if len(match.groups()) > 1 else ""
            try:
                file_name = Path(file_path).name
                return f".to_csv(os.path.join(output_dir, '{file_name}'){rest})"
            except (ValueError, TypeError):
                return match.group(0)
        
        code = self._TO_CSV_PATTERN.sub(replace_to_csv, code)
        
        def replace_savefig(match):
            file_path = match.group(1)
            rest = match.group(2) if len(match.groups()) > 1 else ""
            try:
                file_name = Path(file_path).name
                return f".savefig(os.path.join(output_dir, '{file_name}'){rest})"
            except (ValueError, TypeError):
                return match.group(0)
        
        code = self._SAVEFIG_PATTERN.sub(replace_savefig, code)
        
        def replace_plt_savefig(match):
            file_path = match.group(1)
            rest = match.group(2) if len(match.groups()) > 1 else ""
            try:
                file_name = Path(file_path).name
                return f"plt.savefig(os.path.join(output_dir, '{file_name}'){rest})"
            except (ValueError, TypeError):
                return match.group(0)
        
        code = self._PLT_SAVEFIG_PATTERN.sub(replace_plt_savefig, code)
        
        return code
    
    def _identify_intermediate_files(self, code: str) -> set:
        """
        Identify intermediate output files (files saved by .to_csv(), .savefig() in the workflow).
        These should be read from output_dir, not input_file.
        
        Args:
            code: Code string to analyze
            
        Returns:
            Set of intermediate file paths
        """
        # Input validation
        if not isinstance(code, str):
            return set()
        
        intermediate_files = set()
        
        # Find all files saved with .to_csv() (use pre-compiled pattern)
        to_csv_matches = self._TO_CSV_PATTERN.findall(code)
        for match in to_csv_matches:
            if isinstance(match, tuple) and len(match) > 0:
                file_path = match[0]
                if isinstance(file_path, str):
                    intermediate_files.add(file_path)
            elif isinstance(match, str):
                intermediate_files.add(match)
        
        # Find all files saved with .savefig() or plt.savefig() (use pre-compiled pattern)
        savefig_matches = self._SAVEFIG_PATTERN.findall(code)
        for match in savefig_matches:
            if isinstance(match, tuple) and len(match) > 0:
                file_path = match[0]
                if isinstance(file_path, str):
                    intermediate_files.add(file_path)
            elif isinstance(match, str):
                intermediate_files.add(match)
        
        return intermediate_files
    
    def _fix_import_aliases_simple(self, code: str, import_section: str) -> str:
        """
        Fix import alias mismatches and missing imports in simple mode using AST.
        
        Dynamically detects:
        - Alias usage patterns (e.g., gp.enrichr) and ensures correct import
        - Direct module usage (e.g., argparse.ArgumentParser) and adds missing imports
        - Class instantiation (e.g., StandardScaler()) and adds missing imports
        
        Args:
            code: Code string
            import_section: Current import section (for reference, not used directly)
            
        Returns:
            Code with fixed imports
        """
        # Input validation
        if not isinstance(code, str):
            return str(code) if code is not None else ""
        
        try:
            # Use AST to detect alias mismatches
            alias_fixes = self._detect_alias_mismatches_ast(code)
            
            if not alias_fixes:
                return code
            
            self.logger.logger.info(f"Detected {len(alias_fixes)} import alias fixes needed in simple mode")
            
            # Cache split result (performance optimization)
            lines = code.split('\n')
            changes_made = False
            
            # Apply fixes (sort by line index descending to avoid index shifting issues)
            sorted_fixes = sorted(alias_fixes, key=lambda x: x[1] if x[1] >= 0 else -1, reverse=True)
            
            for correct_import, wrong_import_line_idx in sorted_fixes:
                if wrong_import_line_idx >= 0:
                    # Replace wrong import
                    if wrong_import_line_idx < len(lines):
                        old_line = lines[wrong_import_line_idx]
                        lines[wrong_import_line_idx] = correct_import
                        changes_made = True
                        self.logger.logger.debug(f"Fixed import at line {wrong_import_line_idx + 1}: {old_line.strip()} -> {correct_import}")
                else:
                    # Find where to insert import (after other imports)
                    import_insert_pos = 0
                    for i, line in enumerate(lines):
                        if line.strip().startswith(('import ', 'from ')):
                            import_insert_pos = i + 1
                        elif import_insert_pos > 0 and line.strip() and not line.strip().startswith('#'):
                            break
                    # Add correct import
                    lines.insert(import_insert_pos, correct_import)
                    changes_made = True
                    self.logger.logger.debug(f"Added missing import: {correct_import}")
            
            if changes_made:
                self.logger.logger.info(f"Applied {len(alias_fixes)} import alias fixes in simple mode")
                return '\n'.join(lines)
            else:
                return code
        
        except SyntaxError as e:
            # If AST parsing fails, log and return original code
            self.logger.logger.warning(f"Syntax error fixing import aliases in simple mode: {e}")
            return code
        except Exception as e:
            # Unexpected errors should be logged
            self.logger.logger.error(f"Unexpected error fixing import aliases in simple mode: {e}")
            return code
    
    def _extract_variable_definitions(self, code: str) -> Set[str]:
        """
        Extract variable names that are defined (assigned) in code.
        
        Args:
            code: Code string to analyze
            
        Returns:
            Set of variable names that are defined
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return set()
        
        defined_vars = set()
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Assignment statements: x = ...
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            defined_vars.add(target.id)
                        elif isinstance(target, ast.Tuple):
                            # Multiple assignment: x, y = ...
                            for elt in target.elts:
                                if isinstance(elt, ast.Name):
                                    defined_vars.add(elt.id)
                
                # For loops: for x in ...
                elif isinstance(node, ast.For):
                    if isinstance(node.target, ast.Name):
                        defined_vars.add(node.target.id)
                    elif isinstance(node.target, ast.Tuple):
                        for elt in node.target.elts:
                            if isinstance(elt, ast.Name):
                                defined_vars.add(elt.id)
                
                # With statements: with ... as x
                elif isinstance(node, ast.With):
                    for item in node.items:
                        if item.optional_vars:
                            if isinstance(item.optional_vars, ast.Name):
                                defined_vars.add(item.optional_vars.id)
                
                # Function definitions: def func(...)
                elif isinstance(node, ast.FunctionDef):
                    defined_vars.add(node.name)
                
                # Class definitions: class ClassName
                elif isinstance(node, ast.ClassDef):
                    defined_vars.add(node.name)
                    
        except (SyntaxError, Exception) as e:
            # If parsing fails, return empty set
            pass
        
        return defined_vars
    
    def _extract_variable_usage(self, code: str) -> Set[str]:
        """
        Extract variable names that are used (read) in code.
        
        Args:
            code: Code string to analyze
            
        Returns:
            Set of variable names that are used
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return set()
        
        used_vars = set()
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Name nodes (variable references)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    # Skip built-in names and common module names
                    if node.id not in ['True', 'False', 'None', 'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple']:
                        used_vars.add(node.id)
                
                # Attribute access: obj.attr (we care about obj)
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name) and isinstance(node.value.ctx, ast.Load):
                        used_vars.add(node.value.id)
                        
        except SyntaxError as e:
            # If syntax error, log and return empty set
            self.logger.logger.warning(f"Syntax error extracting variable usage: {e}")
            return set()
        except Exception as e:
            # Unexpected errors should be logged
            self.logger.logger.error(f"Unexpected error extracting variable usage: {e}")
            return set()
        
        return used_vars
    
    def _extract_variable_dependencies(self, node: ast.AST) -> Set[str]:
        """
        Extract variable names that are used (read) in an AST node.
        
        Args:
            node: AST node to analyze
            
        Returns:
            Set of variable names that are used in this node
        """
        dependencies = set()
        
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                # Skip built-in names
                if child.id not in ['True', 'False', 'None', 'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple', 'range', 'enumerate', 'zip']:
                    dependencies.add(child.id)
        
        return dependencies
    
    def _extract_variable_definitions_from_code(
        self, code: str, required_variables: Set[str], defined_variables: Optional[Set[str]] = None
    ) -> Optional[str]:
        """
        Extract code that defines required variables from a code block.
        
        This method extracts only the variable definition statements (assignments)
        that define variables in required_variables, while avoiding code that
        might fail (e.g., inside try/except blocks that failed).
        
        IMPORTANT: Only extracts variable definitions whose dependencies are already
        defined (either in successful executions or in previously extracted definitions).
        
        Args:
            code: Code string to analyze
            required_variables: Set of variable names that need to be defined
            defined_variables: Set of variables already defined in successful executions (optional)
            
        Returns:
            Code string containing variable definitions, or None if no definitions found
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return None
        
        if not isinstance(required_variables, set) or not required_variables:
            return None
        
        # Track variables that are already defined (from successful executions)
        if defined_variables is None:
            defined_variables = set()
        else:
            defined_variables = set(defined_variables)  # Make a copy
        
        try:
            tree = ast.parse(code)
            # Cache split result (performance optimization)
            lines = code.split('\n')
            
            # Single pass: collect all assignments and imports with their dependencies
            # This replaces 4 separate AST walks with 1 consolidated walk
            assignment_info = []  # List of (var_name, node, dependencies, line_range, is_in_try)
            import_info = []  # List of (var_name, node, line_range)
            
            # Track which assignments are already in assignment_info to avoid duplicates
            processed_assignments = set()  # {(lineno, var_name)}
            
            for node in ast.walk(tree):
                # Process regular assignments
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if target.id in required_variables:
                                # Check if already processed (avoid duplicates from try blocks)
                                assignment_key = (node.lineno, target.id)
                                if assignment_key not in processed_assignments:
                                    dependencies = self._extract_variable_dependencies(node.value)
                                    start_line = node.lineno - 1
                                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                                    assignment_info.append((target.id, node, dependencies, (start_line, end_line), False))
                                    processed_assignments.add(assignment_key)
                
                # Process assignments inside try/except blocks
                elif isinstance(node, ast.Try):
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if isinstance(target, ast.Name):
                                    if target.id in required_variables:
                                        # Check if already processed
                                        assignment_key = (stmt.lineno, target.id)
                                        if assignment_key not in processed_assignments:
                                            dependencies = self._extract_variable_dependencies(stmt.value)
                                            start_line = stmt.lineno - 1
                                            end_line = stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno
                                            assignment_info.append((target.id, stmt, dependencies, (start_line, end_line), True))
                                            processed_assignments.add(assignment_key)
                
                # Process imports
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.asname:
                            var_name = alias.asname
                        else:
                            var_name = alias.name.split('.')[0]
                        
                        if var_name in required_variables:
                            start_line = node.lineno - 1
                            end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                            import_info.append((var_name, node, (start_line, end_line)))
                
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.asname:
                            var_name = alias.asname
                        else:
                            var_name = alias.name
                        
                        if var_name in required_variables:
                            start_line = node.lineno - 1
                            end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                            import_info.append((var_name, node, (start_line, end_line)))
            
            # Second pass: extract assignments in dependency order
            # Only extract assignments whose dependencies are satisfied
            extracted_lines = []
            extracted_vars = set(defined_variables)  # Start with already defined variables
            remaining_assignments = assignment_info.copy()
            max_iterations = len(remaining_assignments) * 2  # Prevent infinite loops
            iteration = 0
            
            while remaining_assignments and iteration < max_iterations:
                iteration += 1
                newly_extracted = []
                
                for var_name, node, dependencies, (start_line, end_line), is_in_try in remaining_assignments:
                    # Check if all dependencies are satisfied
                    if var_name not in extracted_vars:
                        # Check if all dependencies are defined
                        missing_deps = dependencies - extracted_vars
                        
                        if not missing_deps:
                            # All dependencies are satisfied, extract this assignment
                            assignment_code = '\n'.join(lines[start_line:end_line])
                            extracted_lines.append(assignment_code)
                            extracted_vars.add(var_name)
                            newly_extracted.append((var_name, node, dependencies, (start_line, end_line), is_in_try))
                
                # Remove extracted assignments from remaining list
                for item in newly_extracted:
                    if item in remaining_assignments:
                        remaining_assignments.remove(item)
                
                # If no new assignments were extracted, break to avoid infinite loop
                if not newly_extracted:
                    break
            
            # Extract import statements that might be needed (already collected in single pass)
            for var_name, node, (start_line, end_line) in import_info:
                if var_name not in extracted_vars:
                    import_code = '\n'.join(lines[start_line:end_line])
                    extracted_lines.append(import_code)
                    extracted_vars.add(var_name)
            
            if extracted_lines:
                # Add a comment explaining why this code is included
                header = f"# Variable definitions extracted from failed execution (required by successful code)"
                return f"{header}\n{chr(10).join(extracted_lines)}"
            
            # If we couldn't extract all required variables due to missing dependencies, log a warning
            if remaining_assignments:
                missing_vars = {var_name for var_name, _, _, _, _ in remaining_assignments}
                missing_deps = set()
                for _, _, deps, _, _ in remaining_assignments:
                    missing_deps.update(deps - extracted_vars)
                
                self.logger.logger.warning(
                    f"Could not extract some variable definitions due to missing dependencies. "
                    f"Missing variables: {missing_vars}, Missing dependencies: {missing_deps}"
                )
            
        except SyntaxError as e:
            # If syntax error, try a simpler regex-based approach for assignments
            # This is a fallback for code that might have syntax errors
            self.logger.logger.warning(f"Syntax error extracting variable definitions from code: {e}, using regex fallback")
            extracted_lines = []
            extracted_vars = set()
            
            for line in code.split('\n'):
                # Simple pattern: variable_name = ...
                for var_name in required_variables:
                    if var_name not in extracted_vars:
                        # Check if this line assigns the variable
                        pattern = rf'^\s*{re.escape(var_name)}\s*='
                        if re.match(pattern, line):
                            extracted_lines.append(line)
                            extracted_vars.add(var_name)
            
            if extracted_lines:
                header = f"# Variable definitions extracted from failed execution (required by successful code)"
                return f"{header}\n{chr(10).join(extracted_lines)}"
        except Exception as e:
            # Unexpected errors should be logged
            self.logger.logger.error(f"Unexpected error extracting variable definitions from code: {e}")
            return None
        
        return None

