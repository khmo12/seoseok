# -*- coding: utf-8 -*-
"""
서석고등학교 교장 시뮬레이션 - 게임 데이터 및 핵심 로직 (웹서버용)
- 이 모듈은 순수 데이터/로직만 담당하며 UI(Flask 라우트)는 app.py에서 처리합니다.
- Gemini 연동: 환경변수 GEMINI_API_KEY (또는 GOOGLE_API_KEY)를 읽어 사용합니다.
  - 키가 없거나 호출이 실패하면 자동으로 키워드 기반 로직으로 폴백합니다.
"""

import random
import json
import os

# ----------------------------
# 상태 및 데이터
# ----------------------------

def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


class GameState:
    def __init__(self):
        self.budget = 55
        self.reputation = 50
        self.satisfaction = 55
        self.morale = 55
        self.academic = 50
        self.month_index = 0  # 0~11, REQUIRED_EVENTS 인덱스와 대응

    def apply(self, effects: dict):
        self.budget = clamp(self.budget + effects.get("budget", 0))
        self.reputation = clamp(self.reputation + effects.get("reputation", 0))
        self.satisfaction = clamp(self.satisfaction + effects.get("satisfaction", 0))
        self.morale = clamp(self.morale + effects.get("morale", 0))
        self.academic = clamp(self.academic + effects.get("academic", 0))

    def is_over(self):
        if self.budget <= 0:
            return "budget"
        if self.reputation <= 0:
            return "reputation"
        if self.morale <= 0:
            return "morale"
        if self.satisfaction <= 0:
            return "satisfaction"
        return None


STAT_LABELS = {"budget": "예산", "reputation": "평판", "satisfaction": "학생만족도",
               "morale": "교사사기", "academic": "학업성취도"}

MONTH_LABELS = ["3월", "3월", "4월", "5월", "5월", "6월", "7월", "9월", "10월", "11월", "12월", "2월(익년)"]

EARLY_ENDINGS = {
    "budget": ("재정 파탄",
        "교육청 감사 결과, 서석고의 재정 상태는 회생 불가 판정을 받았습니다. "
        "당신은 임기 도중 예산 관리 부실 책임을 지고 물러납니다."),
    "reputation": ("신뢰 붕괴",
        "학부모 총회에서 불신임 결의안이 통과되었습니다. 언론에도 부정적인 기사가 "
        "여러 차례 실리며, 당신은 결국 사임을 선택합니다."),
    "morale": ("교사들의 이탈",
        "핵심 교사들이 줄줄이 타 학교로 전출을 신청했습니다. 빈 교무실을 보며, "
        "당신은 조용히 사직서를 씁니다."),
    "satisfaction": ("학생들의 등돌림",
        "전교 학생회가 교장 퇴진을 요구하는 서명운동을 시작했습니다. 더 이상 학교를 "
        "이끌 명분을 잃은 당신은 물러나기로 합니다."),
}

# ----------------------------
# 등장인물 (스탯 변화에 반응)
# ----------------------------

CHARACTERS = {
    "student": {"name": "학생회장 박주환", "role": "학생회장", "stats": ["satisfaction"],
                "persona": ("2학년 전교 1등 출신에 극단적으로 카리스마 넘치는 학생회장. 겉으로는 예의 바르고 "
                            "논리정연하지만, 흥분하면 혁명가처럼 말투가 격해지고 가끔 소름 끼치도록 진지해진다. "
                            "인스타 감성 말투와 급발진 사이를 오간다.")},
    "chairman": {"name": "재단 이사장 최용훈", "role": "재단 이사장", "stats": ["budget", "reputation", "morale"],
                 "persona": ("재벌 3세 느낌의 허세 가득한 재단 이사장. 돈 얘기만 나오면 눈이 돌아가고, "
                             "즉흥적이고 예측불가능하며 자기 골프 스코어나 요트 얘기를 뜬금없이 섞는다. "
                             "화가 나면 과장되게 위협적이고, 기분 좋으면 과하게 통 크다.")},
    "parent": {"name": "학부모회 대표 정미경", "role": "학부모회 대표", "stats": ["academic"],
               "persona": ("강남 사모님st 학부모회 대표. 우아한 말투 속에 살벌한 압박이 숨어있고, "
                           "성적 얘기만 나오면 극도로 예민해지며 드라마틱하게 오버한다. "
                           "은근한 뒷담화와 과장된 걱정을 섞어 말한다.")},
}

STAT_TO_CHARACTER = {
    "satisfaction": "student",
    "budget": "chairman",
    "reputation": "chairman",
    "morale": "chairman",
    "academic": "parent",
}

REACTION_LINES = {
    "student": {
        "very_low": ["\"교장선생님, 저희 진짜 힘듭니다. 학생회 차원에서 공식 항의를 검토하겠습니다.\"",
                     "\"솔직히... 요즘 학교 다니는 게 재미가 없어요. 이대로는 안 됩니다.\""],
        "low": ["\"학생들 사이에 불만이 조금씩 쌓이고 있어요. 신경 좀 써주세요.\""],
        "mid": ["\"나쁘진 않은데, 특별히 좋아진 것도 없는 것 같아요.\""],
        "high": ["\"요즘 애들 사이에서 학교 분위기 좋다는 얘기 많이 나와요!\""],
        "very_high": ["\"교장선생님 최고예요! 전교생이 다 좋아해요!\"",
                      "\"이 정도면 저희가 먼저 감사 인사 드려야 할 것 같은데요?\""],
    },
    "chairman": {
        "very_low": ["\"이런 식이면 이사회에서 가만있지 않을 겁니다. 재고해 주십시오.\"",
                     "\"학교 경영이 이래서야 되겠습니까. 다음 이사회 안건으로 올리겠습니다.\""],
        "low": ["\"숫자가 영 마음에 걸리는군요. 좀 더 신중한 운영이 필요해 보입니다.\""],
        "mid": ["\"무난합니다만, 이사회에 보고할 만한 성과는 아직 부족하군요.\""],
        "high": ["\"운영이 안정적이군요. 이사회에서도 좋게 볼 겁니다.\""],
        "very_high": ["\"훌륭합니다. 이사회 차원에서 표창을 건의해보겠습니다.\"",
                      "\"이 정도 성과면 재단에서도 전폭적으로 지원할 명분이 생기는군요.\""],
    },
    "parent": {
        "very_low": ["\"우리 아이들 성적이 이래서야... 학부모회 차원에서 면담을 요청드립니다.\""],
        "low": ["\"학업 쪽이 좀 아쉽다는 얘기가 학부모님들 사이에서 나오고 있어요.\""],
        "mid": ["\"평범한 수준이네요. 조금만 더 신경 써주시면 좋겠어요.\""],
        "high": ["\"아이들 성적이 오르고 있다고 하니 다들 안심하고 있어요.\""],
        "very_high": ["\"학부모님들 사이에서 서석고 보내길 잘했다는 말이 자자해요!\""],
    },
}


