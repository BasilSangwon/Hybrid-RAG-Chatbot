# 🏗️ System Architecture

## Overview

AI RAG Laboratory는 **실험(Experiment) 중심의 하이브리드 RAG (Vector + Graph)** 시스템이다.  
단순한 정보 검색을 넘어, 데이터 구축 파라미터를 제어하고 성능 변화를 정량적으로 비교할 수 있는 연구용 아키텍처를 지향한다.

## Core Design Principles

### 1. Experiment-First Design (실험 중심 설계)

- **Problem**: 기존 RAG 시스템은 DB를 공유하여, 청크 사이즈나 모델 변경에 따른 성능 비교가 불가능했음.
- **Solution**:
  - 모든 Ingestion 작업을 `Experiment` 단위로 캡슐화.
  - PostgreSQL `JSONB` 컬럼을 활용한 Flexible Config Schema 적용.
  - 실험 ID를 기준으로 Graph/Vector 데이터를 논리적으로 완벽하게 격리.

### 2. Hybrid Retrieval (Vector + Graph)

- **Dual-Path Strategy**:
  - **Vector Search (`pgvector`)**: 질문과 의미적으로 유사한 텍스트 청크 검색 (Semantic match).
  - **Graph Search (`Neo4j`)**: 노드 간의 관계(Relationship)를 추적하여 논리적 연결 고리 파악 (Structure match).
- **Keyword Expansion**:
  - LLM을 이용하여 사용자 질문을 Cypher Query로 변환하고, Knowledge Graph 내에서 연관된 노드 정보를 직접 조회.

### 3. Rate-Limit Resilient Pipeline (안정성)

- **Intelligent Wait**: Google Gemini API의 무료 티어(RPM) 제한을 실시간으로 감지하고, 배치 작업 간 최적의 대기 시간(21s)을 자동 적용하여 중단 없는 대량 데이터 구축 보장.

## Architecture Diagram

```mermaid
graph TD
    subgraph "Data Ingestion Pipeline"
        PDF[PDF Documents] --> |Text Extraction| Chunker[Chunker]
        Chunker --> |Feature Extraction| LLM[LLM (Gemini 1.5 Pro)]

        LLM --> |Vectorize| Embed[Embedding Model]
        Embed --> |Save| PG[PostgreSQL (pgvector)]

        LLM --> |Graph Extraction| GraphTransformer[Graph Transformer]
        GraphTransformer --> |Constraint/Requirement| Neo4j[Neo4j Graph DB]

        subgraph "Experiment Control"
            Config[Experiment Config] --> Chunker
            Config --> LLM
            Config --> GraphTransformer
        end
    end

    subgraph "Retrieval & Generation"
        Query[User Query] --> |Hybrid Search| Retriever[Hybrid Retriever]
        Retriever --> |Vector Search| PG
        Retriever --> |Graph Search| Neo4j

        PG --> |Context A| Augment[Context Augmentation]
        Neo4j --> |Context B| Augment

        Augment --> |Prompt| Generator[LLM (Gemini Flash/Pro)]
        Generator --> Response[Final Answer]
    end
```

## Data Model

### Relational Schema (PostgreSQL)

- **Experiments**: 실험 설정 및 메타데이터 (`JSONB` config)
- **ManualDocs**: 원본 문서 청크 및 Vector Embedding (`vector(768)`)
- **TokenUsage**: API 사용량 및 비용 추적

### Graph Schema (Neo4j)

- **Nodes**:
  - `Product`: 제품 (e.g., Galaxy S25)
  - `Feature`: 주요 기능
  - `Constraint`: 제약 사항 (e.g., "네트워크 연결 필요")
  - `Requirement`: 필수 요건
- **Edges**:
  - `(:Product)-[:HAS_FEATURE]->(:Feature)`
  - `(:Feature)-[:REQUIRES]->(:Constraint)`

## Tech Stack

| Component      | Technology              | Reason                               |
| -------------- | ----------------------- | ------------------------------------ |
| **Backend**    | Python, FastAPI         | 비동기 처리 및 빠른 API 개발         |
| **Vector DB**  | PostgreSQL (`pgvector`) | 메타데이터 조회와 벡터 검색의 단일화 |
| **Graph DB**   | Neo4j                   | 강력한 Cypher 쿼리 및 시각화 도구    |
| **LLM**        | Google Gemini           | 긴 Context Window 및 멀티모달 기능   |
| **Frontend**   | Vanilla JS, HTML        | 가볍고 직관적인 Admin Dashboard 구현 |
| **Deployment** | Docker Compose          | 원클릭 배포 및 환경 격리             |
