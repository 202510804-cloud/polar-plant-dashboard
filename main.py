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

CHART_FONT = dict(family="Noto Sans KR, Malgun Gothic, Apple SD Gothic Neo, sans-serif")

# 2. 데이터 로딩 함수
@st.cache_data
def load_data():
    # 학교 정보 정의 (에러 상황에서도 참조할 수 있도록 함수 최상단 배치)
    school_info = {
        "송도고": {"ec_target": 1.0, "color": "#ABDEE6"},
        "하늘고": {"ec_target": 2.0, "color": "#FFCCB6"}, 
        "아라고": {"ec_target": 4.0, "color": "#F3B0C3"},
        "동산고": {"ec_target": 8.0, "color": "#CBAACB"}
    }
    
    base_path = Path("data")
    
    # 디렉토리 체크
    if not base_path.exists():
        return pd.DataFrame(), pd.DataFrame(), school_info, "❌ 'data/' 폴더를 찾을 수 없습니다. 경로를 확인해주세요."

    all_files = list(base_path.iterdir())
    
    def get_normalized_path(target_name):
        target_norm = unicodedata.normalize('NFC', target_name)
        for p in all_files:
            if unicodedata.normalize('NFC', p.name) == target_norm:
                return p
        return None

    # 환경 데이터 로드 (CSV)
    env_dfs = []
    for school in school_info.keys():
        file_path = get_normalized_path(f"{school}_환경데이터.csv")
        if file_path:
            try:
                df = pd.read_csv(file_path)
                df['school'] = school
                df['target_ec'] = school_info[school]['ec_target']
                env_dfs.append(df)
            except Exception as e:
                st.warning(f"{school} CSV 로드 실패: {e}")
    
    env_data = pd.concat(env_dfs, ignore_index=True) if env_dfs else pd.DataFrame()
    if not env_data.empty:
        env_data['time'] = pd.to_datetime(env_data['time'])

    # 생육 결과 데이터 로드 (XLSX)
    growth_data_list = []
    growth_path = get_normalized_path("4개교_생육결과데이터.xlsx")
    
    if growth_path:
        try:
            xl = pd.ExcelFile(growth_path)
            for sheet in xl.sheet_names:
                norm_sheet = unicodedata.normalize('NFC', sheet)
                if norm_sheet in school_info:
                    df = xl.parse(sheet)
                    df['school'] = norm_sheet
                    df['target_ec'] = school_info[norm_sheet]['ec_target']
                    growth_data_list.append(df)
        except Exception as e:
            st.warning(f"엑셀 파일 로드 실패: {e}")
    
    growth_data = pd.concat(growth_data_list, ignore_index=True) if growth_data_list else pd.DataFrame()

    return env_data, growth_data, school_info, None

# 데이터 불러오기 실행
with st.spinner('데이터를 분석 중입니다...'):
    env_df, growth_df, SCHOOL_INFO, error_msg = load_data()

# 에러 처리 로직
if error_msg:
    st.error(error_msg)
    st.info("💡 Tip: GitHub 리포지토리에 'data' 폴더와 데이터 파일들이 올바르게 업로드되었는지 확인하세요.")
    st.stop()

if env_df.empty or growth_df.empty:
    st.error("⚠️ 데이터를 불러오지 못했습니다. 파일명(NFC/NFD)이나 파일 내용을 확인해주세요.")
    st.stop()

# --- 이하 대시보드 UI 코드 (동일) ---

st.sidebar.title("검색 필터")
selected_school = st.sidebar.selectbox("대상 학교 선택", ["전체"] + list(SCHOOL_INFO.keys()))

if selected_school == "전체":
    disp_env = env_df
    disp_growth = growth_df
else:
    disp_env = env_df[env_df['school'] == selected_school]
    disp_growth = growth_df[growth_df['school'] == selected_school]

st.title("🌱 극지식물 최적 EC 농도 연구 대시보드")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("연구 배경 및 목적")
        st.write("본 연구는 극지 환경에서 자생하는 식물의 최적 생육 조건을 규명하기 위해 수행되었습니다.")
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

with tab2:
    st.subheader("학교별 환경 지표 비교")
    fig_env = make_subplots(rows=2, cols=2, subplot_titles=("평균 온도 (°C)", "평균 습도 (%)", "평균 pH", "목표 EC vs 실측 EC"))
    avg_env = env_df.groupby('school').mean(numeric_only=True).reset_index()
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['temperature'], marker_color='#FF9999'), row=1, col=1)
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['humidity'], marker_color='#99FF99'), row=1, col=2)
    fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['ph'], marker_color='#9999FF'), row=2, col=1)
    fig_env.add_trace(go.Bar(name='목표 EC', x=avg_env['school'], y=avg_env['target_ec']), row=2, col=2)
    fig_env.add_trace(go.Bar(name='실측 EC', x=avg_env['school'], y=avg_env['ec']), row=2, col=2)
    fig_env.update_layout(height=700, showlegend=False, font=CHART_FONT, template="plotly_white")
    st.plotly_chart(fig_env, use_container_width=True)

    with st.expander("환경 데이터 원본 및 다운로드"):
        st.dataframe(disp_env)
        csv = disp_env.to_csv(index=False).encode('utf-8-sig')
        st.download_button("CSV 다운로드", data=csv, file_name=f"{selected_school}_환경데이터.csv", mime='text/csv')

with tab3:
    avg_growth = growth_df.groupby('school').mean(numeric_only=True).reset_index()
    best_school = avg_growth.loc[avg_growth['생중량(g)'].idxmax(), 'school']
    st.info(f"🥇 분석 결과: **{best_school}**에서 평균 생중량이 가장 높게 나타났습니다.")

    fig_growth = make_subplots(rows=2, cols=2, subplot_titles=("평균 생중량(g)", "평균 잎 수(장)", "평균 지상부 길이(mm)", "실험 개체수"))
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['생중량(g)']), row=1, col=1)
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['잎 수(장)']), row=1, col=2)
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['지상부 길이(mm)']), row=2, col=1)
    counts = growth_df['school'].value_counts().reindex(avg_growth['school'])
    fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=counts), row=2, col=2)
    fig_growth.update_layout(height=700, showlegend=False, font=CHART_FONT, template="plotly_white")
    st.plotly_chart(fig_growth, use_container_width=True)

    with st.expander("생육 데이터 원본 및 XLSX 다운로드"):
        st.dataframe(disp_growth)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            disp_growth.to_excel(writer, index=False)
        st.download_button("XLSX 다운로드", data=buffer.getvalue(), file_name=f"{selected_school}_생육데이터.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
