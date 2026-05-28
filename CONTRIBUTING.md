# Diretrizes de Contribuição e Fluxo de Trabalho (Git Workflow)

Para garantir a estabilidade do SisGEn em produção, toda a equipe de desenvolvimento (e qualquer Inteligência Artificial assistente) DEVE seguir obrigatoriamente as seguintes regras:

## 1. O Santuário da Produção (`main`)
* NUNCA faça commits ou edições diretas na branch `main`.
* A branch `main` deve refletir estritamente o ambiente de produção (código limpo, testado e funcional).

## 2. Trabalho Local (Feature Branches)
* Para criar uma nova funcionalidade, corrigir um bug ou refatorar o código, crie sempre uma branch secundária.
* Padrão de nomenclatura:
  * `feature/nome-da-funcionalidade` (Ex: `feature/refatoracao-fada`)
  * `fix/nome-do-bug` (Ex: `fix/barra-progresso`)

## 3. Homologação e Testes Locais
* Antes de solicitar a mesclagem (Merge), o desenvolvedor DEVE:
  * Subir o servidor localmente (`python backend/app.py`).
  * Testar o fluxo completo da sua funcionalidade.
  * Verificar se as alterações não quebraram outras partes do sistema (regressão).

## 4. Mesclagem Segura (Merge)
* Concluiu a feature? Antes de subir para a main:
  1. Baixe as atualizações mais recentes da main (`git fetch origin` e `git pull origin main`).
  2. Resolva os conflitos de código na sua própria branch de feature.
  3. Após resolver os conflitos e testar novamente, faça o Merge ou Pull Request (PR) para a branch `main`.

## 5. Auditoria de IA
* Assistentes de IA atuando neste projeto estão **estritamente proibidos** de mesclar códigos na branch `main` sem que o plano de implementação tenha sido testado na branch de homologação/feature.
