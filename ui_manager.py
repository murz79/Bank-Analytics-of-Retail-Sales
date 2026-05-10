import os

import streamlit as st
import plotly.express as px
from sales_handlers import (
    add_sale_with_request, get_manager_sales,
    create_request, get_active_requests, get_closed_requests,
    cancel_request,
    get_today_sales_with_points,
    get_today_successful_clients,
    get_today_cancelled_clients,
    get_today_requests_count,
    get_today_cross_sales,
    get_employee_actual_points,
    get_monthly_plan_per_employee,
    get_products_by_ids, create_request_with_client
)
from products_handlers import get_all_products
from utils import export_to_excel
import pyperclip
from datetime import date, timedelta, datetime
from database import get_connection
import pandas as pd


def show_manager_page():
    st.sidebar.title(f"Менеджер: {st.session_state.full_name}")
    menu = st.sidebar.radio("Меню", [
        "➕ Добавить продажу",
        "📋 Мои продажи",
        "📄 Отчет за сегодня",
        "📝 Заявки клиентов",
        "🎯 План продаж",
        "💡 Рекомендации"
    ])

    if menu == "➕ Добавить продажу":
        st.header("Быстрое добавление продажи")
        products_df = get_all_products()
        if products_df.empty:
            st.warning("Нет продуктов. Обратитесь к администратору.")
            return

        if 'product_qty' not in st.session_state:
            st.session_state.product_qty = {row['id']: 0 for _, row in products_df.iterrows()}

        sale_date = st.date_input("Дата продажи", value=date.today())

        st.markdown("""
        <style>
        .big-number {
            font-size: 28px;
            font-weight: bold;
            text-align: center;
            margin: 0;
            padding: 0;
            color: #1f77b4;
        }
        </style>
        """, unsafe_allow_html=True)

        st.subheader("Доступные продукты")
        for _, row in products_df.iterrows():
            prod_id = row['id']
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            col1.markdown(f"**{row['name']}**")
            if col2.button("−", key=f"minus_{prod_id}", use_container_width=True):
                if st.session_state.product_qty[prod_id] > 0:
                    st.session_state.product_qty[prod_id] -= 1
                    st.rerun()
            qty = st.session_state.product_qty[prod_id]
            col3.markdown(f"<div class='big-number'>{qty}</div>", unsafe_allow_html=True)
            if col4.button("+", key=f"plus_{prod_id}", use_container_width=True):
                st.session_state.product_qty[prod_id] += 1
                st.rerun()

        st.markdown("---")
        if st.button("✅ Добавить выбранные продажи", type="primary"):
            added = 0
            for prod_id, qty in st.session_state.product_qty.items():
                if qty > 0:
                    add_sale_with_request(st.session_state.user_id, prod_id, qty, sale_date.isoformat())
                    added += 1
            if added > 0:
                st.success(f"Добавлено {added} позиций продаж")
                for prod_id in st.session_state.product_qty:
                    st.session_state.product_qty[prod_id] = 0
                st.rerun()
            else:
                st.warning("Не выбрано ни одного продукта (количество = 0)")

    elif menu == "📋 Мои продажи":
        st.header("История ваших продаж")
        start_date = st.date_input("С даты", value=date.today() - timedelta(days=30))
        end_date = st.date_input("По дату", value=date.today())
        if st.button("Показать"):
            df = get_manager_sales(st.session_state.user_id, start_date.isoformat(), end_date.isoformat())
            if not df.empty:
                st.dataframe(df)
                total_rev = df['revenue'].sum()
                st.metric("Общая выручка", f"{total_rev:,.0f}")
                fig = px.bar(df, x='sale_date', y='revenue', title="Выручка по дням")
                st.plotly_chart(fig)
            else:
                st.info("Нет продаж за выбранный период")


    elif menu == "📄 Отчет за сегодня":
        st.header("📄 Отчет за сегодня")
        today_str = date.today().isoformat()
        # Данные продаж
        sales_df = get_today_sales_with_points(st.session_state.user_id, today_str)
        if not sales_df.empty:
            display_df = sales_df[['product', 'quantity', 'revenue']].copy()
            display_df.columns = ['Продукт', 'Количество', 'Баллы']
            st.subheader("🔍 Детальные продажи за день")
            st.dataframe(display_df, use_container_width=True)
            total_rub = sales_df['revenue'].sum()
            col1, col2 = st.columns(2)
            col1.metric("💰 Итого баллов", f"{total_rub:,.0f}")
        else:
            st.info("За сегодня продаж нет")
            total_rub = 0

        # Данные по заявкам для конверсии, выдано, отказы
        total_requests, success_requests = get_today_requests_count(st.session_state.user_id, today_str)
        successful_clients = get_today_successful_clients(st.session_state.user_id, today_str)
        cancelled_clients = get_today_cancelled_clients(st.session_state.user_id, today_str)
        cross_sales = get_today_cross_sales(st.session_state.user_id, today_str)
        # Формирование текстового отчёта
        report_lines = []
        report_lines.append(f"{date.today()}")
        report_lines.append(f"{st.session_state.full_name}")
        report_lines.append("")
        # Конверсия
        if total_requests > 0:
            conversion = (success_requests / total_requests) * 100
            report_lines.append(
                f"Конверсия: {conversion:.1f}% ({total_requests} / {success_requests})")
        else:
            report_lines.append("Конверсия: нет заявок")

        report_lines.append("")
        # Выдано
        if successful_clients:
            report_lines.append("Выдано:")
            for surname in successful_clients:
                report_lines.append(f"{surname}")
        else:
            report_lines.append("Выдано: нет заявок")
        report_lines.append("")
        # Отказы
        if cancelled_clients:
            report_lines.append("Отказы:")
            for surname, reason in cancelled_clients:
                report_lines.append(f"{surname} - {reason}")
        else:
            report_lines.append("Отказы: нет заявок")
        report_lines.append("")
        # Кросс-продажи
        if cross_sales:
            report_lines.append("Кросс-продажи:")
            for item in cross_sales:
                report_lines.append(f"{item['abbr']}: {item['total_quantity']}")
        else:
            report_lines.append("Кросс-продажи: нет заявок")
        # Добавим итоговые баллы и рубли
        report_lines.append("")
        report_lines.append(f"Итого баллов: {total_rub:.0f}")
        report_text = "\n".join(report_lines)
        st.markdown("---")
        st.subheader("📋 Текстовый отчет за день")
        st.text_area("Содержимое отчета", report_text, height=400, key="daily_report")

        if st.button("📋 Копировать отчет одним нажатием"):
            pyperclip.copy(report_text)
            st.success("✅ Отчет скопирован в буфер обмена!")

        # Кнопка экспорта в Excel (оставляем как было)
        if not sales_df.empty:
            excel_data = export_to_excel(sales_df, "Отчет за день")
            st.download_button("📎 Скачать отчет (Excel)", data=excel_data,
                               file_name=f"sales_report_{date.today()}.xlsx")

    elif menu == "📝 Заявки клиентов":
        st.header("Управление заявками клиентов")
        with st.expander("➕ Создать новую заявку", expanded=False):
            with st.form("new_request"):
                surname = st.text_input("Фамилия клиента *")

                # Дата рождения с ограничениями
                min_birth = date(1900, 1, 1)
                today = date.today()
                max_birth = today - timedelta(
                    days=14 * 365 + 1)  # 14 лет (приблизительно, для точности можно использовать relativedelta, но для демонстрации пойдёт)
                # Более точный расчёт: вычитаем 14 лет и один день, чтобы возраст был строго больше 14 лет (т.е. 14 лет и 1 день не подходит)
                try:
                    max_birth = date(today.year - 14, today.month, today.day) - timedelta(days=1)
                except ValueError:
                    max_birth = date(today.year - 14, today.month, today.day) - timedelta(days=1)

                birth_date = st.date_input("Дата рождения", value=None, min_value=min_birth, max_value=max_birth)

                # Пол
                gender = st.radio("Пол", ["М", "Ж"], horizontal=True)
                # Статус клиента
                client_status = st.radio("Статус клиента", ["Новый", "Действующий"], horizontal=True)
                # Заказанный продукт (только определённые ID)
                product_ids = [1, 2, 3, 4, 9, 11]  # ДК, КН, КК, Стикер, ПДС, Пенсия
                products_df = get_products_by_ids(product_ids)
                if products_df.empty:
                    st.error("Нет доступных продуктов для заказа. Сообщите администратору.")
                    st.stop()
                product_options = {row['name']: row['id'] for _, row in products_df.iterrows()}
                product_name = st.selectbox("Заказанный продукт", list(product_options.keys()))

                submitted = st.form_submit_button("Создать заявку")
                if submitted:
                    # Валидация
                    if not surname.strip():
                        st.error("Введите фамилию клиента.")
                    elif birth_date is None:
                        st.error("Дата рождения обязательна.")
                    elif birth_date > max_birth or birth_date < min_birth:
                        st.error(
                            f"Возраст клиента должен быть не менее 14 лет (дата рождения не позднее {max_birth.strftime('%d.%m.%Y')}) и не ранее 01.01.1900.")
                    else:
                        # Создаём профиль клиента в таблице client_profile
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute('''
                                INSERT INTO client_profile (surname, birth_date, gender, monthly_income)
                                VALUES (?, ?, ?, ?)
                            ''', (surname.strip(), birth_date.isoformat(), gender, 0))
                        client_id = cursor.lastrowid
                        conn.commit()
                        conn.close()

                        # Создаём заявку
                        status_db = "new" if client_status == "Новый" else "existing"
                        create_request_with_client(
                            st.session_state.user_id,
                            surname.strip(),
                            status_db,
                            product_options[product_name],
                            client_id
                        )
                        st.success("Заявка и профиль клиента созданы")
                        st.rerun()

        tab1, tab2 = st.tabs(["🟢 Активные заявки", "🔒 Закрытые заявки"])

        with tab1:
            active_df = get_active_requests(st.session_state.user_id)
            if active_df.empty:
                st.info("Нет активных заявок на сегодня")
            else:
                for idx, row in active_df.iterrows():
                    with st.container():
                        col1, col2, col3, col4, col5 = st.columns([2, 1, 2, 1, 1])
                        col1.write(f"**{row['client_surname']}**")
                        col2.write(row['status'])
                        col3.write(row['product'])
                        col4.write(row['request_date'])
                        if col5.button("Завершить", key=f"complete_{row['id']}"):
                            st.session_state['active_request_id'] = row['id']
                            st.session_state['show_completion_dialog'] = True
                            st.rerun()

                if st.session_state.get('show_completion_dialog', False):
                    req_id = st.session_state['active_request_id']
                    st.markdown("---")
                    st.subheader(f"Завершение заявки #{req_id}")
                    outcome = st.radio("Результат", ["УВ (успешная выдача)", "Отмена"], key="outcome_radio")

                    if outcome == "УВ (успешная выдача)":
                        st.info("Добавьте продажу для этого клиента")
                        temp_qty_key = f"temp_qty_{req_id}"
                        products_df2 = get_all_products()
                        if temp_qty_key not in st.session_state:
                            st.session_state[temp_qty_key] = {row['id']: 0 for _, row in products_df2.iterrows()}

                        st.markdown("""
                        <style>
                        .big-number-dialog {
                            font-size: 24px;
                            font-weight: bold;
                            text-align: center;
                            color: #2c3e50;
                        }
                        </style>
                        """, unsafe_allow_html=True)

                        st.subheader("Выберите продукты и количество")
                        for _, row in products_df2.iterrows():
                            prod_id = row['id']
                            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                            c1.markdown(f"**{row['name']}**")
                            if c2.button("−", key=f"dialog_minus_{req_id}_{prod_id}", use_container_width=True):
                                if st.session_state[temp_qty_key][prod_id] > 0:
                                    st.session_state[temp_qty_key][prod_id] -= 1
                                    st.rerun()
                            qty = st.session_state[temp_qty_key][prod_id]
                            c3.markdown(f"<div class='big-number-dialog'>{qty}</div>", unsafe_allow_html=True)
                            if c4.button("+", key=f"dialog_plus_{req_id}_{prod_id}", use_container_width=True):
                                st.session_state[temp_qty_key][prod_id] += 1
                                st.rerun()

                        sale_date = st.date_input("Дата продажи", value=date.today(), key=f"sale_date_{req_id}")
                        col_btn1, col_btn2 = st.columns(2)
                        if col_btn1.button("✅ Добавить продажи и закрыть заявку", key=f"confirm_sale_{req_id}"):
                            added = False
                            for prod_id, qty in st.session_state[temp_qty_key].items():
                                if qty > 0:
                                    add_sale_with_request(
                                        st.session_state.user_id,
                                        prod_id,
                                        qty,
                                        sale_date.isoformat(),
                                        request_id=req_id
                                    )
                                    added = True
                            if added:
                                st.success("Продажи добавлены, заявка закрыта как успешная")
                                if temp_qty_key in st.session_state:
                                    del st.session_state[temp_qty_key]
                                del st.session_state['show_completion_dialog']
                                del st.session_state['active_request_id']
                                st.rerun()
                            else:
                                st.warning("Не выбрано ни одного продукта")
                        if col_btn2.button("Отмена", key=f"cancel_dialog_{req_id}"):
                            if temp_qty_key in st.session_state:
                                del st.session_state[temp_qty_key]
                            del st.session_state['show_completion_dialog']
                            del st.session_state['active_request_id']
                            st.rerun()

                    else:  # Отмена
                        cancel_reason = st.selectbox(
                            "Причина отмены",
                            ["Недозвон", "Клиент не по адресу", "Не успеваю к клиенту", "Неактуально", "Другое"],
                            key=f"cancel_reason_{req_id}"
                        )
                        other_reason = ""
                        if cancel_reason == "Другое":
                            other_reason = st.text_input("Укажите причину", key=f"other_reason_{req_id}")
                        col_cancel1, col_cancel2 = st.columns(2)
                        if col_cancel1.button("❌ Подтвердить отмену", key=f"confirm_cancel_{req_id}"):
                            final_reason = other_reason if cancel_reason == "Другое" and other_reason else cancel_reason
                            cancel_request(req_id, final_reason)
                            st.success("Заявка отклонена")
                            del st.session_state['show_completion_dialog']
                            del st.session_state['active_request_id']
                            st.rerun()
                        if col_cancel2.button("Отмена", key=f"cancel_cancel_{req_id}"):
                            del st.session_state['show_completion_dialog']
                            del st.session_state['active_request_id']
                            st.rerun()

        with tab2:
            closed_df = get_closed_requests(st.session_state.user_id)
            if closed_df.empty:
                st.info("Нет закрытых заявок")
            else:
                closed_df = closed_df.rename(columns={
                    'client_surname': 'Клиент',
                    'client_status': 'Статус клиента',
                    'product': 'Продукт',
                    'status': 'Результат',
                    'completion_date': 'Дата закрытия',
                    'cancellation_reason': 'Причина отмены'
                })
                closed_df['Причина отмены'] = closed_df['Причина отмены'].fillna('—')
                closed_df['Результат'] = closed_df['Результат'].replace(
                    {'success': '✅ Успешно', 'cancelled': '❌ Отмена'})
                st.dataframe(
                    closed_df[['Клиент', 'Статус клиента', 'Продукт', 'Результат', 'Дата закрытия', 'Причина отмены']])

    elif menu == "🎯 План продаж":
        st.header("🎯 Мой план продаж на месяц")
        # Выбор месяца/года
        current_year = date.today().year
        current_month = date.today().month

        col1, col2 = st.columns(2)
        with col1:
            year = st.number_input("Год", min_value=2020, max_value=current_year + 1, value=current_year, step=1,
                                   key="plan_year")
        with col2:
            month = st.selectbox("Месяц", range(1, 13), format_func=lambda x: datetime(year, x, 1).strftime("%B"),
                                 index=current_month - 1, key="plan_month")
        year_month = f"{year}-{month:02d}"

        # Найти руководителя менеджера
        # Руководитель менеджера хранится в поле supervisor_id в таблице users
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT supervisor_id FROM users WHERE id=?", (st.session_state.user_id,))
        sup_id = c.fetchone()[0]
        conn.close()

        if sup_id:
            plan_per_employee = get_monthly_plan_per_employee(sup_id, year_month)
            if plan_per_employee is not None:
                actual_points = get_employee_actual_points(st.session_state.user_id, year_month)
                st.metric("📋 План на месяц (баллы)", f"{plan_per_employee:.0f}")
                st.metric("⭐ Мои баллы за месяц", f"{actual_points:.0f}")
                if plan_per_employee > 0:
                    percent = (actual_points / plan_per_employee) * 100
                    st.progress(min(percent / 100, 1.0))
                    st.caption(f"Выполнение плана: {percent:.1f}%")
                    if percent >= 100:
                        st.balloons()
                        st.success("🎉 План выполнен! Отличная работа!")
                    elif percent >= 75:
                        st.info("👍 Осталось совсем немного, вы близки к цели!")
                    elif percent >= 50:
                        st.warning("⚠️ Выполнена половина плана, поднажмите!")
                    else:
                        st.error("❌ План ещё не выполнен, есть над чем работать!")
            else:
                st.warning("План на этот месяц ещё не установлен руководителем.")
        else:
            st.error("Не найден ваш руководитель. Обратитесь к администратору.")

    elif menu == "💡 Рекомендации":
        st.header("💡 AI-ассистент продаж")
        st.markdown("Заполните информацию о клиенте для получения рекомендаций по продуктам.")

        # Инициализация данных клиента (без фамилии)
        client_data = {
            "birth_date": None,
            "gender": "",
            "family_status": "",
            "children_count": 0,
            "monthly_income": 0.0,
            "employment_type": "",
            "current_balance": 0.0,
            "total_assets": 0.0,
            "credit_score": 500,
            "requested_product": "",
            "client_status": "",
        }

        with st.form("recommendation_form"):
            col1, col2 = st.columns(2)
            with col1:
                client_data["birth_date"] = st.date_input("Дата рождения", value=None, min_value=date(1900, 1, 1),
                                                          max_value=date.today())
            with col2:
                client_data["gender"] = st.radio("Пол", ["М", "Ж"], horizontal=True)

            client_data["family_status"] = st.selectbox("Семейное положение",
                                                        ["", "женат/замужем", "холост/не замужем", "разведён",
                                                         "вдовец/вдова"])
            client_data["children_count"] = st.number_input("Количество детей", min_value=0, step=1, value=0)
            client_data["monthly_income"] = st.number_input("Доход в месяц (руб.)", min_value=0.0, step=5000.0,
                                                            value=0.0)
            client_data["employment_type"] = st.selectbox("Тип занятости",
                                                          ["", "наёмный сотрудник", "предприниматель", "пенсионер",
                                                           "безработный"])
            client_data["current_balance"] = st.number_input("Текущий баланс на счёте (руб.)", min_value=0.0,
                                                             step=1000.0, value=0.0)
            client_data["total_assets"] = st.number_input("Общие активы в банке (руб.)", min_value=0.0, step=10000.0,
                                                          value=0.0)
            client_data["credit_score"] = st.slider("Кредитный рейтинг (0-1000)", 0, 1000, 500)
            client_data["client_status"] = st.selectbox("Статус клиента", ["Новый", "Действующий"])

            product_ids = [1, 2, 3, 4, 9, 11]  # ДК, КН, КК, Стикер, ПДС, Пенсия
            products_df = get_products_by_ids(product_ids)
            if products_df.empty:
                st.error("Нет доступных продуктов для выбора. Сообщите администратору.")
                st.stop()
            product_options = {row['name']: row['name'] for _, row in products_df.iterrows()}  # name -> name
            client_data["requested_product"] = st.selectbox("Заказанный продукт",
                                                            [""] + list(product_options.keys()))

            submitted = st.form_submit_button("🚀 Получить рекомендацию ИИ")

        if submitted:
            if client_data["birth_date"] is None:
                st.error("Укажите дату рождения.")
            else:
                prompt = f"""

    Ты — ассистент банковского менеджера.
    Информация о клиенте:
    - Возраст: {(date.today().year - client_data['birth_date'].year)} лет (дата рождения {client_data['birth_date']})
    - Пол: {client_data['gender']}
    - Семейное положение: {client_data['family_status']}
    - Количество детей: {client_data['children_count']}
    - Доход: {client_data['monthly_income']} руб.
    - Тип занятости: {client_data['employment_type']}
    - Баланс: {client_data['current_balance']} руб.
    - Активы: {client_data['total_assets']} руб.
    - Кредитный рейтинг: {client_data['credit_score']}
    - Статус клиента: {client_data['client_status']}
    - Клиент заказал продукт: {client_data['requested_product'] if client_data['requested_product'] else 'не указан'}

    Напиши конкретные рекомендации — какие банковские продукты выездному менеджеру продать на встрече этому клиенту.
    Для каждого продукта дай краткий скрипт, как преподнести.
    """
                try:
                    import requests
                    YANDEX_FOLDER_ID = st.secrets["YANDEX_FOLDER_ID"]
                    YANDEX_API_KEY = st.secrets["YANDEX_API_KEY"]
                    YANDEX_GPT_MODEL = st.secrets["YANDEX_GPT_MODEL"]
                    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
                    headers = {
                        "Authorization": f"Api-Key {YANDEX_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    data = {
                        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/{YANDEX_GPT_MODEL}/latest",
                        "completionOptions": {
                            "stream": False,
                            "temperature": 0.6,
                            "maxTokens": 600
                        },
                        "messages": [
                            {"role": "system", "text": "Ты — полезный ассистент банковского менеджера."},
                            {"role": "user", "text": prompt}
                        ]
                    }
                    response = requests.post(url, headers=headers, json=data, timeout=15)
                    if response.status_code == 200:
                        result = response.json()
                        reply = result['result']['alternatives'][0]['message']['text']
                        st.success("Рекомендация от YandexGPT Light:")
                        st.markdown(reply)
                    else:
                        st.error(f"Ошибка API ({response.status_code}): {response.text}")
                        fallback_recommendation()
                except Exception as e:
                    st.error(f"Не удалось подключиться к YandexGPT: {e}")
                    fallback_recommendation()

def fallback_recommendation():
    st.info("🔁 Используется локальная модель рекомендаций (на основе статистики).")
    st.markdown("""
    **Примерные рекомендации (локальная модель):**
    - **Дебетовая карта** → «Дебетовая карта с кэшбэком до 5% – вы будете экономить на каждой покупке.»
    - **Кредитная карта** → «Кредитка с беспроцентным периодом 120 дней – удобно для крупных трат.»
    - **Накопительный счёт** → «Откройте накопительный счёт с доходностью до 10% годовых, чтобы ваши деньги работали на вас.»
    """)