def _tier(value):
    if value < 25:
        return "very_low"
    if value < 45:
        return "low"
    if value < 60:
        return "mid"
    if value < 80:
        return "high"
    return "very_high"


def _pick_reacting_character(effects: dict):
    nonzero = {k: v for k, v in effects.items() if v}
    if not nonzero:
        return None
    top_stat = max(nonzero, key=lambda k: abs(nonzero[k]))
    if abs(nonzero[top_stat]) < 4:
        return None
    char_key = STAT_TO_CHARACTER.get(top_stat)
    if not char_key:
        return None
    return char_key, top_stat, nonzero[top_stat]


def get_character_reaction_static(state: GameState, effects: dict):
    picked = _pick_reacting_character(effects)
    if picked is None:
        return None
    char_key, top_stat, _delta = picked
    char = CHARACTERS[char_key]
    cur_val = getattr(state, top_stat)
    tier = _tier(cur_val)
    line = random.choice(REACTION_LINES[char_key][tier])
    return f"<b>{char['name']}</b> ({char['role']}): {line}"


def get_character_reaction(state: GameState, effects: dict, event_title: str, choice_text: str):
    picked = _pick_reacting_character(effects)
    if picked is None:
        return None
    char_key, top_stat, delta = picked
    char = CHARACTERS[char_key]
    ai_line = ai_generate_reaction(char, state, top_stat, delta, event_title, choice_text)
    if ai_line:
        return f"<b>{char['name']}</b> ({char['role']}): {ai_line}"
    return get_character_reaction_static(state, effects)


# ----------------------------
# 필수 이벤트 일정
# ----------------------------

