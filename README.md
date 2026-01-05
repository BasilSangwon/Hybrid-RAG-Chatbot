지금까지 함께 작업하며 개선했던 **안정성 패치, Graph 구축 노하우, 트러블슈팅** 내용을 모두 통합하여 정리한 최종 `README.md`입니다.

이 내용을 프로젝트 루트의 `README.md` 파일에 덮어쓰시면, 프로젝트의 목적과 사용법을 완벽하게 정리할 수 있습니다.

---

# 🧪 AI RAG Laboratory

실험(Experiment) 기반의 **하이브리드 RAG (Vector + Graph)** 관리 및 연구 시스템입니다.

PDF 문서를 기반으로 Vector DB(정밀 검색)와 Knowledge Graph(관계 추론)를 구축하고, 다양한 LLM 모델을 실시간으로 교체하며 답변 품질을 비교할 수 있습니다.

## 🚀 주요 기능 (Key Features)

- **실험 관리 (Experiment Management)**: Chunk Size, Overlap, LLM 모델 등을 자유롭게 변경하며 RAG 성능을 테스트하고 기록합니다.
- **Hybrid Search**:
  - **Vector Search (PGVector)**: 문맥 기반 유사도 검색으로 구체적인 팩트(Fact)와 문장을 찾아냅니다.
  - **Graph Search (Neo4j)**: `기능` ↔ `제약조건` 간의 관계를 추론하여 "A와 B의 공통점은?"과 같은 복잡한 구조적 질문을 해결합니다.
- **Robust Graph Ingestion (안정적인 구축)**:
  - **API Rate Limit 방지**: Google Gemini 무료 티어(RPM 제한)를 고려하여 배치 작업 간 **자동 대기(21초)** 로직이 적용되어 있습니다.
  - **정밀 스키마 적용**: 문서의 '유의사항(Disclaimer)'이나 '제약조건'을 놓치지 않도록 `Constraint`, `Requirement` 노드가 정의되어 있습니다.
- **Dynamic Model Switching**: 채팅 도중 서버 재시작 없이 `Gemini 2.5 Flash`, `1.5 Pro` 등 모델을 즉시 변경하여 테스트할 수 있습니다.
- **Admin Dashboard**: PDF 업로드, 실험 데이터 관리, 모델별 데이터 삭제/초기화 기능을 제공합니다.

## 📂 프로젝트 구조

```
├── client/          # Admin 대시보드 (admin.html) 및 채팅 UI (index.html)
├── server/
│   ├── core/        # DB 설정, 스키마 (JSONB 활용)
│   ├── pipelines/   # 데이터 구축 파이프라인
│   │   ├── ingest_vec.py   # Vector DB 구축
│   │   └── ingest_graph.py # Graph DB 구축 (Rate Limit 처리 포함)
│   └── main.py      # FastAPI 서버 및 엔드포인트
├── docker-compose.yml
└── requirements.txt
```

## 🏗️ 시스템 아키텍처 (System Architecture)

본 프로젝트는 단순한 RAG를 넘어, **실험(Experiment) 기반의 고도화된 하이브리드 아키텍처**를 채택하고 있습니다.

### 1. 실험(Experiment) 중심 설계

- **데이터 격리**: 모든 학습(Ingestion)은 '실험' 단위로 관리됩니다. `Chunk Size`, `Overlap`, `Prompt` 등의 하이퍼파라미터 변경에 따른 성능 변화를 정량적으로 비교할 수 있습니다.
- **JSONB 활용**: PostgreSQL의 `JSONB` 컬럼을 활용하여, 파라미터 스키마가 변경되어도 DB 구조 변경 없이 유연하게 대응합니다.

### 2. Hybrid Retrieval Strategy (Vector + Graph)

- **Vector DB**: 문맥적 유사성 검색 (Dense Retrieval). 문서의 '내용'을 찾습니다.
- **Graph DB**: 논리적 연결성 검색 (Reasoning Retrieval). 문서의 '구조'를 찾습니다.
- **Neighborhood Search**: 단순 키워드 매칭이 아닌, 그래프상의 인접 노드(1~2 hops)를 탐색하여 느슨하게 연결된 관계까지 찾아냅니다.

### 3. Rate Limit Aware Pipeline

- Google Gemini API의 무료 티어 제한을 고려하여, 배치 작업 사이에 지능형 대기 로직(Intelligent Wait)이 내장되어 있어 중단 없는 데이터 구축이 가능합니다.

## 🗺️ 로드맵 (Roadmap)

### Phase 1: 안정화 (Completed) ✅

- [x] Docker 기반 배포 환경 구축
- [x] Hybrid RAG (Vector + Graph) 파이프라인 구현
- [x] 실험 관리(Experiment) 기능 구현

### Phase 2: 고도화 (Current) 🚧

