# -*- coding: utf-8 -*-
"""verify_tone.py -- 문체가 애널리스트 리포트인가 (v5.21 신설).

배경(2026-09 에프에스티): verify_style 100점을 받은 리포트를 사용자가 읽고
"AI 티가 많이 난다"고 했다. 기존 검증기는 **항목이 있는가**만 보지
**어떻게 쓰였는가**를 보지 않는다. 그래서 체크리스트를 채우는 방향으로 쓰게 되고,
결과가 기계 글이 된다.

한국IR협의회 기업분석 보고서 16편을 fitz 로 실측해 기준선을 잡았다.

    본문 볼드 비율      6.4 ~ 9.0%   (우리 교정 전 19.0%)
    "A가 아니라 B"      0.00/1,000자  (우리 교정 전 1.05)
    "~라는 뜻이다"       0.00/1,000자
    유보 표현           0.39 ~ 1.4/1,000자  (우리 교정 전 0.20)

문장 전체를 볼드로 감싸는 것이 가장 큰 증상이었다 -- 볼드 416개 중
26자 이상이 112개였다. 강조가 그만큼 많으면 강조가 아니다.

사용: python scripts/verify_tone.py {종목명}
"""
import io
import json
import os
import re
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- IR협의회 16편 실측에서 나온 상수 ---
BOLD_RATIO_MAX = 12.0      # 실측 6.4~9.0%. 12% 를 넘으면 강조가 아니라 습관이다
BOLD_RATIO_MIN = 3.0       # (v5.22) 하한. 상한만 두었더니 19.0% -> 0.34% 로 갔다.
                           # fitz span 실측 IR협의회 9.4~15.8%. 강조가 없으면
                           # 어디를 읽을지 모른다 -- 가독성이 떨어진 직접 원인이다
LONG_BOLD_MAX = 12         # 26자 이상 볼드 개수 (문장 통째 강조)
CONTRAST_MAX = 0.35        # "A가 아니라 B" /1,000자. 실측 0.00
META_MAX = 3               # "이 리포트/본 리서치/중심 질문" 등 자의식 표현
HEDGE_MIN = 0.30           # 유보 표현 /1,000자. 실측 0.39~1.40
LABEL_MAX = 3              # "시사점:" 라벨. IR협의회 실측 0회

META_PAT = r'이 리포트|본 리서치|이 글은|중심 질문|정직한 답|앞서 말했듯|위에서 보았듯'
HEDGE_PAT = (r'판단한다|판단된다|전망이다|전망한다|전망된다|추정한다|추정된다|'
             r'예상된다|예상한다|기대된다|파악된다|확인이 필요|확인할 필요|보인다')
CONTRAST_PAT = r'(?:이|가)\s*아니라'
TAUTOLOGY_PAT = r'뜻이다|셈이다|셈이며'


def body_text(sections, order):
    """표 줄을 뺀 본문. 표 안 볼드는 강조가 아니라 서식이다."""
    out = []
    for k in order:
        for line in (sections.get(k) or '').split('\n'):
            if line.lstrip().startswith('|'):
                continue
            out.append(line)
    return '\n'.join(out)


def measure(sections, order):
    t = body_text(sections, order)
    chars = len(re.sub(r'\s|\*', '', t)) or 1
    bolds = [re.sub(r'\s+', ' ', m.group(1)).strip()
             for m in re.finditer(r'\*\*([^*]+?)\*\*', t, flags=re.S)]
    # 마진노트/한 줄 평가 라벨은 렌더 규약이라 제외한다
    bolds = [b for b in bolds
             if not b.startswith(('한 줄:', '한 줄 평가:'))]
    bold_chars = sum(len(b) for b in bolds)
    return {
        'chars': chars,
        'bold_ratio': bold_chars / chars * 100,
        'long_bold': sum(1 for b in bolds if len(b) >= 26),
        'contrast': len(re.findall(CONTRAST_PAT, t)) / chars * 1000,
        'contrast_n': len(re.findall(CONTRAST_PAT, t)),
        'tautology_n': len(re.findall(TAUTOLOGY_PAT, t)),
        'meta': len(re.findall(META_PAT, t)),
        'hedge': len(re.findall(HEDGE_PAT, t)) / chars * 1000,
        'label': len(re.findall(r'시사점:', t)),
        'tautology': len(re.findall(TAUTOLOGY_PAT, t)) / chars * 1000,
    }


