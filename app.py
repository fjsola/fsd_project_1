import pandas as pd
import pymysql
import streamlit as st

from sqlalchemy import text
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="스마트 보안 FDS 관제 시스템", page_icon="🚨", layout="wide"
)

# Streamlit secrets에서 정보 가져와서 SQLAlchemy + PyMySQL 연결 생성
db_host = st.secrets["mysql"]["host"]
db_port = st.secrets["mysql"]["port"]
db_user = st.secrets["mysql"]["user"]
db_password = st.secrets["mysql"]["password"]
db_name = st.secrets["mysql"]["database"]

# PyMySQL을 활용한 SQLAlchemy 커넥션 스트링 (mysql+pymysql 사용)
DATABASE_URL = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"

conn = st.connection("mysql", type="sql", url=DATABASE_URL)

# 앱이 켜질 때 Aiven DB에 테이블이 없으면 자동 생성 및 기본 데이터 삽입
with conn.session as s:
  s.execute(
      text(
          """
        CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            signup_date DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """
      )
  )
  s.execute(
      text(
          """
        CREATE TABLE IF NOT EXISTS cards (
            card_id VARCHAR(20) PRIMARY KEY,
            user_id INT,
            limit_amount INT DEFAULT 5000000,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """
      )
  )
  s.execute(
      text(
          """
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id INT AUTO_INCREMENT PRIMARY KEY,
            card_id VARCHAR(20),
            tx_time DATETIME NOT NULL,
            amount INT NOT NULL,
            merchant_country VARCHAR(10) NOT NULL,
            ip_address VARCHAR(50) NOT NULL,
            status VARCHAR(20) DEFAULT 'NORMAL',
            FOREIGN KEY (card_id) REFERENCES cards(card_id)
        );
    """
      )
  )
  s.execute(
      text(
          """
        CREATE TABLE IF NOT EXISTS alert_logs (
            alert_id INT AUTO_INCREMENT PRIMARY KEY,
            tx_id INT,
            risk_score INT,
            detect_reason VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """
      )
  )

  # ★ 외래 키 에러 방지를 위한 기본 더미 사용자 및 카드 데이터 자동 삽입
  s.execute(
      text(
          """
        INSERT INTO users (user_id, name, phone) 
        VALUES (1, '홍길동', '010-1234-5678')
        ON DUPLICATE KEY UPDATE name=name;
    """
      )
  )
  s.execute(
      text(
          """
        INSERT INTO cards (card_id, user_id, limit_amount) 
        VALUES 
            ('4000-1234-5678-0001', 1, 5000000),
            ('4000-1234-5678-0002', 1, 5000000),
            ('4000-1234-5678-0003', 1, 5000000)
        ON DUPLICATE KEY UPDATE limit_amount=limit_amount;
    """
      )
  )

  s.commit()

# PyMySQL을 사용하는 기존 방식의 DB 연결 함수 (사이드바 결제 요청 등에서 활용)
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

# 제목 및 스타일 타이틀
st.markdown("""
# 🚨 Smart FDS Security Center

### 실시간 이상거래 탐지 및 카드 보안 관제 시스템

---
""")
st.markdown(
    """
<style>

/* 전체 배경 */

.stApp {
    background-color: #f7f9fc;
}

/* KPI 카드 */

[data-testid="metric-container"] {

    background: white;

    border: 1px solid #e5e7eb;

    padding: 20px;

    border-radius: 15px;

    box-shadow: 0 3px 8px rgba(0,0,0,0.08);
}

/* 데이터프레임 */

[data-testid="stDataFrame"] {

    background: white;

    border-radius: 15px;
}

/* 사이드바 */

section[data-testid="stSidebar"] {

    background-color: #1e293b;

}

/* 사이드바 글씨 */

section[data-testid="stSidebar"] * {

    color: white;

}

</style>
    """,
    unsafe_allow_html=True
)

# 데이터베이스에서 등록된 카드 목록 동적 불러오기 (테이블이 비어있을 경우 기본값 활용)
try:
  conn_raw = get_connection()
  df_cards = pd.read_sql("SELECT card_id FROM cards", conn_raw)
  conn_raw.close()
  if df_cards.empty:
    card_list = [
        "4000-1234-5678-0001",
        "4000-1234-5678-0002",
        "4000-1234-5678-0003",
    ]
  else:
    card_list = df_cards["card_id"].tolist()
