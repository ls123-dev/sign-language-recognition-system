import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import cv2
import mediapipe as mp
import numpy as np
import os
import time
import pyttsx3
import mysql.connector
from datetime import datetime

# ======================
# MySQL 连接
# ======================
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="180072",
        database="sign_language_db"
    )

# ======================
# 全局配置
# ======================
st.set_page_config(
    page_title="手语辅助识别系统",
    layout="wide",
    page_icon="✋"
)

# ======================
# 自定义 CSS
# ======================
st.markdown("""
<style>
/* 全局背景 */
.stApp {
    background-color: #F0F8FF;
}

/* 登录注册页面整体外层背景图 */
.main {
    background-image: url("https://img0.baidu.com/it/u=2288264696,831114270&fm=253&fmt=auto&app=138&f=JPEG?w=1000&h=667");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}

/* 登录区域半透明白板 —— 保证文字 100% 清晰 */
.block-container {
    background-color: rgba(255, 255, 255, 0.88);
    padding: 3rem 2rem !important;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    max-width: 700px;
    margin: auto;
}

/* 侧边栏保持白色 */
.stSidebar {
    background-color: #ffffff !important;
}

/* 标题样式 */
.main-header {
    font-size: 30px;
    font-weight: bold;
    color: #2D3748;
    text-align: center;
    margin-bottom: 20px;
}

/* 输入框更清晰 */
.stTextInput, .stSelectbox {
    margin-bottom: 10px;
}

</style>
""", unsafe_allow_html=True)
# ======================
# 语音播报
# ======================
def speak(text):
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except:
        pass

# ======================
# 状态初始化
# ======================
defaults = {
    "logged_in": False,
    "current_user": None,
    "is_admin": False,
    "final_result": "",
    "voice_on": True,
    "recog_interval": 1.2,
    "current_menu": "系统主页",
    "camera_running": False,
    "announcement": "欢迎使用手语辅助识别系统！"
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ======================
# 手势库
# ======================
gesture_names = [
    "你好", "谢谢", "再见", "对不起", "请", "晚安",
    "我", "你", "他", "老师", "吃饭", "喝水",
    "睡觉", "上学", "回家", "生病", "开心", "难过",
    "生气", "喜欢", "可以", "不行", "对", "不对",
    "一", "二", "三", "四", "五", "八"
]

gesture_lib = []
save_path = "gesture_lib"
for i, name in enumerate(gesture_names):
    p = os.path.join(save_path, f"{i}_{name}.npy")
    gesture_lib.append(np.load(p) if os.path.exists(p) else None)

# ======================
# MediaPipe
# ======================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.3,
    min_tracking_confidence=0.3
)

