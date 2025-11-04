"""
Example usage of SessionAnalyzer

This script demonstrates how to use the new SessionAnalyzer to generate
comprehensive cost and usage analytics for Phoenix sessions.

Features demonstrated:
- Fetching session spans with flexible attribute selection
- Generating individual report types (core cost, efficiency, usage patterns)
- Using the generate_all_reports() convenience method
- Custom analysis on fetched dataframes
"""

from session_analyzer import SessionAnalyzer


def example_1_generate_all_reports():
    """Example 1: Generate all three report types for a session."""
    print("="*80)
    print("EXAMPLE 1: Generate All Reports")
    print("="*80)

    # Replace with your actual session ID
    session_id = "postman-31bf6ed1-9b9b-4e48-a0a4-7b408f03cf25"

    try:
        analyzer = SessionAnalyzer()

        # Generate all reports at once
        print(f"\nAnalyzing session: {session_id}")
        results = analyzer.generate_all_reports(session_id)

        # Display summary from each report
        print("\n📊 REPORT SUMMARY")
        print("-"*80)

        # Core Cost Report
        core_cost = results["core_cost"]["summary"]
        cost_est = core_cost.get("cost_estimate", {})
        print(f"\n💰 Core Cost Metrics:")
        print(f"  Total Cost: ${cost_est.get('total_cost_usd', 0):.4f}")
        print(f"  Total Tokens: {core_cost.get('total_tokens', 0):,}")
        print(f"  Spans: {core_cost.get('span_count', 0)}")

        # Efficiency Report
        efficiency = results["efficiency"]["summary"]
        cache_eff = efficiency.get("cache_efficiency", {})
        print(f"\n⚡ Efficiency Metrics:")
        print(f"  Cache Hit Rate: {cache_eff.get('cache_hit_rate', 0):.1%}")
        print(f"  Cache Savings: ${cache_eff.get('estimated_savings_usd', 0):.4f}")
        print(f"  Cost per Token: ${efficiency.get('cost_per_token', 0):.6f}")

        # Usage Patterns Report
        usage = results["usage_patterns"]["summary"]
        by_type = usage.get("by_span_type", {})
        print(f"\n📦 Usage Patterns:")
        for span_type, data in by_type.items():
            print(f"  {span_type}: {data['count']} spans, {data['tokens']:,} tokens")

        print(f"\n✅ All reports saved to outputs/{session_id}/")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure to replace 'your-session-id-here' with an actual session ID")


def example_2_individual_reports():
    """Example 2: Generate individual report types."""
    print("\n" + "="*80)
    print("EXAMPLE 2: Generate Individual Reports")
    print("="*80)

    session_id = "your-session-id-here"

    try:
        analyzer = SessionAnalyzer()

        # Generate just the core cost report
        print(f"\nGenerating core cost report for: {session_id}")
        result = analyzer.core_cost_report(session_id)

        summary = result["summary"]
        print(f"\n💰 Total Cost: ${summary['cost_estimate']['total_cost_usd']:.4f}")
        print(f"📊 Total Tokens: {summary['total_tokens']:,}")

        # Show cost breakdown by model
        if summary.get("by_model"):
            print("\nCost by Model:")
            for model, data in summary["by_model"].items():
                print(f"  • {model}: ${data['cost_usd']:.4f} ({data['tokens']:,} tokens)")

        print(f"\nReport saved to: {result['files']['summary_file']}")

    except Exception as e:
        print(f"❌ Error: {e}")


