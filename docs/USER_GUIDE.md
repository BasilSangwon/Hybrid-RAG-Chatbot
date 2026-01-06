# 📖 User Guide (사용자 가이드)

## 🖥️ Admin Dashboard

`http://localhost:8000/admin`에서 접속할 수 있는 관리자 페이지입니다.

### 1. 시스템 설정 (Configuration)

시스템의 페르소나와 답변 정책을 설정합니다.

- **Active Persona**: 챗봇의 말투와 역할을 정의합니다. (예: "친절한 고객센터 직원")
- **답변 지침**: 특정 상황에서 어떻게 답변해야 할지 규칙을 정합니다. (예: "경쟁사 질문에는 답변하지 않는다")

### 2. 지식 데이터 학습 (Ingestion) ⭐ 중요

가장 핵심적인 기능으로, PDF 문서를 업로드하고 학습시킵니다.

#### 단계별 학습 방법:

1. **PDF 업로드**: `File Upload` 섹션에서 문서를 선택하고 업로드합니다.
2. **Experiment 설정**:
   - `Chunk Size`: 문서 조각 크기 (보통 500~1000 권장)
   - `Overlap`: 조각 간 중복 구간 (보통 50~100)
   - `Model`: 추출에 사용할 LLM 선택 (`gemini-2.5-flash` 권장)
3. **학습 시작**:
   - `⚡ Vector DB`: 단순 검색용 인덱스 생성
   - `🕸️ Graph DB`: 지식 그래프 구축 (오래 걸릴 수 있음, 자동 대기 기능 작동)

### 3. 품질 평가 & QA (Evaluation)

- **Q&A 자동 생성**: PDF를 기반으로 예상 질문/답변 세트를 AI가 자동으로 만들어줍니다.
- **RAGAS 평가**: 현재 모델의 답변 품질을 점수(Faithfulness, Relevance, Precision)로 측정합니다.

---

## 💬 Chat Interface

`http://localhost:8000/`에서 챗봇과 대화할 수 있습니다.

### 주요 기능

1. **Model Selection**: 우측 상단에서 `실험(Experiment)`과 `Chat Model`을 실시간으로 변경하며 테스트할 수 있습니다.
2. **Hybrid Search Result**: 답변 하단에 **[Vector Context]**와 **[Graph Context]**가 표시되어, 챗봇이 어떤 근거로 답변했는지 투명하게 확인할 수 있습니다.

> 💡 **Tip**: 처음 실행 시에는 반드시 **Admin 페이지**에서 최소 하나 이상의 실험(Experiment)을 생성해야 채팅이 가능합니다.
