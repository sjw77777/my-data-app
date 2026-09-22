import datetime
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="KOBIS 박스오피스", page_icon="🎬", layout="wide")

# 인증키는 Streamlit Cloud Secrets에서 불러옵니다.
try:
    API_KEY = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error("KOBIS_KEY를 찾을 수 없습니다.")
    st.info("Streamlit Cloud의 Settings → Secrets에서 KOBIS_KEY를 등록해 주세요.")
    st.stop()

URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

# 한국 시간 기준 오늘과 어제 날짜를 계산합니다.
KST = datetime.timezone(datetime.timedelta(hours=9))
today = datetime.datetime.now(KST).date()
latest_date = today - datetime.timedelta(days=1)

st.title("🎬 KOBIS 박스오피스")
st.write("달력에서 날짜를 골라 그날의 일일 박스오피스를 확인할 수 있습니다.")

# 오늘은 아직 집계 전이므로 어제까지만 선택할 수 있습니다.
selected_date = st.date_input(
    "📅 조회할 날짜",
    value=latest_date,
    max_value=latest_date,
    format="YYYY-MM-DD"
)

target_dt = selected_date.strftime("%Y%m%d")

# 같은 날짜의 결과는 1시간 동안 캐시합니다.
@st.cache_data(ttl=3600)
def fetch_boxoffice(date_str):
    params = {"key": API_KEY, "targetDt": date_str}
    response = requests.get(URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()

try:
    data = fetch_boxoffice(target_dt)
except requests.RequestException:
    st.error("KOBIS 서버에 연결하지 못했습니다.")
    st.info("인터넷 연결이나 KOBIS API 서버 상태를 확인하고 잠시 뒤 다시 시도해 주세요.")
    st.stop()

# 인증키 오류 등으로 faultInfo가 오는 경우입니다.
if "faultInfo" in data:
    fault_info = data["faultInfo"]
    error_code = fault_info.get("errorCode", "알 수 없음")
    error_message = fault_info.get("message", "KOBIS API에서 오류가 발생했습니다.")
    st.error(f"API가 오류를 돌려주었습니다. (오류 코드: {error_code})")
    st.info(
        f"오류 내용: {error_message}\n\n"
        "Streamlit Cloud Secrets의 KOBIS_KEY가 올바른지 확인해 주세요."
    )
    st.stop()

if "boxOfficeResult" not in data:
    st.error("KOBIS API 응답에서 박스오피스 결과를 찾을 수 없습니다.")
    st.info("KOBIS API가 정상적으로 응답했는지 확인해 주세요.")
    st.stop()

movies = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])

# 선택한 날짜에 영화 목록이 없으면 집계 전이라고 안내합니다.
if not movies:
    st.warning("영화 목록이 없습니다.")
    st.info("그날은 아직 집계 전입니다.")
    st.stop()

df = pd.DataFrame(movies)

# KOBIS에서 문자열로 오는 숫자를 실제 숫자로 변환합니다.
for col in ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

df = df.sort_values("rank")

# 1위 영화
top = df.iloc[0]
st.subheader(f"🥇 1위 — {top['movieNm']}")

c1, c2, c3 = st.columns(3)
c1.metric("관객수", f"{top['audiCnt']:,}명")
c2.metric("누적 관객수", f"{top['audiAcc']:,}명")
c3.metric("스크린수", f"{top['scrnCnt']:,}개")

# 전체 순위표
st.subheader("📋 박스오피스 순위")

table = df[["rank", "rankInten", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()

# 전날 대비 순위 변동을 표시합니다.
# 양수 = 순위 상승(빨간 위 화살표), 음수 = 순위 하락(파란 아래 화살표)
def make_rank_change(value):
    if value > 0:
        return f"↑ {value}"
    if value < 0:
        return f"↓ {abs(value)}"
    return "―"

table["순위"] = table["rank"].astype(str)
table["순위 변동"] = table["rankInten"].apply(make_rank_change)

# 누적관객이 100만 명 이상이면 트로피를 붙입니다.
table["영화명"] = table.apply(
    lambda row: f"🏆 {row['movieNm']}" if row["audiAcc"] >= 1_000_000 else row["movieNm"],
    axis=1
)

table["관객수"] = table["audiCnt"].map(lambda x: f"{x:,}")
table["누적관객"] = table["audiAcc"].map(lambda x: f"{x:,}")
table["스크린수"] = table["scrnCnt"].map(lambda x: f"{x:,}")

table = table[["순위", "순위 변동", "영화명", "openDt", "관객수", "누적관객", "스크린수"]]
table.columns = ["순위", "순위 변동", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

# 상승 화살표는 빨간색, 하락 화살표는 파란색으로 표시합니다.
def color_rank_change(value):
    if str(value).startswith("↑"):
        return "color: red; font-weight: bold"
    if str(value).startswith("↓"):
        return "color: blue; font-weight: bold"
    return "color: gray"

styled_table = table.style.map(color_rank_change, subset=["순위 변동"])

st.dataframe(styled_table, hide_index=True, use_container_width=True)

# 관객수 상위 5편
st.subheader("📊 관객수 상위 5편")
top5 = df.sort_values("audiCnt", ascending=False).head(5)

fig = px.bar(
    top5,
    x="movieNm",
    y="audiCnt",
    labels={"movieNm": "영화명", "audiCnt": "관객수"},
    title=f"{selected_date} 관객수 상위 5편"
)

st.plotly_chart(fig, use_container_width=True)
