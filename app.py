import streamlit as st
import pymysql

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

# DB 연결 함수
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

# --- 로그인 화면 ---
if not st.session_state.logged_in:
    st.markdown("# 🚨 Smart FDS Security Center")
    st.markdown("### 로그인 및 권한 선택")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("👨‍💼 관리자 로그인")
        admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw_input")
        if st.button("관리자로 로그인", use_container_width=True):
            # 간단한 관리자 비밀번호 검증 (예: '1234')
            if admin_pw == "1234":
                st.session_state.logged_in = True
                st.session_state.role = "admin"
                st.session_state.user_name = "시스템 관리자"
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")

    with col2:
        st.subheader("👤 일반 사용자 로그인")
        
        # DB에서 카드 목록 및 사용자 정보 불러오기
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
            # 이름 찾기
            matched_user = next((item['name'] for item in card_users if item['card_id'] == selected_card_id), "사용자")
            st.session_state.user_name = matched_user
            st.rerun()

# --- 로그인 이후 메인 화면 ---
else:
    st.sidebar.success(f"현재 접속: **{st.session_state.user_name}** ({'관리자' if st.session_state.role == 'admin' else '일반 사용자'})")
    
    if st.sidebar.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.user_name = ""
        st.session_state.card_id = ""
        st.rerun()

    st.markdown("# 🚨 Smart FDS Security Center")
    st.markdown("---")
    
    if st.session_state.role == "admin":
        st.info("👋 관리자님 환영합니다! 좌측 사이드바의 **1_👨‍💼_admin_dashboard** 페이지를 선택하여 전체 관제 시스템을 이용해 주세요.")
    else:
        st.info(f"👋 {st.session_state.user_name}님 환영합니다! 좌측 사이드바의 **2_👤_user_dashboard** 페이지를 선택하여 본인의 카드 내역을 확인하세요.")
