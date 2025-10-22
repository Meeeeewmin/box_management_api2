# Box_management_api version 2 (2025.10.17)
echo ""
echo "To deploy on another server:"
echo "1. Copy both .tar.gz files"
echo "2. docker load < mariadb-10.11.tar.gz"
echo "3. docker load < iot-box-app.tar.gz"
echo "4. Run: ./run-all.sh"

*# 1. MariaDB 실행*

docker run -d \
  --name iot_box_db \
  -e MYSQL_ROOT_PASSWORD=rootpassword \
  -e MYSQL_DATABASE=iot_box_db \
  -e MYSQL_USER=iot_user \
  -e MYSQL_PASSWORD=iot_password \
  -v iot_box_mariadb_data:/var/lib/mysql \
  mariadb:10.11

*# 30초 대기*

sleep 30

*# 2. 애플리케이션 실행*

docker run -d \
  --name iot_box_app \
  --link iot_box_db:iot_box_db \
  -e DATABASE_URL=mysql+pymysql://iot_user:iot_password@iot_box_db:3306/iot_box_db \
  -p 80:80 \
  iot-box-app:latest

*# 3. 로그 확인*

docker logs -f iot_box_app
