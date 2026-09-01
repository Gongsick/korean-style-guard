#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한국어 문체 점검 (korean-style-guard v1.5)
SKILL.md §5의 1~3단계를 자동화한다. 표준 라이브러리만 쓴다.

규칙은 rules.json 한 곳에 있다. 항목을 늘리려면 이 파일이 아니라 rules.json을 고친다.

사용법:
    python3 check_style.py 원고.md
    python3 check_style.py --style 해요체 원고.md
    python3 check_style.py --style 음슴체-캐주얼 < 원고.txt
    python3 check_style.py --list-styles

--style 을 주면 6축 정합 검사(3단계)가 추가된다. 안 주면 문체를 자동 추정해
리듬만 본다.

▲ 표시는 검토 신호이지 오류 판정이 아니다 — rules.json의 overcorrection_guards를
함께 볼 것. 임계값은 사람 글 21편(27,464자)과 AI 20편을 대조해 정했다.
"""

import json
import os
import re
import statistics
import sys
from collections import Counter

CONJ_HEAD = ["또한", "따라서", "하지만", "그러나", "그리고", "이와 더불어",
             "나아가", "결국", "즉", "한편", "더불어", "그럼에도"]

ENDING_PATTERNS = [
    (r"니다[.!?]?$", "합쇼체"),
    (r"(해요|예요|이에요|에요|죠|아요|어요|세요)[.!?]?$", "해요체"),
    (r"(음|함|됨|임|짐|옴|봄)[.!?]?$", "음슴체"),
    (r"다[.!?]?$", "평서체"),
    (r"(해|야|어|아|지|네|더라|거든|잖아|는데)[.!?]?$", "반말"),
]

# 문체별로 '함께 써도 되는' 종결 층. 한국어는 한 문체 안에서도 평서체(~다)를
# 자유롭게 섞는다. 진짜 붕괴는 비호환 층이 섞일 때다(해요체에 합쇼체 등).
STYLE_COMPAT = {
    "음슴체-캐주얼": {"음슴체", "평서체", "반말"},
    "음슴체-공문":   {"음슴체", "평서체"},
    "반말-구어":     {"반말", "평서체", "음슴체"},
    "해요체":       {"해요체"},
    "격식-합쇼체":   {"합쇼체", "평서체"},
}
ALIASES = {
    "음슴체": "음슴체-캐주얼", "캐주얼음슴체": "음슴체-캐주얼",
    "공문": "음슴체-공문", "개조식": "음슴체-공문", "공문음슴체": "음슴체-공문",
    "반말": "반말-구어", "구어": "반말-구어", "구어체": "반말-구어",
    "격식": "격식-합쇼체", "합쇼체": "격식-합쇼체", "격식체": "격식-합쇼체",
}


def load_rules(explicit=None):
    here = os.path.dirname(os.path.abspath(__file__))
    cands = ([explicit] if explicit else []) + [
        os.path.join(here, "rules.json"),
        os.path.join(here, "..", "rules.json"),
        os.path.join(here, "..", "references", "rules.json"),
    ]
    for p in cands:
        if p and os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f), p
    return None, None


def strip_markup(text):
    """표·코드블록·제목·목록을 제거하고 산문 줄만 돌려준다."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    lines = []
    for ln in text.split("\n"):
        s = ln.strip()
        if not s:
            lines.append("")
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
    out = []
    for ln in lines:
        if not ln:
            continue
        for p in re.split(r"(?<=[.!?])\s+", ln):
            p = p.strip(" \t·-–—▪")
            if len(p.split()) >= 2:
                out.append(p)
    return out


def split_pieces(lines):
    pieces, cur = [], []
    for ln in lines:
        if ln:
            cur.append(ln)
        elif cur:
            pieces.append(cur); cur = []
    if cur:
        pieces.append(cur)
    return [split_sentences(p) for p in pieces if split_sentences(p)]


def classify_ending(sent):
    for pat, name in ENDING_PATTERNS:
        if re.search(pat, sent.rstrip()):
            return name
    return "기타"


def informality_density(text, rules):
    im = rules.get("informality_markers")
    if not im:
        return None
    n = sum(len(re.findall(p, text)) for p in im["patterns"].values())
    return n / max(len(text), 1) * 1000


