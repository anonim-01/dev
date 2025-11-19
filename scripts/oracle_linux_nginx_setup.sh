#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "[hata] Bu betiği sudo ile (root yetkisiyle) çalıştırmalısınız." >&2
    exit 1
fi

APP_DIR=${APP_DIR:-/home/ayzio/ekart-dolum-iade-dev}
APP_USER=${APP_USER:-${SUDO_USER:-$(logname 2>/dev/null || whoami)}}
REPO_URL=${REPO_URL:-https://github.com/ayzio/ekart-dolum-iade-dev.git}
REPO_REF=${REPO_REF:-main}
DOMAIN=${DOMAIN:-example.com}
WWW_DOMAIN=${WWW_DOMAIN:-www.${DOMAIN}}
PYTHON_BIN=${PYTHON_BIN:-python3.11}
SUPERVISOR_CONF=/etc/supervisor/conf.d/ekart.conf
NGINX_CONF=/etc/nginx/conf.d/ekart.conf
LOG_DIR_APP=/var/log/ekart
LOG_DIR_GUNICORN=/var/log/gunicorn
SERVICE_USER=${SERVICE_USER:-nginx}
SUPERVISORCTL_BIN=$(command -v supervisorctl || true)

if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    echo "[!] ${SERVICE_USER} kullanıcısı bulunamadı, ${APP_USER} kullanılacak"
    SERVICE_USER=${APP_USER}
fi

HAVE_SYSTEMCTL=1
if ! command -v systemctl >/dev/null 2>&1 || ! systemctl list-units >/dev/null 2>&1; then
    HAVE_SYSTEMCTL=0
fi

systemctl_safe() {
    if [[ ${HAVE_SYSTEMCTL} -eq 1 ]]; then
        systemctl "$@"
    else
        echo "[!] systemctl '$*' atlandı (systemd mevcut değil)"
        return 0
    fi
}

supervisorctl_safe() {
    if [[ -n "${SUPERVISORCTL_BIN}" ]]; then
        ${SUPERVISORCTL_BIN} "$@" || echo "[!] supervisorctl '$*' başarısız oldu"
    else
        echo "[!] supervisorctl bulunamadı, adım atlandı"
    fi
}

STEP() {
    echo -e "\n[+] $1";
}

STEP "Paket listeleri güncelleniyor"
dnf update -y

STEP "Oracle EPEL deposu etkinleştiriliyor"
dnf install -y oracle-epel-release-el9
dnf config-manager --enable ol9_developer_EPEL || true

STEP "Bağımlılıklar kuruluyor"
dnf install -y nginx git ${PYTHON_BIN} policycoreutils-python-utils firewalld supervisor || true
${PYTHON_BIN} -m ensurepip --upgrade || true
${PYTHON_BIN} -m pip install --upgrade pip || true
if ! rpm -q supervisor &>/dev/null; then
    ${PYTHON_BIN} -m pip install supervisor
fi
systemctl_safe enable --now nginx
systemctl_safe enable --now firewalld

STEP "Depo dizini hazırlanıyor (${APP_DIR})"
mkdir -p "${APP_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
cd "${APP_DIR}"
if [[ -d .git ]]; then
    sudo -u "${APP_USER}" git pull --ff-only
elif [[ -z "$(ls -A . 2>/dev/null)" ]]; then
    sudo -u "${APP_USER}" git clone "${REPO_URL}" .
else
    echo "[!] ${APP_DIR} dizini boş değil; mevcut içeriği kullanıyorum"
fi

STEP "Python sanal ortamı ve bağımlılıklar kuruluyor"
sudo -u "${APP_USER}" ${PYTHON_BIN} -m venv venv
sudo -u "${APP_USER}" bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"

if [[ ! -f .env && -f .env.example ]]; then
    STEP ".env dosyası örnekten oluşturuluyor"
    sudo -u "${APP_USER}" cp .env.example .env
fi

STEP "Gunicorn yapılandırması oluşturuluyor"
cat > "${APP_DIR}/gunicorn_config.py" <<'GUNICORN'
bind = "127.0.0.1:8000"
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5
errorlog = "/var/log/gunicorn/error.log"
accesslog = "/var/log/gunicorn/access.log"
loglevel = "info"
GUNICORN
chown "${APP_USER}:${APP_USER}" "${APP_DIR}/gunicorn_config.py"

STEP "Log dizinleri hazırlanıyor"
mkdir -p "${LOG_DIR_APP}" "${LOG_DIR_GUNICORN}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${LOG_DIR_APP}" "${LOG_DIR_GUNICORN}"

STEP "Supervisor program tanımı uygulanıyor"
mkdir -p "$(dirname "${SUPERVISOR_CONF}")"
cat > "${SUPERVISOR_CONF}" <<SUP
[program:ekart]
command=${APP_DIR}/venv/bin/gunicorn -c gunicorn_config.py main:app
directory=${APP_DIR}
user=${SERVICE_USER}
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=${LOG_DIR_APP}/err.log
stdout_logfile=${LOG_DIR_APP}/out.log
environment=PATH=${APP_DIR}/venv/bin
SUP
supervisorctl_safe reread
supervisorctl_safe update
supervisorctl_safe restart ekart

STEP "Nginx site yapılandırması yazılıyor"
cat > "${NGINX_CONF}" <<NGINX
server {
    listen 80;
    server_name ${DOMAIN} ${WWW_DOMAIN};

    deny 185.67.32.0/22;
    deny 185.67.35.0/24;

    client_max_body_size 10M;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    location /assets/ {
        alias ${APP_DIR}/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
        proxy_buffering off;
    }
}
NGINX

STEP "SELinux bağlamları ayarlanıyor"
semanage fcontext -a -t httpd_sys_content_t "${APP_DIR}(/.*)?" || true
restorecon -Rv "${APP_DIR}"
setsebool -P httpd_can_network_connect 1

STEP "Firewall kuralları uygulanıyor"
if command -v firewall-cmd >/dev/null 2>&1; then
    firewall-cmd --permanent --add-service=http || echo "[!] firewall-cmd http kuralı eklenemedi"
    firewall-cmd --permanent --add-service=https || echo "[!] firewall-cmd https kuralı eklenemedi"
    firewall-cmd --reload || echo "[!] firewall-cmd reload başarısız"
else
    echo "[!] firewall-cmd bulunamadı, adım atlandı"
fi

STEP "Nginx test ediliyor ve yeniden yükleniyor"
nginx -t
systemctl_safe reload nginx

cat <<POST

Kurulum tamamlandı.
- Kaynak dizini: ${APP_DIR}
- Supervisor programı: ekart
- Nginx konfigi: ${NGINX_CONF}

Cloudflare DNS'inizi bu sunucunun public IP'sine yönlendirmeyi ve SSL sertifikası için Certbot veya Cloudflare Full (Strict) modunu etkinleştirmeyi unutmayın.
POST
