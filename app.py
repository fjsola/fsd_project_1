import pandas as pd
import pymysql
import streamlit as st

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

# 앱이 켜질 때 Aiven DB에 테이블이 없으면 자동 생성
with conn.session as s:
  s.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            signup_date DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
  s.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            card_id VARCHAR(20) PRIMARY KEY,
            user_id INT,
            limit_amount INT DEFAULT 5000000,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)
  s.execute("""
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
    """)
  s.execute("""
        CREATE TABLE IF NOT EXISTS alert_logs (
            alert_id INT AUTO_INCREMENT PRIMARY KEY,
            tx_id INT,
            risk_score INT,
            detect_reason VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
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
  )


# 제목 및 스타일 타이틀
st.title("🚨 스마트 보안 FDS (이상 거래 탐지) 관제 시스템")
st.markdown("실시간 결제 시뮬레이션 및 내 카드 보안 모니터링 대시보드입니다.")
st.markdown("---")

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
st.sidebar.header("💳 실시간 결제 요청 시뮬레이터")
card_id = st.sidebar.selectbox("사용할 카드 선택", card_list)

amount = st.sidebar.number_input(
    "결제 금액 (원)", min_value=1000, max_value=10000000, value=50000, step=1000
)
country = st.sidebar.selectbox("결제 국가", ["KR", "US", "CN", "VN"])
ip_address = st.sidebar.text_input("접속 IP", "123.142.50.11")

if st.sidebar.button("🚀 결제 승인 요청", use_container_width=True):
  conn_exec = get_connection()
  try:
    with conn_exec.cursor() as cursor:
      # 1. 거래 내역 삽입
      cursor.execute(
          "INSERT INTO transactions (card_id, tx_time, amount, merchant_country,"
          " ip_address) VALUES (%s, NOW(), %s, %s, %s)",
          (card_id, amount, country, ip_address),
      )
      conn_exec.commit()

      # 2. 간단한 실시간 룰 검증 (200만원 초과 또는 해외 결제 시 차단)
      if amount > 2000000 or country != "KR":
        cursor.execute(
            "UPDATE transactions SET status = 'BLOCKED' WHERE tx_id ="
            " LAST_INSERT_ID()"
        )
        conn_exec.commit()
        st.sidebar.error("⚠️ [이상 거래 감지] 위험 거래로 차단되었습니다!")
      else:
        st.sidebar.success("✅ 정상 승인되었습니다.")
  finally:
    conn_exec.close()
  # 화면 새로고침 효과
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
tab1, tab2 = st.tabs(["📊 실시간 보안 경보 로그", "📋 내 카드 거래 내역"])

with tab1:
  st.markdown("### 🚨 최근 보안 경보 현황")
  if df_alerts.empty:
    st.info("💡 선택한 카드에 발생한 보안 경보가 없습니다. 안전합니다!")
  else:
    st.dataframe(df_alerts, use_container_width=True)

with tab2:
  st.markdown("### 💳 최근 거래 내역")
  if df_tx.empty:
    st.info("💡 해당 카드의 거래 내역이 없습니다.")
  else:
    st.dataframe(df_tx, use_container_width=True)
