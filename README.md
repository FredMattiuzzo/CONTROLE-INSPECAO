# CONTROLE-INSPECAO (SAI)

Sistema de Agendamento de Inspeções (SAI) construído em Django.

Este repositório contém:
- Um app Django chamado `schedule` com a agenda semanal/mensal e CRUD de entradas (inspeções e ausências)
- Autenticação via Django (tela de login em `/` e logout), com permissões para gestores e inspetores
- UI em Português (Brasil), com modal para criar entradas e cartões compactos com “Detalhes”


## Sumário

- Visão geral da arquitetura
- Como rodar localmente (Windows/PowerShell)
- Fluxo de autenticação e permissões
- Modelos e regras de negócio
- Formulário e validações
- Views, URLs e rotas principais
- Templates e comportamento do modal
- Admin e “Acesso superior”
- Dicas para uso em LAN (ALLOWED_HOSTS)
- Solução de problemas comuns
- Próximos passos


## Visão geral da arquitetura

- Backend: Django 5.2.x, SQLite local (`db.sqlite3`)
- App: `schedule`
	- Modelos: `User`, `InspectorProfile`, `ScheduleEntry`
	- Formulário principal: `ScheduleEntryForm`
	- Views: agendas semanal/mensal e CRUD de entradas
	- Templates: base, semanal, mensal e parcial do modal
- Autenticação: `django.contrib.auth` (Login/Logout). O app `schedule` faz o “espelhamento” de usuários em seu próprio modelo `User` para regras específicas (papel Gestor/Inspetor) e para registrar quem concluiu uma inspeção.

Arquivos importantes:
- `sai_project/urls.py` — roteamento de nível de projeto (login em `/`, agenda em `/agenda/`, admin em `/admin/`)
- `schedule/urls.py` — rotas do app (semanal, mensal, CRUD, acesso superior)
- `schedule/models.py` — modelos de domínio e regras de persistência
- `schedule/forms.py` — regras de validação e normalização de formulário
- `schedule/views.py` — lógica de exibição e permissões
- `schedule/templates/` — base e páginas da agenda, além do modal de criação


## Como rodar localmente (Windows/PowerShell)

Pré-requisitos:
- Python 3.11+ (recomendado 3.12 ou 3.13)
- Pip disponível no PATH

Passos típicos:
1) (Opcional, mas recomendado) Criar um ambiente virtual
	 - PowerShell: python -m venv .venv; .\.venv\Scripts\Activate.ps1
2) Instalar dependências
	 - pip install -r requirements.txt
	 - Se não quiser usar o arquivo, instale ao menos Django 5.2.x: pip install "Django>=5.2,<5.3"
3) Aplicar migrações
	 - python manage.py migrate
4) Criar um superusuário do Django (para acessar /admin)
	 - python manage.py createsuperuser
5) Rodar o servidor
	 - python manage.py runserver

Após subir:
- Acesse http://127.0.0.1:8000/ para a tela de login
- A agenda semanal fica em http://127.0.0.1:8000/agenda/
- A visão mensal em http://127.0.0.1:8000/agenda/mensal/
- O admin Django em http://127.0.0.1:8000/admin/


## Fluxo de autenticação e permissões

- Login: a raiz `/` serve `LoginView` (template `registration/login.html`).
- Logout: link no topo direito da interface, retorna ao login.
- Permissões na UI:
	- Gestores: podem criar/editar/excluir entradas de qualquer inspetor.
	- Inspetores: só podem gerenciar as próprias entradas.

Como o app decide se você é Gestor ou Inspetor?
- Há dois níveis de usuário:
	1) Usuário Django (auth) — controla login e `is_staff`/`is_superuser`.
	2) Usuário do SAI (`schedule.models.User`) — define o papel “Gestor” ou “Inspetor” e é usado para vincular `InspectorProfile` e para preencher `concluded_by` quando uma inspeção é concluída.

Regra efetiva de “Gestor” no sistema:
- Se o usuário Django tiver `is_staff = True`, ele é tratado como Gestor (mesmo se não existir registro correspondente no modelo `schedule.User`).
- Alternativamente, se existir um `schedule.User` com `role = MANAGER` e `username` igual ao do usuário Django, também é Gestor.

Para Inspetores:
- É necessário criar um `schedule.User` com `role = INSPECTOR` e um `InspectorProfile` ativo para esse usuário.
- Sem esse vínculo, o inspetor não terá permissão para criar/editar entradas (o sistema bloqueia o acesso).

Observação: Para que o campo “concluded_by” seja registrado ao concluir uma inspeção, é recomendável que o usuário (mesmo gestor) tenha uma entrada em `schedule.User` com o mesmo `username` do Django Auth.


## Modelos e regras de negócio

Local: `schedule/models.py`

- `User`
	- Campos: `username` (único), `password_hash` (não utilizado para login Django), `role` (INSPECTOR/Gestor)
	- Função: refere-se à camada de domínio do SAI; mapeia o `username` do Django para um papel.

- `InspectorProfile`
	- Campos: `user` (OneToOne com `User`), `full_name`, `is_active`
	- Função: perfil ativo do inspetor para aparecer na agenda e criar entradas.

- `ScheduleEntry`
	- Campos principais: `entry_type` (Inspeção/Ausência), `inspector`, `date`, `sa_number`, `content`
	- Campos de inspeção: `inspection_type` (Interna/Externa), `status` (Agendada/Concluída/Reprovada)
	- Metadados de conclusão: `concluded_by` (`User` do SAI) e `concluded_at`
	- Regras no `save()`:
		- Para Ausência: zera `inspection_type`, `status`, `concluded_by`, `concluded_at`.
		- Para Inspeção: se `status` vazio, assume “Agendada”. Se não “Concluída/Reprovada”, limpa `concluded_by/at`.


