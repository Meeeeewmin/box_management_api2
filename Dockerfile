FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY main.py .
COPY index.html /usr/share/nginx/html/

# Nginx 설정 복사
COPY nginx.conf /etc/nginx/sites-available/default

# Supervisor 설정
RUN echo "[supervisord]\n\
nodaemon=true\n\
user=root\n\
\n\
[program:api]\n\
command=/usr/local/bin/uvicorn main:app --host 127.0.0.1 --port 8000\n\
directory=/app\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
priority=1\n\
\n\
[program:nginx]\n\
command=/bin/bash -c 'sleep 3 && /usr/sbin/nginx -g \"daemon off;\"'\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
priority=2" > /etc/supervisor/conf.d/supervisord.conf

# 포트 노출
EXPOSE 80

# 환경 변수 (기본값)
ENV DATABASE_URL=mysql+pymysql://iot_user:iot_password@iot_box_db:3306/iot_box_db

# Supervisor 실행
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
