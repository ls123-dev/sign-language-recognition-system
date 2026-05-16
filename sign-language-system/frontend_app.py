import streamlit as st
import cv2
import mediapipe as mp
import torch
import numpy as np
import time

# 固定50个词汇顺序
CHINESE_WORDS = [
    "你好", "谢谢", "再见", "对不起", "没关系", "请", "早上好", "晚安",
    "我", "你", "他", "我们", "爸爸", "妈妈", "老师", "同学",
    "吃饭", "喝水", "睡觉", "上学", "回家", "出门", "休息", "生病",
    "开心", "高兴", "难过", "生气", "喜欢", "害怕",
    "学习", "工作", "知道", "明白", "努力", "读书",
    "可以", "不行", "对", "不对", "有", "没有",
    "一", "二", "三", "四", "五", "六", "七", "八"
]

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
FIXED_FRAMES = 40
INPUT_SIZE = 50
LOCK_TIME = 2.5

# 模型结构不变
class SignLSTM(torch.nn.Module):
    def __init__(self, input_size=50, hidden_dim=256, num_classes=500):
        super().__init__()
        self.lstm = torch.nn.LSTM(input_size=input_size, hidden_size=hidden_dim, num_layers=2,
                                   batch_first=True, bidirectional=True, dropout=0.3)
        self.dropout = torch.nn.Dropout(0.5)
        self.fc = torch.nn.Linear(hidden_dim * 2, num_classes)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.dropout(out[:, -1, :])
        return self.fc(out)

@st.cache_resource
def load_model():
    model = SignLSTM().to(DEVICE)
    model.load_state_dict(torch.load("csl_500_model.pth", map_location=DEVICE))
    model.eval()
    return model

model = load_model()

# 只检测上半身，过滤人脸干扰
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.6, min_tracking_confidence=0.6)
mp_drawing = mp.solutions.drawing_utils

sequence = []
last_idx = 0
last_result_time = 0

st.set_page_config(page_title="50词手势采集", layout="wide")
st.title("50词自定义手势编号采集")
st.subheader("摆好姿势静置2秒，记录每个词对应的编号")

frame_placeholder = st.empty()
result_placeholder = st.empty()

col1, col2 = st.columns(2)
with col1:
    start_btn = st.button("启动识别", use_container_width=True)
with col2:
    stop_btn = st.button("停止识别", use_container_width=True)

if start_btn:
    # 高清摄像头
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    while cap.isOpened() and not stop_btn:
        ret, frame = cap.read()
        if not ret:
            st.error("摄像头打开失败")
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)

        # 只取上肢关键点，避开脸部
        kp = []
        if res.pose_landmarks:
            for lm in res.pose_landmarks.landmark[11:28]:
                kp.extend([lm.x, lm.y, lm.z])

        while len(kp) < INPUT_SIZE:
            kp.append(0.0)
        kp = kp[:INPUT_SIZE]

        sequence.append(kp)
        if len(sequence) > FIXED_FRAMES:
            sequence.pop(0)

        if len(sequence) == FIXED_FRAMES:
            now = time.time()
            if now - last_result_time > LOCK_TIME:
                seq = np.array(sequence)
                mean = np.mean(seq, axis=0)
                std = np.std(seq, axis=0) + 1e-6
                seq = (seq - mean) / std

                tensor = torch.tensor(seq, dtype=torch.float32).unsqueeze(0).to(DEVICE)
                with torch.no_grad():
                    last_idx = model(tensor).argmax(1).item()
                last_result_time = now
                sequence = []

        # 只画上身关键点
        if res.pose_landmarks:
            for i in range(11, 28):
                lm = res.pose_landmarks.landmark[i]
                h, w, _ = frame.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)

        # 显示编号
        show = f"当前识别编号：{last_idx}"
        cv2.putText(frame, show, (30, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0,255,0), 3)
        frame_placeholder.image(frame, channels="BGR", use_container_width=True)
        result_placeholder.success(show)

    cap.release()