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
- `os`: OS/서버 상태 진단 노드입니다. 현재는 스텁입니다.
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
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-4.1-mini"
```

`OPENAI_MODEL`은 선택값입니다. 지정하지 않으면 기본값으로 `gpt-4.1-mini`를 사용합니다.

FastAPI 서버 실행:

```bash
uvicorn src.main:app --reload
```

## 프로젝트 구조

```text
src
├── main.py
├── graph_builder.py
├── core
│   ├── llm_client.py
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