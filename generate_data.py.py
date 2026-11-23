import random
from datetime import datetime, timedelta
import pymysql
from faker import Faker

fake = Faker("ko_KR")

# MySQL 데이터베이스 연결 설정
connection = pymysql.connect(
    host="localhost",
    user="root",
    password="mysql1234",  # 본인 비밀번호로 수정
    database="fds_system",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

try:
  with connection.cursor() as cursor:
    # 1. 가상 사용자 5명 생성
    for i in range(1, 6):
      cursor.execute(
          "INSERT INTO users (name, phone) VALUES (%s, %s)",
          (fake.name(), fake.phone_number()),
      )
    connection.commit()

    # 2. 카드 정보 생성 (사용자당 1개씩)
    for i in range(1, 6):
      card_num = f"4000-1234-5678-000{i}"
      cursor.execute(
          "INSERT INTO cards (card_id, user_id, limit_amount) VALUES (%s, %s,"
          " %s)",
          (card_num, i, 3000000),
      )
    connection.commit()

    # 3. 대량 거래 데이터(더미) 생성 (정상 + 이상 거래 시나리오)
    cards = [f"4000-1234-5678-000{i}" for i in range(1, 6)]
    base_time = datetime.now() - timedelta(days=1)

    print("더미 데이터 생성 중...")
    for _ in range(1000):  # 1000건 생성 (발표용으로는 10만 건까지 늘려도 좋음)
      card_id = random.choice(cards)
      tx_time = base_time + timedelta(
          minutes=random.randint(1, 1440)
      )  # 하루 동안 무작위 시간
      amount = random.randint(10000, 300000)
      country = "KR"
      ip_address = f"192.168.0.{random.randint(1, 255)}"

      # [이상 거래 시나리오 주입] 특정 카드에 단시간 해외 고액 결제 유발
      if card_id == "4000-1234-5678-0001" and random.random() < 0.05:
        country = "US"
        amount = 2500000

      cursor.execute(
          "INSERT INTO transactions (card_id, tx_time, amount, merchant_country,"
          " ip_address) VALUES (%s, %s, %s, %s, %s)",
          (card_id, tx_time, amount, country, ip_address),
      )
    connection.commit()
    print("더미 데이터 적재 완료!")

finally:
  connection.close()