MAIN_EVENTS = [
    {"title": "1. 3월 - 취임과 입학식",
     "desc": "당신은 오늘 서석고등학교 제 OO대 교장으로 첫 출근을 했습니다. 신입생 입학식도 겸하는 "
             "자리에서, 취임사와 축사를 통해 어떤 방향을 강조하시겠습니까?",
     "choices": [
        ("입시 성과를 최우선으로 삼겠다고 선언한다.", {"academic": 11, "satisfaction": -6, "morale": -4},
         "교사들 사이에서 '또 성과 압박이냐'는 우려가 나오지만, 일부는 반깁니다."),
        ("학생들의 행복과 자율성을 강조한다.", {"satisfaction": 11, "reputation": -4, "academic": -4},
         "학생들은 환영하지만, 일부 학부모는 '입시는 어떡하냐'며 걱정합니다."),
        ("교사와의 소통·협업을 최우선 가치로 내세운다.", {"morale": 11, "reputation": 4},
         "교사들은 안도하지만, 구체적인 비전이 없다는 지적도 나옵니다."),
     ]},
    {"title": "2. 3월 - 전국연합학력평가(3월 모의고사)",
     "desc": "새 학년 첫 모의고사 성적표가 나왔습니다. 특히 고3 결과가 예상보다 낮아, 학년부장이 대책 마련을 요청합니다.",
     "choices": [
        ("전 학년 대상 새벽·야간 보충수업을 즉시 편성한다.", {"academic": 13, "morale": -8, "satisfaction": -6},
         "성적 개선의 기틀은 마련됐지만, 학생과 교사 모두 피로를 호소합니다."),
        ("데이터를 분석해 취약 단원 중심의 맞춤 특강만 편성한다.", {"academic": 7, "budget": -8, "morale": -2},
         "예산이 들지만 효율적인 접근이라는 평가를 받습니다."),
        ("한 번의 시험 결과에 일희일비하지 않겠다며 기존 방침을 유지한다.", {"morale": 4, "academic": -3},
         "교사들은 안도했지만 일부 학부모는 안일하다고 지적합니다."),
     ]},
    {"title": "3. 4월 - 1학기 중간고사",
     "desc": "1학기 중간고사 기간입니다. 일부 학급에서 커닝 의혹이 제기되었고, 시험 감독 방식에 대한 이견도 나오고 있습니다.",
     "choices": [
        ("전 시험장에 CCTV와 추가 감독관을 투입해 엄격히 관리한다.", {"reputation": 6, "budget": -8, "satisfaction": -4},
         "공정성 논란은 잦아들었지만, 학생들은 감시받는 느낌이라 불만도 있습니다."),
        ("담임 재량에 맡기되 의혹이 제기된 학급만 재조사한다.", {"reputation": 2, "morale": 2},
         "무난하게 넘어갔지만 근본적인 신뢰 회복은 더디게 진행됩니다."),
        ("커닝 의혹을 축소하고 조용히 넘어간다.", {"reputation": -9, "satisfaction": -3},
         "'역시 덮으려 하는구나'라는 여론이 확산되었습니다."),
     ]},
    {"title": "4. 5월 - 체육대회",
     "desc": "전교생이 참여하는 체육대회 준비가 한창입니다. 예산과 안전, 형식을 두고 학생회와 교사들의 의견이 갈립니다.",
     "choices": [
        ("예산을 크게 늘려 반티, 응원전, 외부 진행팀까지 준비한다.", {"budget": -14, "satisfaction": 13, "reputation": 4},
         "역대급 체육대회라는 평가를 받았지만 예산 지출이 상당했습니다."),
        ("학생 자치로 소박하게 진행하되 안전관리만 철저히 한다.", {"budget": -4, "satisfaction": 8, "morale": 3},
         "자율성과 안전이 균형을 이뤘다는 좋은 평가를 받았습니다."),
        ("안전사고 우려로 대회 규모를 대폭 축소한다.", {"satisfaction": -11, "reputation": -3},
         "학생들의 실망이 컸지만, 다행히 사고는 없었습니다."),
     ]},
    {"title": "5. 5월 - 수학여행",
     "desc": "2학년 수학여행 일정과 행선지를 확정해야 합니다. 최근 타 학교 수학여행 안전사고 뉴스로 학부모들의 우려도 큽니다.",
     "choices": [
        ("안전 인증된 업체와 코스로 예정대로 진행한다.", {"satisfaction": 10, "budget": -10, "reputation": 3},
         "학생들은 크게 만족했고, 큰 사고 없이 마무리되었습니다."),
        ("학부모 설명회를 열어 안전대책을 공유한 뒤 진행한다.", {"satisfaction": 7, "reputation": 5, "budget": -6},
         "투명한 소통 덕분에 신뢰도가 함께 올랐습니다."),
        ("안전을 이유로 수학여행을 전면 취소하고 교내 프로그램으로 대체한다.", {"satisfaction": -13, "reputation": 2},
         "일부 학부모는 안심했지만 학생들의 실망이 매우 컸습니다."),
     ]},
    {"title": "6. 6월 - 전국연합학력평가(6월 모의고사)",
     "desc": "고3 수험생들의 실전 감각을 가늠하는 6월 모의고사입니다. 이 성적이 여름방학 학습 전략의 기준이 됩니다.",
     "choices": [
        ("성적 우수자 대상 심화반을 신설한다.", {"academic": 10, "satisfaction": -5, "budget": -6},
         "우수 학생들의 만족도는 높았지만, 소외감을 느끼는 학생들도 생겼습니다."),
        ("전체 학생 대상 자기주도학습 시간을 확대한다.", {"academic": 6, "morale": -3},
         "형평성 있는 접근이라는 평가를 받았습니다."),
        ("담임·교과 교사의 개별 상담으로 방향을 잡는다.", {"academic": 5, "morale": -2, "satisfaction": 3},
         "세심한 접근에 학생 and 학부모 모두 만족했지만 교사 부담이 늘었습니다."),
     ]},
    {"title": "7. 7월 - 1학기 기말고사와 여름방학",
     "desc": "1학기를 마무리하는 기말고사가 끝나고 여름방학이 시작됩니다. 방학 중 보충수업 운영 방식을 정해야 합니다.",
     "choices": [
        ("전 학년 필수 방학특강을 편성한다.", {"academic": 9, "morale": -6, "satisfaction": -7},
         "성적은 오르는 추세지만, 방학 없는 방학이라는 불만이 나왔습니다."),
        ("희망자만 신청받는 선택형 특강으로 운영한다.", {"academic": 4, "satisfaction": 4, "budget": -4},
         "자율성과 학습 기회를 동시에 챙겼다는 호평을 받았습니다."),
        ("방학은 온전히 휴식 기간으로 두고 특강을 운영하지 않는다.", {"satisfaction": 8, "morale": 6, "academic": -6},
         "학생과 교사 모두 재충전했지만, 일부 학부모는 불안해했습니다."),
     ]},
    {"title": "8. 9월 - 2학기 개학과 전국연합학력평가(9월 모의고사)",
     "desc": "2학기가 시작되고, 수능을 앞둔 고3에게는 사실상 마지막 대규모 모의고사인 9월 모의고사 결과가 나왔습니다.",
     "choices": [
        ("수능 D-day 카운트다운과 함께 총력 체제로 전환한다.", {"academic": 12, "morale": -9, "satisfaction": -8},
         "막판 스퍼트 분위기가 조성됐지만, 긴장감이 학교 전체를 짓누릅니다."),
        ("실전 모의 수능(모의평가 방식)을 추가 편성해 적응력을 높인다.", {"academic": 8, "budget": -7, "morale": -3},
         "실전 감각이 올랐다는 평가를 받았습니다."),
        ("멘탈 관리 프로그램과 상담을 대폭 강화한다.", {"satisfaction": 8, "morale": 3, "academic": 2},
         "학생들의 불안감이 줄었고, 예상외로 학습 효율도 올랐습니다."),
     ]},
    {"title": "9. 10월 - 지역 축제 '서석제'",
     "desc": "매년 열리는 학교 축제 '서석제'를 어떤 방식으로 준비할지 학생회가 문의해왔습니다. 수능을 한 달 앞둔 시점이라 반대 의견도 있습니다.",
     "choices": [
        ("예산을 넉넉히 지원해 외부 공연팀까지 초청한다.", {"budget": -13, "satisfaction": 12, "reputation": 4},
         "역대 최고 축제라는 평가를 받았지만 예산 지출이 컸습니다."),
        ("학생 자치로 소박하게 진행하되 전폭적으로 지지한다.", {"budget": -5, "satisfaction": 8, "morale": 3},
         "학생들의 자율성과 만족도가 함께 올랐습니다."),
        ("수능이 임박했다는 이유로 축제를 취소한다.", {"satisfaction": -12, "academic": 3},
         "학생들의 불만이 컸지만, 일부 고3 학부모는 지지했습니다."),
     ]},
    {"title": "10. 11월 - 대학수학능력시험(수능)",
     "desc": "드디어 수능 당일입니다. 고사장 운영과 재학생들의 응원, 시험 이후 케어까지 교장으로서 챙길 것이 많습니다.",
     "choices": [
        ("전 교직원을 동원해 완벽한 고사장 운영과 응원 열기를 조성한다.", {"reputation": 6, "morale": -5, "budget": -5},
         "시험 당일은 매끄럽게 진행됐지만 교직원들의 피로가 누적됐습니다."),
        ("차분하고 담담한 분위기로 평소처럼 운영한다.", {"morale": 3, "satisfaction": 2},
         "과도한 긴장 없이 안정적으로 시험이 마무리되었습니다."),
        ("가채점 직후 즉시 입시 상담 체제를 가동한다.", {"academic": 7, "morale": -4},
         "발빠른 대응에 학생과 학부모 모두 만족했지만 교사들은 지쳤습니다."),
     ]},
    {"title": "11. 12월 - 2학기 기말고사와 대입 결과 발표",
     "desc": "2학기 기말고사와 함께, 3학년 졸업생들의 대입 결과가 속속 발표되고 있습니다. 이 결과는 학교의 평판에 직접적인 영향을 줍니다.",
     "choices": [
        ("결과를 대대적으로 홍보하고 현수막을 내건다.", {"reputation": 9, "satisfaction": -3},
         "좋은 성과에 평판이 크게 올랐지만, 과시적이라는 반응도 있습니다."),
        ("결과와 무관하게 담담히 학생 개개인의 노력을 축하한다.", {"satisfaction": 8, "morale": 5},
         "학생과 교사 모두 따뜻한 마무리라고 느꼈습니다."),
        ("결과를 분석해 내년도 입시 전략 회의를 소집한다.", {"academic": 9, "morale": -3},
         "체계적인 전략이 마련되었지만 교사들은 다소 부담을 느꼈습니다."),
     ]},
    {"title": "12. 2월 - 졸업식, 그리고 임기의 매듭",
     "desc": "어느덧 1년의 마지막, 졸업식 날입니다. 졸업생들 앞에서 마지막 인사를 전할 시간입니다.",
     "choices": [
        ("지난 1년간의 성과와 숫자를 강조하는 연설을 한다.", {"reputation": 6, "satisfaction": -3},
         "성과 중심의 연설에 일부는 뿌듯해했고, 일부는 아쉬워했습니다."),
        ("한 사람 한 사람의 이름을 부르며 개인적인 축하를 전한다.", {"satisfaction": 11, "morale": 6},
         "졸업생과 교사 모두 눈시울을 붉히는 감동적인 순간이었습니다."),
        ("담담하게 감사 인사만 짧게 전한다.", {"reputation": 2},
         "간결했지만 다소 아쉬워하는 반응도 있었습니다."),
     ]},
]

