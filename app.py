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
    page_title="AI 스터디 트래커",
    page_icon="📚",
    layout="wide"
)

st.title("📚 AI 스터디 트래커")

st.markdown(
    """
    <style>
        .study-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 16px;
            border-radius: 12px;
        }
        .study-highlight {
            background: linear-gradient(90deg, #f97316, #facc15);
            color: #0f172a;
            padding: 6px 12px;
            border-radius: 999px;
            font-weight: 600;
            display: inline-block;
        }
    </style>
    """,
    unsafe_allow_html=True
)

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
DB_PATH = os.path.join(DATA_DIR, "study.db")


def get_db_connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_records (
                date TEXT PRIMARY KEY,
                task_plan INTEGER NOT NULL,
                task_deep_focus INTEGER NOT NULL,
                task_review INTEGER NOT NULL,
                task_practice INTEGER NOT NULL,
                task_reading INTEGER NOT NULL,
                task_summary INTEGER NOT NULL,
                focus_minutes INTEGER NOT NULL,
                break_minutes INTEGER NOT NULL,
                sessions INTEGER NOT NULL,
                focus_score INTEGER NOT NULL,
                mood INTEGER NOT NULL,
                energy INTEGER NOT NULL,
                achievement INTEGER NOT NULL,
                subjects TEXT NOT NULL,
                notes TEXT NOT NULL
            )
            """
        )


def fetch_record(record_date):
    with get_db_connection() as conn:
        cur = conn.execute(
            """
            SELECT date, task_plan, task_deep_focus, task_review,
                   task_practice, task_reading, task_summary,
                   focus_minutes, break_minutes, sessions,
                   focus_score, mood, energy, achievement,
                   subjects, notes
            FROM study_records
            WHERE date = ?
            """,
            (record_date,)
        )
        row = cur.fetchone()
        if not row:
            return None
        subjects = [s for s in row[14].split(",") if s] if row[14] else []
        return {
            "date": row[0],
            "task_plan": bool(row[1]),
            "task_deep_focus": bool(row[2]),
            "task_review": bool(row[3]),
            "task_practice": bool(row[4]),
            "task_reading": bool(row[5]),
            "task_summary": bool(row[6]),
            "focus_minutes": row[7],
            "break_minutes": row[8],
            "sessions": row[9],
            "focus_score": row[10],
            "mood": row[11],
            "energy": row[12],
            "achievement": row[13],
            "subjects": subjects,
            "notes": row[15]
        }


def upsert_record(record):
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO study_records (
                date, task_plan, task_deep_focus, task_review,
                task_practice, task_reading, task_summary,
                focus_minutes, break_minutes, sessions,
                focus_score, mood, energy, achievement,
                subjects, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                task_plan=excluded.task_plan,
                task_deep_focus=excluded.task_deep_focus,
                task_review=excluded.task_review,
                task_practice=excluded.task_practice,
                task_reading=excluded.task_reading,
                task_summary=excluded.task_summary,
                focus_minutes=excluded.focus_minutes,
                break_minutes=excluded.break_minutes,
                sessions=excluded.sessions,
                focus_score=excluded.focus_score,
                mood=excluded.mood,
                energy=excluded.energy,
                achievement=excluded.achievement,
                subjects=excluded.subjects,
                notes=excluded.notes
            """,
            (
                record["date"],
                int(record["task_plan"]),
                int(record["task_deep_focus"]),
                int(record["task_review"]),
                int(record["task_practice"]),
                int(record["task_reading"]),
                int(record["task_summary"]),
                record["focus_minutes"],
                record["break_minutes"],
                record["sessions"],
                record["focus_score"],
                record["mood"],
                record["energy"],
                record["achievement"],
                ",".join(record["subjects"]),
                record["notes"]
            )
        )


def delete_record(record_date):
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM study_records WHERE date = ?",
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
            FROM study_records
            WHERE date >= ? AND date < ?
            """,
            (start_date.isoformat(), end_date.isoformat())
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def fetch_records_for_dates(dates):
    if not dates:
        return {}
    with get_db_connection() as conn:
        cur = conn.execute(
            f"""
            SELECT date, achievement, focus_minutes, sessions
            FROM study_records
            WHERE date IN ({",".join("?" * len(dates))})
            """,
            dates
        )
        return {
            row[0]: {
                "achievement": row[1],
                "focus_minutes": row[2],
                "sessions": row[3]
            }
            for row in cur.fetchall()
        }


def fetch_focus_data_since(start_date):
    with get_db_connection() as conn:
        cur = conn.execute(
            """
            SELECT date, focus_minutes
            FROM study_records
            WHERE date >= ?
            ORDER BY date DESC
            """,
            (start_date,)
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


def generate_report(study_data, weather, pet, style, api_key):
    if not api_key:
        return "❌ OpenAI API Key가 필요합니다."

    system_prompts = {
        "스파르타 코치": "너는 매우 엄격하고 직설적인 스터디 코치다.",
        "따뜻한 멘토": "너는 공감 능력이 뛰어난 따뜻한 스터디 멘토다.",
        "게임 마스터": "너는 RPG 게임의 퀘스트 마스터처럼 스터디 미션을 준다."
    }

    user_prompt = f"""