def check(sections, order):
    """반환: [(코드, 라벨, 상태, 실측, 기준, 왜)]"""
    m = measure(sections, order)
    rows = [
        # 하한은 본문이 1,000자는 돼야 적용한다. 짧은 조각에서 밀도를 따지면
        # 픽스처·부분 섹션이 전부 FAIL 이 나고, 그러면 게이트를 무시하게 된다.
        ('T1', '본문 볼드 비율',
         (m['bold_ratio'] <= BOLD_RATIO_MAX
          and (m['chars'] < 1000 or m['bold_ratio'] >= BOLD_RATIO_MIN)),
         f"{m['bold_ratio']:.1f}%", f"{BOLD_RATIO_MIN}~{BOLD_RATIO_MAX}%",
         'IR협의회 실측 6.4~15.8%. 많으면 습관이고 없으면 길잡이가 없다'),
        ('T2', '문장 통째 볼드(26자+)', m['long_bold'] <= LONG_BOLD_MAX,
         f"{m['long_bold']}개", f"<= {LONG_BOLD_MAX}개",
         '문장 전체 강조는 IR협의회 본문에 없다'),
        # 절대 2회 이하는 밀도와 무관하게 통과시킨다. 본문이 짧으면 밀도가
        # 튀어서 한 번 쓴 강조까지 FAIL 이 나고, 그러면 게이트를 무시하게 된다.
        ('T3', '"A가 아니라 B"', m['contrast'] <= CONTRAST_MAX or m['contrast_n'] <= 2,
         f"{m['contrast']:.2f}/1k", f"<= {CONTRAST_MAX}",
         '대구는 한 번이면 강조, 스무 번이면 버릇이다 (실측 0.00)'),
        ('T4', '자의식 표현', m['meta'] <= META_MAX,
         f"{m['meta']}회", f"<= {META_MAX}회",
         '"이 리포트의 중심 질문" 같은 메타 발언은 실측 0회'),
        ('T5', '유보 표현', m['hedge'] >= HEDGE_MIN,
         f"{m['hedge']:.2f}/1k", f">= {HEDGE_MIN}",
         '추정을 추정이라 적는다. 단정만 있으면 AI 글로 읽힌다 (실측 0.39~1.40)'),
        ('T6', '"시사점:" 라벨', m['label'] <= LABEL_MAX,
         f"{m['label']}회", f"<= {LABEL_MAX}회",
         'IR협의회는 라벨 대신 문단 안에서 해석한다 (실측 0회)'),
        ('T7', '"뜻이다/셈이다"', m['tautology'] <= 0.35 or m['tautology_n'] <= 2,
         f"{m['tautology']:.2f}/1k", '<= 0.35',
         '앞 문장을 다시 푸는 재진술 (실측 0.00~0.05)'),
    ]
    return rows, m


def main(stock_name):
    p = os.path.join(ROOT, 'scripts', f'analysis_{stock_name}.json')
    if not os.path.exists(p):
        print(f'[ERR] {p} 없음')
        return 2
    d = json.load(open(p, encoding='utf-8'))
    sections = d.get('sections') or {}
    order = (d.get('meta') or {}).get('section_order') or list(sections)

    print('=' * 72)
    print(f'  verify_tone (v5.21): {stock_name}')
    print('  한국IR협의회 기업분석 16편 실측 기준')
    print('=' * 72)
    rows, m = check(sections, order)
    fail = 0
    for code, label, ok, got, want, why in rows:
        icon = '✓' if ok else '✗'
        print(f"  [{icon} {code}] {label:20s} {got:>10s}  (기준 {want})")
        if not ok:
            fail += 1
            print(f"           -> {why}")
    print(f"\n  본문 {m['chars']:,}자 / FAIL {fail}건")
    if fail:
        print('  [차단] 문체가 애널리스트 리포트에서 멀다. '
              '볼드를 풀고, 대구를 줄이고, 추정은 추정이라고 적는다.')
    else:
        print('  [OK] 문체 기준 통과.')
    print('=' * 72)
    return 1 if fail else 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('사용: python scripts/verify_tone.py {종목명}')
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
