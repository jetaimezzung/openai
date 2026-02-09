import streamlit as st
import requests
import random
from datetime import datetime
import pandas as pd
from openai import OpenAI

# ==================================================
# 기본 설정
# ==================================================
st.set_page_config(
    page_title="AI 습관 트래커",
    page_icon="📊",
    layout="wide"
)

st.title("📊 AI 습관 트래커")

# ==================================================
# Sidebar – API Keys
# ==================================================
st.sidebar.header("🔑 API 설정")

openai_api_key = st.sidebar.text_input(
    "OpenAI API Key",
    type="password",
    placeholder="sk-..."
)

weather_api_key = st.sidebar.text_input(
    "OpenWeatherMap API Key",
    type="password",
    placeholder="OpenWeather API Key"
)

# ==================================================
# Session State 초기화
# ==================================================
if "history" not in st.session_state:
    st.session_state.history = []

# ==================================================
# API Functions
# ==================================================
def get_weather(city, api_key):
    if not api_key:
        return None
    try:
        url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}&appid={api_key}&units=metric&lang=kr"
        )
        res = requests.get(url, timeout=10)
        data = res.json()
        return {
            "temp": data["main"]["temp"],
            "desc": data["weather"][0]["description"]
        }
    except:
        return None


def get_dog_image():
    try:
        res = requests.get(
            "https://dog.ceo/api/breeds/image/random",
            timeout=10
        )
        data = res.json()
        img_url = data["message"]
        breed = img_url.split("/breeds/")[1].split("/")[0].replace("-", " ")
        return img_url, breed
    except:
        return None


def generate_report(habits, mood, weather, breed, style, api_key):
    if not api_key:
        return "❌ OpenAI API Key가 필요합니다."

    system_prompts = {
        "스파르타 코치": "너는 매우 엄격하고 직설적인 코치다.",
        "따뜻한 멘토": "너는 공감 능력이 뛰어난 따뜻한 멘토다.",
        "게임 마스터": "너는 RPG 게임의 퀘스트 마스터다."
    }

    user_prompt = f"""
오늘의 습관 달성 현황: {habits}
기분 점수: {mood}/10
날씨 정보: {weather}
강아지 품종: {breed}

아래 형식으로 리포트를 작성해줘:
- 컨디션 등급 (S~D)
- 습관 분석
- 날씨 코멘트
- 내일 미션
- 오늘의 한마디
"""

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": system_prompts[style]},
            {"role": "user", "content": user_prompt}
        ]
    )

    return response.choices[0].message.content


# ==================================================
# 습관 체크인 UI
# ==================================================
st.subheader("✅ 오늘의 습관 체크인")

col1, col2 = st.columns(2)

with col1:
    wake = st.checkbox("🌅 기상 미션")
    water = st.checkbox("💧 물 마시기")
    study = st.checkbox("📚 공부 / 독서")

with col2:
    workout = st.checkbox("🏃 운동하기")
    sleep = st.checkbox("😴 수면 관리")

habits = {
    "기상": wake,
    "물": water,
    "공부": study,
    "운동": workout,
    "수면": sleep
}

mood = st.slider("😊 오늘 기분 점수", 1, 10, 5)

city = st.selectbox(
    "🌍 도시 선택",
    ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon",
     "Gwangju", "Suwon", "Ulsan", "Jeju", "Sejong"]
)

coach_style = st.radio(
    "🎭 AI 코치 스타일",
    ["스파르타 코치", "따뜻한 멘토", "게임 마스터"]
)

# ==================================================
# 달성률 계산
# ==================================================
completed = sum(habits.values())
achievement = int((completed / 5) * 100)

m1, m2, m3 = st.columns(3)
m1.metric("📈 달성률", f"{achievement}%")
m2.metric("✅ 달성 습관", f"{completed}/5")
m3.metric("😊 기분", f"{mood}/10")

# ==================================================
# 기록 저장
# ==================================================
today_record = {
    "date": datetime.now().strftime("%m/%d"),
    "achievement": achievement
}

if st.button("📌 오늘 기록 저장"):
    st.session_state.history.append(today_record)
    st.success("기록이 저장되었습니다!")

# ==================================================
# 7일 바 차트 (샘플 + 오늘)
# ==================================================
sample_days = ["D-6", "D-5", "D-4", "D-3", "D-2", "D-1"]
sample_data = [random.randint(40, 90) for _ in range(6)]

chart_df = pd.DataFrame({
    "day": sample_days + ["Today"],
    "achievement": sample_data + [achievement]
})

st.subheader("📊 최근 7일 습관 달성률")
st.bar_chart(chart_df.set_index("day"))

# ==================================================
# AI 리포트 생성
# ==================================================
st.subheader("🤖 AI 코치 컨디션 리포트")

if st.button("🧠 컨디션 리포트 생성"):
    weather = get_weather(city, weather_api_key)
    dog = get_dog_image()

    weather_text = (
        f"{weather['temp']}°C, {weather['desc']}"
        if weather else "날씨 정보 없음"
    )

    dog_img, dog_breed = dog if dog else (None, "알 수 없음")

    report = generate_report(
        habits, mood, weather_text, dog_breed,
        coach_style, openai_api_key
    )

    col_w, col_d = st.columns(2)

    with col_w:
        st.markdown("### 🌤 오늘의 날씨")
        st.write(weather_text)

    with col_d:
        st.markdown("### 🐶 오늘의 강아지")
        if dog_img:
            st.image(dog_img, use_column_width=True)
            st.caption(f"품종: {dog_breed}")

    st.markdown("### 📋 AI 리포트")
    st.write(report)

    st.markdown("### 📤 공유용 텍스트")
    st.code(report)

# ==================================================
# API 안내
# ==================================================
with st.expander("ℹ️ API 안내"):
    st.markdown("""
- **OpenAI API**: https://platform.openai.com/
- **OpenWeatherMap**: https://openweathermap.org/api
- **Dog CEO API**: https://dog.ceo/dog-api/
""")
