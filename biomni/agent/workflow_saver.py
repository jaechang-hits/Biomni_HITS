"""
Workflow Saver Module

Saves workflow code as standalone Python scripts with metadata.
"""

import os
import re
import ast
from pathlib import Path
from typing import Optional, Dict, List, Set
from datetime import datetime

from .workflow_tracker import WorkflowTracker
from .code_filter import CodeFilter
from .code_extractor import CodeExtractor
from .workflow_llm_processor import WorkflowLLMProcessor
from .workflow_validator import WorkflowValidator
from .workflow_preprocessor import WorkflowPreprocessor
from .workflow_postprocessor import WorkflowPostprocessor
from .workflow_logger import WorkflowLogger


class WorkflowSaver:
    """Saves workflow code as standalone Python scripts."""
    
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
        save_mode: str = "simple"  # "llm" or "simple"
    ) -> Optional[str]:
        """
        Save workflow automatically at session end.
        First tries to load from saved execute block files, then falls back to in-memory history.
        
        Args:
            tracker: WorkflowTracker instance with execution history
            workflow_name: Optional workflow name (auto-extracted if not provided)
            
        Returns:
            Path to saved workflow file, or None if saving failed
        """
        # Get in-memory history first (most up-to-date)
        in_memory_history = tracker.get_execution_history()
        
        # Try to load execute blocks from files (for debugging and reconstruction)
        # Only load files from current session to avoid mixing with previous runs
        file_history = tracker.load_execute_blocks_from_files(filter_by_session=True)
        
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
        else:
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
        # Log workflow generation start
        if not workflow_name:
            temp_name = "unnamed"
        else:
            temp_name = workflow_name
        self.logger.log_workflow_start(temp_name, len(execution_history))
        
        # Log execution summary
        self.logger.log_execution_summary(execution_history)
        
        # Filter to data processing code
        filtered_executions = self.code_filter.filter_executions(execution_history)
        
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
        preprocessed_data = self.preprocessor.preprocess(filtered_executions)
        
        # Log preprocessing results
        self.logger.log_preprocessing_results(preprocessed_data)
        
        print(f"   ✓ Extracted {len(preprocessed_data['imports'])} imports")
        print(f"   ✓ Mapped {len(preprocessed_data['output_file_mapping'])} output files")
        print(f"   ✓ Identified {len(preprocessed_data['hardcoded_paths'])} hardcoded paths")
        print(f"   ✓ Extracted {len(preprocessed_data['functions'])} functions")
        
        # Generate workflow code using LLM with retry logic (Phase 2: Auto-retry)
        expected_output_files = list(preprocessed_data.get('output_file_mapping', {}).keys())
        max_retries = 5
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
            for error in validation_errors[:5]:  # Show first 5 errors
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
        output_files = []
        
        # Patterns for output file operations
        patterns = [
            r'\.to_csv\(["\']([^"\']+)["\']',
            r'\.savefig\(["\']([^"\']+)["\']',
            r'gseaplot\([^,]+ofname=["\']([^"\']+)["\']',
            r'\.to_excel\(["\']([^"\']+)["\']',
            r'\.to_json\(["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, code)
            for match in matches:
                file_name = Path(match).name
                output_files.append(file_name)
        
        return list(set(output_files))  # Remove duplicates
    
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
        # If code_blocks is a string, use it directly
        if isinstance(code_blocks, str):
            workflow_code = code_blocks
        else:
            # If it's a list, join them
            workflow_code = "\n\n".join(code_blocks) if isinstance(code_blocks, list) else str(code_blocks)
        
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
        
        # Combine everything
        complete_file = f"""{header}

{import_section}

{workflow_code_clean}

{main_block}
"""
        
        return complete_file
    
    def get_workflow_name(self, execution_history: List[Dict]) -> str:
        """
        Extract workflow name from execution history.
        
        Args:
            execution_history: List of execution entries
            
        Returns:
            Workflow name
        """
        # Try to extract from code patterns
        for execution in execution_history:
            code = execution.get("code", "")
            
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
        # Sanitize workflow name for filename
        safe_name = self._sanitize_filename(workflow_name)
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if temp:
            filename = f"workflow_{safe_name}_{timestamp}.tmp.py"
        else:
            filename = f"workflow_{safe_name}_{timestamp}.py"
        
        file_path = self.workflows_dir / filename
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(workflow_content)
        
        if temp:
            print(f"Workflow saved to temporary file: {file_path}")
        else:
            print(f"Workflow saved to: {file_path}")
        return str(file_path)
    
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
        if len(safe_name) > 50:
            safe_name = safe_name[:50]
        
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
        """Remove import statements from code to avoid duplication."""
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
        
        Returns:
            List of import-related error messages
        """
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
            
            # Check for common alias patterns used in code
            code_str = code
            common_patterns = {
                'pd': ('pandas', 'import pandas as pd'),
                'np': ('numpy', 'import numpy as np'),
                'plt': ('matplotlib.pyplot', 'import matplotlib.pyplot as plt'),
                'sns': ('seaborn', 'import seaborn as sns'),
                'stats': ('scipy.stats', 'from scipy import stats'),
            }
            
            for alias, (module, expected_import) in common_patterns.items():
                # Check if alias is used in code
                if re.search(rf'\b{alias}\.', code_str):
                    # Check if import exists with correct alias
                    if alias not in imports:
                        errors.append(f"Code uses '{alias}.' but missing import: {expected_import}")
                    elif imports[alias] != module and not imports[alias].endswith(module.split('.')[-1]):
                        errors.append(f"Code uses '{alias}.' but import mismatch: found '{imports[alias]}', expected '{module}'")
        
        except Exception as e:
            errors.append(f"Import validation error: {str(e)}")
        
        return errors
    
    def _check_undefined_names(self, code: str) -> List[str]:
        """
        Basic check for potentially undefined names.
        
        Returns:
            List of undefined name warnings
        """
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
            
            # Check for common undefined patterns
            code_lines = code.split('\n')
            for i, line in enumerate(code_lines, 1):
                # Skip comments and empty lines
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                
                # Check for common undefined patterns
                if re.search(r'\bpd\.', line) and 'pd' not in defined_names:
                    errors.append(f"Line {i}: 'pd' may be undefined (use 'import pandas as pd')")
                if re.search(r'\bnp\.', line) and 'np' not in defined_names:
                    errors.append(f"Line {i}: 'np' may be undefined (use 'import numpy as np')")
                if re.search(r'\bplt\.', line) and 'plt' not in defined_names:
                    errors.append(f"Line {i}: 'plt' may be undefined (use 'import matplotlib.pyplot as plt')")
                if re.search(r'\bsns\.', line) and 'sns' not in defined_names:
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
            
            # Step 1: Extract all imports and their aliases
            imports_by_alias = {}  # {alias: (module, import_line, full_import_stmt)}
            imports_by_module = {}  # {module: (alias, import_line, full_import_stmt)}
            
            for node in ast.walk(tree):
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
            
            # Step 2: Detect module/class usage in code
            # Track both alias usage (pd.read_csv) and direct module usage (argparse.ArgumentParser)
            used_aliases = set()  # For alias patterns like pd., np., plt.
            used_modules = set()  # For direct module usage like argparse., glob., os.
            used_classes = set()  # For class instantiation like StandardScaler(), PCA()
            
            for node in ast.walk(tree):
                # Detect attribute access: something.attribute
                if isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        module_or_alias = node.value.id
                        # Check if it's a known module name or alias
                        used_modules.add(module_or_alias)
                        used_aliases.add(module_or_alias)
                
                # Detect class instantiation: ClassName()
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
        
        except (SyntaxError, Exception) as e:
            # If AST parsing fails, return empty list (fallback to regex)
            pass
        
        return fixes
    
    def save_and_validate_workflow(
        self,
        tracker: WorkflowTracker,
        workflow_name: Optional[str] = None,
        max_fix_attempts: int = 2,
        save_mode: str = "simple"  # "llm" or "simple"
    ) -> Optional[str]:
        """
        Save workflow and validate it. If validation fails, attempt to fix using LLM (up to max_fix_attempts times).
        
        This is the main entry point that handles both generation and validation.
        Validation failures will prevent the workflow from being saved in final location.
        
        Args:
            tracker: WorkflowTracker instance with execution history
            workflow_name: Optional workflow name (auto-extracted if not provided)
            max_fix_attempts: Maximum number of fix attempts (default: 2, only used in LLM mode)
            save_mode: Save mode - "llm" for LLM-based generation, "simple" for concatenation (default: "simple")
            
        Returns:
            Path to saved workflow file, or None if saving/validation failed
        """
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
        
        # Get input/output files for validation
        expected_outputs = tracker.get_expected_output_files()
        input_files = tracker.get_input_files()
        
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
        with open(temp_workflow_path, 'r', encoding='utf-8') as f:
            current_workflow = f.read()
        
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
            with open(temp_workflow_path, 'w', encoding='utf-8') as f:
                f.write(fixed_workflow)
            
            validation_result = self.validator.validate_workflow(
                temp_workflow_path,
                input_files,
                expected_outputs
            )
            
            if validation_result["valid"]:
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
            
            current_workflow = fixed_workflow
            error_msg = self._build_comprehensive_error_message(validation_result)
            print(f"⚠️  Rule-based fixes were not sufficient")
        
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
        output_file_mapping = preprocessed_data.get("output_file_mapping", {})
        code_blocks_to_add = []
        
        for missing_file in missing_output_files:
            # Find which executions generate this file
            exec_indices = output_file_mapping.get(missing_file, [])
            
            if not exec_indices:
                # Try to find by filename pattern matching
                for exec_idx, execution in enumerate(executions, 1):
                    output_files = execution.get("output_files", [])
                    for output_file in output_files:
                        from pathlib import Path
                        if Path(output_file).name == missing_file:
                            exec_indices = [exec_idx]
                            break
                    if exec_indices:
                        break
            
            if exec_indices:
                # Extract code from these executions
                for exec_idx in exec_indices:
                    if 0 < exec_idx <= len(executions):
                        execution = executions[exec_idx - 1]
                        code = execution.get("code", "")
                        if code:
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
        # Remove comments that are too specific
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip very specific debug comments
            if line.strip().startswith('#') and any(
                keyword in line.lower() for keyword in ['debug', 'test', 'check', 'verify']
            ):
                continue
            cleaned_lines.append(line)
        
        code = '\n'.join(cleaned_lines)
        
        # Try to parameterize hardcoded paths
        # Replace absolute paths with relative or parameterized paths
        from pathlib import Path
        import re
        
        # Pattern for absolute paths
        abs_path_pattern = r'["\'](/[^"\']+)["\']'
        
        def replace_path(match):
            path_str = match.group(1)
            path_obj = Path(path_str)
            # If it's the output file, use parameterized name
            if path_obj.name == output_file:
                return f'"{output_file}"'
            # Otherwise, try to make it relative
            return f'"{path_obj.name}"'
        
        code = re.sub(abs_path_pattern, replace_path, code)
        
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
        # Find the best insertion point (before main block or at end of process_data)
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
                    if lines[j].strip() and not lines[j].startswith(' ') and not lines[j].startswith('\t'):
                        if not lines[j].strip().startswith('def ') and not lines[j].strip().startswith('class '):
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
            file_name = block_info["file"]
            code = block_info["code"]
            exec_idx = block_info.get("execution_index", "?")
            
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
        # Extract imports from all inserted code blocks
        all_required_imports = set()
        
        for block_info in code_blocks:
            code = block_info["code"]
            # Extract imports from this code block
            imports = self.code_extractor.extract_imports(code)
            all_required_imports.update(imports)
            
            # Also check for common import patterns used in code
            import_patterns = {
                r'\bpd\.': 'import pandas as pd',
                r'\bnp\.': 'import numpy as np',
                r'\bplt\.': 'import matplotlib.pyplot as plt',
                r'\bsns\.': 'import seaborn as sns',
                r'\bstats\.': 'from scipy import stats',
                r'\bgp\.': 'import gseapy as gp',
            }
            
            for pattern, import_stmt in import_patterns.items():
                if re.search(pattern, code):
                    all_required_imports.add(import_stmt)
        
        # Extract current imports from workflow
        current_imports = self.code_extractor.extract_imports(workflow_code)
        current_imports_set = set(current_imports)
        
        # Find missing imports
        missing_imports = []
        for required_import in all_required_imports:
            # Check if this import or a similar one exists
            import_exists = False
            for current_import in current_imports_set:
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
            import_section = self._find_import_section_in_code(workflow_code)
            if import_section:
                # Insert after import section
                new_imports = "\n".join(missing_imports)
                lines = workflow_code.split('\n')
                insert_pos = import_section["end_line"]
                lines.insert(insert_pos, new_imports)
                workflow_code = '\n'.join(lines)
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
    
    def _find_import_section_in_code(self, code: str) -> Optional[Dict]:
        """Find the import section in code and return its end line number."""
        lines = code.split('\n')
        import_start = None
        import_end = None
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                if import_start is None:
                    import_start = i
                import_end = i + 1
            elif import_start is not None and stripped and not stripped.startswith('#'):
                # End of import section
                break
        
        if import_end is not None:
            return {"start_line": import_start, "end_line": import_end}
        
        return None
    
    def _finalize_workflow_file(self, temp_file_path: str) -> str:
        """
        Finalize temporary workflow file by renaming it to final name.
        
        Args:
            temp_file_path: Path to temporary workflow file (.tmp.py)
            
        Returns:
            Path to finalized workflow file
        """
        temp_path = Path(temp_file_path)
        if not temp_path.exists():
            return temp_file_path
        
        # Remove .tmp from filename
        final_filename = temp_path.name.replace('.tmp.py', '.py')
        final_path = temp_path.parent / final_filename
        
        # Rename file
        temp_path.rename(final_path)
        
        print(f"✅ Workflow finalized: {final_path}")
        return str(final_path)
    
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
        if differences:
            error_parts.append(f"\nDETAILED DIFFERENCES ({len(differences)} total):")
            for i, diff in enumerate(differences[:10], 1):  # Show up to 10 differences
                error_parts.append(f"  {i}. {diff}")
            if len(differences) > 10:
                error_parts.append(f"  ... and {len(differences) - 10} more differences")
        
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
        if stderr:
            error_parts.append(f"\nEXECUTION STDERR:\n{stderr[:1000]}")  # Limit to 1000 chars
        
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
        # Filter to only successful executions
        successful_executions = [
            exec_entry for exec_entry in execution_history
            if exec_entry.get("success", False)
        ]
        
        if not successful_executions:
            print("⚠️  No successful executions found to save workflow.")
            return None
        
        print(f"📝 Saving workflow in simple mode (concatenating {len(successful_executions)} successful execution(s))...")
        
        # Extract workflow name if not provided
        if not workflow_name:
            workflow_name = self.get_workflow_name(successful_executions)
        
        # Step 1: Analyze variable dependencies
        # Extract variables used in successful executions
        used_variables = set()
        for exec_entry in successful_executions:
            code = exec_entry.get("code", "").strip()
            if code:
                used_variables.update(self._extract_variable_usage(code))
        
        # Step 2: Extract variable definitions from successful executions
        defined_variables = set()
        for exec_entry in successful_executions:
            code = exec_entry.get("code", "").strip()
            if code:
                defined_variables.update(self._extract_variable_definitions(code))
        
        # Step 3: Find missing variable definitions
        missing_variables = used_variables - defined_variables
        
        # Step 4: Extract variable definitions from failed executions
        dependency_code_blocks = []
        if missing_variables:
            print(f"🔍 Analyzing variable dependencies: {len(missing_variables)} missing variable(s) found")
            failed_executions = [
                exec_entry for exec_entry in execution_history
                if not exec_entry.get("success", False)
            ]
            
            for exec_entry in failed_executions:
                code = exec_entry.get("code", "").strip()
                if code:
                    # Extract only variable definitions that are needed
                    var_def_code = self._extract_variable_definitions_from_code(
                        code, missing_variables
                    )
                    if var_def_code:
                        dependency_code_blocks.append(var_def_code)
                        # Update defined variables to avoid duplicates
                        new_defs = self._extract_variable_definitions(var_def_code)
                        defined_variables.update(new_defs)
                        missing_variables -= new_defs
        
        # Step 5: Concatenate code blocks (dependencies first, then successful executions)
        code_blocks = []
        
        # Add dependency code blocks first (variable definitions from failed executions)
        code_blocks.extend(dependency_code_blocks)
        
        # Add successful execution code blocks
        for exec_entry in successful_executions:
            code = exec_entry.get("code", "").strip()
            if code:
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
        # Add argparse import if not present
        if "import argparse" not in code and "argparse" not in code:
            # Find first import line
            lines = code.split('\n')
            import_end = 0
            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')):
                    import_end = i + 1
                elif import_end > 0 and line.strip() and not line.strip().startswith('#'):
                    break
            
            # Insert argparse import
            lines.insert(import_end, "import argparse")
            code = '\n'.join(lines)
        
        # Add argparse setup at the beginning (after imports, before main code)
        lines = code.split('\n')
        
        # Find where imports end
        import_end = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                import_end = i + 1
            elif import_end > 0 and line.strip() and not line.strip().startswith('#'):
                break
        
        # First, identify intermediate output files (files saved by .to_csv() in the workflow)
        # These should be read from output_dir, not input_file
        intermediate_files = set()
        
        # Find all files saved with .to_csv()
        to_csv_matches = re.findall(r'\.to_csv\(["\']([^"\']+)["\']', code)
        intermediate_files.update(to_csv_matches)
        
        # Find all files saved with .savefig() or plt.savefig()
        savefig_matches = re.findall(r'(?:plt\.)?\.savefig\(["\']([^"\']+)["\']', code)
        intermediate_files.update(savefig_matches)
        
        # Also check for common intermediate file patterns
        common_intermediate_patterns = [
            r'metadata\.csv', r'filtered.*\.csv', r'deg_results\.csv', 
            r'results\.csv', r'pca.*\.csv', r'enrichment.*\.csv'
        ]
        
        # Detect multiple input file patterns in code
        # Find all unique file paths that are read (not intermediate files)
        input_file_patterns = set()
        
        # Find pd.read_csv() calls with hardcoded paths
        read_csv_matches = re.findall(r'pd\.read_csv\(["\']([^"\']+)["\']', code)
        read_parquet_matches = re.findall(r'pd\.read_parquet\(["\']([^"\']+)["\']', code)
        
        # Combine all file paths
        all_file_paths = set(read_csv_matches + read_parquet_matches)
        
        # Filter out intermediate files and absolute paths
        for file_path in all_file_paths:
            file_name = Path(file_path).name
            # Skip intermediate files
            is_intermediate = (
                file_path in intermediate_files or
                any(re.search(pattern, file_path, re.IGNORECASE) for pattern in common_intermediate_patterns)
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
                default_file_name = Path(default_path).name
                input_file_vars.append(f"""# Set {file_type} input file path
if args.{var_name}:
    {var_name} = args.{var_name}
else:
    # Default: try to find matching file in current directory
    import glob
    matching_files = glob.glob('*{file_type}*') + glob.glob('*{default_file_name}*')
    if matching_files:
        {var_name} = matching_files[0]
    else:
        {var_name} = "{default_path}"
""")
            
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
        
        # First, identify intermediate output files (files saved by .to_csv() in the workflow)
        # These should be read from output_dir, not input_file
        intermediate_files = set()
        
        # Find all files saved with .to_csv()
        to_csv_matches = re.findall(r'\.to_csv\(["\']([^"\']+)["\']', code)
        intermediate_files.update(to_csv_matches)
        
        # Find all files saved with .savefig() or plt.savefig()
        savefig_matches = re.findall(r'(?:plt\.)?\.savefig\(["\']([^"\']+)["\']', code)
        intermediate_files.update(savefig_matches)
        
        # Also check for common intermediate file patterns
        common_intermediate_patterns = [
            r'metadata\.csv', r'filtered.*\.csv', r'deg_results\.csv', 
            r'results\.csv', r'pca.*\.csv', r'enrichment.*\.csv'
        ]
        
        # Replace common input file patterns
        # Pattern: pd.read_csv("file.csv", ...) - need to match the entire call
        # But skip intermediate files (they should use output_dir)
        def replace_read_csv(match):
            file_path = match.group(1)
            rest = match.group(2) if len(match.groups()) > 1 else ""
            
            # Check if this is an intermediate file (saved in this workflow)
            is_intermediate = (
                file_path in intermediate_files or
                any(re.search(pattern, file_path, re.IGNORECASE) for pattern in common_intermediate_patterns)
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
        # This regex matches the opening quote, file path, closing quote, and captures any remaining parameters
        code = re.sub(
            r'pd\.read_csv\(["\']([^"\']+)["\']([^)]*)\)',
            replace_read_csv,
            code
        )
        
        # Also handle pd.read_parquet with same logic
        def replace_read_parquet(match):
            file_path = match.group(1)
            rest = match.group(2) if len(match.groups()) > 1 else ""
            
            is_intermediate = (
                file_path in intermediate_files or
                any(re.search(pattern, file_path, re.IGNORECASE) for pattern in common_intermediate_patterns)
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
        
        code = re.sub(
            r'pd\.read_parquet\(["\']([^"\']+)["\']([^)]*)\)',
            replace_read_parquet,
            code
        )
        
        # Pattern: file_path = "file.csv" (but only if it's a simple assignment, not already using input_file)
        # Don't replace if file_path is already set from input_file
        if 'file_path = input_file' not in code:
            code = re.sub(
                r'^(\s*)file_path\s*=\s*["\']([^"\']+)["\']',
                lambda m: f'{m.group(1)}file_path = input_file if input_file else "{m.group(2)}"',
                code,
                flags=re.MULTILINE
            )
        
        # Also handle pd.read_csv(file_path, ...) - but only if file_path is not already set from input_file
        # If file_path was already replaced with input_file logic, keep using file_path variable
        # This handles cases like: file_path = input_file if input_file else "file.csv"; pd.read_csv(file_path, ...)
        # In this case, we don't need to replace file_path in pd.read_csv() because it's already parameterized
        
        # Replace output file patterns
        # Pattern: .to_csv('file.csv') or .to_csv('file.csv', index=False, ...)
        # Match entire function call including all parameters
        code = re.sub(
            r'\.to_csv\(["\']([^"\']+)["\']([^)]*)\)',
            lambda m: f".to_csv(os.path.join(output_dir, '{Path(m.group(1)).name}'){m.group(2)})",
            code
        )
        
        # Pattern: .savefig('file.png') or .savefig('file.png', dpi=300, ...)
        # Match entire function call including all parameters
        code = re.sub(
            r'\.savefig\(["\']([^"\']+)["\']([^)]*)\)',
            lambda m: f".savefig(os.path.join(output_dir, '{Path(m.group(1)).name}'){m.group(2)})",
            code
        )
        
        # Pattern: plt.savefig('file.png') or plt.savefig('file.png', dpi=300, ...)
        # Match entire function call including all parameters
        code = re.sub(
            r'plt\.savefig\(["\']([^"\']+)["\']([^)]*)\)',
            lambda m: f"plt.savefig(os.path.join(output_dir, '{Path(m.group(1)).name}'){m.group(2)})",
            code
        )
        
        return code
    
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
        try:
            # Use AST to detect alias mismatches
            alias_fixes = self._detect_alias_mismatches_ast(code)
            
            if not alias_fixes:
                return code
            
            self.logger.logger.info(f"Detected {len(alias_fixes)} import alias fixes needed in simple mode")
            
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
        
        except (SyntaxError, Exception) as e:
            # If AST parsing fails, log and return original code
            self.logger.logger.warning(f"Failed to fix import aliases in simple mode: {e}")
            return code
    
    def _extract_variable_definitions(self, code: str) -> Set[str]:
        """
        Extract variable names that are defined (assigned) in code.
        
        Args:
            code: Code string to analyze
            
        Returns:
            Set of variable names that are defined
        """
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
                        
        except (SyntaxError, Exception) as e:
            # If parsing fails, return empty set
            pass
        
        return used_vars
    
    def _extract_variable_definitions_from_code(
        self, code: str, required_variables: Set[str]
    ) -> Optional[str]:
        """
        Extract code that defines required variables from a code block.
        
        This method extracts only the variable definition statements (assignments)
        that define variables in required_variables, while avoiding code that
        might fail (e.g., inside try/except blocks that failed).
        
        Args:
            code: Code string to analyze
            required_variables: Set of variable names that need to be defined
            
        Returns:
            Code string containing variable definitions, or None if no definitions found
        """
        if not required_variables:
            return None
        
        try:
            tree = ast.parse(code)
            lines = code.split('\n')
            extracted_lines = []
            extracted_vars = set()
            
            # Walk through AST to find assignments that define required variables
            # We'll extract assignments even from try/except blocks, but remove the try/except wrapper
            for node in ast.walk(tree):
                # Extract assignments (even from try/except blocks)
                if isinstance(node, ast.Assign):
                    # Check if this assignment defines any required variable
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if target.id in required_variables and target.id not in extracted_vars:
                                # Extract the assignment statement
                                start_line = node.lineno - 1
                                end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                                
                                # Get the code for this assignment
                                assignment_code = '\n'.join(lines[start_line:end_line])
                                extracted_lines.append(assignment_code)
                                extracted_vars.add(target.id)
                
                # Also extract import statements that might be needed
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.asname:
                            var_name = alias.asname
                        else:
                            var_name = alias.name.split('.')[0]
                        
                        if var_name in required_variables and var_name not in extracted_vars:
                            start_line = node.lineno - 1
                            end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                            import_code = '\n'.join(lines[start_line:end_line])
                            extracted_lines.append(import_code)
                            extracted_vars.add(var_name)
                
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.asname:
                            var_name = alias.asname
                        else:
                            var_name = alias.name
                        
                        if var_name in required_variables and var_name not in extracted_vars:
                            start_line = node.lineno - 1
                            end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                            import_code = '\n'.join(lines[start_line:end_line])
                            extracted_lines.append(import_code)
                            extracted_vars.add(var_name)
            
            # Also check try/except blocks for variable definitions
            # Extract assignments from try blocks (remove the try/except wrapper)
            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    for stmt in node.body:
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if isinstance(target, ast.Name):
                                    if target.id in required_variables and target.id not in extracted_vars:
                                        start_line = stmt.lineno - 1
                                        end_line = stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno
                                        assignment_code = '\n'.join(lines[start_line:end_line])
                                        extracted_lines.append(assignment_code)
                                        extracted_vars.add(target.id)
            
            if extracted_lines:
                # Add a comment explaining why this code is included
                header = f"# Variable definitions extracted from failed execution (required by successful code)"
                return f"{header}\n{chr(10).join(extracted_lines)}"
            
        except (SyntaxError, Exception) as e:
            # If parsing fails, try a simpler regex-based approach for assignments
            # This is a fallback for code that might have syntax errors
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
        
        return None

