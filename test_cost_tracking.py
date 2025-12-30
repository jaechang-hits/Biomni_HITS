#!/usr/bin/env python3
"""
Test script to verify cost tracking is working.
"""

import os
import sys

# Set environment variable
os.environ["COST_TRACKING_ENABLED"] = "true"

# Test imports
try:
    from biomni.cost import (
        TokenTracker,
        CostReport,
        CostTrackingLLMWrapper,
        is_cost_tracking_enabled,
    )
    print("✅ Cost tracking module imported successfully")
except ImportError as e:
    print(f"❌ Failed to import cost tracking module: {e}")
    sys.exit(1)

# Test if enabled
print(f"✅ Cost tracking enabled: {is_cost_tracking_enabled()}")

# Test token tracker
try:
    tracker = TokenTracker(session_id="test_session", log_dir="./test_costs/logs")
    print("✅ TokenTracker created successfully")
except Exception as e:
    print(f"❌ Failed to create TokenTracker: {e}")
    sys.exit(1)

# Test tracking a call
try:
    tracker.track_llm_call(
        model="test-model",
        input_tokens=100,
        output_tokens=50,
        context="test_context"
    )
    print("✅ Token tracking call succeeded")
except Exception as e:
    print(f"❌ Failed to track token usage: {e}")
    sys.exit(1)

# Test cost report
try:
    report = CostReport()
    cost_data = report.generate_session_report(tracker)
    print(f"✅ Cost report generated: ${cost_data.get('total_cost', 0):.4f}")
    print(f"   Total calls: {cost_data.get('total_calls', 0)}")
except Exception as e:
    print(f"❌ Failed to generate cost report: {e}")
    sys.exit(1)

# Test saving report
try:
    report_file = report.save_report(cost_data, log_dir="./test_costs/logs")
    print(f"✅ Cost report saved to: {report_file}")
except Exception as e:
    print(f"❌ Failed to save cost report: {e}")
    sys.exit(1)

print("\n✅ All cost tracking tests passed!")
