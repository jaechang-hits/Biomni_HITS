"""
Workflow Preprocessor Module

Rule-based preprocessing before LLM processing.
Extracts imports, maps output files, identifies hardcoded paths, etc.
"""

import re
import sys
from typing import List, Dict, Set, Optional
from pathlib import Path
from collections import defaultdict

from biomni.workflow.utils.code_extractor import CodeExtractor


class WorkflowPreprocessor:
    """
    Preprocesses execution history using rule-based methods.
    
    This reduces the workload on LLM by handling tasks that can be done
    deterministically using rules and patterns.
    """
    
    # Pre-compiled regex patterns for performance
    _IMPORT_ALIAS_PATTERNS = [
        (re.compile(r'pd\.'), 'pandas', 'pd'),
        (re.compile(r'np\.'), 'numpy', 'np'),
        (re.compile(r'plt\.'), 'matplotlib.pyplot', 'plt'),
        (re.compile(r'sns\.'), 'seaborn', 'sns'),
        (re.compile(r'stats\.'), 'scipy.stats', 'stats'),
        (re.compile(r'gp\.'), 'gseapy', 'gp'),
    ]
    
    # Standard library modules (using sys.stdlib_module_names if available, otherwise fallback)
    if sys.version_info >= (3, 10):
        _STDLIB_MODULES = set(sys.stdlib_module_names)
    else:
        _STDLIB_MODULES = {
            'os', 'sys', 'json', 'csv', 'datetime', 'pathlib', 're',
            'collections', 'itertools', 'functools', 'argparse', 'ast',
            'hashlib', 'logging', 'subprocess', 'tempfile', 'shutil',
            'urllib', 'http', 'socket', 'threading', 'multiprocessing',
            'pickle', 'sqlite3', 'xml', 'html', 'email', 'base64', 'zlib'
        }
    
    # Compiled regex for try/except detection (not in strings/comments)
    _TRY_EXCEPT_PATTERN = re.compile(r'\btry\s*:|except\s+')
    
    def __init__(self):
        """Initialize the preprocessor."""
        self.code_extractor = CodeExtractor()
    
    def preprocess(self, executions: List[Dict]) -> Dict:
        """
        Preprocess execution history using rule-based methods.
        
        Args:
            executions: List of execution entries
            
        Returns:
            Dictionary with preprocessed data:
            {
                "imports": List[str],  # Cleaned and deduplicated imports
                "import_aliases": Dict[str, str],  # Module -> alias mapping
                "output_file_mapping": Dict[str, List[int]],  # Output file -> execution indices
                "hardcoded_paths": List[Dict],  # Hardcoded paths with context
                "functions": List[Dict],  # Extracted functions
                "file_operations": Dict,  # File read/write operations
                "code_structure": Dict,  # Code structure analysis
                "preprocessed_executions": List[Dict]  # Executions with metadata
            }
        """
        # Input validation
        if not isinstance(executions, list):
            return self._empty_preprocessed_data()
        
        if not executions:
            return self._empty_preprocessed_data()
        
        # Extract and clean imports
        imports_data = self._extract_and_clean_imports(executions)
        
        # Map output files to code blocks
        output_file_mapping = self._map_output_files(executions)
        
        # Identify hardcoded paths
        hardcoded_paths = self._identify_hardcoded_paths(executions)
        
        # Extract functions
        functions = self._extract_functions(executions)
        
        # Extract file operations
        file_operations = self._extract_file_operations(executions)
        
        # Analyze code structure
        code_structure = self._analyze_code_structure(executions)
        
        # Add metadata to executions
        preprocessed_executions = self._add_metadata_to_executions(
            executions, imports_data, output_file_mapping
        )
        
        return {
            "imports": imports_data["imports"],
            "import_aliases": imports_data["aliases"],
            "output_file_mapping": output_file_mapping,
            "hardcoded_paths": hardcoded_paths,
            "functions": functions,
            "file_operations": file_operations,
            "code_structure": code_structure,
            "preprocessed_executions": preprocessed_executions
        }
    
    def _empty_preprocessed_data(self) -> Dict:
        """Return empty preprocessed data structure."""
        return {
            "imports": [],
            "import_aliases": {},
            "output_file_mapping": {},
            "hardcoded_paths": [],
            "functions": [],
            "file_operations": {"read_operations": [], "write_operations": []},
            "code_structure": {},
            "preprocessed_executions": []
        }
    
    def _extract_and_clean_imports(self, executions: List[Dict]) -> Dict:
        """
        Extract and clean imports from all executions.
        
        Returns:
            {
                "imports": List[str],  # Cleaned import statements
                "aliases": Dict[str, str]  # Module -> alias mapping
            }
        """
        # Input validation
        if not isinstance(executions, list):
            return {"imports": [], "aliases": {}}
        
        all_imports = []
        import_aliases = {}
        
        for execution in executions:
            if not isinstance(execution, dict):
                continue
            
            code = execution.get("code", "")
            if not isinstance(code, str) or not code.strip():
                continue
            
            # Extract imports using CodeExtractor
            imports = self.code_extractor.extract_imports(code)
            all_imports.extend(imports)
            
            # Analyze import aliases
            aliases = self._analyze_import_aliases(code)
            import_aliases.update(aliases)
        
        # Deduplicate and clean imports
        cleaned_imports = self._clean_imports(all_imports, import_aliases)
        
        return {
            "imports": cleaned_imports,
            "aliases": import_aliases
        }
    
    def _analyze_import_aliases(self, code: str) -> Dict[str, str]:
        """
        Analyze import aliases from code usage patterns.
        
        Args:
            code: Code string to analyze
            
        Returns:
            Dictionary mapping module name to alias
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return {}
        
        aliases = {}
        
        # Use pre-compiled patterns for performance
        for pattern, module, alias in self._IMPORT_ALIAS_PATTERNS:
            if pattern.search(code):
                aliases[module] = alias
        
        return aliases
    
    def _clean_imports(self, imports: List[str], aliases: Dict[str, str]) -> List[str]:
        """
        Clean and deduplicate imports, ensuring correct aliases.
        
        Args:
            imports: List of import statements
            aliases: Dictionary of module -> alias mappings
            
        Returns:
            Cleaned and deduplicated import list
        """
        # Input validation
        if not isinstance(imports, list):
            return []
        if not isinstance(aliases, dict):
            aliases = {}
        
        cleaned = set()
        
        for imp in imports:
            # Skip empty imports
            if not isinstance(imp, str) or not imp.strip():
                continue
            
            # Normalize import statement
            imp = imp.strip()
            
            # Check if we need to add alias
            for module, alias in aliases.items():
                # Handle "import module" -> "import module as alias"
                if imp == f"import {module}":
                    imp = f"import {module} as {alias}"
                # Handle "from module import something" -> check if alias needed
                elif imp.startswith(f"from {module} import"):
                    # For "from module import item", we can't add module-level alias
                    # But we can check if item-level alias is needed
                    if "*" not in imp and f" as {alias}" not in imp:
                        # Check if the imported item is used with the alias
                        # This is complex, so we keep the original for now
                        # Future enhancement: parse AST to check item usage
                        pass
            
            cleaned.add(imp)
        
        # Sort imports: standard library first, then third-party
        stdlib_imports = []
        third_party_imports = []
        
        for imp in sorted(cleaned):
            # Extract module name safely
            imp_parts = imp.split()
            if len(imp_parts) < 2:
                # Malformed import, skip or add to third-party
                third_party_imports.append(imp)
                continue
            
            # Handle "import module" or "import module as alias"
            if imp_parts[0] == "import":
                module_name = imp_parts[1].split(".")[0]  # Get base module name
            # Handle "from module import ..."
            elif imp_parts[0] == "from" and len(imp_parts) >= 2:
                module_name = imp_parts[1].split(".")[0]  # Get base module name
            else:
                # Unknown format, add to third-party
                third_party_imports.append(imp)
                continue
            
            # Check if module is in stdlib (exact match on base module name)
            if module_name in self._STDLIB_MODULES:
                stdlib_imports.append(imp)
            else:
                third_party_imports.append(imp)
        
        return stdlib_imports + third_party_imports
    
    def _map_output_files(self, executions: List[Dict]) -> Dict[str, List[int]]:
        """
        Map output files to execution indices.
        
        Returns:
            Dictionary mapping output file name to list of execution indices
        """
        # Input validation
        if not isinstance(executions, list):
            return {}
        
        output_mapping = defaultdict(list)
        
        for idx, execution in enumerate(executions):
            if not isinstance(execution, dict):
                continue
            
            output_files = execution.get("output_files", [])
            # Ensure output_files is a list
            if not isinstance(output_files, list):
                continue
            
            for output_file in output_files:
                if not isinstance(output_file, str):
                    continue
                # Extract just the filename
                try:
                    file_name = Path(output_file).name
                    output_mapping[file_name].append(idx)
                except (ValueError, TypeError):
                    # Invalid path, skip
                    continue
        
        return dict(output_mapping)
    
    def _identify_hardcoded_paths(self, executions: List[Dict]) -> List[Dict]:
        """
        Identify hardcoded file paths in code.
        
        Returns:
            List of dictionaries with path information
        """
        # Input validation
        if not isinstance(executions, list):
            return []
        
        hardcoded_paths = []
        
        for idx, execution in enumerate(executions):
            if not isinstance(execution, dict):
                continue
            
            code = execution.get("code", "")
            if not isinstance(code, str) or not code.strip():
                continue
            
            # Use CodeExtractor to identify paths
            try:
                paths = self.code_extractor.identify_hardcoded_paths(code)
                if not isinstance(paths, list):
                    continue
                
                for path_info in paths:
                    if isinstance(path_info, dict):
                        path_info = path_info.copy()  # Avoid modifying original
                        path_info["execution_index"] = idx
                        hardcoded_paths.append(path_info)
            except Exception:
                # Skip if extraction fails
                continue
        
        return hardcoded_paths
    
    def _extract_functions(self, executions: List[Dict]) -> List[Dict]:
        """
        Extract function definitions from code.
        
        Returns:
            List of function definitions with metadata
        """
        # Input validation
        if not isinstance(executions, list):
            return []
        
        all_functions = []
        
        for idx, execution in enumerate(executions):
            if not isinstance(execution, dict):
                continue
            
            code = execution.get("code", "")
            if not isinstance(code, str) or not code.strip():
                continue
            
            # Use CodeExtractor to extract functions
            try:
                functions = self.code_extractor.extract_functions(code)
                if not isinstance(functions, list):
                    continue
                
                for func in functions:
                    if isinstance(func, dict):
                        func = func.copy()  # Avoid modifying original
                        func["execution_index"] = idx
                        all_functions.append(func)
            except Exception:
                # Skip if extraction fails
                continue
        
        return all_functions
    
    def _extract_file_operations(self, executions: List[Dict]) -> Dict:
        """
        Extract file read/write operations from all executions.
        
        Returns:
            Dictionary with read and write operations
        """
        # Input validation
        if not isinstance(executions, list):
            return {"read_operations": [], "write_operations": []}
        
        all_read_ops = []
        all_write_ops = []
        
        for idx, execution in enumerate(executions):
            if not isinstance(execution, dict):
                continue
            
            code = execution.get("code", "")
            if not isinstance(code, str) or not code.strip():
                continue
            
            # Use CodeExtractor to extract file operations
            try:
                file_ops = self.code_extractor.extract_file_operations(code)
                if not isinstance(file_ops, dict):
                    continue
                
                read_ops = file_ops.get("read_operations", [])
                write_ops = file_ops.get("write_operations", [])
                
                if isinstance(read_ops, list):
                    for op in read_ops:
                        if isinstance(op, dict):
                            op = op.copy()  # Avoid modifying original
                            op["execution_index"] = idx
                            all_read_ops.append(op)
                
                if isinstance(write_ops, list):
                    for op in write_ops:
                        if isinstance(op, dict):
                            op = op.copy()  # Avoid modifying original
                            op["execution_index"] = idx
                            all_write_ops.append(op)
            except Exception:
                # Skip if extraction fails
                continue
        
        return {
            "read_operations": all_read_ops,
            "write_operations": all_write_ops
        }
    
    def _analyze_code_structure(self, executions: List[Dict]) -> Dict:
        """
        Analyze code structure across all executions.
        
        Returns:
            Dictionary with structure analysis
        """
        # Input validation
        if not isinstance(executions, list):
            return {
                "total_functions": 0,
                "total_classes": 0,
                "total_lines": 0,
                "num_executions": 0,
                "has_try_except": False,
                "has_error_handling": False,
                "avg_lines_per_execution": 0
            }
        
        total_functions = 0
        total_classes = 0
        total_lines = 0
        has_try_except = False
        has_error_handling = False
        
        for execution in executions:
            if not isinstance(execution, dict):
                continue
            
            code = execution.get("code", "")
            if not isinstance(code, str) or not code.strip():
                continue
            
            try:
                complexity = self.code_extractor.get_code_complexity(code)
                if isinstance(complexity, dict):
                    total_functions += complexity.get("function_count", 0)
                    total_classes += complexity.get("class_count", 0)
                    total_lines += complexity.get("line_count", 0)
                
                # Use regex to detect try/except (not in strings/comments)
                # This is a simple check - for more accuracy, use AST parsing
                # Exclude comment lines
                lines = code.split('\n')
                code_without_comments = []
                for line in lines:
                    stripped = line.strip()
                    # Skip comment-only lines
                    if stripped and not stripped.startswith('#'):
                        code_without_comments.append(line)
                code_clean = '\n'.join(code_without_comments)
                
                if self._TRY_EXCEPT_PATTERN.search(code_clean):
                    has_try_except = True
                    has_error_handling = True
            except Exception:
                # Skip if analysis fails
                continue
        
        return {
            "total_functions": total_functions,
            "total_classes": total_classes,
            "total_lines": total_lines,
            "num_executions": len(executions),
            "has_try_except": has_try_except,
            "has_error_handling": has_error_handling,
            "avg_lines_per_execution": total_lines / len(executions) if executions else 0
        }
    
    def _add_metadata_to_executions(
        self, 
        executions: List[Dict], 
        imports_data: Dict,
        output_file_mapping: Dict[str, List[int]]
    ) -> List[Dict]:
        """
        Add preprocessing metadata to executions.
        
        Returns:
            List of executions with added metadata
        """
        # Input validation
        if not isinstance(executions, list):
            return []
        if not isinstance(imports_data, dict):
            imports_data = {}
        if not isinstance(output_file_mapping, dict):
            output_file_mapping = {}
        
        preprocessed = []
        
        for idx, execution in enumerate(executions):
            if not isinstance(execution, dict):
                continue
            
            code = execution.get("code", "")
            if not isinstance(code, str):
                code = ""
            
            # Get output files safely
            output_files = execution.get("output_files", [])
            if not isinstance(output_files, list):
                output_files = []
            
            # Add metadata
            try:
                execution_with_metadata = execution.copy()
                
                # Extract metadata safely
                output_file_names = []
                for f in output_files:
                    if isinstance(f, str):
                        try:
                            output_file_names.append(Path(f).name)
                        except (ValueError, TypeError):
                            pass
                
                # Extract imports, functions, and complexity
                imports = []
                functions = []
                complexity = {}
                
                if code.strip():
                    try:
                        imports = self.code_extractor.extract_imports(code)
                        functions = self.code_extractor.extract_functions(code)
                        complexity = self.code_extractor.get_code_complexity(code)
                    except Exception:
                        # Use defaults if extraction fails
                        pass
                
                execution_with_metadata["preprocessing_metadata"] = {
                    "has_output_files": len(output_files) > 0,
                    "output_file_names": output_file_names,
                    "has_imports": len(imports) > 0 if isinstance(imports, list) else False,
                    "has_functions": len(functions) > 0 if isinstance(functions, list) else False,
                    "complexity": complexity if isinstance(complexity, dict) else {}
                }
                
                preprocessed.append(execution_with_metadata)
            except Exception:
                # Skip if metadata addition fails
                continue
        
        return preprocessed

