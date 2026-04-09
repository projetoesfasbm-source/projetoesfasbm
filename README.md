# 📌 Projeto ESFASBM – Sistema de Gestão Escolar

Este sistema foi desenvolvido a partir de uma **proposta do Comandante da Escola de Formação de Sargentos (Maj Humberto)**, que identificou a necessidade de uma solução digital para **gestão administrativa e acadêmica da escola**.  
O projeto foi conduzido por alunos da ESFASBM, aplicando práticas modernas de desenvolvimento de software, integração de tecnologias e implantação em ambiente real.

---

## 🎯 Objetivo
Criar uma plataforma web que auxilie na **organização de dados, relatórios e processos internos da escola**, oferecendo uma solução prática, escalável e de fácil manutenção.

---

## 🚀 Funcionalidades Principais
- **Interface web responsiva** construída com HTML/CSS e templates dinâmicos.  
- **Backend em Python**, estruturado em módulos e APIs.  
- **Banco de dados versionado** com migrations.  
- **Geração de relatórios em PDF** utilizando WeasyPrint.  
- **Testes automatizados** para garantir qualidade e confiabilidade.  
- **Implantação simplificada** com Docker e docker-compose.  

---

## 🛠️ Tecnologias Utilizadas
- Python 3.x  
- HTML5 / CSS3  
- Docker & Docker Compose  
- WeasyPrint  
- Git/GitHub  

---

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

---

## ⚙️ Como Executar

**Clonar o repositório**
```bash
git clone https://github.com/projetoesfasbm-source/projetoesfasbm.git
cd projetoesfasbm
```

**Criar ambiente virtual e instalar dependências**
```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

**Rodar com Docker (opcional)**
```bash
docker-compose up --build
```

**Executar o projeto**
```bash
python backend/app.py
```

**Acessar no navegador**
```
http://localhost:5000
```

---

## ✅ Testes
Para rodar os testes automatizados:
```bash
pytest
```

---

## 👥 Equipe e Contribuições Individuais
O desenvolvimento foi realizado por alunos da **ESFASBM**, com divisão clara de responsabilidades:  

- **Sd PM Toillier** → Desenvolvimento do **frontend** (HTML, CSS, templates).  
- **Sd PM Oliveira** → Desenvolvimento do **backend** (Python, lógica de negócio, APIs, integrações).  
- **Sd PM Werle** → Configuração de **servidor, banco de dados** e implantação do sistema.  

---

## 📌 Observação Final
Este projeto não foi apenas acadêmico, mas sim uma **demanda institucional real**, atendendo a uma necessidade prática da Escola de Formação de Sargentos.  
