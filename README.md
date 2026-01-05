# AI RAG Laboratory

**실험(Experiment) 기반 Hybrid RAG (Vector + Graph)** 연구 및 관리 시스템.

PDF 문서를 기반으로 Vector DB(정밀 검색)와 Knowledge Graph(관계 추론)를 구축하고, 다양한 LLM 모델과 파라미터를 실시간으로 교체하며 답변 품질을 정량적으로 비교 분석함.

## 🚀 Key Features

- **Experiment Management**: Chunk Size, Overlap, LLM Model 등 RAG 파라미터를 실험 단위로 관리 및 기록.
- **Hybrid Search Strategy**:
  - **Vector Search (PGVector)**: 문맥적 유사성(Semantic) 기반 Fact 검색.
  - **Graph Search (Neo4j)**: 노드 간 관계(Relationship) 추론을 통한 구조적 답변 도출.
- **Robust Ingestion Pipeline**:
  - **Smart Rate Limiting**: Google Gemini 무료 티어(RPM) 고려, 배치 작업 간 자동 대기(Intelligent Wait) 로직 적용.
  - **Constraint-Aware Schema**: 문서 내 '유의사항'이나 '제약조건'을 놓치지 않도록 강제된 Graph 스키마 적용.
- **Dynamic Model Switching**: 서버 재시작 없이 Chat Session 도중 모델(Gemini Flash/Pro) 즉시 교체 가능.
- **Admin Dashboard**: PDF 업로드, 실험 데이터 시각화, 지식 베이스 관리(CRUD) UI 제공.

## 📂 Project Structure

```bash
├── client/          # Frontend (Admin Dashboard & Chat UI)
├── server/          # Backend (FastAPI)
│   ├── core/        # Config, DB Connection, Schema
│   ├── pipelines/   # Ingestion Pipelines (Vector/Graph)
│   └── main.py      # REST API Endpoints
├── docs/            # Architecture & Dev Logs
├── docker-compose.yml
└── requirements.txt
```

## 🏗️ System Architecture

> 💡 상세 아키텍처 설계 및 다이어그램은 [**docs/ARCHITECTURE.md**](docs/ARCHITECTURE.md) 참고.

### Core Philosophy

본 시스템은 **"데이터 격리(Isolation)"**와 **"검색 보완(Hybrid)"**을 핵심 설계 철학으로 함.

- **Ingestion**: 모든 데이터 구축은 `Experiment ID`를 기준으로 격리되어, 파라미터 변경에 따른 성능 간섭을 원천 차단함.
- **Retrieval**: Keyword 매칭의 한계를 극복하기 위해 `Graph Neighborhood Search`(1~2 hop)를 결합하여 답변 커버리지 극대화.

## 🗺️ Roadmap

### Phase 1: Stabilization (Completed) ✅

- [x] **Infrastructure**: Docker Compose 기반 서비스 오케스트레이션 구축
- [x] **Core Pipeline**: Hybrid RAG (Vector + Graph) Ingestion 구현
- [x] **Management**: 실험(Experiment) CRUD 및 데이터 격리 구조 설계

### Phase 2: Advanced Retrieval (Current) 🚧

- [ ] **Multi-Modal Ingestion**: PDF 내 이미지/차트/도표 추출 및 Graph 노드화 (Unstructured / LlamaIndex 활용)
- [ ] **Auto-Evaluation**: RAGAS 프레임워크 도입, Ground Truth 기반 답변 품질(Precision/Recall) 자동 채점
- [ ] **Query Optimization**: 사용자 질문 의도 분류(Intent Classification)에 따른 Search Strategy 동적 최적화

### Phase 3: Expansion (Planned) 📅

- [ ] **Scalability**: Celery/Redis 도입으로 Ingestion Worker 분리 및 병렬 처리 (대용량 PDF 대응)
- [ ] **Local LLM**: vLLM/Ollama 연동을 통한 On-Premise 환경 지원 (Llama 3, Mistral)
- [ ] **Interactive Graph**: D3.js/Cytoscape.js 기반 지식 그래프 탐색 및 시각화 도구 강화

## 🛠️ Installation & Setup

### 1. Environment Config

프로젝트 루트에 `.env` 파일 생성.

```env
GOOGLE_API_KEY=your_key_here
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
DB_CONNECTION=postgresql+psycopg2://user:password@localhost:5432/ragdb
```

### 2. Docker Run

깨끗한 환경 구동을 위해 Volume 초기화 후 빌드 권장.

```bash
# 초기화 및 실행
docker-compose down -v
docker-compose up -d --build
```

### 3. Access Points

- **Chat UI**: `http://localhost:8000/`
- **Admin Dashboard**: `http://localhost:8000/admin`
- **Neo4j Browser**: `http://localhost:7474`

## 📚 Documentation

- [**Architecture Details**](docs/ARCHITECTURE.md): 시스템 설계 원칙 및 다이어그램
- [**Dev Log (Worklog)**](docs/WORKLOG.md): 개발 히스토리 및 트러블슈팅 기록
