import pandas as pd
import pymysql
import streamlit as st
import plotly.express as px
from sqlalchemy import text
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="스마트 보안 FDS 관제 시스템", page_icon="🚨", layout="wide"
)

# 세션 상태 초기화
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_name = ""
    st.session_state.card_id = ""

# DB 연결 정보 설정
db_host = st.secrets["mysql"]["host"]
db_port = st.secrets["mysql"]["port"]
db_user = st.secrets["mysql"]["user"]
db_password = st.secrets["mysql"]["password"]
db_name = st.secrets["mysql"]["database"]

DATABASE_URL = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
conn = st.connection("mysql", type="sql", url=DATABASE_URL)

# 앱 실행 시 테이블 자동 생성 및 더미 데이터 삽입
with conn.session as s:
    # 1. 사용자 정보 테이블
    s.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            signup_date DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """))
    
    # 2. 가맹점 업종 마스터 테이블 (추가됨 ✨)
    s.execute(text("""
        CREATE TABLE IF NOT EXISTS merchant_categories (
            category_id INT AUTO_INCREMENT PRIMARY KEY,
            category_name VARCHAR(50) NOT NULL,
            risk_weight INT DEFAULT 10
        );
    """))

    # 3. 카드 정보 테이블 (users와 1:N 관계)
    s.execute(text("""
        CREATE TABLE IF NOT EXISTS cards (
            card_id VARCHAR(20) PRIMARY KEY,
            user_id INT,
            limit_amount INT DEFAULT 5000000,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """))

    # 4. 거래 내역 테이블 (cards와 1:N 관계)
    s.execute(text("""
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id INT AUTO_INCREMENT PRIMARY KEY,
            card_id VARCHAR(20),
            tx_time DATETIME NOT NULL,
            amount INT NOT NULL,
            merchant_category VARCHAR(50) NOT NULL,
            foreign_transaction INT DEFAULT 0,
            location_mismatch INT DEFAULT 0,
            device_trust_score INT DEFAULT 80,
            velocity_last_24h INT DEFAULT 1,
            ip_address VARCHAR(50) NOT NULL,
            status VARCHAR(20) DEFAULT 'NORMAL',
            FOREIGN KEY (card_id) REFERENCES cards(card_id)
        );
    """))

    # 5. FDS 탐지 규칙 정의 테이블 (추가됨 ✨)
    s.execute(text("""
        CREATE TABLE IF NOT EXISTS fraud_rules (
            rule_id INT AUTO_INCREMENT PRIMARY KEY,
            rule_name VARCHAR(100) NOT NULL,
            threshold_value INT NOT NULL,
            score_weight INT NOT NULL
        );
    """))

    # 6. 보안 경보 로그 테이블 (transactions와 1:N 관계)
    s.execute(text("""
        CREATE TABLE IF NOT EXISTS alert_logs (
            alert_id INT AUTO_INCREMENT PRIMARY KEY,
            tx_id INT,
            risk_score INT,
            detect_reason VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tx_id) REFERENCES transactions(tx_id)
        );
    """))

    # --- 초기 기본 마스터 및 더미 데이터 자동 삽입 ---
    s.execute(text("""
        INSERT INTO users (user_id, name, phone) 
        VALUES (1, '홍길동', '010-1234-5678')
        ON DUPLICATE KEY UPDATE name=name;
    """))

    s.execute(text("""
        INSERT INTO merchant_categories (category_id, category_name, risk_weight) 
        VALUES 
            (1, 'Electronics', 15),
            (2, 'Travel', 20),
            (3, 'Grocery', 5),
            (4, 'Food', 5),
            (5, 'Clothing', 10)
        ON DUPLICATE KEY UPDATE category_name=category_name;
    """))

    s.execute(text("""
        INSERT INTO cards (card_id, user_id, limit_amount) 
        VALUES 
            ('4000-1234-5678-0001', 1, 5000000),
            ('4000-1234-5678-0002', 1, 5000000),
            ('4000-1234-5678-0003', 1, 5000000)
        ON DUPLICATE KEY UPDATE limit_amount=limit_amount;
    """))

    s.execute(text("""
        INSERT INTO fraud_rules (rule_id, rule_name, threshold_value, score_weight) 
        VALUES 
            (1, '고액 결제 탐지', 2000000, 40),
            (2, '초고액 결제 탐지', 5000000, 30),
            (3, '단시간 반복 결제', 5, 30),
            (4, '해외 결제 위험', 1, 20)
        ON DUPLICATE KEY UPDATE rule_name=rule_name;
    """))

    s.commit()

def get_connection():
    return pymysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

# 스타일 적용
st.markdown("""
<style>
.stApp { background-color: #f7f9fc; }
[data-testid="metric-container"] { background: white; border: 1px solid #e5e7eb; padding: 20px; border-radius: 15px; box-shadow: 0 3px 8px rgba(0,0,0,0.08); }
[data-testid="stDataFrame"] { background: white; border-radius: 15px; }
section[data-testid="stSidebar"] { background-color: #F8FAFC; }
section[data-testid="stSidebar"] * { color: black; }
</style>
""", unsafe_allow_html=True)

# DB에서 카드 목록 불러오기
try:
    conn_raw = get_connection()
    df_cards = pd.read_sql("SELECT card_id FROM cards", conn_raw)
    conn_raw.close()
    card_list = df_cards["card_id"].tolist() if not df_cards.empty else ["4000-1234-5678-0001", "4000-1234-5678-0002", "4000-1234-5678-0003"]
except:
    card_list = ["4000-1234-5678-0001", "4000-1234-5678-0002", "4000-1234-5678-0003"]


# ==========================================
# 1. 로그인 화면 (로그인 전)
# ==========================================
if not st.session_state.logged_in:
    st.markdown("# 🚨 Smart FDS Security Center")
    st.markdown("### 로그인 및 권한 선택")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("👨‍💼 관리자 로그인")
        admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw_input")
        if st.button("관리자로 로그인", use_container_width=True):
            if admin_pw == "1234":  # 필요시 비밀번호 변경 가능
                st.session_state.logged_in = True
                st.session_state.role = "admin"
                st.session_state.user_name = "시스템 관리자"
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")

    with col2:
        st.subheader("👤 일반 사용자 로그인")
        try:
            conn = get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT c.card_id, u.name FROM cards c JOIN users u ON c.user_id = u.user_id")
                card_users = cursor.fetchall()
            conn.close()
        except:
            card_users = [{"card_id": "4000-1234-5678-0001", "name": "홍길동"}]

        card_options = {f"{item['name']} ({item['card_id']})": item['card_id'] for item in card_users}
        selected_card_label = st.selectbox("사용할 카드 선택", list(card_options.keys()))
        
        if st.button("사용자로 로그인", use_container_width=True):
            st.session_state.logged_in = True
            st.session_state.role = "user"
            selected_card_id = card_options[selected_card_label]
            st.session_state.card_id = selected_card_id
            matched_user = next((item['name'] for item in card_users if item['card_id'] == selected_card_id), "사용자")
            st.session_state.user_name = matched_user
            st.rerun()

# ==========================================
# 2. 메인 대시보드 화면 (로그인 후)
# ==========================================
else:
    # 사이드바 설정 (로그아웃 및 결제 시뮬레이터)
    st.sidebar.success(f"현재 접속: **{st.session_state.user_name}** ({'관리자' if st.session_state.role == 'admin' else '일반 사용자'})")
    if st.sidebar.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.user_name = ""
        st.session_state.card_id = ""
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("# 💳 결제 시뮬레이터")
    st.sidebar.markdown("카드 결제를 생성하여 실시간 FDS 탐지 기능을 테스트합니다.\n---")

    sim_card_id = st.sidebar.selectbox("사용할 카드 선택", card_list, key="sim_card")
    amount = st.sidebar.number_input("결제 금액 (원)", min_value=1000, max_value=10000000, value=50000, step=1000)
    country = st.sidebar.selectbox("결제 국가", ["KR", "US", "CN", "VN"])
    ip_address = st.sidebar.text_input("접속 IP", "123.142.50.11")

    if st.sidebar.button("🚀 결제 승인 요청", use_container_width=True):
        conn_exec = get_connection()
        try:
            with conn_exec.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO transactions (card_id, tx_time, amount, merchant_country, ip_address)
                    VALUES (%s, NOW(), %s, %s, %s)
                """, (sim_card_id, amount, country, ip_address))
                conn_exec.commit()
                tx_id = cursor.lastrowid

                risk_score = 0
                reasons = []
                if amount > 2000000:
                    risk_score += 40
                    reasons.append("고액결제")
                if country != "KR":
                    risk_score += 20
                    reasons.append("해외결제")
                
                cursor.execute("""
                    SELECT COUNT(*) AS cnt FROM transactions
                    WHERE card_id=%s AND tx_time >= NOW() - INTERVAL 5 MINUTE
                """, (sim_card_id,))
                recent_count = cursor.fetchone()["cnt"]
                if recent_count >= 3:
                    risk_score += 30
                    reasons.append("5분내 반복결제")

                hour = datetime.now().hour
                if 1 <= hour <= 5:
                    risk_score += 15
                    reasons.append("심야거래")
                if amount >= 5000000:
                    risk_score += 30
                    reasons.append("초고액결제")

                if risk_score >= 60:
                    status = "BLOCKED"
                elif risk_score >= 30:
                    status = "REVIEW"
                else:
                    status = "NORMAL"

                cursor.execute("UPDATE transactions SET status=%s WHERE tx_id=%s", (status, tx_id))
                conn_exec.commit()

                if risk_score >= 30:
                    cursor.execute("""
                        INSERT INTO alert_logs (tx_id, risk_score, detect_reason)
                        VALUES (%s, %s, %s)
                    """, (tx_id, risk_score, ", ".join(reasons)))
                    conn_exec.commit()

                if status == "BLOCKED":
                    st.sidebar.error(f"⚠️ 차단됨 (위험도: {risk_score})")
                elif status == "REVIEW":
                    st.sidebar.warning(f"🔎 추가 검토 필요 (위험도: {risk_score})")
                else:
                    st.sidebar.success(f"✅ 정상 승인 (위험도: {risk_score})")
        finally:
            conn_exec.close()
        st.rerun()

    # 메인 상단 타이틀
    st.markdown("# 🚨 Smart FDS Security Center")
    if st.session_state.role == "admin":
        st.markdown("### 👑 관리자 전용 통합 관제 대시보드")
    else:
        st.markdown(f"### 👤 일반 사용자 대시보드 (보유 카드: {st.session_state.card_id})")
    st.markdown("---")

    # 요약 지표 카드
    conn_metrics = get_connection()
    try:
        total_tx_count = pd.read_sql("SELECT COUNT(*) as cnt FROM transactions", conn_metrics)["cnt"].iloc[0]
        blocked_tx_count = pd.read_sql("SELECT COUNT(*) as cnt FROM transactions WHERE status = 'BLOCKED'", conn_metrics)["cnt"].iloc[0]
        alert_count = pd.read_sql("SELECT COUNT(*) as cnt FROM alert_logs", conn_metrics)["cnt"].iloc[0]
    except:
        total_tx_count, blocked_tx_count, alert_count = 0, 0, 0
    conn_metrics.close()

    col1, col2, col3 = st.columns(3)
    col1.metric(label="📦 전체 누적 거래 건수", value=f"{total_tx_count:,} 건")
    col2.metric(label="🛡️ 차단된 위험 거래", value=f"{blocked_tx_count:,} 건", delta_color="inverse")
    col3.metric(label="🚨 보안 경보(Alert)", value=f"{alert_count:,} 건")

    st.markdown("---")

    # 관리자일 때만 전체 통계 차트 표시 / 사용자는 본인 내역에 집중
    if st.session_state.role == "admin":
        chart_conn = get_connection()
        df_country = pd.read_sql("SELECT merchant_country, COUNT(*) cnt FROM transactions GROUP BY merchant_country", chart_conn)
        df_status = pd.read_sql("SELECT status, COUNT(*) cnt FROM transactions GROUP BY status", chart_conn)
        df_hour = pd.read_sql("SELECT HOUR(tx_time) AS hour, COUNT(*) AS cnt FROM transactions GROUP BY HOUR(tx_time) ORDER BY hour", chart_conn)
        chart_conn.close()

        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.subheader("🌎 국가별 거래 현황")
            fig_country = px.bar(df_country, x="merchant_country", y="cnt", color="merchant_country", text_auto=True)
            fig_country.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig_country, width="stretch")

        with col_chart2:
            st.subheader("🛡️ 거래 상태 분석")
            fig_status = px.bar(df_status, x="status", y="cnt", color="status", text_auto=True)
            fig_status.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig_status, width="stretch")

        st.subheader("⏰ 시간대별 거래 현황")
        fig_hour = px.line(df_hour, x="hour", y="cnt", markers=True)
        fig_hour.update_layout(height=400)
        st.plotly_chart(fig_hour, width="stretch")

        st.subheader("🚨 카드별 평균 위험도")
        df_risk = pd.read_sql("""
            SELECT t.card_id, AVG(a.risk_score) AS avg_risk
            FROM transactions t JOIN alert_logs a ON t.tx_id = a.tx_id
            GROUP BY t.card_id ORDER BY avg_risk DESC
        """, get_connection())
        df_risk["avg_risk"] = df_risk["avg_risk"].round(1)
        st.dataframe(df_risk.rename(columns={"card_id": "카드번호", "avg_risk": "평균 위험도"}), width="stretch")

    # 데이터 조회 및 필터링 (관리자는 전체 또는 선택, 사용자는 본인 카드만 고정)
    if st.session_state.role == "admin":
        st.subheader("🔍 관리자 조회 필터")
        filter_option = st.selectbox("조회할 방식을 선택하세요", ["전체 카드 보기"] + card_list)
        if filter_option == "전체 카드 보기":
            query_alerts = "SELECT a.alert_id, t.card_id, t.amount, t.merchant_country, a.detect_reason, a.created_at FROM alert_logs a JOIN transactions t ON a.tx_id = t.tx_id ORDER BY a.created_at DESC LIMIT 10"
            query_tx = "SELECT * FROM transactions ORDER BY tx_time DESC LIMIT 10"
            params = None
        else:
            query_alerts = "SELECT a.alert_id, t.card_id, t.amount, t.merchant_country, a.detect_reason, a.created_at FROM alert_logs a JOIN transactions t ON a.tx_id = t.tx_id WHERE t.card_id = %s ORDER BY a.created_at DESC LIMIT 10"
            query_tx = "SELECT * FROM transactions WHERE card_id = %s ORDER BY tx_time DESC LIMIT 10"
            params = (filter_option,)
    else:
        # 일반 사용자는 본인 카드 내역만 자동 조회
        query_alerts = "SELECT a.alert_id, t.card_id, t.amount, t.merchant_country, a.detect_reason, a.created_at FROM alert_logs a JOIN transactions t ON a.tx_id = t.tx_id WHERE t.card_id = %s ORDER BY a.created_at DESC LIMIT 10"
        query_tx = "SELECT * FROM transactions WHERE card_id = %s ORDER BY tx_time DESC LIMIT 10"
        params = (st.session_state.card_id,)

    conn_data = get_connection()
    try:
        df_alerts = pd.read_sql(query_alerts, conn_data, params=params if params else None)
        df_tx = pd.read_sql(query_tx, conn_data, params=params if params else None)
    except:
        df_alerts = pd.DataFrame()
        df_tx = pd.DataFrame()
    conn_data.close()

    def highlight_status(row):
        if row["status"] == "BLOCKED":
            return ["background-color:#ffcccc"] * len(row)
        elif row["status"] == "REVIEW":
            return ["background-color:#fff3cd"] * len(row)
        return [""] * len(row)

    tab1, tab2 = st.tabs(["📊 실시간 보안 경보 로그", "📋 거래 내역"])

    with tab1:
        st.markdown("### 🚨 보안 경보 현황")
        if df_alerts.empty:
            st.info("💡 발생한 보안 경보가 없습니다.")
        else:
            st.dataframe(df_alerts, width="stretch")

    with tab2:
        st.markdown("### 💳 거래 내역")
        if df_tx.empty:
            st.info("💡 거래 내역이 없습니다.")
        else:
            st.dataframe(df_tx.style.apply(highlight_status, axis=1), width="stretch")
