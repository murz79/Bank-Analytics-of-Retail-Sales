import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from sales_handlers import (
    get_all_managers_rating, get_all_supervisors,
    abc_analysis, forecast_plan_completion, get_monthly_plan_per_employee,
    get_employee_actual_points, get_product_pairs_analysis
)
from database import get_connection
from utils import export_to_excel

def show_analytics_page():
    st.header("📈 Аналитика")

    # Общий выбор месяца и года
    current_year = date.today().year
    current_month = date.today().month
    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input("Год", min_value=2020, max_value=current_year + 1, value=current_year, step=1,
                               key="analytics_year")
    with col2:
        month = st.selectbox("Месяц", range(1, 13), format_func=lambda x: date(year, x, 1).strftime("%B"),
                             index=current_month - 1, key="analytics_month")
    year_month = f"{year}-{month:02d}"

    # Вкладки
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🏆 Рейтинг менеджеров", "📦 ABC-анализ продуктов", "📈 Прогноз выполнения плана", "🔄 Анализ парности продуктов"])

    # ---------- Вкладка 1: Рейтинг менеджеров (без изменений) ----------
    with tab1:
        df_rating = get_all_managers_rating(year_month)
        if df_rating.empty:
            st.info("Нет данных для отображения за выбранный период.")
        else:
            supervisors = get_all_supervisors()
            sup_names = ["Все руководители"] + supervisors['full_name'].tolist()
            selected_sup = st.selectbox("Фильтр по руководителю", sup_names, key="rating_sup_filter")
            if selected_sup != "Все руководители":
                df_rating = df_rating[df_rating['Руководитель'] == selected_sup]

            sort_column = st.selectbox(
                "Сортировать по",
                ["Баллы (факт)", "Выполнение плана (%)", "Конверсия заявок (%)", "Кросс-продажи",
                 "Конверсия доходных продуктов (%)", "Всего заявок"],
                key="rating_sort"
            )
            sort_asc = st.checkbox("По возрастанию", key="rating_asc")
            df_rating = df_rating.sort_values(by=sort_column, ascending=sort_asc)

            st.subheader("Таблица рейтинга")
            st.dataframe(df_rating, use_container_width=True)

            st.subheader("Визуализация")
            chart_type = st.radio(
                "Выберите показатель для графика",
                ["Баллы (факт)", "Выполнение плана (%)", "Конверсия заявок(%)", "Кросс-продажи",
                 "Конверсия доходных продуктов (%)", "Всего заявок"],
                horizontal=True, key="chart_type"
            )
            fig = px.bar(df_rating, x='Менеджер', y=chart_type, color='Руководитель',
                         title=f"{chart_type} по менеджерам", text_auto=True)
            st.plotly_chart(fig, use_container_width=True)

            excel_data = export_to_excel(df_rating, "Рейтинг")
            st.download_button(
                label="📎 Скачать таблицу (Excel)",
                data=excel_data,
                file_name=f"rating_{year_month}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # ---------- Вкладка 2: ABC-анализ продуктов ----------
    with tab2:
        st.subheader("ABC-анализ продуктов (по выручке)")
        df_abc = abc_analysis(year_month)
        if df_abc.empty:
            st.info("За выбранный период нет продаж.")
        else:
            # Цветовая маркировка
            def color_group(val):
                if val == 'A':
                    return 'background-color: #d4edda'
                elif val == 'B':
                    return 'background-color: #fff3cd'
                else:
                    return 'background-color: #f8d7da'

            st.dataframe(df_abc.style.map(color_group, subset=['group']))

            # График
            fig_abc = px.bar(df_abc, x='product', y='revenue', color='group',
                             title=f"ABC-анализ продуктов за {year_month}",
                             labels={'product': 'Продукт', 'revenue': 'Выручка (руб.)'},
                             text='revenue')
            fig_abc.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
            st.plotly_chart(fig_abc, use_container_width=True)

            # Pie chart
            fig_pie = px.pie(df_abc, names='product', values='revenue', title="Доля выручки по продуктам")
            st.plotly_chart(fig_pie, use_container_width=True)

    # ---------- Вкладка 3: Прогноз выполнения плана ----------
    with tab3:
        st.subheader("Прогноз выполнения плана")
        st.caption("Прогноз рассчитывается на основе фактических баллов за прошедшие дни месяца.")

        # Загружаем список менеджеров
        conn = get_connection()
        managers_df = pd.read_sql_query(
            "SELECT id, full_name, supervisor_id FROM users WHERE role='manager' ORDER BY full_name", conn)
        conn.close()

        if managers_df.empty:
            st.warning("Нет менеджеров в системе.")
        else:
            all_forecasts = []
            for _, row in managers_df.iterrows():
                fcast = forecast_plan_completion(row['id'], year_month, row['supervisor_id'])
                if fcast:
                    all_forecasts.append({
                        'Менеджер': row['full_name'],
                        'План': fcast['plan'],
                        'Факт сейчас': fcast['actual_now'],
                        'Прогноз на месяц': round(fcast['projected']),
                        'Текущее выполнение %': round(fcast['actual_percent'], 1),
                        'Прогнозируемое выполнение %': round(fcast['projected_percent'], 1)
                    })
            if all_forecasts:
                df_all = pd.DataFrame(all_forecasts)
                st.dataframe(df_all, use_container_width=True)

                # График прогноза
                fig_forecast = px.bar(df_all, x='Менеджер', y=['Факт сейчас', 'Прогноз на месяц'],
                                      barmode='group', title="Сравнение факта и прогноза")
                st.plotly_chart(fig_forecast, use_container_width=True)

    with tab4:
        st.subheader("Анализ парности продуктов (кросс-продажи)")
        st.caption("Правила ассоциации на основе продаж в рамках одной заявки.")

        # Фильтр по дате (опционально)
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Дата начала (необязательно)", value=None)
        with col2:
            end_date = st.date_input("Дата окончания (необязательно)", value=None)

        min_support = st.slider("Минимальный support (порог частоты)", 0.01, 0.2, 0.02, step=0.01)

        if st.button("Рассчитать парные правила"):
            start = start_date.isoformat() if start_date else None
            end = end_date.isoformat() if end_date else None
            df_pairs = get_product_pairs_analysis(start, end, min_support)
            if df_pairs.empty:
                st.info("Не найдено пар продуктов с заданным support.")
            else:
                st.dataframe(df_pairs)
                st.caption("Интерпретация: lift > 1 – положительная связь, чем выше, тем сильнее.")

                # График: топ-10 пар по lift
                top10 = df_pairs.head(10)
                fig = px.bar(top10, x='product_A', y='lift', color='product_B',
                             title="Топ-10 пар продуктов по силе связи (lift)",
                             labels={'product_A': 'Продукт А', 'lift': 'Lift'})
                st.plotly_chart(fig)
