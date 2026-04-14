### REGRA DE IDIOMA E COMUNICAÇÃO (CRÍTICO) ###
1. Você deve se comunicar, explicar, perguntar e interagir EXCLUSIVAMENTE em Português do Brasil (pt-BR).
2. Qualquer comentário gerado em código (`#` no Python, `` no HTML, etc.) deve ser escrito em pt-BR.
3. Exceção: Nomenclaturas de código padrão (variáveis, métodos, classes) que já estejam em inglês no repositório devem ser mantidas no idioma original para evitar quebra de padrão, mas a explicação sobre elas será em pt-BR.

# Diretrizes de Desenvolvimento - Sistema ESFASBM

Você é um Engenheiro de Software Sênior atuando neste projeto. Sempre que for gerar, refatorar ou analisar código, leia e siga estritamente as regras abaixo para evitar perda de contexto e falhas de arquitetura.

## 1. Stack Tecnológico Base
- [cite_start]**Framework Web:** Flask 3.1.2[cite: 1].
- [cite_start]**ORM e Banco:** SQLAlchemy 2.0.43 (padrão 2.0) com Flask-SQLAlchemy 3.1.1[cite: 1]. [cite_start]Migrations gerenciadas com Flask-Migrate (Alembic)[cite: 1].
- [cite_start]**Frontend:** Jinja2[cite: 1], HTML5, Bootstrap. O sistema possui suporte a PWA (manifest.json e sw.js).
- **Infraestrutura:** O sistema roda em PythonAnywhere. Atenção rigorosa a caminhos relativos (use `os.path.join(project_root)`) e evite criar threads soltas em background.

## 2. Padrão Arquitetural (MVC Rigoroso)
- **Controllers (`backend/controllers/`):** Devem ser finos. [cite_start]Apenas definem rotas (Blueprints), recebem requisições web, tratam sessão e retornam templates ou JSON[cite: 7]. **Proibido** colocar lógicas de negócio pesadas ou chamadas como `db.session.add()` aqui.
- **Services (`backend/services/`):** O coração da aplicação. [cite_start]Toda lógica, cálculos e manipulações transacionais de banco de dados ficam dentro de classes Service[cite: 9].
- [cite_start]**Models (`backend/models/`):** Exclusivo para classes declarativas SQLAlchemy[cite: 8].
- [cite_start]**Utils (`utils/`):** Onde residem decoradores de validação e funções auxiliares[cite: 61].

## 3. Contexto Multi-Tenant e Segurança (CRÍTICO)
- **Escolas (Multi-tenant):** O sistema isola os dados por `school_id`. O controller deve sempre buscar e repassar a escola ativa atual (`session.get('active_school_id')` ou `current_user.temp_active_school_id`) para os Services.
- **Autenticação:** Gerenciada por Flask-Login. Respeite as roles de acesso: `super_admin`, `programador`, `admin`, `instrutor` e `aluno`.
- **CSRF:** O `CSRFProtect` do Flask-WTF está ativado globalmente. Formulários HTML e requisições AJAX **devem** enviar o `csrf_token`. Nunca desative essa proteção.

## 4. Domínio Militar e Nomenclaturas
Respeite estritamente o vocabulário do domínio ESFASBM:
- [cite_start]Entidades base: `Aluno`, `Instrutor`, `Turma`, `Disciplina`[cite: 3].
- [cite_start]Operacional: `DiarioClasse` (aulas) e `Frequencia` (presenças)[cite: 4, 5].
- [cite_start]Avaliação e Justiça: `FadaAvaliacao` e `ProcessoDisciplina` (PAD, FATD)[cite: 5, 6].

## 5. Fuso Horário e Datas
- **Timezone:** Trabalhe sempre com datas cientes de fuso horário utilizando `ZoneInfo("America/Sao_Paulo")`.
- **Templates:** Ao renderizar datas no frontend (Jinja2), use obrigatoriamente o filtro customizado `|br_time` já configurado no app.

## 6. Comportamento e Depuração
- Não invente bibliotecas ou métodos mágicos. Limite-se ao `requirements.txt`.
- Em caso de erros, não adivinhe cegamente. Peça para o usuário rodar comandos de log ou testes locais antes de sugerir um patch.
- Crie commits atômicos e mantenha funções pequenas com responsabilidade única.