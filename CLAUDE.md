# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Arize Reporter** is a Python analytics tool for tracking and analyzing per-user AI session costs using Arize Phoenix as the data source. It generates three types of production-ready analytics reports with file-based persistence (no database required).

**Design Philosophy:** Simplicity over complexity. Single-use design, no complex caching layers, persistent storage to disk.

## Quick Start

### Environment Setup

```bash
# Activate virtual environment (Python 3.12)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (see example.env for template)
cp example.env .env
# Edit .env with your Phoenix server URL and API key
```

### Common Commands

```bash
# Run all tests
python test.py

# Run examples
python example_usage.py

# Analyze a specific session (generates all three reports)
python session_analyzer.py <session-id>

# Run in Python REPL
python -c "from session_analyzer import SessionAnalyzer; analyzer = SessionAnalyzer(); results = analyzer.generate_all_reports('session-id')"
```

## Architecture

### Core Component: SessionAnalyzer Class

Single monolithic class (`session_analyzer.py`) with three report methods:

```python
SessionAnalyzer(base_url, api_key, output_dir)
├── fetch_session_spans()       # Flexible data retrieval with attribute selection
├── core_cost_report()          # A: Total costs, by model/provider, token breakdown
├── efficiency_report()         # B: Cache efficiency, cost-per-token, failure analysis
├── usage_patterns_report()     # C: Span type breakdown, tool usage, temporal analysis
├── generate_all_reports()      # Convenience method for all three
└── get_messages()              # Extract session messages with token usage
```

**Key Design Patterns:**
- **No caching:** Each report fetches fresh data from Phoenix (simplicity over optimization)
- **File-based persistence:** Reports save to `outputs/{session_id}/` as JSON summaries + CSV dataframes with timestamps
- **Error resilience:** `_safe_sum()` returns 0 for missing columns; fallback to `MODEL_PRICING` table when Phoenix lacks cost data
- **Unprefixed attribute names:** When using `.select()`, pass unprefixed names like `"llm.model_name"` (not `"attributes.llm.model_name"`). Returned DataFrame columns are also unprefixed.

### Data Flow

1. **Fetch** → `fetch_session_spans(session_id, attributes=None)` queries Phoenix
2. **Analyze** → Report methods perform pandas analysis on fetched data
3. **Store** → Save `{report_type}_summary_{timestamp}.json` + `{report_type}_data_{timestamp}.csv`

### Available Span Attributes (45+ total)

**Standard:** name, span_kind, parent_id, start_time, end_time, status_code, status_message

**Context:** span_id, trace_id

**I/O:** input.value, input.mime_type, output.value, output.mime_type

**LLM:** model_name, provider, token counts (prompt/completion/total), cache details, invocation parameters, input_messages, output_messages, tools, system

**Tool:** tool.name, tool.description

**Session:** session.id

**Metadata:** custom metadata field

See docstring in `session_analyzer.py` (lines 10-44) for complete attribute list.

## Report Types

### Report A: Core Cost Metrics
- Total costs by session
- Cost breakdown by model and provider
- Token usage statistics (prompt, completion, total)
- Cost estimates (fallback to `MODEL_PRICING` table)

### Report B: Efficiency & Optimization
- Cache efficiency (hit rate, savings estimate)
- Cost-per-token calculations
- Failure cost analysis (wasted spend on failed spans)

### Report C: Usage Patterns
- Cost/count by span type (LLM, TOOL, CHAIN, etc.)
- Tool usage breakdown
- Temporal analysis (session duration, spans/minute, peak usage)

## Cost Estimation

Hardcoded `MODEL_PRICING` table (line ~250 in session_analyzer.py) provides fallback pricing when Phoenix lacks cost data:

```
GPT-4: $0.03/1K prompt, $0.06/1K completion
Claude 3.5 Sonnet: $0.003/1K prompt, $0.015/1K completion
GPT-3.5 Turbo: $0.0005/1K prompt, $0.0015/1K completion
[+ 10+ other models]
```

## File Structure

```
arize_reporter/
├── session_analyzer.py         # Main SessionAnalyzer class (671 lines)
├── example_usage.py            # 5 documented usage examples
├── test.py                     # Comprehensive test suite
├── requirements.txt            # Python dependencies
├── example.env                 # Environment template
├── .env                        # Actual config (git-ignored)
├── docs/
│   ├── readme.md               # Full API documentation
│   └── plans/2025-11-03-session-analyzer-redesign.md  # Design document
├── scripts/session_analyze.py  # Jupyter notebook analysis
└── outputs/                    # Report storage (git-ignored)
    └── {session_id}/
        ├── {report_type}_summary_{timestamp}.json
        └── {report_type}_data_{timestamp}.csv
```