# ======================
# 登录页面（带密码验证+性别/联系方式注册）
# ======================
if not st.session_state.logged_in:
    st.markdown('<div class="main-header" style="text-align:center;"> 用户登录</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["登录", "注册"])

    # 密码验证函数：8位以上 + 数字+字母混合
    def check_pwd(pwd):
        if len(pwd) < 8:
            return False
        has_num = any(c.isdigit() for c in pwd)
        has_letter = any(c.isalpha() for c in pwd)
        return has_num and has_letter

    # --------------------
    # 登录 TAB
    # --------------------
    with tab1:
        u = st.text_input("用户名", key="login_username")
        p = st.text_input("密码", type="password", key="login_password")
        
        # 密码格式错误红色提示
        if p and not check_pwd(p):
            st.markdown(
                '<p style="color:red; font-size:14px;">至少8位密码且必须为数字与字母混合</p>',
                unsafe_allow_html=True
            )

        if st.button("登录系统", use_container_width=True, type="primary", key="login_btn"):
            if not check_pwd(p):
                st.error("密码格式不符合要求！")
            else:
                db = get_db_connection()
                cursor = db.cursor()
                cursor.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s", (u, p))
                user = cursor.fetchone()
                if user:
                    st.session_state.logged_in = True
                    st.session_state.current_user = u
                    st.session_state.is_admin = (u == "admin")
                    st.rerun()
                else:
                    st.error("用户名或密码错误")
                cursor.close()
                db.close()

    # --------------------
    # 注册 TAB（完整版：性别、联系方式、8位编号、密码校验）
    # --------------------
    with tab2:
        u_new = st.text_input("设置用户名", key="reg_username")
        p_new = st.text_input("设置密码", type="password", key="reg_password")
        new_gender = st.selectbox("性别", ["未设置", "男", "女"], key="reg_gender")
        new_contact = st.text_input("联系方式", key="reg_contact")

        # 密码错误红色提示
        if p_new and not check_pwd(p_new):
            st.markdown(
                '<p style="color:red; font-size:14px;">至少8位密码且必须为数字与字母混合</p>',
                unsafe_allow_html=True
            )

        if st.button("注册账号", use_container_width=True, key="reg_btn"):
            if not check_pwd(p_new):
                st.error("密码格式不符合要求，无法注册！")
            else:
                db = get_db_connection()
                cursor = db.cursor()

                # 自动生成 8 位连续用户编号 00000001、00000002...
                cursor.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()[0]
                new_user_id = f"{count + 1:08d}"

                cursor.execute("SELECT * FROM users WHERE username=%s", (u_new,))
                if cursor.fetchone():
                    st.error("用户名已存在")
                else:
                    cursor.execute("""
                        INSERT INTO users (username, password_hash, gender, contact, status, user_id)
                        VALUES (%s, %s, %s, %s, '有效', %s)
                    """, (u_new, p_new, new_gender, new_contact, new_user_id))
                    db.commit()
                    st.success(f"注册成功！你的用户编号：{new_user_id}")
                cursor.close()
                db.close()
    st.stop()
# ======================
# 左侧固定菜单
# ======================
with st.sidebar:
    st.markdown('<div class="sidebar-card" style="text-align:center; font-size:18px; font-weight:bold;">✋ 手语识别系统</div>', unsafe_allow_html=True)
    menu_list = ["系统主页", "实时识别", "手语学习", "我的记录", "个人中心"]
    if st.session_state.is_admin:
        menu_list += ["管理员后台", "系统公告", "消息通知"]

    for item in menu_list:
        if st.button(item, use_container_width=True, key=f"menu_{item}"):
            st.session_state.current_menu = item
            st.rerun()

    st.markdown(f"""<div class="sidebar-card">👤 用户：{st.session_state.current_user}</div>""", unsafe_allow_html=True)
    if st.button("🚪 退出登录", use_container_width=True, key="logout_btn"):
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.session_state.is_admin = False
        st.rerun()

    with st.expander("⚙️ 识别设置"):
        st.session_state.recog_interval = st.slider("识别间隔(秒)", 0.7, 3.0, 1.2, key="recog_slider")
        st.session_state.voice_on = st.checkbox("语音播报", st.session_state.voice_on, key="voice_check")

# ======================
# 页面：系统主页
# ======================
if st.session_state.current_menu == "系统主页":
    st.markdown('<div class="main-header">系统主页</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="announcement">📢 系统公告：{st.session_state.announcement}</div>', unsafe_allow_html=True)

    st.info("""
    手语辅助识别系统基于MediaPipe手部关键点检测技术开发，
    支持实时摄像头手语识别、语音播报、手语学习、历史记录管理、用户权限管理等完整功能，
    专为听障群体沟通辅助、普通用户手语学习打造，操作简单、识别高效、实用性强。
    """)

    st.subheader("👤 个人信息")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**用户名：**", st.session_state.current_user)
        st.write("**账号身份：**", "管理员" if st.session_state.is_admin else "普通注册用户")
    with col2:
        st.empty()

    st.subheader("个人使用数据统计")
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM recognition_history WHERE username=%s AND DATE(create_time)=CURDATE()", (st.session_state.current_user,))
    today_cnt = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM recognition_history WHERE username=%s AND YEARWEEK(create_time)=YEARWEEK(NOW())", (st.session_state.current_user,))
    week_cnt = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM recognition_history WHERE username=%s", (st.session_state.current_user,))
    all_cnt = cursor.fetchone()[0]

    word_num = len(gesture_names)

    cursor.close()
    db.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("今日识别次数", today_cnt)
    c2.metric("本周识别次数", week_cnt)
    c3.metric("累计识别次数", all_cnt)
    c4.metric("可用手语词汇", word_num)

    st.subheader("系统更新日志")
    st.markdown("""
    <div class="update-log">
    <strong>v1.0.0（2026-05-10）</strong>
    <ul>
        <li>完成用户注册、登录、个人中心基础功能开发</li>
        <li>实现实时手语识别、手部关键点可视化、语音播报功能</li>
        <li>上线手语学习库，内置30个常用手语词汇</li>
        <li>新增识别历史记录、按日期检索、单条记录删除功能</li>
    </ul>
    <strong>v1.1.0（2026-05-13）</strong>
    <ul>
        <li>优化界面布局，左侧菜单固定展示，提升操作便捷性</li>
        <li>摄像头改为手动开启控制，避免自动启动占用资源</li>
        <li>新增管理员用户封禁、公告发布、消息通知功能</li>
        <li>完善系统主页数据统计、更新日志展示模块</li>
        <li>修复识别重复记录、摄像头释放异常等问题</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("💡 使用小贴士")
    st.warning("""
    1. 进入实时识别页面需手动点击打开摄像头；
    2. 保持手部正对镜头、光线充足识别更准确；
    3. 可在侧边栏调节识别间隔与语音播报开关；
    4. 所有识别记录自动保存，可按日期查询。
    """)

# ======================
# 页面：个人中心
# ======================
elif st.session_state.current_menu == "个人中心":
    st.markdown('<div class="main-header">👤 个人中心</div>', unsafe_allow_html=True)
    db = get_db_connection()
    cursor = db.cursor()

    # 读取当前用户信息
    cursor.execute("SELECT gender, contact, avatar_url FROM users WHERE username=%s", (st.session_state.current_user,))
    info = cursor.fetchone()
    gender = info[0] if info else "未设置"
    contact = info[1] if info else ""
    avatar_url = info[2] if info else ""

    st.subheader("基础信息设置")
    # 性别选择
    new_gender = st.selectbox("性别", ["未设置", "男", "女"], index=["未设置", "男", "女"].index(gender))
    # 联系方式
    new_contact = st.text_input("联系方式", value=contact)
    # 头像（用URL，也可以改成上传文件，这里用URL简单实现）
    new_avatar = st.text_input("头像链接", value=avatar_url, placeholder="输入头像图片链接")

    if st.button("保存信息", use_container_width=True):
        cursor.execute("""
            UPDATE users 
            SET gender=%s, contact=%s, avatar_url=%s 
            WHERE username=%s
        """, (new_gender, new_contact, new_avatar, st.session_state.current_user))
        db.commit()
        st.success("信息保存成功！")

    st.divider()
    st.subheader("修改密码")
    old = st.text_input("当前密码", type="password", key="old_pwd")
    new = st.text_input("新密码", type="password", key="new_pwd")
    if st.button("修改密码", use_container_width=True):
        cursor.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s", (st.session_state.current_user, old))
        if cursor.fetchone():
            cursor.execute("UPDATE users SET password_hash=%s WHERE username=%s", (new, st.session_state.current_user))
            db.commit()
            st.success("密码修改成功")
        else:
            st.error("原密码错误")
    cursor.close()
    db.close()
# ======================
# 页面：我的记录
# ======================
elif st.session_state.current_menu == "我的记录":
    st.markdown('<div class="main-header">我的识别记录</div>', unsafe_allow_html=True)
    date_selected = st.date_input("选择日期查询", key="record_date")
    db = get_db_connection()
    cursor = db.cursor()
    if st.session_state.is_admin:
        cursor.execute("SELECT id, username, result, create_time FROM recognition_history WHERE DATE(create_time)=%s ORDER BY id DESC", (str(date_selected),))
    else:
        cursor.execute("SELECT id, result, create_time FROM recognition_history WHERE username=%s AND DATE(create_time)=%s ORDER BY id DESC", (st.session_state.current_user, str(date_selected)))
    rows = cursor.fetchall()
    for r in rows:
        if st.session_state.is_admin:
            id_, user, res, ct = r
            c1,c2,c3,c4 = st.columns([1,2,3,1])
            c1.write(user)
            c2.write(res)
            c3.write(ct)
            if c4.button("删除", key=f"admin_del_{id_}"):
                cursor.execute("DELETE FROM recognition_history WHERE id=%s", (id_,))
                db.commit()
                st.rerun()
        else:
            id_, res, ct = r
            c1,c2,c3 = st.columns([3,3,1])
            c1.write(res)
            c2.write(ct)
            if c3.button("删除", key=f"user_del_{id_}"):
                cursor.execute("DELETE FROM recognition_history WHERE id=%s", (id_,))
                db.commit()
                st.rerun()
    cursor.close()
    db.close()

# ======================
# 页面：手语学习
# ======================
elif st.session_state.current_menu == "手语学习":
    st.markdown('<div class="main-header">📖 手语学习库</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    data = {
        "你好":"右手举到额头旁，掌心朝前","谢谢":"右手竖大拇指","再见":"右手平举，掌心向外",
        "对不起":"右手五指并拢，轻拍胸口","请":"右手掌心向上，水平向前伸出","晚安":"右手贴脸颊",
        "我":"指自己","你":"指前方","他":"指侧面","老师":"右手在头顶做戴帽动作","吃饭":"模拟吃饭",
        "喝水":"模拟喝水","睡觉":"模拟睡觉","上学":"模拟背包","回家":"手搭屋顶","生病":"摸额头",
        "开心":"拇指向上","难过":"摸眼角","生气":"握拳","喜欢":"手贴胸口","可以":"拇指向上",
        "不行":"拇指向下","对":"食指中指向上","不对":"双手交叉","一":"食指","二":"两指","三":"三指","四":"四指","五":"五指","八":"八字"
    }
    for i,(k,v) in enumerate(data.items()):
        with cols[i%3]:
            with st.container(border=True):
                st.markdown(f"**{k}**")
                st.caption(v)
    st.markdown("---")
    st.success("欢迎用户对此手语学习库进行指正或补充，联系方式为2529225936@qq.com")

# ======================
# 页面：实时识别
# ======================
# ======================
# 页面：手语实时识别（WebRTC方案，彻底解决空白问题）
# ======================
elif st.session_state.current_menu == "实时识别":
    st.markdown('<div class="main-header">✋ 实时手语识别</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([2,1])
    with col1:
        st.subheader("🎥 摄像头画面")
        frame_box = st.empty()
        if st.button("📷 打开/关闭摄像头", use_container_width=True, type="primary", key="cam_toggle"):
            st.session_state.camera_running = not st.session_state.camera_running

    with col2:
        st.subheader("🔊 识别结果")
        res_box = st.empty()
        score_box = st.empty()

    if not st.session_state.camera_running:
        frame_box.info("👆 点击上方按钮打开摄像头")
        st.stop()

    cap = cv2.VideoCapture(0)
    last_check = 0

    while st.session_state.camera_running:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = hands.process(rgb)

        best_score = 0
        detected = ""

        if time.time() - last_check > st.session_state.recog_interval:
            if res.multi_hand_landmarks:
                for hl in res.multi_hand_landmarks:
                    pts = np.array([[lm.x, lm.y, lm.z] for lm in hl.landmark])
                    min_d, best_idx = 999, -1
                    for i, ref in enumerate(gesture_lib):
                        if ref is None: continue
                        d = np.linalg.norm(pts - ref)
                        if d < min_d:
                            min_d, best_idx = d, i
                    if best_idx != -1 and min_d < 1.5:
                        detected = gesture_names[best_idx]
                        best_score = round((1.0 - min_d/1.5), 2)

            if detected and detected != st.session_state.final_result:
                st.session_state.final_result = detected
                db = get_db_connection()
                cursor = db.cursor()
                cursor.execute("INSERT INTO recognition_history (username, result) VALUES (%s, %s)", (st.session_state.current_user, detected))
                db.commit()
                cursor.close()
                db.close()
                if st.session_state.voice_on:
                    speak(detected)
            last_check = time.time()

        if res.multi_hand_landmarks:
            for hl in res.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)

        frame_box.image(frame, channels="BGR", width="stretch")
        res_box.markdown(f'<div class="result-box">{st.session_state.final_result}</div>', unsafe_allow_html=True)
        if best_score > 0:
            score_box.metric("置信度", f"{best_score*100:.0f}%")
        else:
            score_box.empty()

    cap.release()
# ======================
# 页面：消息通知中心（管理员/用户 一对一聊天+数据库存记录）
# ======================
elif st.session_state.current_menu == "消息通知":
    st.markdown('<div class="main-header">💬 消息通知聊天中心</div>', unsafe_allow_html=True)
    db = get_db_connection()
    cursor = db.cursor()

    # ========== 管理员端：选择指定用户对话 ==========
    if st.session_state.is_admin:
        # 获取所有普通用户
        cursor.execute("SELECT username FROM users WHERE username != 'admin'")
        user_list = [row[0] for row in cursor.fetchall()]
        select_user = st.selectbox("选择要对话的用户", user_list, key="chat_select_user")
        chat_target = select_user

        st.divider()
        st.subheader(f"正在与【{chat_target}】聊天")

        # 加载双方聊天记录
        cursor.execute("""
            SELECT sender,content,create_time 
            FROM chat_message 
            WHERE (sender=%s AND receiver=%s) OR (sender=%s AND receiver=%s)
            ORDER BY create_time ASC
        """, ("admin", chat_target, chat_target, "admin"))
        msg_list = cursor.fetchall()

        # 展示聊天记录
        chat_container = st.container(border=True)
        with chat_container:
            for sender,content,ct in msg_list:
                if sender == "admin":
                    st.success(f"管理员：{content} 【{ct}】")
                else:
                    st.info(f"{sender}：{content} 【{ct}】")

        # 管理员发消息
        msg_input = st.text_input("输入发送消息", key="admin_chat_input")
        if st.button("发送消息", use_container_width=True, key="admin_chat_send"):
            if msg_input.strip() != "":
                cursor.execute(
                    "INSERT INTO chat_message(sender,receiver,content) VALUES(%s,%s,%s)",
                    ("admin", chat_target, msg_input.strip())
                )
                db.commit()
                st.rerun()

    # ========== 普通用户端：只能和管理员聊天 ==========
    else:
        chat_target = "admin"
        st.subheader("与管理员对话窗口")
        st.divider()

        # 加载自己和管理员的聊天记录
        cursor.execute("""
            SELECT sender,content,create_time 
            FROM chat_message 
            WHERE (sender=%s AND receiver=%s) OR (sender=%s AND receiver=%s)
            ORDER BY create_time ASC
        """, (st.session_state.current_user, "admin", "admin", st.session_state.current_user))
        msg_list = cursor.fetchall()

        # 展示聊天记录
        chat_container = st.container(border=True)
        with chat_container:
            for sender,content,ct in msg_list:
                if sender == "admin":
                    st.success(f"管理员：{content} 【{ct}】")
                else:
                    st.info(f"我：{content} 【{ct}】")

        # 普通用户发消息给管理员
        msg_input = st.text_input("输入消息发送给管理员", key="user_chat_input")
        if st.button("发送消息", use_container_width=True, key="user_chat_send"):
            if msg_input.strip() != "":
                cursor.execute(
                    "INSERT INTO chat_message(sender,receiver,content) VALUES(%s,%s,%s)",
                    (st.session_state.current_user, "admin", msg_input.strip())
                )
                db.commit()
                st.rerun()

    cursor.close()
    db.close()# ======================
# 页面：管理员后台
# ======================
elif st.session_state.current_menu == "管理员后台" and st.session_state.is_admin:
    st.markdown('<div class="main-header">🔑 管理员后台 - 用户管理 & 数据统计</div>', unsafe_allow_html=True)
    db = get_db_connection()
    cursor = db.cursor()

    # 顶部数据统计面板
    st.subheader("📊 系统数据统计")
    col1, col2, col3, col4 = st.columns(4)

    # 统计各项数据
    cursor.execute("SELECT COUNT(*) FROM users WHERE username!='admin'")
    total_user = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE username!='admin' AND status='有效'")
    active_user = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE username!='admin' AND status='封禁'")
    ban_user = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM recognition_history")
    total_records = cursor.fetchone()[0]

    col1.metric("总注册用户", total_user)
    col2.metric("正常有效用户", active_user)
    col3.metric("已封禁用户", ban_user)
    col4.metric("全站识别总记录", total_records)

    st.divider()

    # 用户列表表头
    st.subheader("👥 用户列表（点击用户名可查看该用户全部识别记录）")
    cols = st.columns([1.2, 2, 1.2, 2, 2.5, 1.5, 1.5])
    cols[0].write("用户编号")
    cols[1].write("用户名")
    cols[2].write("性别")
    cols[3].write("联系方式")
    cols[4].write("账号创建时间")
    cols[5].write("账号状态")
    cols[6].write("操作")

    # 查询所有普通用户 按8位编号升序（早创建编号越小）
    cursor.execute("""
        SELECT user_id, username, gender, contact, create_time, status 
        FROM users 
        WHERE username != 'admin'
        ORDER BY user_id ASC
    """)
    user_list = cursor.fetchall()

    # 保存当前选中查看记录的用户
    selected_user = st.session_state.get("selected_user", None)

    # 遍历渲染每一行用户
    for user in user_list:
        user_id, username, gender, contact, create_time, status = user
        cols = st.columns([1.2, 2, 1.2, 2, 2.5, 1.5, 1.5])

        cols[0].write(user_id)
        # 点击用户名按钮 选中查看记录
        if cols[1].button(username, key=f"show_rec_{username}"):
            st.session_state["selected_user"] = username
            st.rerun()

        cols[2].write(gender)
        cols[3].write(contact if contact else "无")
        cols[4].write(str(create_time)[:19])

        # 状态标色
        if status == "有效":
            cols[5].markdown('<span style="color:green">正常</span>', unsafe_allow_html=True)
        else:
            cols[5].markdown('<span style="color:red">已封禁</span>', unsafe_allow_html=True)

        # 封禁 / 解封按钮
        if status == "有效":
            if cols[6].button("封禁", key=f"ban_{user_id}"):
                cursor.execute("UPDATE users SET status='封禁' WHERE user_id=%s", (user_id,))
                db.commit()
                st.rerun()
        else:
            if cols[6].button("解封", key=f"unban_{user_id}"):
                cursor.execute("UPDATE users SET status='有效' WHERE user_id=%s", (user_id,))
                db.commit()
                st.rerun()

    st.divider()

    # 展示选中用户的所有识别记录
    if selected_user:
        st.subheader(f"📄 用户【{selected_user}】全部手语识别记录")
        cursor.execute("""
            SELECT result, create_time 
            FROM recognition_history 
            WHERE username = %s 
            ORDER BY create_time DESC
        """, (selected_user,))
        records = cursor.fetchall()

        if not records:
            st.info("该用户暂无任何手语识别记录")
        else:
            for idx, (res, ct) in enumerate(records, 1):
                st.write(f"{idx}. 识别结果：{res}　｜　时间：{str(ct)[:19]}")

        # 关闭查看
        if st.button("关闭查看记录", type="secondary"):
            del st.session_state["selected_user"]
            st.rerun()

    cursor.close()
    db.close()
# ======================
# 页面：系统公告（管理员发布 + 用户查看）
# ======================
elif st.session_state.current_menu == "系统公告":
    st.markdown('<div class="main-header">📢 系统公告</div>', unsafe_allow_html=True)

    # 只有管理员可以编辑
    if st.session_state.is_admin:
        new_announce = st.text_area("编辑系统公告", value=st.session_state.announcement, height=150)
        if st.button("发布公告", use_container_width=True, type="primary"):
            st.session_state.announcement = new_announce
            st.success("公告发布成功！")

    # 所有用户都能看
    st.markdown(f"""
    <div style="font-size:18px; line-height:1.8; padding:15px; background:#f8f9fa; border-radius:10px;">
    {st.session_state.announcement}
    </div>
    """, unsafe_allow_html=True)