except:
  card_list = [
      "4000-1234-5678-0001",
      "4000-1234-5678-0002",
      "4000-1234-5678-0003",
  ]
# --- [사이드바] 결제 시뮬레이터 입력 폼 ---

st.sidebar.markdown("""

# 💳 결제 시뮬레이터

카드 결제를 생성하여

실시간 FDS 탐지 기능을 테스트합니다.

---

""")

card_id = st.sidebar.selectbox(
    "사용할 카드 선택",
    card_list
)

amount = st.sidebar.number_input(
    "결제 금액 (원)",
    min_value=1000,
    max_value=10000000,
    value=50000,
    step=1000
)

country = st.sidebar.selectbox(
    "결제 국가",
    ["KR", "US", "CN", "VN"]
)

ip_address = st.sidebar.text_input(
    "접속 IP",
    "123.142.50.11"
)

if st.sidebar.button("🚀 결제 승인 요청", use_container_width=True):

    conn_exec = get_connection()

    try:

        with conn_exec.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO transactions
                (
                    card_id,
                    tx_time,
                    amount,
                    merchant_country,
                    ip_address
                )
                VALUES
                (
                    %s,
                    NOW(),
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    card_id,
                    amount,
                    country,
                    ip_address
                )
            )

            conn_exec.commit()

            tx_id = cursor.lastrowid

            risk_score = 0
            reasons = []

            # 고액 결제
            if amount > 2000000:
                risk_score += 40
                reasons.append("고액결제")

            # 해외 결제
            if country != "KR":
                risk_score += 20
                reasons.append("해외결제")
                
            # 최근 5분 내 반복 결제
            cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM transactions
            WHERE card_id=%s
            AND tx_time >= NOW() - INTERVAL 5 MINUTE
            """, (card_id,))

            recent_count = cursor.fetchone()["cnt"]

            # 최근 5분내 반복 결제 
            if recent_count >= 3:
                risk_score += 30
                reasons.append("5분내 반복결제")

            # 심야 거래
            hour = datetime.now().hour

            if 1 <= hour <= 5:
                risk_score += 15
                reasons.append("심야거래")

            # 초고액 결제
            if amount >= 5000000:
                risk_score += 30
                reasons.append("초고액결제")

            # 상태 결정
            if risk_score >= 60:
                status = "BLOCKED"

            elif risk_score >= 30:
                status = "REVIEW"

            else:
                status = "NORMAL"

            cursor.execute(
                """
                UPDATE transactions
                SET status=%s
                WHERE tx_id=%s
                """,
                (
                    status,
                    tx_id
                )
            )

            conn_exec.commit()

            if risk_score >= 30:

                cursor.execute(
                    """
                    INSERT INTO alert_logs
                    (
                        tx_id,
                        risk_score,
                        detect_reason
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        tx_id,
                        risk_score,
                        ", ".join(reasons)
                    )
                )

                conn_exec.commit()

            if status == "BLOCKED":

                st.sidebar.error(
                    f"⚠️ 차단됨 (위험도: {risk_score})"
                )

            elif status == "REVIEW":

                st.sidebar.warning(
                    f"🔎 추가 검토 필요 (위험도: {risk_score})"
                )

            else:

                st.sidebar.success(
                    f"✅ 정상 승인 (위험도: {risk_score})"
                )

    finally:

        conn_exec.close()

    st.rerun()


# --- [메인 화면] 상단 요약 지표 카드 (st.metric 활용) ---
conn_metrics = get_connection()
try:
  total_tx_count = pd.read_sql(
      "SELECT COUNT(*) as cnt FROM transactions", conn_metrics
  )["cnt"].iloc[0]
  blocked_tx_count = pd.read_sql(
      "SELECT COUNT(*) as cnt FROM transactions WHERE status = 'BLOCKED'",
      conn_metrics,
  )["cnt"].iloc[0]
  alert_count = pd.read_sql(
      "SELECT COUNT(*) as cnt FROM alert_logs", conn_metrics
  )["cnt"].iloc[0]
except:
  total_tx_count, blocked_tx_count, alert_count = 0, 0, 0
conn_metrics.close()

