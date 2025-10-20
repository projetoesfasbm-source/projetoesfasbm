# backend/services/mail_merge_service.py

import pandas as pd
from docx import Document
from io import BytesIO
import zipfile
import re

class MailMergeService:
    @staticmethod
    def _find_placeholders(document):
        """Encontra todos os placeholders no formato {{placeholder}} no documento."""
        placeholders = set()
        pattern = re.compile(r'\{\{([^}]+)\}\}')
        
        full_text = "\n".join([p.text for p in document.paragraphs])
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    full_text += "\n" + cell.text

        for match in pattern.finditer(full_text):
            placeholders.add(match.group(1).strip())
                            
        return list(placeholders)

    @staticmethod
    def _replace_text_in_paragraph(paragraph, placeholders, data_row):
        """Substitui todos os placeholders em um parágrafo."""
        full_text = paragraph.text
        
        # Realiza todas as substituições no texto do parágrafo
        for key in placeholders:
            placeholder_tag = f"{{{{{key}}}}}"
            # Usa uma função lambda com re.sub para evitar problemas com caracteres especiais
            full_text = re.sub(
                re.escape(placeholder_tag), 
                str(data_row.get(key, '')), 
                full_text
            )

        # Se houveram mudanças, reescreve o parágrafo
        if full_text != paragraph.text:
            # Limpa o parágrafo mantendo a formatação
            p_runs = paragraph.runs
            for run in p_runs:
                run.clear()
            # Adiciona o novo texto em um único 'run', que herdará o estilo do parágrafo
            paragraph.add_run(full_text)

    @staticmethod
    def generate_documents(template_file, data_file, output_format='docx'):
        """
        Gera documentos em massa a partir de um template docx e uma planilha de dados.
        Retorna os bytes de um arquivo zip.
        """
        try:
            template_doc = Document(template_file)
            df = pd.read_excel(data_file)
            
            df.columns = [str(col).strip() for col in df.columns]

            placeholders = MailMergeService._find_placeholders(template_doc)
            
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for index, row in df.iterrows():
                    doc = Document(template_file)
                    data_row = row.to_dict()

                    # Itera e substitui em todos os parágrafos do corpo
                    for p in doc.paragraphs:
                        MailMergeService._replace_text_in_paragraph(p, placeholders, data_row)

                    # Itera e substitui em todas as tabelas
                    for table in doc.tables:
                        for r in table.rows:
                            for cell in r.cells:
                                for p in cell.paragraphs:
                                    MailMergeService._replace_text_in_paragraph(p, placeholders, data_row)

                    doc_buffer = BytesIO()
                    doc.save(doc_buffer)
                    doc_buffer.seek(0)
                    
                    # Usa uma coluna específica para nomear o arquivo, se existir (ex: 'nome'), senão usa o índice
                    file_name_base = str(data_row.get('nome', f"documento_{index + 1}")).strip()
                    filename = f"Certificado_{file_name_base}.docx"
                    
                    zf.writestr(filename, doc_buffer.getvalue())

            zip_buffer.seek(0)
            return zip_buffer, None
            
        except Exception as e:
            return None, str(e)