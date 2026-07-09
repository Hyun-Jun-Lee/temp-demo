# DA Ops Demo

사내에서 사용한 DB 운영 진단 workflow를 축소한 LangGraph 기반 미니 데모입니다.

사용자 질문과 DB 이름을 입력받아 질문의 범위를 분류하고, 필요한 진단 노드를 실행한 뒤 요약과 검증을 거쳐 최종 응답을 생성합니다.

## 주요 기술

- Python 3.11+
- FastAPI
- LangGraph
- LangChain / langchain-openai
- OpenAI-compatible LLM
- uv

## 그래프 흐름

```text
START
  -> classifier
      -> global_health
          -> memory and/or os
      -> memory and/or os
  -> summary
  -> validation
  -> END
```

### 노드 역할

- `classifier`: 사용자 질문을 보고 다음에 실행할 노드를 결정합니다.
  - 포괄 질문: `global_health`
  - 메모리 질문: `memory`
  - OS/서버 질문: `os`
- `global_health`: 포괄적인 DB 상태 질문을 받아 `memory`, `os` 중 필요한 세부 진단 노드를 선택합니다.
- `memory`: Oracle DB 인스턴스의 Shared Pool, parse, cache, reserved pool 관련 메모리 압박을 분석합니다.
- `os`: 인스턴스별 OS 리소스 분석 결과를 RAC 레벨로 요약하고, CPU/메모리 압박, swap/paging, PGA 압박, workload skew, node imbalance를 판단합니다.
- `summary`: 실행된 진단 노드의 `node_result`를 요약해 `summary_result`를 생성합니다.
- `validation`: `user_question`, `node_result`, `summary_result`를 검증하고 `final_response`를 생성합니다.

## 상태 구조

그래프 state는 `src/core/state.py`의 `MainState`를 사용합니다.

필수 입력:

- `db_name`
- `user_question`

노드 실행 중 생성되는 값:

- `target_nodes`
- `node_result`
- `summary_result`
- `validation_result`
- `final_response`

`node_result`는 LangGraph reducer를 사용해 각 노드 결과를 누적합니다.

## 실행 방법

의존성 설치:

```bash
uv sync
```

환경변수 설정:

```bash
export OPENROUTER_API_KEY="your-api-key"
export OPENROUTER_MODEL_NAME="openai/gpt-4.1-mini"
```

`OPENROUTER_API_KEY`, `OPENROUTER_MODEL_NAME`은 필수값입니다.

FastAPI 서버 실행:

```bash
uvicorn src.main:app --reload
```

## API

### 그래프 실행 요청

```http
POST /graph/invoke
```

요청을 받으면 graph 실행은 background task로 처리하고, API는 즉시 `run_id`를 반환합니다.

요청:

```json
{
  "user_question": "DB 상태 정상인가요?",
  "db_name": "TESTDB"
}
```

응답:

```json
{
  "run_id": "uuid",
  "run_status": "QUEUED"
}
```

### 진행 상태 조회

```http
GET /graph/runs/{run_id}/status
```

해당 `run_id`의 노드별 최신 상태를 조회합니다.

### 작업 이력 조회

```http
GET /graph/runs/{run_id}/tasks
```

해당 `run_id`의 노드 실행 이벤트 전체를 조회합니다.

노드 실행 상태는 SQLite 테이블 `node_runs`에 저장됩니다.

필드:

- `run_id`
- `node_name`
- `node_status`
- `node_result`
- `created_at`

기본 DB 파일은 `da_ops_demo.sqlite3`입니다. `DA_OPS_DB_PATH` 환경변수로 경로를 변경할 수 있습니다.

## 프로젝트 구조

```text
src
├── main.py
├── graph_builder.py
├── core
│   ├── llm_client.py
│   ├── run_repository.py
│   ├── state.py
│   └── utils.py
├── nodes
│   ├── classifier_node.py
│   ├── global_health_node.py
│   ├── memory_node.py
│   ├── os_node.py
│   ├── summary_node.py
│   └── validation_node.py
└── prompt
    ├── classifier_prompt.py
    ├── global_health_prompt.py
    ├── memory_prompt.py
    ├── os_prompt.py
    ├── summary_prompt.py
    └── validation_prompt.py
```
