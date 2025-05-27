# 🛡️ AgentRisk - Sistema de Avaliação de Riscos para IA Autônoma

## 🚀 Deploy no Streamlit Cloud

### Pré-requisitos
- Conta no GitHub
- Conta no Streamlit Cloud (https://share.streamlit.io)
- Chave da API OpenAI

### Passos para Deploy

#### 1️⃣ Preparar Repositório GitHub
```bash
# Criar novo repositório
git init agentrisk
cd agentrisk

# Adicionar arquivos
# - agentrisk.py (código principal)
# - requirements.txt
# - README.md

git add .
git commit -m "Initial commit - AgentRisk v1.0"
git remote add origin https://github.com/SEU_USUARIO/agentrisk.git
git push -u origin main
```

#### 2️⃣ Conectar no Streamlit Cloud
1. Acesse https://share.streamlit.io
2. Clique em "New app"
3. Conecte seu repositório GitHub
4. Configure:
   - **Repository:** `SEU_USUARIO/agentrisk`
   - **Branch:** `main`
   - **Main file path:** `agentrisk.py`
   - **App URL:** `agentrisk-SEU_USUARIO` (ou personalizado)

#### 3️⃣ Configurar Secrets
No Streamlit Cloud, vá em:
- **Settings** → **Secrets**
- Adicione:
```toml
OPENAI_API_KEY = "sk-..."
```

#### 4️⃣ Deploy Automático
- O Streamlit Cloud fará deploy automaticamente
- Cada push no GitHub atualiza a aplicação
- URL pública será gerada automaticamente

### 📁 Estrutura do Repositório
```
agentrisk/
├── agentrisk.py          # Aplicação principal
├── requirements.txt      # Dependências Python
├── README.md            # Documentação
└── .gitignore           # Arquivos a ignorar
```

### 🔑 Configuração das Chaves

#### OpenAI API Key
1. Acesse https://platform.openai.com/api-keys
2. Crie uma nova chave API
3. Adicione nos Secrets do Streamlit:
   ```
   OPENAI_API_KEY = "sua_chave_aqui"
   ```

### 🛠️ Arquivo requirements.txt
```
streamlit>=1.28.0
openai>=1.0.0
fpdf>=2.7.6
python-dateutil>=2.8.2
```

### 📊 Funcionalidades Implementadas

#### ✅ Análise de Riscos
- 15 categorias específicas de Agentic AI
- Integração com OpenAI GPT-4
- Fallback para análise local
- Score de 0-100 com classificação automática

#### ✅ Interface Completa
- Design responsivo com CSS personalizado
- Dashboard interativo com gráficos
- Sistema de filtros e ordenação
- Geração de relatórios PDF

#### ✅ Integração Universal
- Session State para outros sistemas Streamlit
- Simulação de sistemas (HeatGlass, CarGlass, etc.)
- Preparado para API REST futura
- Documentação para desenvolvedores

#### ✅ Configurações Av