# ── 측정 ──────────────────────────────────────────────────────────
def analyze(text, rules):
    lines = strip_markup(text)
    sents = split_sentences(lines)
    if not sents:
        return None
    prose = " ".join(sents)

    lengths = [len(s.split()) for s in sents]
    mean = statistics.mean(lengths)
    cv = statistics.pstdev(lengths) / mean if mean else 0.0

    strata = Counter(classify_ending(s) for s in sents)
    forms = Counter(s.rstrip(".!?…\"')]").strip()[-3:] for s in sents)
    top_form, top_cnt = forms.most_common(1)[0]
    conj = sum(1 for s in sents if any(s.startswith(c) for c in CONJ_HEAD))

    imd = informality_density(text, rules)
    casual = sum(strata.get(k, 0) for k in ("해요체", "반말", "음슴체")) / len(sents)
    im_shown = imd if casual >= 0.4 else None

    # 닫는 마무리 — 격식체·공문은 장르 규범이라 건너뛴다
    formal = (strata.get("합쇼체", 0) / len(sents) >= 0.5
              or (strata.get("음슴체", 0) / len(sents) >= 0.5 and (imd or 0) < 1.0))
    closing = None
    pieces = split_pieces(lines)
    if len(pieces) >= 3 and not formal:
        cf = rules.get("closing_forms", {}).get("patterns", {})
        hits, detail = 0, []
        for pc in pieces:
            tail = pc[-1].rstrip(".!?~… ")[-18:]
            for kind, pats in cf.items():
                if any(re.search(p, tail) for p in pats):
                    hits += 1; detail.append((kind, pc[-1])); break
        closing = {"total": len(pieces), "hits": hits,
                   "ratio": hits / len(pieces), "detail": detail}

    return {"n": len(sents), "mean": mean, "cv": cv,
            "top_form": top_form, "form_ratio": top_cnt / len(sents),
            "conj": conj / len(sents), "comma": prose.count(",") / len(sents),
            "strata": strata, "forms": forms, "closing": closing,
            "informality": im_shown, "imd_raw": imd, "sents": sents}


def lexicon_hits(text, rules):
    out = []
    for grp in rules.get("lexical", []):
        c = Counter()
        for pat in grp["patterns"]:
            for m in re.finditer(pat, text):
                c[m.group(0)] += 1
        if c:
            out.append((grp, c))
    return out


# ── 3단계: 문체 정합 ───────────────────────────────────────────────
def style_check(text, r, style, rules):
    spec = rules["styles"][style]
    axes = spec["axes"]
    sents = r["sents"]
    out = []

    # ① 종결어미 정합
    ok_strata = STYLE_COMPAT[style] | {"기타"}
    wrong = [s for s in sents if classify_ending(s) not in ok_strata]
    ratio = 1 - len(wrong) / len(sents)
    out.append(("종결어미", ratio >= rules["styles"][style].get("ending_min", 0.85),
                f"{ratio*100:.0f}% 일치 (기대 {axes['ending']})",
                [f"[{classify_ending(s)}] {s[:54]}" for s in wrong[:4]]))

    # ② 금지 표현
    bad = []
    for rule in spec.get("forbid", []):
        for s in sents:
            hay = s.split(" ")[0] if rule.get("anchor") == "sentence_start" else s
            m = re.search(rule["pattern"], hay)
            if m:
                bad.append(f"'{m.group(0)}' — {rule['why']}\n           └ {s[:54]}")
    out.append(("금지 표현", not bad, f"{len(bad)}건", bad[:5]))

    # ③ 문장 길이
    lo, hi = axes["sent_len"]
    over = [s for s in sents if len(s.split()) > hi]
    ratio_over = len(over) / len(sents)
    out.append(("문장 길이", ratio_over <= 0.30,
                f"{lo}~{hi}어절 기대, 초과 {len(over)}문장 ({ratio_over*100:.0f}%)",
                [f"{len(s.split())}어절 · {s[:50]}"
                 for s in sorted(over, key=lambda x: -len(x.split()))[:3]]))

    # ④ 관형절 중첩
    nest_max = axes["clause_nest"]
    nested = []
    for s in sents:
        n = len(re.findall(r"[가-힣](는|던|을)\s[가-힣]{2,}(이|가|을|를|은|는)\s", s))
        if n > nest_max:
            nested.append(f"중첩 {n} · {s[:50]}")
    out.append(("관형절 중첩", True,
                f"허용 {nest_max}중, 초과 {len(nested)}문장 — 참고용(사람 글이 오히려 더 많음)",
                nested[:2]))

    # ⑤ 구어 표지
    im = rules.get("informality_markers", {})
    if style in im.get("applies_to", []):
        d = r["imd_raw"] or 0
        lim = im["warn_below_total"]
        out.append(("구어 표지", d >= lim, f"{d:.2f}/1천자 (기대 {lim} 이상)",
                    [im["warn_note"]] if d < lim else []))

    # ⑥ 조건부 어미 (반말 전용) — 위반이 아니라 확인 항목
    ce = spec.get("conditional_endings")
    if ce:
        used = [f"'{k}' — {v}" for k, v in ce.items()
                if re.search(k + r"[.!?]?(\s|$)", text)]
        out.append(("조건부 어미", True, f"{len(used)}종 사용 — 사용 조건 확인", used))

    return out


