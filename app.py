import streamlit as st
import numpy as np
import mediapipe as mp
from collections import deque
import json
import os

# ======================== 配置（云端兼容版）========================
# 手势库路径（适配 GitHub 云端结构）
GESTURE_LIB_PATH = "./sign-language-system/gesture_lib"

# 用户数据保存到 JSON（云端不能用本地 MySQL）
USER_DATA_FILE = "users.json"
HISTORY_FILE = "history.json"

# ======================== 初始化工具========================
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# 加载手势库
gesture_map = {}
if os.path.exists(GESTURE_LIB_PATH):
    for fname in os.listdir(GESTURE_LIB_PATH):
        if fname.endswith(".npy"):
            name = fname.replace(".npy", "")
            data = np.load(os.path.join(GESTURE_LIB_PATH, fname), allow_pickle=True)
            gesture_map[name] = data

points_history = deque(maxlen=10)

# ======================== JSON 用户系统 ========================
def load_users():
    if not os.path.exists(USER_DATA_FILE):
        return {"admin": "123456"}
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False)

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(item):
    history = load_history()
    history.append(item)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)

# ======================== 识别函数 ========================
def recognize_gesture(landmarks):
    if not gesture_map:
        return "未配置手势库"
    current = np.array(landmarks).flatten()
    min_dist = float("inf")
    result = "未知"
    for name, data in gesture_map.items():
        dist = np.linalg.norm(current - data.flatten())
        if dist < min_dist:
            min_dist = dist
            result = name
    return result if min_dist < 30 else "未知"

# ======================== 界面 ========================
st.title("✋ 手语识别系统（云端部署版）")

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
                st.session_state.user = username
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
    st.success(f"欢迎回来：{st.session_state.user}")
    run = st.toggle("开启摄像头")
    win = st.empty()

    if run:
        # 改用streamlit内置的摄像头组件，绕过cv2的依赖问题
        from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
        import av

        RTC_CONFIGURATION = RTCConfiguration(
            {"iceServers": [{"urls": ["st:turn:openrelay.metered.ca:80", "turn:openrelay.metered.ca:80?transport=udp", "turn:openrelay.metered.ca:3478", "turn:openrelay.metered.ca:3478?transport=udp", "turn:openrelay.metered.ca:443", "turn:openrelay.metered.ca:443?transport=tcp", "turns:openrelay.metered.ca:443", "turns:openrelay.metered.ca:443?transport=tcp"]}]}
        )

        class VideoProcessor:
            def recv(self, frame):
                img = frame.to_ndarray(format="bgr24")
                img = np.fliplr(img)
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                with mp_hands.Hands(
                    min_detection_confidence=0.7,
                    min_tracking_confidence=0.7,
                    max_num_hands=1
                ) as hands:
                    res = hands.process(rgb)
                if res.multi_hand_landmarks:
                    for h in res.multi_hand_landmarks:
                        points = [
                            [lm.x, lm.y, lm.z] for lm in h.landmark
                        ]
                        g = recognize_gesture(points)
                        cv2.putText(img, g, (50, 100),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    2, (0, 255, 0), 3)
                        mp_drawing.draw_landmarks(img, h, mp_hands.HAND_CONNECTIONS)
                return av.VideoFrame.from_ndarray(img, format="bgr24")

        webrtc_streamer(
            key="example",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=RTC_CONFIGURATION,
            video_processor_factory=VideoProcessor,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )
    else:
        st.info("请点击上方开关开启摄像头")
