"""
Workflow Service Module

Standalone service for saving workflows from execute blocks.
Can be used independently of the Agent for workflow reconstruction.
"""

from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from .workflow_tracker import WorkflowTracker
from .workflow_saver import WorkflowSaver
from .workflow_validator import WorkflowValidator


class WorkflowService:
    """
    Standalone service for saving workflows from execute blocks.
    
    This service can be used independently of the Agent to:
    - Load execute blocks from files
    - Generate and save workflows
    - Validate saved workflows
    """
    
    @staticmethod
    def save_workflow_from_execute_blocks(
        execute_blocks_dir: str,
        workflows_dir: str,
        llm,
        workflow_name: Optional[str] = None,
        session_start_time: Optional[datetime] = None,
        filter_by_session: bool = True,
        max_fix_attempts: int = 2,
        save_mode: str = "simple"  # "llm" or "simple"
    ) -> Optional[str]:
        """
        Load execute blocks from files and save workflow.
        
        This method can be called independently of the Agent to reconstruct
        and save workflows from previously saved execute blocks.
        
        Args:
            execute_blocks_dir: Directory containing execute block JSON files
            workflows_dir: Directory to save workflow files
            llm: LLM instance for workflow generation
            workflow_name: Optional workflow name (auto-extracted if not provided)
            session_start_time: Optional session start time for filtering (if None, uses current time)
            filter_by_session: If True, only load files from current session (default: True)
            max_fix_attempts: Maximum number of fix attempts during validation (default: 2)
        
        Returns:
            Path to saved workflow file, or None if saving failed
        """
        execute_blocks_path = Path(execute_blocks_dir)
        workflows_path = Path(workflows_dir)
        
        if not execute_blocks_path.exists():
            print(f"⚠️  Execute blocks directory does not exist: {execute_blocks_dir}")
            return None
        
        # Create a temporary WorkflowTracker to load execute blocks
        # We don't need a work_dir since we're loading from files
        tracker = WorkflowTracker(work_dir=None)
        tracker.execute_blocks_dir = execute_blocks_path
        
        # Set session start time if provided
        if session_start_time:
            tracker.session_start_time = session_start_time
        
        # Load execute blocks from files
        execution_history = tracker.load_execute_blocks_from_files(
            filter_by_session=filter_by_session
        )
        
        if not execution_history:
            print("ℹ️  No execute blocks found to save workflow from.")
            return None
        
        print(f"📂 Loaded {len(execution_history)} execute block(s) from files")
        
        # Initialize saver and validator
        # WorkflowSaver expects work_dir, and creates work_dir/workflows subdirectory
        # But we want to use workflows_dir directly, so we pass workflows_path.parent as work_dir
        # and then override workflows_dir
        saver = WorkflowSaver(llm, str(workflows_path.parent), validator=None)
        # Override workflows_dir to use the provided directory directly
        saver.workflows_dir = workflows_path
        saver.workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # Validator also needs work_dir for temp directory
        validator = WorkflowValidator(str(workflows_path.parent))
        saver.validator = validator
        
        # Save and validate workflow
        workflow_path = saver.save_and_validate_workflow(
            tracker,
            workflow_name,
            max_fix_attempts=max_fix_attempts,
            save_mode=save_mode
        )
        
        return workflow_path
    
    @staticmethod
    def save_workflow_from_tracker(
        tracker: WorkflowTracker,
        workflows_dir: str,
        llm,
        workflow_name: Optional[str] = None,
        max_fix_attempts: int = 2,
        save_mode: str = "simple"  # "llm" or "simple"
    ) -> Optional[str]:
        """
        Save workflow from an existing WorkflowTracker instance.
        
        This is a convenience method for when you already have a WorkflowTracker
        (e.g., from an Agent instance).
        
        Args:
            tracker: WorkflowTracker instance with execution history
            workflows_dir: Directory to save workflow files
            llm: LLM instance for workflow generation
            workflow_name: Optional workflow name (auto-extracted if not provided)
            max_fix_attempts: Maximum number of fix attempts during validation (default: 2)
        
        Returns:
            Path to saved workflow file, or None if saving failed
        """
        workflows_path = Path(workflows_dir)
        
        # Initialize saver and validator
        # WorkflowSaver expects work_dir, and creates work_dir/workflows subdirectory
        # But we want to use workflows_dir directly, so we pass workflows_path.parent as work_dir
        # and then override workflows_dir
        saver = WorkflowSaver(llm, str(workflows_path.parent), validator=None)
        # Override workflows_dir to use the provided directory directly
        saver.workflows_dir = workflows_path
        saver.workflows_dir.mkdir(parents=True, exist_ok=True)
        
        # Validator also needs work_dir for temp directory
        validator = WorkflowValidator(str(workflows_path.parent))
        saver.validator = validator
        
        # Save and validate workflow
        workflow_path = saver.save_and_validate_workflow(
            tracker,
            workflow_name,
            max_fix_attempts=max_fix_attempts,
            save_mode=save_mode
        )
        
        return workflow_path

