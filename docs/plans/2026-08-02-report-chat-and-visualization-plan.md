---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
created: 2026-08-02
feature: report-chat-and-visualization
---

# Report Chat and Visualization Plan

## Goal

`Report` 화면을 단순 결과 조회 화면에서 운영자가 보고서를 탐색할 수 있는 분석 화면으로 확장한다.

추가할 기능은 두 가지다.

1. Report 화면에서 AI 채팅 기능을 제공해 선택된 `run_id` 보고서에 대해 질의응답할 수 있게 한다.
2. Report 화면에 수집된 node/report 데이터를 차트로 시각화한다.

## Current Baseline

현재 구조:

- `src/main.py`
  - `GET /reports`
  - `GET /reports/{run_id}`
  - `POST /graph/invoke`
  - graph 완료 시 `save_report(...)` 호출
- `src/core/run_repository.py`
  - `node_runs` 테이블
  - `reports` 테이블
  - report 저장/조회 함수
- `src/static/index.html`
  - 단일 HTML UI
  - `실행` 탭
  - `Report` 탭
  - report 목록/상세
  - report metric card/table 렌더링
- `src/core/llm_client.py`
  - OpenRouter 우선, OpenAI fallback
  - `ChatOpenAI`
- 각 node output schema
  - `global_health`: health/signal score
  - `memory`: severity/confidence/key_metrics
  - `os`: severity/pressure/cluster_metrics/instance_scores
  - `summary`: overall_status/overall_score/key_findings/recommended_actions

## Scope

### In Scope

- Report별 AI 채팅 API
- Report 화면 채팅 UI
- Report 채팅 내역 저장
- Report 데이터에서 chart-friendly series 생성
- Report 화면 chart UI
- 기본 차트 렌더링
- chart 데이터 API
- backend repository 함수 확장
- API smoke 테스트 또는 최소 TestClient 검증

### Out of Scope

- 실제 운영 DB metric 수집 구현
- 사용자 인증/권한
- 다중 사용자 세션 분리
- WebSocket streaming
- 외부 chart build pipeline 도입
- 복잡한 dashboard builder

## Product Requirements Traceability

| ID | Requirement | Source |
| --- | --- | --- |
| R1 | Report 화면에서 선택된 report에 대해 AI 질의응답을 할 수 있어야 한다. | User request item 1 |
| R2 | AI 답변은 선택된 `run_id`의 report 내용을 primary evidence로 사용해야 한다. | User request item 1, existing report model |
| R3 | Report 화면에 수집된 데이터를 chart로 시각화해야 한다. | User request item 2 |
| R4 | Chart는 현재 저장된 report/node_result 구조에서 파생되어야 한다. | Existing architecture |
| R5 | 기존 `Report` 탭과 run_id 선택 UX를 유지해야 한다. | Existing UI |
| R6 | Chart rendering은 Chart.js를 사용해야 한다. | User decision |
| R7 | Report 채팅 내역은 SQLite에 저장되어야 한다. | User decision |
| R8 | AI 채팅은 report 기반 답변에 일반 DB 운영지식을 보충할 수 있어야 한다. | User decision |
| R9 | 채팅 범위는 단일 `run_id` 대상으로만 제한한다. | User decision |

## Proposed Architecture

```text
Report tab
  ├─ report list
  ├─ report detail
  ├─ charts panel
  │   └─ GET /reports/{run_id}/charts
  └─ AI chat panel
      ├─ GET /reports/{run_id}/chat
      └─ POST /reports/{run_id}/chat

SQLite
  ├─ reports
  ├─ node_runs
  └─ report_chat_messages
```

## Data Model Changes

### New Table: `report_chat_messages`

Add in `src/core/run_repository.py`.

Fields:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `run_id TEXT NOT NULL`
- `role TEXT NOT NULL`
  - `user`
  - `assistant`
- `content TEXT NOT NULL`
- `metadata_json TEXT`
  - assistant message의 `cited_nodes`, `confidence_score`, grounding label 등을 저장
  - user message는 `NULL` 가능
- `created_at TEXT NOT NULL`

Rationale:

- Current app already uses SQLite and repository helpers.
- Chat history should survive page refresh.
- Keeping chat separate from `reports` avoids mutating immutable report results.

### Chart Data Shape

Charts should be generated from existing `report_result.node_result`.

Proposed response:

```json
{
  "run_id": "uuid",
  "charts": [
    {
      "id": "risk_scores",
      "title": "Risk Scores",
      "type": "bar",
      "labels": ["Overall", "Memory", "OS", "CPU", "Memory Pressure", "Imbalance"],
      "values": [48, 12, 48, 62, 55, 66]
    }
  ]
}
```

## Backend Work

### 1. Repository Extensions

File: `src/core/run_repository.py`

