"""
Test script for Bedrock Agent invocation.

This script tests calling the Bedrock Agent directly to verify it's working.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llmops_agent.config import settings
from llmops_agent.services.bedrock_service import get_bedrock_service


async def test_agent():
    """Test Bedrock Agent invocation."""

    print("=" * 70)
    print("Testing Bedrock Agent")
    print("=" * 70)
    print()

    # Check configuration
    if not settings.bedrock_agent_id:
        print("❌ BEDROCK_AGENT_ID not set in .env")
        print("   Run scripts/setup_bedrock_agent.sh first!")
        return False

    if not settings.bedrock_agent_alias_id:
        print("❌ BEDROCK_AGENT_ALIAS_ID not set in .env")
        print("   Run scripts/setup_bedrock_agent.sh first!")
        return False

    print(f"✅ Agent ID: {settings.bedrock_agent_id}")
    print(f"✅ Alias ID: {settings.bedrock_agent_alias_id}")
    print()

    # Initialize service
    bedrock = get_bedrock_service()

    # Test message
    test_message = (
        "Train a Named Entity Recognition model on the ciER dataset. "
        "My budget is $10 and I need F1 score above 85%."
    )

    print("Test Message:")
    print(f"  {test_message}")
    print()

    try:
        print("Invoking Bedrock Agent...")
        print()

        response = await bedrock.invoke_agent(
            agent_id=settings.bedrock_agent_id,
            agent_alias_id=settings.bedrock_agent_alias_id,
            session_id="test-session-123",
            input_text=test_message,
            enable_trace=True,
        )

        print("✅ Agent Response:")
        print("-" * 70)
        print(response.get("completion", "No completion"))
        print("-" * 70)
        print()

        if response.get("trace"):
            print("Agent Trace (tool calls):")
            print(json.dumps(response["trace"], indent=2))
            print()

        print("✅ Test successful!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_agent())
    sys.exit(0 if success else 1)
