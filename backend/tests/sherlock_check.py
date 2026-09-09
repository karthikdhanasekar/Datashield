"""Quick Sherlock + social-analyzer module check"""
import asyncio, sys
sys.path.insert(0, '/app')

async def main():
    # Test Sherlock (using sherlock_project)
    print("=== Sherlock (sherlock_project) ===")
    from app.osint.sherlock_adapter import check_username_sherlock
    results = await check_username_sherlock("testinghypothesis2", timeout_per_site=10)
    print(f"Findings: {len(results)}")
    for r in results[:3]:
        print(f"  [{r['severity'].upper()}] {r['source_title']}")

    # Test Social-Analyzer
    print("\n=== Social-Analyzer ===")
    from app.osint.social_analyzer_adapter import check_username_social_analyzer
    results2 = await check_username_social_analyzer("testinghypothesis2")
    print(f"Findings: {len(results2)}")
    for r in results2[:3]:
        print(f"  [{r['severity'].upper()}] {r['source_title']}")

asyncio.run(main())