Add:

- `init_db()` migration for `report_chat_messages`
- `save_report_chat_message(run_id, role, content, metadata=None)`
- `get_report_chat_messages(run_id)`

Test scenarios:

- Creates table if missing.
- Saves user and assistant messages.
- Persists assistant metadata and reads it back.
- Reads messages ordered by `created_at ASC`.
- Returns empty list for known report with no chat history.

### 2. Report Chat Prompt

New file: `src/prompt/report_chat_prompt.py`

Suggested constants:

- `SYSTEM_PROMPT`
- `USER_PROMPT`

Prompt responsibilities:

- Use the selected report as the primary evidence.
- Answer only for the selected `run_id`.
- Supplement with general DB operation knowledge when useful.
- Clearly separate report-based facts from general operational guidance.
- If report lacks evidence for a specific claim, say so.
- Distinguish final response, summary, node outputs, metrics, and source data.
- Write Korean responses.
- Keep answer concise but operational.

Suggested input placeholders:

- `{user_question}`
- `{report_result}`
- `{chat_history}`

### 3. Report Chat Schema

Option A, simple:

```python
class ReportChatResult(BaseModel):
    answer: str
    cited_nodes: list[str]
    confidence_score: int
```

Rationale:

- `answer` drives UI.
- `cited_nodes` makes grounding visible.
- `confidence_score` allows subtle quality signal.

### 4. Report Chat API

File: `src/main.py`

Add models:

- `ReportChatRequest`
- `ReportChatResponse`
- `ReportChatMessage`
- `ReportChatHistoryResponse`

Add endpoints:

- `GET /reports/{run_id}/chat`
- `POST /reports/{run_id}/chat`

Behavior:

- `GET` returns persisted chat messages.
- `POST` validates report exists.
- `POST` stores user message.
- `POST` calls LLM with selected report and prior chat history.
- `POST` stores assistant message.
- `POST` returns assistant answer, cited nodes, confidence score.

Error behavior:

- Unknown `run_id`: 404.
- Empty question: 422 via Pydantic validation.
- LLM failure: 500 with short error detail.

Test scenarios:

- Unknown `run_id` returns 404.
- Known report accepts chat question.
- Chat response is persisted.
- Chat history includes user and assistant messages.

### 5. Chart Data API

File: `src/main.py`

Add:

- `GET /reports/{run_id}/charts`

Implementation options:

- Keep chart extraction in `src/main.py` initially for demo speed.
- Prefer a helper file if it grows:
  - `src/core/report_charts.py`

Recommended helper:

```python
def build_report_charts(report_result: dict) -> list[dict]:
    ...
```

Initial charts:

1. Risk score bar chart
   - Overall Risk
   - Global Health
   - Memory Severity
   - OS Severity
   - OS CPU Pressure
   - OS Memory Pressure
   - Imbalance

2. Memory metrics bar chart
   - `memory.key_metrics`

3. OS cluster metrics bar chart
   - `os.cluster_metrics`

4. Per-instance score chart
   - `os.instance_scores`
   - x-axis: host or instance
   - values: severity, CPU, memory, workload share

Test scenarios:

- Report with all nodes produces all charts.
- Report missing `memory` still produces OS and overall charts.
- Report missing `os` still produces memory and overall charts.
- Empty metric objects return empty `charts` or omit those chart sections.

## Frontend Work

File: `src/static/index.html`

### 1. Report Layout Update

Current report detail stacks:

- metadata cards
- final response
- raw JSON

Update to:

```text
Report tab
  ├─ left: report list
  └─ right:
      ├─ summary/score cards
      ├─ charts section
      ├─ final response
      ├─ AI chat section
      └─ raw JSON details
```

### 2. Chart Rendering

Use Chart.js through a CDN in the existing single HTML UI.

Rationale:

- The user selected Chart.js.
- It supports bar, grouped bar, doughnut, and line charts without adding a frontend build step.
- It is a good fit for the existing Tailwind CDN based demo UI.

Implementation notes:

- Add Chart.js CDN script in `src/static/index.html`.
- Maintain a chart instance registry and destroy old chart instances before rendering a newly selected report.
- Render empty states when chart data is unavailable.
- Prefer initial chart types:
  - bar chart for node/risk scores
  - grouped bar chart for OS instance scores
  - bar chart for memory and OS metrics

### 3. Chat UI

Add to Report detail:

- Chat history area
- Input textbox
- `질문하기` button
- Loading state while waiting for answer
- Confidence/cited node metadata on assistant answers

UX rules:

- Disable chat input until a report is selected.
- Show “이 report에 대해 질문해보세요” empty state.
- After submitting, append user message immediately.
- Show assistant loading bubble.
- Replace loading bubble with answer.
- Keep chat scoped to selected `run_id`.