- [ ] **Multi-Modal 지원**: 텍스트뿐만 아니라 이미지(표, 차트)를 분석하여 Graph에 통합
- [ ] **평가 자동화 (Auto-Eval)**: RAGAS 등을 도입하여 답변 품질을 LLM이 자동으로 채점

### Phase 3: 확장 (Planned) 📅

- [ ] **분산 처리**: 데이터 구축 속도 향상을 위한 Worker 노드 분리 (Celery/Redis)
- [ ] **Open Source LLM**: 로컬 GPU(Llama 3 등) 지원 추가

## 🛠️ 설치 및 실행 (Installation)

### 1\. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 API 키를 설정하세요.

```env
GOOGLE_API_KEY=your_google_api_key
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
DB_CONNECTION=postgresql+psycopg2://user:password@localhost:5432/ragdb
```

### 2\. Docker 실행 (초기화 권장)

DB 구조가 변경되었거나 깨끗한 환경에서 시작하려면 **반드시 데이터 볼륨을 삭제**하고 실행해야 합니다.

```bash
# 1. 컨테이너 종료 및 기존 데이터 볼륨 삭제 (완전 초기화)
docker-compose down -v

# 2. 컨테이너 빌드 및 실행
docker-compose up -d --build
```

- 접속 주소:
  - **Chat UI**: `http://localhost:8000/`
  - **Admin**: `http://localhost:8000/admin`
  - **Neo4j Browser**: `http://localhost:7474`

---

## 🕸️ Graph RAG 구축 가이드 (Best Practices)

Graph DB는 구축 비용(시간, API Call)이 높으므로, 정확한 데이터를 위해 아래 설정을 권장합니다.

### 1\. 모델 선택 (Model Selection)

- **구축용 (Extractor)**: 반드시 **`gemini-1.5-pro`** 또는 \*\*`gemini-2.5-pro`\*\*와 같은 **고성능 모델**을 선택하세요.
  - `Flash` 모델은 속도는 빠르지만, 문서 구석의 '유의사항'이나 '제약조건' 연결을 놓칠 확률이 높습니다.
- **채팅용 (Chat)**: 구축된 데이터를 조회할 때는 `Flash` 모델을 사용해도 무방합니다.

### 2\. 추천 설정값 (Recommended Config)

- **Chunk Size**: `600` \~ `800` (작게 설정하여 텍스트 밀도를 높여야 관계 추출이 잘 됩니다.)
- **Overlap**: `100`

### 3\. 구축 소요 시간 안내

- 무료 티어(Free Tier)의 `429 ResourceExhausted` 오류를 방지하기 위해, 시스템은 데이터를 1개 배치(Batch) 처리할 때마다 **약 20초간 대기**합니다.
- 따라서 문서 분량에 따라 구축에 수 분 이상 소요될 수 있습니다. (서버 로그에서 `Waiting 21s...` 메시지 확인 가능)

---

## 📊 Knowledge Graph Schema

LLM은 문서를 분석하여 아래 정의된 노드와 관계로 지식 그래프를 생성합니다.

### Nodes (노드)

- `Product`: 제품명 (예: Galaxy S25)
- `Feature`: 주요 기능 (예: 실시간 통역)
- `Constraint` / `Requirement`: **제약 조건 및 필수 요건** (예: 삼성 계정, 네트워크 연결)
- `Spec`: 제품 사양
- `Component`: 하드웨어 구성 요소

### Relationships (관계)

- `(:Feature)-[:REQUIRES]->(:Constraint)`: 기능이 특정 조건을 필요로 함
- `(:Product)-[:HAS_FEATURE]->(:Feature)`: 제품이 기능을 포함함
- `(:Feature)-[:HAS_CONDITION]->(:Condition)`

---

## 🛠️ 트러블슈팅 (Troubleshooting)

### Q. "429 You exceeded your current quota" 오류가 발생해요.

- Google Gemini 무료 티어의 하루(50회) 또는 분당 사용량을 초과한 경우입니다.
- **해결책**:
  1.  `ingest_graph.py`의 자동 대기 로직(21초)이 적용되어 있는지 확인하세요.
  2.  다른 Google 계정의 API Key를 사용하거나, 할당량이 초기화되는 다음 날 다시 시도하세요.

### Q. Graph 구축 중 "The node property 'id' is reserved" 오류 발생

- Neo4j의 예약어인 `id`를 속성명으로 사용할 수 없어 발생한 문제입니다.
- **해결책**: 최신 코드에는 `id` 대신 **`name`** 속성을 사용하도록 수정되어 있습니다. `ingest_graph.py`를 업데이트하세요.

### Q. DB를 완전히 초기화하고 싶어요.

- Docker Volume을 포함하여 깨끗하게 지우려면 아래 명령어를 사용하세요.

<!-- end list -->

```bash
docker-compose down -v
docker-compose up -d --build
```
