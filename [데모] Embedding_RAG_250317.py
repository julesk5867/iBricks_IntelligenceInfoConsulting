import json
import torch
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import re
from konlpy.tag import Okt  # More widely available than Mecab
from rank_bm25 import BM25Okapi

# 파일 로드
filepath = r"/content/drive/MyDrive/[아이브릭스/데모_1293_표및텍스트결과추출_250313.json"
with open(filepath, 'r') as f:
    data = json.load(f)

# ================= 1. 향상된 임베딩 모델 사용 =================
# KoSBERT 모델 사용 (의미적 유사성에 특화된 모델)
model = SentenceTransformer('jhgan/ko-sbert-nli')


# ================= 2. 텍스트 전처리 함수 =================
def preprocess_text(text):
    if not isinstance(text, str):
        return ""

    # 기본 전처리
    text = re.sub(r'\s+', ' ', text)  # 여러 공백을 하나로
    text = text.strip()

    # 특수 문자 정리 (단, 의미있는 특수문자는 유지)
    text = re.sub(r'[^\w\s\.\,\?\!\(\)\[\]\:\;\-\_\']', ' ', text)

    return text


# ================= 3. 한국어 자연어 처리 도구 초기화 =================
okt = Okt()


def extract_keywords(text):
    if not isinstance(text, str):
        return ""

    # 명사 추출
    nouns = okt.nouns(text)

    # 짧은 명사 필터링 (한글자 명사 제거)
    filtered_nouns = [noun for noun in nouns if len(noun) > 1]

    # 명사가 없는 경우, 형태소 분석 결과에서 명사, 동사, 형용사 태그를 가진 단어 추출
    if not filtered_nouns:
        pos_tags = okt.pos(text)
        filtered_nouns = [word for word, pos in pos_tags if pos in ['Noun', 'Verb', 'Adjective'] and len(word) > 1]

    return ' '.join(filtered_nouns)


# ================= 4. 쿼리 확장 함수 =================
def expand_query(query_text):
    # 원본 쿼리 전처리
    processed_query = preprocess_text(query_text)

    # 키워드 추출
    keywords = extract_keywords(processed_query)

    # 확장 쿼리 생성
    expanded_queries = [
        processed_query,  # 원본 쿼리
        keywords,  # 추출된 키워드
        processed_query + " " + keywords,  # 원본 + 키워드
    ]

    # 중복 제거 및 빈 문자열 제거
    expanded_queries = [q for q in expanded_queries if q.strip()]
    expanded_queries = list(set(expanded_queries))

    # 쿼리가 질문 형태인 경우 질문 마커 제거한 버전 추가
    if "?" in query_text or "있나요" in query_text or "무엇" in query_text or "어떤" in query_text:
        # 질문형 표현 제거
        simple_query = re.sub(r'\?|있나요|무엇인가요|어떤가요|어떤 것|무엇|어떤', '', processed_query).strip()
        if simple_query and simple_query not in expanded_queries:
            expanded_queries.append(simple_query)

    return expanded_queries


# ================= 5. 향상된 임베딩 생성 함수 =================
def get_enhanced_embedding(text):
    # 텍스트 전처리
    processed_text = preprocess_text(text)

    if not processed_text:
        # 빈 텍스트는 0벡터 반환
        return np.zeros(768)

    # 키워드 추출
    keywords = extract_keywords(processed_text)

    # 임베딩 생성
    text_embedding = model.encode(processed_text)

    # 키워드가 있는 경우 키워드 임베딩 생성 및 결합
    if keywords:
        keyword_embedding = model.encode(keywords)
        # 가중치를 적용한 임베딩 (원본:0.7, 키워드:0.3)
        combined_embedding = 0.7 * text_embedding + 0.3 * keyword_embedding
    else:
        combined_embedding = text_embedding

    # 정규화
    norm = np.linalg.norm(combined_embedding)
    if norm > 0:
        normalized_embedding = combined_embedding / norm
    else:
        normalized_embedding = combined_embedding

    return normalized_embedding


# ================= 6. BM25 모델 초기화 =================
# 문서 토큰화
tokenized_documents = []
for item in data:
    if 'content1' in item and isinstance(item['content1'], str):
        # 각 문서를 띄어쓰기 기준으로 토큰화
        tokens = preprocess_text(item['content1']).split()
        tokenized_documents.append(tokens)
    else:
        tokenized_documents.append([])

# BM25 모델 생성
bm25 = BM25Okapi(tokenized_documents)

# ================= 7. 문서 임베딩 생성 =================
print("문서 임베딩 생성 중...")
for i in range(len(data)):
    if 'content1' in data[i] and isinstance(data[i]['content1'], str):
        data[i]['enhanced_embedding'] = get_enhanced_embedding(data[i]['content1'])
    else:
        data[i]['enhanced_embedding'] = np.zeros(768)  # 콘텐츠가 없는 경우 0벡터


