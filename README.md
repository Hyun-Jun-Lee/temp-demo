# DA Ops Demo

사내 DB 운영 진단 workflow를 축소한 LangGraph 기반 미니 데모입니다.

사용자가 DB를 선택하고 질문을 입력하면 graph가 질문을 분류하고, 필요한 진단 노드를 실행한 뒤 요약, 검증, report 저장까지 처리합니다. Web UI에서는 노드 진행상황과 최종 report를 확인할 수 있습니다.

## 빠른 실행

### 1. 의존성 설치

```bash
uv sync
```

### 2. 환경변수 설정

`.env.sample`을 참고해 `.env` 파일을 만듭니다.

```bash
cp .env.sample .env
```

LLM Provider는 OpenRouter 또는 OpenAI 중 하나를 사용하면 됩니다.

Option A, OpenRouter 사용:

```bash
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL_NAME=google/gemini-3-flash-preview
```

Option B, OpenAI API 직접 사용:

```bash
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4.1-mini
```

OpenRouter 환경변수가 있으면 OpenRouter를 우선 사용합니다. OpenRouter 값을 설정하지 않고 `OPENAI_API_KEY`를 설정하면 OpenAI API를 사용합니다.

앱은 `.env` 파일을 자동으로 읽습니다. shell에서 직접 export해도 됩니다.

```bash
export OPENROUTER_API_KEY="your-openrouter-api-key"
export OPENROUTER_MODEL_NAME="google/gemini-3-flash-preview"
# or
export OPENAI_API_KEY="your-openai-api-key"
export OPENAI_MODEL="gpt-4.1-mini"
```

### 3. 서버 실행

```bash
.venv/bin/uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Web UI 접속

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8000
```

## Web UI 기능

- DB 목록 테이블에서 DB 선택
- 질문 입력 후 `질문하기` 실행
- graph 실행은 background task로 처리
- 노드 진행상황 조회
  - `QUEUED`
  - `RUNNING`
  - `COMPLETE`
  - `FAILED`
- 노드 카드 클릭 시 해당 노드 결과 확인
- 실행 완료 후 `Report 바로가기` 버튼 활성화
- `Report` 탭에서 run_id별 최종 report 확인
- report 상세에서 수치 카드, 핵심 발견, 권고사항, 원본 JSON 확인

## 주요 기술

- Python 3.11+
- FastAPI
- LangGraph
- LangChain / langchain-openai
- OpenRouter OpenAI-compatible API 또는 OpenAI API
- SQLite
- Tailwind CSS
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

- `classifier`
  - 사용자 질문을 보고 다음에 실행할 노드를 결정합니다.
  - 포괄 질문은 `global_health`로 보냅니다.
  - 메모리 질문은 `memory`, OS/서버 질문은 `os`로 보냅니다.

- `global_health`
  - DB 전반 상태 overview 데이터를 확인한 뒤 필요한 서브 에이전트를 선택합니다.
  - memory 신호가 있으면 `memory`
  - OS/server 신호가 있으면 `os`
  - 둘 다 있거나 데이터가 불충분하면 둘 다 선택합니다.

- `memory`
  - Oracle DB 인스턴스의 Shared Pool, parse, cache, reserved pool, ORA-04031 위험을 분석합니다.
  - demo에서는 정상 또는 경고 샘플 데이터가 시나리오에 따라 반환됩니다.

- `os`
  - 인스턴스별 OS 리소스 분석 결과를 RAC 레벨로 요약합니다.
  - CPU/메모리 압박, swap/paging, PGA 압박, workload skew, node imbalance를 판단합니다.
  - demo에서는 정상 또는 경고 샘플 데이터가 시나리오에 따라 반환됩니다.

- `summary`
  - 실행된 노드의 `node_result`를 통합해 `summary_result`와 report용 score/finding/action을 생성합니다.

- `validation`
  - `user_question`, `node_result`, `summary_result`를 검증하고 `final_response`를 생성합니다.

## 상태 저장

SQLite를 사용합니다. 기본 DB 파일은 `da_ops_demo.sqlite3`입니다.

경로는 환경변수로 변경할 수 있습니다.

```bash
export DA_OPS_DB_PATH=/tmp/da_ops_demo.sqlite3
```

### node_runs

노드 실행 이벤트를 저장합니다.

- `run_id`
- `node_name`
- `node_status`
- `node_result`
- `created_at`

### reports

graph 완료 후 최종 report를 저장합니다.

- `run_id`
- `report_result`
- `created_at`

## API

### Health Check

```http
GET /health
```

### DB 목록 조회

```http
GET /api/databases
```

### Graph 실행 요청

```http
POST /graph/invoke
```

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

### Report 목록 조회

```http
GET /reports
```

### Report 상세 조회

```http
GET /reports/{run_id}
```

## Demo 시나리오

현재 실제 DB 조회는 연결되어 있지 않고, 더미 데이터 함수가 시나리오별 샘플 데이터를 반환합니다.

기본값은 실행마다 랜덤입니다.

가능한 시나리오:

- `normal`
- `memory_warning`
- `os_warning`
- `mixed_warning`

특정 시나리오를 고정하려면 아래 환경변수를 설정합니다.

```bash
export DA_OPS_DEMO_SCENARIO=os_warning
```

또는 `.env`에 추가할 수 있습니다.

```bash
DA_OPS_DEMO_SCENARIO=os_warning
```

## 프로젝트 구조

```text
src
├── main.py
├── graph_builder.py
├── core
│   ├── demo_scenarios.py
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
├── prompt
│   ├── classifier_prompt.py
│   ├── global_health_prompt.py
│   ├── memory_prompt.py
│   ├── os_prompt.py
│   ├── summary_prompt.py
│   └── validation_prompt.py
└── static
    └── index.html
```

## 개발 메모

- LLM client는 `src/core/llm_client.py`의 `get_llm_client()`에서 생성합니다.
- OpenRouter 사용 시 endpoint는 `https://openrouter.ai/api/v1`입니다.
- OpenRouter 또는 OpenAI 중 하나를 설정하면 됩니다. 둘 다 설정하면 OpenRouter가 우선입니다.
- 각 노드는 `with_structured_output`과 Pydantic schema를 사용합니다.
- prompt에는 역할과 판단 기준을 두고, 응답 schema는 노드 코드에서 관리합니다.
- graph 실행 상태와 report는 SQLite에 저장됩니다.
