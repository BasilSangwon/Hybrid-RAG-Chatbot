# Dockerfile

# 1. pgvector 기반 이미지 사용
FROM ankane/pgvector:latest

# 2. 설치에 필요한 변수 설정 (PostgreSQL 15 가정)
ARG PG_VERSION=15
ENV PG_VERSION=${PG_VERSION}
# [추가] pg_bigm의 안정된 릴리스 태그 지정
ARG PG_BIGM_TAG=v1.2-20240606

USER root

# 3. 개발 도구 및 필수 패키지 설치 + 로케일 설정
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    unzip \
    build-essential \
    postgresql-server-dev-$PG_VERSION \
    locales && \
    rm -rf /var/lib/apt/lists/* && \
    localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8 && \
    localedef -i ko_KR -c -f UTF-8 -A /usr/share/locale/locale.alias ko_KR.UTF-8

ENV LANG ko_KR.utf8

# 4. [최종 수정] pg_bigm 소스 ZIP 다운로드, 컴파일, 설치
RUN echo "Compiling pg_bigm for PostgreSQL $PG_VERSION..." && \
    wget --no-check-certificate https://github.com/pgbigm/pg_bigm/archive/${PG_BIGM_TAG}.zip -O pg_bigm_source.zip && \
    unzip pg_bigm_source.zip && \
    cd pg_bigm* && \ 
    make USE_PGXS=1 && \
    make USE_PGXS=1 install

# 5. 설치 후 불필요한 개발 도구와 소스 정리 (컨테이너 경량화)
RUN cd / && \
    rm -rf pg_bigm* && \
    apt-get purge -y unzip wget build-essential postgresql-server-dev-$PG_VERSION && \
    apt-get autoremove -y

USER postgres