# ----------------------------
# 확률적 돌발 이벤트 풀
# ----------------------------

SIDE_EVENTS = {
    "natural_disaster": [
        {"title": "[자연재해] 태풍 북상", "desc": "대형 태풍이 북상 중입니다. 등교 여부를 오늘 중으로 결정해야 합니다.",
         "choices": [
            ("전면 휴교를 결정하고 원격수업으로 전환한다.", {"satisfaction": 4, "academic": -5, "budget": -3},
             "안전은 확보했지만 학습 결손 우려가 나왔습니다."),
            ("등하교 시간만 조정해 정상 등교를 유지한다.", {"reputation": -6, "satisfaction": -3},
             "큰 사고는 없었지만 무리한 결정이었다는 비판이 나왔습니다."),
         ]},
        {"title": "[자연재해] 기록적 폭설", "desc": "밤사이 폭설로 등굣길이 위험합니다. 빙판길 낙상 사고 우려가 큽니다.",
         "choices": [
            ("등교 시간을 2시간 늦추고 제설 작업을 총동원한다.", {"budget": -6, "satisfaction": 5, "reputation": 3},
             "안전하고 합리적인 대응이라는 평가를 받았습니다."),
            ("정상 등교를 유지하되 개별 지각은 눈감아준다.", {"satisfaction": -4, "reputation": -3},
             "실제로 몇 건의 낙상 사고가 발생해 비판을 받았습니다."),
         ]},
        {"title": "[자연재해] 미세먼지 비상저감조치", "desc": "며칠째 미세먼지 '매우 나쁨' 단계가 이어지고 있습니다. 체육 수업과 야외활동 진행 여부를 정해야 합니다.",
         "choices": [
            ("모든 실외활동을 전면 중단하고 공기청정기를 추가 설치한다.", {"budget": -7, "satisfaction": 3, "morale": 2},
             "세심한 대응에 학부모들의 신뢰가 높아졌습니다."),
            ("마스크 착용만 권고하고 기존 일정을 유지한다.", {"satisfaction": -3, "reputation": -2},
             "일부 학부모의 항의가 이어졌습니다."),
         ]},
        {"title": "[자연재해] 지진 발생", "desc": "인근 지역에서 지진이 발생해 학교 건물 안전 점검 요구가 빗발치고 있습니다.",
         "choices": [
            ("즉시 전문 업체를 불러 전면 정밀 점검을 실시한다.", {"budget": -10, "reputation": 6, "satisfaction": 4},
             "철저한 대응에 학교에 대한 신뢰가 크게 올랐습니다."),
            ("육안 점검 후 이상 없다고 판단해 수업을 재개한다.", {"reputation": -7, "satisfaction": -4},
             "안일한 대응이라는 비판 여론이 형성되었습니다."),
         ]},
    ],
    "incident": [
        {"title": "[사건사고] 학교폭력 신고 접수", "desc": "한 학급에서 지속적인 괴롭힘 정황이 담긴 신고서가 접수되었습니다. 가해 학생 학부모는 강하게 항의하고 있습니다.",
         "choices": [
            ("학교폭력대책심의위원회를 즉시 소집해 원칙대로 처리한다.", {"reputation": 7, "morale": 3, "satisfaction": 4, "budget": -3},
             "절차대로 처리되어 신뢰를 얻었지만, 가해 학생 학부모와의 갈등이 남았습니다."),
            ("양측을 불러 조용히 중재를 시도한다.", {"reputation": -5, "satisfaction": -4},
             "일부는 '축소하려는 것 아니냐'는 의혹을 제기했습니다."),
         ]},
        {"title": "[사건사고] 화재경보 오작동", "desc": "수업 중 화재경보가 오작동하며 전교생이 긴급 대피하는 소동이 벌어졌습니다.",
         "choices": [
            ("전면 시설 점검과 함께 대피 매뉴얼을 재정비한다.", {"budget": -6, "reputation": 4, "morale": 2},
             "혼란은 있었지만 사후 대응이 좋은 평가를 받았습니다."),
            ("단순 해프닝으로 정리하고 넘어간다.", {"reputation": -4, "satisfaction": -2},
             "안전불감증이라는 지적이 나왔습니다."),
         ]},
        {"title": "[사건사고] 급식 식중독 의심 사례", "desc": "일부 학생들이 급식 후 복통을 호소해 식중독 의심 신고가 들어왔습니다.",
         "choices": [
            ("즉시 급식을 중단하고 보건당국에 역학조사를 의뢰한다.", {"budget": -5, "reputation": 5, "satisfaction": 3},
             "신속하고 투명한 대응이라는 평가를 받았습니다."),
            ("일단 상황을 지켜보며 급식을 계속 운영한다.", {"reputation": -9, "satisfaction": -6},
             "늑장 대응이라는 강한 비판을 받았습니다."),
         ]},
        {"title": "[사건사고] SNS 학교 비방 논란", "desc": "익명 커뮤니티에 학교와 특정 교사를 저격하는 글이 퍼지며 학부모들 사이에 논란이 커지고 있습니다.",
         "choices": [
            ("사실관계를 공개적으로 확인하고 정식으로 해명한다.", {"reputation": 5, "morale": -2},
             "정면 대응이 신뢰 회복에 도움이 되었습니다."),
            ("시간이 지나면 잦아들 것이라 보고 대응하지 않는다.", {"reputation": -8},
             "논란이 더 확산되며 학교 이미지에 타격을 입었습니다."),
         ]},
        {"title": "[사건사고] 시험지 유출 의혹", "desc": "중간고사 직후 특정 학급에서 시험지가 사전 유출됐다는 의혹이 제기되었습니다.",
         "choices": [
            ("전면 재시험을 결정하고 진상조사를 실시한다.", {"reputation": 6, "academic": -3, "budget": -2},
             "공정성을 지켰다는 평가를 받았지만 혼란이 있었습니다."),
            ("증거 불충분을 이유로 조사 없이 넘어간다.", {"reputation": -10, "satisfaction": -3},
             "은폐 의혹이 커지며 학교에 대한 불신이 깊어졌습니다."),
         ]},
    ],
    "complaint": [
        {"title": "[민원] 급식 질 저하 항의", "desc": "급식 단가 인상 없이 식자재비가 올라 급식 질이 떨어졌다는 민원이 접수됩니다.",
         "choices": [
            ("예산을 추가 투입해 식단의 질을 회복한다.", {"budget": -8, "satisfaction": 6},
             "학생들의 불만이 빠르게 가라앉았습니다."),
            ("식단 구성만 조정하고 예산은 유지한다.", {"satisfaction": -3},
             "임시방편이라는 평가가 나왔습니다."),
         ]},
        {"title": "[민원] 과도한 야간자율학습 강요 민원", "desc": "한 학부모가 '과도한 야간자율학습 강요'를 주장하며 교육청에 민원을 넣었고, 지역 신문사에서 취재 요청이 들어왔습니다.",
         "choices": [
            ("투명하게 모든 자료를 공개하고 인터뷰에 적극 응한다.", {"reputation": 7, "budget": -2},
             "정직한 태도가 좋은 평가를 받았습니다."),
            ("취재 요청을 거절하고 내부적으로만 조용히 해결한다.", {"reputation": -7},
             "오히려 '뭔가 있다'는 억측이 확산되었습니다."),
         ]},
        {"title": "[민원] 교사 갑질 의혹 제기", "desc": "한 학부모가 담임 교사의 언행이 부적절했다며 공식 민원을 제기했습니다. 해당 교사는 억울함을 호소합니다.",
         "choices": [
            ("객관적 조사위원회를 꾸려 공정하게 조사한다.", {"reputation": 5, "morale": 1},
             "절차적 공정성을 지켰다는 평가를 받았습니다."),
            ("학부모를 달래 민원을 취하하도록 설득한다.", {"reputation": -6, "morale": -3},
             "무마 시도라는 비판과 함께 교사의 신뢰도 흔들렸습니다."),
         ]},
        {"title": "[민원] 두발·복장 규정 완화 요구", "desc": "학생회가 두발과 복장 자율화를 요구하는 서명을 모아 제출했습니다. 일부 학부모와 교사는 우려를 표합니다.",
         "choices": [
            ("학생회 요구를 대폭 수용해 규정을 대폭 완화한다.", {"satisfaction": 9, "morale": -3},
             "학생들은 크게 환영했지만 일부 교사는 지도가 어려워졌다고 토로합니다."),
            ("공청회를 거쳐 단계적으로 일부만 완화한다.", {"satisfaction": 4, "reputation": 2},
             "절충안에 대체로 만족하는 분위기입니다."),
         ]},
    ],
    "goodwill": [
        {"title": "[호재] 전국 대회 수상 소식", "desc": "한 학생이 전국 토론대회에서 대상을 수상해 학교에 좋은 소식이 전해졌습니다.",
         "choices": [
            ("전교생 앞에서 성대하게 축하 행사를 연다.", {"reputation": 5, "satisfaction": 5, "budget": -3},
             "학교 전체에 활기가 돌았습니다."),
            ("조용히 상장을 전달하며 격려한다.", {"satisfaction": 2},
             "소박하지만 따뜻한 축하가 되었습니다."),
         ]},
        {"title": "[호재] 동문회의 장학금 기부 제안", "desc": "서석고 동문회에서 우수 학생을 위한 장학금을 기부하겠다고 제안합니다.",
         "choices": [
            ("감사히 받아 장학 제도를 신설한다.", {"budget": 10, "reputation": 5, "satisfaction": 3},
             "학교 재정에 큰 보탬이 되었고 평판도 올랐습니다."),
            ("동문회의 영향력 확대를 우려해 정중히 사양한다.", {"reputation": -2},
             "신중한 선택이었지만 아쉬워하는 목소리도 있었습니다."),
         ]},
        {"title": "[호재] 지역 대학·기업의 진로 프로그램 협약 제안", "desc": "지역 대학과 기업에서 서석고 학생들을 위한 진로 프로그램 협약을 제안해왔습니다.",
         "choices": [
            ("적극적으로 협약을 체결하고 프로그램을 확대한다.", {"reputation": 6, "satisfaction": 6, "budget": -4},
             "학생들의 진로 선택 폭이 넓어졌다는 호평을 받았습니다."),
            ("현재도 충분하다며 제안을 정중히 거절한다.", {"reputation": -3},
             "일부 학부모들은 아쉬움을 표했습니다."),
         ]},
        {"title": "[호재] 우수 교사 시도교육감 표창", "desc": "한 교사가 시도교육감 표창 대상자로 선정되었다는 소식이 전해졌습니다.",
         "choices": [
            ("전교 조회에서 공식적으로 축하하고 홍보한다.", {"morale": 6, "reputation": 3},
             "교사들의 자부심이 크게 올랐습니다."),
            ("개인 성과이니 담담하게 넘어간다.", {"morale": 1},
             "축하 분위기가 다소 미미했습니다."),
         ]},
    ],
}

