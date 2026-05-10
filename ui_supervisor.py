import streamlit as st
from datetime import date, datetime, timedelta
import plotly.express as px
from sales_handlers import (
    get_supervisor_group_sales,
    get_monthly_plan_per_employee,
    set_monthly_plan_per_employee,
    get_employee_count_in_group,
    get_group_plan_points,
    get_group_actual_points,
    get_employees_with_points
)


def show_supervisor_page():
    st.sidebar.title(f"Руководитель: {st.session_state.full_name}")
    menu = st.sidebar.radio("Меню", [
        "📊 Продажи группы",
        "🎯 План продаж",
        "👥 Мои сотрудники",
        "📈 Аналитика"
    ])

    if menu == "📊 Продажи группы":
        st.header("Продажи сотрудников группы")
        start_date = st.date_input("С даты", value=date.today() - timedelta(days=30))
        end_date = st.date_input("По дату", value=date.today())
        if st.button("Показать"):
            df = get_supervisor_group_sales(st.session_state.user_id, start_date.isoformat(), end_date.isoformat())
            if not df.empty:
                st.dataframe(df)
                total = df['revenue'].sum()
                st.metric("Общая выручка группы", f"{total:,.0f}")
                fig = px.bar(df, x='sale_date', y='revenue', color='manager', title="Выручка по менеджерам")
                st.plotly_chart(fig)
            else:
                st.info("Нет продаж за период")

    elif menu == "🎯 План продаж":
        st.header("🎯 Установка плана продаж (в баллах на одного сотрудника)")

        current_year = date.today().year
        current_month = date.today().month

        col1, col2 = st.columns(2)
        with col1:
            year = st.number_input("Год", min_value=2020, max_value=current_year + 1, value=current_year, step=1)
        with col2:
            month = st.selectbox("Месяц", options=range(1, 13),
                                 format_func=lambda x: datetime(year, x, 1).strftime("%B"), index=current_month - 1)

        year_month = f"{year}-{month:02d}"

        plan_per_employee = get_monthly_plan_per_employee(st.session_state.user_id, year_month)
        emp_count = get_employee_count_in_group(st.session_state.user_id)
        group_plan = get_group_plan_points(st.session_state.user_id, year_month)
        group_actual = get_group_actual_points(st.session_state.user_id, year_month)

        st.subheader("📊 Текущие показатели")
        if plan_per_employee is not None:
            st.info(f"📌 План на одного сотрудника: {plan_per_employee:.0f} баллов")
            st.info(f"👥 Количество сотрудников в группе: {emp_count}")
            st.metric("🎯 План группы", f"{group_plan:.0f} баллов" if group_plan else "Не установлен")
            st.metric("⭐ Факт группы", f"{group_actual:.0f} баллов")
            if group_plan and group_plan > 0:
                percent_group = (group_actual / group_plan) * 100
                st.progress(min(percent_group / 100, 1.0))
                st.caption(f"Выполнение плана группы: {percent_group:.1f}%")
        else:
            st.warning(f"План на {year_month} ещё не установлен")

        st.divider()

        with st.form("set_plan_form"):
            new_plan = st.number_input("План на одного сотрудника (в баллах)", min_value=0.0, step=100.0, format="%.0f")
            submitted = st.form_submit_button("✅ Установить план")
            if submitted:
                set_monthly_plan_per_employee(st.session_state.user_id, year_month, new_plan)
                st.success(f"План на {year_month} установлен: {new_plan:.0f} баллов на сотрудника")
                st.rerun()

    elif menu == "📈 Аналитика":
        from ui_analytics import show_analytics_page  # импорт внутри функции
        show_analytics_page()

    else:  # Мои сотрудники
        st.header("👥 Мои сотрудники: выполнение плана")

        current_year = date.today().year
        current_month = date.today().month

        col1, col2 = st.columns(2)
        with col1:
            year = st.number_input("Год", min_value=2020, max_value=current_year + 1, value=current_year, step=1,
                                   key="emp_year")
        with col2:
            month = st.selectbox("Месяц", options=range(1, 13),
                                 format_func=lambda x: datetime(year, x, 1).strftime("%B"), index=current_month - 1,
                                 key="emp_month")

        year_month = f"{year}-{month:02d}"

        df = get_employees_with_points(st.session_state.user_id, year_month)
        if df.empty:
            st.warning("У вас пока нет закреплённых сотрудников.")
        else:
            st.dataframe(df[['ФИО', 'Логин', 'План (баллы)', 'Факт (баллы)', 'Выполнение %']], use_container_width=True)

            # График выполнения
            # Если план установлен, строим диаграмму только для тех, у кого он есть
            if 'Выполнение %' in df.columns and df['Выполнение %'].dtype in ['float64', 'int64']:
                fig = px.bar(df, x='ФИО', y='Выполнение %', title="Выполнение плана сотрудниками (%)",
                             text='Выполнение %')
                fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig.update_layout(yaxis_title="Выполнение (%)", xaxis_title="Сотрудник")
                st.plotly_chart(fig, use_container_width=True)

            st.subheader("📋 Полная детализация")
            st.dataframe(df, use_container_width=True)