def example_3_fetch_custom_attributes():
    """Example 3: Fetch spans with custom attributes for analysis."""
    print("\n" + "="*80)
    print("EXAMPLE 3: Custom Span Fetching")
    print("="*80)

    session_id = "your-session-id-here"

    try:
        analyzer = SessionAnalyzer()

        # Fetch specific attributes only (without "attributes." prefix)
        print(f"\nFetching custom attributes for: {session_id}")
        df = analyzer.fetch_session_spans(
            session_id,
            attributes=[
                "name",
                "llm.model_name",
                "llm.token_count.total",
                "llm.token_count.prompt",
                "llm.token_count.completion",
                "start_time",
                "end_time"
            ]
        )

        print(f"\n✅ Fetched {len(df)} spans with {len(df.columns)} columns")

        # Perform custom analysis (DataFrame columns are unprefixed when using .select())
        if not df.empty and "llm.token_count.total" in df.columns:
            total_tokens = df["llm.token_count.total"].sum()
            avg_tokens = df["llm.token_count.total"].mean()

            print(f"\nCustom Analysis:")
            print(f"  Total tokens: {total_tokens:,.0f}")
            print(f"  Average tokens per span: {avg_tokens:.0f}")

            # Find most expensive span
            if "name" in df.columns:
                max_idx = df["llm.token_count.total"].idxmax()
                max_span = df.loc[max_idx]
                print(f"  Most expensive span: {max_span['name']} ({max_span['llm.token_count.total']:,.0f} tokens)")

    except Exception as e:
        print(f"❌ Error: {e}")


def example_4_compare_sessions():
    """Example 4: Compare multiple sessions."""
    print("\n" + "="*80)
    print("EXAMPLE 4: Compare Multiple Sessions")
    print("="*80)

    # Replace with your actual session IDs
    session_ids = [
        "session-1",
        "session-2",
        "session-3"
    ]

    try:
        analyzer = SessionAnalyzer()

        print(f"\nComparing {len(session_ids)} sessions...\n")

        comparison_data = []

        for session_id in session_ids:
            # Generate core cost report for each session
            result = analyzer.core_cost_report(session_id)
            summary = result["summary"]

            comparison_data.append({
                "session_id": session_id[:30],
                "cost": summary["cost_estimate"]["total_cost_usd"],
                "tokens": summary["total_tokens"],
                "spans": summary["span_count"]
            })

        # Display comparison table
        print(f"{'Session ID':32} {'Cost':>12} {'Tokens':>12} {'Spans':>8}")
        print("-"*70)

        for data in comparison_data:
            print(f"{data['session_id']:32} ${data['cost']:11.4f} {data['tokens']:12,} {data['spans']:8}")

        # Totals
        total_cost = sum(d["cost"] for d in comparison_data)
        total_tokens = sum(d["tokens"] for d in comparison_data)
        total_spans = sum(d["spans"] for d in comparison_data)

        print("-"*70)
        print(f"{'TOTAL':32} ${total_cost:11.4f} {total_tokens:12,} {total_spans:8}")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")


def example_5_fetch_all_attributes():
    """Example 5: Fetch all available attributes."""
    print("\n" + "="*80)
    print("EXAMPLE 5: Fetch All Attributes")
    print("="*80)

    session_id = "your-session-id-here"

    try:
        analyzer = SessionAnalyzer()

        # Fetch ALL columns by not specifying attributes
        print(f"\nFetching all available attributes for: {session_id}")
        df = analyzer.fetch_session_spans(session_id)  # No attributes = fetch all

        print(f"\n✅ Fetched {len(df)} spans")
        print(f"\nAvailable columns ({len(df.columns)} total):")
        for col in sorted(df.columns)[:20]:  # Show first 20
            print(f"  • {col}")

        if len(df.columns) > 20:
            print(f"  ... and {len(df.columns) - 20} more columns")

        # Can now perform any custom pandas analysis
        print(f"\nDataframe shape: {df.shape}")

    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Run all examples."""
    print("\n" + "🚀 " + "="*76)
    print("SESSION ANALYZER - EXAMPLE USAGE")
    print("="*78 + " 🚀\n")

    # Run Example 1: Generate all reports
    example_1_generate_all_reports()

    # Run Example 2: Individual reports
    # Uncomment to run:
    # example_2_individual_reports()

    # Run Example 3: Custom attribute fetching
    # Uncomment to run:
    # example_3_fetch_custom_attributes()

    # Run Example 4: Compare sessions
    # Uncomment to run:
    # example_4_compare_sessions()

    # Run Example 5: Fetch all attributes
    # Uncomment to run:
    # example_5_fetch_all_attributes()

    print("\n" + "="*80)
    print("💡 TIP: Edit the session IDs in this file to analyze your own sessions")
    print("="*80)


if __name__ == "__main__":
    main()
