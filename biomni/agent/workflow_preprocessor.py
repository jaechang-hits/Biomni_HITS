"""
Workflow Preprocessor Module

Rule-based preprocessing before LLM processing.
Extracts imports, maps output files, identifies hardcoded paths, etc.
"""

import re
from typing import List, Dict, Set, Optional
from pathlib import Path
from collections import defaultdict

from .code_extractor import CodeExtractor


class WorkflowPreprocessor:
    """
    Preprocesses execution history using rule-based methods.
    
    This reduces the workload on LLM by handling tasks that can be done
    deterministically using rules and patterns.
    """
    
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
        all_imports = []
        import_aliases = {}
        
        for execution in executions:
            code = execution.get("code", "")
            if not code:
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
        
        Returns:
            Dictionary mapping module name to alias
        """
        aliases = {}
        
        # Common patterns
        patterns = [
            (r'pd\.', 'pandas', 'pd'),
            (r'np\.', 'numpy', 'np'),
            (r'plt\.', 'matplotlib.pyplot', 'plt'),
            (r'sns\.', 'seaborn', 'sns'),
            (r'stats\.', 'scipy.stats', 'stats'),
            (r'gp\.', 'gseapy', 'gp'),
        ]
        
        for pattern, module, alias in patterns:
            if re.search(pattern, code):
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
        cleaned = set()
        
        for imp in imports:
            # Skip empty imports
            if not imp or not imp.strip():
                continue
            
            # Normalize import statement
            imp = imp.strip()
            
            # Check if we need to add alias
            for module, alias in aliases.items():
                # Handle "import module" -> "import module as alias"
                if imp == f"import {module}":
                    imp = f"import {module} as {alias}"
                # Handle "from module import *" -> "from module import *" (keep as is)
                elif imp.startswith(f"from {module} import"):
                    # Check if alias is already in the import
                    if f" as {alias}" not in imp and "*" not in imp:
                        # Try to add alias if needed
                        pass  # Keep original for now
            
            cleaned.add(imp)
        
        # Sort imports: standard library first, then third-party
        stdlib_imports = []
        third_party_imports = []
        
        stdlib_modules = {
            'os', 'sys', 'json', 'csv', 'datetime', 'pathlib', 're',
            'collections', 'itertools', 'functools', 'argparse'
        }
        
        for imp in sorted(cleaned):
            module_name = imp.split()[1] if len(imp.split()) > 1 else ""
            if any(stdlib in module_name for stdlib in stdlib_modules):
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
        output_mapping = defaultdict(list)
        
        for idx, execution in enumerate(executions):
            output_files = execution.get("output_files", [])
            for output_file in output_files:
                # Extract just the filename
                file_name = Path(output_file).name
                output_mapping[file_name].append(idx)
        
        return dict(output_mapping)
    
    def _identify_hardcoded_paths(self, executions: List[Dict]) -> List[Dict]:
        """
        Identify hardcoded file paths in code.
        
        Returns:
            List of dictionaries with path information
        """
        hardcoded_paths = []
        
        for idx, execution in enumerate(executions):
            code = execution.get("code", "")
            if not code:
                continue
            
            # Use CodeExtractor to identify paths
            paths = self.code_extractor.identify_hardcoded_paths(code)
            
            for path_info in paths:
                path_info["execution_index"] = idx
                hardcoded_paths.append(path_info)
        
        return hardcoded_paths
    
    def _extract_functions(self, executions: List[Dict]) -> List[Dict]:
        """
        Extract function definitions from code.
        
        Returns:
            List of function definitions with metadata
        """
        all_functions = []
        
        for idx, execution in enumerate(executions):
            code = execution.get("code", "")
            if not code:
                continue
            
            # Use CodeExtractor to extract functions
            functions = self.code_extractor.extract_functions(code)
            
            for func in functions:
                func["execution_index"] = idx
                all_functions.append(func)
        
        return all_functions
    
    def _extract_file_operations(self, executions: List[Dict]) -> Dict:
        """
        Extract file read/write operations from all executions.
        
        Returns:
            Dictionary with read and write operations
        """
        all_read_ops = []
        all_write_ops = []
        
        for idx, execution in enumerate(executions):
            code = execution.get("code", "")
            if not code:
                continue
            
            # Use CodeExtractor to extract file operations
            file_ops = self.code_extractor.extract_file_operations(code)
            
            for op in file_ops.get("read_operations", []):
                op["execution_index"] = idx
                all_read_ops.append(op)
            
            for op in file_ops.get("write_operations", []):
                op["execution_index"] = idx
                all_write_ops.append(op)
        
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
        total_functions = 0
        total_classes = 0
        total_lines = 0
        has_try_except = False
        has_error_handling = False
        
        for execution in executions:
            code = execution.get("code", "")
            if not code:
                continue
            
            complexity = self.code_extractor.get_code_complexity(code)
            total_functions += complexity.get("function_count", 0)
            total_classes += complexity.get("class_count", 0)
            total_lines += complexity.get("line_count", 0)
            
            if "try:" in code or "except" in code:
                has_try_except = True
                has_error_handling = True
        
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
        preprocessed = []
        
        for idx, execution in enumerate(executions):
            code = execution.get("code", "")
            
            # Add metadata
            execution_with_metadata = execution.copy()
            execution_with_metadata["preprocessing_metadata"] = {
                "has_output_files": len(execution.get("output_files", [])) > 0,
                "output_file_names": [Path(f).name for f in execution.get("output_files", [])],
                "has_imports": len(self.code_extractor.extract_imports(code)) > 0,
                "has_functions": len(self.code_extractor.extract_functions(code)) > 0,
                "complexity": self.code_extractor.get_code_complexity(code)
            }
            
            preprocessed.append(execution_with_metadata)
        
        return preprocessed

