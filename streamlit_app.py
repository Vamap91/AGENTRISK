import streamlit as st
import json
import datetime
import base64
import io
from typing import Dict, List, Tuple
import re

# Importações condicionais para evitar erros
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    st.warning("📄 Geração de PDF indisponível. Instale fpdf2 para ativar esta funcionalidade.")

try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    st.warning("🤖 OpenAI indisponível. Usando análise baseada em regras.")

# Configuração da página
st.set_page_config(
    page_title="AgentRisk - Avaliação de Riscos em IA Autônoma",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuração da OpenAI
@st.cache_resource
def get_openai_client():
    """Inicializa cliente OpenAI com chave dos secrets"""
    if not OPENAI_AVAILABLE:
        return None
        
    try:
        if "OPENAI_API_KEY" in st.secrets:
            api_key = st.secrets["OPENAI_API_KEY"]
            return OpenAI(api_key=api_key)
        else:
            st.info("💡 Configure OPENAI_API_KEY nos Secrets para ativar análise avançada com IA")
            return None
    except Exception as e:
        st.warning(f"⚠️ Problema na configuração OpenAI: {str(e)}")
        return None

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .risk-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .risk-high { border-left: 5px solid #dc2626; }
    .risk-medium { border-left: 5px solid #f59e0b; }
    .risk-low { border-left: 5px solid #10b981; }
    .score-container {
        text-align: center;
        padding: 2rem;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .score-high { background: #fef2f2; border: 2px solid #dc2626; }
    .score-medium { background: #fffbeb; border: 2px solid #f59e0b; }
    .score-low { background: #f0fdf4; border: 2px solid #10b981; }
    .integration-button {
        background: linear-gradient(45deg, #10b981, #059669);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-weight: bold;
    }
    .stButton > button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Definição dos 15 riscos baseados no documento IBM
AGENTIC_AI_RISKS = {
    "1": {
        "nome": "Desalinhamento de Objetivos",
        "descricao": "Agente pode buscar objetivos diferentes dos pretendidos pela organização",
        "categoria": "Governança",
        "keywords": ["objetivo", "meta", "propósito", "direcionamento", "alinhamento"]
    },
    "2": {
        "nome": "Ações Autônomas Indesejadas",
        "descricao": "Execução de ações sem aprovação humana adequada em contextos críticos",
        "categoria": "Autonomia",
        "keywords": ["autônomo", "automático", "sem supervisão", "independente"]
    },
    "3": {
        "nome": "Uso Indevido de APIs",
        "descricao": "Utilização inadequada ou excessiva de APIs e serviços externos",
        "categoria": "Integração",
        "keywords": ["api", "serviço externo", "integração", "chamada", "endpoint"]
    },
    "4": {
        "nome": "Decepção e Viés de Persona",
        "descricao": "Comportamentos enganosos ou enviesados baseados na persona do agente",
        "categoria": "Comportamento",
        "keywords": ["persona", "comportamento", "viés", "enganoso", "manipulação"]
    },
    "5": {
        "nome": "Persistência de Memória Inadequada",
        "descricao": "Retenção inapropriada de informações sensíveis ou contextos obsoletos",
        "categoria": "Memória",
        "keywords": ["memória", "persistência", "histórico", "contexto", "retenção"]
    },
    "6": {
        "nome": "Transparência e Explicabilidade Limitada",
        "descricao": "Dificuldade em explicar decisões e processos de raciocínio do agente",
        "categoria": "Transparência",
        "keywords": ["explicação", "transparência", "black box", "interpretabilidade"]
    },
    "7": {
        "nome": "Vulnerabilidades de Segurança",
        "descricao": "Exposição a ataques, vazamentos de dados e falhas de segurança",
        "categoria": "Segurança",
        "keywords": ["segurança", "vulnerabilidade", "ataque", "proteção", "criptografia"]
    },
    "8": {
        "nome": "Conformidade Regulatória",
        "descricao": "Não atendimento a regulamentações como AI Act, LGPD e normas setoriais",
        "categoria": "Compliance",
        "keywords": ["regulamentação", "compliance", "lgpd", "gdpr", "ai act", "norma"]
    },
    "9": {
        "nome": "Escalabilidade e Performance",
        "descricao": "Limitações na capacidade de escalar e manter performance adequada",
        "categoria": "Performance",
        "keywords": ["escalabilidade", "performance", "latência", "throughput", "capacidade"]
    },
    "10": {
        "nome": "Qualidade e Integridade dos Dados",
        "descricao": "Problemas na qualidade, completude e veracidade dos dados utilizados",
        "categoria": "Dados",
        "keywords": ["dados", "qualidade", "integridade", "veracidade", "completude"]
    },
    "11": {
        "nome": "Monitoramento e Auditoria",
        "descricao": "Ausência de sistemas adequados de monitoramento e trilhas de auditoria",
        "categoria": "Observabilidade",
        "keywords": ["monitoramento", "auditoria", "log", "rastreamento", "observabilidade"]
    },
    "12": {
        "nome": "Gestão de Exceções e Falhas",
        "descricao": "Tratamento inadequado de situações excepcionais e recuperação de falhas",
        "categoria": "Robustez",
        "keywords": ["exceção", "falha", "erro", "recuperação", "fallback"]
    },
    "13": {
        "nome": "Dependências Externas",
        "descricao": "Riscos associados à dependência de serviços e recursos externos",
        "categoria": "Dependência",
        "keywords": ["dependência", "terceiros", "fornecedor", "disponibilidade"]
    },
    "14": {
        "nome": "Impacto nos Stakeholders",
        "descricao": "Efeitos não intencionais em usuários, funcionários e outras partes interessadas",
        "categoria": "Social",
        "keywords": ["stakeholder", "usuário", "impacto social", "funcionário"]
    },
    "15": {
        "nome": "Evolução e Adaptação Descontrolada",
        "descricao": "Mudanças não supervisionadas no comportamento através de aprendizado contínuo",
        "categoria": "Evolução",
        "keywords": ["evolução", "adaptação", "aprendizado", "mudança comportamental"]
    }
}

class AgentRiskAnalyzer:
    """Analisador de riscos para sistemas de IA autônoma usando OpenAI"""
    
    def __init__(self, openai_client):
        self.client = openai_client
        self.risks = AGENTIC_AI_RISKS
    
    def analyze_system(self, system_description: str, system_name: str = "") -> Dict:
        """Analisa um sistema usando OpenAI e retorna avaliação de riscos"""
        
        if not self.client:
            # Fallback para análise baseada em regras se OpenAI não disponível
            return self._fallback_analysis(system_description, system_name)
        
        try:
            # Análise usando OpenAI
            risk_scores = {}
            
            for risk_id, risk_info in self.risks.items():
                score, recommendations = self._analyze_single_risk(
                    system_description, risk_id, risk_info
                )
                
                risk_scores[risk_id] = {
                    "score": score,
                    "level": self._get_risk_level(score),
                    "recommendations": recommendations
                }
            
            # Score global
            global_score = sum(r["score"] for r in risk_scores.values()) / len(risk_scores)
            
            return {
                "system_name": system_name,
                "global_score": round(global_score, 1),
                "global_level": self._get_risk_level(global_score),
                "risks": risk_scores,
                "analysis_date": datetime.datetime.now().isoformat(),
                "analysis_method": "OpenAI GPT-4"
            }
            
        except Exception as e:
            st.warning(f"⚠️ Erro na análise OpenAI: {str(e)}. Usando análise alternativa.")
            return self._fallback_analysis(system_description, system_name)
    
    def _analyze_single_risk(self, description: str, risk_id: str, risk_info: Dict) -> Tuple[float, List[str]]:
        """Analisa um risco específico usando OpenAI"""
        
        prompt = f"""
        Você é um especialista em avaliação de riscos de IA autônoma. Analise o sistema descrito abaixo para o risco específico mencionado.

        SISTEMA A SER ANALISADO:
        {description}

        RISCO A AVALIAR:
        Nome: {risk_info['nome']}
        Descrição: {risk_info['descricao']}
        Categoria: {risk_info['categoria']}

        INSTRUÇÕES:
        1. Avalie o nível de risco de 0 a 100 (0 = sem risco, 100 = risco crítico)
        2. Considere fatores como: autonomia, dados processados, impacto das decisões, supervisão humana, controles existentes
        3. Forneça 3 recomendações específicas para mitigar este risco

        FORMATO DE RESPOSTA (JSON):
        {{
            "score": <número de 0 a 100>,
            "justificativa": "<explicação de 2-3 linhas>",
            "recommendations": [
                "<recomendação 1>",
                "<recomendação 2>",
                "<recomendação 3>"
            ]
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            result = json.loads(response.choices[0].message.content)
            return result["score"], result["recommendations"]
            
        except Exception as e:
            # Fallback para análise baseada em regras
            return self._calculate_risk_score_fallback(description, risk_id, risk_info)
    
    def _fallback_analysis(self, system_description: str, system_name: str) -> Dict:
        """Análise de fallback baseada em regras quando OpenAI não está disponível"""
        
        risk_scores = {}
        description_lower = system_description.lower()
        
        for risk_id, risk_info in self.risks.items():
            score, recommendations = self._calculate_risk_score_fallback(
                description_lower, risk_id, risk_info
            )
            
            risk_scores[risk_id] = {
                "score": score,
                "level": self._get_risk_level(score),
                "recommendations": recommendations
            }
        
        global_score = sum(r["score"] for r in risk_scores.values()) / len(risk_scores)
        
        return {
            "system_name": system_name,
            "global_score": round(global_score, 1),
            "global_level": self._get_risk_level(global_score),
            "risks": risk_scores,
            "analysis_date": datetime.datetime.now().isoformat(),
            "analysis_method": "Análise Baseada em Regras"
        }
    
    def _calculate_risk_score_fallback(self, description: str, risk_id: str, risk_info: Dict) -> Tuple[float, List[str]]:
        """Cálculo de risco baseado em palavras-chave (fallback)"""
        
        base_score = 35
        keywords = risk_info.get("keywords", [])
        
        # Aumenta score baseado em palavras-chave encontradas
        for keyword in keywords:
            if keyword in description:
                base_score += 12
        
        # Palavras que indicam controles (diminuem risco)
        control_keywords = [
            "supervisão", "controle", "governança", "auditoria", "monitoramento",
            "seguro", "protegido", "compliance", "responsável", "transparente"
        ]
        
        for keyword in control_keywords:
            if keyword in description:
                base_score -= 8
        
        # Palavras que aumentam risco
        high_risk_keywords = [
            "autônomo", "sem supervisão", "automático", "crítico", "sensível",
            "personalização", "decisão", "financeiro", "saúde"
        ]
        
        for keyword in high_risk_keywords:
            if keyword in description:
                base_score += 10
        
        final_score = max(0, min(100, base_score))
        recommendations = self._get_recommendations(risk_id, final_score)
        
        return final_score, recommendations
    
    def _get_risk_level(self, score: float) -> str:
        """Converte score numérico em nível de risco"""
        if score >= 70:
            return "Alto"
        elif score >= 40:
            return "Moderado"
        else:
            return "Baixo"
    
    def _get_recommendations(self, risk_id: str, score: float) -> List[str]:
        """Gera recomendações específicas para cada risco"""
        
        recommendations_map = {
            "1": [
                "Definir objetivos claros e mensuráveis para o agente",
                "Implementar sistema de validação de metas organizacionais",
                "Estabelecer revisões periódicas de alinhamento estratégico"
            ],
            "2": [
                "Implementar aprovação humana para ações críticas",
                "Definir thresholds para intervenção automática",
                "Criar sistema de escalação para decisões importantes"
            ],
            "3": [
                "Implementar rate limiting e controle de uso de APIs",
                "Auditar regularmente chamadas para serviços externos",
                "Estabelecer fallbacks para falhas de dependências"
            ],
            "4": [
                "Realizar testes adversariais de comportamento",
                "Implementar diversidade nos dados de treinamento",
                "Monitorar vieses em tempo real"
            ],
            "5": [
                "Implementar políticas de retenção de dados",
                "Usar técnicas de esquecimento seletivo",
                "Realizar limpeza periódica de contextos obsoletos"
            ],
            "6": [
                "Implementar técnicas de XAI (Explainable AI)",
                "Criar logs detalhados do processo decisório",
                "Desenvolver interfaces de transparência"
            ],
            "7": [
                "Implementar autenticação e autorização robustas",
                "Usar criptografia para dados sensíveis",
                "Realizar testes de penetração regulares"
            ],
            "8": [
                "Mapear requisitos regulatórios aplicáveis",
                "Implementar controles de compliance",
                "Realizar auditorias de conformidade"
            ],
            "9": [
                "Implementar arquitetura escalável e resiliente",
                "Monitorar métricas de performance continuamente",
                "Planejar capacidade baseada em demanda prevista"
            ],
            "10": [
                "Implementar validação contínua de qualidade de dados",
                "Estabelecer pipeline de data quality",
                "Criar métricas de integridade dos dados"
            ],
            "11": [
                "Implementar logging abrangente e estruturado",
                "Criar dashboards de monitoramento em tempo real",
                "Estabelecer alertas proativos"
            ],
            "12": [
                "Implementar tratamento robusto de exceções",
                "Criar mecanismos de fallback seguros",
                "Testar cenários de falha regularmente"
            ],
            "13": [
                "Mapear e monitorar dependências críticas",
                "Implementar alternativas para serviços essenciais",
                "Estabelecer SLAs com fornecedores"
            ],
            "14": [
                "Avaliar impacto em stakeholders regularmente",
                "Implementar canais de feedback",
                "Comunicar mudanças transparentemente"
            ],
            "15": [
                "Implementar controles de evolução supervisionada",
                "Monitorar mudanças comportamentais",
                "Estabelecer checkpoints de validação"
            ]
        }
        
        return recommendations_map.get(risk_id, ["Implementar boas práticas de IA responsável"])

class PDFGenerator:
    """Gerador de relatórios em PDF otimizado"""
    
    def __init__(self):
        self.pdf_available = PDF_AVAILABLE
    
    def generate_report(self, analysis_result: Dict) -> bytes:
        """Gera relatório PDF da análise de riscos"""
        
        if not self.pdf_available:
            # Fallback: gerar relatório em texto
            return self._generate_text_report(analysis_result)
        
        try:
            pdf = FPDF()
            pdf.add_page()
            
            # Configurar fonte
            pdf.set_font("Arial", "B", 18)
            
            # Cabeçalho
            pdf.cell(0, 15, "AgentRisk - Relatorio de Avaliacao", 0, 1, 'C')
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 10, f"Sistema: {analysis_result.get('system_name', 'N/A')}", 0, 1, 'C')
            pdf.cell(0, 8, f"Data da Analise: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1, 'C')
            pdf.cell(0, 8, f"Metodo: {analysis_result.get('analysis_method', 'N/A')}", 0, 1, 'C')
            pdf.ln(10)
            
            # Sumário Executivo
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "SUMARIO EXECUTIVO", 0, 1)
            pdf.set_font("Arial", size=11)
            
            global_score = analysis_result['global_score']
            global_level = analysis_result['global_level']
            
            # Score Global
            pdf.cell(0, 8, f"Score Global de Risco: {global_score}/100", 0, 1)
            pdf.cell(0, 8, f"Classificacao: {global_level}", 0, 1)
            
            # Contadores por nível
            high_count = sum(1 for r in analysis_result['risks'].values() if r['level'] == 'Alto')
            medium_count = sum(1 for r in analysis_result['risks'].values() if r['level'] == 'Moderado')
            low_count = sum(1 for r in analysis_result['risks'].values() if r['level'] == 'Baixo')
            
            pdf.cell(0, 8, f"Riscos Altos: {high_count} | Moderados: {medium_count} | Baixos: {low_count}", 0, 1)
            pdf.ln(8)
            
            # Riscos por categoria
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "ANALISE DETALHADA", 0, 1)
            
            # Ordenar riscos por score (maior primeiro)
            sorted_risks = sorted(
                analysis_result['risks'].items(),
                key=lambda x: x[1]['score'],
                reverse=True
            )
            
            pdf.set_font("Arial", size=9)
            
            for risk_id, risk_data in sorted_risks[:10]:  # Limitar a 10 para evitar overflow
                risk_info = AGENTIC_AI_RISKS[risk_id]
                
                # Nome do risco (evitar caracteres especiais)
                risk_name = risk_info['nome'].replace('ã', 'a').replace('ç', 'c').replace('õ', 'o')
                pdf.set_font("Arial", "B", 10)
                pdf.cell(0, 7, f"{risk_id}. {risk_name}", 0, 1)
                
                # Detalhes
                pdf.set_font("Arial", size=9)
                pdf.cell(0, 5, f"Score: {risk_data['score']}/100 | Nivel: {risk_data['level']}", 0, 1)
                
                # Primeira recomendação (sem acentos)
                if risk_data['recommendations']:
                    rec = risk_data['recommendations'][0][:80].replace('ã', 'a').replace('ç', 'c')
                    pdf.cell(0, 5, f"Recomendacao: {rec}...", 0, 1)
                
                pdf.ln(2)
            
            # Rodapé
            pdf.ln(10)
            pdf.set_font("Arial", "I", 8)
            pdf.cell(0, 5, "Este relatorio foi gerado automaticamente pelo sistema AgentRisk", 0, 1, 'C')
            
            return pdf.output(dest='S').encode('latin-1')
            
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {str(e)}")
            return self._generate_text_report(analysis_result)
    
    def _generate_text_report(self, analysis_result: Dict) -> bytes:
        """Gera relatório em formato texto como fallback"""
        
        report = f"""
AGENTRISK - RELATÓRIO DE AVALIAÇÃO DE RISCOS
============================================

Sistema: {analysis_result.get('system_name', 'N/A')}
Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
Método: {analysis_result.get('analysis_method', 'Análise Local')}

SUMÁRIO EXECUTIVO
=================
Score Global: {analysis_result['global_score']}/100
Nível de Risco: {analysis_result['global_level']}

DISTRIBUIÇÃO DE RISCOS
=====================
"""
        
        high_count = sum(1 for r in analysis_result['risks'].values() if r['level'] == 'Alto')
        medium_count = sum(1 for r in analysis_result['risks'].values() if r['level'] == 'Moderado')
        low_count = sum(1 for r in analysis_result['risks'].values() if r['level'] == 'Baixo')
        
        report += f"Riscos Altos: {high_count}\n"
        report += f"Riscos Moderados: {medium_count}\n"
        report += f"Riscos Baixos: {low_count}\n\n"
        
        report += "ANÁLISE DETALHADA\n"
        report += "=================\n\n"
        
        # Ordenar riscos por score
        sorted_risks = sorted(
            analysis_result['risks'].items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        
        for risk_id, risk_data in sorted_risks:
            risk_info = AGENTIC_AI_RISKS[risk_id]
            report += f"{risk_id}. {risk_info['nome']}\n"
            report += f"   Score: {risk_data['score']}/100 | Nível: {risk_data['level']}\n"
            report += f"   Categoria: {risk_info['categoria']}\n"
            if risk_data['recommendations']:
                report += f"   Recomendação: {risk_data['recommendations'][0]}\n"
            report += "\n"
        
        report += "\n---\nRelatório gerado pelo AgentRisk\n"
        
        return report.encode('utf-8')

# Inicialização com cache
@st.cache_resource
def get_analyzer():
    client = get_openai_client()
    return AgentRiskAnalyzer(client)

@st.cache_resource  
def get_pdf_generator():
    return PDFGenerator()

def main():
    """Função principal da aplicação"""
    
    # Header principal com informações de deploy
    st.markdown("""
    <div class="main-header">
        <h1>🛡️ AgentRisk</h1>
        <p>IA para Governança, Conformidade e Avaliação de Riscos em Sistemas Autônomos</p>
        <small>🚀 Rodando no Streamlit Cloud</small>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar configurações
    client = get_openai_client()
    
    # Status das funcionalidades
    col1, col2, col3 = st.columns(3)
    with col1:
        if client:
            st.success("✅ OpenAI: Ativo")
        else:
            st.info("ℹ️ OpenAI: Análise Local")
    
    with col2:
        if PDF_AVAILABLE:
            st.success("✅ PDF: Disponível")
        else:
            st.info("ℹ️ PDF: Relatório em Texto")
            
    with col3:
        st.success("✅ Sistema: Operacional")
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Menu de Navegação")
        page = st.selectbox(
            "Escolha uma opção:",
            ["🏠 Análise de Risco", "📊 Dashboard", "📋 Sobre os 15 Riscos", "🔗 Integração", "⚙️ Configurações"]
        )
        
        # Informações do sistema
        st.markdown("---")
        st.markdown("**📍 Status do Sistema**")
        st.info(f"🌐 Deploy: Streamlit Cloud\n🤖 IA: {'OpenAI GPT-4' if client else 'Análise Local'}")
    
    # Navegação por páginas
    if page == "🏠 Análise de Risco":
        show_risk_analysis_page()
    elif page == "📊 Dashboard":
        show_dashboard_page()
    elif page == "📋 Sobre os 15 Riscos":
        show_risks_info_page()
    elif page == "🔗 Integração":
        show_integration_page()
    else:
        show_settings_page()

def show_risk_analysis_page():
    """Página principal de análise de riscos"""
    
    st.header("📝 Análise de Risco do Sistema")
    
    # Verificar se há dados de integração
    if 'integrated_system' in st.session_state:
        st.success(f"🔗 Sistema integrado: {st.session_state.integrated_system['name']}")
        system_name = st.session_state.integrated_system['name']
        system_description = st.session_state.integrated_system['description']
        
        with st.expander("Ver descrição do sistema integrado"):
            st.text_area("Descrição:", value=system_description, height=100, disabled=True)
            
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Limpar Integração", use_container_width=True):
                del st.session_state.integrated_system
                st.rerun()
        with col2:
            if st.button("✏️ Editar Descrição", use_container_width=True):
                st.session_state.edit_mode = True
                st.rerun()
    else:
        # Formulário manual
        col1, col2 = st.columns([1, 1])
        
        with col1:
            system_name = st.text_input(
                "🏷️ Nome do Sistema:", 
                placeholder="Ex: HeatGlass, CarGlass Assistant",
                help="Nome identificador do sistema a ser analisado"
            )
        
        with col2:
            system_type = st.selectbox(
                "🔧 Tipo de Sistema:",
                ["Assistente Virtual", "Sistema de Análise", "Automação de Processos", 
                 "Chatbot", "Sistema de Recomendação", "IA Generativa", "Sistema de Monitoramento", "Outro"],
                help="Selecione a categoria que melhor descreve seu sistema"
            )
        
        system_description = st.text_area(
            "📄 Descrição Técnica do Sistema:",
            placeholder="""Descreva detalhadamente:
• Funcionalidades principais
• Tecnologias utilizadas (LLMs, APIs, frameworks)
• Tipos de dados processados
• Nível de autonomia das decisões
• Integração com outros sistemas
• Controles de segurança existentes
• Supervisão humana implementada""",
            help="Quanto mais detalhada a descrição, mais precisa será a análise de riscos.",
            height=200
        )
    
    # Botão de análise
    col1, col2 = st.columns([3, 1])
    
    with col1:
        analyze_button = st.button(
            "🔍 Analisar Riscos", 
            type="primary", 
            use_container_width=True,
            help="Inicia a análise de riscos usando IA"
        )
    
    with col2:
        st.button("📋 Exemplo", help="Carregar exemplo de descrição")
    
    if analyze_button:
        if system_description.strip():
            with st.spinner("🔄 Analisando riscos do sistema com IA..."):
                analyzer = get_analyzer()
                analysis_result = analyzer.analyze_system(system_description, system_name)
                
                # Salvar resultado na sessão
                st.session_state.analysis_result = analysis_result
                
                st.success("✅ Análise concluída!")
                st.balloons()  # Efeito visual
                st.rerun()
        else:
            st.error("⚠️ Por favor, forneça uma descrição do sistema.")
    
    # Mostrar resultados se disponíveis
    if 'analysis_result' in st.session_state:
        show_analysis_results(st.session_state.analysis_result)

def show_analysis_results(analysis_result: Dict):
    """Exibe os resultados da análise de riscos"""
    
    st.header("📊 Resultados da Análise")
    
    # Informações da análise
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"🏷️ **Sistema:** {analysis_result.get('system_name', 'N/A')}")
    with col2:
        st.info(f"🕒 **Analisado em:** {datetime.datetime.fromisoformat(analysis_result['analysis_date']).strftime('%d/%m/%Y %H:%M')}")
    with col3:
        st.info(f"🤖 **Método:** {analysis_result.get('analysis_method', 'N/A')}")
    
    # Score global
    global_score = analysis_result['global_score']
    global_level = analysis_result['global_level']
    
    score_class = "score-low" if global_score < 40 else "score-medium" if global_score < 70 else "score-high"
    emoji = "🟢" if global_score < 40 else "🟡" if global_score < 70 else "🔴"
    
    st.markdown(f"""
    <div class="score-container {score_class}">
        <h2>{emoji} Score Global de Risco</h2>
        <h1>{global_score}/100</h1>
        <h3>Nível: {global_level}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Métricas rápidas
    col1, col2, col3 = st.columns(3)
    
    high_count = sum(1 for r in analysis_result['risks'].values() if r['level'] == 'Alto')
    medium_count = sum(1 for r in analysis_result['risks'].values() if r['level'] == 'Moderado')
    low_count = sum(1 for r in analysis_result['risks'].values() if r['level'] == 'Baixo')
    
    with col1:
        st.metric("🔴 Riscos Altos", high_count, delta=-high_count if high_count > 0 else None)
    with col2:
        st.metric("🟡 Riscos Moderados", medium_count)
    with col3:
        st.metric("🟢 Riscos Baixos", low_count, delta=low_count if low_count > 0 else None)
    
    # Análise por risco
    st.subheader("🔍 Análise Detalhada por Risco")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        risk_filter = st.selectbox("Filtrar por nível:", ["Todos", "Alto", "Moderado", "Baixo"])
    with col2:
        category_filter = st.selectbox("Filtrar por categoria:", 
                                     ["Todas"] + list(set(risk['categoria'] for risk in AGENTIC_AI_RISKS.values())))
    with col3:
        sort_option = st.selectbox("Ordenar por:", ["Score (Maior)", "Score (Menor)", "Nome", "Categoria"])
    
    # Aplicar filtros
    risks_to_show = analysis_result['risks']
    
    if risk_filter != "Todos":
        risks_to_show = {k: v for k, v in risks_to_show.items() if v['level'] == risk_filter}
    
    if category_filter != "Todas":
        risks_to_show = {k: v for k, v in risks_to_show.items() 
                        if AGENTIC_AI_RISKS[k]['categoria'] == category_filter}
    
    # Aplicar ordenação
    if sort_option == "Score (Maior)":
        risks_to_show = dict(sorted(risks_to_show.items(), key=lambda x: x[1]['score'], reverse=True))
    elif sort_option == "Score (Menor)":
        risks_to_show = dict(sorted(risks_to_show.items(), key=lambda x: x[1]['score']))
    elif sort_option == "Nome":
        risks_to_show = dict(sorted(risks_to_show.items(), key=lambda x: AGENTIC_AI_RISKS[x[0]]['nome']))
    elif sort_option == "Categoria":
        risks_to_show = dict(sorted(risks_to_show.items(), key=lambda x: AGENTIC_AI_RISKS[x[0]]['categoria']))
    
    # Mostrar riscos
    for risk_id, risk_data in risks_to_show.items():
        risk_info = AGENTIC_AI_RISKS[risk_id]
        
        risk_class = "risk-low" if risk_data['level'] == "Baixo" else "risk-medium" if risk_data['level'] == "Moderado" else "risk-high"
        level_emoji = "🟢" if risk_data['level'] == "Baixo" else "🟡" if risk_data['level'] == "Moderado" else "🔴"
        
        with st.container():
            st.markdown(f"""
            <div class="risk-card {risk_class}">
                <h4>{level_emoji} {risk_id}. {risk_info['nome']}</h4>
                <p><strong>Categoria:</strong> {risk_info['categoria']} | <strong>Score:</strong> {risk_data['score']}/100 | <strong>Nível:</strong> {risk_data['level']}</p>
                <p><strong>Descrição:</strong> {risk_info['descricao']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Recomendações
            with st.expander(f"💡 Recomendações para {risk_info['nome']}"):
                for i, rec in enumerate(risk_data['recommendations'], 1):
                    st.write(f"**{i}.** {rec}")
                
                if risk_data['score'] >= 70:
                    st.error("⚠️ **ATENÇÃO:** Este é um risco de nível ALTO que requer ação imediata!")
                elif risk_data['score'] >= 40:
                    st.warning("⚡ **CUIDADO:** Este risco deve ser monitorado e mitigado.")
    
    # Botões de ação
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📄 Gerar Relatório", use_container_width=True):
            with st.spinner("Gerando relatório..."):
                pdf_generator = get_pdf_generator()
                report_bytes = pdf_generator.generate_report(analysis_result)
                
                # Determinar tipo de arquivo baseado na disponibilidade do PDF
                if PDF_AVAILABLE:
                    file_name = f"AgentRisk_Report_{analysis_result.get('system_name', 'Sistema')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                    mime_type = "application/pdf"
                else:
                    file_name = f"AgentRisk_Report_{analysis_result.get('system_name', 'Sistema')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt"
                    mime_type = "text/plain"
                
                st.download_button(
                    label="⬇️ Download Relatório",
                    data=report_bytes,
                    file_name=file_name,
                    mime=mime_type,
                    use_container_width=True
                )
    
    with col2:
        if st.button("📊 Ver Dashboard", use_container_width=True):
            # Simular mudança de página via session state
            st.session_state.show_dashboard = True
            st.rerun()
    
    with col3:
        if st.button("🔄 Nova Análise", use_container_width=True):
            for key in ['analysis_result', 'integrated_system']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    with col4:
        if st.button("📤 Compartilhar", use_container_width=True):
            st.info("🔗 Link de compartilhamento copiado! (funcionalidade em desenvolvimento)")

def show_dashboard_page():
    """Página de dashboard com métricas agregadas"""
    
    st.header("📊 Dashboard de Riscos")
    
    if 'analysis_result' not in st.session_state:
        st.warning("⚠️ Nenhuma análise disponível. Realize uma análise primeiro.")
        if st.button("🔙 Voltar para Análise"):
            st.rerun()
        return
    
    analysis = st.session_state.analysis_result
    
    # Informações do sistema analisado
    st.info(f"📊 Dashboard para: **{analysis.get('system_name', 'Sistema Anônimo')}**")
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Score Global", 
            f"{analysis['global_score']}/100",
            delta=f"{analysis['global_level']}"
        )
    
    with col2:
        high_risks = sum(1 for r in analysis['risks'].values() if r['level'] == 'Alto')
        st.metric("Riscos Altos", high_risks, delta=f"-{high_risks}" if high_risks > 0 else "0")
    
    with col3:
        medium_risks = sum(1 for r in analysis['risks'].values() if r['level'] == 'Moderado')
        st.metric("Riscos Moderados", medium_risks)
    
    with col4:
        low_risks = sum(1 for r in analysis['risks'].values() if r['level'] == 'Baixo')
        st.metric("Riscos Baixos", low_risks, delta=f"+{low_risks}" if low_risks > 0 else "0")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Distribuição por Nível de Risco")
        levels = [r['level'] for r in analysis['risks'].values()]
        level_counts = {
            'Alto': levels.count('Alto'),
            'Moderado': levels.count('Moderado'),
            'Baixo': levels.count('Baixo')
        }
        st.bar_chart(level_counts)
    
    with col2:
        st.subheader("🏷️ Distribuição por Categoria")
        categories = [AGENTIC_AI_RISKS[risk_id]['categoria'] for risk_id in analysis['risks'].keys()]
        category_counts = {}
        for cat in set(categories):
            category_counts[cat] = categories.count(cat)
        st.bar_chart(category_counts)
    
    # Top riscos mais críticos
    st.subheader("⚠️ Top 5 Riscos Mais Críticos")
    
    sorted_risks = sorted(
        analysis['risks'].items(),
        key=lambda x: x[1]['score'],
        reverse=True
    )[:5]
    
    for i, (risk_id, risk_data) in enumerate(sorted_risks, 1):
        risk_info = AGENTIC_AI_RISKS[risk_id]
        level_emoji = "🔴" if risk_data['level'] == "Alto" else "🟡" if risk_data['level'] == "Moderado" else "🟢"
        
        col1, col2, col3 = st.columns([1, 4, 1])
        
        with col1:
            st.markdown(f"**#{i}**")
        with col2:
            st.markdown(f"{level_emoji} **{risk_info['nome']}** - {risk_info['categoria']}")
        with col3:
            st.markdown(f"**{risk_data['score']}/100**")
    
    # Análise por categoria
    st.subheader("📋 Resumo por Categoria")
    
    # Agrupar riscos por categoria
    risks_by_category = {}
    for risk_id, risk_data in analysis['risks'].items():
        category = AGENTIC_AI_RISKS[risk_id]['categoria']
        if category not in risks_by_category:
            risks_by_category[category] = []
        risks_by_category[category].append((risk_id, risk_data))
    
    # Mostrar cada categoria
    for category, risks in risks_by_category.items():
        avg_score = sum(risk_data['score'] for _, risk_data in risks) / len(risks)
        high_count = sum(1 for _, risk_data in risks if risk_data['level'] == 'Alto')
        
        with st.expander(f"🔸 {category} - Score Médio: {avg_score:.1f}/100"):
            for risk_id, risk_data in risks:
                risk_info = AGENTIC_AI_RISKS[risk_id]
                level_emoji = "🔴" if risk_data['level'] == "Alto" else "🟡" if risk_data['level'] == "Moderado" else "🟢"
                st.write(f"{level_emoji} **{risk_info['nome']}**: {risk_data['score']}/100")

def show_integration_page():
    """Página de demonstração de integração"""
    
    st.header("🔗 Integração com Outros Sistemas")
    
    st.markdown("""
    Esta página demonstra como integrar o **AgentRisk** com outros sistemas do ecossistema Agente.
    """)
    
    # Sistemas exemplo do ecossistema
    st.subheader("🎯 Sistemas Disponíveis para Integração")
    
    example_systems = {
        "HeatGlass": {
            "name": "HeatGlass",
            "description": """Sistema de análise térmica autônomo que utiliza IA para processamento de imagens termográficas em tempo real, detecção automática de anomalias de temperatura, geração de alertas automatizados, integração com sensores IoT, machine learning para predição de falhas, interface web para visualização, API REST para integração, armazenamento de dados históricos e processamento de grandes volumes sem supervisão humana constante. O sistema toma decisões críticas sobre manutenção preventiva e pode parar operações automaticamente em caso de risco.""",
            "icon": "🌡️",
            "risk_level": "Alto"
        },
        "CarGlass Assistant": {
            "name": "CarGlass Assistant", 
            "description": """Assistente virtual autônomo para atendimento ao cliente que processa linguagem natural, acessa base de conhecimento para respostas automatizadas, integra com CRM e ERP, realiza agendamentos automaticamente, processa pagamentos e transações, coleta dados de clientes, toma decisões sobre aprovação de serviços, escala atendimento sem intervenção humana e utiliza dados pessoais para personalização. Sistema crítico para experiência do cliente e operações comerciais.""",
            "icon": "🚗",
            "risk_level": "Moderado"
        },
        "MindGlass": {
            "name": "MindGlass",
            "description": """Sistema de análise comportamental que utiliza deep learning para analisar padrões de usuários, toma decisões automatizadas baseadas em perfis comportamentais, processa dados biométricos e comportamentais sensíveis, sistema de recomendações personalizadas, integração com múltiplas fontes de dados, capacidade de adaptação e aprendizado contínuo, operação 24/7 com mínima supervisão e impacto direto em decisões críticas de negócio. Potencial alto impacto em privacidade e viés algorítmico.""",
            "icon": "🧠",
            "risk_level": "Alto"
        },
        "Oráculo": {
            "name": "Oráculo",
            "description": """Sistema de business intelligence autônomo que coleta dados de múltiplas fontes automaticamente, executa análises preditivas complexas, gera insights e recomendações estratégicas, toma decisões de investimento automatizadas, processa dados financeiros sensíveis, integra com sistemas bancários, monitora compliance, opera com alto nível de autonomia, influencia decisões corporativas críticas e utiliza algoritmos de machine learning não supervisionado. Sistema com impacto financeiro direto e decisões de alto valor.""",
            "icon": "🔮",
            "risk_level": "Alto"
        }
    }
    
    for system_key, system_info in example_systems.items():
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
            
            with col1:
                st.markdown(f"## {system_info['icon']}")
            
            with col2:
                st.markdown(f"**{system_info['name']}**")
                st.caption(f"Nível de Risco Estimado: {system_info['risk_level']}")
            
            with col3:
                risk_color = "🔴" if system_info['risk_level'] == "Alto" else "🟡"
                st.markdown(f"{risk_color} {system_info['risk_level']}")
            
            with col4:
                if st.button(f"🔗 Integrar", key=f"integrate_{system_key}", use_container_width=True):
                    st.session_state.integrated_system = system_info
                    st.success(f"✅ {system_info['name']} integrado com sucesso!")
                    st.balloons()
                    
                    # Auto-redirect para análise
                    st.info("🔄 Redirecionando para análise...")
                    st.rerun()
            
            with st.expander(f"📋 Ver descrição técnica - {system_info['name']}"):
                st.text_area("Descrição:", value=system_info['description'], height=100, disabled=True, key=f"desc_{system_key}")
    
    # Instruções de integração técnica
    st.markdown("---")
    st.subheader("🛠️ Instruções para Desenvolvedores")
    
    tab1, tab2, tab3 = st.tabs(["Session State", "API REST", "Botão de Integração"])
    
    with tab1:
        st.markdown("### Integração via Session State (Streamlit)")
        st.code("""
# No seu sistema principal (ex: HeatGlass)
import streamlit as st

if st.button("🛡️ Avaliar Riscos com AgentRisk"):
    # Definir dados do sistema
    st.session_state.integrated_system = {
        'name': 'Meu Sistema',
        'description': '''
        Descrição técnica detalhada do sistema:
        - Funcionalidades principais
        - Tecnologias utilizadas  
        - Dados processados
        - Nível de autonomia
        - Controles de segurança
        '''
    }
    
    # Redirecionar para AgentRisk
    st.switch_page("agentrisk.py")
        """, language="python")
    
    with tab2:
        st.markdown("### API REST (Versão Futura)")
        st.code("""
# Endpoint para análise de riscos
POST /api/v1/analyze

# Payload
{
    "system_name": "Nome do Sistema",
    "system_description": "Descrição técnica...",
    "analysis_options": {
        "include_recommendations": true,
        "risk_threshold": "moderate"
    }
}

# Response
{
    "analysis_id": "uuid",
    "global_score": 65.2,
    "global_level": "Moderado", 
    "risks": {...},
    "pdf_report_url": "https://..."
}
        """, language="json")
    
    with tab3:
        st.markdown("### Botão de Integração Universal")
        st.code("""
# Componente reutilizável para qualquer sistema
def agentrisk_integration_button(system_name, system_description):
    if st.button(f"🛡️ Avaliar {system_name} com AgentRisk", 
                 type="secondary",
                 use_container_width=True):
        
        st.session_state.integrated_system = {
            'name': system_name,
            'description': system_description
        }
        
        st.success(f"✅ {system_name} será analisado pelo AgentRisk")
        return True
    return False

# Uso em qualquer sistema
if agentrisk_integration_button("MeuSistema", "Descrição..."):
    # Lógica de redirecionamento
    pass
        """, language="python")

def show_risks_info_page():
    """Página com informações sobre os 15 riscos"""
    
    st.header("📋 Os 15 Riscos de Agentic AI")
    st.markdown("*Baseado no documento 'Agentic AI in Financial Services - IBM Consulting (Maio/2025)'*")
    
    # Organizar por categoria
    risks_by_category = {}
    for risk_id, risk_info in AGENTIC_AI_RISKS.items():
        category = risk_info['categoria']
        if category not in risks_by_category:
            risks_by_category[category] = []
        risks_by_category[category].append((risk_id, risk_info))
    
    # Mostrar estatísticas gerais
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Riscos", "15")
    with col2:
        st.metric("Categorias", len(risks_by_category))
    with col3:
        st.metric("Baseado em", "IBM Consulting 2025")
    
    # Mostrar riscos por categoria
    for category, risks in risks_by_category.items():
        st.subheader(f"🔸 {category}")
        
        for risk_id, risk_info in risks:
            with st.expander(f"{risk_id}. {risk_info['nome']}"):
                st.markdown(f"**Descrição:** {risk_info['descricao']}")
                st.markdown(f"**Categoria:** {risk_info['categoria']}")
                
                # Mostrar palavras-chave se disponíveis
                if 'keywords' in risk_info:
                    keywords_str = ", ".join(risk_info['keywords'])
                    st.markdown(f"**Palavras-chave:** {keywords_str}")
                
                # Exemplos de controles
                controls_examples = {
                    "1": "Definição clara de objetivos, validação regular de metas",
                    "2": "Thresholds de aprovação, escalação para humanos",
                    "3": "Rate limiting, monitoramento de uso, fallbacks",
                    "4": "Testes adversariais, diversidade de dados",
                    "5": "Políticas de retenção, esquecimento seletivo"
                }
                
                if risk_id in controls_examples:
                    st.info(f"💡 **Exemplos de Controles:** {controls_examples[risk_id]}")

def show_settings_page():
    """Página de configurações do sistema"""
    
    st.header("⚙️ Configurações do AgentRisk")
    
    # Configurações de OpenAI
    st.subheader("🤖 Configuração da IA")
    
    client = get_openai_client()
    if client:
        st.success("✅ OpenAI configurada e funcionando")
        
        # Teste de conectividade
        if st.button("🧪 Testar Conexão OpenAI"):
            try:
                with st.spinner("Testando conexão..."):
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": "Teste de conectividade. Responda apenas: OK"}],
                        max_tokens=10
                    )
                    st.success(f"✅ Teste bem-sucedido: {response.choices[0].message.content}")
            except Exception as e:
                st.error(f"❌ Erro no teste: {str(e)}")
    else:
        st.error("❌ OpenAI não configurada")
        st.info("""
        **Para configurar:**
        1. Acesse as configurações do app no Streamlit Cloud
        2. Vá em 'Secrets'
        3. Adicione: `OPENAI_API_KEY = "sua_chave_aqui"`
        4. Salve e faça redeploy
        """)
    
    # Configurações de análise
    st.subheader("🔧 Configurações de Análise")
    
    col1, col2 = st.columns(2)
    
    with col1:
        high_risk_threshold = st.slider("Limite para Risco Alto:", 50, 90, 70, 5)
        st.caption(f"Riscos com score ≥ {high_risk_threshold} serão classificados como 'Alto'")
    
    with col2:
        medium_risk_threshold = st.slider("Limite para Risco Moderado:", 20, 60, 40, 5)
        st.caption(f"Riscos com score ≥ {medium_risk_threshold} serão classificados como 'Moderado'")
    
    # Informações do sistema
    st.subheader("📊 Informações do Sistema")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"""
        **Versão:** AgentRisk v1.0
        **Deploy:** Streamlit Cloud
        **IA:** {'OpenAI GPT-4' if client else 'Análise Local'}
        **Riscos Analisados:** 15
        """)
    
    with col2:
        st.info(f"""
        **Última Atualização:** {datetime.datetime.now().strftime('%d/%m/%Y')}
        **Repositório:** GitHub (Auto-deploy)
        **Documentação:** IBM Consulting 2025
        **Status:** ✅ Operacional
        """)
    
    # Limpeza de dados
    st.subheader("🗑️ Gerenciamento de Dados")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Limpar Dados da Sessão", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("✅ Dados da sessão limpos!")
            st.rerun()
    
    with col2:
        if st.button("🔄 Reiniciar Aplicação", use_container_width=True):
            st.rerun()
    
    # Sobre o projeto
    st.markdown("---")
    st.subheader("ℹ️ Sobre o AgentRisk")
    
    st.markdown("""
    **AgentRisk** é um sistema de avaliação de riscos especializado em IA autônoma (Agentic AI).
    
    **Desenvolvido para:**
    - ✅ Avaliar 15 categorias específicas de riscos
    - ✅ Gerar relatórios executivos 
    - ✅ Integrar com ecossistema de sistemas
    - ✅ Garantir conformidade regulatória
    
    **Baseado em:**
    - 📚 "Agentic AI in Financial Services" - IBM Consulting (Maio/2025)
    - 🏛️ AI Act (União Europeia)
    - 🇧🇷 LGPD (Brasil)
    - 🌍 Melhores práticas internacionais
    
    **Próximas versões:**
    - 🔄 API REST completa
    - 🔄 Dashboard avançado
    - 🔄 Histórico de análises
    - 🔄 Alertas proativos
    """)

if __name__ == "__main__":
    main()
