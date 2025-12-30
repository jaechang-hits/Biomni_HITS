"""
Workflow Postprocessor Module

Rule-based postprocessing after LLM processing.
Validates and fixes LLM-generated workflow code.
"""

import re
import ast
from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path

from biomni.workflow.utils.code_extractor import CodeExtractor


class WorkflowPostprocessor:
    """
    Postprocesses LLM-generated workflow code using rule-based methods.
    
    Validates imports, output files, and code structure, then applies
    automatic fixes where possible.
    """
    
    # Compiled regex patterns for performance
    _IMPORT_PATTERN = re.compile(r'^import\s+(\S+)', re.MULTILINE)
    _FROM_IMPORT_PATTERN = re.compile(r'^from\s+(\S+)\s+import', re.MULTILINE)
    _IMPORT_WITH_ALIAS_PATTERN = re.compile(r'^import\s+(\S+)\s+as\s+(\S+)', re.MULTILINE)
    
    # Patterns for detecting module usage (not in strings/comments)
    _USAGE_PATTERNS = {
        'argparse': re.compile(r'\bargparse\.'),
        'os': re.compile(r'\bos\.'),
        'sys': re.compile(r'\bsys\.'),
        'pd': re.compile(r'\bpd\.'),
        'np': re.compile(r'\bnp\.'),
        'plt': re.compile(r'\bplt\.'),
        'sns': re.compile(r'\bsns\.'),
        'stats': re.compile(r'\bstats\.'),
    }
    
    # Import check patterns (compiled)
    _IMPORT_CHECK_PATTERNS = {
        'argparse': re.compile(r'^import\s+argparse\b', re.MULTILINE),
        'os': re.compile(r'^import\s+os\b', re.MULTILINE),
        'sys': re.compile(r'^import\s+sys\b', re.MULTILINE),
        'pandas as pd': re.compile(r'^import\s+pandas\s+as\s+pd\b', re.MULTILINE),
        'numpy as np': re.compile(r'^import\s+numpy\s+as\s+np\b', re.MULTILINE),
        'matplotlib.pyplot as plt': re.compile(r'^import\s+matplotlib\.pyplot\s+as\s+plt\b', re.MULTILINE),
        'seaborn as sns': re.compile(r'^import\s+seaborn\s+as\s+sns\b', re.MULTILINE),
        'scipy import stats': re.compile(r'^from\s+scipy\s+import\s+stats\b', re.MULTILINE),
    }
    
    # Alias fix patterns (compiled)
    _ALIAS_FIX_PATTERNS = [
        (re.compile(r'^import\s+pandas\s*$', re.MULTILINE), 'import pandas as pd', r'\bpd\.'),
        (re.compile(r'^import\s+numpy\s*$', re.MULTILINE), 'import numpy as np', r'\bnp\.'),
        (re.compile(r'^import\s+matplotlib\.pyplot\s*$', re.MULTILINE), 'import matplotlib.pyplot as plt', r'\bplt\.'),
        (re.compile(r'^import\s+seaborn\s*$', re.MULTILINE), 'import seaborn as sns', r'\bsns\.'),
    ]
    
    def __init__(self):
        """Initialize the postprocessor."""
        self.code_extractor = CodeExtractor()
    
    def postprocess(
        self, 
        workflow_code: str, 
        preprocessed_data: Dict
    ) -> Tuple[str, Dict]:
        """
        Postprocess LLM-generated workflow code.
        
        Args:
            workflow_code: LLM-generated workflow code
            preprocessed_data: Preprocessed data from WorkflowPreprocessor
            
        Returns:
            Tuple of (fixed_workflow_code, validation_report)
        """
        # Input validation
        if not isinstance(workflow_code, str):
            workflow_code = str(workflow_code) if workflow_code is not None else ""
        
        if not workflow_code.strip():
            return workflow_code, {
                "import_issues": ["Empty workflow code"],
                "output_file_issues": [],
                "syntax_errors": [],
                "fixes_applied": []
            }
        
        validation_report = {
            "import_issues": [],
            "output_file_issues": [],
            "syntax_errors": [],
            "fixes_applied": []
        }
        
        # 1. Fix imports
        workflow_code, import_issues = self._fix_imports(
            workflow_code, 
            preprocessed_data.get("imports", []),
            preprocessed_data.get("import_aliases", {})
        )
        validation_report["import_issues"] = import_issues
        
        # 2. Validate output files
        output_file_issues = self._validate_output_files(
            workflow_code,
            preprocessed_data.get("output_file_mapping", {})
        )
        validation_report["output_file_issues"] = output_file_issues
        
        # 3. Check syntax
        syntax_errors = self._check_syntax(workflow_code)
        validation_report["syntax_errors"] = syntax_errors
        
        # 4. Apply auto-fixes
        workflow_code, fixes_applied = self._apply_auto_fixes(workflow_code)
        validation_report["fixes_applied"] = fixes_applied
        
        return workflow_code, validation_report
    
    def _fix_imports(
        self, 
        workflow_code: str, 
        expected_imports: List[str],
        import_aliases: Dict[str, str]
    ) -> Tuple[str, List[str]]:
        """
        Fix import statements in workflow code.
        
        Returns:
            Tuple of (fixed_code, list_of_issues)
        """
        # Input validation
        if not isinstance(workflow_code, str) or not workflow_code.strip():
            return workflow_code, []
        
        if not isinstance(expected_imports, list):
            expected_imports = []
        if not isinstance(import_aliases, dict):
            import_aliases = {}
        
        issues = []
        fixed_code = workflow_code
        
        # Extract current imports from code using CodeExtractor
        current_imports = self.code_extractor.extract_imports(workflow_code)
        
        # Check for missing imports
        missing_imports = []
        for expected_import in expected_imports:
            if not self._import_exists(expected_import, current_imports):
                missing_imports.append(expected_import)
        
        # Check for incorrect aliases
        incorrect_aliases = []
        for module, expected_alias in import_aliases.items():
            if not self._check_alias(workflow_code, module, expected_alias):
                incorrect_aliases.append((module, expected_alias))
        
        # Fix missing imports
        if missing_imports:
            # Find where to insert imports (after docstring, before first code)
            import_section = self.code_extractor.find_import_section(fixed_code, return_char_positions=True)
            if import_section:
                # Insert missing imports
                new_imports = "\n".join(missing_imports)
                fixed_code = fixed_code[:import_section["end"]] + "\n" + new_imports + "\n" + fixed_code[import_section["end"]:]
                issues.append(f"Added {len(missing_imports)} missing imports")
            else:
                # Add at the beginning
                fixed_code = "\n".join(missing_imports) + "\n\n" + fixed_code
                issues.append(f"Added {len(missing_imports)} missing imports at the beginning")
        
        # Fix incorrect aliases
        for module, expected_alias in incorrect_aliases:
            # Replace incorrect import statements
            # Pattern 1: import module -> import module as alias
            import_pattern = re.compile(rf'^import\s+{re.escape(module)}\s*$', re.MULTILINE)
            if import_pattern.search(fixed_code):
                fixed_code = import_pattern.sub(f'import {module} as {expected_alias}', fixed_code)
                issues.append(f"Fixed alias for {module} -> {expected_alias}")
            
            # Pattern 2: from module import * -> from module import * (keep as is, cannot add alias)
            # Note: from imports cannot have module-level aliases, only item-level aliases
            # So we skip from imports for alias fixing
        
        return fixed_code, issues
    
    def _validate_output_files(
        self, 
        workflow_code: str, 
        expected_output_files: Dict[str, List[int]]
    ) -> List[str]:
        """
        Validate that all expected output files are generated.
        
        Returns:
            List of issues found
        """
        # Input validation
        if not isinstance(workflow_code, str) or not workflow_code.strip():
            return []
        
        if not isinstance(expected_output_files, dict):
            return []
        
        issues = []
        
        # Extract output files from code using CodeExtractor
        generated_files = set(self.code_extractor.extract_output_files(workflow_code))
        
        # Check for missing output files
        for expected_file in expected_output_files.keys():
            if expected_file not in generated_files:
                issues.append(f"Missing output file: {expected_file}")
        
        return issues
    
    def _check_syntax(self, workflow_code: str) -> List[str]:
        """
        Check for syntax errors in workflow code.
        
        Returns:
            List of syntax errors found
        """
        # Input validation
        if not isinstance(workflow_code, str) or not workflow_code.strip():
            return []
        
        errors = []
        
        try:
            ast.parse(workflow_code)
        except SyntaxError as e:
            # Provide more detailed error information
            error_msg = f"Syntax error at line {e.lineno}"
            if e.offset:
                error_msg += f", column {e.offset}"
            error_msg += f": {e.msg}"
            if e.text:
                error_msg += f" (near: {e.text.strip()})"
            errors.append(error_msg)
        except Exception as e:
            # Catch other parsing errors
            errors.append(f"Parse error: {str(e)}")
        
        return errors
    
    def _apply_auto_fixes(self, workflow_code: str) -> Tuple[str, List[str]]:
        """
        Apply automatic fixes to common issues.
        
        Returns:
            Tuple of (fixed_code, list_of_fixes_applied)
        """
        # Input validation
        if not isinstance(workflow_code, str) or not workflow_code.strip():
            return workflow_code, []
        
        fixes_applied = []
        fixed_code = workflow_code
        
        # Find import section once and cache it (performance optimization)
        import_section = self.code_extractor.find_import_section(fixed_code, return_char_positions=True)
        import_insert_pos = import_section["end"] if import_section else 0
        
        # Collect all missing imports to add at once
        missing_imports = []
        
        # Fix 1: Ensure argparse is imported if used (not in strings/comments)
        if self._is_module_used(fixed_code, 'argparse') and not self._has_import(fixed_code, 'argparse'):
            missing_imports.append("import argparse")
            fixes_applied.append("Added missing argparse import")
        
        # Fix 2: Ensure os and sys are imported if used
        if self._is_module_used(fixed_code, 'os') and not self._has_import(fixed_code, 'os'):
            missing_imports.append("import os")
            fixes_applied.append("Added missing os import")
        
        if self._is_module_used(fixed_code, 'sys') and not self._has_import(fixed_code, 'sys'):
            missing_imports.append("import sys")
            fixes_applied.append("Added missing sys import")
        
        # Fix 3: Common import alias fixes - check usage and add if missing
        import_fixes = [
            ('pd', 'import pandas as pd', 'pandas as pd'),
            ('np', 'import numpy as np', 'numpy as np'),
            ('plt', 'import matplotlib.pyplot as plt', 'matplotlib.pyplot as plt'),
            ('sns', 'import seaborn as sns', 'seaborn as sns'),
            ('stats', 'from scipy import stats', 'scipy import stats'),
        ]
        
        for alias, required_import, import_check_key in import_fixes:
            if self._is_module_used(fixed_code, alias) and not self._has_import(fixed_code, import_check_key):
                missing_imports.append(required_import)
                fixes_applied.append(f"Added missing import: {required_import}")
        
        # Add all missing imports at once (performance optimization)
        if missing_imports:
            new_imports = "\n".join(missing_imports)
            if import_section:
                fixed_code = fixed_code[:import_insert_pos] + "\n" + new_imports + "\n" + fixed_code[import_insert_pos:]
            else:
                # No import section, add at beginning
                fixed_code = new_imports + "\n\n" + fixed_code
        
        # Fix 4: Fix incorrect aliases (import pandas -> import pandas as pd if pd. is used)
        # No need to re-find import section for alias fixes (they modify existing imports)
        for pattern, replacement, usage_key in self._ALIAS_FIX_PATTERNS:
            usage_pattern = self._USAGE_PATTERNS.get(usage_key, None)
            if usage_pattern and usage_pattern.search(fixed_code):
                if pattern.search(fixed_code):
                    fixed_code = pattern.sub(replacement, fixed_code)
                    fixes_applied.append(f"Fixed import alias: {replacement}")
        
        return fixed_code, fixes_applied
    
    def _is_module_used(self, code: str, module_name: str) -> bool:
        """
        Check if a module is used in code (not in strings or comments).
        
        Args:
            code: Code string to check
            module_name: Module name to check (e.g., 'argparse', 'pd', 'os')
            
        Returns:
            True if module is used, False otherwise
        """
        # Use compiled pattern if available
        pattern = self._USAGE_PATTERNS.get(module_name)
        if pattern:
            return pattern.search(code) is not None
        
        # Fallback: simple pattern
        pattern = re.compile(rf'\b{re.escape(module_name)}\.')
        return pattern.search(code) is not None
    
    def _has_import(self, code: str, import_key: str) -> bool:
        """
        Check if an import exists in code (not in strings or comments).
        
        Args:
            code: Code string to check
            import_key: Import identifier (e.g., 'argparse', 'pandas as pd')
            
        Returns:
            True if import exists, False otherwise
        """
        # Use compiled pattern if available
        pattern = self._IMPORT_CHECK_PATTERNS.get(import_key)
        if pattern:
            return pattern.search(code) is not None
        
        # Fallback: check in extracted imports
        imports = self.code_extractor.extract_imports(code)
        return any(import_key in imp for imp in imports)
    
    def _import_exists(self, expected_import: str, current_imports: List[str]) -> bool:
        """
        Check if an import exists in current imports.
        
        Uses exact module name matching to avoid false positives.
        """
        # Extract module name from expected import
        if expected_import.startswith('import '):
            module = expected_import.replace('import ', '').split(' as ')[0].strip()
        elif expected_import.startswith('from '):
            module = expected_import.replace('from ', '').split(' import ')[0].strip()
        else:
            return False
        
        # Check if any current import matches exactly (avoid false positives)
        for current_import in current_imports:
            # Extract module from current import
            if current_import.startswith('import '):
                current_module = current_import.replace('import ', '').split(' as ')[0].strip()
            elif current_import.startswith('from '):
                current_module = current_import.replace('from ', '').split(' import ')[0].strip()
            else:
                continue
            
            # Exact match (avoid "pandas" matching "pandas_utils")
            if current_module == module:
                return True
        
        return False
    
    def _check_alias(self, code: str, module: str, expected_alias: str) -> bool:
        """
        Check if module is used with correct alias.
        
        Args:
            code: Code string to check
            module: Module name
            expected_alias: Expected alias
            
        Returns:
            True if alias is correct or not used, False if incorrect
        """
        # Input validation
        if not isinstance(code, str) or not isinstance(module, str) or not isinstance(expected_alias, str):
            return True  # Invalid input, assume OK
        
        # Check if code uses the alias
        alias_pattern = re.compile(rf'\b{re.escape(expected_alias)}\.')
        if not alias_pattern.search(code):
            return True  # Not used, so no issue
        
        # Check if import has correct alias
        import_pattern = re.compile(rf'import\s+{re.escape(module)}\s+as\s+{re.escape(expected_alias)}\b')
        if import_pattern.search(code):
            return True
        
        return False

