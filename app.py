import streamlit as st
import numpy as np
import mediapipe as mp
from collections import deque
import json
import os

# 配置
GESTURE_LIB_PATH = "./sign-language-system/gesture_lib"
USER_DATA_FILE = "users.json"

# 初始化
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
gesture_map = {}

# 加载手势库
if os.path.exists(GESTURE_LIB_PATH):
    for fname in os.listdir(GESTURE_LIB_PATH):
        if fname.endswith(".npy"):
            name = fname.replace(".npy", "")
            gesture_map[name] = np.load(os.path.join(GESTURE_LIB_PATH, fname), allow_pickle=True)

# 用户系统
def load_users():
    if not os.path.exists(USER_DATA_FILE):
        return {"admin": "123456"}
    with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# 识别函数
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

# 界面
st.title("✋ 手语识别系统")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    username = st.text_input("账号")
    pwd = st.text_input("密码", type="password")
    if st.button("登录"):
        users = load_users()
        if username in users and users[username] == pwd:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("账号或密码错误")
else:
    st.success("登录成功！")
    run = st.toggle("开启摄像头")
    if run:
        st.info("正在初始化摄像头...")
        # 用streamlit_webrtc组件，完全绕过cv2依赖问题
        from streamlit_webrtc import webrtc_streamer, VideoProcessorBase
        import av

        class HandProcessor(VideoProcessorBase):
            def __init__(self):
                self.hands = mp_hands.Hands(min_detection_confidence=0.7)
            def recv(self, frame):
                img = frame.to_ndarray(format="bgr24")
                img = np.fliplr(img)
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                res = self.hands.process(rgb)
                if res.multi_hand_landmarks:
                    for h in res.multi_hand_landmarks:
                        points = [[lm.x, lm.y, lm.z] for lm in h.landmark]
                        text = recognize_gesture(points)
                        cv2.putText(img, text, (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,255,0), 3)
                        mp_drawing.draw_landmarks(img, h, mp_hands.HAND_CONNECTIONS)
                return av.VideoFrame.from_ndarray(img, format="bgr24")

        webrtc_streamer(key="hand", video_processor_factory=HandProcessor)
