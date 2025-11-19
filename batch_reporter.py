"""
Batch Report Generator for Arize Phoenix

Generates time-windowed analytics reports for understanding platform usage.
Supports scheduled execution (cron) and multiple report types.

Report Types:
- session_summary: High-level platform usage overview
- conversation: Full transcript export as CSV
- cost: Cost tracking and optimization insights
- engagement: Usage patterns and behavior analysis
- top_sessions: Identify high-value or problematic sessions

Usage:
    # Python API
    from batch_reporter import BatchReporter
    reporter = BatchReporter()
    results = reporter.run_window("daily")

    # CLI
    python batch_reporter.py --window daily
    python batch_reporter.py --start "2025-11-18T00:00:00" --end "2025-11-19T00:00:00"
"""

import os
import json
import argparse
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

from session_analyzer import SessionAnalyzer, MODEL_PRICING

load_dotenv()


class BatchReporter:
    """
    Generate batch reports over time windows for platform analytics.

    Attributes:
        analyzer: SessionAnalyzer instance for data fetching
        output_dir: Directory for batch report output
    """

    # Predefined time windows
    TIME_WINDOWS = {
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
        "monthly": timedelta(days=30)
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        output_dir: str = "batch_outputs"
    ):
        """
        Initialize BatchReporter.

        Args:
            base_url: Phoenix server URL (defaults to PHOENIX_BASE_URL env var)
            api_key: Phoenix API key (defaults to PHOENIX_API_KEY env var)
            output_dir: Directory for batch outputs
        """
        self.output_dir = output_dir
        self.analyzer = SessionAnalyzer(
            base_url=base_url,
            api_key=api_key,
            output_dir=output_dir
        )

    def run_batch(
        self,
        start_time: datetime,
        end_time: datetime,
        reports: Optional[List[str]] = None,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run batch reports for a time window.

        Args:
            start_time: Start of time window
            end_time: End of time window
            reports: List of report types to generate. If None, generates all.
                    Options: ["session_summary", "conversation", "cost", "engagement", "top_sessions"]
            project_name: Phoenix project name

        Returns:
            Dict with results from each report type
        """
        all_reports = ["session_summary", "conversation", "cost", "engagement", "top_sessions"]
        reports = reports or all_reports

        # Create output directory for this batch
        batch_dir = self._create_batch_directory(start_time, end_time)

        results = {
            "batch_id": batch_dir.name,
            "time_window": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "reports": {}
        }

        # Fetch all data once for efficiency
        print(f"Fetching data for time window: {start_time} to {end_time}")
        df = self.analyzer.fetch_session_spans(
            start_time=start_time,
            end_time=end_time,
            project_name=project_name
        )

        if df.empty:
            results["message"] = "No data found for time window"
            self._save_manifest(batch_dir, results)
            return results

        session_count = df['attributes.session.id'].nunique() if 'attributes.session.id' in df.columns else (
            df['session.id'].nunique() if 'session.id' in df.columns else 'unknown'
        )
        print(f"Found {len(df)} spans across {session_count} sessions")

        # Normalize column names - handle both prefixed and unprefixed
        df = self._normalize_columns(df)

        # Generate requested reports
        report_methods = {
            "session_summary": self._session_summary_report,
            "conversation": self._conversation_export,
            "cost": self._cost_analysis_report,
            "engagement": self._engagement_report,
            "top_sessions": self._top_sessions_report
        }

        for report_name in reports:
            if report_name in report_methods:
                print(f"Generating {report_name} report...")
                try:
                    result = report_methods[report_name](df, batch_dir, start_time, end_time)
                    results["reports"][report_name] = result
                    print(f"  -> Completed {report_name}")
                except Exception as e:
                    results["reports"][report_name] = {"error": str(e)}
                    print(f"  -> Error in {report_name}: {e}")

        # Save batch manifest
        self._save_manifest(batch_dir, results)

        return results

    def run_window(
        self,
        window: str = "daily",
        reports: Optional[List[str]] = None,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run batch for a predefined time window ending now.

        Args:
            window: One of "hourly", "daily", "weekly", "monthly"
            reports: Report types to generate
            project_name: Phoenix project name

        Returns:
            Batch results
        """
        if window not in self.TIME_WINDOWS:
            raise ValueError(f"Unknown window: {window}. Options: {list(self.TIME_WINDOWS.keys())}")

        end_time = datetime.now()
        start_time = end_time - self.TIME_WINDOWS[window]

        return self.run_batch(start_time, end_time, reports, project_name)

    # -------------------------------------------------------------------------
    # Report Methods
    # -------------------------------------------------------------------------

    def _session_summary_report(
        self,
        df: pd.DataFrame,
        batch_dir: Path,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Generate session summary report."""
        summary = {
            "report_type": "session_summary",
            "time_window": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            }
        }

        # Session metrics
        if "session.id" in df.columns:
            sessions = df["session.id"].dropna().unique()
            summary["total_sessions"] = len(sessions)
        else:
            summary["total_sessions"] = 0

        # Trace metrics (conversations)
        if "context.trace_id" in df.columns:
            traces = df["context.trace_id"].dropna().unique()
            summary["total_traces"] = len(traces)
        else:
            summary["total_traces"] = 0

        # Total spans
        summary["total_spans"] = len(df)

        # Message count (AGENT spans typically contain user messages)
        if "span_kind" in df.columns:
            agent_spans = df[df["span_kind"] == "AGENT"]
            summary["total_user_interactions"] = len(agent_spans)
        else:
            summary["total_user_interactions"] = len(df)

        # Duration analysis
        if "start_time" in df.columns and "end_time" in df.columns:
            df_time = df.copy()
            if df_time["start_time"].dtype == "object":
                df_time["start_time"] = pd.to_datetime(df_time["start_time"])
            if df_time["end_time"].dtype == "object":
                df_time["end_time"] = pd.to_datetime(df_time["end_time"])

            if "session.id" in df.columns:
                session_durations = df_time.groupby("session.id").agg(
                    start=("start_time", "min"),
                    end=("end_time", "max")
                )
                session_durations["duration_minutes"] = (
                    (session_durations["end"] - session_durations["start"]).dt.total_seconds() / 60
                )

                summary["avg_session_duration_minutes"] = round(
                    session_durations["duration_minutes"].mean(), 2
                )
                summary["total_duration_minutes"] = round(
                    session_durations["duration_minutes"].sum(), 2
                )

        # Daily breakdown
        if "start_time" in df.columns:
            df_time = df.copy()
            if df_time["start_time"].dtype == "object":
                df_time["start_time"] = pd.to_datetime(df_time["start_time"])

            df_time["date"] = df_time["start_time"].dt.date.astype(str)
            daily_counts = df_time.groupby("date").size().to_dict()
            summary["spans_per_day"] = daily_counts

            if "session.id" in df.columns:
                daily_sessions = df_time.groupby("date")["session.id"].nunique().to_dict()
                summary["sessions_per_day"] = daily_sessions

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = batch_dir / f"session_summary_{timestamp}.json"

        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        # Save session list as CSV
        data_file = None
        if "session.id" in df.columns:
            agg_dict = {}
            if "context.span_id" in df.columns:
                agg_dict["span_count"] = ("context.span_id", "count")
            else:
                agg_dict["span_count"] = ("session.id", "count")

            if "start_time" in df.columns:
                agg_dict["first_activity"] = ("start_time", "min")
            if "end_time" in df.columns:
                agg_dict["last_activity"] = ("end_time", "max")

            if agg_dict:
                session_df = df.groupby("session.id").agg(**agg_dict).reset_index()
                data_file = batch_dir / f"session_summary_data_{timestamp}.csv"
                session_df.to_csv(data_file, index=False)

        return {
            "summary_file": str(summary_file),
            "data_file": str(data_file) if data_file else None,
            "metrics": summary
        }

    def _conversation_export(
        self,
        df: pd.DataFrame,
        batch_dir: Path,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Export conversations as CSV."""
        conversations = []

        for _, row in df.iterrows():
            conv = self.analyzer._extract_conversation_from_span(row)
            if conv["human"] or conv["ai"]:
                conversation_row = {
                    "session_id": row.get("session.id", "") if "session.id" in df.columns else "",
                    "trace_id": row.get("context.trace_id", "") if "context.trace_id" in df.columns else "",
                    "timestamp": row.get("start_time", "") if "start_time" in df.columns else "",
                    "human_message": conv["human"],
                    "ai_response": conv["ai"]
                }

                # Add metrics if available
                if "llm.model_name" in df.columns:
                    conversation_row["model"] = row.get("llm.model_name", "")
                if "llm.token_count.total" in df.columns:
                    conversation_row["tokens"] = row.get("llm.token_count.total", 0)

                conversations.append(conversation_row)

        # Create DataFrame
        conv_df = pd.DataFrame(conversations)

        # Save CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = batch_dir / f"conversations_{timestamp}.csv"
        conv_df.to_csv(csv_file, index=False)

        return {
            "csv_file": str(csv_file),
            "total_conversations": len(conv_df),
            "sessions_included": conv_df["session_id"].nunique() if "session_id" in conv_df.columns and len(conv_df) > 0 else 0
        }

    def _cost_analysis_report(
        self,
        df: pd.DataFrame,
        batch_dir: Path,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Generate cost analysis report."""
        summary = {
            "report_type": "cost_analysis",
            "time_window": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            }
        }

        # Token totals
        token_cols = {
            "prompt": "llm.token_count.prompt",
            "completion": "llm.token_count.completion",
            "total": "llm.token_count.total",
            "cache_read": "llm.token_count.prompt_details.cache_read"
        }

        tokens = {}
        for name, col in token_cols.items():
            if col in df.columns:
                tokens[f"total_{name}_tokens"] = int(pd.to_numeric(df[col], errors='coerce').fillna(0).sum())

        summary["tokens"] = tokens

        # Cost by model
        by_model = {}
        total_cost = 0

        if "llm.model_name" in df.columns:
            for model_name in df["llm.model_name"].dropna().unique():
                model_df = df[df["llm.model_name"] == model_name]

                prompt = pd.to_numeric(model_df.get("llm.token_count.prompt", pd.Series([0])), errors='coerce').fillna(0).sum()
                completion = pd.to_numeric(model_df.get("llm.token_count.completion", pd.Series([0])), errors='coerce').fillna(0).sum()

                cost = self.analyzer._estimate_cost(model_name, prompt, completion)
                total_cost += cost

                by_model[model_name] = {
                    "spans": len(model_df),
                    "prompt_tokens": int(prompt),
                    "completion_tokens": int(completion),
                    "cost_usd": round(cost, 4)
                }

        summary["total_cost_usd"] = round(total_cost, 4)
        summary["by_model"] = by_model

        # Cost by provider
        by_provider = {}
        if "llm.provider" in df.columns:
            for provider in df["llm.provider"].dropna().unique():
                provider_df = df[df["llm.provider"] == provider]
                provider_tokens = int(pd.to_numeric(provider_df.get("llm.token_count.total", pd.Series([0])), errors='coerce').fillna(0).sum())
                by_provider[provider] = {
                    "spans": len(provider_df),
                    "tokens": provider_tokens
                }

        summary["by_provider"] = by_provider

        # Cache efficiency
        cache_read = tokens.get("total_cache_read_tokens", 0)
        total_prompt = tokens.get("total_prompt_tokens", 0)

        if total_prompt > 0:
            cache_hit_rate = cache_read / total_prompt
        else:
            cache_hit_rate = 0

        # Estimate cache savings (cached tokens cost ~10% of normal)
        cache_savings = 0
        if "llm.model_name" in df.columns and cache_read > 0:
            for model_name in df["llm.model_name"].dropna().unique():
                model_df = df[df["llm.model_name"] == model_name]
                model_cache = pd.to_numeric(model_df.get("llm.token_count.prompt_details.cache_read", pd.Series([0])), errors='coerce').fillna(0).sum()
                pricing = MODEL_PRICING.get(model_name, {"prompt": 0})
                cache_savings += model_cache * pricing["prompt"] * 0.9

        summary["cache_efficiency"] = {
            "hit_rate": round(cache_hit_rate, 3),
            "cached_tokens": cache_read,
            "estimated_savings_usd": round(cache_savings, 4)
        }

        # Failed request costs
        if "status_code" in df.columns:
            failed_df = df[df["status_code"] != "OK"]
            failed_tokens = int(pd.to_numeric(failed_df.get("llm.token_count.total", pd.Series([0])), errors='coerce').fillna(0).sum())

            failed_cost = 0
            if "llm.model_name" in failed_df.columns:
                for model_name in failed_df["llm.model_name"].dropna().unique():
                    model_failed = failed_df[failed_df["llm.model_name"] == model_name]
                    prompt = pd.to_numeric(model_failed.get("llm.token_count.prompt", pd.Series([0])), errors='coerce').fillna(0).sum()
                    completion = pd.to_numeric(model_failed.get("llm.token_count.completion", pd.Series([0])), errors='coerce').fillna(0).sum()
                    failed_cost += self.analyzer._estimate_cost(model_name, prompt, completion)

            summary["failed_requests"] = {
                "count": len(failed_df),
                "wasted_tokens": failed_tokens,
                "wasted_cost_usd": round(failed_cost, 4)
            }

        # Cost by session
        data_file = None
        if "session.id" in df.columns:
            session_costs = []
            for session_id in df["session.id"].dropna().unique():
                session_df = df[df["session.id"] == session_id]
                session_cost = 0

                if "llm.model_name" in session_df.columns:
                    for model_name in session_df["llm.model_name"].dropna().unique():
                        model_session = session_df[session_df["llm.model_name"] == model_name]
                        prompt = pd.to_numeric(model_session.get("llm.token_count.prompt", pd.Series([0])), errors='coerce').fillna(0).sum()
                        completion = pd.to_numeric(model_session.get("llm.token_count.completion", pd.Series([0])), errors='coerce').fillna(0).sum()
                        session_cost += self.analyzer._estimate_cost(model_name, prompt, completion)

                session_costs.append({
                    "session_id": session_id,
                    "cost_usd": round(session_cost, 4),
                    "spans": len(session_df)
                })

            session_costs_df = pd.DataFrame(session_costs).sort_values("cost_usd", ascending=False)

            # Save session costs
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            data_file = batch_dir / f"cost_analysis_data_{timestamp}.csv"
            session_costs_df.to_csv(data_file, index=False)

        # Save summary
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = batch_dir / f"cost_analysis_{timestamp}.json"

        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        return {
            "summary_file": str(summary_file),
            "data_file": str(data_file) if data_file else None,
            "metrics": summary
        }

    def _engagement_report(
        self,
        df: pd.DataFrame,
        batch_dir: Path,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Generate user engagement report."""
        summary = {
            "report_type": "engagement",
            "time_window": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            }
        }

        # Temporal analysis
        if "start_time" in df.columns:
            df_time = df.copy()
            if df_time["start_time"].dtype == "object":
                df_time["start_time"] = pd.to_datetime(df_time["start_time"])

            # Hourly usage
            df_time["hour"] = df_time["start_time"].dt.hour
            hourly = df_time.groupby("hour").size().to_dict()
            summary["hourly_usage"] = {str(k): v for k, v in hourly.items()}

            # Peak hour
            if hourly:
                peak_hour = max(hourly, key=hourly.get)
                summary["peak_hour"] = f"{peak_hour:02d}:00"

            # Day of week usage
            df_time["day_of_week"] = df_time["start_time"].dt.day_name()
            daily = df_time.groupby("day_of_week").size().to_dict()
            summary["daily_usage"] = daily

        # Span type distribution
        if "span_kind" in df.columns:
            span_types = df["span_kind"].value_counts().to_dict()
            summary["span_type_distribution"] = span_types

        # Tool usage
        if "tool.name" in df.columns:
            tool_usage = df["tool.name"].dropna().value_counts().to_dict()
            summary["tool_usage"] = tool_usage

        # Model usage distribution
        if "llm.model_name" in df.columns:
            model_usage = df["llm.model_name"].dropna().value_counts().to_dict()
            summary["model_usage"] = model_usage

        # Session length distribution
        if "session.id" in df.columns:
            spans_per_session = df.groupby("session.id").size()
            summary["session_length_stats"] = {
                "min": int(spans_per_session.min()),
                "max": int(spans_per_session.max()),
                "mean": round(spans_per_session.mean(), 1),
                "median": int(spans_per_session.median())
            }

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = batch_dir / f"engagement_{timestamp}.json"

        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        return {
            "summary_file": str(summary_file),
            "metrics": summary
        }

    def _top_sessions_report(
        self,
        df: pd.DataFrame,
        batch_dir: Path,
        start_time: datetime,
        end_time: datetime,
        top_n: int = 10
    ) -> Dict[str, Any]:
        """Generate top sessions report."""
        if "session.id" not in df.columns:
            return {"error": "No session.id column found"}

        summary = {
            "report_type": "top_sessions",
            "time_window": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "top_n": top_n
        }

        # Calculate metrics per session
        session_metrics = []

        for session_id in df["session.id"].dropna().unique():
            session_df = df[df["session.id"] == session_id]

            metrics = {
                "session_id": session_id,
                "span_count": len(session_df)
            }

            # Cost
            cost = 0
            if "llm.model_name" in session_df.columns:
                for model_name in session_df["llm.model_name"].dropna().unique():
                    model_df = session_df[session_df["llm.model_name"] == model_name]
                    prompt = pd.to_numeric(model_df.get("llm.token_count.prompt", pd.Series([0])), errors='coerce').fillna(0).sum()
                    completion = pd.to_numeric(model_df.get("llm.token_count.completion", pd.Series([0])), errors='coerce').fillna(0).sum()
                    cost += self.analyzer._estimate_cost(model_name, prompt, completion)
            metrics["cost_usd"] = round(cost, 4)

            # Duration
            if "start_time" in session_df.columns and "end_time" in session_df.columns:
                start = pd.to_datetime(session_df["start_time"]).min()
                end = pd.to_datetime(session_df["end_time"]).max()
                metrics["duration_minutes"] = round((end - start).total_seconds() / 60, 2)

            # Tokens
            if "llm.token_count.total" in session_df.columns:
                metrics["total_tokens"] = int(pd.to_numeric(session_df["llm.token_count.total"], errors='coerce').fillna(0).sum())

            # Errors
            if "status_code" in session_df.columns:
                metrics["error_count"] = len(session_df[session_df["status_code"] != "OK"])

            session_metrics.append(metrics)

        metrics_df = pd.DataFrame(session_metrics)

        # Top by cost
        if "cost_usd" in metrics_df.columns and len(metrics_df) > 0:
            top_by_cost = metrics_df.nlargest(top_n, "cost_usd")[["session_id", "cost_usd"]].to_dict("records")
            summary["top_by_cost"] = top_by_cost

        # Top by duration
        if "duration_minutes" in metrics_df.columns and len(metrics_df) > 0:
            top_by_duration = metrics_df.nlargest(top_n, "duration_minutes")[["session_id", "duration_minutes"]].to_dict("records")
            summary["top_by_duration"] = top_by_duration

        # Top by tokens
        if "total_tokens" in metrics_df.columns and len(metrics_df) > 0:
            top_by_tokens = metrics_df.nlargest(top_n, "total_tokens")[["session_id", "total_tokens"]].to_dict("records")
            summary["top_by_tokens"] = top_by_tokens

        # Sessions with errors
        if "error_count" in metrics_df.columns and len(metrics_df) > 0:
            with_errors = metrics_df[metrics_df["error_count"] > 0].nlargest(top_n, "error_count")[["session_id", "error_count"]].to_dict("records")
            summary["sessions_with_errors"] = with_errors

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = batch_dir / f"top_sessions_{timestamp}.json"

        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        # Save full metrics
        data_file = batch_dir / f"top_sessions_data_{timestamp}.csv"
        metrics_df.to_csv(data_file, index=False)

        return {
            "summary_file": str(summary_file),
            "data_file": str(data_file),
            "metrics": summary
        }

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names by removing 'attributes.' prefix.

        When fetching ALL attributes (no .select()), columns have 'attributes.' prefix.
        This normalizes them to match the unprefixed format used elsewhere.
        """
        rename_map = {}
        for col in df.columns:
            if col.startswith("attributes."):
                new_name = col.replace("attributes.", "", 1)
                rename_map[col] = new_name

        if rename_map:
            df = df.rename(columns=rename_map)

        return df

    def _create_batch_directory(self, start_time: datetime, end_time: datetime) -> Path:
        """Create output directory for this batch."""
        # Name based on date range
        start_str = start_time.strftime("%Y-%m-%d")
        end_str = end_time.strftime("%Y-%m-%d")

        if start_str == end_str:
            dir_name = f"{start_str}_batch"
        else:
            dir_name = f"{start_str}_to_{end_str}_batch"

        batch_dir = Path(self.output_dir) / dir_name
        batch_dir.mkdir(parents=True, exist_ok=True)

        return batch_dir

    def _save_manifest(self, batch_dir: Path, results: Dict[str, Any]):
        """Save batch manifest with all report metadata."""
        manifest_file = batch_dir / "batch_manifest.json"

        with open(manifest_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """CLI entry point for batch report generation."""
    parser = argparse.ArgumentParser(
        description="Generate batch analytics reports from Arize Phoenix"
    )

    parser.add_argument(
        "--window",
        choices=["hourly", "daily", "weekly", "monthly"],
        default="daily",
        help="Predefined time window (default: daily)"
    )

    parser.add_argument(
        "--start",
        type=str,
        help="Custom start time (ISO format: 2025-11-18T00:00:00)"
    )

    parser.add_argument(
        "--end",
        type=str,
        help="Custom end time (ISO format: 2025-11-19T00:00:00)"
    )

    parser.add_argument(
        "--reports",
        type=str,
        help="Comma-separated list of reports: session_summary,conversation,cost,engagement,top_sessions"
    )

    parser.add_argument(
        "--project",
        type=str,
        help="Phoenix project name"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="batch_outputs",
        help="Output directory for reports"
    )

    args = parser.parse_args()

    # Parse reports
    reports = None
    if args.reports:
        reports = [r.strip() for r in args.reports.split(",")]

    # Initialize reporter
    reporter = BatchReporter(output_dir=args.output_dir)

    # Run batch
    if args.start and args.end:
        # Custom time window
        start_time = datetime.fromisoformat(args.start)
        end_time = datetime.fromisoformat(args.end)
        results = reporter.run_batch(start_time, end_time, reports, args.project)
    else:
        # Predefined window
        results = reporter.run_window(args.window, reports, args.project)

    # Print summary
    print("\n" + "="*60)
    print("BATCH REPORT COMPLETE")
    print("="*60)
    print(f"Batch ID: {results['batch_id']}")
    print(f"Time Window: {results['time_window']['start']} to {results['time_window']['end']}")

    if "message" in results:
        print(f"\nMessage: {results['message']}")

    if "reports" in results:
        print("\nGenerated Reports:")
        for name, data in results["reports"].items():
            if "error" in data:
                print(f"  {name}: ERROR - {data['error']}")
            else:
                print(f"  {name}: OK")
                if "summary_file" in data:
                    print(f"    -> {data['summary_file']}")

    print("\nManifest saved to batch directory")


if __name__ == "__main__":
    main()
