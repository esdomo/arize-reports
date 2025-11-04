"""
Session Analyzer for Arize Phoenix - Product Analytics Tool

This module provides comprehensive cost and usage analytics for user sessions tracked in Arize Phoenix.
Designed for product analytics with three pre-defined report types:
- Core Cost Metrics: Total costs, by model/provider, token breakdowns
- Efficiency & Optimization: Cache efficiency, cost-per-token, failure analysis
- Usage Patterns: Cost by span type, tool usage, temporal trends

Attributes per span:

  - name
  - span_kind
  - parent_id
  - start_time
  - end_time
  - status_code
  - status_message
  - events
  - context.span_id
  - context.trace_id
  - attributes.input.value
  - attributes.input.mime_type
  - attributes.output.value
  - attributes.output.mime_type
  - attributes.metadata
  - attributes.llm.invocation_parameters
  - attributes.llm.input_messages
  - attributes.llm.output_messages
  - attributes.llm.model_name
  - attributes.llm.system
  - attributes.llm.provider
  - attributes.llm.tools
  - attributes.llm.token_count.prompt
  - attributes.llm.token_count.prompt_details.cache_read
  - attributes.llm.token_count.completion_details.reasoning
  - attributes.llm.token_count.total
  - attributes.llm.token_count.completion
  - attributes.llm.token_count.completion_details.audio
  - attributes.llm.token_count.prompt_details.audio
  - attributes.openinference.span.kind
  - attributes.session.id
  - attributes.tool.description
  - attributes.tool.name

"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from phoenix.client import Client
from phoenix.client.types.spans import SpanQuery
import pandas as pd


# Load environment variables from .env file
load_dotenv()



# Standard model pricing (fallback when Phoenix doesn't provide costs)
MODEL_PRICING = {
    "gpt-4": {"prompt": 0.03 / 1000, "completion": 0.06 / 1000},
    "gpt-4-turbo": {"prompt": 0.01 / 1000, "completion": 0.03 / 1000},
    "gpt-4-turbo-preview": {"prompt": 0.01 / 1000, "completion": 0.03 / 1000},
    "gpt-4o": {"prompt": 0.00125 / 1000, "completion": 0.01 / 1000},
    "gpt-4o-2024-08-06": {"prompt": 0.00375 / 1000, "completion": 0.015 / 1000},
    "gpt-4o-mini": {"prompt": 0.00015 / 1000, "completion": 0.0006 / 1000},
    "gpt-3.5-turbo": {"prompt": 0.0005 / 1000, "completion": 0.0015 / 1000},
    "claude-3-opus-20240229": {"prompt": 0.015 / 1000, "completion": 0.075 / 1000},
    "claude-3-sonnet-20240229": {"prompt": 0.003 / 1000, "completion": 0.015 / 1000},
    "claude-3-5-sonnet-20241022": {"prompt": 0.003 / 1000, "completion": 0.015 / 1000},
    "claude-3-haiku-20240307": {"prompt": 0.00025 / 1000, "completion": 0.00125 / 1000},
}


class SessionAnalyzer:
    """
    Comprehensive session analytics for Arize Phoenix.

    Provides flexible span data fetching and three pre-defined report types
    for product cost analysis.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        output_dir: str = "outputs"
    ):
        """
        Initialize the Session Analyzer.

        Args:
            base_url: Phoenix server URL (defaults to PHOENIX_BASE_URL env var)
            api_key: Phoenix API key (defaults to PHOENIX_API_KEY env var)
            output_dir: Directory to store analysis reports (default: "outputs")
        """
        self.base_url = base_url or os.getenv("PHOENIX_BASE_URL")
        self.api_key = api_key or os.getenv("PHOENIX_API_KEY")
        self.output_dir = output_dir

        if not self.base_url:
            raise ValueError("PHOENIX_BASE_URL must be set in .env or passed as base_url")
        if not self.api_key:
            raise ValueError("PHOENIX_API_KEY must be set in .env or passed as api_key")

        self.client = Client(
            base_url=self.base_url,
            api_key=self.api_key
        )

    def fetch_session_spans(
        self,
        session_id: str,
        attributes: Optional[List[str]] = None,
        project_name: Optional[str] = None,
        limit: int = 10000
    ) -> pd.DataFrame:
        """
        Fetch spans for a specific session from Phoenix.

        Args:
            session_id: The session ID to fetch spans for
            attributes: Optional list of attributes to select. If None, fetches ALL columns.
            project_name: Phoenix project name (defaults to PROJECT env var, or "default")
            limit: Maximum number of spans to fetch (default: 10000)

        Returns:
            pandas DataFrame with requested span data
        """
        query = SpanQuery().where(f"session.id == '{session_id}'")

        if attributes:
            query = query.select(*attributes)
        # If attributes=None, Phoenix returns all available columns

        df = self.client.spans.get_spans_dataframe(
            query=query,
            project_identifier=project_name or os.getenv("PROJECT", "default"),
            limit=limit
        )

        return df

    def core_cost_report(
        self,
        session_id: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Core Cost Metrics report.

        Includes: Total costs, cost by model/provider, token breakdowns.

        Args:
            session_id: Session to analyze
            project_name: Phoenix project name (optional)

        Returns:
            Dict containing summary metrics and file paths
        """
        # Fetch required attributes (without "attributes." prefix for query)
        attributes = [
            "context.span_id",
            "name",
            "llm.model_name",
            "llm.provider",
            "llm.token_count.prompt",
            "llm.token_count.completion",
            "llm.token_count.total",
            "session.id"
        ]

        df = self.fetch_session_spans(session_id, attributes, project_name)

        if df.empty:
            return self._empty_report(session_id, "core_cost")

        # Calculate metrics (column names are unprefixed when using .select())
        total_tokens = self._safe_sum(df, "llm.token_count.total")
        total_prompt_tokens = self._safe_sum(df, "llm.token_count.prompt")
        total_completion_tokens = self._safe_sum(df, "llm.token_count.completion")

        # Cost by model
        by_model = {}
        if "llm.model_name" in df.columns:
            for model_name in df["llm.model_name"].dropna().unique():
                model_df = df[df["llm.model_name"] == model_name]
                prompt_tokens = self._safe_sum(model_df, "llm.token_count.prompt")
                completion_tokens = self._safe_sum(model_df, "llm.token_count.completion")

                by_model[model_name] = {
                    "spans": len(model_df),
                    "tokens": int(self._safe_sum(model_df, "llm.token_count.total")),
                    "prompt": int(prompt_tokens),
                    "completion": int(completion_tokens),
                    "cost_usd": self._estimate_cost(model_name, prompt_tokens, completion_tokens)
                }

        # Cost by provider
        by_provider = {}
        if "llm.provider" in df.columns:
            for provider in df["llm.provider"].dropna().unique():
                provider_df = df[df["llm.provider"] == provider]
                by_provider[provider] = {
                    "spans": len(provider_df),
                    "tokens": int(self._safe_sum(provider_df, "llm.token_count.total")),
                    "prompt": int(self._safe_sum(provider_df, "llm.token_count.prompt")),
                    "completion": int(self._safe_sum(provider_df, "llm.token_count.completion"))
                }

        # Calculate total cost
        total_cost = sum(model_data["cost_usd"] for model_data in by_model.values())

        summary = {
            "session_id": session_id,
            "report_type": "core_cost",
            "timestamp": datetime.now().isoformat(),
            "span_count": len(df),
            "total_tokens": int(total_tokens),
            "total_prompt_tokens": int(total_prompt_tokens),
            "total_completion_tokens": int(total_completion_tokens),
            "by_model": by_model,
            "by_provider": by_provider,
            "cost_estimate": {
                "note": "Calculated using standard pricing",
                "total_cost_usd": round(total_cost, 4),
                "by_model": {model: data["cost_usd"] for model, data in by_model.items()}
            }
        }

        # Save report
        files = self._save_report(session_id, "core_cost", summary, df)

        return {
            "session_id": session_id,
            "report_type": "core_cost",
            "timestamp": summary["timestamp"],
            "summary": summary,
            "files": files,
            "row_count": len(df)
        }

    def efficiency_report(
        self,
        session_id: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Efficiency & Optimization report.

        Includes: Cache efficiency, cost-per-token, failure analysis.

        Args:
            session_id: Session to analyze
            project_name: Phoenix project name (optional)

        Returns:
            Dict containing summary metrics and file paths
        """
        # Fetch required attributes (without "attributes." prefix for query)
        attributes = [
            "context.span_id",
            "name",
            "status_code",
            "status_message",
            "llm.model_name",
            "llm.token_count.prompt",
            "llm.token_count.prompt_details.cache_read",
            "llm.token_count.completion",
            "llm.token_count.total",
            "session.id"
        ]

        df = self.fetch_session_spans(session_id, attributes, project_name)

        if df.empty:
            return self._empty_report(session_id, "efficiency")

        # Cache efficiency (column names are unprefixed when using .select())
        total_prompt_tokens = self._safe_sum(df, "llm.token_count.prompt")
        cache_read_tokens = self._safe_sum(df, "llm.token_count.prompt_details.cache_read")
        cache_hit_rate = (cache_read_tokens / total_prompt_tokens) if total_prompt_tokens > 0 else 0

        # Estimate cache savings (cache reads cost ~10% of regular prompt tokens)
        cache_savings = 0
        if "llm.model_name" in df.columns and cache_read_tokens > 0:
            for model_name in df["llm.model_name"].dropna().unique():
                model_df = df[df["llm.model_name"] == model_name]
                model_cache_tokens = self._safe_sum(model_df, "llm.token_count.prompt_details.cache_read")
                pricing = MODEL_PRICING.get(model_name, {"prompt": 0})
                cache_savings += model_cache_tokens * pricing["prompt"] * 0.9  # 90% savings

        # Cost per token
        total_tokens = self._safe_sum(df, "llm.token_count.total")
        total_cost = 0
        if "llm.model_name" in df.columns:
            for model_name in df["llm.model_name"].dropna().unique():
                model_df = df[df["llm.model_name"] == model_name]
                prompt_tokens = self._safe_sum(model_df, "llm.token_count.prompt")
                completion_tokens = self._safe_sum(model_df, "llm.token_count.completion")
                total_cost += self._estimate_cost(model_name, prompt_tokens, completion_tokens)

        cost_per_token = (total_cost / total_tokens) if total_tokens > 0 else 0

        # Failure analysis
        failed_spans = []
        if "status_code" in df.columns:
            failed_df = df[df["status_code"] != "OK"]
            failed_spans = failed_df["context.span_id"].tolist() if "context.span_id" in failed_df.columns else []
            wasted_tokens = self._safe_sum(failed_df, "llm.token_count.total")

            # Calculate wasted cost
            wasted_cost = 0
            if "llm.model_name" in failed_df.columns:
                for model_name in failed_df["llm.model_name"].dropna().unique():
                    model_failed_df = failed_df[failed_df["llm.model_name"] == model_name]
                    prompt_tokens = self._safe_sum(model_failed_df, "llm.token_count.prompt")
                    completion_tokens = self._safe_sum(model_failed_df, "llm.token_count.completion")
                    wasted_cost += self._estimate_cost(model_name, prompt_tokens, completion_tokens)
        else:
            wasted_tokens = 0
            wasted_cost = 0

        summary = {
            "session_id": session_id,
            "report_type": "efficiency",
            "timestamp": datetime.now().isoformat(),
            "cache_efficiency": {
                "total_prompt_tokens": int(total_prompt_tokens),
                "cache_read_tokens": int(cache_read_tokens),
                "cache_hit_rate": round(cache_hit_rate, 3),
                "estimated_savings_usd": round(cache_savings, 4)
            },
            "cost_per_token": round(cost_per_token, 8),
            "failure_analysis": {
                "failed_spans": len(failed_spans),
                "failed_span_ids": failed_spans[:10],  # Limit to first 10
                "wasted_tokens": int(wasted_tokens),
                "wasted_cost_estimate_usd": round(wasted_cost, 4)
            }
        }

        # Save report
        files = self._save_report(session_id, "efficiency", summary, df)

        return {
            "session_id": session_id,
            "report_type": "efficiency",
            "timestamp": summary["timestamp"],
            "summary": summary,
            "files": files,
            "row_count": len(df)
        }

    def usage_patterns_report(
        self,
        session_id: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Usage Patterns report.

        Includes: Cost by span type, tool usage, temporal analysis.

        Args:
            session_id: Session to analyze
            project_name: Phoenix project name (optional)

        Returns:
            Dict containing summary metrics and file paths
        """
        # Fetch required attributes (without "attributes." prefix for query)
        attributes = [
            "context.span_id",
            "name",
            "span_kind",
            "start_time",
            "end_time",
            "tool.name",
            "llm.model_name",
            "llm.token_count.total",
            "session.id"
        ]

        df = self.fetch_session_spans(session_id, attributes, project_name)

        if df.empty:
            return self._empty_report(session_id, "usage_patterns")

        # By span type (column names are unprefixed when using .select())
        by_span_type = {}
        if "span_kind" in df.columns:
            for span_kind in df["span_kind"].dropna().unique():
                kind_df = df[df["span_kind"] == span_kind]
                total_tokens = self._safe_sum(kind_df, "llm.token_count.total")
                by_span_type[span_kind] = {
                    "count": len(kind_df),
                    "tokens": int(total_tokens),
                    "avg_tokens_per_span": round(total_tokens / len(kind_df), 1) if len(kind_df) > 0 else 0
                }

        # Tool usage
        tool_usage = {}
        if "tool.name" in df.columns:
            for tool_name in df["tool.name"].dropna().unique():
                tool_df = df[df["tool.name"] == tool_name]
                tool_usage[tool_name] = {
                    "invocations": len(tool_df)
                }

        # Temporal analysis
        temporal_analysis = {}
        if "start_time" in df.columns and "end_time" in df.columns:
            df_time = df.dropna(subset=["start_time", "end_time"])
            if not df_time.empty:
                # Convert to datetime if they're strings
                if df_time["start_time"].dtype == "object":
                    df_time["start_time"] = pd.to_datetime(df_time["start_time"])
                if df_time["end_time"].dtype == "object":
                    df_time["end_time"] = pd.to_datetime(df_time["end_time"])

                session_start = df_time["start_time"].min()
                session_end = df_time["end_time"].max()
                duration_seconds = (session_end - session_start).total_seconds()

                spans_per_minute = (len(df_time) / duration_seconds * 60) if duration_seconds > 0 else 0

                # Find peak usage minute
                df_time["minute"] = df_time["start_time"].dt.floor("1min")
                peak_minute = df_time.groupby("minute").size().idxmax() if len(df_time) > 0 else None

                temporal_analysis = {
                    "session_duration_seconds": round(duration_seconds, 1),
                    "spans_per_minute": round(spans_per_minute, 1),
                    "peak_usage_minute": peak_minute.strftime("%H:%M") if peak_minute is not None else None
                }

        summary = {
            "session_id": session_id,
            "report_type": "usage_patterns",
            "timestamp": datetime.now().isoformat(),
            "by_span_type": by_span_type,
            "tool_usage": tool_usage,
            "temporal_analysis": temporal_analysis
        }

        # Save report
        files = self._save_report(session_id, "usage_patterns", summary, df)

        return {
            "session_id": session_id,
            "report_type": "usage_patterns",
            "timestamp": summary["timestamp"],
            "summary": summary,
            "files": files,
            "row_count": len(df)
        }


    def get_messages(
        self,
        session_id: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Geneartes CSV with messages and their token usage.
        """
        
        # Fetch required attributes (without "attributes." prefix for query)
        attributes = [
            "input.value",
            "output.value",
            "context.span_id",
            "context.trace_id",
            "parent_id",
            "session.id",
            "span_kind",
            "start_time",
            "end_time", 
            "input.value",
            "output.value",
            "metadata",
            "llm.model_name",
            "llm.input_messages",
            "llm.output_messages",
            "llm.token_count.total",
            "llm.token_count.prompt",
            "llm.token_count.prompt_details.cache_read",
            "llm.token_count.completion_details.reasoning",
            "llm.token_count.completion",
        ]

        df = self.fetch_session_spans(session_id, attributes, project_name)

        if df.empty:
            return self._empty_report(session_id, "usage_patterns")

        # Save report
        files = self._save_dataframe(session_id, "session_messages", df)

        return {
            "session_id": session_id,
            "report_type": "session_messages",
            "files": files,
            "row_count": len(df)
        }

    def generate_all_reports(
        self,
        session_id: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate all three report types for a session.

        Convenience method for comprehensive analysis.

        Args:
            session_id: Session to analyze
            project_name: Phoenix project name (optional)

        Returns:
            Dict with keys: "core_cost", "efficiency", "usage_patterns"
        """
        return {
            "core_cost": self.core_cost_report(session_id, project_name),
            "efficiency": self.efficiency_report(session_id, project_name),
            "usage_patterns": self.usage_patterns_report(session_id, project_name)
        }

    # Helper methods

    def _safe_sum(self, df: pd.DataFrame, column: str) -> float:
        """Safely sum a column, handling missing columns and NaN values."""
        if column not in df.columns:
            return 0.0
        # Use pd.to_numeric to avoid future pandas deprecation warning
        return float(pd.to_numeric(df[column], errors='coerce').fillna(0).sum())

    def _ensure_output_dir(self, session_id: str) -> Path:
        """Create output directory for session if it doesn't exist."""
        path = Path(self.output_dir) / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _save_dataframe(self, session_id: str, report_type: str, dataframe: pd.DataFrame):
        output_path = self._ensure_output_dir(session_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = output_path / f"{report_type}_data_{timestamp}.csv"
        dataframe.to_csv(csv_file, index=False)
        
        return {
            "data_file": str(csv_file)
        }
        
        
    def _save_report(
        self,
        session_id: str,
        report_type: str,
        summary_dict: Dict[str, Any],
        dataframe: pd.DataFrame
    ) -> Dict[str, str]:
        """
        Save both summary JSON and dataframe CSV.

        Args:
            session_id: Session ID
            report_type: Type of report (core_cost, efficiency, usage_patterns)
            summary_dict: Summary metrics dictionary
            dataframe: DataFrame with span data

        Returns:
            Dict with "summary_file" and "data_file" paths
        """
        output_path = self._ensure_output_dir(session_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save summary JSON
        summary_file = output_path / f"{report_type}_summary_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary_dict, f, indent=2, default=str)

        # Save dataframe CSV
        csv_file = output_path / f"{report_type}_data_{timestamp}.csv"
        dataframe.to_csv(csv_file, index=False)

        return {
            "summary_file": str(summary_file),
            "data_file": str(csv_file)
        }

    def _estimate_cost(
        self,
        model_name: str,
        prompt_tokens: float,
        completion_tokens: float
    ) -> float:
        """
        Estimate cost when Phoenix doesn't provide it.

        Args:
            model_name: Name of the model
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Estimated cost in USD
        """
        pricing = MODEL_PRICING.get(model_name, {"prompt": 0, "completion": 0})
        cost = (prompt_tokens * pricing["prompt"]) + (completion_tokens * pricing["completion"])
        return round(cost, 6)

    def _empty_report(self, session_id: str, report_type: str) -> Dict[str, Any]:
        """Return empty report structure when no spans found."""
        return {
            "session_id": session_id,
            "report_type": report_type,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "message": "No spans found for this session"
            },
            "files": {},
            "row_count": 0
        }


def main():
    """Example usage of SessionAnalyzer."""
    analyzer = SessionAnalyzer()

    # Example session ID - replace with your actual session ID
    session_id = "postman-31bf6ed1-9b9b-4e48-a0a4-7b408f03cf25"

    try:
        # Generate all reports
        print(f"Analyzing session: {session_id}")
        results = analyzer.get_messages(session_id)

        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)

        for report_type, result in results.items():
            print(f"\n{report_type.upper()}")
            print("-" * 60)
            print(f"  Spans analyzed: {result['row_count']}")

            summary = result.get("summary", {})
            if "total_cost_usd" in summary.get("cost_estimate", {}):
                print(f"  Total cost: ${summary['cost_estimate']['total_cost_usd']:.4f}")

            files = result.get("files", {})
            if files:
                print(f"  Summary: {files.get('summary_file')}")
                print(f"  Data: {files.get('data_file')}")

    except Exception as e:
        print(f"Error analyzing session: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
