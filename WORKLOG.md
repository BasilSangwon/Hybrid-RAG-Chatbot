# 🛠️ 개발 작업 일지 (Dev Log)

## 2024-12-15 Admin Q&A 기능 개선
### ✅ 완료된 작업

#### 1. Knowledge Base 관리 기능 추가
- **검색 기능**: 실시간 필터링 (질문/답변 검색)
- **전체 삭제**: `DELETE /api/answers_all` API + 확인 다이얼로그

#### 2. Q&A 자동 생성 개선
| 기능 | 설명 |
|------|------|
| 생성 개수 설정 | 1~50개 범위 지정 가능 |
| 청크 기반 처리 | 전체 PDF 커버 (5,000자/청크) |
| 동적 토큰 예상 | PDF 선택 시 실시간 계산 |
| 작업 상태 표시 | 진행 중 UI + 완료 알림 |
| 작업 취소 | threading.Event 기반 안전한 취소 |

#### 3. API 추가
- `DELETE /api/answers_all` - 지식 전체 삭제
- `GET /api/file_info/{filename}` - PDF 분석 정보
- `POST /api/generate_qa/cancel` - Q&A 생성 취소

### 📁 변경된 파일
- `server/main.py`
- `server/pipelines/qa_gen.py`
- `client/admin.html`
- `client/js/admin/evaluation.js`
- `client/js/admin/main.js`
- `client/js/admin/config.js`

## [2025-12-04] RAG 시스템 대규모 리팩토링: 실험(Experiment) 기반 아키텍처 전환

### 1. 배경 및 문제점 (Background & Problem)
* **실험 관리의 부재:** 기존 시스템은 단일 DB(`manual_docs`)에 데이터를 계속 덮어쓰거나 추가하는 방식이라, `Chunk Size`나 `Overlap` 변경에 따른 성능 변화를 정량적으로 비교하기 어려웠음.
* **데이터 오염:** 여러 LLM(Gemini Flash vs Pro)으로 생성한 Graph 데이터가 섞여서, 특정 모델의 성능을 검증할 수 없었음.
* **Graph 검색 실패:** LLM이 생성한 Cypher 쿼리가 너무 엄격한 관계(Relationship)를 요구하여, 데이터가 있음에도 `Graph search failed`가 빈번하게 발생함.
* **Vector 검색 한계:** 문서의 구석(각주, 주의사항)에 있는 중요 정보를 `k=4` 설정으로는 가져오지 못하는 문제 확인.

### 2. 주요 변경 사항 (Key Changes)

#### A. 아키텍처 및 DB 설계 (Architecture & DB)
* **실험(Experiment) 테이블 도입:**
    * 모든 학습(Ingestion) 행위를 하나의 '실험'으로 정의.
    * **JSONB 도입:** `config` 컬럼을 PostgreSQL `JSONB` 타입으로 설정하여, 추후 설정값(Chunk, Temperature, Prompt 등)이 늘어나도 DB 스키마 변경 없이 유연하게 저장 가능하도록 설계.
    * **데이터 격리:** Vector DB는 `collection_name`, Graph DB는 `experiment_id` 속성을 사용하여 실험별 데이터를 완벽하게 분리.

#### B. 폴더 구조 재정비 (Refactoring)
* **표준 구조 적용:** `pipeline` 폴더를 `server` 내부로 이동시켜 의존성 문제 해결 및 Docker 빌드 최적화.
    * `server/core/`: DB 및 설정
    * `server/services/`: 공통 모듈 (Embedder 등)
    * `server/pipelines/`: 학습 실행 스크립트

#### C. Graph RAG 로직 개선 (Engineering)
* **Schema 강제 (Ingestion):** `LLMGraphTransformer` 사용 시 `allowed_nodes`와 `allowed_rels`를 지정하여, LLM이 임의의 라벨(예: '생성', 'WITH')을 만들지 못하도록 통제.
* **검색 로직 변경 (Retrieval):**
    * 기존: 엄격한 관계 탐색 (`MATCH (a)-[HAS_FEATURE]->(b)`) → **실패 원인**
    * 변경: **Broad Keyword Search** (`toLower(n.id) CONTAINS 'keyword'`) 및 **Neighborhood Search** (`-[*1..2]-`) 도입.
    * 효과: 연결 고리가 느슨하거나 정확한 관계명이 아니더라도 관련 노드를 모두 찾아내어 답변 성공률 비약적 상승.

#### D. Vector RAG 튜닝
* **검색 범위 확장:** `k` 값을 4에서 **10~20**으로 늘려, 문서의 부록이나 주의사항(Fine print)까지 Context에 포함되도록 개선.

#### E. UI/UX (Admin Dashboard)
* **실험 제어:** Chunk Size, Overlap, Model 등을 직접 입력하여 실험을 생성하는 UI 구현.
* **동적 모델 로딩:** Google API (`/api/models`)를 호출하여 현재 사용 가능한 최신 LLM 리스트를 실시간으로 불러오도록 변경.
* **현황 모니터링:** DB에 저장된 모델별 노드 개수 현황을 시각화.

### 3. 결과 (Result)
* **성능:** Graph RAG가 "정보 없음"을 뱉던 문제 해결. `[실시간 통역] - [네트워크 조건]` 관계를 찾아내어 답변 성공.
* **확장성:** 다양한 청크 사이즈와 모델 조합을 무제한으로 실험하고 비교할 수 있는 **LLMOps 기초 환경** 구축 완료.