오늘의 스터디 기록: {study_data}
날씨 정보: {weather}
펫 캐릭터: {pet}

아래 형식으로 리포트를 작성해줘:
- 집중 컨디션 등급 (S~D)
- 학습 분석
- 날씨 코멘트
- 내일 미션 2개
- 오늘의 한마디 (20자 이내)
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
# 스터디 체크인 UI
# ==================================================
st.subheader("✅ 오늘의 스터디 체크인")

init_db()
today_iso = date.today().isoformat()
today_saved = fetch_record(today_iso) or {}

st.markdown(
    '<span class="study-highlight">오늘의 스터디 모드: 집중과 회복을 균형 있게!</span>',
    unsafe_allow_html=True
)

st.markdown("### 🧭 핵심 학습 미션")
mission_col1, mission_col2, mission_col3 = st.columns(3)

with mission_col1:
    task_plan = st.checkbox("🗺️ 계획 세우기", value=today_saved.get("task_plan", False))
    task_deep_focus = st.checkbox("🎯 딥 포커스", value=today_saved.get("task_deep_focus", False))

with mission_col2:
    task_review = st.checkbox("🔁 복습", value=today_saved.get("task_review", False))
    task_practice = st.checkbox("🧪 문제 풀이", value=today_saved.get("task_practice", False))

with mission_col3:
    task_reading = st.checkbox("📖 읽기", value=today_saved.get("task_reading", False))
    task_summary = st.checkbox("🧠 개념 정리", value=today_saved.get("task_summary", False))

task_values = [
    task_plan,
    task_deep_focus,
    task_review,
    task_practice,
    task_reading,
    task_summary
]

st.markdown("### ⏱️ 집중 루틴")
routine_col1, routine_col2, routine_col3 = st.columns(3)
with routine_col1:
    focus_minutes = st.slider(
        "집중 시간 (분)",
        0,
        360,
        int(today_saved.get("focus_minutes", 90)),
        step=10
    )
with routine_col2:
    sessions = st.number_input(
        "포모도로 세션 수",
        min_value=0,
        max_value=12,
        value=int(today_saved.get("sessions", 3))
    )
with routine_col3:
    break_minutes = st.slider(
        "휴식 시간 (분)",
        0,
        120,
        int(today_saved.get("break_minutes", 30)),
        step=5
    )

subjects_options = [
    "국어",
    "수학",
    "영어",
    "과학",
    "사회",
    "코딩",
    "자격증",
    "독서",
    "기타"
]
subjects = st.multiselect(
    "📌 오늘 공부한 영역",
    subjects_options,
    default=today_saved.get("subjects", [])
)

notes = st.text_area(
    "📝 학습 메모",
    value=today_saved.get("notes", ""),
    placeholder="핵심 개념, 내일 할 일, 막힌 부분을 적어보세요."
)

mood = st.slider("😊 오늘 기분 점수", 1, 10, int(today_saved.get("mood", 6)))
energy = st.slider("🔋 에너지 레벨", 1, 10, int(today_saved.get("energy", 6)))
focus_score = st.slider("🎯 집중도 점수", 1, 10, int(today_saved.get("focus_score", 6)))

city = st.selectbox(
    "🌍 도시 선택",
    ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon",
     "Gwangju", "Suwon", "Ulsan", "Jeju", "Sejong"]
)

coach_style = st.radio(
    "🎭 AI 코치 스타일",
    ["스파르타 코치", "따뜻한 멘토", "게임 마스터"]
)

st.sidebar.header("🎯 스터디 목표")
daily_target_minutes = st.sidebar.number_input(
    "하루 목표 집중 시간 (분)",
    min_value=30,
    max_value=600,
    value=120,
    step=10
)
weekly_target_sessions = st.sidebar.number_input(
    "주간 포모도로 목표",
    min_value=5,
    max_value=60,
    value=20,
    step=1
)

# ==================================================
# 달성률 계산
# ==================================================
task_score = (sum(task_values) / len(task_values)) * 40
time_score = min(focus_minutes / daily_target_minutes, 1) * 50
focus_score_component = (focus_score / 10) * 10
achievement = int(task_score + time_score + focus_score_component)

