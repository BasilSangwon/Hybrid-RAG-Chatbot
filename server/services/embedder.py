import torch
from langchain_huggingface import HuggingFaceEmbeddings

def get_bge_m3_embedding():
    # 1. 장치 확인 (GPU 우선)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"   🚀 [Model] BAAI/bge-m3 로드 중... (Device: {device.upper()})", flush=True)

    # 2. LangChain 호환 임베딩 생성
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",
        model_kwargs={'device': device},
        # [중요] 코사인 유사도 검색을 위해 정규화(Normalize) 필수
        encode_kwargs={'normalize_embeddings': True} 
    )
    return embeddings
