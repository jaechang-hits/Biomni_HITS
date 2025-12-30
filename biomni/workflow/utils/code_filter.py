"""
Code Filter Module

Basic rule-based filtering to identify data processing code.
"""

import re
from typing import List, Dict, Optional


class CodeFilter:
    """Filters code to identify data processing operations."""
    
    # Keywords that indicate data processing
    # Compound keywords (with underscore) should be checked first for accuracy
    DATA_PROCESSING_KEYWORDS = [
        # File operations (compound keywords first)
        'read_csv', 'read_excel', 'read_json', 'read_parquet', 'read_table',
        'to_csv', 'to_excel', 'to_json', 'to_parquet',
        # GSEA and enrichment analysis
        'gsea', 'prerank', 'enrichment', 'pathway', 'gseaplot', 'enrichr', 'fgsea',
        # Statistical analysis
        'ttest', 'anova', 'correlation', 'regression', 'differential',
        # Data processing operations
        'load', 'read', 'process', 'transform', 'clean',
        'filter', 'merge', 'join', 'aggregate', 'groupby', 'apply',
        'map', 'reduce', 'compute', 'calculate', 'analyze', 'statistics',
        'save', 'write', 'export',
        'fit', 'train', 'predict', 'evaluate', 'score',
    ]
    
    # Keywords that indicate exploration/debugging (to exclude)
    # Note: 'try', 'except', 'pass' removed - they are common in data processing code
    EXPLORATION_KEYWORDS = [
        'head', 'tail', 'describe', 'info', 'dtypes', 'shape',
        'columns', 'index', 'explore', 'inspect', 'check', 'verify',
        'print', 'display', 'show', 'view', 'look', 'see',
        'debug'
    ]
    
    # Keywords that indicate visualization (usually exclude)
    VISUALIZATION_KEYWORDS = [
        'plot', 'plt.', 'matplotlib', 'seaborn', 'sns.', 'show()',
        'hist', 'bar', 'scatter', 'line', 'box', 'violin', 'heatmap'
    ]
    
    # Compiled regex patterns for file operations (performance optimization)
    _FILE_READ_PATTERNS = [
        re.compile(r'\.read_csv\('),
        re.compile(r'\.read_excel\('),
        re.compile(r'\.read_json\('),
        re.compile(r'\.read_parquet\('),
        re.compile(r'\.read_table\('),
        re.compile(r'open\([^,]+,\s*["\']r'),
        re.compile(r'np\.load\('),
        re.compile(r'pickle\.load\('),
    ]
    
    _FILE_WRITE_PATTERNS = [
        re.compile(r'\.to_csv\('),
        re.compile(r'\.to_excel\('),
        re.compile(r'\.to_json\('),
        re.compile(r'\.to_parquet\('),
        re.compile(r'\.savefig\('),
        re.compile(r'\.save\('),
        re.compile(r'open\([^,]+,\s*["\']w'),
        re.compile(r'open\([^,]+,\s*["\']wb'),
        re.compile(r'open\([^,]+,\s*["\']wt'),
        re.compile(r'np\.save\('),
        re.compile(r'pickle\.dump\('),
    ]
    
    def is_data_processing_code(self, code: str) -> bool:
        """
        Determine if code is data processing code using basic rules.
        
        Args:
            code: Code string to analyze
            
        Returns:
            True if code appears to be data processing, False otherwise
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return False
        
        code_lower = code.lower()
        
        # Check for data processing keywords
        # Compound keywords (with underscore) are checked first with simple substring matching
        # Short keywords use word boundaries to avoid false positives (e.g., 'test' matching 'ttest')
        has_processing_keyword = False
        for keyword in self.DATA_PROCESSING_KEYWORDS:
            if '_' in keyword:
                # Compound keywords: simple substring match (e.g., 'read_csv', 'to_csv')
                if keyword in code_lower:
                    has_processing_keyword = True
                    break
            elif len(keyword) >= 4:
                # Medium/long keywords: simple substring match (e.g., 'groupby', 'enrichment')
                if keyword in code_lower:
                    has_processing_keyword = True
                    break
            else:
                # Short keywords (3 chars or less): use word boundary to avoid false positives
                # (e.g., 'map', 'fit' should not match 'mapreduce', 'fitted')
                if re.search(r'\b' + re.escape(keyword) + r'\b', code_lower):
                    has_processing_keyword = True
                    break
        
        # Check for exploration keywords (exclude if present)
        has_exploration_keyword = any(
            re.search(r'\b' + re.escape(keyword) + r'\b', code_lower)
            for keyword in self.EXPLORATION_KEYWORDS
        )
        
        # Check for visualization keywords (exclude standalone visualization)
        has_visualization_keyword = any(
            keyword in code_lower for keyword in self.VISUALIZATION_KEYWORDS
        )
        
        # If it's only visualization without processing, exclude
        if has_visualization_keyword and not has_processing_keyword:
            return False
        
        # If it's only exploration, exclude
        if has_exploration_keyword and not has_processing_keyword:
            return False
        
        # Must have at least one processing keyword
        return has_processing_keyword
    
    def filter_executions(self, executions: List[Dict]) -> List[Dict]:
        """
        Filter execution history to keep only data processing code.
        
        Priority: Output files > Data processing keywords
        
        Args:
            executions: List of execution entries
            
        Returns:
            Filtered list of execution entries
        """
        if not isinstance(executions, list):
            return []
        
        filtered = []
        
        for execution in executions:
            # Input validation
            if not isinstance(execution, dict):
                continue
            
            # Only include successful executions
            if not execution.get("success", False):
                continue
            
            code = execution.get("code", "")
            if not isinstance(code, str) or not code.strip():
                continue
            
            # PRIORITY 1: If execution has output files, always include it
            # This ensures all code that generates output files is included
            output_files = execution.get("output_files", [])
            if isinstance(output_files, list) and len(output_files) > 0:
                filtered.append(execution)
                continue
            
            # PRIORITY 2: Check if it's data processing code
            if self.is_data_processing_code(code):
                filtered.append(execution)
        
        return filtered
    
    def is_file_operation(self, code: str) -> bool:
        """
        Check if code performs file I/O operations.
        
        Args:
            code: Code string to analyze
            
        Returns:
            True if code performs file operations
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return False
        
        code_lower = code.lower()
        
        # Check for read operations
        if any(pattern.search(code_lower) for pattern in self._FILE_READ_PATTERNS):
            return True
        
        # Check for write operations
        if any(pattern.search(code_lower) for pattern in self._FILE_WRITE_PATTERNS):
            return True
        
        return False
    
    def has_output_operation(self, code: str) -> bool:
        """
        Check if code creates output files.
        
        Args:
            code: Code string to analyze
            
        Returns:
            True if code creates output files
        """
        # Input validation
        if not isinstance(code, str) or not code.strip():
            return False
        
        code_lower = code.lower()
        
        # Use compiled patterns for better performance
        return any(pattern.search(code_lower) for pattern in self._FILE_WRITE_PATTERNS)

