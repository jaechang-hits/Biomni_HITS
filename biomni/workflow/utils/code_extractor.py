"""
Code Extractor Module

Extracts and analyzes code structure using AST parsing.
"""

import ast
import re
import sys
import importlib.util
from typing import List, Dict, Set, Optional
from pathlib import Path


class CodeExtractor:
    """Extracts code structure and components using AST parsing."""
    
    # Standard library modules (using sys.stdlib_module_names if available)
    if sys.version_info >= (3, 10):
        _STDLIB_MODULES = set(sys.stdlib_module_names)
    else:
        _STDLIB_MODULES = {
            'os', 'sys', 'json', 'csv', 'datetime', 'pathlib', 're',
            'collections', 'itertools', 'functools', 'argparse', 'ast',
            'hashlib', 'logging', 'subprocess', 'tempfile', 'shutil',
            'urllib', 'http', 'socket', 'threading', 'multiprocessing',
            'pickle', 'sqlite3', 'xml', 'html', 'email', 'base64', 'zlib',
            'time', 'warnings', 'io', 'glob', 'math', 'random', 'string'
        }
    
    def _is_package_available(self, module_name: str) -> bool:
        """
        Check if a Python package/module is available in the current environment.
        
        Args:
            module_name: Name of the module to check (e.g., 'pandas', 'numpy', 'mygene')
            
        Returns:
            True if package is available, False otherwise
        """
        # Check if it's a standard library module
        if module_name in self._STDLIB_MODULES:
            return True
        
        # Check if it's a built-in module
        if module_name in sys.builtin_module_names:
            return True
        
        # Try to find the module spec
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                return False
            
            # Additional check: try to actually import it to ensure it's usable
            # This catches cases where the module exists but has import errors
            try:
                __import__(module_name)
                return True
            except (ImportError, ModuleNotFoundError, AttributeError):
                return False
        except (ImportError, ValueError, AttributeError, Exception):
            return False
    
    def _extract_module_name_from_import(self, import_stmt: str) -> str:
        """
        Extract module name from import statement.
        
        Args:
            import_stmt: Import statement (e.g., 'import pandas as pd', 'from scipy import stats')
            
        Returns:
            Module name (e.g., 'pandas', 'scipy')
        """
        import_stmt = import_stmt.strip()
        
        if import_stmt.startswith('import '):
            # import module_name [as alias]
            module = import_stmt.replace('import ', '').split(' as ')[0].strip()
            # Get base module name (first part before dot)
            return module.split('.')[0]
        elif import_stmt.startswith('from '):
            # from module_name import ...
            parts = import_stmt.replace('from ', '').split(' import ')
            if len(parts) >= 1:
                module = parts[0].strip()
                # Get base module name (first part before dot)
                return module.split('.')[0]
        
        return ""
    
    def filter_available_imports(self, imports: List[str]) -> List[str]:
        """
        Filter import statements to only include packages available in the current environment.
        
        Args:
            imports: List of import statements
            
        Returns:
            Filtered list of import statements (only available packages)
        """
        if not isinstance(imports, list):
            return []
        
        available_imports = []
        unavailable_modules = set()
        
        for import_stmt in imports:
            if not isinstance(import_stmt, str):
                continue
            
            module_name = self._extract_module_name_from_import(import_stmt)
            
            if not module_name:
                # Could not parse, include it (safer to include than exclude)
                available_imports.append(import_stmt)
                continue
            
            # Check if module is available
            if self._is_package_available(module_name):
                available_imports.append(import_stmt)
            else:
                unavailable_modules.add(module_name)
        
        # Log unavailable modules if any
        if unavailable_modules:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Filtered out {len(unavailable_modules)} unavailable package(s): {sorted(unavailable_modules)}"
            )
        
        return available_imports
    
    def extract_functions(self, code: str) -> List[Dict]:
        """
        Extract function definitions from code using AST.
        
        Args:
            code: Code string to analyze
            
        Returns:
            List of function definitions with their metadata
        """
        functions = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "lineno": node.lineno,
                        "code": ast.get_source_segment(code, node) or ""
                    }
                    functions.append(func_info)
        except SyntaxError:
            # If code is not valid Python, return empty list
            pass
        
        return functions
    
    def extract_imports(self, code: str, filter_unavailable: bool = True) -> List[str]:
        """
        Extract and deduplicate import statements.
        
        Args:
            code: Code string to analyze
            filter_unavailable: If True, filter out packages not available in current environment
            
        Returns:
            List of unique import statements (filtered if filter_unavailable=True)
        """
        imports = set()
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Include alias if present
                        import_stmt = f"import {alias.name}"
                        if alias.asname:
                            import_stmt += f" as {alias.asname}"
                        imports.add(import_stmt)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if node.names:
                        # Include aliases if present
                        names_list = []
                        for alias in node.names:
                            name = alias.name
                            if alias.asname:
                                name += f" as {alias.asname}"
                            names_list.append(name)
                        names = ", ".join(names_list)
                        imports.add(f"from {module} import {names}")
                    else:
                        imports.add(f"from {module} import *")
        except SyntaxError:
            # If code is not valid Python, try regex fallback
            import_pattern = r'^(import\s+\S+|from\s+\S+\s+import\s+[^\n]+)'
            matches = re.findall(import_pattern, code, re.MULTILINE)
            imports.update(matches)
        
        imports_list = sorted(list(imports))
        
        # Filter out unavailable packages if requested
        if filter_unavailable:
            imports_list = self.filter_available_imports(imports_list)
        
        return imports_list
    
    def identify_hardcoded_paths(self, code: str) -> List[Dict]:
        """
        Identify hardcoded file paths in code.
        
        Args:
            code: Code string to analyze
            
        Returns:
            List of hardcoded paths with their context
        """
        hardcoded_paths = []
        
        # Patterns for file paths in strings
        path_patterns = [
            r'["\']([^"\']*\.(?:csv|tsv|txt|json|xlsx|xls|pkl|h5|hdf5|png|jpg|jpeg|pdf))["\']',
            r'["\']([^"\']*[/\\][^"\']+)["\']',  # Path-like strings
        ]
        
        for pattern in path_patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                path_str = match.group(1)
                # Check if it looks like a file path
                if '/' in path_str or '\\' in path_str or '.' in Path(path_str).suffix:
                    hardcoded_paths.append({
                        "path": path_str,
                        "position": match.start(),
                        "context": self._get_context(code, match.start(), match.end())
                    })
        
        return hardcoded_paths
    
    def extract_file_operations(self, code: str) -> Dict:
        """
        Extract file read/write operations.
        
        Args:
            code: Code string to analyze
            
        Returns:
            Dictionary with read and write operations
        """
        read_operations = []
        write_operations = []
        
        # Read operations
        read_patterns = [
            (r'pd\.read_csv\(["\']([^"\']+)["\']', 'pandas.read_csv'),
            (r'pd\.read_excel\(["\']([^"\']+)["\']', 'pandas.read_excel'),
            (r'pd\.read_json\(["\']([^"\']+)["\']', 'pandas.read_json'),
            (r'open\(["\']([^"\']+)["\'],\s*["\']r["\']', 'open_read'),
            (r'np\.load\(["\']([^"\']+)["\']', 'numpy.load'),
        ]
        
        # Write operations
        write_patterns = [
            (r'\.to_csv\(["\']([^"\']+)["\']', 'pandas.to_csv'),
            (r'\.to_excel\(["\']([^"\']+)["\']', 'pandas.to_excel'),
            (r'\.to_json\(["\']([^"\']+)["\']', 'pandas.to_json'),
            (r'open\(["\']([^"\']+)["\'],\s*["\']w', 'open_write'),
            (r'plt\.savefig\(["\']([^"\']+)["\']', 'matplotlib.savefig'),
            (r'\.save\(["\']([^"\']+)["\']', 'generic.save'),
        ]
        
        for pattern, operation_type in read_patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                read_operations.append({
                    "file": match.group(1),
                    "operation": operation_type,
                    "position": match.start()
                })
        
        for pattern, operation_type in write_patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                write_operations.append({
                    "file": match.group(1),
                    "operation": operation_type,
                    "position": match.start()
                })
        
        return {
            "read_operations": read_operations,
            "write_operations": write_operations
        }
    
    def extract_variables(self, code: str) -> List[str]:
        """
        Extract variable names from code (basic extraction).
        
        Args:
            code: Code string to analyze
            
        Returns:
            List of variable names
        """
        variables = set()
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    variables.add(node.id)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            variables.add(target.id)
        except SyntaxError:
            pass
        
        return sorted(list(variables))
    
    def get_code_complexity(self, code: str) -> Dict:
        """
        Get basic code complexity metrics.
        
        Args:
            code: Code string to analyze
            
        Returns:
            Dictionary with complexity metrics
        """
        try:
            tree = ast.parse(code)
            
            function_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
            class_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            line_count = len(code.split('\n'))
            
            return {
                "function_count": function_count,
                "class_count": class_count,
                "line_count": line_count,
                "is_complex": function_count > 5 or class_count > 2
            }
        except SyntaxError:
            return {
                "function_count": 0,
                "class_count": 0,
                "line_count": len(code.split('\n')),
                "is_complex": False
            }
    
    def _get_context(self, code: str, start: int, end: int, context_lines: int = 2) -> str:
        """
        Get context around a position in code.
        
        Args:
            code: Code string
            start: Start position
            end: End position
            context_lines: Number of lines of context
            
        Returns:
            Context string
        """
        lines = code.split('\n')
        start_line = code[:start].count('\n')
        end_line = code[:end].count('\n')
        
        context_start = max(0, start_line - context_lines)
        context_end = min(len(lines), end_line + context_lines + 1)
        
        return '\n'.join(lines[context_start:context_end])
    
    def merge_imports(self, import_lists: List[List[str]]) -> List[str]:
        """
        Merge multiple import lists and remove duplicates.
        
        Args:
            import_lists: List of import statement lists
            
        Returns:
            Merged and deduplicated import list
        """
        all_imports = set()
        
        for import_list in import_lists:
            all_imports.update(import_list)
        
        return sorted(list(all_imports))
    
    def extract_all_imports_from_executions(self, executions: List[Dict]) -> List[str]:
        """
        Extract all imports from a list of execution entries.
        
        Args:
            executions: List of execution dictionaries
            
        Returns:
            Merged list of all unique imports
        """
        all_imports = []
        
        for execution in executions:
            code = execution.get("code", "")
            imports = self.extract_imports(code)
            all_imports.extend(imports)
        
        return self.merge_imports([all_imports])
    
    def find_import_section(self, code: str, return_char_positions: bool = False) -> Optional[Dict]:
        """
        Find the import section in code.
        
        Args:
            code: Code string to analyze
            return_char_positions: If True, return character positions; if False, return line numbers
            
        Returns:
            Dictionary with "start" and "end" keys, or None if no import section found.
            If return_char_positions=True: {"start": int, "end": int} (character positions)
            If return_char_positions=False: {"start_line": int, "end_line": int} (line numbers, 0-based)
        """
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
            if return_char_positions:
                # Calculate character positions
                start_pos = sum(len(lines[i]) + 1 for i in range(import_start))
                end_pos = sum(len(lines[i]) + 1 for i in range(import_end)) if import_end else start_pos
                return {"start": start_pos, "end": end_pos}
            else:
                # Return line numbers
                return {"start_line": import_start, "end_line": import_end}
        
        return None
    
    def extract_output_files(self, code: str) -> List[str]:
        """
        Extract output file names from code.
        
        Args:
            code: Code string to analyze
            
        Returns:
            List of output file names (just filenames, not full paths)
        """
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

