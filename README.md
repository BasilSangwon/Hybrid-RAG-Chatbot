# 🧪 AI RAG Laboratory
실험(Experiment) 기반의 하이브리드 RAG(Vector + Graph) 관리 시스템입니다.

## 🚀 주요 기능
- **실험 관리:** Chunk Size, Overlap, LLM 모델 등을 자유롭게 변경하며 실험 가능.
- **Hybrid Search:** Vector DB(문맥)와 Graph DB(관계)를 동시에 검색.
- **유연한 아키텍처:** PostgreSQL JSONB를 활용하여 설정값 변경에 유연하게 대응.

## 📂 프로젝트 구조
- `client/`: Admin 대시보드 및 채팅 UI
- `server/core/`: DB 설정 및 스키마 (JSONB 적용)
- `server/pipelines/`: 데이터 학습 파이프라인 (Ingestion)

## 🛠️ 설치 및 실행 (주의: 초기화 필수)
구조가 변경되었으므로 반드시 기존 데이터를 삭제하고 재구동해야 합니다.
```bash
docker-compose down -v
docker-compose up -d --build