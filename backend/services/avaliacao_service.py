# backend/services/avaliacao_service.py
from datetime import datetime
from sqlalchemy import select, func
from ..models.database import db
from ..models.avaliacao import AvaliacaoAtitudinal, AvaliacaoItem
from ..models.processo_disciplina import ProcessoDisciplina

class AvaliacaoService:
    
    CRITERIOS_FADA = [
        "1. Expressão oral e escrita",
        "2. Planejamento e método",
        "3. Perseverança e Tenacidade",
        "4. Apresentação pessoal",
        "5. Lealdade",
        "6. Tato",
        "7. Equilíbrio emocional",
        "8. Disciplina",
        "9. Responsabilidade",
        "10. Maturidade",
        "11. Assiduidade",
        "12. Pontualidade",
        "13. Dicção de voz e comando",
        "14. Liderança",
        "15. Relacionamento interpessoal",
        "16. Ética",
        "17. Produtividade",
        "18. Eficiência"
    ]

    @staticmethod
    def calcular_nota_disciplinar(aluno_id: int, data_inicio: datetime, data_fim: datetime) -> float:
        """
        Calcula a NDisc baseada nos processos finalizados no período.
        Fórmula: NDisc = (20 - Pontos Descontados) / 2
        """
        pontos_descontados = db.session.scalar(
            select(func.sum(ProcessoDisciplina.pontos))
            .where(
                ProcessoDisciplina.aluno_id == aluno_id,
                ProcessoDisciplina.status == 'Finalizado',
                ProcessoDisciplina.data_decisao >= data_inicio,
                ProcessoDisciplina.data_decisao <= data_fim
            )
        ) or 0.0
        
        ndisc = (20.0 - float(pontos_descontados)) / 2.0
        return max(0.0, min(10.0, ndisc))

    @staticmethod
    def criar_avaliacao(dados: dict, avaliador_id: int) -> tuple[bool, str]:
        try:
            aluno_id = int(dados.get('aluno_id'))
            data_inicio = datetime.strptime(dados.get('periodo_inicio'), '%Y-%m-%d')
            data_fim = datetime.strptime(dados.get('periodo_fim'), '%Y-%m-%d')
            
            # 1. Calcula a Nota Disciplinar (Objetiva)
            nota_disciplinar = AvaliacaoService.calcular_nota_disciplinar(aluno_id, data_inicio, data_fim)
            
            # 2. Processa as notas da FADA (Subjetiva)
            soma_fada = 0.0
            itens_fada = []
            for i, criterio in enumerate(AvaliacaoService.CRITERIOS_FADA):
                nota = float(dados.get(f'criterio_{i}', 0.0))
                soma_fada += nota
                itens_fada.append({'criterio': criterio, 'nota': nota})
            
            nota_fada = soma_fada / len(AvaliacaoService.CRITERIOS_FADA)
            
            # 3. Calcula a Nota Final Atitudinal: (NDisc + FADA) / 2
            nota_final = (nota_disciplinar + nota_fada) / 2.0

            # 4. Salva no Banco
            nova_avaliacao = AvaliacaoAtitudinal(
                aluno_id=aluno_id,
                avaliador_id=avaliador_id,
                periodo_inicio=data_inicio,
                periodo_fim=data_fim,
                nota_disciplinar=round(nota_disciplinar, 2),
                nota_fada=round(nota_fada, 2),
                nota_final=round(nota_final, 3),
                data_fechamento=datetime.utcnow(),
                observacoes=dados.get('observacoes')
            )
            db.session.add(nova_avaliacao)
            db.session.flush()

            for item in itens_fada:
                db.session.add(AvaliacaoItem(
                    avaliacao_id=nova_avaliacao.id,
                    criterio=item['criterio'],
                    nota=item['nota']
                ))

            db.session.commit()
            return True, "Avaliação registrada com sucesso!"

        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao salvar: {str(e)}"

    @staticmethod
    def get_avaliacoes_aluno(aluno_id: int) -> list[AvaliacaoAtitudinal]:
        return db.session.scalars(
            select(AvaliacaoAtitudinal)
            .where(AvaliacaoAtitudinal.aluno_id == aluno_id)
            .order_by(AvaliacaoAtitudinal.created_at.desc())
        ).all()

    @staticmethod
    def get_avaliacao_por_id(avaliacao_id: int) -> AvaliacaoAtitudinal | None:
        return db.session.get(AvaliacaoAtitudinal, avaliacao_id)