import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 1. 페이지 설정 및 한글 폰트 CSS 적용
st.set_page_config(page_title="🌱 극지식물 최적 EC 농도 연구", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
html, body, [class*="css"], .stMarkdown {
    font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# 폰트 설정 (Plotly용)
CHART_FONT = dict(family="Noto Sans KR, Malgun Gothic, Apple SD Gothic Neo, sans-serif")

# 2. 데이터 로딩 함수 (NFC/NFD 대응)
@st.cache_data
def load_data():
    base_path = Path("data")
    if not base_path.exists():
        st.error("❌ 'data/' 디렉토리가 존재하지 않습니다.")
        return None, None

    # 파일 목록 정규화 및 탐색
    all_files = list(base_path.iterdir())
    
    def get_normalized_path(target_name):
        for p in all_files:
            if unicodedata.normalize('NFC', p.name) == unicodedata.normalize('NFC', target_name):
                return p
        return None

    # 학교 정보 정의
    school_info = {
        "송도고": {"ec_target": 1.0, "color": "#ABDEE6"},
        "하늘고": {"ec_target": 2.0, "color": "#FFCCB6"}, # 최적
        "아라고": {"ec_target": 4.0, "color": "#F3B0C3"},
        "동산고": {"ec_target": 8.0, "color": "#CBAACB"}
    }

    env_dfs = []
    # 환경 데이터 로드 (CSV)
    for school in school_info.keys():
        file_path = get_normalized_path(f"{school}_환경데이터.csv")
        if file_path:
            df = pd.read_csv(file_path)
            df['school'] = school
            df['target_ec'] = school_info[school]['ec_target']
            env_dfs.append(df)
    
    env_data = pd.concat(env_dfs, ignore_index=True) if env_dfs else pd.DataFrame()
    if not env_data.empty:
        env_data['time'] = pd.to_datetime(env_data['time'])

    # 생육 결과 데이터 로드 (XLSX)
    growth_path = get_normalized_path("4개교_생육결과데이터.xlsx")
    growth_data_dict = {}
    if growth_path:
        xl = pd.ExcelFile(growth_path)
        # 시트명 정규화 비교
        for sheet in xl.sheet_names:
            norm_sheet = unicodedata.normalize('NFC', sheet)
            if norm_sheet in school_info:
                df = xl.parse(sheet)
                df['school'] = norm_sheet
                df['target_ec'] = school_info[norm_sheet]['ec_target']
                growth_data_dict[norm_sheet] = df
    
    growth_data = pd.concat(growth_data_dict.values(), ignore_index=True) if growth_data_dict else pd.DataFrame()

    return env_data, growth_data, school_info

# 데이터 불러오기 실행
with st.spinner('데이터를 불러오는 중입니다...'):
    env_df, growth_df, SCHOOL_INFO = load_data()

if env_df.empty or growth_df.empty:
    st.error("데이터 파일을 찾을 수 없거나 형식이 잘못되었습니다. 파일명을 확인해주세요.")
    st.stop()

# 3. 사이드바 구성
st.sidebar.title("검색 필터")
selected_school = st.sidebar.selectbox("대상 학교 선택", ["전체"] + list(SCHOOL_INFO.keys()))

# 데이터 필터링
if selected_school == "전체":
    disp_env = env_df
    disp_growth = growth_df
else:
    disp_env = env_df[env_df['school'] == selected_school]
    disp_growth = growth_df[growth_df['school'] == selected_school]

# 메인 화면 제목
st.title("🌱 극지식물 최적 EC 농도 연구 대시보드")
st.markdown("---")

# 4. 탭 구성
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# --- Tab 1: 실험 개요 ---
with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("연구 배경 및 목적")
        st.write("""
        본 연구는 극지 환경에서 자생하는 식물의 최적 생육 조건을 규명하기 위해 수행되었습니다.
        특히 양액의 **EC(전기전도도) 농도** 변화가 식물의 생중량, 잎 수 및 뿌리 발달에 미치는 영향을 4개 학교와의 협업 데이터를 통해 분석합니다.
        """)
        
        # 학교별 조건 표
        st.subheader("학교별 실험 설계 조건")
        info_table = []
        for s, v in SCHOOL_INFO.items():
            count = len(growth_df[growth_df['school'] == s])
            info_table.append({"학교명": s, "EC 목표값": v['ec_target'], "개체수": f"{count}개", "비고": "최적" if s == "하늘고" else "-"})
        st.table(pd.DataFrame(info_table))

    with col2:
        st.subheader("Key Metrics")
        st.metric("총 실험 개체수", f"{len(growth_df)} 개")
        st.metric("평균 온도", f"{env_df['temperature'].mean():.1f} °C")
        st.metric("평균 습도", f"{env_df['humidity'].mean():.1f} %")
        st.success(f"최적 EC 농도: 2.0 (하늘고)")

# --- Tab 2: 환경 데이터 ---
with tab2:
    st.subheader("학교별 환경 지표 비교")
    
    # 2x2 서브플롯
    fig_env = make_subplots(rows=2, cols=2, subplot_titles=("평균 온도 (°C)", "평균 습도 (%)", "평균 pH", "목표 EC vs 실측 EC"))
    
    avg_env = env_df.groupby('school').mean(numeric_only=True).reset_index()
    
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['temperature'], marker_color='#FF9999'), row=1, col=1)
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['humidity'], marker_color='#99FF99'), row=1, col=2)
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['ph'], marker_color='#9999FF'), row=2, col=1)
    
    # 이중 막대 (목표 vs 실측)
    fig_env.add_trace(go.Bar(name='목표 EC', x=avg_env['school'], y=avg_env['target_ec']), row=2, col=2)
    fig_env.add_trace(go.Bar(name='실측 EC', x=avg_env['school'], y=avg_env['ec']), row=2, col=2)

    fig_env.update_layout(height=700, showlegend=False, font=CHART_FONT, template="plotly_white")
    st.plotly_chart(fig_env, use_container_width=True)

    if selected_school != "전체":
        st.subheader(f"📈 {selected_school} 시계열 변화")
        fig_line = make_subplots(specs=[[{"secondary_y": True}]])
        fig_line.add_trace(go.Scatter(x=disp_env['time'], y=disp_env['temperature'], name="온도(°C)"), secondary_y=False)
        fig_line.add_trace(go.Scatter(x=disp_env['time'], y=disp_env['humidity'], name="습도(%)"), secondary_y=True)
        fig_line.add_trace(go.Scatter(x=disp_env['time'], y=disp_env['ec'], name="실측 EC", line=dict(dash='dash')), secondary_y=False)
        
        # 목표 EC 수평선
        target_val = SCHOOL_INFO[selected_school]['ec_target']
        fig_line.add_hline(y=target_val, line_dash="dot", annotation_text="목표 EC", line_color="red")
        
        fig_line.update_layout(font=CHART_FONT, hovermode="x unified")
        st.plotly_chart(fig_line, use_container_width=True)

    with st.expander("환경 데이터 원본 및 다운로드"):
        st.dataframe(disp_env)
        csv = disp_env.to_csv(index=False).encode('utf-8-sig')
        st.download_button("CSV 다운로드", data=csv, file_name=f"{selected_school}_환경데이터.csv", mime='text/csv')

