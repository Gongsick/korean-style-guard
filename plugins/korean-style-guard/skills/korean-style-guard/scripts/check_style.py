#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한국어 문체 점검 (korean-style-guard v1.0)
SKILL.md §5의 1~2단계를 자동화한다. 표준 라이브러리만 쓴다.

사용법:
    python3 check_style.py 원고.md
    python3 check_style.py < 원고.txt

산문을 대상으로 한다. 표·코드블록·목록·제목은 측정에서 제외한다.
▲ 표시는 검토 신호이지 오류 판정이 아니다 — SKILL.md §6 과교정 금지를 함께 볼 것.
"""

import re
import sys
import statistics
from collections import Counter

# ── 1단계: 어휘 검색 ────────────────────────────────────────────────
LEXICON = {
    "L1 공간·기하 은유": r"궤를 (같이|달리)|결을 (맞추|같이)|결이 (통하|다르)|축을 (세우|형성)|기준을 가르|방점을 (찍|두)|무게추|외연을 확장|지평을 넓|층위를 나누|접점을 찾|스펙트럼이 넓|판을 새로 짜",
    "L1 영어 직역": r"간극을 (좁히|메우)|파고들|양날의 검|태피스트리|시간의 시험|게임 체인저|빙산의 일각|중추적 역할|청사진을 제시|촉매제로|균형점을 찾|새로운 장을 열",
    "L1 결말 상투구": r"시사하는 바가|시사점을 던져|단초를 제공|마중물이 되|다각도로 조명|톡톡히 해내|귀추가 주목|지속적인 관심이 요구|곱씹어 볼 만|방향성을 제시",
    "L1 수식어 인플레": r"다양한|혁신적|획기적|놀라운|압도적|유의미한|효과적으로|성공적으로|궁극적으로|근본적으로|유기적으로|전략적으로|무궁무진",
    "L2 이중 피동": r"되어지|되어졌|보여지|보여졌|불려지|쓰여지|잊혀지|모아지|나뉘어지",
    "L2 조사 번역투": r"에 있어서|에 다름 아니|와 관련하여|을 바탕으로|에 기인하|에 의해 (결정|수행|진행)",
    "L2 형식명사": r"것으로 사료|것으로 판단|할 필요가 있|라는 점에서|라는 측면에서",
    "L4 구성 상투": r"살펴보(겠|도록)|결론적으로|정리하면|밝은 미래|앞으로의 행보",
}

# 빈도로 판단하는 항목 (1~2회는 정상)
FREQ_ONLY = {"L1 수식어 인플레", "L2 조사 번역투"}
FREQ_LIMIT = 3

# ── 2단계: 리듬 측정 ────────────────────────────────────────────────
CONJ_HEAD = ["또한", "따라서", "하지만", "그러나", "그리고", "이와 더불어",
             "나아가", "결국", "즉", "한편", "더불어", "그럼에도"]

ENDING_PATTERNS = [
    (r"니다[.!?]?$", "합쇼체"),
    (r"(해요|예요|이에요|에요|죠|아요|어요|세요)[.!?]?$", "해요체"),
    (r"(음|함|됨|임|짐|옴|봄)[.!?]?$", "음슴체"),
    (r"다[.!?]?$", "평서체"),
    (r"(해|야|어|아|지|네|더라|거든|잖아|는데)[.!?]?$", "반말"),
]


def strip_markup(text: str):
    """표·코드블록·제목·목록을 제거하고 산문 줄만 돌려준다."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    lines = []
    for ln in text.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if s.startswith(("|", "#", ">")):
            continue
        if re.match(r"^[-*+]\s|^\d+\.\s", s):
            continue
        if re.match(r"^[-=]{3,}$", s):
            continue
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
        s = re.sub(r"`(.+?)`", r"\1", s)
        lines.append(s)
    return lines


def split_sentences(lines):
    """줄바꿈을 1차 경계로, 문장부호를 2차 경계로 삼는다."""
    out = []
    for ln in lines:
        for p in re.split(r"(?<=[.!?])\s+", ln):
            p = p.strip(" \t·-–—▪")
            if len(p.split()) >= 2:
                out.append(p)
    return out


def classify_ending(sent: str) -> str:
    s = sent.rstrip()
    for pat, name in ENDING_PATTERNS:
        if re.search(pat, s):
            return name
    return "기타"


