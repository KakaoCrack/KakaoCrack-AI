from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def update_summary(npc_name, old_summary, history_str):
    system_prompt = f"""
    너는 미스터리 추리 게임의 유능한 시나리오 작가다.
    NPC '{npc_name}'와 유저의 최근 대화 내용을 바탕으로 기존의 [장기 기억 요약]을 업데이트해야 한다.
    NPC가 거짓말을 할 수 있기 때문에 주관을 넣은 요약을 배제하고, 오로지 사실만을 기재한 요약을 진행하라.

    [기존 요약]: {old_summary}
    [최근 대화]:
    {history_str}

    ### 지침:
    1. 기존 요약과 새로운 대화 내용 중 중요한 사실(알리바이, 태도 변화, 새로운 단서)을 통합하라.
    2. 너무 길지 않게 2~3문장 내외의 한국어로 요약하라.
    3. 반드시 업데이트된 요약 텍스트만 출력하라.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system_prompt}]
    )
    
    return response.choices[0].message.content.strip()