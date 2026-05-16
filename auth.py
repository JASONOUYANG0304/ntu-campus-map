import smtplib
import random
import streamlit as st
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
import os

load_dotenv()
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

def send_verification_code(target_email):
    # 產生 6 位數驗證碼
    code = str(random.randint(100000, 999999))
    st.session_state["verify_code"] = code
    st.session_state["verify_email"] = target_email

    # 組合信件
    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = target_email
    msg["Subject"] = "臺大地圖 驗證碼"
    msg.attach(MIMEText(f"你的驗證碼是：{code}\n\n10分鐘內有效。", "plain"))

    # 寄信
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, target_email, msg.as_string())

    return True

def check_login():
    st.subheader("登入")
    email = st.text_input("輸入台大信箱")

    if st.button("寄送驗證碼"):
        if not email.endswith("@ntu.edu.tw"):
            st.error("請使用台大信箱（@ntu.edu.tw）")
        else:
            send_verification_code(email)
            st.success("驗證碼已寄出，請檢查信箱")

    code_input = st.text_input("輸入驗證碼")
    if st.button("驗證"):
        if code_input == st.session_state.get("verify_code"):
            st.session_state["is_ntu"] = True
            st.session_state["user"] = st.session_state["verify_email"]
            st.success("登入成功！")
        else:
            st.error("驗證碼錯誤")

def is_logged_in():
    return st.session_state.get("is_ntu", False)