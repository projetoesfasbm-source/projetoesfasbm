# Manual do Usuário – Sistema ESFASBM

## 1. Visão geral do sistema
O Sistema ESFASBM foi desenvolvido para centralizar a gestão acadêmica e administrativa da Escola de Formação de Sargentos, permitindo organização de dados, emissão de relatórios e suporte aos processos internos em uma plataforma web unificada.【F:README.md†L1-L19】

### Público-alvo
O manual atende cinco perfis principais: Super Administradores, Programadores, Administradores de Escola, Instrutores e Alunos. Cada perfil possui permissões específicas descritas na próxima seção.

## 2. Papéis de usuário e níveis de acesso
O controle de acesso é feito por papéis (_roles_) associados aos usuários. A tabela abaixo resume objetivos e permissões principais de cada perfil.

| Perfil | Finalidade | Principais permissões |
| --- | --- | --- |
| **Super Administrador** | Gerenciar todas as escolas e vínculos do ecossistema. | Acessa páginas exclusivas de administração global, pode alternar a visualização entre escolas, criar e remover escolas, atribuir e revogar vínculos, criar administradores e redefinir senhas de qualquer usuário comum.【F:utils/decorators.py†L18-L81】【F:backend/controllers/main_controller.py†L57-L94】【F:backend/controllers/super_admin_controller.py†L16-L217】 |
| **Programador** | Suporte técnico avançado e manutenção do sistema. | Possui acesso privilegiado às áreas administrativas e de agenda de aulas, compartilhando grande parte das permissões de super administradores em páginas operacionais (cadastros, horários, análises).【F:utils/decorators.py†L7-L81】【F:backend/controllers/horario_controller.py†L104-L170】 |
| **Administrador da Escola** | Operar a gestão cotidiana de uma escola específica. | Realiza pré-cadastro, gerencia alunos, instrutores, turmas, disciplinas, horários, históricos e relatórios dentro da sua escola.【F:utils/decorators.py†L71-L93】【F:backend/controllers/admin_controller.py†L11-L52】【F:backend/controllers/aluno_controller.py†L86-L190】【F:backend/controllers/instrutor_controller.py†L83-L174】【F:backend/controllers/turma_controller.py†L36-L133】【F:backend/controllers/disciplina_controller.py†L34-L129】【F:backend/controllers/horario_controller.py†L101-L239】【F:backend/controllers/relatorios_controller.py†L32-L156】【F:backend/controllers/historico_controller.py†L73-L125】【F:backend/controllers/justica_controller.py†L93-L228】 |
| **Instrutor** | Planejar e conduzir atividades pedagógicas. | Visualiza e edita seus vínculos com turmas, pode cadastrar aulas nas turmas vinculadas, responder ou aplicar questionários e consultar dados necessários para suas instruções.【F:utils/decorators.py†L31-L69】【F:backend/controllers/horario_controller.py†L104-L170】【F:backend/controllers/questionario_controller.py†L119-L205】 |
| **Aluno** | Acompanhar desempenho individual e receber comunicados. | Ativa a própria conta, acessa dashboard, horário da turma, histórico acadêmico e responde questionários; recebe notificações e participa de processos disciplinares quando pertinente.【F:backend/models/user.py†L22-L41】【F:backend/controllers/auth_controller.py†L120-L189】【F:backend/controllers/main_controller.py†L50-L160】【F:backend/controllers/horario_controller.py†L56-L128】【F:backend/controllers/historico_controller.py†L18-L120】【F:backend/controllers/notification_controller.py†L9-L51】【F:backend/controllers/justica_controller.py†L77-L157】

> **Dica:** Se a sua conta exigir troca de senha ao primeiro acesso, finalize o cadastro em "Meu Perfil" para liberar todas as funções disponíveis.【F:backend/models/user.py†L30-L32】【F:backend/controllers/user_controller.py†L141-L178】

## 3. Acesso ao sistema

### 3.1 Pré-cadastro
O pré-cadastro é responsabilidade de administradores ou perfis superiores. Eles inserem uma ou várias matrículas, definem a função desejada e vinculam a escola correspondente, garantindo que o usuário possa completar o registro depois.【F:backend/controllers/main_controller.py†L97-L160】【F:backend/controllers/admin_controller.py†L11-L52】

### 3.2 Ativação e cadastro inicial
Usuários pré-cadastrados acessam a página de registro, informam matrícula, dados pessoais, definem senha (mínimo de 8 caracteres) e, quando aplicável, escolhem a turma ou escola. O sistema valida as informações, cria perfis de aluno ou instrutor e ativa a conta.【F:backend/controllers/auth_controller.py†L120-L189】

