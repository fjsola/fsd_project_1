import streamlit as st
import pandas as pd
import pymysql

st.set_page_config(page_title="내 카드 조회", page_icon="👤", layout="wide")

# 권한 체크
if "logged_in" not in st.session_state or not st.session_state.logged_in or st.session_state.role != "user":
    st.warning("⚠️ 접근 권한이 없습니다. 메인 페이지에서 일반 사용자로 로그인해주세요.")
    st.stop()

def get_connection():
    return pymysql.connect(
        host=st.secrets["mysql"]["host"],
        port=st.secrets["mysql"]["port"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

my_card_id = st.session_state.card_id
my_name = st.session_state.user_name

st.title(f"👤 {my_name}님의 카드 보안 관제 대시보드")
st.markdown(f"**조회 중인 카드 번호:** `{my_card_id}`")
st.markdown("---")

# 내 카드 전용 데이터 조회
conn_data = get_connection()
try:
    query_alerts = """
        SELECT a.alert_id, t.card_id, t.amount, t.merchant_country, a.detect_reason, a.created_at
        FROM alert_logs a JOIN transactions t ON a.tx_id = t.tx_id
        WHERE t.card_id = %s ORDER BY a.created_at DESC LIMIT 10
    """
    query_tx = "SELECT * FROM transactions WHERE card_id = %s ORDER BY tx_time DESC LIMIT 10"
    
    df_alerts = pd.read_sql(query_alerts, conn_data, params=(my_card_id,))
    df_tx = pd.read_sql(query_tx, conn_data, params=(my_card_id,))
except:
    df_alerts = pd.DataFrame()
    df_tx = pd.DataFrame()
conn_data.close()

def highlight_status(row):
    if row["status"] == "BLOCKED": return ["background-color:#ffcccc"] * len(row)
    elif row["status"] == "REVIEW": return ["background-color:#fff3cd"] * len(row)
    return [""] * len(row)

tab1, tab2 = st.tabs(["📊 내 카드 보안 경보 로그", "📋 내 카드 거래 내역"])

with tab1:
    st.markdown("### 🚨 내 카드 보안 경보 현황")
    if df_alerts.empty:
        st.info("💡 내 카드에 발생한 보안 경보가 없습니다. 안전합니다!")
    else:
        st.dataframe(df_alerts.rename(columns={"alert_id": "경보ID", "card_id": "카드번호", "amount": "금액", "merchant_country": "국가", "detect_reason": "탐지사유", "created_at": "발생시각"}), width="stretch")

with tab2:
    st.markdown("### 💳 내 카드 최근 거래 내역")
    if df_tx.empty:
        st.info("💡 해당 카드의 거래 내역이 없습니다.")
    else:
        st.dataframe(df_tx.style.apply(highlight_status, axis=1), width="stretch")