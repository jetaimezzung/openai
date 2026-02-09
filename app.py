import streamlit as st
import requests
from datetime import datetime, date, timedelta
import pandas as pd
from openai import OpenAI
import sqlite3
import os
import calendar

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
# Database 초기화
# ==================================================
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "habits.db")


def get_db_connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS habits (
                date TEXT PRIMARY KEY,
                habit_wake INTEGER NOT NULL,
                habit_water INTEGER NOT NULL,
                habit_study INTEGER NOT NULL,
                habit_workout INTEGER NOT NULL,
                habit_sleep INTEGER NOT NULL,
                mood INTEGER NOT NULL,
                achievement INTEGER NOT NULL
            )
            """
        )


def fetch_record(record_date):
    with get_db_connection() as conn:
        cur = conn.execute(
            """
            SELECT date, habit_wake, habit_water, habit_study,
                   habit_workout, habit_sleep, mood, achievement
            FROM habits
            WHERE date = ?
            """,
            (record_date,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "date": row[0],
            "habit_wake": bool(row[1]),
            "habit_water": bool(row[2]),
            "habit_study": bool(row[3]),
            "habit_workout": bool(row[4]),
            "habit_sleep": bool(row[5]),
            "mood": row[6],
            "achievement": row[7]
        }


def upsert_record(record):
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO habits (
                date, habit_wake, habit_water, habit_study,
                habit_workout, habit_sleep, mood, achievement
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                habit_wake=excluded.habit_wake,
                habit_water=excluded.habit_water,
                habit_study=excluded.habit_study,
                habit_workout=excluded.habit_workout,
                habit_sleep=excluded.habit_sleep,
                mood=excluded.mood,
                achievement=excluded.achievement
            """,
            (
                record["date"],
                int(record["habit_wake"]),
                int(record["habit_water"]),
                int(record["habit_study"]),
                int(record["habit_workout"]),
                int(record["habit_sleep"]),
                record["mood"],
                record["achievement"]
            )
        )


def delete_record(record_date):
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM habits WHERE date = ?",
            (record_date,)
        )


def fetch_records_for_month(year, month):
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    with get_db_connection() as conn:
        cur = conn.execute(
            """
            SELECT date, achievement
            FROM habits
            WHERE date >= ? AND date < ?
            """,
            (start_date.isoformat(), end_date.isoformat())
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def fetch_records_for_dates(dates):
    with get_db_connection() as conn:
        cur = conn.execute(
            f"""
            SELECT date, achievement
            FROM habits
            WHERE date IN ({",".join("?" * len(dates))})
            """,
            dates
        )
        return {row[0]: row[1] for row in cur.fetchall()}

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

init_db()
today_iso = date.today().isoformat()
today_saved = fetch_record(today_iso) or {}

col1, col2 = st.columns(2)

with col1:
    wake = st.checkbox("🌅 기상 미션", value=today_saved.get("habit_wake", False))
    water = st.checkbox("💧 물 마시기", value=today_saved.get("habit_water", False))
    study = st.checkbox("📚 공부 / 독서", value=today_saved.get("habit_study", False))

with col2:
    workout = st.checkbox("🏃 운동하기", value=today_saved.get("habit_workout", False))
    sleep = st.checkbox("😴 수면 관리", value=today_saved.get("habit_sleep", False))

habits = {
    "기상": wake,
    "물": water,
    "공부": study,
    "운동": workout,
    "수면": sleep
}

mood = st.slider("😊 오늘 기분 점수", 1, 10, today_saved.get("mood", 5))

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
    "date": today_iso,
    "habit_wake": wake,
    "habit_water": water,
    "habit_study": study,
    "habit_workout": workout,
    "habit_sleep": sleep,
    "mood": mood,
    "achievement": achievement
}

if st.button("📌 오늘 기록 저장"):
    upsert_record(today_record)
    st.success("기록이 저장되었습니다!")

# ==================================================
# 7일 바 차트
# ==================================================
recent_dates = [
    (date.today() - timedelta(days=offset)).isoformat()
    for offset in range(6, -1, -1)
]
recent_records = fetch_records_for_dates(recent_dates)
chart_df = pd.DataFrame({
    "day": [datetime.fromisoformat(d).strftime("%m/%d") for d in recent_dates],
    "achievement": [recent_records.get(d, 0) for d in recent_dates]
})

st.subheader("📊 최근 7일 습관 달성률")
st.bar_chart(chart_df.set_index("day"))

# ==================================================
# 달력 + 상세 패널
# ==================================================
st.subheader("🗓️ 월간 체크 달력")

calendar_col, detail_col = st.columns([2, 1])

with calendar_col:
    month_picker = st.date_input("달력 월 선택", date.today())
    month_records = fetch_records_for_month(month_picker.year, month_picker.month)
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(month_picker.year, month_picker.month)
    week_rows = []
    for week in month_days:
        row = {}
        for idx, day_num in enumerate(week):
            label = ""
            if day_num != 0:
                day_date = date(month_picker.year, month_picker.month, day_num).isoformat()
                has_record = day_date in month_records
                label = f"{day_num}"
                if has_record:
                    label = f"{label} ✅"
            row[calendar.day_abbr[idx]] = label
        week_rows.append(row)
    calendar_df = pd.DataFrame(week_rows)
    st.data_editor(
        calendar_df,
        hide_index=True,
        disabled=True,
        width="stretch"
    )

with detail_col:
    st.markdown("### 📋 선택한 날짜 기록")
    selected_date = st.date_input("기록 날짜 선택", date.today(), key="detail_date")
    selected_iso = selected_date.isoformat()
    selected_record = fetch_record(selected_iso)

    with st.form("detail_form"):
        detail_wake = st.checkbox(
            "🌅 기상 미션",
            value=bool(selected_record and selected_record["habit_wake"]),
            key="detail_wake"
        )
        detail_water = st.checkbox(
            "💧 물 마시기",
            value=bool(selected_record and selected_record["habit_water"]),
            key="detail_water"
        )
        detail_study = st.checkbox(
            "📚 공부 / 독서",
            value=bool(selected_record and selected_record["habit_study"]),
            key="detail_study"
        )
        detail_workout = st.checkbox(
            "🏃 운동하기",
            value=bool(selected_record and selected_record["habit_workout"]),
            key="detail_workout"
        )
        detail_sleep = st.checkbox(
            "😴 수면 관리",
            value=bool(selected_record and selected_record["habit_sleep"]),
            key="detail_sleep"
        )
        detail_mood = st.slider(
            "😊 기분 점수",
            1,
            10,
            int(selected_record["mood"]) if selected_record else 5,
            key="detail_mood"
        )
        detail_completed = sum(
            [
                detail_wake,
                detail_water,
                detail_study,
                detail_workout,
                detail_sleep
            ]
        )
        detail_achievement = int((detail_completed / 5) * 100)
        st.caption(f"달성률: {detail_achievement}%")
        submitted = st.form_submit_button("💾 기록 수정 저장")

    if submitted:
        upsert_record(
            {
                "date": selected_iso,
                "habit_wake": detail_wake,
                "habit_water": detail_water,
                "habit_study": detail_study,
                "habit_workout": detail_workout,
                "habit_sleep": detail_sleep,
                "mood": detail_mood,
                "achievement": detail_achievement
            }
        )
        st.success("기록이 저장되었습니다!")

    if st.button("🗑️ 기록 삭제", type="secondary"):
        delete_record(selected_iso)
        st.warning("기록이 삭제되었습니다.")

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
