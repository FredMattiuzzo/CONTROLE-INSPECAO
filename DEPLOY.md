# Guia de Deploy - Sistema de Controle de Inspeção

Este guia descreve o passo a passo para deploy do sistema em um servidor Ubuntu Server LTS.

## 📋 Pré-requisitos

- Ubuntu Server 24.04 LTS (ou 22.04 LTS)
- Acesso SSH ao servidor
- Usuário com privilégios sudo
- 2GB RAM mínimo
- 10GB de espaço em disco

## 🔧 1. Preparação do Servidor

### 1.1. Atualizar o sistema

```bash
sudo apt update
sudo apt upgrade -y
```

### 1.2. Instalar dependências do sistema

```bash
sudo apt install -y python3.11 python3.11-venv python3-pip nginx supervisor git
```

### 1.3. Criar usuário para a aplicação (opcional, mas recomendado)

```bash
sudo adduser --disabled-password --gecos "" saiapp
sudo usermod -aG sudo saiapp
```

## 📦 2. Configuração da Aplicação

### 2.1. Fazer login com o usuário criado

```bash
su - saiapp
```

### 2.2. Clonar o projeto ou transferir arquivos

**Opção A - Via Git (se houver repositório):**
```bash
cd /home/saiapp
git clone <url_do_repositorio> CONTROLE-INSPECAO
```

**Opção B - Via SCP/SFTP (transferir da máquina local):**
```bash
# No Windows (PowerShell), execute:
scp -r "C:\Users\frederico.neto\PROJECTS\CONTROLE_INSPECAO\CONTROLE-INSPECAO" saiapp@10.1.1.50:/home/saiapp/
```

### 2.3. Criar e ativar ambiente virtual

```bash
cd /home/saiapp/CONTROLE-INSPECAO
python3.11 -m venv venv
source venv/bin/activate
```

### 2.4. Instalar dependências Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### 2.5. Configurar variáveis de ambiente

```bash
nano /home/saiapp/CONTROLE-INSPECAO/.env
```

Adicione o seguinte conteúdo:

```env
DEBUG=0
ALLOWED_HOSTS=10.1.1.50,localhost,127.0.0.1,seu-dominio.com
SECRET_KEY=sua-chave-secreta-super-segura-aqui
```

### 2.6. Atualizar settings.py para ler .env

Edite o arquivo `sai_project/settings.py` e adicione no topo:

```python
from pathlib import Path
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
```

Instale python-dotenv:
```bash
pip install python-dotenv
```

### 2.7. Executar migrações e coletar arquivos estáticos

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 2.8. Criar superusuário

```bash
python manage.py createsuperuser
```

### 2.9. Testar a aplicação

```bash
python manage.py runserver 0.0.0.0:8000
```

Acesse `http://10.1.1.50:8000` para verificar se funciona. Pressione `Ctrl+C` para parar.

## 🚀 3. Configuração do Gunicorn

### 3.1. Criar arquivo de configuração do Gunicorn

```bash
nano /home/saiapp/CONTROLE-INSPECAO/gunicorn_config.py
```

Adicione:

```python
import multiprocessing

# Diretório de trabalho
chdir = '/home/saiapp/CONTROLE-INSPECAO'

# Bind
bind = '127.0.0.1:8000'

# Workers (para 2GB RAM, use 2-3 workers)
workers = 2
threads = 2
worker_class = 'sync'

# Logging
accesslog = '/home/saiapp/CONTROLE-INSPECAO/logs/gunicorn_access.log'
errorlog = '/home/saiapp/CONTROLE-INSPECAO/logs/gunicorn_error.log'
loglevel = 'info'

# Timeout
timeout = 120

# Daemon mode
daemon = False
```

### 3.2. Criar diretório de logs

```bash
mkdir -p /home/saiapp/CONTROLE-INSPECAO/logs
```

### 3.3. Testar Gunicorn manualmente

```bash
cd /home/saiapp/CONTROLE-INSPECAO
source venv/bin/activate
gunicorn sai_project.wsgi:application -c gunicorn_config.py
```

Pressione `Ctrl+C` para parar após verificar que funciona.

## 🔄 4. Configuração do Supervisor (Process Manager)

### 4.1. Criar arquivo de configuração

```bash
sudo nano /etc/supervisor/conf.d/sai_project.conf
```

Adicione:

```ini
[program:sai_project]
command=/home/saiapp/CONTROLE-INSPECAO/venv/bin/gunicorn sai_project.wsgi:application -c /home/saiapp/CONTROLE-INSPECAO/gunicorn_config.py
directory=/home/saiapp/CONTROLE-INSPECAO
user=saiapp
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/saiapp/CONTROLE-INSPECAO/logs/supervisor.log
environment=PATH="/home/saiapp/CONTROLE-INSPECAO/venv/bin"
```

