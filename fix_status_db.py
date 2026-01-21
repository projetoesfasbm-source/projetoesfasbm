import logging
from sqlalchemy import text
from backend.app import create_app
from backend.models.database import db

# Configuração de Log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def corrigir_banco_dados():
    """
    Converte a coluna status para VARCHAR e normaliza os valores antigos.
    """
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("=== INICIANDO CORREÇÃO DO BANCO DE DADOS ===")
            
            with db.engine.connect() as conn:
                # PASSO 1: Alterar a estrutura da tabela (DDL)
                # Remove a restrição de ENUM e permite qualquer texto
                logger.info("1. Convertendo coluna 'status' da tabela 'processos_disciplina' para VARCHAR(50)...")
                try:
                    # Sintaxe MySQL/MariaDB
                    conn.execute(text("ALTER TABLE processos_disciplina MODIFY COLUMN status VARCHAR(50) NULL;"))
                    logger.info("   -> Estrutura alterada com sucesso.")
                except Exception as e:
                    logger.error(f"   -> Erro ao alterar estrutura (pode já ser varchar?): {e}")

                # PASSO 2: Atualizar dados (DML)
                logger.info("2. Normalizando valores antigos para o padrão do sistema...")
                
                # Lista de atualizações: (SQL, Descrição)
                updates = [
                    (
                        "UPDATE processos_disciplina SET status = 'AGUARDANDO_CIENCIA' WHERE status LIKE 'Aguardando%' OR status = 'created'",
                        "Aguardando Ciência -> AGUARDANDO_CIENCIA"
                    ),
                    (
                        "UPDATE processos_disciplina SET status = 'ALUNO_NOTIFICADO' WHERE status LIKE 'Aluno Notificado%'",
                        "Aluno Notificado -> ALUNO_NOTIFICADO"
                    ),
                    (
                        "UPDATE processos_disciplina SET status = 'DEFESA_ENVIADA' WHERE status LIKE 'Defesa Enviada%'",
                        "Defesa Enviada -> DEFESA_ENVIADA"
                    ),
                    (
                        "UPDATE processos_disciplina SET status = 'EM_ANALISE' WHERE status LIKE 'Em Análise%' OR status LIKE 'Em Analise%'",
                        "Em Análise -> EM_ANALISE"
                    ),
                    (
                        "UPDATE processos_disciplina SET status = 'FINALIZADO' WHERE status LIKE 'Finalizado%'",
                        "Finalizado -> FINALIZADO"
                    ),
                    (
                        "UPDATE processos_disciplina SET status = 'ARQUIVADO' WHERE status LIKE 'Arquivado%'",
                        "Arquivado -> ARQUIVADO"
                    )
                ]
                
                total_afetados = 0
                for sql_cmd, desc in updates:
                    result = conn.execute(text(sql_cmd))
                    if result.rowcount > 0:
                        logger.info(f"   -> Aplicado: {desc} ({result.rowcount} registros)")
                        total_afetados += result.rowcount
                
                if total_afetados == 0:
                    logger.info("   -> Nenhum registro precisou ser atualizado (dados já estavam corretos ou tabela vazia).")

                # Confirma as alterações
                conn.commit()
                logger.info("=== SUCESSO: Banco de dados corrigido e dados normalizados! ===")

        except Exception as e:
            logger.error(f"ERRO CRÍTICO DURANTE A EXECUÇÃO: {e}")
            # Tenta rollback em caso de erro na transação de dados
            try:
                with db.engine.connect() as conn:
                    conn.rollback()
            except:
                pass

if __name__ == "__main__":
    corrigir_banco_dados()