today_cards = st.columns(4)
today_cards[0].metric("🎯 학습 달성률", f"{achievement}%")
today_cards[1].metric("⏱️ 집중 시간", f"{focus_minutes}분")
today_cards[2].metric("🧩 포모도로", f"{sessions}회")
today_cards[3].metric("🔋 에너지", f"{energy}/10")

# ==================================================
# 기록 저장
# ==================================================
today_record = {
    "date": today_iso,
    "task_plan": task_plan,
    "task_deep_focus": task_deep_focus,
    "task_review": task_review,
    "task_practice": task_practice,
    "task_reading": task_reading,
    "task_summary": task_summary,
    "focus_minutes": focus_minutes,
    "break_minutes": break_minutes,
    "sessions": sessions,
    "focus_score": focus_score,
    "mood": mood,
    "energy": energy,
    "achievement": achievement,
    "subjects": subjects,
    "notes": notes
}

if st.button("📌 오늘 기록 저장"):
    upsert_record(today_record)
    st.success("기록이 저장되었습니다!")

# ==================================================
# 7일 차트
# ==================================================
recent_dates = [
    (date.today() - timedelta(days=offset)).isoformat()
    for offset in range(6, -1, -1)
]
recent_records = fetch_records_for_dates(recent_dates)
chart_df = pd.DataFrame({
    "day": [datetime.fromisoformat(d).strftime("%m/%d") for d in recent_dates],
    "achievement": [recent_records.get(d, {}).get("achievement", 0) for d in recent_dates],
    "focus_minutes": [recent_records.get(d, {}).get("focus_minutes", 0) for d in recent_dates],
    "sessions": [recent_records.get(d, {}).get("sessions", 0) for d in recent_dates]
})

st.subheader("📊 최근 7일 스터디 리듬")
chart_cols = st.columns(2)
with chart_cols[0]:
    st.markdown("**달성률 추이**")
    st.bar_chart(chart_df.set_index("day")[["achievement"]])
with chart_cols[1]:
    st.markdown("**집중 시간 추이**")
    st.line_chart(chart_df.set_index("day")[["focus_minutes"]])

st.markdown("### 🧭 주간 목표 진행도")
weekly_focus = chart_df["focus_minutes"].sum()
weekly_sessions = chart_df["sessions"].sum()
week_cols = st.columns(3)
week_cols[0].metric("주간 집중 시간", f"{weekly_focus}분")
week_cols[1].metric("주간 포모도로", f"{weekly_sessions}회")
week_cols[2].metric("포모도로 목표", f"{weekly_target_sessions}회")

st.markdown("### 🔥 집중 스트릭")
streak_threshold = max(int(daily_target_minutes * 0.6), 1)
lookback_days = 60
focus_map = fetch_focus_data_since(
    (date.today() - timedelta(days=lookback_days)).isoformat()
)
current_streak = 0
for offset in range(0, lookback_days):
    day = (date.today() - timedelta(days=offset)).isoformat()
    minutes = focus_map.get(day, 0)
    if minutes >= streak_threshold:
        current_streak += 1
    else:
        break

best_streak = 0
running = 0
for offset in range(lookback_days, -1, -1):
    day = (date.today() - timedelta(days=offset)).isoformat()
    minutes = focus_map.get(day, 0)
    if minutes >= streak_threshold:
        running += 1
        best_streak = max(best_streak, running)
    else:
        running = 0

streak_cols = st.columns(2)
streak_cols[0].metric("현재 스트릭", f"{current_streak}일")
streak_cols[1].metric("베스트 스트릭(최근 60일)", f"{best_streak}일")