### 4. Frontend JS Functions

Add:

- `loadReportCharts(runId)`
- `renderCharts(charts)`
- `loadReportChat(runId)`
- `sendReportChatMessage()`
- `renderChatMessages(messages)`
- `appendChatMessage(message)`

Modify:

- `loadReport(runId)`
  - also call `loadReportCharts(runId)`
  - also call `loadReportChat(runId)`

## Testing Plan

### Backend

If adding test files:

- `tests/test_report_chat_api.py`
- `tests/test_report_charts.py`
- `tests/test_run_repository.py`

If keeping demo minimal:

- Use `fastapi.testclient.TestClient` smoke scripts.
- Verify:
  - `GET /reports` still works.
  - `GET /reports/{run_id}` still works.
  - `GET /reports/{run_id}/charts` returns expected chart ids.
  - `GET /reports/{run_id}/chat` returns history.
  - `POST /reports/{run_id}/chat` stores and returns answer.

### Frontend

Manual/browser checks:

- Report tab loads.
- Selecting report renders score cards.
- Charts render with current report data.
- Chat input is disabled before report selection.
- Chat answer appears and remains after refresh.
- Switching reports switches chat history and charts.

## Implementation Units

### Unit 1: Report Chat Storage

Files:

- `src/core/run_repository.py`

Work:

- Add chat table.
- Add chat save/read helpers.

Validation:

- Repository smoke test with temporary SQLite path.

### Unit 2: Report Chat LLM API

Files:

- `src/main.py`
- `src/prompt/report_chat_prompt.py`

Work:

- Add prompt.
- Add structured output model.
- Add `GET /reports/{run_id}/chat`.
- Add `POST /reports/{run_id}/chat`.

Validation:

- Unknown report returns 404.
- Known report stores user and assistant messages.

### Unit 3: Chart Data Builder API

Files:

- `src/main.py`
- `src/core/report_charts.py`

Work:

- Extract chart data from report JSON.
- Add `GET /reports/{run_id}/charts`.

Validation:

- Works for reports with memory only, OS only, both, and missing metrics.

### Unit 4: Report UI Charts

Files:

- `src/static/index.html`

Work:

- Add chart section.
- Render Chart.js charts.
- Handle empty chart state.

Validation:

- Browser smoke test at `GET /`.
- Report tab displays chart cards.

### Unit 5: Report UI Chat

Files:

- `src/static/index.html`

Work:

- Add report chat section.
- Load chat history on report selection.
- Submit chat messages.
- Show loading and error states.

Validation:

- Chat response persists after refresh.
- Switching reports changes chat context.

## Resolved Decisions

### D1. Chart Library

Decision: use Chart.js.

Implementation:

- Load Chart.js through CDN in `src/static/index.html`.
- Keep the backend chart API library-agnostic by returning labels, values, datasets, and chart type metadata.
- Keep the demo lightweight by avoiding a frontend build pipeline.

### D2. Chat Answer Persistence

Decision: persist report chat history in SQLite.

Implementation:

- Add `report_chat_messages` table.
- Store both user and assistant messages.
- Load history by selected `run_id` when the report detail opens.

### D3. Chat Grounding Strictness

Decision: allow general DB operation knowledge as supplemental context.

Implementation:

- The selected report remains the primary source.
- The assistant can add general DB operation guidance when the report does not fully answer the question.
- The prompt should label whether a point is based on report evidence or general DB 운영지식.
- The response schema should keep `cited_nodes` for report-based evidence and `confidence_score` for answer quality.

### D4. Report Scope

Decision: chat is scoped to a single selected `run_id`.

Implementation:

- API paths remain `GET /reports/{run_id}/chat` and `POST /reports/{run_id}/chat`.
- The chat prompt receives only the selected report and that report's chat history.
- Cross-run comparison is explicitly out of scope for this phase.

## Risks

- Report JSON 구조가 node schema 변경에 민감하다.
  - Mitigation: chart builder should tolerate missing fields.

- LLM chat answers may hallucinate beyond report data.
  - Mitigation: prompt must distinguish report evidence from general DB 운영지식 and expose `cited_nodes`.

- Chart.js CDN may fail in offline/internal network environments.
  - Mitigation: acceptable for current demo; production/internal deployment can vendor Chart.js as a static asset.

- Single HTML file is growing large.
  - Mitigation: acceptable for current demo; if it grows further, split static JS/CSS files.

- SQLite schema migrations are simple `CREATE TABLE IF NOT EXISTS`.
  - Mitigation: sufficient for demo; production should use migration tooling.

## Suggested Next Step

Decisions are resolved. Implementation can proceed in this order:

1. Report chat storage
2. Chart data API
3. Report chat API
4. Report chart UI
5. Report chat UI
