import json
from openai import OpenAI
import os
from dotenv import load_dotenv
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from services.rag_service import generate_rag_response
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

REJECTION_TEMPLATES = {
    "라이언": {
        "text": "지금 중요한 건 그게 아닐 텐데요. 수사와 관련 없는 이야기는 나중에 하시죠.",
        "stat_effect": { "suspicion": 0, "affection": -5 } 
    },
    "어피치": {
        "text": "에이~ 형사님도 참! 지금 그런 얘기를 할 때가 아니잖아요~",
        "stat_effect": { "suspicion": 0, "affection": -5 }
    },
    "무지": {
        "text": "아... 네? 잘 못 들었어요... 너무 졸려서... 사건 이야기 아니면 다음에 해주세요...",
        "stat_effect": { "suspicion": 0, "affection": -5 }
    },
    "프로도": {
        "text": "시간 낭비군. 그런 쓸데없는 얘기를 할 거면 이만 가보지.",
        "stat_effect": { "suspicion": 0, "affection": -5 }
    }
}

def classify_intent(user_msg):
    prompt = f"""
    너는 미스터리 추리 게임의 시스템 컨트롤러다. 
    유저의 입력이 게임 내러티브에 포함되는지 판단하고, 특정 아이템이나 결정적 증거를 추출하라.

    ### 아이템 목록
    - 갈색 털뭉치(ITEM_01), 커피 자국(ITEM_02), 보안카드(ITEM_03), 초콜릿 봉지(ITEM_04) 

    ### 분류 규칙
    0. Investigation: 사건, 알리바이, 증거물, 용의자 행적 관련 질문.
    1. Social: 인사, 칭찬, 캐릭터 신상 질문 등 라포 형성 시도.
    2. Irrelevant: 세계관과 무관한 외부 정보(날씨, 주식 등).

    ### 분류 규칙에 대한 추가 지침
    의도를 파악하기 힘들더라도 앞선 대화의 연장선인 것 같은 경우에는 0 혹은 1로 분류.
    아래는 로그의 예시이다.
      "role": "USER", "message": "프로도, 정말로 아는 게 아무것도 없어,
      "role": "NPC", "message": "하, 진짜 웃긴 질문이네. 난 당신보다 더 많은 걸 알고 있을지도 몰라.",
      "role": "USER", "message": "그래? 뭘 알고있는데,
      "role": "NPC", "message": "어이, 농담으로 받아들여야겠는데? 겉으로 보이는 게 다가 아니란 거 아직 모르나 보네.",
      "role": "USER", "message": "농담으로 받아들여야한다니 그게 무슨 소리야,
    이 로그에서도 "USER"의 메세지와 같이 NPC와 대화하는 듯한 context로 판단될 시에는 0혹은 1로 분류한다.
      
    ### 결정적 증거 판단 (is_critical_evidence)
    - 유저가 [프로도]를 상대로 다음 두 가지 요소를 동시에 언급하는지 판단하라:
      1. '갈색 털뭉치(fur_ball)' 아이템 제시 또는 언급.
      2. '무지'가 '프로도'와 '부딪혔다'는 사실(혹은 커피를 쏟았다는 사실)에 대한 추궁.
    - 위 두 조건이 모두 충족되면 true, 아니면 false이다.

    유저 메시지: "{user_msg}"
    
    출력 형식(JSON):
    {{
        "intent_code": 0|1|2,
        "detected_item": "ITEM_아이템ID 또는 null",
        "is_critical_evidence": true|false
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)