# ==================================================
# 달력 + 상세 패널
# ==================================================
st.subheader("🗓️ 월간 스터디 달력")

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
        detail_task_plan = st.checkbox(
            "🗺️ 계획 세우기",
            value=bool(selected_record and selected_record["task_plan"]),
            key="detail_task_plan"
        )
        detail_task_deep_focus = st.checkbox(
            "🎯 딥 포커스",
            value=bool(selected_record and selected_record["task_deep_focus"]),
            key="detail_task_deep_focus"
        )
        detail_task_review = st.checkbox(
            "🔁 복습",
            value=bool(selected_record and selected_record["task_review"]),
            key="detail_task_review"
        )
        detail_task_practice = st.checkbox(
            "🧪 문제 풀이",
            value=bool(selected_record and selected_record["task_practice"]),
            key="detail_task_practice"
        )
        detail_task_reading = st.checkbox(
            "📖 읽기",
            value=bool(selected_record and selected_record["task_reading"]),
            key="detail_task_reading"
        )
        detail_task_summary = st.checkbox(
            "🧠 개념 정리",
            value=bool(selected_record and selected_record["task_summary"]),
            key="detail_task_summary"
        )
        detail_focus_minutes = st.slider(
            "집중 시간 (분)",
            0,
            360,
            int(selected_record["focus_minutes"]) if selected_record else 90,
            step=10,
            key="detail_focus_minutes"
        )
        detail_sessions = st.number_input(
            "포모도로 세션 수",
            min_value=0,
            max_value=12,
            value=int(selected_record["sessions"]) if selected_record else 3,
            key="detail_sessions"
        )
        detail_break_minutes = st.slider(
            "휴식 시간 (분)",
            0,
            120,
            int(selected_record["break_minutes"]) if selected_record else 30,
            step=5,
            key="detail_break_minutes"
        )
        detail_focus_score = st.slider(
            "🎯 집중도 점수",
            1,
            10,
            int(selected_record["focus_score"]) if selected_record else 6,
            key="detail_focus_score"
        )
        detail_mood = st.slider(
            "😊 기분 점수",
            1,
            10,
            int(selected_record["mood"]) if selected_record else 6,
            key="detail_mood"
        )
        detail_energy = st.slider(
            "🔋 에너지 레벨",
            1,
            10,
            int(selected_record["energy"]) if selected_record else 6,
            key="detail_energy"
        )
        detail_subjects = st.multiselect(
            "📌 오늘 공부한 영역",
            subjects_options,
            default=selected_record["subjects"] if selected_record else [],
            key="detail_subjects"
        )
        detail_notes = st.text_area(
            "📝 학습 메모",
            value=selected_record["notes"] if selected_record else "",
            key="detail_notes"
        )
        detail_task_values = [
            detail_task_plan,
            detail_task_deep_focus,
            detail_task_review,
            detail_task_practice,
            detail_task_reading,
            detail_task_summary
        ]
        detail_task_score = (sum(detail_task_values) / len(detail_task_values)) * 40
        detail_time_score = min(detail_focus_minutes / daily_target_minutes, 1) * 50
        detail_focus_component = (detail_focus_score / 10) * 10
        detail_achievement = int(detail_task_score + detail_time_score + detail_focus_component)
        st.caption(f"달성률: {detail_achievement}%")
        submitted = st.form_submit_button("💾 기록 수정 저장")

    if submitted:
        upsert_record(
            {
                "date": selected_iso,
                "task_plan": detail_task_plan,
                "task_deep_focus": detail_task_deep_focus,
                "task_review": detail_task_review,
                "task_practice": detail_task_practice,
                "task_reading": detail_task_reading,
                "task_summary": detail_task_summary,
                "focus_minutes": detail_focus_minutes,
                "break_minutes": detail_break_minutes,
                "sessions": detail_sessions,
                "focus_score": detail_focus_score,
                "mood": detail_mood,
                "energy": detail_energy,
                "achievement": detail_achievement,
                "subjects": detail_subjects,
                "notes": detail_notes
            }
        )
        st.success("기록이 저장되었습니다!")

    if st.button("🗑️ 기록 삭제", type="secondary"):
        delete_record(selected_iso)
        st.warning("기록이 삭제되었습니다.")

# ==================================================
# 오늘의 요약 카드
# ==================================================
st.subheader("✨ 오늘의 스터디 요약")
summary_cols = st.columns(2)
with summary_cols[0]:
    st.markdown(
        f"""
        <div class="study-card">
            <h4>오늘의 하이라이트</h4>
            <p>집중 시간 <strong>{focus_minutes}분</strong>, 포모도로 <strong>{sessions}회</strong></p>
            <p>완료 미션 <strong>{sum(task_values)}/{len(task_values)}</strong></p>
        </div>
        """,
        unsafe_allow_html=True
    )
with summary_cols[1]:
    st.markdown(
        f"""
        <div class="study-card">
            <h4>학습 메모</h4>
            <p>{notes if notes else "오늘의 메모를 남겨보세요."}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# ==================================================
# AI 리포트 생성
# ==================================================
st.subheader("🤖 AI 코치 스터디 리포트")

if st.button("🧠 컨디션 리포트 생성"):
    weather = get_weather(city, weather_api_key)
    dog = get_dog_image()

    weather_text = (
        f"{weather['temp']}°C, {weather['desc']}"
        if weather else "날씨 정보 없음"
    )

    dog_img, dog_breed = dog if dog else (None, "알 수 없음")
    study_data = {
        "tasks": {
            "계획": task_plan,
            "딥 포커스": task_deep_focus,
            "복습": task_review,
            "문제풀이": task_practice,
            "읽기": task_reading,
            "개념정리": task_summary
        },
        "focus_minutes": focus_minutes,
        "break_minutes": break_minutes,
        "sessions": sessions,
        "focus_score": focus_score,
        "mood": mood,
        "energy": energy,
        "subjects": subjects,
        "notes": notes,
        "achievement": achievement
    }

    report = generate_report(
        study_data, weather_text, dog_breed,
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
