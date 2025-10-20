# 📌 Projeto ESFASBM

Sistema web desenvolvido como projeto acadêmico, com foco em **aprendizado de desenvolvimento de software**, organização de código e uso de ferramentas modernas de deploy.  

## 🚀 Funcionalidades
- Interface web construída com **HTML/CSS** e templates dinâmicos.  
- Backend em **Python**, estruturado em módulos.  
- Integração com banco de dados e uso de **migrations** para versionamento.  
- Geração de relatórios em PDF utilizando **WeasyPrint**.  
- Estrutura de testes automatizados para validação do código.  
- Configuração de ambiente com **Docker e docker-compose** para fácil implantação.  

## 🛠️ Tecnologias Utilizadas
- **Python 3.x**  
- **HTML5 / CSS3**  
- **Docker & Docker Compose**  
- **WeasyPrint**  
- **Git/GitHub** para versionamento  

## 📂 Estrutura do Projeto
```
projetoesfasbm/
│── backend/          # Lógica principal do sistema
│── migrations/       # Controle de versão do banco de dados
│── scripts/          # Scripts auxiliares
│── static/           # Arquivos estáticos (CSS, imagens, JS)
│── templates/        # Templates HTML
│── tests/            # Testes automatizados
│── utils/            # Funções utilitárias
│── docker-compose.yml
│── requirements.txt
│── weasyprint_api.py
```

## ⚙️ Como Executar
1. **Clonar o repositório**
   ```bash
   git clone https://github.com/projetoesfasbm-source/projetoesfasbm.git
   cd projetoesfasbm
   ```

2. **Criar ambiente virtual e instalar dependências**
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/Mac
   venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   ```

3. **Rodar com Docker (opcional)**
   ```bash
   docker-compose up --build
   ```

4. **Executar o projeto**
   ```bash
   python backend/app.py
   ```

5. **Acessar no navegador**
   ```
   http://localhost:5000
   ```

## ✅ Testes
Para rodar os testes automatizados:
```bash
pytest
```

## 📖 Contribuição
- Fork o projeto  
- Crie uma branch (`git checkout -b feature/nova-funcionalidade`)  
- Commit suas alterações (`git commit -m 'Adiciona nova funcionalidade'`)  
- Push para a branch (`git push origin feature/nova-funcionalidade`)  
- Abra um Pull Request  

## 👥 Autores
Projeto desenvolvido por alunos da **ESFASBM**, sendo Sd PM Toillier, Sd PM Werle e Sd PM Oliveira.  
