"""
Workflow LLM Processor Module

Uses LLM to extract and structure workflow code from execution history.
"""

import re
import json
import sys
from typing import List, Dict, Optional
from datetime import datetime
from langchain_core.messages import HumanMessage

from biomni.workflow.utils.code_extractor import CodeExtractor


class WorkflowLLMProcessor:
    """Processes execution history using LLM to generate reusable workflow code."""
    
    # Pre-compiled regex patterns for performance
    _IMPORT_LINE_PATTERN = re.compile(r'^(import\s+\S+|from\s+\S+\s+import\s+[^\n]+)', re.MULTILINE)
    _IMPORT_ALIAS_PATTERN = re.compile(r'import\s+(\S+)\s+as\s+(\w+)')
    _FROM_IMPORT_PATTERN = re.compile(r'from\s+(\S+)\s+import')
    _ALIAS_USAGE_PATTERNS = {
        'pd': re.compile(r'\bpd\.'),
        'np': re.compile(r'\bnp\.'),
        'plt': re.compile(r'\bplt\.'),
        'sns': re.compile(r'\bsns\.'),
        'stats': re.compile(r'\bstats\.'),
        'sm': re.compile(r'\bsm\.'),
        'sklearn': re.compile(r'\bsklearn\.'),
    }
    
    # Constants
    MAX_RESULT_LENGTH = 500
    CODE_PREVIEW_LENGTH = 300
    WORKFLOW_CODE_PREVIEW_LENGTH = 3000
    PREVIOUS_ATTEMPT_PREVIEW_LENGTH = 2000
    
    def __init__(self, llm):
        """
        Initialize with LLM instance.
        
        Args:
            llm: LLM instance to use for processing
        """
        self.llm = llm
        self.code_extractor = CodeExtractor()
    
    def extract_workflow_code(
        self, 
        execution_history: List[Dict],
        preprocessed_data: Optional[Dict] = None,
        missing_outputs: Optional[List[str]] = None,
        retry_attempt: int = 0,
        previous_attempt_code: Optional[str] = None
    ) -> str:
        """
        Use LLM to extract and structure workflow code from execution history.
        
        Args:
            execution_history: List of execution entries
            preprocessed_data: Optional preprocessed data from WorkflowPreprocessor
            missing_outputs: Optional list of missing output files
            retry_attempt: Retry attempt number
            previous_attempt_code: Previous attempt code for retry
            
        Returns:
            Structured workflow code as a standalone Python script
        """
        # Input validation
        if not isinstance(execution_history, list):
            return ""
        
        if not isinstance(retry_attempt, int) or retry_attempt < 0:
            retry_attempt = 0
        
        # Filter to only successful executions
        successful_executions = [
            entry for entry in execution_history
            if isinstance(entry, dict) and entry.get("success", False)
        ]
        
        if not successful_executions:
            return ""
        
        # Prepare execution history for LLM (always use output file grouping for better organization)
        if preprocessed_data:
            # Use output file grouped summary for better organization
            execution_summary = self._prepare_execution_summary_with_output_grouping(
                successful_executions,
                preprocessed_data
            )
        else:
            execution_summary = self._prepare_execution_summary(successful_executions)
        
        # Always use detailed LLM prompt (not simplified) for better quality control
        # Preprocessed data is provided as reference, but LLM makes the decisions
        prompt = self._create_detailed_extraction_prompt(
            execution_summary,
            preprocessed_data=preprocessed_data,
            filtered_executions=execution_history,
            missing_outputs=missing_outputs,
            retry_attempt=retry_attempt,
            previous_attempt_code=previous_attempt_code
        )
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            workflow_code = response.content.strip()
            
            # Clean up response (remove markdown code blocks if present)
            workflow_code = self._clean_llm_response(workflow_code)
            
            return workflow_code
        except Exception as e:
            print(f"Error in LLM workflow extraction: {e}")
            return ""
    
    def generate_standalone_script(
        self,
        code_blocks: List[str],
        metadata: Dict,
        workflow_name: Optional[str] = None
    ) -> str:
        """
        Generate standalone executable Python script.
        
        Args:
            code_blocks: List of code blocks to include
            metadata: Metadata dictionary
            workflow_name: Name of the workflow
            
        Returns:
            Complete standalone Python script
        """
        # Input validation
        if not isinstance(code_blocks, list):
            return ""
        
        if not isinstance(metadata, dict):
            metadata = {}
        
        # Extract imports from all code blocks (with validation)
        import_lists = []
        for code in code_blocks:
            if isinstance(code, str) and code.strip():
                try:
                    imports = self.code_extractor.extract_imports(code)
                    if isinstance(imports, list):
                        import_lists.append(imports)
                except Exception:
                    # Skip if extraction fails
                    continue
        
        all_imports = self.code_extractor.merge_imports(import_lists) if import_lists else []
        
        # Generate script header
        header = self._generate_header(metadata, workflow_name)
        
        # Combine code blocks
        main_code = "\n\n".join(code_blocks)
        
        # Generate main execution block
        main_block = self._generate_main_block()
        
        # Combine everything
        script = f"""{header}

{self._format_imports(all_imports)}

{main_code}

{main_block}
"""
        
        return script
    
    def extract_metadata(self, execution_history: List[Dict]) -> Dict:
        """
        Extract metadata from execution history.
        
        Args:
            execution_history: List of execution entries
            
        Returns:
            Metadata dictionary
        """
        # Input validation
        if not isinstance(execution_history, list):
            return {
                "generated_date": datetime.now().isoformat(),
                "input_formats": [],
                "output_formats": [],
                "tools_used": [],
                "libraries": [],
                "environment": {
                    "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    "required_packages": [],
                    "os": sys.platform
                },
                "description": "Workflow extracted from 0 execution(s)"
            }
        
        # Collect all imports
        all_imports = set()
        input_files = set()
        output_files = set()
        
        for entry in execution_history:
            if not isinstance(entry, dict):
                continue
            
            code = entry.get("code", "")
            if isinstance(code, str) and code.strip():
                try:
                    imports = self.code_extractor.extract_imports(code)
                    if isinstance(imports, list):
                        all_imports.update(imports)
                except Exception:
                    # Skip if extraction fails
                    pass
            
            # Safely get input/output files
            input_files_list = entry.get("input_files", [])
            if isinstance(input_files_list, list):
                input_files.update(f for f in input_files_list if isinstance(f, str))
            
            output_files_list = entry.get("output_files", [])
            if isinstance(output_files_list, list):
                output_files.update(f for f in output_files_list if isinstance(f, str))
        
        # Determine input/output formats
        input_formats = self._detect_file_formats(list(input_files))
        output_formats = self._detect_file_formats(list(output_files))
        
        # Extract tools/libraries from imports
        tools_used = self._extract_tools_from_imports(list(all_imports))
        
        # Get environment info
        environment = {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "required_packages": list(all_imports),
            "os": sys.platform
        }
        
        return {
            "generated_date": datetime.now().isoformat(),
            "input_formats": input_formats,
            "output_formats": output_formats,
            "tools_used": tools_used,
            "libraries": list(all_imports),
            "environment": environment,
            "description": f"Workflow extracted from {len(execution_history)} execution(s)"
        }
    
    def _analyze_import_usage(self, executions: List[Dict]) -> Dict[str, str]:
        """
        Analyze actual import usage patterns from execution history.
        
        Args:
            executions: List of execution dictionaries
            
        Returns:
            Dict mapping module names to their aliases (e.g., {'pandas': 'pd', 'numpy': 'np'})
        """
        # Input validation
        if not isinstance(executions, list):
            return {}
        
        import_patterns = {}
        
        # Common import aliases mapping
        common_aliases = {
            'pandas': 'pd',
            'numpy': 'np',
            'matplotlib.pyplot': 'plt',
            'seaborn': 'sns',
            'scipy': 'scipy',
            'scipy.stats': 'stats',
            'statsmodels': 'sm',
            'sklearn': 'sklearn',
            'os': 'os',
            'sys': 'sys',
            'json': 'json',
            'csv': 'csv',
            'gzip': 'gzip',
            'pathlib': 'Path',
        }
        
        for execution in executions:
            if not isinstance(execution, dict):
                continue
            
            code = execution.get("code", "")
            if not isinstance(code, str) or not code.strip():
                continue
            
            # Extract import statements using pre-compiled pattern
            import_lines = self._IMPORT_LINE_PATTERN.findall(code)
            
            for imp_line in import_lines:
                # Check for alias: import pandas as pd
                alias_match = self._IMPORT_ALIAS_PATTERN.search(imp_line)
                if alias_match:
                    module = alias_match.group(1)
                    alias = alias_match.group(2)
                    import_patterns[module] = alias
                else:
                    # Check for from import: from pandas import DataFrame
                    from_match = self._FROM_IMPORT_PATTERN.search(imp_line)
                    if from_match:
                        module = from_match.group(1)
                        # Check if code uses common alias pattern
                        if module in common_aliases:
                            alias = common_aliases[module]
                            # Verify alias is actually used in code using pre-compiled pattern
                            pattern = self._ALIAS_USAGE_PATTERNS.get(alias)
                            if pattern and pattern.search(code):
                                import_patterns[module] = alias
            
            # Also check actual usage patterns in code
            for module, expected_alias in common_aliases.items():
                if module not in import_patterns:
                    # Check if code uses the alias using pre-compiled pattern
                    pattern = self._ALIAS_USAGE_PATTERNS.get(expected_alias)
                    if pattern and pattern.search(code):
                        import_patterns[module] = expected_alias
        
        return import_patterns
    
    def _prepare_execution_summary(self, executions: List[Dict]) -> str:
        """
        Prepare execution history summary for LLM.
        
        Args:
            executions: List of execution dictionaries
            
        Returns:
            Summary string for LLM
        """
        # Input validation
        if not isinstance(executions, list):
            return ""
        
        summary_parts = []
        
        # Analyze import usage patterns
        import_patterns = self._analyze_import_usage(executions)
        
        if import_patterns:
            import_info = "IMPORT USAGE PATTERNS DETECTED:\n"
            for module, alias in sorted(import_patterns.items()):
                import_info += f"- {module} is used as '{alias}' (e.g., {alias}.function_name)\n"
            summary_parts.append(import_info)
            summary_parts.append("")
        
        # Collect all output files for summary
        all_output_files = set()
        for execution in executions:
            output_files = execution.get("output_files", [])
            for output_file in output_files:
                # Extract just the filename for clarity
                from pathlib import Path
                file_name = Path(output_file).name
                all_output_files.add(file_name)
        
        for idx, execution in enumerate(executions, 1):
            if not isinstance(execution, dict):
                continue
            
            code = execution.get("code", "")
            if not isinstance(code, str):
                code = ""
            
            result = execution.get("result", "")
            if not isinstance(result, str):
                result = ""
            
            input_files = execution.get("input_files", [])
            if not isinstance(input_files, list):
                input_files = []
            
            output_files = execution.get("output_files", [])
            if not isinstance(output_files, list):
                output_files = []
            
            summary_parts.append(f"=== Execution {idx} ===")
            summary_parts.append(f"Code:\n{code}")
            
            if input_files:
                # Filter to only string file paths
                valid_input_files = [f for f in input_files if isinstance(f, str)]
                if valid_input_files:
                    summary_parts.append(f"Input files: {', '.join(valid_input_files)}")
            
            if output_files:
                # Filter to only string file paths
                valid_output_files = [f for f in output_files if isinstance(f, str)]
                if valid_output_files:
                    summary_parts.append(f"Output files: {', '.join(valid_output_files)}")
            
            # Include result if it's short
            if result and len(result) < self.MAX_RESULT_LENGTH:
                summary_parts.append(f"Result: {result[:self.MAX_RESULT_LENGTH]}")
            
            summary_parts.append("")
        
        # Add required output files section at the end
        if all_output_files:
            summary_parts.append("\n" + "="*60)
            summary_parts.append("REQUIRED OUTPUT FILES:")
            summary_parts.append("The workflow MUST generate ALL of the following output files:")
            for output_file in sorted(all_output_files):
                summary_parts.append(f"  - {output_file}")
            summary_parts.append("\nCRITICAL: All code blocks that generate these output files MUST be included.")
            summary_parts.append("If a code block generates an output file, it MUST be part of the workflow,")
            summary_parts.append("even if it is in a try/except block or uses error handling.")
            summary_parts.append("="*60)
        
        return "\n".join(summary_parts)
    
    def _prepare_execution_summary_with_output_grouping(
        self,
        executions: List[Dict],
        preprocessed_data: Dict
    ) -> str:
        """
        Prepare execution summary grouped by output files.
        
        This helps LLM understand which code blocks generate which output files.
        
        Args:
            executions: List of execution dictionaries
            preprocessed_data: Preprocessed data dictionary
            
        Returns:
            Summary string for LLM
        """
        # Input validation
        if not isinstance(executions, list):
            return ""
        
        if not isinstance(preprocessed_data, dict):
            preprocessed_data = {}
        
        summary_parts = []
        
        # Analyze import usage patterns
        import_patterns = self._analyze_import_usage(executions)
        
        if import_patterns:
            import_info = "IMPORT USAGE PATTERNS DETECTED:\n"
            for module, alias in sorted(import_patterns.items()):
                import_info += f"- {module} is used as '{alias}' (e.g., {alias}.function_name)\n"
            summary_parts.append(import_info)
            summary_parts.append("")
        
        # Get output file mapping
        output_file_mapping = preprocessed_data.get("output_file_mapping", {})
        if not isinstance(output_file_mapping, dict):
            output_file_mapping = {}
        
        # Group executions by output files
        output_file_executions = {}
        for output_file, exec_indices in output_file_mapping.items():
            if not isinstance(exec_indices, list):
                continue
            
            for exec_idx in exec_indices:
                # Validate exec_idx: must be positive and within bounds
                if not isinstance(exec_idx, int) or exec_idx < 1:
                    continue
                
                if exec_idx <= len(executions):
                    exec_entry = executions[exec_idx - 1]
                    if isinstance(exec_entry, dict):
                        if output_file not in output_file_executions:
                            output_file_executions[output_file] = []
                        output_file_executions[output_file].append((exec_idx, exec_entry))
        
        # Executions without output files
        executions_with_outputs = set()
        for exec_list in output_file_executions.values():
            for exec_idx, _ in exec_list:
                # Convert to 0-based index, ensure it's valid
                idx_0_based = exec_idx - 1
                if 0 <= idx_0_based < len(executions):
                    executions_with_outputs.add(idx_0_based)
        
        # Add output file grouped sections
        if output_file_executions:
            summary_parts.append("="*80)
            summary_parts.append("CODE BLOCKS GROUPED BY OUTPUT FILES")
            summary_parts.append("="*80)
            summary_parts.append("")
            
            for output_file in sorted(output_file_executions.keys()):
                exec_list = output_file_executions[output_file]
                summary_parts.append(f"OUTPUT FILE: {output_file}")
                summary_parts.append(f"Generated by execution(s): {[idx for idx, _ in exec_list]}")
                summary_parts.append("")
                
                for exec_idx, exec_entry in exec_list:
                    if not isinstance(exec_entry, dict):
                        continue
                    
                    code = exec_entry.get("code", "")
                    if not isinstance(code, str):
                        code = ""
                    
                    input_files = exec_entry.get("input_files", [])
                    if not isinstance(input_files, list):
                        input_files = []
                    
                    output_files = exec_entry.get("output_files", [])
                    if not isinstance(output_files, list):
                        output_files = []
                    
                    summary_parts.append(f"  === Execution {exec_idx} (generates {output_file}) ===")
                    summary_parts.append(f"  Code:")
                    # Indent code for readability (optimized: use list comprehension)
                    code_lines = code.split('\n')
                    indented_lines = [f"  {line}" for line in code_lines]
                    summary_parts.extend(indented_lines)
                    
                    if input_files:
                        valid_input_files = [f for f in input_files if isinstance(f, str)]
                        if valid_input_files:
                            summary_parts.append(f"  Input files: {', '.join(valid_input_files)}")
                    summary_parts.append("")
            
            summary_parts.append("="*80)
            summary_parts.append("")
        
        # Add executions without output files (if any)
        executions_without_outputs = [
            (idx + 1, exec_entry) for idx, exec_entry in enumerate(executions)
            if idx not in executions_with_outputs
        ]
        
        if executions_without_outputs:
            summary_parts.append("="*80)
            summary_parts.append("ADDITIONAL CODE BLOCKS (no direct output files)")
            summary_parts.append("="*80)
            summary_parts.append("")
            
            for exec_idx, exec_entry in executions_without_outputs:
                if not isinstance(exec_entry, dict):
                    continue
                
                code = exec_entry.get("code", "")
                if not isinstance(code, str):
                    code = ""
                
                summary_parts.append(f"=== Execution {exec_idx} ===")
                summary_parts.append(f"Code:\n{code}")
                summary_parts.append("")
        
        # Add required output files section
        all_output_files = set(output_file_mapping.keys())
        if all_output_files:
            summary_parts.append("\n" + "="*60)
            summary_parts.append("REQUIRED OUTPUT FILES:")
            summary_parts.append("The workflow MUST generate ALL of the following output files:")
            for output_file in sorted(all_output_files):
                summary_parts.append(f"  - {output_file}")
            summary_parts.append("\nCRITICAL: All code blocks that generate these output files MUST be included.")
            summary_parts.append("If a code block generates an output file, it MUST be part of the workflow,")
            summary_parts.append("even if it is in a try/except block or uses error handling.")
            summary_parts.append("="*60)
        
        return "\n".join(summary_parts)
    
    def _create_extraction_prompt(self, execution_summary: str) -> str:
        """Create LLM prompt for workflow extraction."""
        return f"""You are a code analysis and refactoring assistant. Your task is to extract and structure 
reusable workflow code from a series of executed code blocks.

EXECUTED CODE BLOCKS:
{execution_summary}

TASK:
1. Identify code blocks that represent actual data processing (not exploration or debugging)
2. Extract reusable functions/classes
3. Parameterize hardcoded paths and values (convert file paths to function parameters)
4. Structure as a standalone executable Python script
5. Ensure the script can be run independently with command-line arguments

CRITICAL IMPORT REQUIREMENTS:
- ALL imports MUST use the EXACT aliases shown in "IMPORT USAGE PATTERNS DETECTED" above
- If the code uses `pd.read_csv()`, you MUST write `import pandas as pd` (NOT `import pandas`)
- If the code uses `np.array()`, you MUST write `import numpy as np` (NOT `import numpy`)
- If the code uses `plt.figure()`, you MUST write `import matplotlib.pyplot as plt` (NOT `import matplotlib.pyplot`)
- If the code uses `sns.scatterplot()`, you MUST write `import seaborn as sns` (NOT `import seaborn`)
- If the code uses `stats.ttest_ind()`, you MUST write `from scipy import stats` (NOT `import scipy`)
- ALWAYS check the actual code usage patterns and match the imports accordingly
- Standard library imports (os, sys, json, etc.) can be without aliases unless specifically used with alias
- NEVER use `import pandas` if code uses `pd.` - ALWAYS use `import pandas as pd`
- NEVER use `import numpy` if code uses `np.` - ALWAYS use `import numpy as np`
- NEVER use `import matplotlib.pyplot` if code uses `plt.` - ALWAYS use `import matplotlib.pyplot as plt`
- NEVER use `import seaborn` if code uses `sns.` - ALWAYS use `import seaborn as sns`

OUTPUT FORMAT:
- Complete standalone Python script with:
  - All necessary imports at the top with CORRECT aliases matching code usage
  - Function/class definitions
  - Main execution block (if __name__ == "__main__":) that accepts command-line arguments
  - Proper error handling
  - Clear docstrings

REQUIREMENTS:
- The script must be executable independently
- File paths should be parameterized (use sys.argv or argparse)
- Include all necessary imports with CORRECT aliases
- Remove any exploration/debugging code
- Keep only data processing logic
- Ensure the script produces the same output files when given the same input files
- DOUBLE-CHECK that all import aliases match their usage in the code

CRITICAL OUTPUT FILE REQUIREMENTS:
- The workflow MUST generate ALL output files listed in "REQUIRED OUTPUT FILES" section above
- If a code block generates an output file (e.g., gsea_results.csv, gsea_plot.png, volcano_plot.png), 
  that code block MUST be included in the workflow
- Do NOT exclude code blocks that generate output files, even if they are in try/except blocks
- Do NOT exclude code blocks that generate output files, even if they use error handling
- Ensure all output files are generated when the workflow is executed
- Before finalizing the workflow, verify that all required output files have corresponding code

EXCLUDE:
- Data exploration code (head(), describe(), info(), etc.) - UNLESS it generates output files
- Failed executions
- Debugging/test code - UNLESS it generates output files
- Visualization code (unless integral to processing OR generates output files)
- Print statements for debugging

OUTPUT FILE VALIDATION CHECKLIST:
1. ✓ All output files listed in "REQUIRED OUTPUT FILES" have corresponding code in the workflow
2. ✓ Each output file (e.g., .csv, .png, .json) is generated by at least one code block
3. ✓ Code blocks that generate output files are included, even if in try/except blocks
4. ✓ The workflow will produce all expected output files when executed

VALIDATION CHECKLIST BEFORE OUTPUT:
1. ✓ All imports have correct aliases matching code usage
2. ✓ If code uses `pd.`, import is `import pandas as pd`
3. ✓ If code uses `np.`, import is `import numpy as np`
4. ✓ If code uses `plt.`, import is `import matplotlib.pyplot as plt`
5. ✓ If code uses `sns.`, import is `import seaborn as sns`
6. ✓ All functions/variables used in code are properly imported

CRITICAL: Output ONLY the Python code. Do NOT include any explanatory text before or after the code.
Wrap the code in markdown code blocks (```python ... ```) if needed, but ensure the code itself is valid Python.
Start directly with imports or function definitions. Do not include sentences like "Here is the code:" or similar explanations."""
    
    def _create_detailed_extraction_prompt(
        self,
        execution_summary: str,
        preprocessed_data: Optional[Dict] = None,
        filtered_executions: Optional[List[Dict]] = None,
        missing_outputs: Optional[List[str]] = None,
        retry_attempt: int = 0,
        previous_attempt_code: Optional[str] = None
    ) -> str:
        """
        Create detailed LLM prompt for workflow extraction.
        
        Uses LLM for most decisions while providing preprocessed data as reference.
        This gives LLM more context and control for better quality.
        """
        # Add retry-specific message if this is a retry
        retry_message = ""
        if retry_attempt > 0 and missing_outputs:
            # Build comprehensive retry message with previous attempt context
            retry_parts = [
                "=" * 80,
                f"⚠️  RETRY ATTEMPT {retry_attempt + 1} - CRITICAL MISSING OUTPUT FILES ⚠️",
                "=" * 80,
                "",
                f"The previous attempt(s) FAILED to include code for the following output files:",
                ""
            ]
            
            # List all missing files with emphasis
            for i, missing_file in enumerate(missing_outputs, 1):
                retry_parts.append(f"  {i}. {missing_file} ⚠️ MISSING - MUST BE INCLUDED")
            
            retry_parts.extend([
                "",
                "CRITICAL REQUIREMENTS:",
                "1. YOU MUST INCLUDE CODE TO GENERATE ALL OF THESE FILES",
                "2. Refer to the 'CODE BLOCKS GROUPED BY OUTPUT FILES' section below",
                "3. Find the exact code blocks that generate these files",
                "4. DO NOT skip these files again - they are REQUIRED",
                ""
            ])
            
            # Include previous attempt code if available (for comparison)
            if previous_attempt_code and isinstance(previous_attempt_code, str):
                code_preview = previous_attempt_code[:self.PREVIOUS_ATTEMPT_PREVIEW_LENGTH]
                code_truncated = len(previous_attempt_code) > self.PREVIOUS_ATTEMPT_PREVIEW_LENGTH
                retry_parts.extend([
                    "=" * 80,
                    "PREVIOUS ATTEMPT CODE (REFERENCE ONLY - DO NOT COPY AS-IS)",
                    "=" * 80,
                    "The code below was generated in the previous attempt but FAILED to include",
                    "the required output files. Use this as reference to understand what was",
                    "generated, but you MUST add the missing output file generation code.",
                    "",
                    "```python",
                    code_preview + ("..." if code_truncated else ""),
                    "```",
                    "",
                    "ANALYSIS:",
                    f"- The code above is missing {len(missing_outputs)} required output file(s)",
                    "- You MUST add code to generate ALL missing files listed above",
                    "- Look for the code blocks in EXECUTED CODE BLOCKS that generate these files",
                    ""
                ])
            
            retry_parts.extend([
                "=" * 80,
                ""
            ])
            
            retry_message = "\n".join(retry_parts)
        
        # Extract output files and requirements from execution summary or preprocessed data
        output_files = []
        output_files_section = ""
        min_lines = 500  # Default minimum
        min_functions = 3  # Default minimum
        
        if preprocessed_data:
            output_file_mapping = preprocessed_data.get("output_file_mapping", {})
            output_files = list(output_file_mapping.keys())
            
            # Create detailed output file section
            for output_file in sorted(output_files):
                exec_indices = output_file_mapping[output_file]
                output_files_section += f"\n  - {output_file} (generated by execution(s): {exec_indices})"
                # Add code preview for this output file
                if filtered_executions:
                    code_previews = []
                    for exec_idx in exec_indices:
                        # Validate exec_idx: must be positive and within bounds
                        if isinstance(exec_idx, int) and 0 < exec_idx <= len(filtered_executions):
                            exec_entry = filtered_executions[exec_idx - 1]
                            if isinstance(exec_entry, dict):
                                code = exec_entry.get("code", "")
                                if isinstance(code, str):
                                    # Get first N chars of code for better context
                                    code_preview = code[:self.CODE_PREVIEW_LENGTH].replace('\n', ' ').strip()
                                    if code_preview:
                                        code_previews.append(f"    Execution {exec_idx} code preview: {code_preview}...")
                    if code_previews:
                        output_files_section += "\n" + "\n".join(code_previews)
            
            # Estimate minimum code length based on output files
            min_lines = max(500, len(output_files) * 60)  # At least 60 lines per output file
            min_functions = max(3, len(output_files) // 2)  # At least 3 functions, more if many outputs
        
        # Format preprocessed data as reference (if available) - LLM makes final decisions
        preprocessed_section = ""
        if preprocessed_data:
            imports_text = "\n".join([f"  {imp}" for imp in preprocessed_data.get("imports", [])])
            hardcoded_paths = preprocessed_data.get("hardcoded_paths", [])
            paths_text = "\n".join([
                f"  - {p['path']} (in execution {p.get('execution_index', '?')})"
                for p in hardcoded_paths[:10]
            ])
            if len(hardcoded_paths) > 10:
                paths_text += f"\n  ... and {len(hardcoded_paths) - 10} more"
            
            preprocessed_section = f"""
================================================================================
PREPROCESSED DATA (REFERENCE ONLY - YOU ANALYZE AND DECIDE)
================================================================================
The following information was extracted by rule-based preprocessing, but YOU should
analyze the code blocks yourself and make your own decisions:

- Imports detected: {len(preprocessed_data.get('imports', []))} imports
  {imports_text}
- Hardcoded paths detected: {len(hardcoded_paths)} paths (need parameterization)
  {paths_text}
- Functions extracted: {len(preprocessed_data.get('functions', []))} functions

IMPORTANT: This is REFERENCE data only. You must:
1. Analyze the code blocks yourself to determine correct imports
2. Verify import aliases match actual code usage
3. Make your own decisions about code structure and organization
4. Ensure all output files are generated
"""
        
        return f"""You are an expert code analysis and refactoring assistant specializing in 
bioinformatics workflows. Your task is to extract and structure reusable workflow code 
from a series of executed code blocks into a complete, standalone Python script.

{retry_message}
================================================================================
🚨 CRITICAL: REQUIRED OUTPUT FILES (MUST BE GENERATED - HIGHEST PRIORITY) 🚨
================================================================================
⚠️  WARNING: THE PREVIOUS ATTEMPT FAILED TO INCLUDE CODE FOR ALL OUTPUT FILES ⚠️

The workflow MUST generate ALL {len(output_files) if output_files else 'expected'} output files listed below.
THIS IS THE MOST IMPORTANT REQUIREMENT. FAILURE TO GENERATE ANY OF THESE FILES WILL CAUSE THE WORKFLOW TO FAIL.

REQUIRED OUTPUT FILES (MUST BE GENERATED):
{output_files_section if output_files_section else "  (See EXECUTED CODE BLOCKS section for output files)"}

MANDATORY VALIDATION CHECKLIST (MUST COMPLETE BEFORE OUTPUTTING):
1. □ Count the number of output files in the list above: {len(output_files) if output_files else 'N/A'}
2. □ For EACH output file, verify that your workflow contains code that generates it
3. □ Count the number of output file generation code blocks in your workflow
4. □ These two counts MUST BE EQUAL - if not, you are missing code blocks
5. □ Verify each output file has a corresponding .to_csv(), .savefig(), or similar call
6. □ Verify all output file generation code is reachable from main() function
7. □ Verify no output files are skipped or excluded

⚠️  IF YOU SKIP ANY OUTPUT FILE, THE WORKFLOW WILL BE INCOMPLETE AND USELESS ⚠️
⚠️  INCLUDE ALL CODE BLOCKS THAT GENERATE OUTPUT FILES, EVEN IF THEY ARE IN try/except BLOCKS ⚠️

{preprocessed_section}
================================================================================
EXECUTED CODE BLOCKS
================================================================================
{execution_summary}

================================================================================
YOUR TASK (ANALYZE AND DECIDE)
================================================================================
You need to analyze the code blocks above and make the following decisions:

1. **Code Selection & Filtering**
   - Identify which code blocks represent actual data processing (not exploration/debugging)
   - Include ALL code blocks that generate output files (even if in try/except blocks)
   - Exclude: head(), describe(), info() calls (unless they generate output files)
   - Exclude: failed executions (unless they generate output files)
   - Exclude: debugging/test code (unless they generate output files)

2. **Import Analysis**
   - Analyze the code to determine which imports are needed
   - Check import usage patterns (e.g., `pd.read_csv()` → `import pandas as pd`)
   - Ensure ALL imports use correct aliases matching their usage
   - Common patterns:
     * `pd.` → `import pandas as pd`
     * `np.` → `import numpy as np`
     * `plt.` → `import matplotlib.pyplot as plt`
     * `sns.` → `import seaborn as sns`
     * `stats.` → `from scipy import stats`
   - Include all necessary imports, even if not in preprocessed data

3. **Function Extraction & Structure**
   - Extract reusable functions from code blocks
   - Group related code into logical functions
   - Create at least {min_functions} functions (one per major analysis step)
   - Functions should be well-documented with docstrings
   - Determine function call order based on dependencies

4. **Path Parameterization**
   - Identify hardcoded file paths in the code
   - Convert them to command-line arguments using argparse
   - Use --input for input files, --output_dir for output directory
   - Make paths relative to output directory or configurable

5. **Output File Generation**
   - Ensure ALL required output files are generated
   - Each output file must have corresponding code in the workflow
   - Verify output file generation code is included and callable
   - Check that file paths are properly parameterized

6. **Error Handling**
   - Add appropriate error handling
   - Handle file not found errors
   - Handle missing dependencies gracefully
   - Provide clear error messages

================================================================================
REQUIREMENTS
================================================================================
- The script must be executable independently with argparse
- Structure: imports → function definitions → main() → if __name__ == "__main__"
- Use argparse for command-line arguments (--input, --output_dir, etc.)
- **Minimum code length: ~{min_lines} lines** (to ensure completeness)
- **Minimum functions: {min_functions} functions** (for proper structure)
- All imports must use correct aliases matching code usage
- All output files must be generated when the script runs
- Code must be complete, valid Python (no syntax errors)
- Include proper docstrings for functions

================================================================================
🚨 CRITICAL OUTPUT FILE REQUIREMENTS (READ THIS CAREFULLY) 🚨
================================================================================
THIS IS THE MOST IMPORTANT SECTION. READ IT MULTIPLE TIMES.

1. **MANDATORY INCLUSION RULE**: 
   - If a code block generates ANY output file (even one), it MUST be included in the workflow
   - NO EXCEPTIONS - even if the code is in a try/except block
   - NO EXCEPTIONS - even if it uses error handling
   - NO EXCEPTIONS - even if it appears "optional" or "debugging"
   - NO EXCEPTIONS - even if it's a visualization that seems "secondary"

2. **OUTPUT FILE GENERATION VERIFICATION**:
   - For EACH output file in the REQUIRED OUTPUT FILES list:
     * Find the code block that generates it (check "CODE BLOCKS GROUPED BY OUTPUT FILES" section)
     * Include that ENTIRE code block in your workflow
     * Ensure the output file path/name matches exactly
     * Verify the code is callable from main() function

3. **BEFORE OUTPUTTING - FINAL CHECK**:
   Step 1: Count required output files: {len(output_files) if output_files else 'N/A'}
   Step 2: Count output file generation code blocks in your workflow: ___
   Step 3: These two numbers MUST BE EQUAL
   Step 4: If not equal, you are missing code blocks - GO BACK AND ADD THEM
   Step 5: For each output file, verify it has a generation call (.to_csv, .savefig, etc.)

4. **COMMON MISTAKES TO AVOID**:
   ❌ DO NOT skip code blocks just because they're in try/except
   ❌ DO NOT skip code blocks just because they have error handling
   ❌ DO NOT skip visualization code that generates .png files
   ❌ DO NOT assume some output files are "optional"
   ❌ DO NOT exclude code blocks that generate multiple output files
   ✅ DO include ALL code blocks that generate ANY output file
   ✅ DO verify each output file has corresponding generation code
   ✅ DO ensure all output file generation code is in the workflow

================================================================================
OUTPUT FORMAT
================================================================================
- Complete standalone Python script
- Start with imports (analyze code to determine correct imports with aliases)
- Then function definitions (at least {min_functions} functions)
- Then main() function with argparse
- Finally: if __name__ == "__main__": main()
- Minimum length: ~{min_lines} lines
- Must be valid, executable Python code

================================================================================
🚨 FINAL VALIDATION BEFORE OUTPUTTING (MANDATORY) 🚨
================================================================================
YOU MUST COMPLETE ALL OF THESE STEPS BEFORE OUTPUTTING YOUR CODE:

STEP 1 - OUTPUT FILE VERIFICATION (MOST IMPORTANT):
  1.1. Count output files in REQUIRED OUTPUT FILES section: {len(output_files) if output_files else 'N/A'}
  1.2. List each output file and verify your workflow has code to generate it:
       {chr(10).join([f"      - {f}: {'✓' if f else '✗'} Code found" for f in (output_files[:10] if output_files else [])])}
       {'      ... and more' if output_files and len(output_files) > 10 else ''}
  1.3. Count output file generation code blocks in your workflow: ___
  1.4. These two counts MUST MATCH - if not, you are missing code blocks
  1.5. For each output file, verify it has a generation call in your workflow

STEP 2 - CODE QUALITY VERIFICATION:
  2.1. ✓ Verify code length is at least ~{min_lines} lines
  2.2. ✓ Verify at least {min_functions} functions are defined
  2.3. ✓ Verify all imports use correct aliases matching code usage
  2.4. ✓ Verify no syntax errors
  2.5. ✓ Verify all required output files will be generated

⚠️  DO NOT OUTPUT UNTIL STEP 1 IS COMPLETE AND VERIFIED ⚠️

CRITICAL: Output ONLY the Python code. Do NOT include any explanatory text.
Start directly with imports (analyze the code blocks to determine correct imports).
The code must be complete, valid Python that generates ALL required output files."""
    
    def _clean_llm_response(self, response: str) -> str:
        """
        Clean LLM response to extract only Python code.
        
        Handles various formats:
        - Markdown code blocks (```python ... ```)
        - Code blocks without language (``` ... ```)
        - Plain code with surrounding text
        
        Args:
            response: LLM response string
            
        Returns:
            Cleaned Python code string
        """
        # Input validation
        if not isinstance(response, str):
            return ""
        
        # First, try to extract code from markdown code blocks
        # Pattern: ```python\n...\n``` or ```\n...\n```
        code_block_pattern = re.compile(r'```(?:python)?\n(.*?)```', re.DOTALL)
        matches = code_block_pattern.findall(response)
        
        if matches:
            # Use the longest match (most likely the actual code)
            code = max(matches, key=len).strip()
            return code
        
        # If no code blocks found, try to find Python code patterns
        # Look for import statements or def/class keywords
        lines = response.split('\n')
        code_start = None
        code_end = None
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Python code typically starts with import, def, class, or comment/docstring
            if stripped.startswith(('import ', 'from ', 'def ', 'class ', '#', '"""', "'''")):
                if code_start is None:
                    code_start = i
                code_end = i + 1
            elif code_start is not None:
                # Continue collecting code lines
                if stripped or line.startswith(' ') or line.startswith('\t'):
                    code_end = i + 1
                else:
                    # Empty line might be end of code block
                    break
        
        if code_start is not None and code_end is not None:
            code = '\n'.join(lines[code_start:code_end]).strip()
            return code
        
        # Fallback: return response as-is but remove obvious non-code lines
        # Remove lines that don't look like Python code
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip lines that are clearly not code
            if not stripped:
                continue
            # Skip lines that are explanations (start with common explanation words)
            if stripped.lower().startswith(('here is', 'this is', 'the following', 'below is', 'above is')):
                continue
            # Skip lines that are too long and don't contain code patterns
            if len(stripped) > 200 and not any(keyword in stripped.lower() for keyword in ['import', 'def', 'class', '=', '(', ')', '[', ']']):
                continue
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    
    def _format_imports(self, imports: List[str]) -> str:
        """Format import statements."""
        if not imports:
            return ""
        
        return "\n".join(imports)
    
    def _generate_header(self, metadata: Dict, workflow_name: Optional[str] = None) -> str:
        """Generate script header with metadata."""
        name = workflow_name or "Workflow"
        date = metadata.get("generated_date", datetime.now().isoformat())
        description = metadata.get("description", "")
        
        input_formats = ", ".join(metadata.get("input_formats", []))
        output_formats = ", ".join(metadata.get("output_formats", []))
        tools = ", ".join(metadata.get("tools_used", []))
        
        env = metadata.get("environment", {})
        python_version = env.get("python_version", "Unknown")
        
        return f'''"""
Workflow: {name}
Generated: {date}
Description: {description}

Metadata:
- Input formats: {input_formats or "N/A"}
- Output formats: {output_formats or "N/A"}
- Tools/Libraries: {tools or "N/A"}
- Environment: Python {python_version}, {env.get("os", "Unknown")}
"""'''
    
    def _generate_main_block(self) -> str:
        """Generate main execution block."""
        return '''if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python workflow.py <input_file1> [input_file2] ... [output_file]")
        sys.exit(1)
    
    # Get input files (all but last argument)
    input_files = sys.argv[1:-1] if len(sys.argv) > 2 else [sys.argv[1]]
    
    # Get output file (last argument, optional)
    output_file = sys.argv[-1] if len(sys.argv) > 2 and sys.argv[-1].endswith(('.csv', '.xlsx', '.json', '.txt')) else None
    
    # Execute workflow
    try:
        process_data(input_files, output_file)
        print("Workflow completed successfully.")
    except Exception as e:
        print(f"Error executing workflow: {e}")
        sys.exit(1)'''
    
    def _detect_file_formats(self, file_paths: List[str]) -> List[str]:
        """
        Detect file formats from file paths.
        
        Args:
            file_paths: List of file path strings
            
        Returns:
            List of detected format names
        """
        # Input validation
        if not isinstance(file_paths, list):
            return []
        
        formats = set()
        
        for file_path in file_paths:
            if not isinstance(file_path, str) or not file_path:
                continue
            
            # Extract extension safely
            if '.' in file_path:
                ext = file_path.split('.')[-1].upper()
            else:
                ext = None
            
            format_map = {
                'CSV': 'CSV',
                'TSV': 'TSV',
                'TXT': 'TXT',
                'XLSX': 'Excel',
                'XLS': 'Excel',
                'JSON': 'JSON',
                'PKL': 'Pickle',
                'PNG': 'PNG',
                'JPG': 'JPEG',
                'JPEG': 'JPEG',
                'PDF': 'PDF'
            }
            
            if ext and ext in format_map:
                formats.add(format_map[ext])
        
        return sorted(list(formats))
    
    def _extract_tools_from_imports(self, imports: List[str]) -> List[str]:
        """Extract tool/library names from import statements."""
        tools = set()
        
        for imp in imports:
            # Extract module name
            if imp.startswith('import '):
                module = imp.replace('import ', '').split()[0]
                tools.add(module)
            elif imp.startswith('from '):
                module = imp.replace('from ', '').split()[0]
                tools.add(module)
        
        return sorted(list(tools))
    
    def fix_workflow_code(
        self,
        workflow_code: str,
        error_message: str,
        attempt_number: int = 1
    ) -> str:
        """
        Use LLM to fix workflow code based on error message.
        
        Args:
            workflow_code: Current workflow code that failed
            error_message: Error message from execution or validation
            attempt_number: Current attempt number (1 or 2)
            
        Returns:
            Fixed workflow code
        """
        prompt = self._create_fix_prompt(workflow_code, error_message, attempt_number)
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            fixed_code = response.content.strip()
            
            # Clean up response (remove markdown code blocks if present)
            fixed_code = self._clean_llm_response(fixed_code)
            
            return fixed_code
        except Exception as e:
            print(f"Error in LLM workflow fixing: {e}")
            return workflow_code  # Return original code if fixing fails
    
    def _create_fix_prompt(self, workflow_code: str, error_message: str, attempt_number: int) -> str:
        """Create LLM prompt for fixing workflow code."""
        # Analyze import usage in the current code
        import_patterns = self._analyze_import_usage_from_code(workflow_code)
        
        import_guidance = ""
        if import_patterns:
            import_guidance = "\nDETECTED IMPORT USAGE IN CODE:\n"
            for module, alias in sorted(import_patterns.items()):
                import_guidance += f"- Code uses '{alias}.' → MUST have `import {module} as {alias}`\n"
            import_guidance += "\n"
        
        return f"""You are a Python code debugging assistant. A workflow script has failed with an error. 
Your task is to fix the code so it runs successfully.

CURRENT WORKFLOW CODE:
```python
{workflow_code}
```

ERROR MESSAGE:
{error_message}
{import_guidance}
TASK:
Fix the code to resolve the error. Common issues include:
1. Missing or incorrect import aliases - THIS IS THE MOST COMMON ERROR
2. Missing import statements
3. Incorrect function or variable names
4. Syntax errors
5. Missing dependencies

CRITICAL IMPORT FIXING RULES:
- Scan the ENTIRE code for module usage patterns (e.g., `pd.`, `np.`, `plt.`, `sns.`, `stats.`)
- For EVERY module usage, ensure the import statement uses the CORRECT alias:
  * If code contains `pd.read_csv()` or `pd.DataFrame()` → MUST have `import pandas as pd`
  * If code contains `np.array()` or `np.log10()` → MUST have `import numpy as np`
  * If code contains `plt.figure()` or `plt.savefig()` → MUST have `import matplotlib.pyplot as plt`
  * If code contains `sns.scatterplot()` or `sns.heatmap()` → MUST have `import seaborn as sns`
  * If code contains `stats.ttest_ind()` → MUST have `from scipy import stats` or `import scipy.stats as stats`
  * If code contains `multipletests()` → MUST have `from statsmodels.stats.multitest import multipletests`
- NEVER write `import pandas` if code uses `pd.` - ALWAYS write `import pandas as pd`
- NEVER write `import numpy` if code uses `np.` - ALWAYS write `import numpy as np`
- NEVER write `import matplotlib.pyplot` if code uses `plt.` - ALWAYS write `import matplotlib.pyplot as plt`
- NEVER write `import seaborn` if code uses `sns.` - ALWAYS write `import seaborn as sns`
- Check ALL function calls and variable references in the code
- If an error mentions "NameError: name 'pd' is not defined" → Add `import pandas as pd`
- If an error mentions "NameError: name 'np' is not defined" → Add `import numpy as np`
- If an error mentions "NameError: name 'plt' is not defined" → Add `import matplotlib.pyplot as plt`
- If an error mentions "NameError: name 'sns' is not defined" → Add `import seaborn as sns`

STEP-BY-STEP FIXING PROCESS:
1. Read the error message carefully
2. Identify which module/function is missing or incorrectly imported
3. Scan the code to find ALL usages of that module (e.g., search for `pd.`, `np.`, `plt.`, `sns.`)
4. Check the import section - does it have the correct alias?
5. If not, fix the import statement to match the usage
6. Repeat for all modules used in the code
7. Verify ALL imports are correct before outputting

OUTPUT FORMAT:
Output ONLY the complete fixed Python code. Do NOT include any explanatory text before or after the code.
Wrap the code in markdown code blocks (```python ... ```) if needed, but ensure the code itself is valid Python.
Start directly with imports or function definitions. Do not include sentences like "Here is the fixed code:" or similar explanations.

This is attempt {attempt_number} of 2. Make sure the fix is complete and correct. Double-check ALL imports match their usage."""
    
    def _analyze_import_usage_from_code(self, code: str) -> Dict[str, str]:
        """
        Analyze import usage patterns from code string.
        
        Args:
            code: Code string to analyze
            
        Returns:
            Dict mapping module names to their aliases
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return {}
        
        import_patterns = {}
        
        # Common alias patterns to check
        alias_patterns = {
            'pd': 'pandas',
            'np': 'numpy',
            'plt': 'matplotlib.pyplot',
            'sns': 'seaborn',
            'stats': 'scipy.stats',
            'sm': 'statsmodels',
            'sklearn': 'sklearn',
        }
        
        for alias, module in alias_patterns.items():
            # Check if alias is used in code using pre-compiled pattern
            pattern = self._ALIAS_USAGE_PATTERNS.get(alias)
            if pattern and pattern.search(code):
                import_patterns[module] = alias
        
        return import_patterns
    
    def generate_workflow_description(
        self,
        workflow_code: str,
        execution_history: List[Dict],
        preprocessed_data: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Generate a human-readable description of the workflow analysis.
        
        Args:
            workflow_code: Complete workflow code
            execution_history: List of execution entries
            preprocessed_data: Optional preprocessed data
            
        Returns:
            Workflow description as text, or None if failed
        """
        try:
            # Prepare summary of what was done
            analysis_summary = self._prepare_analysis_summary(workflow_code, execution_history)
            
            # Create prompt for description generation
            prompt = self._create_description_prompt(workflow_code, analysis_summary)
            
            # Get description from LLM
            response = self.llm.invoke([HumanMessage(content=prompt)])
            description = response.content.strip()
            
            # Clean up response (remove markdown code blocks if present)
            description = self._clean_description_response(description)
            
            return description
        except Exception as e:
            print(f"Error generating workflow description: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _prepare_analysis_summary(
        self, 
        workflow_code: str, 
        execution_history: List[Dict]
    ) -> str:
        """
        Prepare summary of analyses performed.
        
        Returns:
            Summary text of analyses
        """
        summary_parts = []
        
        # Extract function names and their purposes
        functions = re.findall(r'def\s+(\w+)\([^)]*\):', workflow_code)
        
        # Identify analysis types
        analysis_types = []
        
        # Check for common analysis patterns
        if 'PCA' in workflow_code or 'pca' in workflow_code.lower():
            analysis_types.append("PCA (Principal Component Analysis)")
        if 'DEG' in workflow_code or 'differential' in workflow_code.lower() or 'ttest' in workflow_code.lower():
            analysis_types.append("Differential Expression Analysis (DEG)")
        if 'gsea' in workflow_code.lower() or 'prerank' in workflow_code.lower():
            analysis_types.append("GSEA (Gene Set Enrichment Analysis)")
        if 'volcano' in workflow_code.lower():
            analysis_types.append("Volcano Plot")
        if 'heatmap' in workflow_code.lower() or 'clustermap' in workflow_code.lower():
            analysis_types.append("Heatmap Visualization")
        
        # Check for preprocessing steps
        preprocessing_steps = []
        if 'filter' in workflow_code.lower() or 'dropna' in workflow_code.lower():
            preprocessing_steps.append("Data filtering")
        if 'standardize' in workflow_code.lower() or 'StandardScaler' in workflow_code:
            preprocessing_steps.append("Data standardization")
        if 'classify' in workflow_code.lower() or 'metadata' in workflow_code.lower():
            preprocessing_steps.append("Sample classification/metadata creation")
        
        summary_parts.append(f"Functions identified: {', '.join(functions)}")
        if analysis_types:
            summary_parts.append(f"Analysis types: {', '.join(analysis_types)}")
        if preprocessing_steps:
            summary_parts.append(f"Preprocessing steps: {', '.join(preprocessing_steps)}")
        
        return "\n".join(summary_parts)
    
    def _create_description_prompt(
        self, 
        workflow_code: str, 
        analysis_summary: str
    ) -> str:
        """
        Create prompt for generating workflow description.
        
        Returns:
            Prompt string
        """
        # Limit workflow code length for prompt
        if not isinstance(workflow_code, str):
            workflow_code = str(workflow_code) if workflow_code is not None else ""
        
        code_preview = workflow_code[:self.WORKFLOW_CODE_PREVIEW_LENGTH]
        if len(workflow_code) > self.WORKFLOW_CODE_PREVIEW_LENGTH:
            code_preview += "\n... (code continues)"
        
        return f"""You are a bioinformatics analysis documentation expert. Your task is to create 
a clear, structured description of the data processing and analysis workflow.

WORKFLOW CODE:
```python
{code_preview}
```

ANALYSIS SUMMARY:
{analysis_summary}

TASK:
Create a structured description of the workflow that includes:

1. **Data Preprocessing**
   - What preprocessing steps were performed
   - Details of each preprocessing step (e.g., filtering criteria, normalization methods)

2. **Analysis Steps**
   - Each major analysis performed (e.g., PCA, DEG, GSEA)
   - Purpose of each analysis
   - Methods/techniques used (e.g., "T-test with Benjamini-Hochberg FDR correction", "limma", "DESeq2")
   - Key parameters (e.g., number of components for PCA, significance thresholds)

3. **Visualization**
   - What plots/figures are generated
   - Purpose of each visualization

OUTPUT FORMAT:
- Use numbered list format (1., 2., 3., etc.)
- Be specific about methods and techniques used
- Include key parameters and thresholds
- Use clear, concise language
- Focus on what was done, not how the code works

EXAMPLE FORMAT:
1. Data Preprocessing
   - Loaded RNA-seq count data from TSV file
   - Classified samples into Tumor and Normal groups based on TCGA barcode structure
   - Filtered data to include only Tumor and Normal samples (excluded 'Other' samples)

2. PCA Analysis
   - Purpose: Dimensionality reduction and visualization of sample relationships
   - Method: Selected top 5000 most variable genes, standardized data using StandardScaler, 
     performed PCA with 2 components
   - Output: PCA plot showing PC1 vs PC2 colored by sample type

3. Differential Expression Analysis (DEG)
   - Purpose: Identify genes differentially expressed between Tumor and Normal samples
   - Method: T-test (unequal variances) with Benjamini-Hochberg FDR correction
   - Filtering: Genes with mean expression > 1 in at least one group
   - Significance criteria: padj < 0.05 and |log2FoldChange| > 1
   - Output: CSV file with log2FoldChange, pvalue, and padj for each gene

4. Visualization
   - Volcano plot: Shows log2FoldChange vs -log10(adjusted p-value) with significant genes highlighted
   - Heatmap: Top 50 significant DEGs with hierarchical clustering

CRITICAL: Output ONLY the description text. Do NOT include markdown formatting, code blocks, or explanations.
Start directly with "1. Data Preprocessing" or similar numbered list."""
    
    def _clean_description_response(self, response: str) -> str:
        """
        Clean LLM response for description (remove markdown, code blocks, etc.).
        
        Args:
            response: LLM response string
            
        Returns:
            Cleaned description text
        """
        # Remove markdown code blocks if present
        response = re.sub(r'```[^\n]*\n', '', response)
        response = re.sub(r'```', '', response)
        
        # Remove common explanation prefixes
        lines = response.split('\n')
        cleaned_lines = []
        skip_until_number = True
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines at the beginning
            if not stripped and not cleaned_lines:
                continue
            
            # Start collecting from first numbered item
            if skip_until_number:
                if re.match(r'^\d+\.', stripped):
                    skip_until_number = False
                    cleaned_lines.append(line)
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()

