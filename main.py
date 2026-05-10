import streamlit as st
from database import init_db
from auth import authenticate
from ui_manager import show_manager_page
from ui_supervisor import show_supervisor_page
from ui_admin import show_admin_page

def login_page():
    st.title("🔐 Вход в систему анализа продаж")
    with st.form("login"):
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти")
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state.user_id = user[0]
                st.session_state.full_name = user[2]
                st.session_state.role = user[3]
                st.session_state.supervisor_id = user[4]
                st.rerun()
            else:
                st.error("Неверные учетные данные")

def main():
    init_db()
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None

    if st.session_state.user_id is None:
        login_page()
    else:
        role = st.session_state.role
        if role == 'manager':
            show_manager_page()
        elif role == 'supervisor':
            show_supervisor_page()
        elif role == 'admin':
            show_admin_page()

        if st.sidebar.button("🚪 Выйти"):
            for key in ['user_id', 'full_name', 'role', 'supervisor_id', 'product_qty']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()