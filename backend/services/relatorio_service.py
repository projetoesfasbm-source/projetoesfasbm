# backend/services/relatorio_service.py

from _future_ import annotations
import os
import json
from io import BytesIO
from typing import Any, Dict, List, Tuple
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import aliased

# Importações seguras que não dependem do banco de dados ou de outros serviços locais
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
GA_CREDENTIALS_JSON = os.environ.get("GA_CREDENTIALS_JSON")

def _get_google_credentials() -> Credentials:
    if not GA_CREDENTIALS_JSON:
        raise RuntimeError("A variável de ambiente GA_CREDENTIALS_JSON não foi configurada.")
    try:
        info = json.loads(GA_CREDENTIALS_JSON)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception as e:
        raise RuntimeError(f"Erro ao carregar credenciais do Google: {e}")

def _upload_xlsx_and_convert_to_sheet(filename: str, xlsx_bytes: bytes) -> str | None:
    try:
        creds = _get_google_credentials()
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': filename, 'mimeType': 'application/vnd.google-apps.spreadsheet'}
        media = MediaIoBaseUpload(BytesIO(xlsx_bytes), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        permission = {'type': 'anyone', 'role': 'reader'}
        service.permissions().create(fileId=file.get('id'), body=permission).execute()
        return file.get('webViewLink')
    except HttpError as error:
        print(f"Ocorreu um erro na API do Google Drive: {error}")
        return None
    except Exception as e:
        print(f"Ocorreu um erro inesperado durante o upload para o Google Drive: {e}")
        return None

class RelatorioService:

    @staticmethod
    def _get_dia_offset(dia_semana_str: str) -> int:
        """
        Converte string do dia da semana (ex: 'segunda-feira') para offset numérico (0=seg, 6=dom).
        Normaliza strings para evitar erros com acentos ou casing.
        """
        if not dia_semana_str:
            return 0

        s = dia_semana_str.lower().strip()
        if 'segunda' in s: return 0
        if 'terca' in s or 'terça' in s: return 1
        if 'quarta' in s: return 2
        if 'quinta' in s: return 3
        if 'sexta' in s: return 4
        if 'sabado' in s or 'sábado' in s: return 5
        if 'domingo' in s: return 6
        return 0

    @staticmethod
    def get_horas_aula_por_instrutor(
        data_inicio: date,
        data_fim: date,
        is_rr_filter: bool,
        instrutor_ids_filter: List[int] | None,
        school_id: int
    ) -> List[Dict[str, Any]]:
        """
        Busca e formata os dados de horas-aula por instrutor, FILTRANDO PELA ESCOLA (school_id).
        """
        from ..models import db, Horario, User, Instrutor, Disciplina, Semana, Ciclo

        # Criar aliases para permitir o join duplo (instrutor 1 e instrutor 2)
        Instrutor1 = aliased(Instrutor)
        User1 = aliased(User)
        Instrutor2 = aliased(Instrutor)
        User2 = aliased(User)

        # Seleciona todos os dados, INCLUINDO a Semana e o Horario (que contem o pelotao)
        query = (
            select(
                Horario,
                Disciplina,
                Instrutor1, User1,
                Instrutor2, User2,
                Semana
            )
            .join(Semana, Horario.semana_id == Semana.id)
            .join(Ciclo, Semana.ciclo_id == Ciclo.id) # Join Necessário para filtrar escola
            .join(Disciplina, Horario.disciplina_id == Disciplina.id)
            # Join Obrigatório para o Instrutor 1 (Titular)
            .join(Instrutor1, Horario.instrutor_id == Instrutor1.id)
            .join(User1, Instrutor1.user_id == User1.id)
            # Join Opcional (Left Join) para o Instrutor 2 (Auxiliar/Monitor)
            .outerjoin(Instrutor2, Horario.instrutor_id_2 == Instrutor2.id)
            .outerjoin(User2, Instrutor2.user_id == User2.id)
            .filter(
                Semana.data_inicio <= data_fim,
                Semana.data_fim >= data_inicio,
                Ciclo.school_id == school_id # FILTRO DE ESCOLA ADICIONADO
            )
        )

        rows = db.session.execute(query).all()

        # Dicionário para agregação: matricula -> dados
        dados_agrupados = {}

        # Conjunto para garantir unicidade do pagamento por SLOT DE TEMPO
        # Chave: (instrutor_id, data_real_da_aula, periodo_aula)
        slots_pagos = set()

        def processar_instrutor(user_obj, instrutor_obj, disciplina_obj, data_aula, periodo_aula, duracao, pelotao_str):
            """Soma horas apenas se o slot (Instrutor+Dia+Periodo) ainda não foi pago."""
            if not user_obj or not instrutor_obj:
                return

            # Chave robusta de unicidade: Quem + Quando + Qual Periodo
            chave_slot = (instrutor_obj.id, data_aula, periodo_aula)

            # Se já pagamos este instrutor neste horário específico, ignoramos duplicatas do banco
            if chave_slot in slots_pagos:
                return

            # Aplica Filtros de Relatório
            if is_rr_filter and not instrutor_obj.is_rr:
                return
            if instrutor_ids_filter and instrutor_obj.id not in instrutor_ids_filter:
                return

            # Marca slot como pago
            slots_pagos.add(chave_slot)

            chave_agrupamento = user_obj.matricula

            # Inicializa a estrutura do instrutor se não existir
            if chave_agrupamento not in dados_agrupados:
                dados_agrupados[chave_agrupamento] = {
                    "info": {
                        "user": {
                            "posto_graduacao": user_obj.posto_graduacao,
                            "matricula": user_obj.matricula,
                            "nome_completo": user_obj.nome_completo,
                        }
                    },
                    "disciplinas_map": {}
                }

            # Inicializa a disciplina para este instrutor se não existir
            nome_disc = disciplina_obj.materia
            if nome_disc not in dados_agrupados[chave_agrupamento]["disciplinas_map"]:
                dados_agrupados[chave_agrupamento]["disciplinas_map"][nome_disc] = {
                    "nome": nome_disc,
                    "ch_total": 0,  # Começa com 0 e soma conforme encontra pelotões
                    "ch_a_pagar": 0,
                    "_pelotoes_contabilizados": set() # Controle interno para somar CH Total uma vez por turma
                }

            item_disciplina = dados_agrupados[chave_agrupamento]["disciplinas_map"][nome_disc]

            # Normaliza o nome do pelotão para evitar duplicidade por espaços extras
            pelotao_clean = pelotao_str.strip() if pelotao_str else "PADRAO"

            # --- Lógica de Soma de CH Total por Turma (Pelotão) ---
            # Se este pelotão ainda não foi contabilizado para esta disciplina deste instrutor, soma a CH Total
            if pelotao_clean not in item_disciplina["_pelotoes_contabilizados"]:
                item_disciplina["ch_total"] += (disciplina_obj.carga_horaria_prevista or 0)
                item_disciplina["_pelotoes_contabilizados"].add(pelotao_clean)

            # Soma a duração das aulas a pagar
            item_disciplina["ch_a_pagar"] += duracao

        # Itera sobre todas as linhas retornadas
        for row in rows:
            horario = row[0]   # Objeto Horario
            disciplina = row[1] # Objeto Disciplina
            inst1 = row[2]      # Objeto Instrutor (1)
            usr1 = row[3]       # Objeto User (1)
            inst2 = row[4]      # Objeto Instrutor (2)
            usr2 = row[5]       # Objeto User (2)
            semana = row[6]     # Objeto Semana

            duracao = horario.duracao or 1
            periodo = horario.periodo

            # Obtém o pelotão diretamente do horário (string)
            pelotao = getattr(horario, 'pelotao', '')

            # Calcula a data real da aula para evitar duplicidade de semanas sobrepostas
            offset_dias = RelatorioService._get_dia_offset(horario.dia_semana)
            data_aula = semana.data_inicio + timedelta(days=offset_dias)

            # 1. Processa Instrutor 1 (Titular)
            if inst1 and usr1:
                processar_instrutor(usr1, inst1, disciplina, data_aula, periodo, duracao, pelotao)

            # 2. Processa Instrutor 2 (Auxiliar/Dupla)
            if inst2 and usr2:
                # Segurança contra erro de cadastro (mesmo ID nos dois campos)
                if not (inst1 and inst1.id == inst2.id):
                    processar_instrutor(usr2, inst2, disciplina, data_aula, periodo, duracao, pelotao)

        # Formata a saída final
        lista_final = []
        chaves_ordenadas = sorted(dados_agrupados.keys())

        for chave in chaves_ordenadas:
            item = dados_agrupados[chave]
            lista_disciplinas = list(item["disciplinas_map"].values())

            # Remove chaves internas auxiliares antes de retornar para não sujar o template
            for d in lista_disciplinas:
                if "_pelotoes_contabilizados" in d:
                    del d["_pelotoes_contabilizados"]

            lista_final.append({
                "info": item["info"],
                "disciplinas": lista_disciplinas
            })

        return lista_final

    @staticmethod
    def export_to_google_sheets(contexto: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Gera o arquivo XLSX em memória e faz o upload para o Google Drive.
        """
        from .xlsx_service import gerar_mapa_gratificacao_xlsx

        try:
            xlsx_bytes = gerar_mapa_gratificacao_xlsx(
                dados=contexto.get("dados"),
                valor_hora_aula=float(contexto.get("valor_hora_aula") or 0.0),
                nome_mes_ano=contexto.get("nome_mes_ano"),
                titulo_curso=contexto.get("titulo_curso"),
                opm_nome=contexto.get("opm"),
                escola_nome=contexto.get("escola_nome"),
                data_emissao=contexto.get("data_emissao"),
                telefone=contexto.get("telefone"),
                auxiliar_nome=contexto.get("auxiliar_nome"),
                comandante_nome=contexto.get("comandante_nome"),
                digitador_nome=contexto.get("digitador_nome"),
                auxiliar_funcao=contexto.get("auxiliar_funcao"),
                comandante_funcao=contexto.get("comandante_funcao"),
                data_fim=contexto.get("data_fim"),
                cidade_assinatura=contexto.get("cidade"),
            )

            nome_arquivo = f'Relatório Horas-Aula - {contexto.get("nome_mes_ano", "geral")}'
            sheet_url = _upload_xlsx_and_convert_to_sheet(nome_arquivo, xlsx_bytes)

            if sheet_url:
                return True, sheet_url
            else:
                return False, "Falha no upload do arquivo para o Google Drive. Verifique as credenciais da API."
        except Exception as e:
            print(f"ERRO CRÍTICO ao exportar para Google Sheets: {e}")
            return False, f"Ocorreu um erro interno ao gerar ou enviar o arquivo: {e}"