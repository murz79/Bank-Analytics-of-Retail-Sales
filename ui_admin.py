import streamlit as st
from datetime import date, timedelta
import pandas as pd
from auth import register_user, delete_user, get_all_users, get_supervisors
from products_handlers import add_product, delete_product, get_all_products
from sales_handlers import get_sales_report
from utils import export_to_excel

def show_admin_page():
    st.sidebar.title("Администратор")
    menu = st.sidebar.radio("Меню", ["👥 Управление пользователями", "📦 Управление продуктами", "📑 Формирование отчета"])

    if menu == "👥 Управление пользователями":
        st.header("Добавление нового пользователя")
        with st.form("add_user"):
            username = st.text_input("Логин")
            full_name = st.text_input("Полное имя")
            password = st.text_input("Пароль", type="password")
            role = st.selectbox("Роль", ["manager", "supervisor", "admin"])
            supervisor_id = None
            if role == "manager":
                supervisors = get_supervisors()
                sup_dict = {row['full_name']: row['id'] for _, row in supervisors.iterrows()}
                if sup_dict:
                    sup_name = st.selectbox("Руководитель", list(sup_dict.keys()))
                    supervisor_id = sup_dict[sup_name]
                else:
                    st.warning("Нет руководителей. Сначала добавьте руководителя.")
            submitted = st.form_submit_button("Добавить")
            if submitted:
                if register_user(username, password, full_name, role, supervisor_id):
                    st.success("Пользователь добавлен")
                else:
                    st.error("Логин уже существует")

        st.header("Существующие пользователи")
        users_df = get_all_users()
        st.dataframe(users_df)
        user_to_delete = st.selectbox("Выберите ID пользователя для удаления", users_df['id'].tolist())
        if st.button("Удалить пользователя"):
            if delete_user(user_to_delete):
                st.success("Удален")
                st.rerun()
            else:
                st.error("Нельзя удалить администратора")

    elif menu == "📦 Управление продуктами":
        st.header("Добавить продукт")
        with st.form("add_product"):
            name = st.text_input("Название продукта")
            category = st.text_input("Категория")
            price = st.number_input("Базовая цена", min_value=0.0, step=100.0)
            if st.form_submit_button("Добавить"):
                if add_product(name, category, price):
                    st.success("Продукт добавлен")
                else:
                    st.error("Такой продукт уже есть")
        st.header("Удалить продукт")
        products = get_all_products()
        prod_dict = {row['name']: row['id'] for _, row in products.iterrows()}
        if prod_dict:
            prod_name = st.selectbox("Выберите продукт", list(prod_dict.keys()))
            if st.button("Удалить продукт"):
                delete_product(prod_dict[prod_name])
                st.success("Удалено")
                st.rerun()
        else:
            st.info("Нет продуктов для удаления")

    elif menu == "📈 Аналитика":
        from ui_analytics import show_analytics_page  # импорт внутри функции
        show_analytics_page()

    else:  # Формирование отчета
        st.header("Сформировать отчет по продажам")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Дата начала", value=date.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("Дата окончания", value=date.today())
        if st.button("Сформировать отчет"):
            df = get_sales_report(start_date.isoformat(), end_date.isoformat())
            if not df.empty:
                st.dataframe(df)
                pivot = pd.pivot_table(df, values='revenue', index='manager', columns='product', aggfunc='sum', fill_value=0)
                st.subheader("Сводка по менеджерам и продуктам")
                st.dataframe(pivot)
                # Экспорт в Excel с двумя листами
                output = export_to_excel(df, "Детали")
                # Для pivot нужен отдельный экспорт, упростим
                with pd.ExcelWriter("temp.xlsx", engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Детали', index=False)
                    pivot.to_excel(writer, sheet_name='Сводка')
                with open("temp.xlsx", "rb") as f:
                    excel_data = f.read()
                st.download_button("Скачать отчет Excel", data=excel_data, file_name=f"report_{start_date}_{end_date}.xlsx")
            else:
                st.info("Нет данных за выбранный период")