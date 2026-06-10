from locust import HttpUser, task, between
import re

class ProfessorEscolaUser(HttpUser):
    # Simula um professor lendo a tela por 1 a 5 segundos antes de clicar no próximo link
    wait_time = between(1.0, 5.0)

    def on_start(self):
        """
        Executado automaticamente quando um usuário virtual "nasce".
        Ele entra na página de login, rouba o token de segurança (CSRF) e faz o login POST.
        """
        # ==========================================
        # PREENCHA COM SUAS CREDENCIAIS REAIS AQUI
        # ==========================================
        self.matricula = "4512316"
        self.senha = "#SNKZ!HIiy*9"
        
        # 1. Pega a página de login para pegar o Token de segurança e o Cookie de Sessão inicial
        response = self.client.get("/login")
        
        # 2. Usa Regex para pescar o csrf_token escondido no HTML
        csrf_token = None
        match = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', response.text)
        if match:
            csrf_token = match.group(1)
        
        if not csrf_token:
            print("AVISO: CSRF Token não encontrado! O login pode falhar.")

        # 3. Dispara o POST de login real
        self.client.post("/login", data={
            "identificacao": self.matricula,
            "password": self.senha,
            "csrf_token": csrf_token,
            "remember": "y"
        })

    @task(3) # Peso 3: Acontece com mais frequência
    def carregar_dashboard(self):
        self.client.get("/")

    @task(2)
    def consultar_quadro_horario(self):
        # Acessa a rota raiz de horários
        self.client.get("/horario/")

    @task(2)
    def acessar_justica_disciplina(self):
        # Acessa a rota raiz de justiça
        self.client.get("/justica-e-disciplina/")

    @task(1) # Peso 1: Acontece com menos frequência
    def acessar_diarios(self):
        # Acessa a listagem de diários do instrutor
        self.client.get("/diario-classe/instrutor/pendentes")