### 3.3 Login e encerramento de sessão
O acesso é feito por matrícula, usuário ou e-mail combinado com senha. Contas inativas redirecionam o usuário ao registro para completar a ativação. O logout encerra a sessão e retorna à tela de login.【F:backend/controllers/auth_controller.py†L88-L118】

### 3.4 Recuperação de senha
Caso esqueça a senha, solicite um e-mail de redefinição. O sistema envia um link temporário que permite cadastrar uma nova senha com os requisitos mínimos estabelecidos.【F:backend/controllers/auth_controller.py†L195-L205】

## 4. Navegação inicial e recursos gerais

### 4.1 Dashboard e contexto de escola
Após o login, o dashboard apresenta indicadores da escola associada. Super administradores e programadores podem alternar a escola em visualização por meio do parâmetro `view_as_school`, útil para auditoria multiunidade.【F:backend/controllers/main_controller.py†L57-L94】

### 4.2 Notificações e alertas
O sino de notificações exibe mensagens recentes; é possível marcar itens individuais ou todos como lidos, além de acessar o histórico completo pela página dedicada.【F:backend/controllers/notification_controller.py†L9-L51】

### 4.3 Perfil do usuário
Em **Meu Perfil**, todos os usuários podem atualizar dados pessoais, e-mail, senha e foto. Alunos definem a turma e instrutores informam disponibilidade, incluindo status de reserva remunerada.【F:backend/controllers/user_controller.py†L49-L184】

### 4.4 Dispositivos móveis e notificações push
Usuários autenticados podem registrar tokens de dispositivos móveis para receber notificações push via Firebase. O sistema evita duplicidades e garante associação ao usuário correto.【F:backend/controllers/push_controller.py†L7-L40】

## 5. Rotinas do Administrador da Escola

### 5.1 Gestão de alunos
- **Listagem e filtros:** Visualize alunos por turma, com busca e paginação.【F:backend/controllers/aluno_controller.py†L86-L110】  
- **Edição detalhada:** Atualize dados pessoais, turma, função e foto; o formulário adapta o catálogo de postos e graduações conforme a categoria escolhida.【F:backend/controllers/aluno_controller.py†L112-L169】  
- **Funções e exclusão:** Ajuste funções específicas via formulário rápido e remova cadastros quando necessário.【F:backend/controllers/aluno_controller.py†L171-L193】

### 5.2 Gestão de instrutores
- **Cadastro completo:** Registre novos instrutores com dados pessoais, credenciais e opções de posto/graduação vinculados à escola atual.【F:backend/controllers/instrutor_controller.py†L83-L107】  
- **Edição e manutenção:** Atualize dados, controle status de reserva remunerada e remova vínculos quando preciso.【F:backend/controllers/instrutor_controller.py†L108-L174】

### 5.3 Turmas e cargos
- **Listagem e destaque:** Consulte todas as turmas; alunos visualizam primeiro sua turma atual.【F:backend/controllers/turma_controller.py†L36-L48】  
- **Detalhes e cargos:** Verifique a distribuição de cargos internos e salve alterações diretamente do painel da turma.【F:backend/controllers/turma_controller.py†L49-L70】  
- **Cadastro/edição:** Crie turmas informando ano e alunos associados ou edite turmas existentes com seleção múltipla; alunos sem turma aparecem como candidatos.【F:backend/controllers/turma_controller.py†L72-L121】  
- **Exclusão:** Remova turmas após validação de segurança.【F:backend/controllers/turma_controller.py†L123-L133】

### 5.4 Disciplinas e carga horária
- **Visão por turma:** Escolha uma turma para acompanhar progresso de carga horária cumprida em cada disciplina.【F:backend/controllers/disciplina_controller.py†L34-L59】  
- **Cadastro em lote:** Defina matéria, carga horária prevista, ciclo letivo e turmas atendidas em uma única operação.【F:backend/controllers/disciplina_controller.py†L61-L83】  
- **Edição individual e exclusão:** Ajuste detalhes específicos de uma disciplina ou remova registros quando necessário.【F:backend/controllers/disciplina_controller.py†L86-L129】

### 5.5 Quadro de horários
- **Visualização:** Exiba o quadro semanal por turma e ciclo, com configuração de intervalos automatizada a partir das preferências do site.【F:backend/controllers/horario_controller.py†L36-L128】  
- **Agendamento:** Programadores, administradores e instrutores vinculados podem editar o grid de aulas, registrar detalhes das lições e remover ou aprovar solicitações.【F:backend/controllers/horario_controller.py†L101-L239】  
- **Exportação:** Gere PDF do quadro para distribuição offline.【F:backend/controllers/horario_controller.py†L130-L153】