col1, col2, col3 = st.columns(3)
col1.metric(label="📦 전체 누적 거래 건수", value=f"{total_tx_count:,} 건")
col2.metric(
    label="🛡️ 차단된 위험 거래",
    value=f"{blocked_tx_count:,} 건",
    delta_color="inverse",
)
col3.metric(label="🚨 보안 경보(Alert)", value=f"{alert_count:,} 건")

st.markdown("---")

if blocked_tx_count > 0:

    st.warning(
        f"⚠️ 위험 거래 {blocked_tx_count}건 탐지"
    )

# 차트 데이터 조회

chart_conn = get_connection()

df_country = pd.read_sql("""
SELECT
merchant_country,
COUNT(*) cnt
FROM transactions
GROUP BY merchant_country
""", chart_conn)

df_status = pd.read_sql("""
SELECT
status,
COUNT(*) cnt
FROM transactions
GROUP BY status
""", chart_conn)

df_hour = pd.read_sql("""
SELECT
HOUR(tx_time) AS hour,
COUNT(*) AS cnt
FROM transactions
GROUP BY HOUR(tx_time)
ORDER BY hour
""", chart_conn)

chart_conn.close()

# 차트 출력

col_chart1, col_chart2 = st.columns(2)

with col_chart1:

    st.subheader("🌎 국가별 거래 현황")

    st.bar_chart(
        df_country.set_index(
            "merchant_country"
        )
    )

with col_chart2:

    st.subheader("🛡️ 거래 상태 분석")

    st.bar_chart(
        df_status.set_index(
            "status"
        )
    )

st.subheader("⏰ 시간대별 거래 현황")

st.bar_chart(
    df_hour.set_index(
        "hour"
    )
)

# 내 카드 맞춤형 조회 필터
st.subheader("🔍 내 카드 맞춤형 조회 필터")
filter_option = st.selectbox(
    "조회할 방식을 선택하세요", ["전체 카드 보기 (관리자 모드)"] + card_list
)

# 필터 적용 쿼리 작성
if filter_option == "전체 카드 보기 (관리자 모드)":
  query_alerts = """
        SELECT a.alert_id, t.card_id, t.amount, t.merchant_country, a.detect_reason, a.created_at
        FROM alert_logs a
        JOIN transactions t ON a.tx_id = t.tx_id
        ORDER BY a.created_at DESC LIMIT 10
    """
  query_tx = "SELECT * FROM transactions ORDER BY tx_time DESC LIMIT 10"
  params = None
else:
  query_alerts = """
        SELECT a.alert_id, t.card_id, t.amount, t.merchant_country, a.detect_reason, a.created_at
        FROM alert_logs a
        JOIN transactions t ON a.tx_id = t.tx_id
        WHERE t.card_id = %s
        ORDER BY a.created_at DESC LIMIT 10
    """
  query_tx = (
      "SELECT * FROM transactions WHERE card_id = %s ORDER BY tx_time DESC LIMIT"
      " 10"
  )
  params = (filter_option,)

# 데이터 조회 및 출력
conn_data = get_connection()
try:
  df_alerts = pd.read_sql(
      query_alerts, conn_data, params=params if params else None
  )
  df_tx = pd.read_sql(query_tx, conn_data, params=params if params else None)
except:
  df_alerts = pd.DataFrame()
  df_tx = pd.DataFrame()
conn_data.close()

# 탭(Tab) 레이아웃 구성
def highlight_status(row):

    if row["status"] == "BLOCKED":
        return ["background-color:#ffcccc"] * len(row)

    elif row["status"] == "REVIEW":
        return ["background-color:#fff3cd"] * len(row)

    return [""] * len(row)

tab1, tab2 = st.tabs(["📊 실시간 보안 경보 로그", "📋 내 카드 거래 내역"])

with tab1:

    st.markdown("### 🚨 최근 보안 경보 현황")

    if df_alerts.empty:

        st.info(
            "💡 선택한 카드에 발생한 보안 경보가 없습니다. 안전합니다!"
        )

    else:

        st.dataframe(
            df_alerts,
            width="stretch"
        )

with tab2:

    st.markdown("### 💳 최근 거래 내역")

    if df_tx.empty:

        st.info(
            "💡 해당 카드의 거래 내역이 없습니다."
        )

    else:

        st.dataframe(
            df_tx.style.apply(
                highlight_status,
                axis=1
            ),
            width="stretch"
        )
