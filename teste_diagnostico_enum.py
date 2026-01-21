import logging
from sqlalchemy import inspect
from backend.app import create_app
from backend.models.database import db

# Configuração de Log
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def diagnosticar_colunas_travadas():
    """
    Verifica se existem colunas no banco de dados definidas como ENUM.
    O ideal para evitar erros de migração é que sejam VARCHAR.
    """
    app = create_app()
    
    with app.app_context():
        inspector = inspect(db.engine)
        tabelas = inspector.get_table_names()
        
        encontrou_erro = False
        
        logger.info("=== INICIANDO DIAGNÓSTICO DE TIPOS DE DADOS ===")
        
        for tabela in tabelas:
            colunas = inspector.get_columns(tabela)
            for coluna in colunas:
                nome = coluna['name']
                tipo = str(coluna['type']).upper()
                
                # Verifica se é um ENUM do banco de dados (MySQL/Postgres)
                if 'ENUM' in tipo:
                    logger.warning(f"[ALERTA] Tabela '{tabela}' -> Coluna '{nome}' está travada como {tipo}.")
                    logger.warning(f"   -> Sugestão: Converter para VARCHAR no banco e controlar via Python.")
                    encontrou_erro = True
                
                # Verificação extra para a tabela crítica de processos
                if tabela == 'processos_disciplinares' and nome == 'status':
                    if 'VARCHAR' not in tipo and 'TEXT' not in tipo:
                         logger.error(f"[CRÍTICO] A coluna 'status' em 'processos_disciplinares' ainda é {tipo}!")
                         encontrou_erro = True
                    else:
                        logger.info(f"[OK] Tabela '{tabela}' -> Coluna '{nome}' está correta ({tipo}).")

        if not encontrou_erro:
            logger.info("=== SUCESSO: Nenhuma coluna ENUM restritiva encontrada no banco. ===")
            logger.info("O banco está configurado para aceitar atualizações de status sem quebrar.")
        else:
            logger.error("=== FALHA: Foram encontradas colunas ENUM que podem bloquear futuras atualizações. ===")

if __name__ == "__main__":
    diagnosticar_colunas_travadas()