SIDE_EVENT_WEIGHTS = {
    "natural_disaster": 0.15,
    "incident": 0.35,
    "complaint": 0.25,
    "goodwill": 0.25,
}

SIDE_EVENT_TRIGGER_CHANCE = 0.45  # 필수 이벤트 사이에 확률적 이벤트가 끼어들 확률


def pick_random_side_event(used_titles):
    categories = list(SIDE_EVENT_WEIGHTS.keys())
    weights = list(SIDE_EVENT_WEIGHTS.values())
    for _ in range(10):
        cat = random.choices(categories, weights=weights, k=1)[0]
        pool = [e for e in SIDE_EVENTS[cat] if e["title"] not in used_titles]
        if pool:
            return random.choice(pool)
    all_events = [e for cat in SIDE_EVENTS.values() for e in cat]
    return random.choice(all_events)


# ----------------------------
# 자유 입력 판정 로직
# ----------------------------

POSITIVE_KEYWORDS = {
    "academic": ["성적", "입시", "학업", "보충", "모의고사", "공부", "학습", "진학", "특강"],
    "satisfaction": ["학생", "행복", "자율", "축제", "동아리", "휴식", "존중", "쉬는", "체험"],
    "morale": ["교사", "선생님", "협의", "소통", "처우", "연구년", "격려", "회식", "휴가"],
    "reputation": ["언론", "홍보", "평판", "지역사회", "신뢰", "공개", "협약", "인터뷰", "명성"],
    "budget": ["예산", "지원금", "투자", "기부", "장학금", "절약", "협찬"],
}
NEGATIVE_MARKERS = ["금지", "축소", "해고", "방치", "무시", "묵인", "은폐", "강요", "압박", "삭감",
                     "거부", "방관", "폐지", "체벌", "처벌", "숨기"]
