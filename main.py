# 어제의 박스오피스 — KOBIS 일별 박스오피스 API
import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)


# 인증키는 비밀 금고(secrets)에서 불러온다.
# 코드에 인증키를 직접 쓰지 않는다.
try:
    API_KEY = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error("KOBIS_KEY를 찾을 수 없습니다.")
    st.info(
        "Streamlit Cloud의 Settings → Secrets에서 "
        "KOBIS_KEY를 정확하게 등록했는지 확인해 주세요."
    )
    st.stop()


URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# '어제'를 한국 시간 기준으로 계산한다.
# 배포 서버의 시계가 한국 시간이 아니어도 정확하게 계산된다.
KST = datetime.timezone(datetime.timedelta(hours=9))
yesterday = datetime.datetime.now(KST).date() - datetime.timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")


# 같은 날짜를 다시 조회하면 1시간 동안 저장된 결과를 사용한다.
@st.cache_data(ttl=3600)
def fetch_boxoffice(date_str):
    """KOBIS API에서 해당 날짜의 일별 박스오피스를 받아 온다."""
    params = {
        "key": API_KEY,
        "targetDt": date_str
    }

    res = requests.get(URL, params=params, timeout=10)
    res.raise_for_status()

    return res.json()


st.title("🎬 어제의 박스오피스")
st.caption(f"조회 날짜: {yesterday} (한국 시간 기준 어제)")


# KOBIS API에 요청한다.
try:
    data = fetch_boxoffice(target_dt)

except requests.RequestException as e:
    st.error("KOBIS 서버에 연결하지 못했습니다.")
    st.info(
        "인터넷 연결이나 KOBIS API 서버 상태를 확인하고 "
        "잠시 뒤 새로고침해 주세요."
    )
    st.stop()

except Exception as e:
    st.error("데이터를 불러오는 중 문제가 발생했습니다.")
    st.info(f"오류 내용: {e}")
    st.stop()


# 인증키가 틀리면 상태코드는 200이지만 faultInfo가 온다.
if "faultInfo" in data:
    fault_info = data["faultInfo"]

    error_message = fault_info.get(
        "message",
        "KOBIS API에서 오류가 발생했습니다."
    )

    error_code = fault_info.get(
        "errorCode",
        "알 수 없음"
    )

    st.error(
        f"API가 오류를 돌려주었습니다. "
        f"(오류 코드: {error_code})"
    )
    st.info(
        f"오류 내용: {error_message}\n\n"
        "Streamlit Cloud의 Secrets에서 KOBIS_KEY 값이 "
        "올바르게 입력되어 있는지 확인해 주세요."
    )
    st.stop()


# boxOfficeResult가 없는 경우
if "boxOfficeResult" not in data:
    st.error("KOBIS API 응답에서 박스오피스 결과를 찾을 수 없습니다.")
    st.info(
        "KOBIS API가 정상적으로 응답했는지 확인하고 "
        "잠시 뒤 다시 시도해 주세요."
    )
    st.stop()


# 영화 목록을 가져온다.
movies = data.get("boxOfficeResult", {}).get(
    "dailyBoxOfficeList",
    []
)


# 영화 목록이 비어 있는 경우
if not movies:
    st.warning("영화 목록이 비어 있습니다.")
    st.info(
        "아직 해당 날짜의 박스오피스가 집계되지 않았거나 "
        "KOBIS API에서 데이터를 제공하지 않는 날짜일 수 있습니다."
    )
    st.stop()


# DataFrame으로 변환한다.
df = pd.DataFrame(movies)


# KOBIS에서 숫자가 문자열로 오므로 실제 숫자로 변환한다.
# 이렇게 해야 정렬과 그래프에서 숫자로 제대로 처리된다.
for col in ["rank", "audiCnt", "audiAcc", "scrnCnt"]:
    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    ).fillna(0).astype(int)


# 순위 기준으로 정렬한다.
df = df.sort_values("rank")


# 1위 영화를 지표 카드 세 장으로 크게 보여준다.
top = df.iloc[0]

st.subheader(f"🥇 1위 — {top['movieNm']}")

c1, c2, c3 = st.columns(3)

c1.metric(
    "어제 관객수",
    f"{top['audiCnt']:,}명"
)

c2.metric(
    "누적 관객수",
    f"{top['audiAcc']:,}명"
)

c3.metric(
    "스크린수",
    f"{top['scrnCnt']:,}개"
)


# 전체 순위표
st.subheader("📋 어제의 순위표")

table = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# 표에서 보기 좋게 열 이름을 한국어로 바꾼다.
table.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 숫자에 천 단위 쉼표를 표시한다.
table["관객수"] = table["관객수"].map(lambda x: f"{x:,}")
table["누적관객"] = table["누적관객"].map(lambda x: f"{x:,}")
table["스크린수"] = table["스크린수"].map(lambda x: f"{x:,}")


st.dataframe(
    table,
    hide_index=True,
    use_container_width=True
)


# 관객수 상위 5편을 막대그래프로 보여준다.
st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .copy()
)


fig = px.bar(
    top5,
    x="movieNm",
    y="audiCnt",
    labels={
        "movieNm": "영화명",
        "audiCnt": "어제 관객수"
    },
    title="관객수 상위 5편"
)


st.plotly_chart(
    fig,
    use_container_width=True
)