# ── 출력 ──────────────────────────────────────────────────────────
def main():
    argv = sys.argv[1:]
    rules_path = style = None
    if "--rules" in argv:
        i = argv.index("--rules"); rules_path = argv[i + 1]; del argv[i:i + 2]
    if "--style" in argv:
        i = argv.index("--style"); style = argv[i + 1]; del argv[i:i + 2]

    rules, used = load_rules(rules_path)
    if rules is None:
        print("오류: rules.json을 찾을 수 없음. --rules 로 경로를 지정하세요.", file=sys.stderr)
        sys.exit(1)

    if "--list-styles" in argv:
        print("\n지정 가능한 문체:")
        for k, v in rules["styles"].items():
            if k.startswith("_"):      # _calibration 등 메타 항목
                continue
            a = v["axes"]
            print(f"  {k:<14} {a['ending']:<16} {a['sent_len'][0]}~{a['sent_len'][1]}어절, "
                  f"담화표지 {a['discourse_marker']}")
        print("\n별칭: " + ", ".join(f"{k}→{v}" for k, v in ALIASES.items()) + "\n")
        return

    if style:
        style = ALIASES.get(style, style)
        if style not in rules["styles"] or style.startswith("_"):
            print(f"오류: 모르는 문체 '{style}'. --list-styles 로 목록을 보세요.", file=sys.stderr)
            sys.exit(1)

    if argv:
        text = open(argv[0], encoding="utf-8").read(); src = argv[0]
    else:
        text = sys.stdin.read(); src = "(stdin)"

    print(f"\n■ 대상: {src}")
    print(f"■ 규칙: {os.path.basename(used)} v{rules['meta']['version']}"
          + (f"   ■ 지정 문체: {style}" if style else "   ■ 문체 미지정 (리듬만 검사)"))

    print("\n[1단계] 어휘 검색")
    hits = lexicon_hits(text, rules)
    if not hits:
        print("  걸린 항목 없음")
    for grp, c in hits:
        total = sum(c.values())
        d = total / max(len(text), 1) * 1000
        limit = grp.get("per_1000", 0)
        over = d > limit and total >= grp.get("min_hits", 1)
        items = ", ".join(f"{k}({v})" for k, v in c.most_common(6))
        print(f"  {'▲ ' if over else '  '}[{grp['layer']}] {grp['name']} · {total}건 "
              f"({d:.2f}/1천자, 허용 {limit}) → {items}")
        if over and grp.get("context_ok"):
            print(f"       ↳ 다음 맥락이면 무시: {grp['context_ok']}")

    print("\n[2단계] 리듬 측정")
    r = analyze(text, rules)
    if not r:
        print("  측정할 산문이 없음"); return
    th = rules["rhythm"]
    f = lambda c: "▲" if c else " "

    print(f"   문장 수            {r['n']}")
    print(f"   평균 길이(어절)    {r['mean']:.1f}")
    if r["n"] >= th["length_cv"].get("min_sentences", 8):
        print(f" {f(r['cv'] < th['length_cv']['warn_below'])} 길이 변동계수      {r['cv']:.2f}   (경고: {th['length_cv']['warn_below']:.2f} 미만)")
    else:
        print(f"   길이 변동계수      {r['cv']:.2f}   (문장 {r['n']}개 — 표본이 작아 판정 보류)")
    print(f" {f(r['form_ratio'] > th['ending_mode']['warn_above'])} 최빈 종결형        '{r['top_form']}' {r['form_ratio']*100:.0f}%  (경고: {th['ending_mode']['warn_above']*100:.0f}% 초과)")
    print(f" {f(r['conj'] > th['head_conjunction']['warn_above'])} 문두 접속사 비율   {r['conj']*100:.0f}%   (경고: {th['head_conjunction']['warn_above']*100:.0f}% 초과)")
    print(f" {f(r['comma'] > th['comma_per_sent']['warn_above'])} 문장당 쉼표        {r['comma']:.2f}   (경고: {th['comma_per_sent']['warn_above']:.2f} 초과)")

    if r["informality"] is not None:
        lim = rules["informality_markers"]["warn_below_total"]
        print(f" {f(r['informality'] < lim)} 구어 표지 밀도     {r['informality']:.2f}/1천자  (캐주얼 문체 경고: {lim} 미만)")

    cl = r["closing"]
    if cl:
        warn = cl["ratio"] > th["closing_ratio"]["warn_above"]
        print(f" {f(warn)} 닫는 마무리 비율   {cl['hits']}/{cl['total']} = {cl['ratio']*100:.0f}%  (경고: {th['closing_ratio']['warn_above']*100:.0f}% 초과)")
        if warn:
            for kind, last in cl["detail"][:4]:
                print(f"       · [{kind}] {last[-46:]}")
    else:
        print("   닫는 마무리 비율   생략 (글 3편 미만이거나 격식체·공문)")

    print("\n   종결형 상위: " + ", ".join(f"'{k}' {v}" for k, v in r["forms"].most_common(6)))
    print("   문체 층 분포: " + ", ".join(f"{k} {v}" for k, v in r["strata"].most_common()))

    if style:
        print(f"\n[3단계] 문체 정합 — {style}")
        for name, ok, summary, detail in style_check(text, r, style, rules):
            print(f" {'  ' if ok else '▲ '}{name:<10} {summary}")
            for d in detail:
                print(f"       · {d}")

    print("\n※ ▲는 검토 신호이지 오류 판정이 아니다. rules.json의 overcorrection_guards를 함께 볼 것.\n")


if __name__ == "__main__":
    main()