# --- Tab 3: 생육 결과 ---
with tab3:
    # 핵심 결과 카드
    avg_growth = growth_df.groupby('school').mean(numeric_only=True).reset_index()
    best_school = avg_growth.loc[avg_growth['생중량(g)'].idxmax(), 'school']
    
    st.info(f"🥇 분석 결과: **{best_school}**(목표 EC: {SCHOOL_INFO[best_school]['ec_target']})에서 평균 생중량이 가장 높게 나타났습니다.")

    # 2x2 생육 비교
    fig_growth = make_subplots(rows=2, cols=2, subplot_titles=("평균 생중량(g)", "평균 잎 수(장)", "평균 지상부 길이(mm)", "실험 개체수"))
    
    colors = ['#D3D3D3'] * len(avg_growth)
    best_idx = avg_growth[avg_growth['school'] == "하늘고"].index[0]
    colors[best_idx] = '#FF4B4B' # 최적 강조

    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['생중량(g)'], marker_color=colors), row=1, col=1)
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['잎 수(장)']), row=1, col=2)
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['지상부 길이(mm)']), row=2, col=1)
    
    counts = growth_df['school'].value_counts().reindex(avg_growth['school'])
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=counts), row=2, col=2)

    fig_growth.update_layout(height=700, showlegend=False, font=CHART_FONT, template="plotly_white")
    st.plotly_chart(fig_growth, use_container_width=True)

    # 박스플롯 분포
    st.subheader("학교별 생중량 분포 비교")
    fig_box = px.box(growth_df, x="school", y="생중량(g)", color="school", 
                     color_discrete_map={k: v['color'] for k, v in SCHOOL_INFO.items()})
    fig_box.update_layout(font=CHART_FONT)
    st.plotly_chart(fig_box, use_container_width=True)

    # 상관관계
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.plotly_chart(px.scatter(disp_growth, x="잎 수(장)", y="생중량(g)", color="school", trendline="ols", 
                                   title="잎 수 vs 생중량 상관관계", font_family=CHART_FONT['family']), use_container_width=True)
    with col_c2:
        st.plotly_chart(px.scatter(disp_growth, x="지상부 길이(mm)", y="생중량(g)", color="school", trendline="ols", 
                                   title="지상부 길이 vs 생중량 상관관계", font_family=CHART_FONT['family']), use_container_width=True)

    with st.expander("생육 데이터 원본 및 XLSX 다운로드"):
        st.dataframe(disp_growth)
        
        # XLSX 다운로드 (BytesIO 사용 필수)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            disp_growth.to_excel(writer, index=False, sheet_name='Growth_Data')
        
        st.download_button(
            label="XLSX 다운로드",
            data=buffer.getvalue(),
            file_name=f"{selected_school}_생육데이터.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
