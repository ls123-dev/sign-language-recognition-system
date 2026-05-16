import streamlit as st
import json
import os

# ======================== 配置 ========================
USER_DATA_FILE = "users.json"

# ======================== 用户系统 ========================
def load_users():
    if not os.path.exists(USER_DATA_FILE):
        return {"admin": "123456"}
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False)

# ======================== 界面 ========================
st.title("✅ 手语识别系统（云端稳定版）")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["登录", "注册"])
    users = load_users()

    with tab1:
        username = st.text_input("账号")
        pwd = st.text_input("密码", type="password")
        if st.button("登录"):
            if username in users and users[username] == pwd:
                st.session_state.logged_in = True
                st.success("登录成功！")
                st.rerun()
            else:
                st.error("账号或密码错误")

    with tab2:
        new_user = st.text_input("新账号")
        new_pwd = st.text_input("新密码", type="password")
        if st.button("注册"):
            if new_user in users:
                st.warning("账号已存在")
            else:
                users[new_user] = new_pwd
                save_users(users)
                st.success("注册成功！")
else:
    st.success("✅ 登录成功！")
    st.write("🎯 你的手语识别系统已成功部署在 Streamlit 云端！")
    st.write("🔹 账号：admin")
    st.write("🔹 密码：123456")

    st.info("""
    💡 说明：
    由于 OpenCV / MediaPipe 在云端环境无法安装，
    摄像头识别功能需要在本地电脑运行才能使用。
    """)
