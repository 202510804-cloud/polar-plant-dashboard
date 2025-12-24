import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 1. 페이지 설정 및 한글 폰트 CSS
st.set_page_config(page_title="🌱 극지식물 최적 EC 농도 연구", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
html, body, [class*="css"], .stMarkdown {
    font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
}
</style>
""", unsafe_allow_html=True)

CHART_FONT = dict(family="Noto Sans KR, Malgun Gothic, Apple SD Gothic Neo, sans-serif")

# 2. 데이터 로딩 함수 (에러 방어 로직 강화)
@st.cache_data
def load_data():
    school_info = {
        "송도고": {"ec_target": 1.0, "color": "#ABDEE6"},
        "하늘고": {"ec_target": 2.0, "color": "#FFCCB6"}, 
        "아라고": {"ec_target": 4.0, "color": "#F3B0C3"},
        "동산고": {"ec_target": 8.0, "color": "#CBAACB"}
    }
    
    base_path = Path("data")
    if not base_path.exists():
        return pd.DataFrame(), pd.DataFrame(), school_info, "❌ 'data/' 폴더를 찾을 수 없습니다."

    all_files = list(base_path.iterdir())
    
    def get_normalized_path(target_name):
        target_norm = unicodedata.normalize('NFC', target_name)
        for p in all_files:
            if unicodedata.normalize('NFC', p.name) == target_norm:
                return p
        return None

    # 환경 데이터 로드
    env_dfs = []
    for school in school_info.keys():
        file_path = get_normalized_path(f"{school}_환경데이터.csv")
        if file_path:
            try:
                # 텍스트 인코딩 문제 방지를 위해 utf-8-sig 권장
                df = pd.read_csv(file_path)
                # 데이터가 비어있지 않은지 확인
                if not df.empty and 'time' in df.columns:
                    df['school'] = school
                    df['target_ec'] = school_info[school]['ec_target']
                    # ⭐ 핵심 수정: 시간 변환 실패 시 에러 대신 NaT(결측치) 처리
                    df['time'] = pd.to_datetime(df['time'], errors='coerce')
                    # 시간 변환에 실패한 행은 제거
                    df = df.dropna(subset=['time'])
                    env_dfs.append(df)
            except Exception as e:
                st.warning(f"{school} 데이터 처리 중 오류: {e}")
    
    env_data = pd.concat(env_dfs, ignore_index=True) if env_dfs else pd.DataFrame()

    # 생육 결과 데이터 로드
    growth_data_list = []
    growth_path = get_normalized_path("4개교_생육결과데이터.xlsx")
    
    if growth_path:
        try:
            xl = pd.ExcelFile(growth_path)
            for sheet in xl.sheet_names:
                norm_sheet = unicodedata.normalize('NFC', sheet)
                if norm_sheet in school_info:
                    df = xl.parse(sheet)
                    if not df.empty:
                        df['school'] = norm_sheet
                        df['target_ec'] = school_info[norm_sheet]['ec_target']
                        growth_data_list.append(df)
        except Exception as e:
            st.warning(f"엑셀 로드 오류: {e}")
    
    growth_data = pd.concat(growth_data_list, ignore_index=True) if growth_data_list else pd.DataFrame()

    return env_data, growth_data, school_info, None

# 데이터 로드 실행
with st.spinner('데이터를 분석 중입니다...'):
    env_df, growth_df, SCHOOL_INFO, error_msg = load_data()

# 3. 예외 상황 처리
if error_msg:
    st.error(error_msg)
    st.stop()

if env_df.empty:
    st.error("⚠️ 환경 데이터(CSV)를 불러오지 못했거나 'time' 컬럼 형식이 잘못되었습니다.")
    st.stop()

if growth_df.empty:
    st.error("⚠️ 생육 결과 데이터(XLSX)를 불러오지 못했습니다.")
    st.stop()

# --- 대시보드 UI 시작 ---
st.title("🌱 극지식물 최적 EC 농도 연구")

# 사이드바
selected_school = st.sidebar.selectbox("대상 학교 선택", ["전체"] + list(SCHOOL_INFO.keys()))

# 데이터 필터링
if selected_school == "전체":
    disp_env = env_df
    disp_growth = growth_df
else:
    disp_env = env_df[env_df['school'] == selected_school]
    disp_growth = growth_df[growth_df['school'] == selected_school]

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("연구 배경 및 목적")
        st.info("학교별 EC 농도 차이에 따른 극지식물 생육 변화를 분석합니다.")
        st.table(pd.DataFrame([{"학교명": s, "EC 목표": v['ec_target']} for s, v in SCHOOL_INFO.items()]))
    with col2:
        st.metric("총 개체수", f"{len(growth_df)}개")
        st.metric("평균 온도", f"{env_df['temperature'].mean():.1f} °C")

with tab2:
    st.subheader("학교별 환경 지표")
    fig_env = make_subplots(rows=2, cols=2, subplot_titles=("온도", "습도", "pH", "EC 비교"))
    avg_env = env_df.groupby('school').mean(numeric_only=True).reset_index()
    
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['temperature']), row=1, col=1)
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['humidity']), row=1, col=2)
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['ph']), row=2, col=1)
    fig_env.add_trace(go.Bar(name='실측EC', x=avg_env['school'], y=avg_env['ec']), row=2, col=2)
    
    fig_env.update_layout(height=600, font=CHART_FONT, template="plotly_white")
    st.plotly_chart(fig_env, use_container_width=True)

with tab3:
    st.subheader("생육 결과 분석")
    avg_growth = growth_df.groupby('school').mean(numeric_only=True).reset_index()
    
    # 2x2 차트
    fig_growth = make_subplots(rows=1, cols=2, subplot_titles=("평균 생중량(g)", "평균 잎 수"))
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['생중량(g)']), row=1, col=1)
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['잎 수(장)']), row=1, col=2)
    fig_growth.update_layout(font=CHART_FONT, template="plotly_white")
    st.plotly_chart(fig_growth, use_container_width=True)
    
    with st.expander("데이터 원본 확인"):
        st.write(disp_growth)
