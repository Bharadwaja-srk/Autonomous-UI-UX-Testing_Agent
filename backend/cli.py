"""
Command Line Interface for CI/CD Integration.
Allows running the Autonomous UI/UX Testing Agent headlessly in CI pipelines.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from backend.orchestrator import TestOrchestrator
from backend.schemas import TestMode, TestStatus
from backend.github_integration import GitHubIntegration

def main():
    parser = argparse.ArgumentParser(description="Autonomous UI/UX & Accessibility Testing Agent CLI")
    
    parser.add_argument("goal", help="The natural language goal to test (e.g. 'Add a product to cart and checkout')")
    parser.add_argument("url", help="The target URL to test")
    
    parser.add_argument("--mode", type=str, choices=[m.value for m in TestMode], default=TestMode.GOAL_DIRECTED.value,
                        help="Testing mode to run")
    parser.add_argument("--device", type=str, default="desktop", 
                        help="Device profile (desktop, tablet, mobile, mobile_landscape)")
    parser.add_argument("--max-steps", type=int, default=30, 
                        help="Maximum number of steps to allow before aborting")
    parser.add_argument("--headless", action="store_true", default=True, 
                        help="Run browser in headless mode (default: True)")
    parser.add_argument("--headed", dest="headless", action="store_false", 
                        help="Run browser in headed mode (visible)")
    
    parser.add_argument("--visual-regression", action="store_true", 
                        help="Enable visual regression testing against baselines")
    parser.add_argument("--baseline-id", type=str, 
                        help="Run ID of the baseline to compare against (if visual regression enabled)")
                        
    parser.add_argument("--file-bugs", action="store_true", 
                        help="Automatically file High/Critical bugs to GitHub Issues (requires GITHUB_TOKEN)")
                        
    parser.add_argument("--fail-on-bug", action="store_true",
                        help="Exit with non-zero status if any bugs are detected (useful for breaking CI builds)")

    args = parser.parse_args()

    # Configure event loop for Windows compatibility if needed
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Run the orchestrator
    exit_code = asyncio.run(run_test(args))
    sys.exit(exit_code)


async def run_test(args) -> int:
    print(f"\n🚀 Starting Autonomous QA Agent")
    print(f"Goal: '{args.goal}'")
    print(f"Target: {args.url}")
    print(f"Device: {args.device} | Mode: {args.mode}")
    print("-" * 50)

    def on_step(payload):
        step = payload.get("step")
        msg = payload.get("message")
        status = payload.get("status")
        if msg:
            print(f"[Step {step}] {msg}")

    orchestrator = TestOrchestrator(
        headless=args.headless,
        max_steps=args.max_steps,
        on_step_callback=on_step
    )

    try:
        evaluation = await orchestrator.execute_test(
            goal=args.goal,
            target_url=args.url,
            mode=TestMode(args.mode),
            device_name=args.device,
            enable_visual_regression=args.visual_regression,
            baseline_run_id=args.baseline_id,
        )
        
        print("\n" + "=" * 50)
        print(f"✅ Audit Complete - Status: {evaluation.status.value}")
        print(f"Friction Score: {evaluation.friction_score}/100")
        print(f"Accessibility Score: {evaluation.accessibility_score}/100")
        
        # Display Bugs
        bugs = evaluation.bug_reports
        if bugs:
            print(f"\n🐞 Detected {len(bugs)} Bugs:")
            for bug in bugs:
                print(f"  - [{bug.severity.value}] {bug.title}")
                
            # GitHub Integration
            if args.file_bugs:
                print("\nFiling bugs to GitHub...")
                github = GitHubIntegration()
                filed = await github.file_critical_bugs(bugs)
                if filed:
                    print(f"Successfully filed {len(filed)} issues to GitHub.")
                else:
                    print("No issues were filed (check configuration or severity levels).")
        
        # Display CI artifacts location
        print(f"\n📊 Report available at: reports/{evaluation.run_id}.html")
        print(f"🎥 Session recording: sessions/{evaluation.session_recording_ref}.json")
        print("=" * 50 + "\n")

        # Determine exit code based on failure states
        if evaluation.status == TestStatus.FAILED:
            return 1
            
        if args.fail_on_bug and bugs:
            print("❌ Exiting with error code 2 due to detected bugs (--fail-on-bug is active).")
            return 2
            
        return 0

    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    main()
