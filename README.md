# CONTROLE-INSPECAO (SAI)

Sistema de Agendamento de Inspeções (SAI) construído em Django.

O aplicativo é uma agenda (semanal e mensal) para organizar inspeções e outros tipos de entradas por inspetor e por data, com autenticação, permissões e rotinas de CRUD.

## Funcionalidades (resumo)

- Agenda semanal (Seg–Sex) por inspetor, com cartões por dia.
- Agenda mensal em formato de grade (cards por dia) e navegação entre meses.
- Tipos de entrada:
  - **Inspeção** (Interna ou Externa)
  - **Ausência**
  - **Relatório**
- Status de inspeção: **Agendada**, **Concluída**, **Reprovada**.
- Inspeção **Externa** pode ter campo **Cliente** (exibido nos cards).
- Busca global por palavras-chave (inclui SA, descrição, cliente e nome do inspetor): redireciona para a semana correta e destaca o card.
- Mover entradas (drag and drop na agenda semanal) com validação de permissão.
- Controle de permissões:
  - **Gestor**: pode gerenciar entradas de qualquer inspetor.
  - **Inspetor**: gerencia somente as próprias entradas.

## Stack / arquitetura

- Django 5.2.x
- Banco: SQLite (arquivo [db.sqlite3](db.sqlite3))
- App principal: `schedule`

Arquivos úteis:

- [manage.py](manage.py)
- [sai_project/settings.py](sai_project/settings.py)
- [schedule/urls.py](schedule/urls.py)
- [schedule/views.py](schedule/views.py)
- [schedule/models.py](schedule/models.py)
- [schedule/templates/schedule/](schedule/templates/schedule/)

## Rotas principais

- `/` → login
- `/agenda/` → agenda semanal
- `/agenda/mensal/` → agenda mensal
- `/agenda/busca/?q=...` → busca global (redireciona para `/agenda/?week=...&focus=...`)
- `/admin/` → admin Django

## Como rodar (Docker)

Pré-requisitos:

- Docker + Docker Compose

Subir o projeto:

- `docker compose up --build`

Primeira execução (migrations e usuário admin):

- `docker compose exec web python manage.py migrate`
- `docker compose exec web python manage.py createsuperuser`

Acessar:

- http://localhost:8000/ (login)
- http://localhost:8000/agenda/ (semanal)
- http://localhost:8000/agenda/mensal/ (mensal)

Observação importante (ALLOWED_HOSTS):

- O projeto atualmente define `ALLOWED_HOSTS` fixo em [sai_project/settings.py](sai_project/settings.py). Se você acessar via `localhost`/`127.0.0.1` e receber **DisallowedHost**, inclua `localhost` e `127.0.0.1` nessa lista.

## Como rodar (local / Windows)

Pré-requisitos:

- Python 3.11+

Passo a passo (PowerShell):

- `python -m venv .venv`
- `.\.venv\Scripts\Activate.ps1`
- `pip install -r requirements.txt`
- `python manage.py migrate`
- `python manage.py createsuperuser`
- `python manage.py runserver`

Acessar:

- http://127.0.0.1:8000/

## Cadastro inicial (usuários e perfis)

O sistema usa dois níveis:

1) **Django Auth** (login /admin, `is_staff`, `is_superuser`)
2) Tabelas do app **schedule** para regras de domínio:
   - `schedule.User` (papel) e `InspectorProfile` (inspetor ativo)

Regra de permissão de gestor:

- Se o usuário Django tem `is_staff = True`, ele é tratado como **Gestor**.
- Alternativamente, um registro `schedule.User` com `role = MANAGER` e `username` igual ao do Django também é considerado Gestor.

Para um inspetor conseguir usar a agenda:

- Crie um `schedule.User` com `role = INSPECTOR` e `username` igual ao usuário do Django.
- Crie um `InspectorProfile` ativo para esse `schedule.User`.

Dica: para registrar corretamente `concluded_by` quando marcar uma inspeção como concluída/reprovada, crie também o `schedule.User` para quem irá concluir.

\## Busca global (como funciona)

- Use o campo de busca na interface (ou acesse `/agenda/busca/?q=TERMO`).
- O backend procura por `SA`, conteúdo, cliente e nome do inspetor.
- Se houver vários resultados, a navegação usa um índice (`i`) e o total (`total`) e “pula” automaticamente para a semana do próximo resultado, destacando o card via `focus`.

## Problemas comuns

- **DisallowedHost**: ajuste `ALLOWED_HOSTS` em [sai_project/settings.py](sai_project/settings.py).
- **403/sem permissão**: confirme se o usuário tem `is_staff` (gestor) ou se existe `schedule.User` + `InspectorProfile` ativo (inspetor).
- **Não aparece para quem concluiu**: crie `schedule.User` com o mesmo `username` do usuário do Django.

## Licença

Uso interno do projeto.

