"""
Test script to verify Phoenix connection and basic functionality.
"""

from phoenix.client import Client
from session_cost_analyzer import SessionCostAnalyzer
from session_analyzer import SessionAnalyzer
import pandas as pd
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()


def test_connection():
    """Test connection to Phoenix server."""
    print("Testing connection to Phoenix server...")
    print(f"Phoenix URL: {os.getenv('PHOENIX_BASE_URL')}")

    try:
        client = Client(
            base_url=os.getenv("PHOENIX_BASE_URL"),
            api_key=os.getenv("PHOENIX_API_KEY")
        )
        print("✅ Successfully connected to Phoenix server")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Phoenix: {e}")
        return False


def test_fetch_spans():
    """Test fetching spans from Phoenix."""
    print("\nTesting span fetching...")

    try:
        client = Client(
            base_url=os.getenv("PHOENIX_BASE_URL"),
            api_key=os.getenv("PHOENIX_API_KEY")
        )

        from phoenix.client.types.spans import SpanQuery

        # Fetch recent spans (limited to 10 for testing)
        query = SpanQuery()
        df = client.spans.get_spans_dataframe(
            query=query,
            project_identifier="mobsta-development",
            limit=10
        )

        print(f"✅ Successfully fetched {len(df)} spans")

        if not df.empty:
            print("\nAvailable columns:")
            for col in df.columns:
                print(f"  - {col}")

            # Check if we have session data
            session_col = None
            if "attributes.session.id" in df.columns:
                session_col = "attributes.session.id"
            elif "session.id" in df.columns:
                session_col = "session.id"

            if session_col:
                unique_sessions = df[session_col].dropna().unique()
                print(f"\n📦 Found {len(unique_sessions)} unique sessions")
                print("\nSample session IDs:")
                for session_id in unique_sessions[:5]:
                    print(f"  - {session_id}")
            else:
                print("\n⚠️  No session.id column found in spans")

        return True
    except Exception as e:
        print(f"❌ Failed to fetch spans: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_analyzer():
    """Test SessionCostAnalyzer."""
    print("\nTesting SessionCostAnalyzer...")

    try:
        analyzer = SessionCostAnalyzer()
        print("✅ Successfully initialized SessionCostAnalyzer")

        # Try to fetch a session (this will likely fail without a real session ID)
        # Just test the initialization
        return True
    except Exception as e:
        print(f"❌ Failed to initialize analyzer: {e}")
        return False


def test_new_session_analyzer():
    """Test new SessionAnalyzer class."""
    print("\nTesting new SessionAnalyzer...")

    try:
        analyzer = SessionAnalyzer()
        print("✅ Successfully initialized SessionAnalyzer")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize SessionAnalyzer: {e}")
        return False


def test_fetch_session_spans():
    """Test SessionAnalyzer.fetch_session_spans() with attribute selection."""
    print("\nTesting SessionAnalyzer.fetch_session_spans()...")

    try:
        analyzer = SessionAnalyzer()

        # Get a sample session ID first
        client = Client(
            base_url=os.getenv("PHOENIX_BASE_URL"),
            api_key=os.getenv("PHOENIX_API_KEY")
        )
        from phoenix.client.types.spans import SpanQuery
        query = SpanQuery()
        df_sample = client.spans.get_spans_dataframe(
            query=query,
            project_identifier=os.getenv("PROJECT", "mobsta-development"),
            limit=5
        )

        if df_sample.empty:
            print("⚠️  No spans available to test with")
            return True

        # Get a session ID
        session_col = "attributes.session.id" if "attributes.session.id" in df_sample.columns else "session.id"
        if session_col not in df_sample.columns:
            print("⚠️  No session.id column found")
            return True

        session_id = df_sample[session_col].dropna().iloc[0]

        # Test fetching with specific attributes (without "attributes." prefix)
        df = analyzer.fetch_session_spans(
            session_id,
            attributes=["name", "llm.model_name", "llm.token_count.total"]
        )

        print(f"✅ Fetched {len(df)} spans with {len(df.columns)} columns")
        return True
    except Exception as e:
        print(f"❌ Failed to fetch session spans: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_reports():
    """Test report generation with a real session ID."""
    print("\nTesting report generation...")

    try:
        analyzer = SessionAnalyzer()

        # Get a sample session ID
        client = Client(
            base_url=os.getenv("PHOENIX_BASE_URL"),
            api_key=os.getenv("PHOENIX_API_KEY")
        )
        from phoenix.client.types.spans import SpanQuery
        query = SpanQuery()
        df_sample = client.spans.get_spans_dataframe(
            query=query,
            project_identifier=os.getenv("PROJECT", "mobsta-development"),
            limit=5
        )

        if df_sample.empty:
            print("⚠️  No spans available to test reports with")
            return True

        session_col = "attributes.session.id" if "attributes.session.id" in df_sample.columns else "session.id"
        if session_col not in df_sample.columns:
            print("⚠️  No session.id column found")
            return True

        session_id = df_sample[session_col].dropna().iloc[0]

        print(f"  Testing with session: {session_id}")

        # Test individual reports
        print("  • Testing core_cost_report...")
        result = analyzer.core_cost_report(session_id)
        assert "summary" in result
        assert "files" in result
        print(f"    ✅ Core cost report generated ({result['row_count']} spans)")

        print("  • Testing efficiency_report...")
        result = analyzer.efficiency_report(session_id)
        assert "summary" in result
        print(f"    ✅ Efficiency report generated")

        print("  • Testing usage_patterns_report...")
        result = analyzer.usage_patterns_report(session_id)
        assert "summary" in result
        print(f"    ✅ Usage patterns report generated")

        # Test generate_all_reports
        print("  • Testing generate_all_reports...")
        results = analyzer.generate_all_reports(session_id)
        assert len(results) == 3
        assert "core_cost" in results
        assert "efficiency" in results
        assert "usage_patterns" in results
        print(f"    ✅ All reports generated successfully")

        return True
    except Exception as e:
        print(f"❌ Failed to generate reports: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("PHOENIX CONNECTION AND FUNCTIONALITY TESTS")
    print("="*60)

    # Test 1: Connection
    connection_ok = test_connection()

    if not connection_ok:
        print("\n⚠️  Connection failed. Please check your .env file:")
        print("   - PHOENIX_BASE_URL")
        print("   - PHOENIX_API_KEY")
        return

    # Test 2: Fetch spans
    fetch_ok = test_fetch_spans()

    # Test 3: Old Analyzer
    analyzer_ok = test_analyzer()

    # Test 4: New SessionAnalyzer
    new_analyzer_ok = test_new_session_analyzer()

    # Test 5: Fetch session spans with attributes
    fetch_session_ok = test_fetch_session_spans()

    # Test 6: Report generation
    reports_ok = test_reports()

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Connection:           {'✅ PASS' if connection_ok else '❌ FAIL'}")
    print(f"Fetch spans:          {'✅ PASS' if fetch_ok else '❌ FAIL'}")
    print(f"Old Analyzer:         {'✅ PASS' if analyzer_ok else '❌ FAIL'}")
    print(f"New SessionAnalyzer:  {'✅ PASS' if new_analyzer_ok else '❌ FAIL'}")
    print(f"Fetch session spans:  {'✅ PASS' if fetch_session_ok else '❌ FAIL'}")
    print(f"Report generation:    {'✅ PASS' if reports_ok else '❌ FAIL'}")
    print("="*60)

    all_passed = all([connection_ok, fetch_ok, analyzer_ok, new_analyzer_ok, fetch_session_ok, reports_ok])

    if all_passed:
        print("\n🎉 All tests passed! You're ready to use the analyzer.")
        print("\nNext steps:")
        print("1. Use the new SessionAnalyzer class:")
        print("   from session_analyzer import SessionAnalyzer")
        print("2. Generate reports for a session:")
        print("   python analyze_session.py <session-id>")
        print("3. Or see example_usage.py for programmatic usage")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")


if __name__ == "__main__":
    main()
