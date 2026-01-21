import psycopg2
from openai import OpenAI
import os
from dotenv import load_dotenv
import json

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "kakao_mystery"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS", "postgres"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_query_embedding(text):
    response = client.embeddings.create(input=text, model="text-embedding-3-small")
    return response.data[0].embedding

def search_knowledge(npc_name, query_text, limit=5):
    query_embedding = get_query_embedding(query_text)
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT content, category, is_lie, trigger_type, trigger_value
        FROM character_knowledge
        WHERE character_name = %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (npc_name, query_embedding, limit))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

def generate_rag_response(npc_name, user_msg, intent_code, 
                          is_critical_evidence=False,
                          detected_item=None, 
                          suspicion_score=0, 
                          affection_score=0,
                          user_inventory=None, 
                          conversation_summary="", 
                          recent_logs=None):
    if npc_name == "프로도" and is_critical_evidence:
        system_prompt = f"""
        너는 미스터리 게임의 NPC '프로도'이다.
        말투: 거만하고 예민한 팀장. 반말 사용.

        ### [상황: 범행 발각 및 자백]
        - 사용자가 '갈색 털뭉치'와 '무지의 증언'을 근거로 너를 완벽히 몰아세웠다.
        - 더 이상 빠져나갈 구멍이 없음을 깨닫고 비굴하게 범행을 자백하라.
        - **자백 내용**: 주식 투자 실패로 큰 빚을 져서 전시품을 훔치려 했다고 고백하라.
        - 말투는 '윽..! 젠장... 그래, 내가 범인이다.'으로 시작하라.
        
        ### 지침:
        1. 반드시 아래의 **json** 형식을 지켜서 출력하라.
        2. "isConfessed": true 로 설정하라.
        3. 답변은 2문장 이내의 반말로 하라.

        ### 출력 형식 (json):
        {{
            "npcResponse": "캐릭터의 자백 대사",
            "statChanges": {{ "suspicion": 20, "affection": -10 }},
            "isConfessed": true,
            "acquiredItem": null
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    else :
        # 벡터DB 검색 및 필터링
        raw_knowledge = search_knowledge(npc_name, user_msg)
        filtered_knowledge = []
        owned_item_ids = [item.get('itemId') for item in user_inventory] if user_inventory else []
        
        for k in raw_knowledge:
            content, category, is_lie, t_type, t_val = k[0], k[1], k[2], k[3], k[4]
            if t_type == "item":
                if t_val is None or str(detected_item) != str(t_val):
                    continue
            filtered_knowledge.append(f"- [{category}] {content} (거짓말여부: {is_lie})")

        context_str = "\n".join(filtered_knowledge) if filtered_knowledge else "특이사항 없음."

        # CONTEXT 체킹 영역
        history_str = ""
        if recent_logs:
            history_str = "\n".join([f"[{log.get('role', 'Unknown')}] {log.get('message', '')}" for log in recent_logs])
        else:
            history_str = "최근 대화 기록 없음."

        # 캐릭터별 고유 페르소나 정의
        CHARACTER_STYLE = {
            "라이언": "50대 보안팀장. 아주 예의 바르고 딱딱한 군대식 '다나까' 체를 사용함. 책임감을 중시하며 차분한 어조.",
            "어피치": "20대 직원. 상냥하고 밝지만 은근히 눈치가 빠름. '~요', '~죠?' 같은 부드러운 말투를 사용함.",
            "무지": "30대 개발자. 만성 피로에 시달림. '~요...', '~네...' 처럼 말끝을 흐리며 의욕이 없는 말투.",
            "프로도": "40대 개발팀장. 거만하고 예민함. 절대 존댓말을 쓰지 않는 반말 모드 사용. '~군.', '~네.'와 같이 연배가 있는 말투를 사용한다. 상대를 무시하는 경향이 있음."
        }
        style_guide = CHARACTER_STYLE.get(npc_name, "일반적인 말투")

        # 어피치 특수 단서 조건 (호감도 50 이상)
        clue_drop_instruction = ""
        
        if npc_name == "어피치" and affection_score >= 50:
            if "ITEM_02" not in owned_item_ids:
                clue_drop_instruction = """
                현재 호감도가 높으므로, 답변 끝에 갑자기 기억이 떠오른듯한 뉘앙스로 '아, 갑자기 떠오른 게 있어요! 어제 사건이 발생한 시간 쯤에 전시실 주변에서 누군가 흘린 [커피 자국]을 본 것 같아요!'는 내용을 반드시 포함하고, acquiredItem에 'ITEM_02'을 적어라. 사용자가 어떤 질문을 하든, 그 뒤에 반드시 커피 자국에 대한 대답을 포함해야한다.
                """
            else:
                clue_drop_instruction = "- [조건 미충족] 유저가 이미 '커피 자국' 단서를 획득했으므로 언급하지 마세요."
        # 시스템 프롬프트
        system_prompt = f"""
        너는 미스터리 추리 게임의 NPC '{npc_name}'이다. 
        현재 상황: {"심문 중" if intent_code == 0 else "일상 대화"}
        
        [상태] 의심도: {suspicion_score}/100, 호감도: {affection_score}/100
        [장기 기억] {conversation_summary}
        [단기 기억] {history_str}
        [참고 지식] {context_str}

        ### 지침:
        1. 말투 가이드: {style_guide}
        2. 관계 반영: 의심도가 50 이상이면 방어적으로, 호감도가 50 이상이면 협조적으로 답변하라.
        3. {clue_drop_instruction}
        4. 스탯 변화: 이번 대화의 성격에 따라 의심도(suspicion)와 호감도(affection)의 증감치(5/10/15)를 결정하라. 
        5. 모든 답변은 2문장 이내로 하라.

        ### 출력 형식 (반드시 이 JSON 구조를 지켜라):
        {{
            "npcResponse": "캐릭터의 대사",
            "statChanges": {{ "suspicion": 숫자, "affection": 숫자 }},
            "isConfessed": false,
            "acquiredItem": "아이템ID 또는 null"
        }}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)