COST_MARKERS = ["투입", "확대", "신설", "도입", "전면", "즉시", "대대적", "총동원"]


def evaluate_custom_heuristic(text: str):
    t = text.strip()
    if not t:
        return {}, "결정을 내리지 못하고 상황을 그대로 지켜보기로 했습니다."

    negative = any(k in t for k in NEGATIVE_MARKERS)
    touched = [stat for stat, kws in POSITIVE_KEYWORDS.items() if any(kw in t for kw in kws)]

    effects = {}
    if not touched:
        for stat in ["budget", "reputation", "satisfaction", "morale", "academic"]:
            effects[stat] = random.choice([-4, -2, 0, 2, 4])
        flavor = ("교장선생님의 다소 이례적인 결정에, 학교 곳곳에서는 이렇다 할 방향성을 "
                   "읽어내기 어려웠지만, 크고 작은 영향이 골고루 나타났습니다.")
        return effects, flavor

    base = -8 if negative else 9
    for stat in touched:
        effects[stat] = base + random.randint(-2, 2)

    if any(k in t for k in COST_MARKERS) and "budget" not in effects:
        effects["budget"] = effects.get("budget", 0) - random.randint(4, 10)

    if negative:
        flavor = "다소 강경하거나 소극적인 결정으로 받아들여지며, 관련된 영역에서 반발과 우려가 크게 나타났습니다."
    else:
        flavor = "교장선생님의 소신 있는 결정이 관련된 영역에 뚜렷한 영향을 남겼습니다."
    return effects, flavor


def _get_gemini_api_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _extract_json(raw: str):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    return json.loads(raw)


LAST_GEMINI_ERROR = None
# 주의: gemini-1.5-flash / gemini-2.0-flash 는 2026년 기준 서비스 종료된 모델입니다.
# 현재(2026-07) 사용 가능한 모델로 교체했습니다. 추후 모델이 또 바뀌면 이 리스트만 수정하면 됩니다.
GEMINI_MODEL_CANDIDATES = ["gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-flash-lite-latest"]

GAME_TONE = (
    "이 게임은 한국 고등학교를 배경으로 한 '약간 미쳐있는' 블랙코미디 경영 시뮬레이션이다. "
    "모든 서술과 대사는 과장되고 예측불가능하며 극적이어야 한다. 등장인물들은 감정 기복이 크고, "
    "가끔 뜬금없이 폭주하거나 시적으로 오글거리거나 소름 끼치도록 진지해진다. 유치찬란한 드라마, "
    "K-드라마식 클리셰, 급발진 개그를 적극 활용하되, 실제 폭력 묘사나 선정적/혐오적 표현, 특정 "
    "실존 인물 비하는 하지 않는다. 어디까지나 과장된 코미디 톤을 유지한다."
)