## Formulário e validações

Local: `schedule/forms.py` (`ScheduleEntryForm`)

- Monta os choices com rótulos PT-BR e placeholders “Selecione”.
- Define campos opcionais adequados (ex.: SA, status, tipo de inspeção).
- Queryset de inspetores:
	- Gestor: vê todos os inspetores ativos.
	- Inspetor: só o próprio perfil (pré-selecionado).
- Validações em `clean()`:
	- Para Inspeção: exige `inspection_type`; impede agendar inspeção em dia com ausência do mesmo inspetor.
	- Para Ausência: limpa `inspection_type` e `status`.
- Em `save()`:
	- Normaliza metadados de conclusão (`concluded_by/at`) quando o status vira “Concluída”/“Reprovada”.
	- Garante que inspetor não-gestor só salve para seu próprio perfil.


## Views, URLs e rotas principais

Projeto (`sai_project/urls.py`):
- `/` → `LoginView` (template `registration/login.html`)
- `/accounts/` → rotas padrão de auth (login/logout)
- `/agenda/` → inclui rotas do app `schedule`
- `/admin/` → Django admin

App (`schedule/urls.py`):
- `/agenda/` → `WeeklyScheduleView` (semanal)
- `/agenda/mensal/` → `MonthlyScheduleView` (mensal)
- `/agenda/entradas/nova/` → criar entrada (modal ou página)
- `/agenda/entradas/<pk>/editar/` → editar
- `/agenda/entradas/<pk>/excluir/` → excluir
- `/agenda/acesso-superior/` → página com atalho para o admin (somente para quem tem permissão)

Mixins e regras:
- `ScheduleUserMixin` faz o “bridge” entre Django Auth e `schedule.User`, e define `is_manager()` aceitando `is_staff`.
- `ScheduleEntryQuerysetMixin` restringe o queryset por inspetor para não-gestores.
- `ScheduleEntryFormMixin` injeta contexto de permissão, redirecionamento (`next`) e cria o form com o usuário autenticado.


## Templates e comportamento do modal

Local: `schedule/templates/schedule/`

- `base.html` — layout, cabeçalho com usuário logado e logout, estilos e navegação Semanal/Mensal.
- `weekly.html` — grade semanal por inspetor (linhas) e dias (colunas), botão “Nova entrada” e “+” em cada célula.
- `monthly.html` — visão mensal com cartões compactos; também possui “Nova entrada” e “+” por dia.
- `_entry_modal.html` — formulário em modal reutilizado nas visões semanal e mensal. Ele:
	- Prefill de Data e Inspetor ao abrir via “+”.
	- Oculta/mostra campos de inspeção conforme o tipo (Inspeção/Ausência).
	- Reabre automaticamente mostrando erros se houver validações.

Controles de edição:
- Ícones de Editar/Excluir aparecem quando o usuário tem permissão (gestor ou dono da entrada).
- O cartão mostra apenas um resumo; “Detalhes” expande dados complementares.


## Admin e “Acesso superior”

- Admin Django: `/admin/`
	- `schedule.admin` registra `User`, `InspectorProfile` e `ScheduleEntry` com filtros e buscas úteis.
- Página “Acesso superior”: `/agenda/acesso-superior/`
	- Exibe atalho para o admin somente para quem tem permissão efetiva (Gestor/`is_staff`).

Cadastro inicial (recomendado):
1) Crie um superusuário (`createsuperuser`) para acessar `/admin/`.
2) No admin, crie registros em `schedule.User` com `username` igual ao do Django Auth:
	 - Para gestores: `role = MANAGER`.
	 - Para inspetores: `role = INSPECTOR` e crie também um `InspectorProfile` ativo.


## Dicas para uso em LAN (ALLOWED_HOSTS)

Em desenvolvimento, para acessar via IP da rede local:
- Edite `sai_project/settings.py` e ajuste `ALLOWED_HOSTS` para conter o IP da máquina (por ex.: `['127.0.0.1', '192.168.0.100']`) ou, durante testes, `['*']`.
- Inicie o servidor escutando na rede: `python manage.py runserver 0.0.0.0:8000`
- Acesse de outro dispositivo com `http://<IP-DA-SUA-MÁQUINA>:8000/`.


## Solução de problemas comuns

- “DisallowedHost” ao acessar por IP na rede
	- Ajuste `ALLOWED_HOSTS` (ver seção de LAN) e reinicie o servidor.

- 403 Forbidden ao tentar criar entrada
	- Normalmente indica que o usuário logado não é gestor e não possui `InspectorProfile` ativo vinculado.
	- Crie o `schedule.User` (papel `INSPECTOR`) e o `InspectorProfile` correspondente.

- “TemplateDoesNotExist: registration/login.html”
	- Confirme a existência de `schedule/templates/registration/login.html`.

- Não aparecem inspetores no formulário
	- Para não-gestor: somente o próprio `InspectorProfile` é listado. Verifique se o perfil existe e está ativo.

- Entrada criada não aparece na semana
	- A agenda semanal atual não aplica filtros “escondidos”. Verifique se está olhando na semana correta/dia correto e para o inspetor certo.


## Próximos passos (sugestões)

- Adicionar testes automatizados para validações do formulário e permissões.
- Criar fixtures ou scripts de seed para popular usuários/perfis de demo.
- Melhorar pipeline de estáticos (coleta e minificação) para produção.
- Refinar papéis e permissões (ex.: grupos do Django em vez de modelo `User` próprio).


## Licença

Uso interno. Ajuste de licença conforme a necessidade do projeto.

