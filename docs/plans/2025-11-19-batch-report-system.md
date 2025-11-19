# Batch Report System for Time-Windowed Analytics

**Date:** 2025-11-19
**Status:** Proposed
**Author:** Research Analysis

## Overview

This document outlines the design for a batch job system that generates analytics reports over configurable time windows. The primary goal is to understand how users are using the platform by analyzing session data, conversations, costs, and engagement patterns.

---

## Research Findings

### Current Implementation

The existing `SessionAnalyzer` class provides:

1. **Time-windowed queries** via `fetch_session_spans(start_time, end_time)`
2. **Three report types**: core_cost, efficiency, usage_patterns
3. **Conversation extraction** via `extract_conversation_data()`
4. **Per-session analysis** with file-based output (JSON + CSV)

### Phoenix Client API Capabilities

```python
from phoenix.client import Client
from phoenix.client.types.spans import SpanQuery

client = Client(base_url=url, api_key=key)

# Time-windowed query
df = client.spans.get_spans_dataframe(
    query=SpanQuery().where("span_kind == 'LLM'").select("llm.model_name"),
    project_identifier="my-project",
    start_time=start,
    end_time=end,
    limit=10000
)
```

**Key Features:**
- `start_time`/`end_time` parameters for time filtering
- `SpanQuery.where()` for condition filtering
- `SpanQuery.select()` for attribute selection
- `SpanQuery.explode()` for nested data extraction
- Project-level isolation

### Available Span Attributes (45+ total)

**Session & Context:**
- `session.id` - Unique session identifier
- `context.trace_id` - Conversation thread ID
- `context.span_id` - Individual operation ID

**Timing:**
- `start_time`, `end_time` - Operation timestamps

**User Interactions:**
- `input.value` - User input (JSON with message history)
- `output.value` - AI response (JSON with generations)

**LLM Metrics:**
- `llm.model_name` - Model used (gpt-4o, claude-3-5-sonnet, etc.)
- `llm.provider` - Provider (openai, anthropic)
- `llm.token_count.prompt` - Input tokens
- `llm.token_count.completion` - Output tokens
- `llm.token_count.total` - Total tokens
- `llm.token_count.prompt_details.cache_read` - Cached tokens

**Messages:**
- `llm.input_messages` - Structured input messages
- `llm.output_messages` - Structured output messages

**Tool Usage:**
- `tool.name` - Tool identifier
- `tool.description` - Tool description

**Status:**
- `status_code` - OK/ERROR
- `status_message` - Error details

### Message Structure

**Agent Span Input (input.value):**
```json
{
  "messages": [
    {"type": "system", "content": "You are a helpful assistant..."},
    {"type": "human", "content": "User's question"},
    {"type": "ai", "content": "Previous AI response"}
  ]
}
```

**Agent Span Output (output.value):**
```json
{
  "generations": [[{
    "message": {
      "type": "ai",
      "kwargs": {"content": "AI's response text"}
    }
  }]]
}
```

---

## Proposed Batch Job System

### Design Principles

1. **Time-window driven** - All reports operate on configurable time ranges
2. **Aggregation-focused** - Summarize across multiple sessions
3. **User behavior oriented** - Answer "how are users using our platform?"
4. **Scheduled execution** - Cron-compatible for automated runs
5. **Output flexibility** - JSON summaries + CSV details

### Report Types

#### 1. Session Summary Report
**Purpose:** High-level platform usage overview

**Metrics:**
- Total sessions in time window
- Total conversations (traces)
- Total user messages
- Average session duration
- Average messages per session
- Unique session count (proxy for active users)

**Output:**
```json
{
  "time_window": {"start": "...", "end": "..."},
  "total_sessions": 150,
  "total_traces": 420,
  "total_user_messages": 1250,
  "avg_session_duration_minutes": 12.5,
  "avg_messages_per_session": 8.3,
  "sessions_per_day": {"2025-11-18": 75, "2025-11-19": 75}
}
```

#### 2. Conversation Export Report
**Purpose:** Full transcript data for analysis

**Contents:**
- Session ID
- Timestamp
- Human message
- AI response
- Metadata (model, tokens, latency)

**Output:** CSV with columns:
`session_id, trace_id, timestamp, human_message, ai_response, model, tokens, latency_seconds`

#### 3. Cost Analysis Report
**Purpose:** Cost tracking and optimization insights

**Metrics:**
- Total cost (estimated)
- Cost by model
- Cost by provider
- Cost by session
- Token usage breakdown
- Cache efficiency and savings
- Failed request costs (wasted spend)

**Output:**
```json
{
  "time_window": {"start": "...", "end": "..."},
  "total_cost_usd": 45.23,
  "by_model": {
    "gpt-4o": {"cost": 30.50, "tokens": 125000},
    "gpt-4o-mini": {"cost": 14.73, "tokens": 850000}
  },
  "cache_efficiency": {
    "hit_rate": 0.42,
    "estimated_savings_usd": 8.50
  },
  "failed_request_cost_usd": 1.23
}
```

#### 4. User Engagement Report
**Purpose:** Usage patterns and behavior analysis

**Metrics:**
- Usage by hour of day
- Usage by day of week
- Peak usage times
- Tool usage breakdown
- Span type distribution (LLM, TOOL, CHAIN, AGENT)
- Session length distribution