### 5.6 Histórico acadêmico
- **Minhas notas:** Ao acessar o histórico de um aluno, o sistema sincroniza automaticamente matrículas em disciplinas da turma e calcula média final.【F:backend/controllers/historico_controller.py†L52-L104】  
- **Avaliações:** Administradores podem registrar notas e pareceres diretamente no histórico do aluno.【F:backend/controllers/historico_controller.py†L105-L168】

### 5.7 Relatórios oficiais
- Gere relatórios de horas-aula em PDF ou XLSX, com filtros por período, instrutor e efetivo da reserva. O formulário traz campos padrão editáveis para cabeçalhos institucionais.【F:backend/controllers/relatorios_controller.py†L32-L156】

### 5.8 Justiça e Disciplina
- Cadastre fatos disciplinares usando uma lista de infrações padronizadas, acompanhe processos em andamento/finalizados e gere relatórios para análises externas.【F:backend/controllers/justica_controller.py†L16-L228】

## 6. Rotinas do Instrutor

### 6.1 Planejamento de aulas
Instrutores enxergam o quadro de horários das turmas às quais estão vinculados e podem agendar aulas nos slots autorizados, incluindo dupla docência quando cadastrada.【F:backend/controllers/horario_controller.py†L101-L209】

### 6.2 Questionários e feedback
Eles podem criar novos questionários, registrar perguntas com múltiplos formatos de resposta e acompanhar estatísticas e participantes. Também é possível registrar respostas em nome de turmas ou indivíduos quando necessário.【F:backend/controllers/questionario_controller.py†L21-L205】

### 6.3 Comunicação com os alunos
Notificações e questionários respondidos aparecem imediatamente na caixa do instrutor, permitindo acompanhamento de feedbacks e defesas disciplinares quando o instrutor estiver envolvido.【F:backend/controllers/notification_controller.py†L9-L51】【F:backend/controllers/justica_controller.py†L135-L157】

## 7. Rotinas do Aluno

### 7.1 Ativação da conta
Após o pré-cadastro, o aluno completa seus dados (incluindo escolha da turma) e define uma senha segura antes de acessar o sistema.【F:backend/controllers/auth_controller.py†L120-L176】

### 7.2 Vida acadêmica
- **Dashboard e horários:** O aluno visualiza apenas o quadro de sua turma; se não houver vínculo, o sistema solicita contato com a administração.【F:backend/controllers/horario_controller.py†L56-L70】  
- **Histórico e notas:** O menu “Meu CTSP” apresenta histórico funcional, sanções, elogios e notas consolidadas, garantindo visibilidade transparente do desempenho.【F:backend/controllers/historico_controller.py†L18-L120】  
- **Questionários e comunicações:** Questionários disponíveis podem ser respondidos diretamente no portal; notificações exibem prazos e comunicados relevantes.【F:backend/controllers/questionario_controller.py†L119-L205】【F:backend/controllers/notification_controller.py†L9-L51】

### 7.3 Processos disciplinares
Quando envolvido em um processo, o aluno registra ciência, apresenta defesa e acompanha o status até a conclusão, conforme regras institucionais.【F:backend/controllers/justica_controller.py†L135-L157】

## 8. Boas práticas de uso
1. **Mantenha dados atualizados:** Informações corretas de e-mail e turma garantem recebimento de notificações e relatórios consistentes.【F:backend/controllers/user_controller.py†L141-L178】  
2. **Utilize exportações com responsabilidade:** PDFs, XLSX e documentos gerados contêm dados sensíveis; armazene-os em locais seguros.【F:backend/controllers/horario_controller.py†L130-L153】【F:backend/controllers/relatorios_controller.py†L117-L146】【F:backend/controllers/justica_controller.py†L202-L225】  
3. **Aproveite notificações push:** Cadastre dispositivos móveis confiáveis para receber avisos críticos em tempo real.【F:backend/controllers/push_controller.py†L9-L40】

## 9. Onde buscar suporte
- **Administradores locais:** Primeiro ponto de contato para dúvidas de cadastro e vinculação.  
- **Equipe técnica (Programadores):** Acione em caso de falhas técnicas, pois possuem acesso total às páginas de manutenção e agenda.【F:utils/decorators.py†L7-L81】【F:backend/controllers/horario_controller.py†L101-L170】

Com estes procedimentos, cada perfil consegue operar o Sistema ESFASBM de maneira segura e eficiente, garantindo integridade das informações e cumprimento das rotinas acadêmicas da escola.
