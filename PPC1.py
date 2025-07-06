#!/usr/bin/env python
# coding: utf-8

# In[1]:


import streamlit as st
import datetime
import io
import pandas as pd
import os
from openai import OpenAI
from browser_history import get_history

# === CONFIG ===
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # Replace with your real token
HISTORY_FILE = "history.csv"

# === Initialize session state ===
if "goals_list" not in st.session_state:
    st.session_state["goals_list"] = []
if "browser_log" not in st.session_state:
    st.session_state["browser_log"] = ""

# === Functions ===
def analyze_day_with_ai(goals, actions, browser_log):
    prompt = f"""
    Цель(и) пользователя: {goals}
    Действия за день: {actions}
    Активность в браузере: {browser_log}

    Проанализируй действия пользователя и оцени, насколько его день был направлен на достижение цели (от 0 до 100).
    Дай 2–3 совета, как улучшить выравнивание действий с целями завтра.
    Формат ответа:
    - Оценка: xx/100
    - Советы:
    """
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content

def get_browser_data():
    outputs = get_history()
    history = outputs.histories[-10:]
    return "\n".join([f"{dt.strftime('%H:%M')} — {url}" for dt, url, *_ in history])

def extract_gpt_score_and_advice(text):
    lines = text.strip().split("\n")
    score_line = next((line for line in lines if "Оценка" in line), "")
    score = ''.join([c for c in score_line if c.isdigit()])
    score = int(score) if score else 0
    advice_lines = "\n".join(lines[1:])
    return score, advice_lines.strip()

def log_to_csv(row):
    columns = ["date", "goal", "actions", "browser", "time_spent", "priority", "gpt_score", "manual_score", "gpt_advice"]
    df = pd.DataFrame([row], columns=columns)
    if os.path.exists(HISTORY_FILE):
        existing = pd.read_csv(HISTORY_FILE)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_csv(HISTORY_FILE, index=False)

# === UI ===
st.set_page_config(page_title="Goal Tracker", page_icon="🎯")
st.title("🎯 Целедостижение ИИ — v0.6")

tab1, tab2, tab3, tab4 = st.tabs(["1. Мои Цели", "2. Что я сделал", "3. Анализ", "📊 Прогресс"])

# === TAB 1: Goal Manager ===
with tab1:
    st.header("🎯 Управление целями")

    with st.form("goal_form"):
        name = st.text_input("Название цели")
        category = st.selectbox("Категория", ["Карьера", "Здоровье", "Обучение", "Отношения", "Финансы", "Другое"])
        priority = st.slider("Приоритет", 1, 10, 7)
        submitted = st.form_submit_button("Добавить цель")
        if submitted and name:
            st.session_state["goals_list"].append({
                "name": name, "category": category, "priority": priority
            })
            st.success("✅ Цель добавлена")

    if st.session_state["goals_list"]:
        st.subheader("Мои цели:")
        for idx, goal in enumerate(st.session_state["goals_list"]):
            st.markdown(f"- **{goal['name']}** ({goal['category']}, приоритет: {goal['priority']})")
            if st.button(f"❌ Удалить", key=f"delete_{idx}"):
                st.session_state["goals_list"].pop(idx)
                st.experimental_rerun()
    else:
        st.info("У вас пока нет целей. Добавьте хотя бы одну.")

# === TAB 2: Daily Actions ===
with tab2:
    st.header("🗓️ Что вы сделали сегодня")

    today = st.date_input("Дата", datetime.date.today())
    actions = st.text_area("Что вы сделали для достижения цели?", height=150)
    time_spent = st.slider("Продуктивные часы", 0, 24, 4)

    goal_names = [g["name"] for g in st.session_state["goals_list"]]
    selected_goal = st.selectbox("📌 Какая цель сегодня в фокусе?", goal_names if goal_names else ["Нет целей"])

    if st.button("Сохранить действия"):
        st.session_state["today"] = today
        st.session_state["actions"] = actions
        st.session_state["selected_goal"] = selected_goal
        st.success("✅ Данные сохранены.")

# === TAB 3: Analysis ===
with tab3:
    st.header("📈 Анализ дня")

    if st.button("📥 Автоматически получить историю браузера"):
        with st.spinner("Собираем данные..."):
            try:
                browser_data = get_browser_data()
                st.session_state["browser_log"] = browser_data
                st.success("📊 История получена")
            except Exception as e:
                st.error(f"Ошибка: {e}")

    manual_browser_log = st.text_area("Или вставьте вручную:", value=st.session_state.get("browser_log", ""), height=100)

    if st.button("🔍 Запустить анализ"):
        with st.spinner("GPT анализирует ваш день..."):
            try:
                goals = st.session_state["selected_goal"]
                actions = st.session_state["actions"]
                today = st.session_state["today"]
                priority = next((g["priority"] for g in st.session_state["goals_list"] if g["name"] == goals), 5)
                ai_result = analyze_day_with_ai(goals, actions, manual_browser_log)
                gpt_score, gpt_advice = extract_gpt_score_and_advice(ai_result)
                manual_score = min(time_spent * 4 + priority * 2, 100)

                st.success("✅ Анализ завершён")
                st.markdown("### 📈 Результаты GPT")
                st.markdown(ai_result)
                st.markdown(f"### 🧮 Ваша оценка: `{manual_score}/100`")

                # Log result
                log_to_csv([
                    today, goals, actions, manual_browser_log,
                    time_spent, priority, gpt_score, manual_score, gpt_advice
                ])

                # Markdown export
                report_md = f"""## 🗓️ {today}
### 🎯 Цель:
{goals}

### ✅ Действия:
{actions}

### 🌐 Браузер:
{manual_browser_log}

### 📈 GPT-анализ:
{ai_result}

### 🧮 Моя оценка:
{manual_score}/100
"""
                st.download_button(
                    label="📥 Скачать отчет (.md)",
                    data=report_md,
                    file_name=f"day_report_{today}.md",
                    mime="text/markdown"
                )
            except Exception as e:
                st.error(f"Ошибка анализа: {e}")

# === TAB 4: Progress ===
with tab4:
    st.header("📊 Прогресс по целям")

    if os.path.exists(HISTORY_FILE):
        df = pd.read_csv(HISTORY_FILE)

        goal_filter = st.selectbox("📂 Фильтр по цели", ["Все"] + sorted(df["goal"].unique().tolist()))
        if goal_filter != "Все":
            df = df[df["goal"] == goal_filter]

        st.line_chart(df[["gpt_score", "manual_score"]])
        st.dataframe(df.tail(30))

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button("📁 Скачать историю (CSV)", csv_buffer.getvalue(), "full_history.csv", "text/csv")
    else:
        st.info("Пока нет данных. Сначала проведите хотя бы один анализ.")


# In[ ]:




