# korean-style-guard

한국어 글에서 AI 문체를 걸러내는 Claude 스킬.

어미만 바꾸고 나머지는 문어체로 두는 문제 — "음슴체로 써줘"라고 했는데 `해당 매장은 접근성이 우수한 것으로 판단됨`이 나오는 그 문제 — 를 정면으로 다룬다.

## 설치

```
/plugin marketplace add <계정>/korean-style-guard
/plugin install korean-style-guard@korean-style-guard
```

Claude Code와 Cowork 양쪽에서 쓴다. 설치하면 한국어 글을 쓰거나 고칠 때 자동으로 걸리고, 직접 부를 수도 있다.

```
/korean-style-guard:check-style 원고.md
```

## 무엇을 하나

기존 한국어 AI 문체 자료 대부분은 금지 어휘 목록이다. 이 스킬은 어휘 아래 세 층위를 더 본다.

**1. 문체 정합 (6개 축)**
문체는 종결어미가 아니라 어미·어휘·문장 길이·관형절 중첩·담화표지·조사 생략의 묶음이다. 어미만 맞고 나머지가 안 따라오면 어색해진다. 음슴체는 공문서형과 캐주얼형 두 종류이고, `~잖아`·`~거든`·`~더라`에는 각각 사용 조건이 있다.

**2. 리듬 정량 기준**
어휘를 다 고쳐도 남는 기계 냄새의 정체. 문장 길이 변동계수 0.40 미만이면 길이가 한 곳에 몰린 것이다.

**3. 과교정 방지**
금지어 목록을 기계적으로 적용하면 새로운 AI 티가 생긴다. 문장을 전부 짧게 자르면 균일도가 그대로라 여전히 티가 난다. 치환표에는 "오히려 이 표현이 맞는 맥락" 열이 붙어 있다.

## 점검 스크립트

표준 라이브러리만 쓴다. Claude 없이 단독으로도 돌아간다.

```bash
python3 plugins/korean-style-guard/skills/korean-style-guard/scripts/check_style.py 원고.md
```

`examples/` 표본으로 판별력을 확인할 수 있다.

| | `ai-style.txt` | `human-formal.txt` |
|---|---|---|
| 길이 변동계수 | 0.20 ▲ | 0.39 |
| 최빈 종결형 | `습니다` 60% ▲ | `습니다` 57% |
| 문두 접속사 | 40% ▲ | 0% |
| 어휘 적발 | 4건 | 0건 |

▲는 검토 신호이지 오류 판정이 아니다.

## 구성

```
plugins/korean-style-guard/
├── skills/korean-style-guard/
│   ├── SKILL.md              # 작업 규칙 (Claude가 읽는 본체)
│   ├── scripts/check_style.py
│   └── references/style-guide.md   # 근거·확장 목록 (L1~L5 5층 구조)
└── commands/check-style.md   # /korean-style-guard:check-style
```

`references/style-guide.md`는 스킬 없이 읽어도 되는 독립 문서다. 층위별 항목, 치환 사전 18행, 오탐 맥락, 4단계 검증 절차가 들어 있다.

## 주의

이 저장소의 문서를 점검 스크립트로 돌리면 전부 걸린다. 금지 표현을 예시로 인용했기 때문이다. 검색 대상은 본문이지 규칙집이 아니다.

## 크레딧

어휘·관용구 층위(공간·기하 은유, 영어 직역, 결말 상투구)는 <!-- TODO: 원본 md 작성자 이름 또는 출처 링크 --> 의 조사 자료에서 출발했다. 여기에 문법·리듬·문체 정합 층위와 과교정 방지 규칙, 측정 스크립트를 더했다.

## 라이선스

MIT
