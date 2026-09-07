"""
와이지엔터 위닝펀드 18-1 PPT 본문 내용 채우기 (v3)
- 31 슬라이드 PPT의 각 슬라이드 텍스트 박스를 본 리포트 본문으로 채움
- Cover/Index는 _yg_wf_pptx_builder.py에서 처리, 이 스크립트는 Slide 3~31 본문
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pathlib import Path

NAVY = RGBColor(0x1E, 0x3A, 0x6D)
RED = RGBColor(0xC8, 0x10, 0x2E)
GREY = RGBColor(0x44, 0x44, 0x44)

DST = Path(r'C:\Users\hsh\Desktop\vibecoding\주식 ai 리서치 리포트 에이전트\output\와이지엔터\18-1_와이지엔터테인먼트_기업분석리포트_v2.pptx')


def fill_body_slide(slide, header_text, copy1, body1_head, body1_text, copy2, body2_head, body2_text):
    """본문 슬라이드 — 헤더 + 좌측 카피 + 본문 2개"""
    # 양식 본문 슬라이드는 텍스트박스 위치별로:
    # [0] 섹션 헤더 (산업분석/기업분석/...)
    # [1] 본문 상단 (소제목 + 내용)
    # [3] 본문 하단 (소제목 + 내용)
    # [4] 좌측 카피 하단 (요약 내용)
    # [7] 좌측 카피 상단 (요약 제목/요약 1)

    # 좌측 카피 텍스트 박스들 (T<2.0 또는 5.0<T<6.0)
    # 본문 텍스트 박스들 (L>1.5)

    # 모든 텍스트 박스 찾아 위치별 분류
    text_boxes = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            l = Emu(sh.left).inches if sh.left else 0
            t = Emu(sh.top).inches if sh.top else 0
            text_boxes.append((t, l, sh))

    # 위치별 매핑
    for t_pos, l_pos, sh in text_boxes:
        txt = sh.text_frame.text.strip()
        # 헤더 (좌측 상단, T<0.5)
        if t_pos < 0.5 and l_pos < 1.0 and 'Industry' in txt or 'Company' in txt or 'Investment' in txt or 'Risk' in txt or 'Financial' in txt or 'Valuation' in txt:
            if header_text:
                _set_text(sh.text_frame, header_text, font_size=18, bold=True, color=NAVY)
        # 좌측 카피 상단 (L<1.5, 0.8<T<1.8)
        elif l_pos < 1.5 and 0.8 < t_pos < 1.8:
            if copy1:
                _set_text(sh.text_frame, copy1, font_size=9, color=GREY)
        # 좌측 카피 하단 (L<1.5, 5.5<T<6.3)
        elif l_pos < 1.5 and 5.5 < t_pos < 6.3:
            if copy2:
                _set_text(sh.text_frame, copy2, font_size=9, color=GREY)
        # 본문 상단 (L>1.5, T<2.0)
        elif l_pos >= 1.5 and 0.5 < t_pos < 2.5:
            if body1_head or body1_text:
                _write_body(sh.text_frame, body1_head, body1_text)
        # 본문 하단 (L>1.5, 5.0<T<7.0)
        elif l_pos >= 1.5 and 5.0 < t_pos < 7.0:
            if body2_head or body2_text:
                _write_body(sh.text_frame, body2_head, body2_text)


def _set_text(tf, text, font_size=None, bold=None, color=None):
    tf.clear()
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = text
    if font_size: r.font.size = Pt(font_size)
    if bold is not None: r.font.bold = bold
    if color: r.font.color.rgb = color


def _write_body(tf, subhead, body_text):
    tf.clear()
    p = tf.paragraphs[0]
    if subhead:
        r = p.add_run()
        r.text = subhead
        r.font.size = Pt(11)
        r.font.bold = True
        r.font.color.rgb = NAVY
        p = tf.add_paragraph()
    r = p.add_run()
    r.text = body_text
    r.font.size = Pt(9)


def fill_industry(prs):
    """Phase 4: 산업분석 — PPT 슬라이드 3·4·5·6 (인덱스 2·3·4·5)"""

    # PPT Slide 3 (idx 2) = Word Slide 3: 산업분석 1 상단
    fill_body_slide(
        prs.slides[2],
        header_text='산업분석 Industry Overview',
        copy1='실적은 선방인데\n주가는 부진',
        body1_head='엔터 4사 -39%, 컨센은 +6%',
        body1_text='K-POP 산업이 1년 사이 가장 곤란한 자리에 와 있다. 글로벌 음악산업은 IFPI 기준 2014년 150억$ → 2025년 317억$로 11년간 두 배 넘게 자랐고, 스트리밍 부문이 220억$로 전체 69.6%를 차지하며 매년 6~10% 성장 중이다. 한국은 글로벌 음악산업 매출 7위로 올라섰고 미국 CD 판매 톱10 중 7개가 K-POP 앨범인 만큼 한국 기획사의 산업 내 위상은 분명히 높아진 상태다.\n\n문제는 산업이 자라는 동안 한국 엔터 4사 주가가 정반대로 움직였다는 점이다. 4사 합산 영업이익 컨센서스는 6개월 전 대비 +6% 상향됐는데도, 같은 기간 주가는 4사 평균 -39% 빠졌다. 12개월 선행 PER은 19배까지 내려와 2025년 25~30배 대비 한 단계 내려앉았다. 하이브 25배(과거 40배 상회), SM 15배, JYP 16배, YG 15.9배 모두 고점 대비 평균 -39% 낙폭.',
        copy2='실적과 주가의 괴리',
        body2_head='실적 하향이 아닌 디레이팅의 전형',
        body2_text='와이지엔터테인먼트의 15.9배는 SM 15배와 4사 공동 최저 수준이고, 고점 대비 낙폭도 그만큼 깊다. 지금 시장이 본 것은 이익이 줄었다는 사실이 아니라, 같은 이익에 더 작은 가격표를 붙이고 있다는 사실이다. 복수 증권사 분석은 이를 "실적 하향이 아닌 밸류에이션 디레이팅(Down-rating)의 전형"이라 진단한다. 시장은 K-POP을 더 이상 고성장 성장주가 아닌 성숙기 서비스업으로 다시 분류하는 중이며, 엔터 섹터의 적은 산업 내부가 아니라 외부 매크로 환경에 있다.'
    )

    # PPT Slide 4 (idx 3) = Word Slide 4: 산업분석 1 하단
    fill_body_slide(
        prs.slides[3],
        header_text='산업분석 Industry Overview',
        copy1='한한령·모멘텀·\n반도체 쏠림',
        body1_head='멀티플이 깎인 세 가지 이유 — 한한령',
        body1_text='산업 전문가들은 멀티플 하락의 원인을 세 축으로 분해한다. 첫째, 한한령 해제 기대가 식었다. 2025년에는 한국 가수 EPEX 베이징 공연 확정과 드림콘서트 베이징 추진으로 중국 시장 개방 기대가 최고조에 달했고, 시장은 한한령 해제 옵션 가치를 멀티플에 프리미엄으로 얹어 놓은 상태였다. 한한령이 풀릴 경우의 잠재력은 결코 작지 않다. 2016년 한 해에만 빅뱅이 중국 공연 박스오피스 1위(약 930억 원)를 기록했고, 같은 해 와이지엔터테인먼트의 중국 매출은 약 690억 원, 콘서트 매출은 330억 원에 달했다. 그러나 2026년 1월 정부가 "해제까지 상당한 시간이 소요될 것"이라 정리한 한 줄로 K-POP 4사 주가에서 중국 옵션 프리미엄이 통째로 빠졌다.',
        copy2='모멘텀 부재 + 반도체 쏠림',
        body2_head='다음 성장 트랙 부재 + 외부 대체재',
        body2_text='둘째, 시장이 보기에 K-POP의 다음 성장 스토리가 안 보인다. K-POP은 2018년 BTS·블랙핑크 글로벌 진출, 2023년 음반 판매량 고성장, 2025년 공연 고성장이라는 단계별 성장 트랙을 차례로 보여줬다. 그러나 2026년의 새 트랙이 무엇이냐는 물음에 시장은 아직 답을 받지 못했다. BTS 컴백 보유 하이브를 빼면 엔터 3사 평균 매출 성장률 전망은 +7.7%에 불과한데, 2022~2025년 +35~40% 성장 곡선과 비교하면 확연한 둔화다.\n\n셋째, 외부에 압도적 대체재가 있다. 삼성전자·SK하이닉스 합산 영업이익이 2025년 91조 → 2026년 579조로 +500% 급증할 전망이고, 반도체주는 연초 대비 +112.8% 올랐다. 이익 성장률 500%+ 반도체 대형주가 PER 10배 미만에서 거래되는 장세에서, 연 10% 성장 엔터에 PER 20배 프리미엄을 지불할 자금은 자연히 줄어들 수밖에 없다.'
    )

    # PPT Slide 5 (idx 4) = Word Slide 5: 산업분석 2 상단
    fill_body_slide(
        prs.slides[4],
        header_text='산업분석 Industry Overview',
        copy1='하반기에\n첫 단추가 풀린다',
        body1_head='디레이팅이 영구가 아닌 이유 — 회복 트리거 4가지',
        body1_text='디레이팅이 영구적이라고 보기 어려운 이유는 회복의 단서가 시장 안에 이미 나와 있기 때문이다. 키움증권이 제시한 회복 트리거는 네 가지인데, 그 중 두 가지는 산업 구조 자체를 바꾸는 카드이고 나머지 두 가지는 향후 12개월 안에 가시화되는 단기 카드다.\n\n[카드 1] 콘텐츠 수익화 — K-POP 강점인 고퀄리티 콘텐츠 제작 역량은 동시에 비용 부담을 늘려 영업이익률(OPM)을 깎는 병목으로 작용해 왔다. 자체 예능을 무료 배포에서 구독 모델로 돌리면 산업 전체에 연 매출 잠재력 2.4조, 영업이익 8,400억의 새 시장이 열린다는 추정.\n\n[카드 2] 글로벌 레이블 진출 — 66조 규모 글로벌 레이블 시장에서 한국 4사의 "360도 통합 모델"이 분업형 글로벌 빅3(유니버설·소니·워너) 대비 어디까지 협상력을 가져갈 수 있는지가 관건. BTS 월드투어가 테일러 스위프트 대비 부가매출 효율 +49% 우위.',
        copy2='메가 IP 컴백 트리거',
        body2_head='카드 3·4 — 단기 카드 (와이지 즉시 수혜)',
        body2_text='[카드 3] 현지화 IP 안착 — 캣츠아이(북미)·앤팀(일본) 같은 K-POP 시스템 수출 레퍼런스가 자리잡으면 K-POP 멀티플 정당화의 새 잣대가 된다. 와이지엔터테인먼트도 글로벌 트레이닝 센터(일본·태국·중국·서구권 연습생 선발) 신설로 같은 길에 진입.\n\n[카드 4] 메가 IP 컴백 사이클 — BTS·빅뱅·블랙핑크의 군 제대와 재계약 후속 활동이 분기 실적을 끌어올린다. 네 가지 중 2026 하반기에 가장 빨리 가시화되는 것은 메가 IP 컴백이며, 빅뱅·블랙핑크를 가진 와이지엔터테인먼트도 그 흐름 위에 있다. 콘텐츠 수익화와 글로벌 레이블화는 중장기 카드, 메가 IP 컴백과 현지화 IP는 단기 카드로 분류.'
    )

    # PPT Slide 6 (idx 5) = Word Slide 6: 산업분석 2 하단
    fill_body_slide(
        prs.slides[5],
        header_text='산업분석 Industry Overview',
        copy1='같은 산업,\n다른 4가지 모델',
        body1_head='하이브·SM·JYP·YG — 같은 산업 다른 사업',
        body1_text='K-POP은 한국 4사가 사실상 다 차지하고 있지만, 4사가 같은 사업을 하는 것은 아니다. 각 사의 비즈니스 철학이 분명히 다르고, 그 차이가 멀티플 차이와 실적 변동성을 만든다.\n\n하이브(시총 10.1조·PER 25배): BTS 단일 IP 의존도가 75%까지 갔던 회사. BTS 군 복무 공백을 메우기 위해 NewJeans·LE SSERAFIM·ENHYPEN 등 다종 IP를 확보했고 캣츠아이(북미) 현지화에 베팅. 어도어 분쟁으로 자체 양성 검증 의문 노출.\n\nSM(시총 2.0조·PER 15배): 에스파·NCT·RIIZE 다종 IP 보유. 글로벌 IP 라이선싱·콘서트보다 일본·동남아 현지화 사업이 강점. RIIZE 인기 정체로 차세대 메가 IP 의문.',
        copy2='YG = 두 문제 동시 해결',
        body2_head='JYP 정체 vs YG 차별점',
        body2_text='JYP(시총 2.17조·PER 16배): 트와이스·스트레이키즈 두 메가 IP 외 신규 부재. ITZY·NMIXX·VCHA(북미) 모두 메가 IP 위상 미달. 시장은 JYP를 "현지화 시스템은 강한데 메가 IP는 못 만드는 회사"로 분류. 업계 최고 OPM 25.1%에도 PER 16배 정체.\n\nYG(시총 8,981억·PER 15.9배): 빅뱅·블랙핑크의 메가 IP 두 축에 베이비몬스터로 차세대 후보 입증. 9월 신인 보이그룹과 NEXT MONSTER로 6종 IP 분산 예정. 4사 중 유일하게 "메가 IP 양성 능력 + 컴백 효율화"라는 두 구조적 변화를 동시에 가진 회사. JYP의 정체와 차별화되는 핵심 포인트가 베몬 입증 + 신인 2팀 검증의 단계적 진행에 있다.'
    )

    print('  Phase 4 산업분석 4 슬라이드 완료')


def main():
    prs = Presentation(str(DST))
    print(f'PPT 로드: {len(prs.slides)}개')
    print('\n=== Phase 4: 산업분석 ===')
    fill_industry(prs)

    prs.save(str(DST))
    print(f'\n저장 완료: {DST.stat().st_size / 1024:.1f} KB')


if __name__ == '__main__':
    main()
