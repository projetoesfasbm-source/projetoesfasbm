# backend/services/uniqueness.py
import re
from typing import Optional

def norm_email(v: Optional[str]) -> Optional[str]:
    return v.strip().lower() if v else None

def norm_idfunc(v: Optional[str]) -> Optional[str]:
    if not v: return None
    return re.sub(r"\D+","", v.strip()) or None

def check_uniqueness(db, email: Optional[str], idfunc: Optional[str]):
    """
    Retorna (ok: bool, detalhe: str). ok=True se não encontrou conflito.
    Ajuste os imports dos modelos conforme seu projeto.
    """
    from backend.models import user as user_m
    from backend.models import instrutor as instrutor_m
    from backend.models import aluno as aluno_m
    from backend.models import pre_cadastro as precad_m
    from backend.models import usuario_orfao as orfao_m

    email_n = norm_email(email)
    idfunc_n = norm_idfunc(idfunc)

    # Usuario
    if hasattr(user_m, "User"):
        q = db.session.query(user_m.User)
        if email_n and hasattr(user_m.User, "email"):
            if q.filter(user_m.User.email == email_n).first():
                return False, "E-mail já está em uso na tabela de usuários."
        if idfunc_n and hasattr(user_m.User, "id_func"):
            if db.session.query(user_m.User).filter(user_m.User.id_func == idfunc_n).first():
                return False, "ID Func já está em uso na tabela de usuários."

    # Instrutor
    if hasattr(instrutor_m, "Instrutor"):
        if idfunc_n and hasattr(instrutor_m.Instrutor, "id_func"):
            if db.session.query(instrutor_m.Instrutor).filter(instrutor_m.Instrutor.id_func == idfunc_n).first():
                return False, "ID Func já está em uso na tabela de instrutores."

    # Aluno
    if hasattr(aluno_m, "Aluno"):
        if idfunc_n and hasattr(aluno_m.Aluno, "id_func"):
            if db.session.query(aluno_m.Aluno).filter(aluno_m.Aluno.id_func == idfunc_n).first():
                return False, "ID Func já está em uso na tabela de alunos."

    # Pré-cadastro
    if hasattr(precad_m, "PreCadastro"):
        q = db.session.query(precad_m.PreCadastro)
        if email_n and hasattr(precad_m.PreCadastro, "email"):
            if q.filter(precad_m.PreCadastro.email == email_n).first():
                return False, "E-mail já está reservado em pré-cadastro."
        if idfunc_n and hasattr(precad_m.PreCadastro, "id_func"):
            if db.session.query(precad_m.PreCadastro).filter(precad_m.PreCadastro.id_func == idfunc_n).first():
                return False, "ID Func já está reservado em pré-cadastro."

    # Usuário órfão
    if hasattr(orfao_m, "UsuarioOrfao"):
        q = db.session.query(orfao_m.UsuarioOrfao)
        if email_n and hasattr(orfao_m.UsuarioOrfao, "email"):
            if q.filter(orfao_m.UsuarioOrfao.email == email_n).first():
                return False, "E-mail presente em usuários órfãos."
        if idfunc_n and hasattr(orfao_m.UsuarioOrfao, "id_func"):
            if db.session.query(orfao_m.UsuarioOrfao).filter(orfao_m.UsuarioOrfao.id_func == idfunc_n).first():
                return False, "ID Func presente em usuários órfãos."

    return True, "OK"