### 4.2. Atualizar e iniciar Supervisor

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start sai_project
sudo supervisorctl status
```

## 🌐 5. Configuração do Nginx (Proxy Reverso)

### 5.1. Criar arquivo de configuração do site

```bash
sudo nano /etc/nginx/sites-available/sai_project
```

Adicione:

```nginx
server {
    listen 80;
    server_name 10.1.1.50;

    client_max_body_size 10M;

    # Logs
    access_log /var/log/nginx/sai_project_access.log;
    error_log /var/log/nginx/sai_project_error.log;

    # Arquivos estáticos
    location /static/ {
        alias /home/saiapp/CONTROLE-INSPECAO/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy para Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

### 5.2. Habilitar o site

```bash
sudo ln -s /etc/nginx/sites-available/sai_project /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove site padrão
```

### 5.3. Testar e reiniciar Nginx

```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

## 🔒 6. Segurança e Firewall

### 6.1. Configurar UFW (firewall)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

### 6.2. Ajustar permissões

```bash
sudo chown -R saiapp:www-data /home/saiapp/CONTROLE-INSPECAO
sudo chmod -R 755 /home/saiapp/CONTROLE-INSPECAO
```

## ✅ 7. Verificação Final

### 7.1. Verificar status dos serviços

```bash
# Supervisor
sudo supervisorctl status sai_project

# Nginx
sudo systemctl status nginx

# Firewall
sudo ufw status
```

### 7.2. Acessar a aplicação

Abra o navegador e acesse:
- **http://10.1.1.50**

### 7.3. Verificar logs em caso de problemas

```bash
# Logs do Gunicorn
tail -f /home/saiapp/CONTROLE-INSPECAO/logs/gunicorn_error.log

# Logs do Supervisor
tail -f /home/saiapp/CONTROLE-INSPECAO/logs/supervisor.log

# Logs do Nginx
sudo tail -f /var/log/nginx/sai_project_error.log
```

## 🔄 8. Comandos Úteis para Manutenção

### Reiniciar a aplicação

```bash
sudo supervisorctl restart sai_project
```

### Atualizar código (após mudanças)

```bash
cd /home/saiapp/CONTROLE-INSPECAO
source venv/bin/activate
git pull  # ou transferir arquivos novos via SCP
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart sai_project
```

### Ver logs em tempo real

```bash
sudo supervisorctl tail -f sai_project
```

### Backup do banco de dados

```bash
cp /home/saiapp/CONTROLE-INSPECAO/db.sqlite3 /home/saiapp/backup_$(date +%Y%m%d_%H%M%S).sqlite3
```

## 📊 9. Monitoramento (Opcional)

### 9.1. Instalar htop para monitorar recursos

```bash
sudo apt install htop
htop
```

### 9.2. Verificar uso de memória

```bash
free -h
```

### 9.3. Verificar uso de disco

```bash
df -h
```

## 🆘 10. Troubleshooting

### Problema: Erro 502 Bad Gateway

```bash
# Verificar se Gunicorn está rodando
sudo supervisorctl status sai_project

# Reiniciar
sudo supervisorctl restart sai_project
```

### Problema: Arquivos estáticos não carregam

```bash
# Coletar novamente
cd /home/saiapp/CONTROLE-INSPECAO
source venv/bin/activate
python manage.py collectstatic --noinput

# Verificar permissões
sudo chown -R saiapp:www-data /home/saiapp/CONTROLE-INSPECAO/staticfiles
```

### Problema: Mudanças no código não aparecem

```bash
# Reiniciar Gunicorn via Supervisor
sudo supervisorctl restart sai_project

# Limpar cache do navegador
```

## 📝 11. Checklist de Deploy

- [ ] Ubuntu Server instalado e atualizado
- [ ] Python 3.11, Nginx e Supervisor instalados
- [ ] Código transferido para `/home/saiapp/CONTROLE-INSPECAO`
- [ ] Ambiente virtual criado e dependências instaladas
- [ ] Variáveis de ambiente configuradas (`.env`)
- [ ] Migrações executadas
- [ ] Arquivos estáticos coletados
- [ ] Superusuário criado
- [ ] Gunicorn configurado e testado
- [ ] Supervisor configurado e rodando
- [ ] Nginx configurado e rodando
- [ ] Firewall configurado
- [ ] Aplicação acessível via navegador
- [ ] Logs verificados sem erros

## 🎉 Conclusão

Seu sistema está agora em produção! Para suporte adicional, consulte:
- [Documentação Django](https://docs.djangoproject.com/)
- [Gunicorn Docs](https://docs.gunicorn.org/)
- [Nginx Docs](https://nginx.org/en/docs/)

---

**Última atualização:** Fevereiro 2026