# ================= 8. 유사도 계산 함수 =================
def calculate_similarity_scores(query_text, data_items):
    # 1. 쿼리 전처리 및 확장
    expanded_queries = expand_query(query_text)
    print(f"확장된 쿼리: {expanded_queries}")

    # 2. 쿼리 임베딩 생성
    query_embeddings = [get_enhanced_embedding(query) for query in expanded_queries]

    # 3. BM25 토큰화
    tokenized_queries = [preprocess_text(query).split() for query in expanded_queries]

    # 4. 각 문서마다 점수 계산
    for i, item in enumerate(data_items):
        content_emb = item['enhanced_embedding']

        # 4.1 의미적 유사도 - 코사인 유사도 최대값
        max_cosine_sim = max([
            cosine_similarity([content_emb], [q_emb])[0][0]
            for q_emb in query_embeddings
        ])

        # 4.2 어휘적 유사도 - BM25 점수 최대값 (정규화)
        bm25_scores = [bm25.get_scores(tokenized_query)[i] for tokenized_query in tokenized_queries]
        max_bm25_score = max(bm25_scores) if bm25_scores else 0

        # 최대 BM25 점수 찾기
        all_bm25_scores = []
        for tokenized_query in tokenized_queries:
            scores = bm25.get_scores(tokenized_query)
            all_bm25_scores.extend(scores)

        max_possible_bm25 = max(all_bm25_scores) if all_bm25_scores else 1
        normalized_bm25 = max_bm25_score / max_possible_bm25 if max_possible_bm25 > 0 else 0

        # 4.3 단어 빈도 점수
        content = item.get('content1', '').lower()
        query_keywords = ' '.join([extract_keywords(q) for q in expanded_queries]).lower()
        query_keywords = ' '.join(list(set(query_keywords.split())))  # 중복 제거

        # 쿼리 키워드별 가중치 계산
        keyword_weight = 0
        for keyword in query_keywords.split():
            if len(keyword) > 1 and keyword in content:
                # 키워드 길이에 비례한 가중치 부여 (긴 키워드가 더 중요)
                keyword_weight += len(keyword) * 0.01

        # 4.4 최종 점수 계산 (의미:65%, 어휘:25%, 키워드:10%)
        item['semantic_score'] = max_cosine_sim
        item['lexical_score'] = normalized_bm25
        item['keyword_score'] = min(keyword_weight, 0.2)  # 최대 0.2로 제한

        # 최종 점수는 세 요소의 가중합
        item['final_score'] = (0.65 * max_cosine_sim) + (0.25 * normalized_bm25) + (0.1 * item['keyword_score'])

    return data_items


# ================= 9. 검색 함수 =================
def semantic_search(query_text, data_items, top_k=15):
    # 유사도 점수 계산
    scored_items = calculate_similarity_scores(query_text, data_items)

    # 점수순 정렬 및 상위 K개 추출
    k = min(top_k, len(scored_items))
    top_k_items = sorted(scored_items, key=lambda x: x['final_score'], reverse=True)[:k]

    return top_k_items


# ================= 10. 결과 출력 함수 =================
def print_search_results(results, query_text, target_content=None):
    print(f"\n✅ 쿼리: \"{query_text}\"에 대한 검색 결과:")

    for i, item in enumerate(results):
        print(f"\n🔹 {i + 1}위 청크 (최종 점수: {item['final_score']:.4f}):")
        print(f"  - 의미적 유사도: {item['semantic_score']:.4f}")
        print(f"  - 어휘적 유사도: {item['lexical_score']:.4f}")
        print(f"  - 키워드 점수: {item['keyword_score']:.4f}")
        print(f"  - 내용: {item['content1']}")

    # 목표 청크 검색 (디버깅용)
    if target_content:
        all_ranked = sorted(data, key=lambda x: x['final_score'], reverse=True)
        for i, item in enumerate(all_ranked):
            if target_content in item.get('content1', ''):
                print(f"\n⭐ 목표 청크 \"{target_content}...\"는 {i + 1}위에 랭크되었습니다.")
                print(f"  - 최종 점수: {item['final_score']:.4f}")
                print(f"  - 의미적 유사도: {item['semantic_score']:.4f}")
                print(f"  - 어휘적 유사도: {item['lexical_score']:.4f}")
                print(f"  - 키워드 점수: {item['keyword_score']:.4f}")
                print(f"  - 전체 내용: {item['content1']}")
                break


# 왜 돼..?

# ================= 11. 실행 예시 =================
# 샘플 쿼리 실행
query_text = "OLED의 장점은 어떤 것이 있나요?"  # 3위
# query_text = "플라스틱 LCD(plastic LCD)가 기존의 유리에 비해 갖고 있는 이익은?"#1위
# query_text = "FMC 사업 활성화를 위해서 정책차원에서는 어떤 방향이 있는가?"#1위
# query_text = "기술적 융햡의 가장 기초적인 단계는?"#1위
# query_text = "미국의 UDC 와 일본의 Pioneer 사가 구현한 것은?"#1위
# query_text = "이용자 관점의 이슈는 서비스 이용 욕구는?"#1위

results = semantic_search(query_text, data, top_k=3)
print_search_results(results, query_text)


# ================= 12. 함수화하여 재사용 가능하게 =================
def process_query(query_text, target_content=None):
    """
    주어진 쿼리로 검색을 수행하고 결과를 반환하는 함수

    Args:
        query_text (str): 검색 쿼리
        target_content (str, optional): 목표 청크의 일부 내용 (디버깅용)

    Returns:
        list: 상위 검색 결과 목록
    """
    results = semantic_search(query_text, data, top_k=15)
    print_search_results(results, query_text, target_content)
    return results

# 함수 사용 예시:
# process_query("OLED의 장점은 어떤 것이 있나요?", "OLED는 자체발광 디스플레이로")