def analyze(text: str):
    lines = strip_markup(text)
    sents = split_sentences(lines)
    if not sents:
        return None
    prose = " ".join(sents)

    lengths = [len(s.split()) for s in sents]
    mean = statistics.mean(lengths)
    sd = statistics.pstdev(lengths)
    cv = sd / mean if mean else 0.0

    # 문체 층(합쇼/해요/반말/음슴) — 혼용 탐지용
    strata = Counter(classify_ending(s) for s in sents)

    # 종결형 3음절 — 리듬 단조 탐지용. 한국어 평서문은 대개 '다'로 끝나므로
    # 층위가 아니라 실제 어형(했다/이다/더라/린다)의 다양성을 본다.
    forms = Counter(s.rstrip(".!?…\"')]").strip()[-3:] for s in sents)
    top_end, top_cnt = forms.most_common(1)[0]
    end_ratio = top_cnt / len(sents)

    conj = sum(1 for s in sents if any(s.startswith(c) for c in CONJ_HEAD))
    conj_ratio = conj / len(sents)

    commas = prose.count(",") / len(sents)

    return {
        "문장 수": len(sents),
        "평균 길이(어절)": round(mean, 1),
        "길이 변동계수": f"{cv:.2f}",
        "최빈 종결형": f"'{top_end}' {round(end_ratio * 100)}%",
        "_end_ratio": end_ratio,
        "_cv": cv,
        "문두 접속사 비율": f"{round(conj_ratio * 100)}%",
        "_conj": conj_ratio,
        "문장당 쉼표": round(commas, 2),
        "_comma": commas,
        "_strata": strata,
        "_forms": forms,
    }


def lexicon_hits(text: str):
    out = {}
    for name, pat in LEXICON.items():
        found = [m.group(0) for m in re.finditer(pat, text)]
        if found:
            out[name] = Counter(found)
    return out


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            text = f.read()
        src = sys.argv[1]
    else:
        text = sys.stdin.read()
        src = "(stdin)"

    print(f"\n■ 대상: {src}")

    print("\n[1단계] 어휘 검색")
    hits = lexicon_hits(text)
    if not hits:
        print("  걸린 항목 없음")
    for name, c in hits.items():
        total = sum(c.values())
        mark = "  " if (name in FREQ_ONLY and total < FREQ_LIMIT) else "▲ "
        items = ", ".join(f"{k}({v})" for k, v in c.most_common(8))
        print(f"  {mark}{name} · {total}건 → {items}")

    print("\n[2단계] 리듬 측정")
    r = analyze(text)
    if not r:
        print("  측정할 산문이 없음")
        return

    def flag(cond):
        return "▲" if cond else " "

    print(f"   문장 수            {r['문장 수']}")
    print(f"   평균 길이(어절)    {r['평균 길이(어절)']}")
    print(f" {flag(r['_cv'] < 0.40)} 길이 변동계수      {r['길이 변동계수']}   (경고: 0.40 미만)")
    print(f" {flag(r['_end_ratio'] > 0.60)} 최빈 종결형        {r['최빈 종결형']}  (경고: 60% 초과)")
    print(f" {flag(r['_conj'] > 0.20)} 문두 접속사 비율   {r['문두 접속사 비율']}   (경고: 20% 초과)")
    print(f" {flag(r['_comma'] > 1.0)} 문장당 쉼표        {r['문장당 쉼표']}   (경고: 1.0 초과)")

    print("\n   종결형 상위: " + ", ".join(f"'{k}' {v}" for k, v in r["_forms"].most_common(6)))
    print("   문체 층 분포: " + ", ".join(f"{k} {v}" for k, v in r["_strata"].most_common()))

    mixed = [k for k in ("합쇼체", "해요체", "반말", "음슴체") if r["_strata"].get(k, 0) > 0]
    if len(mixed) > 1:
        print(f" ▲ 문체 혼용 의심: {' + '.join(mixed)} — §6-6 예외 구간인지 확인")

    print("\n※ ▲ 표시는 검토 신호이지 오류 판정이 아니다. 과교정 금지 항목(SKILL.md §6)을 함께 볼 것.\n")


if __name__ == "__main__":
    main()