def _get_gemini_client():
    global LAST_GEMINI_ERROR
    api_key = _get_gemini_api_key()
    if not api_key:
        LAST_GEMINI_ERROR = ("API 키를 찾지 못했습니다. 서버 환경변수(Secrets)에 GEMINI_API_KEY "
                              "(또는 GOOGLE_API_KEY)가 정확한 이름으로 등록되어 있는지, 배포 후 "
                              "재배포(Republish/Redeploy)가 이루어졌는지 확인해주세요.")
        return None
    try:
        from google import genai
    except ImportError:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "google-genai"])
            from google import genai
        except Exception as e:
            LAST_GEMINI_ERROR = f"google-genai 라이브러리 설치 실패: {type(e).__name__}: {e}"
            return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        LAST_GEMINI_ERROR = f"클라이언트 생성 실패: {type(e).__name__}: {e}"
        return None


def _generate_with_fallback(client, contents):
    last_exc = None
    for model_name in GEMINI_MODEL_CANDIDATES:
        try:
            return client.models.generate_content(model=model_name, contents=contents)
        except Exception as e:
            last_exc = e
            continue
    raise last_exc


def evaluate_custom_ai(text: str, event_title: str, event_desc: str, state: GameState):
    global LAST_GEMINI_ERROR
    client = _get_gemini_client()
    if client is None:
        return None

    try:
        prompt = f"""{GAME_TONE}

당신은 이 게임의 심판 역할을 맡았습니다.
현재 상황: {event_title}
상황 설명: {event_desc}

교장선생님(플레이어)이 다음과 같은 자유 서술 결정을 내렸습니다:
"{text}"

이 결정이 학교의 5개 지표(budget=예산, reputation=평판, satisfaction=학생만족도, morale=교사사기, academic=학업성취도)에
미칠 영향을 -18 ~ +18 사이의 정수로 각각 추정하고(과감하고 확실한 결정일수록 절댓값을 크게 주세요),
2~3문장의 한국어 결과 서술을 과장되고 드라마틱한 톤으로 작성하세요.
반드시 아래 JSON 형식으로만 답하세요. 다른 텍스트나 코드블록 표시는 포함하지 마세요.

{{"budget": 0, "reputation": 0, "satisfaction": 0, "morale": 0, "academic": 0, "narrative": "..."}}
"""
        resp = _generate_with_fallback(client, prompt)
        raw = resp.text
        data = _extract_json(raw)
        effects = {k: int(data.get(k, 0)) for k in ["budget", "reputation", "satisfaction", "morale", "academic"]}
        narrative = data.get("narrative", "결정이 학교에 영향을 미쳤습니다.")
        LAST_GEMINI_ERROR = None
        return effects, narrative
    except Exception as e:
        LAST_GEMINI_ERROR = f"API 호출 중 오류: {type(e).__name__}: {e}"
        return None


def evaluate_custom_action(text, event_title, event_desc, state):
    ai_result = evaluate_custom_ai(text, event_title, event_desc, state)
    if ai_result is not None:
        return ai_result[0], ai_result[1], "Gemini 판정"
    effects, flavor = evaluate_custom_heuristic(text)
    source = "간이 판정(키워드 기반)"
    if LAST_GEMINI_ERROR:
        source += f" — Gemini 미사용 사유: {LAST_GEMINI_ERROR}"
    return effects, flavor, source


def test_gemini_connection():
    client = _get_gemini_client()
    if client is None:
        return False, LAST_GEMINI_ERROR
    try:
        resp = _generate_with_fallback(client, "연결 테스트입니다. '성공'이라는 단어 하나만 답해주세요.")
        return True, f"연결 성공! Gemini 응답: {resp.text.strip()[:100]}"
    except Exception as e:
        return False, f"API 호출 실패: {type(e).__name__}: {e}"


def ai_generate_reaction(char: dict, state: GameState, top_stat: str, delta: int, event_title: str, choice_text: str):
    global LAST_GEMINI_ERROR
    client = _get_gemini_client()
    if client is None:
        return None
    try:
        direction = "크게 올랐다" if delta > 0 else "크게 떨어졌다"
        prompt = f"""{GAME_TONE}

캐릭터 정보:
- 이름/직책: {char['name']} ({char['role']})
- 성격: {char['persona']}

방금 벌어진 일: "{event_title}" 상황에서 교장선생님이 "{choice_text}"라는 결정을 내렸고,
그 결과 {STAT_LABELS.get(top_stat, top_stat)} 지표가 {direction} (현재 {getattr(state, top_stat)}/100).

이 캐릭터의 말투와 성격을 살려서, 1~2문장의 대사(따옴표 포함)로 반응하세요. 과장되고 살짝 미친 듯한 톤으로,
이모지를 1개 정도 써도 좋습니다. 반드시 아래 JSON 형식으로만 답하세요.

{{"line": "..."}}
"""
        resp = _generate_with_fallback(client, prompt)
        data = _extract_json(resp.text)
        line = data.get("line", "").strip()
        if not line:
            return None
        LAST_GEMINI_ERROR = None
        return line
    except Exception as e:
        LAST_GEMINI_ERROR = f"반응 생성 실패: {type(e).__name__}: {e}"
        return None