## Environment Variables

**Required (.env file):**
```
PHOENIX_BASE_URL=http://[phoenix-server]  # Phoenix server URL
PHOENIX_API_KEY=[api-key]                 # API authentication
PROJECT=mobsta-development                # Target project (optional)
```

## Testing

```bash
# Run all tests (includes Phoenix connection, span fetching, report generation)
python test.py
```

**Test coverage:**
- Phoenix server connection
- Session span fetching with attribute selection
- All three report types (core cost, efficiency, usage patterns)
- SessionAnalyzer initialization

## Dependencies

**Core:**
- arize-phoenix>=12.9.0 — Phoenix client library
- arize-phoenix-client>=1.21.0 — Phoenix API client
- pandas>=2.0.0 — Data processing and analysis
- python-dotenv>=1.0.0 — Environment configuration

**Optional (commented out):**
- numpy, matplotlib, seaborn — For enhanced data analysis

## Recent Changes & Git Status

**Last commit:** 9dbd830 - init

**Current uncommitted changes:**
- Modified: `.gitignore`, `requirements.txt`, `session_analyzer.py`
- Deleted: `session_message_extractor.py` (replaced by `get_messages()` method)
- Untracked: `notebook.ipynb`

**Recent redesign (2025-11-03):** Transformed from test-focused cost analyzer into production-ready product analytics tool with three pre-defined report types. See `docs/plans/2025-11-03-session-analyzer-redesign.md` for full design document.

## Common Development Tasks

### Adding a New Report Type

1. Create new method in `SessionAnalyzer` class: `def new_report_type_report(self, session_id, project_name=None)`
2. Use `fetch_session_spans()` to get data
3. Analyze with pandas
4. Call `self._save_report()` to persist JSON summary + CSV data
5. Return report dictionary with `session_id`, `summary`, `files`, `row_count`
6. Add tests to `test.py`

### Adding Span Attributes

1. Update docstring (lines 10-44) with new attribute
2. Use attribute name in `.select()` without "attributes." prefix
3. Test in `fetch_session_spans()` with `attributes=["new.attribute"]`

### Cost Estimation Updates

Update `MODEL_PRICING` dictionary (line ~250) with new model pricing:
```python
MODEL_PRICING = {
    "new-model": {
        "prompt": 0.01,      # per 1K tokens
        "completion": 0.03,  # per 1K tokens
    },
    ...
}
```

## Key Implementation Details

### Span Attribute Naming (Important)

- **Input:** Use unprefixed names: `"llm.model_name"`, `"tool.name"`, `"session.id"`
- **Output DataFrame columns:** Also unprefixed when using `.select()`
- When fetching ALL attributes (`attributes=None`), columns have "attributes." prefix

### Error Handling Strategy

- Missing columns: `_safe_sum()` returns 0 (line ~150)
- Missing model pricing: Fallback to hardcoded table
- Empty results: Return empty report structure with message
- File conflicts: Timestamps prevent overwrites, enable historical tracking

### Report Output Format

Every report returns:
```python
{
    "session_id": "...",
    "report_type": "core_cost|efficiency|usage_patterns",
    "timestamp": "2025-11-03T14:30:22",
    "summary": { ... },        # Aggregated metrics
    "files": {                 # Output file paths
        "summary_file": "outputs/.../..._summary_timestamp.json",
        "data_file": "outputs/.../..._data_timestamp.csv"
    },
    "row_count": 15            # Number of spans analyzed
}
```

## Documentation References

- **Full API docs:** `docs/readme.md`
- **Design decisions:** `docs/plans/2025-11-03-session-analyzer-redesign.md`
- **Usage examples:** `example_usage.py` (5 different use cases)
- **Code docstrings:** SessionAnalyzer class and method docstrings

## Future Enhancements (Out of Scope)

Deliberately NOT included (YAGNI principle):
- Database storage
- Query builder interface
- Real-time streaming analysis
- Multi-session aggregation reports
- Cost prediction models
- Anomaly detection algorithms

Add complexity only when needed.

## Active Technologies
- Python 3.12 + arize-phoenix>=12.9.0, arize-phoenix-client>=1.21.0, pandas>=2.0.0, python-dotenv>=1.0.0 (001-session-conversation-analysis)
- File-based (CSV output to outputs/{session_id}/ directory) (001-session-conversation-analysis)
