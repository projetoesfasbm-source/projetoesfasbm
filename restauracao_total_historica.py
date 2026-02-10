from backend.app import create_app
from backend.models.database import db
from backend.models.horario import Horario
from backend.models.turma import Turma
from backend.models.diario_classe import DiarioClasse
from backend.models.semana import Semana
from backend.models.instrutor import Instrutor
from backend.models.ciclo import Ciclo
from sqlalchemy import select

app = create_app()

def get_dia_semana_str(data_obj):
    dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    return dias[data_obj.weekday()]

with app.app_context():
    print("--- INICIANDO RESTAURAÇÃO MASTER (CICLOS + DIÁRIOS) ---")
    
    # 1. Fallback de Instrutor (Necessário para evitar erro de NOT NULL)
    instrutor_fallback = db.session.get(Instrutor, 56) or db.session.scalar(select(Instrutor))
    if not instrutor_fallback:
        print("ERRO: Nenhum instrutor encontrado no banco.")
        exit()

    # --- PARTE 1: RESTAURAR BASEADO NOS DIÁRIOS (O QUE JÁ ACONTECEU) ---
    print("\nPasso 1: Recuperando horários de aulas já ministradas...")
    diarios = db.session.scalars(select(DiarioClasse)).all()
    recriados_diario = 0

    for diario in diarios:
        if diario.periodo is None: continue
        turma = db.session.get(Turma, diario.turma_id)
        if not turma: continue

        semana = db.session.scalar(
            select(Semana)
            .where(Semana.data_inicio <= diario.data_aula)
            .where(Semana.data_fim >= diario.data_aula)
        )
        if not semana: continue

        dia_str = get_dia_semana_str(diario.data_aula)
        
        # Verifica se já existe
        existe = db.session.scalar(
            select(Horario).where(
                Horario.pelotao == turma.nome,
                Horario.semana_id == semana.id,
                Horario.dia_semana == dia_str,
                Horario.periodo == diario.periodo
            )
        )

        if not existe:
            instrutor_real = db.session.scalar(select(Instrutor).where(Instrutor.user_id == diario.responsavel_id))
            id_ins = instrutor_real.id if instrutor_real else instrutor_fallback.id
            
            novo = Horario(
                pelotao=turma.nome,
                dia_semana=dia_str,
                periodo=diario.periodo,
                disciplina_id=diario.disciplina_id,
                instrutor_id=id_ins,
                semana_id=semana.id,
                duracao=1,
                status='concluido'
            )
            db.session.add(novo)
            recriados_diario += 1

    db.session.commit()
    print(f"Sucesso: {recriados_diario} horários de aulas passadas restaurados.")

    # --- PARTE 2: RESTAURAR PLANEJAMENTO POR CICLO (O QUE ESTÁ POR VIR) ---
    # Nota: Esta parte assume que as turmas estão vinculadas a ciclos com disciplinas.
    print("\nPasso 2: Recuperando planejamento de Ciclos para turmas...")
    
    # Se o seu sistema tiver uma tabela de ligação 'planejamento_ciclo' ou similar, 
    # precisaríamos iterar sobre ela. Como o sistema foi "limpo", 
    # vamos garantir que as semanas atuais e futuras tenham os slots básicos.
    
    # Aqui, se você tiver um backup SQL ou JSON dos horários, seria o ideal.
    # Caso contrário, o sistema precisará que os chefes de turma ou coordenadores
    # re-insiram o planejamento futuro, pois a "Limpeza Total" apagou as previsões.

    print("\n" + "="*50)
    print("RESTAURAÇÃO DE HISTÓRICO CONCLUÍDA.")
    print(f"Total de registros recuperados: {recriados_diario}")
    print("="*50)
    print("AVISO: Horários futuros que não tinham diário ainda podem precisar")
    print("de preenchimento manual caso não existam modelos de ciclo salvos.")