def ai_generate_side_event(state: GameState, used_titles: set):
    global LAST_GEMINI_ERROR
    client = _get_gemini_client()
    if client is None:
        return None
    try:
        category = random.choices(
            list(SIDE_EVENT_WEIGHTS.keys()), weights=list(SIDE_EVENT_WEIGHTS.values()), k=1
        )[0]
        category_kr = {"natural_disaster": "자연재해", "incident": "사건사고",
                        "complaint": "민원", "goodwill": "호재(좋은 소식)"}[category]
        prompt = f"""{GAME_TONE}

지금까지 나온 이벤트 제목들(중복 금지): {list(used_titles) if used_titles else '없음'}

현재 학교 상태: 예산 {state.budget}, 평판 {state.reputation}, 학생만족도 {state.satisfaction}, 교사사기 {state.morale}, 학업성취도 {state.academic} (모두 0~100)

카테고리 "{category_kr}"에 해당하는, 서석고등학교에서 벌어질 법한 기상천외하고 웃기면서도 그럴듯한
새로운 돌발 이벤트를 하나 만들어주세요. 제목은 "[{category_kr}] 제목" 형식으로, 상황 설명은 2~3문장,
선택지는 정확히 2개, 각 선택지마다 5개 지표(budget, reputation, satisfaction, morale, academic)에 대한
-15~+15 사이의 영향과 1~2문장의 결과 서술을 포함하세요. 과장되고 재미있는 톤을 유지하되 도가 지나친
잔인함/선정성은 피하세요. 반드시 아래 JSON 형식으로만 답하세요.

{{"title": "[{category_kr}] ...", "desc": "...",
"choice1_text": "...", "choice1_effects": {{"budget":0,"reputation":0,"satisfaction":0,"morale":0,"academic":0}}, "choice1_result": "...",
"choice2_text": "...", "choice2_effects": {{"budget":0,"reputation":0,"satisfaction":0,"morale":0,"academic":0}}, "choice2_result": "..."}}
"""
        resp = _generate_with_fallback(client, prompt)
        data = _extract_json(resp.text)
        stat_keys = ["budget", "reputation", "satisfaction", "morale", "academic"]

        def _clean_effects(raw_effects):
            return {k: int(raw_effects.get(k, 0)) for k in stat_keys}

        title = data["title"].strip()
        desc = data["desc"].strip()
        c1_text = data["choice1_text"].strip()
        c2_text = data["choice2_text"].strip()
        c1_effects = _clean_effects(data.get("choice1_effects", {}))
        c2_effects = _clean_effects(data.get("choice2_effects", {}))
        c1_result = data["choice1_result"].strip()
        c2_result = data["choice2_result"].strip()

        if not title or not desc or not c1_text or not c2_text:
            raise ValueError("빈 필드가 있습니다")

        event = {
            "title": title,
            "desc": desc,
            "choices": [
                (c1_text, c1_effects, c1_result),
                (c2_text, c2_effects, c2_result),
            ],
        }
        LAST_GEMINI_ERROR = None
        return event
    except Exception as e:
        LAST_GEMINI_ERROR = f"돌발 이벤트 생성 실패: {type(e).__name__}: {e}"
        return None


def ai_generate_ending(state: GameState, principal_name: str, game_log: list):
    global LAST_GEMINI_ERROR
    client = _get_gemini_client()
    if client is None:
        return None
    try:
        recent_log = game_log[-8:] if len(game_log) > 8 else game_log
        log_text = "\n".join(f"- {line}" for line in recent_log) if recent_log else "(특기할 기록 없음)"
        prompt = f"""{GAME_TONE}

{principal_name} 교장선생님의 1년 임기가 끝났습니다.

최종 지표: 예산 {state.budget}, 평판 {state.reputation}, 학생만족도 {state.satisfaction}, 교사사기 {state.morale}, 학업성취도 {state.academic} (모두 0~100, 평균 {(state.budget+state.reputation+state.satisfaction+state.morale+state.academic)/5:.1f})

임기 중 주요 결정 기록(최근 순):
{log_text}

이 모든 것을 종합해서, 과장되고 극적이며 살짝 미친 듯한 톤으로 엔딩 타이틀(10자 내외)과
엔딩 서술(3~5문장)을 작성하세요. 최종 지표 평균이 높을수록 영광스럽고 우스꽝스러울 정도로 거창하게,
낮을수록 몰락하는 느낌을 코믹하게 과장해서 표현하세요. 반드시 아래 JSON 형식으로만 답하세요.

{{"title": "...", "desc": "..."}}
"""
        resp = _generate_with_fallback(client, prompt)
        data = _extract_json(resp.text)
        title = data.get("title", "").strip()
        desc = data.get("desc", "").strip()
        if not title or not desc:
            raise ValueError("빈 필드가 있습니다")
        LAST_GEMINI_ERROR = None
        return title, desc
    except Exception as e:
        LAST_GEMINI_ERROR = f"엔딩 생성 실패: {type(e).__name__}: {e}"
        return None


# ----------------------------
# 엔딩 계산
# ----------------------------

def compute_ending(state: GameState):
    total = state.budget + state.reputation + state.satisfaction + state.morale + state.academic
    avg = total / 5

    if avg >= 75:
        title, desc = ("명문 서석고의 전설",
            "당신의 1년은 서석고등학교 역사에 뚜렷한 한 획을 그었습니다. 학생들은 행복했고, "
            "교사들은 자부심을 느꼈으며, 지역사회는 서석고를 다시 보게 되었습니다.")
    elif avg >= 60:
        title, desc = ("안정적인 명가로의 도약",
            "완벽하지는 않았지만, 서석고는 분명히 나아졌습니다. 후임자는 좋은 기반 위에서 학교를 이어받게 되었습니다.")
    elif avg >= 45:
        title, desc = ("무난했던 1년",
            "특별히 나쁘지도, 특별히 뛰어나지도 않은 1년이었습니다. 큰 사고 없이 유지되었지만 뚜렷한 변화도 없었습니다.")
    elif avg >= 30:
        title, desc = ("흔들리는 서석고",
            "여러 위기를 가까스로 넘겼지만, 학교 곳곳에 피로가 쌓였습니다.")
    else:
        title, desc = ("위태로운 유산",
            "당신의 임기는 여러 논란과 갈등 속에 저물었습니다. 서석고는 신뢰 회복이라는 무거운 과제를 안게 되었습니다.")

    stats = {"예산": state.budget, "평판": state.reputation, "학생만족도": state.satisfaction,
             "교사사기": state.morale, "학업성취도": state.academic}
    best = max(stats, key=stats.get)
    worst = min(stats, key=stats.get)
    return title, desc, best, worst, avg


# ----------------------------
