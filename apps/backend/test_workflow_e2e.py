#!/usr/bin/env python3
import asyncio
import json
from pathlib import Path
from backend.agents import generate_workflow
from backend.workflow.store import WorkflowStore

async def test_onboarding_workflow():
    description = "Create an onboarding workflow for a software engineer"
    context = {
        "employee_name": "Alice Chen",
        "email": "alice@gmail.com",
        "role": "Software Engineer",
    }

    tmp_store = WorkflowStore(Path("/tmp/flowforge-test"))

    print("\n" + "=" * 70)
    print("WORKFLOW GENERATION TEST")
    print("=" * 70)
    print(f"\nQuery: {description}")
    print(f"Context: {json.dumps(context, indent=2)}\n")
    print("-" * 70)

    tool_requests = {}
    workflow_output = None
    execution_report = None
    final_cost = 0

    try:
        async for message in generate_workflow(
            description=description,
            context=context,
            workflow_store=tmp_store,
        ):
            msg_type = message["type"]
            content = message["content"]

            if msg_type == "text":
                text = content if len(content) < 120 else content[:120] + "..."
                print(f"💭 Agent: {text}")

            elif msg_type == "tool_use":
                tool_id = content.get("id")
                tool_name = content.get("tool")
                tool_requests[tool_id] = tool_name
                inp = content.get("input", {})
                detail = inp.get("file_path") or inp.get("query") or inp.get("command", "")
                print(f"🔧 [{tool_name}] {detail[:80]}")

            elif msg_type == "tool_result":
                tool_id = content.get("tool_use_id")
                is_error = content.get("is_error", False)
                result = content.get("result", "")

                tool_name = tool_requests.get(tool_id, "unknown")
                if isinstance(result, str):
                    res_preview = result[:80] if len(result) < 80 else result[:80] + "..."
                else:
                    res_preview = str(result)[:80]

                status = "❌" if is_error else "✓"
                print(f"  {status} {res_preview}")

            elif msg_type == "workflow":
                workflow_output = content
                print(f"\n📋 Workflow Generated: {content['name']}")
                print(f"   ID: {content['id']}")
                print(f"   Nodes: {len(content['nodes'])}")
                for node in content['nodes']:
                    print(f"     - {node['id']}: {node['service']}.{node['action']}")

            elif msg_type == "execution_report":
                execution_report = content["report"]
                print(f"\n⚡ Execution Report:")
                print(f"   Total: {execution_report['total_steps']}")
                print(f"   Success: {execution_report['successful']}")
                print(f"   Failed: {execution_report['failed']}")
                print(f"   Skipped: {execution_report['skipped']}")

            elif msg_type == "workflow_saved":
                print(f"\n💾 Saved: {content['workflow_id']} v{content['version']}")

            elif msg_type == "result":
                final_cost = content.get("cost_usd", 0)
                print(f"\n✅ Complete - Cost: ${final_cost:.4f}")

            elif msg_type == "error":
                print(f"\n❌ Error: {content}")

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        raise

    print("\n" + "=" * 70)
    if workflow_output:
        print(f"✓ SUCCESS: Generated workflow '{workflow_output['name']}'")
        if execution_report:
            print(f"✓ Execution: {execution_report['successful']}/{execution_report['total_steps']} passed")
    else:
        print("✗ FAILED: No workflow generated")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_onboarding_workflow())