**Output:**
```json
{
  "time_window": {"start": "...", "end": "..."},
  "hourly_usage": {"00": 12, "01": 8, ..., "23": 45},
  "daily_usage": {"Monday": 120, "Tuesday": 135, ...},
  "peak_hour": "14:00",
  "tool_usage": {
    "web_search": 250,
    "code_executor": 180,
    "file_reader": 320
  },
  "span_type_distribution": {
    "LLM": 1500,
    "TOOL": 750,
    "CHAIN": 300,
    "AGENT": 450
  }
}
```

#### 5. Top Sessions Report (New)
**Purpose:** Identify high-value or problematic sessions

**Metrics:**
- Top N sessions by cost
- Top N sessions by duration
- Top N sessions by message count
- Sessions with errors
- Sessions with high cache efficiency (learning from good patterns)

---

### Architecture

#### Core Class: `BatchReporter`

```python
class BatchReporter:
    def __init__(self, base_url, api_key, output_dir="batch_outputs"):
        self.analyzer = SessionAnalyzer(base_url, api_key, output_dir)

    def run_batch(
        self,
        start_time: datetime,
        end_time: datetime,
        reports: List[str] = None,  # ["session_summary", "cost", ...]
        project_name: str = None
    ) -> Dict[str, Any]:
        """Run batch reports for time window."""
        pass

    def session_summary_report(self, start_time, end_time, project_name) -> Dict:
        """Generate session summary for time window."""
        pass

    def conversation_export(self, start_time, end_time, project_name) -> Dict:
        """Export all conversations in time window."""
        pass

    def cost_analysis_report(self, start_time, end_time, project_name) -> Dict:
        """Aggregate cost analysis for time window."""
        pass

    def engagement_report(self, start_time, end_time, project_name) -> Dict:
        """User engagement patterns for time window."""
        pass

    def top_sessions_report(self, start_time, end_time, project_name, top_n=10) -> Dict:
        """Identify top/notable sessions."""
        pass
```

#### CLI Interface

```bash
# Run all reports for last 24 hours
python batch_reporter.py

# Run specific reports for custom time window
python batch_reporter.py --start "2025-11-18T00:00:00" --end "2025-11-19T00:00:00" --reports session_summary,cost

# Run for last week
python batch_reporter.py --window weekly

# Cron job example (daily report at midnight)
0 0 * * * /path/to/python /path/to/batch_reporter.py --window daily
```

#### Output Structure

```
batch_outputs/
  2025-11-19_daily/
    session_summary_20251119_000000.json
    session_summary_data_20251119_000000.csv
    cost_analysis_20251119_000000.json
    cost_analysis_data_20251119_000000.csv
    conversations_20251119_000000.csv
    engagement_20251119_000000.json
    engagement_data_20251119_000000.csv
    top_sessions_20251119_000000.json
    batch_manifest.json  # Index of all generated reports
```

---

## Time Window Options

| Window | Description | Cron Schedule |
|--------|-------------|---------------|
| hourly | Last hour | `0 * * * *` |
| daily | Last 24 hours | `0 0 * * *` |
| weekly | Last 7 days | `0 0 * * 0` |
| monthly | Last 30 days | `0 0 1 * *` |
| custom | User-defined start/end | Manual or custom |

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create `BatchReporter` class
- [ ] Implement time-window parameter handling
- [ ] Create CLI interface with argparse
- [ ] Implement batch output directory structure
- [ ] Add batch manifest generation

### Phase 2: Report Implementation (Week 1-2)
- [ ] Session Summary Report
- [ ] Conversation Export Report
- [ ] Cost Analysis Report (aggregate existing reports)
- [ ] User Engagement Report
- [ ] Top Sessions Report

### Phase 3: Scheduling & Automation (Week 2)
- [ ] Add scheduling helpers (cron format generation)
- [ ] Implement incremental processing (avoid re-processing)
- [ ] Add report comparison (week-over-week, etc.)

### Phase 4: Future Enhancements (Backlog)
- [ ] S3/cloud storage output
- [ ] Database persistence
- [ ] Real-time streaming analysis
- [ ] Alerting on anomalies (cost spikes, error rates)
- [ ] Web dashboard integration

---

## Key Questions to Answer

The batch report system should help answer these questions about platform usage:

1. **Volume**: How many users are using our platform? How many conversations?
2. **Engagement**: How long are sessions? How many messages per session?
3. **Patterns**: When do users use the platform most? What tools do they use?
4. **Cost**: How much are we spending? Which models cost most?
5. **Efficiency**: How effective is caching? What's the failure rate?
6. **Trends**: Is usage growing? Are costs trending up or down?

---

## Dependencies

**Existing:**
- arize-phoenix-client >= 1.21.0
- pandas >= 2.0.0
- python-dotenv >= 1.0.0

**New:**
- No additional dependencies required
- Uses standard library: datetime, argparse, json

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large time windows may timeout | High | Implement pagination, chunk processing |
| Phoenix API rate limits | Medium | Add retry logic with exponential backoff |
| Memory issues with large datasets | Medium | Stream processing, chunked CSV writes |
| Inconsistent data format | Low | Robust error handling, data validation |

---

## Success Criteria

1. Can generate all report types for any time window
2. Runs successfully as a cron job
3. Processes 10,000+ sessions without memory issues
4. Completes daily batch in under 5 minutes
5. Output files are correctly formatted and readable

---

## Next Steps

1. Review and approve this plan
2. Create implementation document with detailed code structure
3. Implement Phase 1 (Core Infrastructure)
4. Test with sample data
5. Iterate on report formats based on feedback
