import os
import time
import logging
from datetime import datetime, timedelta
from weasyprint import HTML

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from backend.app import create_app
from backend.models.database import db
from backend.models.background_job import BackgroundJob

app = create_app()

def process_pdf_job(job):
    """Gera o PDF usando Weasyprint a partir do HTML salvo no payload."""
    downloads_dir = os.path.join(app.root_path, '..', 'static', 'downloads')
    os.makedirs(downloads_dir, exist_ok=True)
    
    filename = f"document_{job.id}.pdf"
    file_path = os.path.join(downloads_dir, filename)
    
    logging.info(f"Gerando PDF para job {job.id} em {file_path}")
    HTML(string=job.payload).write_pdf(file_path)
    
    return file_path

def cleanup_old_jobs():
    """Remove jobs e arquivos PDF mais velhos que 24 horas."""
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    old_jobs = BackgroundJob.query.filter(BackgroundJob.created_at < cutoff_time).all()
    
    for job in old_jobs:
        if job.result_path and os.path.exists(job.result_path):
            try:
                os.remove(job.result_path)
            except Exception as e:
                logging.error(f"Erro ao deletar arquivo antigo {job.result_path}: {e}")
        db.session.delete(job)
        
    if old_jobs:
        try:
            db.session.commit()
            logging.info(f"Limpeza de rotina: {len(old_jobs)} jobs antigos removidos.")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao limpar jobs antigos: {e}")

def run_worker():
    """Loop principal do worker."""
    logging.info("Iniciando Background Worker...")
    
    last_cleanup = datetime.utcnow()

    while True:
        # Colocar o context manager DENTRO do loop previne memory leaks do SQLAlchemy Identity Map.
        with app.app_context():
            # Executa a limpeza a cada 1 hora
            if (datetime.utcnow() - last_cleanup).total_seconds() > 3600:
                cleanup_old_jobs()
                last_cleanup = datetime.utcnow()

            try:
                # Busca o primeiro job pendente (FIFO)
                job = BackgroundJob.query.filter_by(status='pending').order_by(BackgroundJob.created_at.asc()).first()
                
                if job:
                    # Marca como processando
                    job.status = 'processing'
                    job.started_at = datetime.utcnow()
                    db.session.commit()
                    
                    logging.info(f"Processando Job {job.id} do tipo {job.task_type}")
                    
                    try:
                        if job.task_type == 'generate_pdf':
                            result_path = process_pdf_job(job)
                            job.result_path = result_path
                        else:
                            raise ValueError(f"Task type desconhecido: {job.task_type}")
                            
                        # Finaliza com sucesso
                        job.status = 'completed'
                        job.finished_at = datetime.utcnow()
                        job.payload = None 
                        
                        logging.info(f"Job {job.id} concluído com sucesso!")
                        
                    except Exception as e:
                        job.status = 'failed'
                        job.error_message = str(e)
                        job.finished_at = datetime.utcnow()
                        logging.error(f"Job {job.id} falhou: {str(e)}")
                    
                    # Salva o resultado
                    db.session.commit()
                    
                else:
                    # Se não tem job, dorme um pouco
                    time.sleep(2)
            except Exception as e:
                logging.error(f"Erro no loop principal do worker: {e}")
                db.session.rollback()
                time.sleep(5) # Evita spam de logs se o banco cair

if __name__ == '__main__':
    run_worker()
