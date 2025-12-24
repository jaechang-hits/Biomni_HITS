"""
Workflow Postprocessor Module

Rule-based postprocessing after LLM processing.
Validates and fixes LLM-generated workflow code.
"""

import re
import ast
from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path


class WorkflowPostprocessor:
    """
    Postprocesses LLM-generated workflow code using rule-based methods.
    
    Validates imports, output files, and code structure, then applies
    automatic fixes where possible.
    """
    
    def __init__(self):
        """Initialize the postprocessor."""
        pass
    
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
        issues = []
        fixed_code = workflow_code
        
        # Extract current imports from code
        current_imports = self._extract_imports_from_code(workflow_code)
        
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
            import_section = self._find_import_section(fixed_code)
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
            patterns = [
                (rf'import\s+{re.escape(module)}\s*$', f'import {module} as {expected_alias}'),
                (rf'from\s+{re.escape(module)}\s+import', f'from {module} import'),  # Keep as is for from imports
            ]
            for pattern, replacement in patterns:
                fixed_code = re.sub(pattern, replacement, fixed_code, flags=re.MULTILINE)
            issues.append(f"Fixed alias for {module} -> {expected_alias}")
        
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
        issues = []
        
        # Extract output file patterns from code
        output_patterns = [
            r'\.to_csv\(["\']([^"\']+)["\']',
            r'\.savefig\(["\']([^"\']+)["\']',
            r'gseaplot\([^,]+ofname=["\']([^"\']+)["\']',
            r'\.to_excel\(["\']([^"\']+)["\']',
            r'\.to_json\(["\']([^"\']+)["\']',
        ]
        
        generated_files = set()
        for pattern in output_patterns:
            matches = re.findall(pattern, workflow_code)
            for match in matches:
                file_name = Path(match).name
                generated_files.add(file_name)
        
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
        errors = []
        
        try:
            ast.parse(workflow_code)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        
        return errors
    
    def _apply_auto_fixes(self, workflow_code: str) -> Tuple[str, List[str]]:
        """
        Apply automatic fixes to common issues.
        
        Returns:
            Tuple of (fixed_code, list_of_fixes_applied)
        """
        fixes_applied = []
        fixed_code = workflow_code
        
        # Fix 1: Ensure argparse is imported if used
        if 'argparse' in fixed_code and 'import argparse' not in fixed_code:
            # Add argparse import
            import_section = self._find_import_section(fixed_code)
            if import_section:
                fixed_code = fixed_code[:import_section["end"]] + "\nimport argparse\n" + fixed_code[import_section["end"]:]
                fixes_applied.append("Added missing argparse import")
        
        # Fix 2: Ensure os and sys are imported if used
        if 'os.' in fixed_code and 'import os' not in fixed_code:
            import_section = self._find_import_section(fixed_code)
            if import_section:
                fixed_code = fixed_code[:import_section["end"]] + "\nimport os\n" + fixed_code[import_section["end"]:]
                fixes_applied.append("Added missing os import")
        
        if 'sys.' in fixed_code and 'import sys' not in fixed_code:
            import_section = self._find_import_section(fixed_code)
            if import_section:
                fixed_code = fixed_code[:import_section["end"]] + "\nimport sys\n" + fixed_code[import_section["end"]:]
                fixes_applied.append("Added missing sys import")
        
        # Fix 3: Common import alias fixes - check usage and add if missing
        import_fixes = [
            (r'pd\.', 'import pandas as pd', r'import\s+pandas\s+as\s+pd'),
            (r'np\.', 'import numpy as np', r'import\s+numpy\s+as\s+np'),
            (r'plt\.', 'import matplotlib.pyplot as plt', r'import\s+matplotlib\.pyplot\s+as\s+plt'),
            (r'sns\.', 'import seaborn as sns', r'import\s+seaborn\s+as\s+sns'),
            (r'stats\.', 'from scipy import stats', r'from\s+scipy\s+import\s+stats'),
        ]
        
        for usage_pattern, required_import, import_check_pattern in import_fixes:
            # Check if the pattern is used in code
            if re.search(usage_pattern, fixed_code):
                # Check if the import exists
                if not re.search(import_check_pattern, fixed_code):
                    # Import is missing, add it
                    import_section = self._find_import_section(fixed_code)
                    if import_section:
                        fixed_code = fixed_code[:import_section["end"]] + f"\n{required_import}\n" + fixed_code[import_section["end"]:]
                        fixes_applied.append(f"Added missing import: {required_import}")
                    else:
                        # No import section, add at beginning
                        fixed_code = f"{required_import}\n\n" + fixed_code
                        fixes_applied.append(f"Added missing import at beginning: {required_import}")
        
        # Fix 4: Fix incorrect aliases (import pandas -> import pandas as pd if pd. is used)
        alias_fixes = [
            (r'^import\s+pandas\s*$', 'import pandas as pd', r'pd\.'),
            (r'^import\s+numpy\s*$', 'import numpy as np', r'np\.'),
            (r'^import\s+matplotlib\.pyplot\s*$', 'import matplotlib.pyplot as plt', r'plt\.'),
            (r'^import\s+seaborn\s*$', 'import seaborn as sns', r'sns\.'),
        ]
        
        for pattern, replacement, usage_pattern in alias_fixes:
            if re.search(usage_pattern, fixed_code) and re.search(pattern, fixed_code, re.MULTILINE):
                fixed_code = re.sub(pattern, replacement, fixed_code, flags=re.MULTILINE)
                fixes_applied.append(f"Fixed import alias: {replacement}")
        
        return fixed_code, fixes_applied
    
    def _extract_imports_from_code(self, code: str) -> List[str]:
        """Extract import statements from code."""
        imports = []
        import_pattern = r'^(import\s+\S+|from\s+\S+\s+import\s+[^\n]+)'
        matches = re.findall(import_pattern, code, re.MULTILINE)
        imports.extend([m.strip() for m in matches])
        return imports
    
    def _import_exists(self, expected_import: str, current_imports: List[str]) -> bool:
        """Check if an import exists in current imports."""
        # Extract module name from expected import
        if expected_import.startswith('import '):
            module = expected_import.replace('import ', '').split(' as ')[0].strip()
        elif expected_import.startswith('from '):
            module = expected_import.replace('from ', '').split(' import ')[0].strip()
        else:
            return False
        
        # Check if any current import matches
        for current_import in current_imports:
            if module in current_import:
                return True
        
        return False
    
    def _check_alias(self, code: str, module: str, expected_alias: str) -> bool:
        """Check if module is used with correct alias."""
        # Check if code uses the alias
        alias_pattern = rf'\b{re.escape(expected_alias)}\.'
        if not re.search(alias_pattern, code):
            return True  # Not used, so no issue
        
        # Check if import has correct alias
        import_pattern = rf'import\s+{re.escape(module)}\s+as\s+{re.escape(expected_alias)}'
        if re.search(import_pattern, code):
            return True
        
        return False
    
    def _find_import_section(self, code: str) -> Optional[Dict[str, int]]:
        """Find the import section in code."""
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
        
        if import_start is not None:
            # Calculate character positions
            start_pos = sum(len(lines[i]) + 1 for i in range(import_start))
            end_pos = sum(len(lines[i]) + 1 for i in range(import_end)) if import_end else start_pos
            return {"start": start_pos, "end": end_pos}
        
        return None

