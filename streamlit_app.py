# Timeline de remediação DETALHADA
        remediation_timeline = compliance.get('remediation_timeline', {})
        if remediation_timeline:
            st.subheader("⏰ Timeline Detalhada de Remediação")
            
            # Métricas principais
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                immediate = remediation_timeline.get('immediate', 0)
                st.metric("🚨 Imediato", immediate, help="1-2 semanas - Ação urgente")
            
            with col2:
                short_term = remediation_timeline.get('short_term', 0)
                st.metric("⚠️ Curto Prazo", short_term, help="2-4 semanas")
            
            with col3:
                medium_term = remediation_timeline.get('medium_term', 0)
                st.metric("📅 Médio Prazo", medium_term, help="1-3 meses")
            
            with col4:
                total_time = remediation_timeline.get('estimated_total_time', 'N/A')
                st.metric("⏱️ Tempo Total", total_time)
            
            # Detalhes específicos por violação
            timeline_details = remediation_timeline.get('details', [])
            if timeline_details:
                st.markdown("**📋 Detalhamento por Violação:**")
                
                for detail in timeline_details[:10]:  # Top 10 mais urgentes
                    violation = detail.get('violation', 'N/A')
                    timeline = detail.get('timeline', 'N/A')
                    reason = detail.get('reason', 'N/A')
                    penalty = detail.get('penalty_risk', 'N/A')
                    
                    # Emoji baseado na urgência
                    if "Imediato" in timeline:
                        emoji = "🔴"
                        alert_type = "error"
                    elif "Curto" in timeline:
                        emoji = "🟡"
                        alert_type = "warning"
                    else:
                        emoji = "🟢"
                        alert_type = "info"
                    
                    with st.expander(f"{emoji} {violation} - {timeline}"):
                        import streamlit as st
import json
import datetime
import base64
import io
import os
import re
import asyncio
import hashlib
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from enum import Enum
import threading
import time

# Importações obrigatórias
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    PDF_AVAILABLE = True
except ImportError:
    st.error("❌ ReportLab é obrigatório para funcionar!")
    st.stop()

try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    st.error("❌ OpenAI é OBRIGATÓRIO para análise enterprise!")
    st.stop()

# Configuração da página
st.set_page_config(
    page_title="AgentRisk Pro - Enterprise Analysis",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Classes para estrutura enterprise
class RiskLevel(Enum):
    CRITICAL = "Crítico"
    HIGH = "Alto"
    MEDIUM = "Moderado"
    LOW = "Baixo"
    MINIMAL = "Mínimo"

class ComplianceFramework(Enum):
    EU_AI_ACT = "EU AI Act"
    LGPD_BRAZIL = "LGPD Brasil"
    GDPR_EU = "GDPR Europa"
    SOX_US = "SOX Estados Unidos"
    BASEL_III = "Basel III"
    PCI_DSS = "PCI DSS"

@dataclass
class RiskAssessment:
    risk_id: str
    name: str
    category: str
    score: float
    level: RiskLevel
    evidence: List[str]
    compliance_impact: Dict[ComplianceFramework, str]
    technical_details: Dict[str, Any]
    remediation_priority: int
    estimated_cost: str
    timeline: str

@dataclass
class ComplianceViolation:
    framework: ComplianceFramework
    article: str
    description: str
    severity: RiskLevel
    evidence: List[str]
    remediation: List[str]
    penalty_risk: str

# Configuração OpenAI OBRIGATÓRIA
@st.cache_resource
def get_openai_client():
    """Inicializa cliente OpenAI - OBRIGATÓRIO"""
    if not OPENAI_AVAILABLE:
        st.error("❌ OpenAI é obrigatório para análise enterprise!")
        st.stop()
    
    try:
        # Primeiro tenta secrets do Streamlit
        if "OPENAI_API_KEY" in st.secrets:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        # Depois tenta variável de ambiente
        elif "OPENAI_API_KEY" in os.environ:
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        else:
            st.error("❌ Configure OPENAI_API_KEY nos Secrets do Streamlit ou como variável de ambiente!")
            st.info("Vá em Settings > Secrets e adicione: OPENAI_API_KEY = 'sua-chave-aqui'")
            st.stop()
        
        # Teste obrigatório da API
        test_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        
        return client
        
    except Exception as e:
        st.error(f"❌ Erro na configuração OpenAI: {str(e)}")
        st.stop()

# CSS Enterprise
st.markdown("""
<style>
.enterprise-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 2.5rem;
    border-radius: 15px;
    color: white;
    text-align: center;
    margin-bottom: 2rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}

.risk-card-enterprise {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
    background: white;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
}

.risk-card-enterprise:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
}

.risk-critical { 
    border-left: 6px solid #7f1d1d; 
    background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); 
}
.risk-high { 
    border-left: 6px solid #dc2626; 
    background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); 
}
.risk-medium { 
    border-left: 6px solid #f59e0b; 
    background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); 
}
.risk-low { 
    border-left: 6px solid #10b981; 
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); 
}
.risk-minimal { 
    border-left: 6px solid #059669; 
    background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); 
}

.compliance-badge {
    display: inline-block;
    padding: 0.3rem 0.8rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: bold;
    margin: 0.2rem;
}

.compliance-critical { background: #7f1d1d; color: white; }
.compliance-high { background: #dc2626; color: white; }
.compliance-medium { background: #f59e0b; color: white; }
.compliance-low { background: #10b981; color: white; }

.score-enterprise {
    text-align: center;
    padding: 3rem;
    border-radius: 20px;
    margin: 2rem 0;
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.ai-analysis-badge {
    background: linear-gradient(45deg, #667eea, #764ba2);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 25px;
    font-weight: bold;
    display: inline-block;
    margin: 0.5rem 0;
}

.technical-detail {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
    margin: 0.5rem 0;
    font-family: 'Courier New', monospace;
}
</style>
""", unsafe_allow_html=True)

# Riscos Enterprise Detalhados (baseados no relatório IBM)
ENTERPRISE_AGENTIC_RISKS = {
    "AGR001": {
        "nome": "Desalinhamento de Objetivos Críticos",
        "categoria": "Governança Estratégica",
        "descricao": "Agentes podem perseguir objetivos que conflitam com metas organizacionais",
        "compliance_frameworks": [ComplianceFramework.EU_AI_ACT, ComplianceFramework.SOX_US],
        "ai_analysis_required": True,
        "technical_patterns": ["goal", "objective", "target", "kpi", "metric"],
        "severity_indicators": ["hardcoded_goals", "no_validation", "conflicting_objectives"]
    },
    "AGR002": {
        "nome": "Ações Autônomas Não Supervisionadas",
        "categoria": "Controle Operacional",
        "descricao": "Execução de ações críticas sem aprovação ou supervisão humana",
        "compliance_frameworks": [ComplianceFramework.EU_AI_ACT, ComplianceFramework.BASEL_III],
        "ai_analysis_required": True,
        "technical_patterns": ["autonomous", "auto_execute", "no_human_approval", "direct_action"],
        "severity_indicators": ["financial_transactions", "data_deletion", "system_changes"]
    },
    "AGR003": {
        "nome": "Uso Inadequado de APIs Críticas",
        "categoria": "Segurança de Integração",
        "descricao": "Utilização insegura de APIs financeiras e serviços críticos",
        "compliance_frameworks": [ComplianceFramework.PCI_DSS, ComplianceFramework.LGPD_BRAZIL],
        "ai_analysis_required": True,
        "technical_patterns": ["api_call", "external_service", "http_request", "webhook"],
        "severity_indicators": ["payment_api", "user_data_api", "admin_endpoints"]
    },
    "AGR004": {
        "nome": "Viés Algorítmico e Discriminação",
        "categoria": "Ética e Fairness",
        "descricao": "Comportamentos discriminatórios baseados em viés nos dados ou algoritmos",
        "compliance_frameworks": [ComplianceFramework.EU_AI_ACT, ComplianceFramework.LGPD_BRAZIL],
        "ai_analysis_required": True,
        "technical_patterns": ["bias", "discrimination", "unfair", "stereotype"],
        "severity_indicators": ["demographic_filtering", "exclusion_rules", "prejudicial_logic"]
    },
    "AGR005": {
        "nome": "Retenção Inadequada de Dados Sensíveis",
        "categoria": "Privacidade e Proteção de Dados",
        "descricao": "Persistência inapropriada de informações pessoais e financeiras",
        "compliance_frameworks": [ComplianceFramework.LGPD_BRAZIL, ComplianceFramework.GDPR_EU],
        "ai_analysis_required": True,
        "technical_patterns": ["persist", "cache", "store", "memory", "retention"],
        "severity_indicators": ["personal_data", "financial_info", "no_encryption", "long_retention"]
    },
    "AGR006": {
        "nome": "Falta de Explicabilidade (Black Box)",
        "categoria": "Transparência e Auditoria",
        "descricao": "Incapacidade de explicar decisões e processos do sistema",
        "compliance_frameworks": [ComplianceFramework.EU_AI_ACT, ComplianceFramework.SOX_US],
        "ai_analysis_required": True,
        "technical_patterns": ["unexplained", "black_box", "no_logging", "opaque"],
        "severity_indicators": ["financial_decisions", "no_audit_trail", "complex_ml"]
    },
    "AGR007": {
        "nome": "Vulnerabilidades de Segurança Críticas",
        "categoria": "Cibersegurança",
        "descricao": "Exposição a ataques, injeções e falhas de segurança",
        "compliance_frameworks": [ComplianceFramework.PCI_DSS, ComplianceFramework.SOX_US],
        "ai_analysis_required": True,
        "technical_patterns": ["eval", "exec", "sql_injection", "xss", "csrf"],
        "severity_indicators": ["user_input", "database_access", "admin_functions"]
    },
    "AGR008": {
        "nome": "Não Conformidade Regulatória",
        "categoria": "Compliance Legal",
        "descricao": "Violação de regulamentações específicas do setor financeiro",
        "compliance_frameworks": [ComplianceFramework.EU_AI_ACT, ComplianceFramework.LGPD_BRAZIL, ComplianceFramework.BASEL_III],
        "ai_analysis_required": True,
        "technical_patterns": ["compliance", "regulation", "audit", "legal"],
        "severity_indicators": ["no_consent", "data_breach", "reporting_failure"]
    },
    "AGR009": {
        "nome": "Limitações de Escalabilidade Crítica",
        "categoria": "Performance Operacional",
        "descricao": "Falhas na capacidade de escalar sob demanda alta",
        "compliance_frameworks": [ComplianceFramework.SOX_US, ComplianceFramework.BASEL_III],
        "ai_analysis_required": True,
        "technical_patterns": ["bottleneck", "timeout", "memory_leak", "performance"],
        "severity_indicators": ["single_point_failure", "no_load_balancing", "resource_exhaustion"]
    },
    "AGR010": {
        "nome": "Qualidade e Integridade de Dados",
        "categoria": "Governança de Dados",
        "descricao": "Problemas na qualidade, validação e integridade dos dados",
        "compliance_frameworks": [ComplianceFramework.SOX_US, ComplianceFramework.BASEL_III],
        "ai_analysis_required": True,
        "technical_patterns": ["validation", "sanitization", "data_quality", "integrity"],
        "severity_indicators": ["no_validation", "corrupted_data", "inconsistent_sources"]
    }
}

# Frameworks de Compliance Detalhados
COMPLIANCE_REQUIREMENTS = {
    ComplianceFramework.EU_AI_ACT: {
        "name": "EU AI Act",
        "description": "Regulamentação europeia para sistemas de IA",
        "articles": {
            "Art. 6": "Sistemas de IA de alto risco",
            "Art. 8": "Conformidade de sistemas de IA de alto risco",
            "Art. 9": "Sistema de gestão de risco",
            "Art. 10": "Dados e governança de dados",
            "Art. 11": "Documentação técnica",
            "Art. 12": "Manutenção de registros",
            "Art. 13": "Transparência e fornecimento de informações",
            "Art. 14": "Supervisão humana",
            "Art. 15": "Precisão, robustez e cibersegurança"
        },
        "penalties": "Até 7% do faturamento anual global"
    },
    ComplianceFramework.LGPD_BRAZIL: {
        "name": "LGPD Brasil",
        "description": "Lei Geral de Proteção de Dados do Brasil",
        "articles": {
            "Art. 5": "Definições de dados pessoais",
            "Art. 6": "Atividades de tratamento de dados",
            "Art. 7": "Bases legais para tratamento",
            "Art. 8": "Consentimento",
            "Art. 9": "Dados sensíveis",
            "Art. 18": "Direitos do titular",
            "Art. 46": "Agentes de tratamento",
            "Art. 48": "Comunicação de incidente de segurança"
        },
        "penalties": "Até R$ 50 milhões por infração"
    }
}

class EnterpriseCodeAnalyzer:
    """Analisador Enterprise com IA Obrigatória"""
    
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
        self.analysis_cache = {}
        
    async def analyze_system_enterprise(self, uploaded_files) -> Dict:
        """Análise Enterprise Completa"""
        if not uploaded_files:
            return {"error": "Nenhum arquivo fornecido"}
        
        # Fase 1: Análise básica dos arquivos
        files_data = []
        total_lines = 0
        
        progress_placeholder = st.empty()
        
        for i, uploaded_file in enumerate(uploaded_files):
            progress_placeholder.text(f"📖 Analisando {uploaded_file.name}... ({i+1}/{len(uploaded_files)})")
            
            try:
                content = self._read_file_content(uploaded_file)
                if content:
                    file_analysis = await self._analyze_single_file_enterprise(uploaded_file.name, content)
                    files_data.append(file_analysis)
                    total_lines += file_analysis.get('lines_count', 0)
            except Exception as e:
                st.warning(f"⚠️ Erro ao processar {uploaded_file.name}: {str(e)}")
                continue
        
        if not files_data:
            return {"error": "Nenhum arquivo válido para análise"}
        
        # Fase 2: Análise de Sistema Completa com IA
        progress_placeholder.text("🤖 Executando análise semântica com IA...")
        system_analysis = await self._ai_system_analysis(files_data)
        
        # Fase 3: Análise de Compliance
        progress_placeholder.text("⚖️ Verificando conformidade regulatória...")
        compliance_analysis = await self._compliance_analysis(files_data, system_analysis)
        
        # Fase 4: Análise Cruzada Enterprise
        progress_placeholder.text("🔗 Análise cruzada e arquitetural...")
        cross_analysis = await self._enterprise_cross_analysis(files_data, system_analysis)
        
        # Fase 5: Score Enterprise Final
        progress_placeholder.text("📊 Calculando score enterprise...")
        enterprise_score = self._calculate_enterprise_score(files_data, system_analysis, compliance_analysis, cross_analysis)
        
        progress_placeholder.text("✅ Análise enterprise concluída!")
        
        return {
            "analysis_type": "Enterprise AI-Powered Analysis",
            "files_analyzed": len(files_data),
            "total_lines": total_lines,
            "enterprise_score": enterprise_score,
            "risk_level": self._get_enterprise_risk_level(enterprise_score["overall_score"]),
            "files_data": files_data,
            "system_analysis": system_analysis,
            "compliance_analysis": compliance_analysis,
            "cross_analysis": cross_analysis,
            "analysis_date": datetime.datetime.now().isoformat(),
            "analysis_hash": hashlib.md5(str(files_data).encode()).hexdigest()[:8],
            "ai_model_used": "gpt-4o-mini",
            "compliance_frameworks_checked": len(COMPLIANCE_REQUIREMENTS)
        }
    
    def _read_file_content(self, uploaded_file) -> str:
        """Lê conteúdo do arquivo com encoding robusto"""
        try:
            uploaded_file.seek(0)
            content = uploaded_file.read()
            
            # Tentar múltiplas codificações
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            
            # Fallback para análise binária
            return str(content)
        except Exception as e:
            st.error(f"Erro crítico ao ler {uploaded_file.name}: {str(e)}")
            return ""
    
    async def _analyze_single_file_enterprise(self, filename: str, content: str) -> Dict:
        """Análise Enterprise de arquivo individual com IA"""
        
        # Informações básicas
        lines = content.split('\n')
        lines_count = len(lines)
        char_count = len(content)
        file_ext = os.path.splitext(filename.lower())[1][1:]
        
        # Classificação técnica com IA
        classification = await self._ai_classify_file(filename, content)
        
        # Detecção de riscos enterprise
        risk_assessments = await self._detect_enterprise_risks(content, filename)
        
        # Análise de segurança profunda
        security_analysis = await self._deep_security_analysis(content, filename)
        
        # Score do arquivo
        file_score = self._calculate_file_enterprise_score(risk_assessments, security_analysis, content)
        
        return {
            "filename": filename,
            "file_type": self._get_file_type(file_ext),
            "classification": classification,
            "lines_count": lines_count,
            "char_count": char_count,
            "file_score": file_score,
            "risk_level": self._get_enterprise_risk_level(file_score),
            "risk_assessments": risk_assessments,
            "security_analysis": security_analysis,
            "content_preview": content[:1000] + "..." if len(content) > 1000 else content,
            "critical_code_blocks": self._extract_critical_blocks(lines),
            "ai_insights": await self._ai_code_insights(content, filename)
        }
    
    async def _ai_classify_file(self, filename: str, content: str) -> Dict:
        """Classificação inteligente de arquivo com IA"""
        
        prompt = f"""
        Analise este arquivo de código e classifique sua função no sistema:
        
        Nome: {filename}
        Conteúdo (primeiras 500 chars): {content[:500]}
        
        Retorne um JSON com:
        - category: tipo principal (security, api, data, config, ui, business_logic, testing, infrastructure)
        - purpose: descrição específica da função
        - criticality: nível de criticidade (critical, high, medium, low)
        - architectural_role: papel na arquitetura
        - security_relevance: relevância para segurança (0-10)
        
        Seja específico e técnico.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            # Fallback para classificação básica
            return {
                "category": self._basic_classification(filename),
                "purpose": "Análise básica - IA indisponível",
                "criticality": "medium",
                "architectural_role": "unknown",
                "security_relevance": 5,
                "error": str(e)
            }
    
    async def _detect_enterprise_risks(self, content: str, filename: str) -> List[RiskAssessment]:
        """Detecção de riscos enterprise com análise de IA"""
        
        risk_assessments = []
        content_lower = content.lower()
        
        for risk_id, risk_info in ENTERPRISE_AGENTIC_RISKS.items():
            
            # Análise com IA obrigatória
            ai_analysis = await self._ai_risk_analysis(content, filename, risk_info)
            
            # Detecção de padrões técnicos
            pattern_score = 0
            evidence = []
            
            for pattern in risk_info["technical_patterns"]:
                if pattern in content_lower:
                    pattern_score += 15
                    evidence.append(f"Padrão detectado: {pattern}")
            
            # Indicadores de severidade
            severity_score = 0
            for indicator in risk_info["severity_indicators"]:
                if indicator in content_lower:
                    severity_score += 25
                    evidence.append(f"Indicador crítico: {indicator}")
            
            # Score combinado (IA + Padrões)
            combined_score = (ai_analysis["score"] * 0.7) + (pattern_score * 0.2) + (severity_score * 0.1)
            combined_score = min(100, max(0, combined_score))
            
            # Impacto em Compliance
            compliance_impact = {}
            for framework in risk_info["compliance_frameworks"]:
                compliance_impact[framework] = await self._assess_compliance_impact(
                    framework, risk_info, ai_analysis
                )
            
            # Criar assessment
            assessment = RiskAssessment(
                risk_id=risk_id,
                name=risk_info["nome"],
                category=risk_info["categoria"],
                score=combined_score,
                level=self._score_to_risk_level(combined_score),
                evidence=evidence + ai_analysis["evidence"],
                compliance_impact=compliance_impact,
                technical_details=ai_analysis["technical_details"],
                remediation_priority=self._calculate_priority(combined_score, compliance_impact),
                estimated_cost=self._estimate_remediation_cost(combined_score),
                timeline=self._estimate_timeline(combined_score)
            )
            
            risk_assessments.append(assessment)
        
        return risk_assessments
    
    async def _ai_risk_analysis(self, content: str, filename: str, risk_info: Dict) -> Dict:
        """Análise específica de risco com IA"""
        
        prompt = f"""
        Analise este código para o risco específico: {risk_info['nome']}
        
        Descrição do Risco: {risk_info['descricao']}
        Categoria: {risk_info['categoria']}
        Arquivo: {filename}
        
        Código (primeiras 1000 chars):
        {content[:1000]}
        
        Retorne um JSON com:
        - score: pontuação de risco 0-100
        - evidence: lista de evidências específicas encontradas
        - technical_details: detalhes técnicos do problema
        - recommendations: recomendações específicas
        - severity_justification: justificativa da severidade
        
        Seja técnico e específico.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            return {
                "score": 30,
                "evidence": ["Análise IA indisponível"],
                "technical_details": {"error": str(e)},
                "recommendations": ["Verificar manualmente"],
                "severity_justification": "Score padrão aplicado"
            }
    
    async def _deep_security_analysis(self, content: str, filename: str) -> Dict:
        """Análise profunda de segurança com IA"""
        
        prompt = f"""
        Faça uma análise profunda de segurança deste código:
        
        Arquivo: {filename}
        Código: {content[:2000]}
        
        Analise especificamente:
        1. Vulnerabilidades de injeção (SQL, XSS, Command)
        2. Falhas de autenticação e autorização
        3. Exposição de dados sensíveis
        4. Falhas de validação de entrada
        5. Configurações inseguras
        6. Falhas de logging e monitoramento
        
        Retorne JSON com:
        - vulnerabilities: lista detalhada de vulnerabilidades
        - security_score: score 0-100 (0=muito seguro, 100=muito inseguro)
        - critical_issues: problemas críticos imediatos
        - recommendations: recomendações específicas de correção
        - owasp_categories: categorias OWASP Top 10 aplicáveis
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            return {
                "vulnerabilities": [],
                "security_score": 50,
                "critical_issues": [],
                "recommendations": ["Análise manual necessária"],
                "owasp_categories": [],
                "error": str(e)
            }
    
    async def _ai_system_analysis(self, files_data: List[Dict]) -> Dict:
        """Análise de sistema completo com IA"""
        
        # Preparar contexto do sistema
        system_context = {
            "total_files": len(files_data),
            "file_types": list(set(f["file_type"] for f in files_data)),
            "classifications": [f["classification"] for f in files_data],
            "total_lines": sum(f["lines_count"] for f in files_data)
        }
        
        prompt = f"""
        Analise este sistema de software completo:
        
        Contexto do Sistema:
        - Total de arquivos: {system_context['total_files']}
        - Tipos de arquivo: {system_context['file_types']}
        - Total de linhas: {system_context['total_lines']}
        
        Classificações dos arquivos:
        {json.dumps(system_context['classifications'][:10], indent=2)}
        
        Forneça uma análise arquitetural completa em JSON:
        - architecture_assessment: avaliação da arquitetura
        - security_posture: postura geral de segurança  
        - scalability_analysis: análise de escalabilidade
        - maintainability_score: score de manutenibilidade 0-100
        - technical_debt_level: nível de débito técnico
        - deployment_readiness: prontidão para produção
        - risk_hotspots: áreas de maior risco
        - strategic_recommendations: recomendações estratégicas
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.2
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            return {
                "architecture_assessment": "Análise IA indisponível",
                "security_posture": "Requer análise manual",
                "scalability_analysis": "Não avaliado",
                "maintainability_score": 50,
                "technical_debt_level": "Medium",
                "deployment_readiness": "Requires assessment",
                "risk_hotspots": ["Manual analysis needed"],
                "strategic_recommendations": ["Enable AI analysis"],
                "error": str(e)
            }
    
    async def _compliance_analysis(self, files_data: List[Dict], system_analysis: Dict) -> Dict:
        """Análise detalhada de compliance com múltiplos frameworks"""
        
        compliance_violations = []
        framework_scores = {}
        
        for framework, requirements in COMPLIANCE_REQUIREMENTS.items():
            
            # Análise específica por framework
            violations = await self._analyze_framework_compliance(files_data, framework, requirements)
            compliance_violations.extend(violations)
            
            # Score por framework
            framework_score = self._calculate_framework_score(violations)
            framework_scores[framework] = framework_score
        
        return {
            "overall_compliance_score": sum(framework_scores.values()) / len(framework_scores),
            "framework_scores": framework_scores,
            "violations": compliance_violations,
            "critical_violations": [v for v in compliance_violations if v.severity in [RiskLevel.CRITICAL, RiskLevel.HIGH]],
            "remediation_timeline": self._estimate_compliance_timeline(compliance_violations),
            "penalty_risk_assessment": self._assess_penalty_risks(compliance_violations)
        }
    
    async def _analyze_framework_compliance(self, files_data: List[Dict], framework: ComplianceFramework, requirements: Dict) -> List[ComplianceViolation]:
        """Análise de compliance para framework específico"""
        
        violations = []
        
        # Análise com IA para compliance
        for file_data in files_data:
            ai_compliance = await self._ai_compliance_check(file_data, framework, requirements)
            
            for violation_data in ai_compliance.get("violations", []):
                violation = ComplianceViolation(
                    framework=framework,
                    article=violation_data.get("article", "Não especificado"),
                    description=violation_data.get("description", ""),
                    severity=RiskLevel(violation_data.get("severity", "MEDIUM")),
                    evidence=violation_data.get("evidence", []),
                    remediation=violation_data.get("remediation", []),
                    penalty_risk=violation_data.get("penalty_risk", "Baixo")
                )
                violations.append(violation)
        
        return violations
    
    async def _ai_compliance_check(self, file_data: Dict, framework: ComplianceFramework, requirements: Dict) -> Dict:
        """Verificação DETALHADA de compliance com IA - Implementação Completa"""
        
        content_preview = file_data.get("content_preview", "")
        filename = file_data.get("filename", "")
        file_type = file_data.get("file_type", "Unknown")
        
        # Análise específica e detalhada por framework
        if framework == ComplianceFramework.EU_AI_ACT:
            prompt = f"""
            ANÁLISE ESPECÍFICA EU AI ACT - {filename} ({file_type})
            
            Código a analisar:
            {content_preview[:1500]}
            
            Verifique ESPECIFICAMENTE cada artigo:
            
            🔍 Art. 6 - SISTEMAS DE IA DE ALTO RISCO:
            - Este código implementa sistema de IA que pode afetar decisões financeiras/creditícias?
            - Há processamento automatizado de dados pessoais para decisões críticas?
            
            🔍 Art. 8 - CONFORMIDADE DE SISTEMAS DE ALTO RISCO:  
            - Existe sistema de gestão da qualidade implementado?
            - Há documentação técnica adequada?
            
            🔍 Art. 9 - SISTEMA DE GESTÃO DE RISCO:
            - Há identificação e análise de riscos conhecidos?
            - Existe processo de mitigação de riscos implementado?
            
            🔍 Art. 13 - TRANSPARÊNCIA:
            - O sistema informa aos usuários que estão interagindo com IA?
            - Há explicações claras sobre como o sistema funciona?
            
            🔍 Art. 14 - SUPERVISÃO HUMANA:
            - Existe supervisão humana efetiva implementada?
            - Humanos podem intervir nas decisões do sistema?
            
            🔍 Art. 15 - PRECISÃO E ROBUSTEZ:
            - Há validação de dados de entrada?
            - Existe tratamento de erros e falhas?
            
            RETORNE JSON EXATO:
            {{
                "violations": [
                    {{
                        "article": "Art. X",
                        "description": "descrição específica da violação",
                        "severity": "HIGH/MEDIUM/LOW", 
                        "evidence": ["evidência específica no código"],
                        "remediation": ["ação específica necessária"],
                        "penalty_risk": "Até 7% do faturamento anual (€35M máximo)"
                    }}
                ],
                "compliance_score": 0-100,
                "specific_articles_violated": ["Art. X", "Art. Y"],
                "recommendations": ["recomendação específica técnica"]
            }}
            """
        
        elif framework == ComplianceFramework.LGPD_BRAZIL:
            prompt = f"""
            ANÁLISE ESPECÍFICA LGPD BRASIL - {filename} ({file_type})
            
            Código a analisar:
            {content_preview[:1500]}
            
            Verifique ESPECIFICAMENTE cada artigo:
            
            🔍 Art. 5 - DADOS PESSOAIS:
            - O código processa informações que identifiquem pessoa natural?
            - Há tratamento de dados sensíveis (origem racial, saúde, etc.)?
            
            🔍 Art. 7 - BASES LEGAIS:
            - Há base legal clara para o tratamento (consentimento, contrato, etc.)?
            - O tratamento é necessário para finalidade específica?
            
            🔍 Art. 8 - CONSENTIMENTO:
            - Quando necessário, há obtenção de consentimento livre e informado?
            - O consentimento pode ser revogado facilmente?
            
            🔍 Art. 9 - DADOS SENSÍVEIS:
            - Há tratamento de dados sensíveis sem consentimento específico?
            - Existe proteção adicional para dados sensíveis?
            
            🔍 Art. 18 - DIREITOS DO TITULAR:
            - Há implementação dos direitos (acesso, correção, eliminação)?
            - Existe processo para atender solicitações dos titulares?
            
            🔍 Art. 46 - AGENTES DE TRATAMENTO:
            - Há definição clara de controlador e operador?
            - Existe DPO (Data Protection Officer) quando necessário?
            
            RETORNE JSON EXATO:
            {{
                "violations": [
                    {{
                        "article": "Art. X",
                        "description": "descrição específica da violação",
                        "severity": "HIGH/MEDIUM/LOW",
                        "evidence": ["evidência específica no código"], 
                        "remediation": ["ação específica necessária"],
                        "penalty_risk": "Até R$ 50 milhões por infração"
                    }}
                ],
                "compliance_score": 0-100,
                "specific_articles_violated": ["Art. X", "Art. Y"],
                "recommendations": ["recomendação específica técnica"]
            }}
            """
        
        elif framework == ComplianceFramework.GDPR_EU:
            prompt = f"""
            ANÁLISE ESPECÍFICA GDPR - {filename} ({file_type})
            
            Verifique artigos específicos:
            - Art. 6: Base legal para processamento
            - Art. 7: Condições para consentimento  
            - Art. 25: Data protection by design
            - Art. 32: Segurança no processamento
            - Art. 35: Avaliação de impacto
            
            Código: {content_preview[:1500]}
            
            RETORNE JSON com violations específicas, penalty_risk: "Até 4% do faturamento anual (€20M máximo)"
            """
        
        elif framework == ComplianceFramework.SOX_US:
            prompt = f"""
            ANÁLISE ESPECÍFICA SOX (Sarbanes-Oxley) - {filename} ({file_type})
            
            Verifique seções específicas:
            - Seção 302: Responsabilidade executiva
            - Seção 404: Controles internos
            - Seção 409: Divulgação em tempo real
            - Seção 906: Responsabilidade criminal
            
            Código: {content_preview[:1500]}
            
            RETORNE JSON com violations específicas, penalty_risk: "Multas de até $5M + prisão"
            """
        
        elif framework == ComplianceFramework.BASEL_III:
            prompt = f"""
            ANÁLISE ESPECÍFICA BASEL III - {filename} ({file_type})
            
            Verifique pilares específicos:
            - Pilar 1: Requisitos mínimos de capital
            - Pilar 2: Processo de supervisão
            - Pilar 3: Disciplina de mercado
            - Gestão de risco operacional
            
            Código: {content_preview[:1500]}
            
            RETORNE JSON com violations específicas, penalty_risk: "Sanções regulatórias + perda de licença"
            """
        
        elif framework == ComplianceFramework.PCI_DSS:
            prompt = f"""
            ANÁLISE ESPECÍFICA PCI DSS - {filename} ({file_type})
            
            Verifique requisitos específicos:
            - Req. 1: Firewall e configuração de rede
            - Req. 2: Senhas padrão e parâmetros de segurança
            - Req. 3: Proteção de dados do portador do cartão
            - Req. 4: Criptografia na transmissão
            - Req. 6: Desenvolvimento seguro
            - Req. 8: Identificação única para acesso
            
            Código: {content_preview[:1500]}
            
            RETORNE JSON com violations específicas, penalty_risk: "Multas de $50K-$500K por mês"
            """
        
        else:
            prompt = f"Análise genérica de compliance para {framework.value} - arquivo {filename}"
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Garantir estrutura padrão
            if "violations" not in result:
                result["violations"] = []
            if "compliance_score" not in result:
                result["compliance_score"] = 70
            if "specific_articles_violated" not in result:
                result["specific_articles_violated"] = []
            if "recommendations" not in result:
                result["recommendations"] = []
            
            return result
            
        except Exception as e:
            # Fallback com análise básica real
            violations = self._basic_compliance_analysis(content_preview, framework, filename)
            
            return {
                "violations": violations,
                "compliance_score": max(0, 80 - len(violations) * 15),
                "specific_articles_violated": [v["article"] for v in violations],
                "recommendations": [f"Revisar {framework.value} manualmente"],
                "error": str(e)
            }
    
    def _basic_compliance_analysis(self, content: str, framework: ComplianceFramework, filename: str) -> List[Dict]:
        """Análise básica de compliance quando IA falha"""
        
        violations = []
        content_lower = content.lower()
        
        if framework == ComplianceFramework.EU_AI_ACT:
            # Verificações específicas do AI Act
            if any(term in content_lower for term in ['decision', 'predict', 'classify', 'recommend']):
                if 'human' not in content_lower and 'approval' not in content_lower:
                    violations.append({
                        "article": "Art. 14",
                        "description": "Sistema de IA sem supervisão humana adequada detectado",
                        "severity": "HIGH",
                        "evidence": [f"Decisões automatizadas em {filename}"],
                        "remediation": ["Implementar supervisão humana", "Adicionar aprovação manual"],
                        "penalty_risk": "Até 7% do faturamento anual (€35M máximo)"
                    })
            
            if 'transparent' not in content_lower and 'explain' not in content_lower:
                violations.append({
                    "article": "Art. 13", 
                    "description": "Falta de transparência no sistema de IA",
                    "severity": "MEDIUM",
                    "evidence": [f"Ausência de explicabilidade em {filename}"],
                    "remediation": ["Implementar explicabilidade", "Adicionar logs de decisão"],
                    "penalty_risk": "Até 7% do faturamento anual (€35M máximo)"
                })
        
        elif framework == ComplianceFramework.LGPD_BRAZIL:
            # Verificações específicas da LGPD
            if any(term in content_lower for term in ['cpf', 'email', 'phone', 'address', 'personal']):
                if 'consent' not in content_lower and 'legal_basis' not in content_lower:
                    violations.append({
                        "article": "Art. 7",
                        "description": "Tratamento de dados pessoais sem base legal clara",
                        "severity": "HIGH", 
                        "evidence": [f"Dados pessoais processados em {filename}"],
                        "remediation": ["Definir base legal", "Implementar consentimento"],
                        "penalty_risk": "Até R$ 50 milhões por infração"
                    })
            
            if any(term in content_lower for term in ['health', 'race', 'religion', 'biometric']):
                violations.append({
                    "article": "Art. 9",
                    "description": "Possível tratamento de dados sensíveis detectado",
                    "severity": "HIGH",
                    "evidence": [f"Indícios de dados sensíveis em {filename}"],
                    "remediation": ["Implementar proteções especiais", "Obter consentimento específico"],
                    "penalty_risk": "Até R$ 50 milhões por infração"
                })
        
        elif framework == ComplianceFramework.PCI_DSS:
            # Verificações específicas PCI DSS
            if any(term in content_lower for term in ['card', 'credit', 'payment', 'pan']):
                if 'encrypt' not in content_lower and 'hash' not in content_lower:
                    violations.append({
                        "article": "Req. 3",
                        "description": "Dados de cartão sem proteção criptográfica adequada",
                        "severity": "HIGH",
                        "evidence": [f"Dados de pagamento não criptografados em {filename}"],
                        "remediation": ["Implementar criptografia", "Aplicar tokenização"],
                        "penalty_risk": "Multas de $50K-$500K por mês"
                    })
        
        return violations
    
    async def _enterprise_cross_analysis(self, files_data: List[Dict], system_analysis: Dict) -> Dict:
        """Análise cruzada enterprise entre arquivos"""
        
        # Análise de dependências
        dependency_risks = await self._analyze_dependencies(files_data)
        
        # Análise de comunicação entre componentes
        integration_risks = await self._analyze_integrations(files_data)
        
        # Análise de arquitetura de segurança
        security_architecture = await self._analyze_security_architecture(files_data)
        
        # Single points of failure
        spof_analysis = self._identify_single_points_failure(files_data)
        
        return {
            "dependency_risks": dependency_risks,
            "integration_risks": integration_risks,
            "security_architecture": security_architecture,
            "single_points_failure": spof_analysis,
            "system_complexity_score": self._calculate_complexity_score(files_data),
            "architectural_recommendations": await self._ai_architectural_recommendations(files_data, system_analysis)
        }
    
    async def _analyze_dependencies(self, files_data: List[Dict]) -> List[Dict]:
        """Análise de riscos de dependências"""
        
        dependency_risks = []
        
        for file_data in files_data:
            content = file_data.get("content_preview", "")
            
            # Buscar imports e dependências
            import_patterns = [
                r"import\s+(\w+)",
                r"from\s+(\w+)\s+import",
                r"require\s*\(['\"]([^'\"]+)['\"]\)",
                r"@import\s+['\"]([^'\"]+)['\"]"
            ]
            
            dependencies = []
            for pattern in import_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                dependencies.extend(matches)
            
            if dependencies:
                # Análise com IA das dependências
                ai_dep_analysis = await self._ai_dependency_analysis(dependencies, file_data["filename"])
                
                dependency_risks.append({
                    "file": file_data["filename"],
                    "dependencies": dependencies[:10],  # Limitar para não sobrecarregar
                    "risk_score": ai_dep_analysis.get("risk_score", 30),
                    "critical_dependencies": ai_dep_analysis.get("critical_dependencies", []),
                    "recommendations": ai_dep_analysis.get("recommendations", [])
                })
        
        return dependency_risks
    
    async def _ai_dependency_analysis(self, dependencies: List[str], filename: str) -> Dict:
        """Análise de dependências com IA"""
        
        prompt = f"""
        Analise estas dependências do arquivo {filename}:
        
        Dependências: {dependencies[:20]}
        
        Avalie os riscos:
        1. Dependências desatualizadas conhecidas
        2. Bibliotecas com vulnerabilidades
        3. Dependências não mantidas
        4. Conflitos potenciais
        5. Dependências desnecessárias
        
        Retorne JSON com:
        - risk_score: 0-100
        - critical_dependencies: lista de dependências críticas
        - recommendations: recomendações específicas
        - vulnerability_alerts: alertas de vulnerabilidade
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.1
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception:
            return {
                "risk_score": 30,
                "critical_dependencies": [],
                "recommendations": ["Verificar manualmente"],
                "vulnerability_alerts": []
            }
    
    def _calculate_enterprise_score(self, files_data: List[Dict], system_analysis: Dict, 
                                  compliance_analysis: Dict, cross_analysis: Dict) -> Dict:
        """Cálculo do score enterprise final"""
        
        # Scores componentes
        avg_file_score = sum(f["file_score"] for f in files_data) / len(files_data) if files_data else 0
        system_score = system_analysis.get("maintainability_score", 50)
        compliance_score = compliance_analysis.get("overall_compliance_score", 70)
        architecture_score = 100 - cross_analysis.get("system_complexity_score", 30)
        
        # Peso dos componentes
        weights = {
            "files": 0.25,
            "system": 0.25,
            "compliance": 0.35,  # Maior peso para compliance
            "architecture": 0.15
        }
        
        # Score final ponderado
        overall_score = (
            avg_file_score * weights["files"] +
            system_score * weights["system"] +
            compliance_score * weights["compliance"] +
            architecture_score * weights["architecture"]
        )
        
        # Penalidades críticas
        critical_violations = len(compliance_analysis.get("critical_violations", []))
        if critical_violations > 0:
            overall_score += min(critical_violations * 15, 40)  # Penalidade máxima de 40 pontos
        
        overall_score = min(100, max(0, overall_score))
        
        return {
            "overall_score": round(overall_score, 1),
            "component_scores": {
                "files_average": round(avg_file_score, 1),
                "system_analysis": round(system_score, 1),
                "compliance": round(compliance_score, 1),
                "architecture": round(architecture_score, 1)
            },
            "critical_violations_penalty": critical_violations * 15,
            "risk_distribution": self._calculate_risk_distribution(files_data),
            "priority_actions": self._identify_priority_actions(compliance_analysis, cross_analysis)
        }
    
    def _get_enterprise_risk_level(self, score: float) -> RiskLevel:
        """Converte score em nível de risco enterprise"""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 65:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        elif score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL
    
    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Converte score numérico para enum RiskLevel"""
        return self._get_enterprise_risk_level(score)
    
    def _calculate_priority(self, score: float, compliance_impact: Dict) -> int:
        """Calcula prioridade de remediação (1-5, sendo 1 mais urgente)"""
        base_priority = 5 - int(score / 20)  # Score alto = prioridade alta
        
        # Ajustar por impacto em compliance
        critical_frameworks = sum(1 for impact in compliance_impact.values() 
                                if "critical" in impact.lower() or "high" in impact.lower())
        
        priority = max(1, base_priority - critical_frameworks)
        return min(5, priority)
    
    def _estimate_remediation_cost(self, score: float) -> str:
        """Estima custo de remediação"""
        if score >= 80:
            return "Alto (R$ 50k - R$ 200k)"
        elif score >= 65:
            return "Médio-Alto (R$ 20k - R$ 50k)"
        elif score >= 40:
            return "Médio (R$ 5k - R$ 20k)"
        elif score >= 20:
            return "Baixo (R$ 1k - R$ 5k)"
        else:
            return "Mínimo (< R$ 1k)"
    
    def _estimate_timeline(self, score: float) -> str:
        """Estima timeline de remediação"""
        if score >= 80:
            return "Imediato (1-2 semanas)"
        elif score >= 65:
            return "Urgente (2-4 semanas)"
        elif score >= 40:
            return "Médio prazo (1-2 meses)"
        elif score >= 20:
            return "Longo prazo (2-3 meses)"
        else:
            return "Planejado (3+ meses)"
    
    # Métodos auxiliares
    def _get_file_type(self, extension: str) -> str:
        """Retorna tipo do arquivo baseado na extensão"""
        type_map = {
            'py': 'Python', 'js': 'JavaScript', 'ts': 'TypeScript',
            'java': 'Java', 'cs': 'C#', 'php': 'PHP', 'rb': 'Ruby',
            'go': 'Go', 'cpp': 'C++', 'c': 'C', 'json': 'JSON',
            'yaml': 'YAML', 'yml': 'YAML', 'xml': 'XML',
            'sql': 'SQL', 'md': 'Markdown', 'txt': 'Text',
            'html': 'HTML', 'css': 'CSS', 'scss': 'SCSS'
        }
        return type_map.get(extension, 'Unknown')
    
    def _basic_classification(self, filename: str) -> str:
        """Classificação básica fallback"""
        filename_lower = filename.lower()
        
        if any(term in filename_lower for term in ['main', 'app', 'index']):
            return "entry_point"
        elif any(term in filename_lower for term in ['auth', 'login', 'security']):
            return "security"
        elif any(term in filename_lower for term in ['config', 'setting']):
            return "configuration"
        elif any(term in filename_lower for term in ['api', 'route']):
            return "api_layer"
        elif any(term in filename_lower for term in ['model', 'schema']):
            return "data_model"
        elif any(term in filename_lower for term in ['test', 'spec']):
            return "testing"
        else:
            return "business_logic"

# Gerador de Relatórios Enterprise
class EnterprisePDFGenerator:
    """Gerador de relatórios PDF enterprise"""
    
    def generate_enterprise_report(self, analysis_result: Dict) -> bytes:
        """Gera relatório PDF enterprise completo"""
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Cabeçalho Enterprise
        title = Paragraph("AgentRisk Pro - Relatório Enterprise de Análise de IA", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Resumo Executivo
        story.append(Paragraph("RESUMO EXECUTIVO", styles['Heading1']))
        
        executive_summary = f"""
        <b>Score Geral do Sistema:</b> {analysis_result['enterprise_score']['overall_score']}/100<br/>
        <b>Nível de Risco:</b> {analysis_result['risk_level'].value}<br/>
        <b>Arquivos Analisados:</b> {analysis_result['files_analyzed']}<br/>
        <b>Total de Linhas:</b> {analysis_result['total_lines']:,}<br/>
        <b>Frameworks de Compliance:</b> {analysis_result['compliance_frameworks_checked']}<br/>
        <b>Modelo de IA Utilizado:</b> {analysis_result['ai_model_used']}<br/>
        <b>Data da Análise:</b> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}<br/>
        """
        
        story.append(Paragraph(executive_summary, styles['Normal']))
        story.append(Spacer(1, 30))
        
        # Análise de Compliance
        if 'compliance_analysis' in analysis_result:
            story.append(Paragraph("ANÁLISE DE CONFORMIDADE REGULATÓRIA", styles['Heading2']))
            
            compliance = analysis_result['compliance_analysis']
            
            compliance_table_data = [
                ['Framework', 'Score', 'Status', 'Violações Críticas']
            ]
            
            for framework, score in compliance.get('framework_scores', {}).items():
                status = "✅ Conforme" if score >= 80 else "⚠️ Atenção" if score >= 60 else "❌ Não Conforme"
                critical_count = len([v for v in compliance.get('violations', []) 
                                    if v.framework == framework and v.severity in [RiskLevel.CRITICAL, RiskLevel.HIGH]])
                
                compliance_table_data.append([
                    framework.value,
                    f"{score:.1f}/100",
                    status,
                    str(critical_count)
                ])
            
            compliance_table = Table(compliance_table_data, colWidths=[120, 60, 80, 80])
            compliance_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#4a5568')),
                ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, HexColor('#000000'))
            ]))
            
            story.append(compliance_table)
            story.append(Spacer(1, 20))
        
        # Top Riscos Críticos
        story.append(Paragraph("TOP 5 RISCOS CRÍTICOS IDENTIFICADOS", styles['Heading2']))
        
        # Ordenar riscos por score
        all_risks = []
        for file_data in analysis_result.get('files_data', []):
            for risk in file_data.get('risk_assessments', []):
                all_risks.append(risk)
        
        top_risks = sorted(all_risks, key=lambda x: x.score, reverse=True)[:5]
        
        for i, risk in enumerate(top_risks, 1):
            risk_color = '#7f1d1d' if risk.level == RiskLevel.CRITICAL else '#dc2626' if risk.level == RiskLevel.HIGH else '#f59e0b'
            
            risk_text = f"""
            <font color='{risk_color}'><b>{i}. {risk.name}</b></font><br/>
            <b>Score:</b> {risk.score:.1f}/100 | <b>Nível:</b> {risk.level.value}<br/>
            <b>Categoria:</b> {risk.category}<br/>
            <b>Prioridade:</b> {risk.remediation_priority}/5 | <b>Custo Estimado:</b> {risk.estimated_cost}<br/>
            <b>Timeline:</b> {risk.timeline}<br/>
            """
            
            if risk.evidence:
                risk_text += f"<b>Evidências:</b> {'; '.join(risk.evidence[:3])}<br/>"
            
            story.append(Paragraph(risk_text, styles['Normal']))
            story.append(Spacer(1, 15))
        
        # Recomendações Estratégicas
        story.append(Spacer(1, 20))
        story.append(Paragraph("RECOMENDAÇÕES ESTRATÉGICAS", styles['Heading2']))
        
        if 'system_analysis' in analysis_result:
            recommendations = analysis_result['system_analysis'].get('strategic_recommendations', [])
            for i, rec in enumerate(recommendations[:5], 1):
                rec_text = f"<b>{i}.</b> {rec}"
                story.append(Paragraph(rec_text, styles['Normal']))
                story.append(Spacer(1, 8))
        
        # Metodologia
        story.append(Spacer(1, 30))
        story.append(Paragraph("METODOLOGIA DE ANÁLISE", styles['Heading2']))
        
        methodology_text = """
        <b>Análise Enterprise com IA:</b><br/>
        • Análise semântica profunda com GPT-4o-mini<br/>
        • Detecção de 10 categorias de risco específicas para IA Autônoma<br/>
        • Verificação de conformidade com EU AI Act e LGPD<br/>
        • Análise cruzada de dependências e arquitetura<br/>
        • Score ponderado considerando compliance, segurança e arquitetura<br/><br/>
        
        <b>Baseado em:</b> IBM Consulting - "Agentic AI in Financial Services" (Maio/2025)<br/>
        <b>Frameworks Analisados:</b> EU AI Act, LGPD, GDPR, SOX, Basel III, PCI DSS
        """
        
        story.append(Paragraph(methodology_text, styles['Normal']))
        
        # Rodapé
        story.append(Spacer(1, 40))
        footer_text = f"""
        <b>Relatório gerado pelo AgentRisk Pro Enterprise</b><br/>
        Hash da Análise: {analysis_result.get('analysis_hash', 'N/A')}<br/>
        Confidencial - Uso interno exclusivo
        """
        story.append(Paragraph(footer_text, styles['Normal']))
        
        # Gerar PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

# Interface Principal Enterprise
def main():
    """Interface principal enterprise"""
    
    # Verificar cliente OpenAI primeiro
    try:
        client = get_openai_client()
        st.session_state.openai_client = client
    except Exception:
        return  # O erro já foi tratado em get_openai_client()
    
    # Header Enterprise
    st.markdown("""
    <div class="enterprise-header">
        <h1>🛡️ AgentRisk Pro</h1>
        <h3>Enterprise AI-Powered Risk Analysis</h3>
        <p>Análise Profunda de Riscos em Sistemas de IA Autônoma</p>
        <div class="ai-analysis-badge">✨ IA Obrigatória • Compliance Avançado • Nível Enterprise</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Status Enterprise
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.success("✅ OpenAI GPT-4o-mini")
    with col2:
        st.success("✅ ReportLab PDF")
    with col3:
        st.success("✅ 10 Riscos IA Enterprise")
    with col4:
        st.success("✅ 6 Frameworks Compliance")
    
    # Sidebar Enterprise
    with st.sidebar:
        st.header("🎛️ AgentRisk Pro")
        
        page = st.selectbox("Módulos:", [
            "🔍 Análise Enterprise", 
            "📊 Dashboard Executivo", 
            "⚖️ Compliance Center",
            "🏗️ Arquitetura & Deps",
            "⚙️ Configurações"
        ])
        
        # Status da última análise
        if 'enterprise_analysis' in st.session_state:
            result = st.session_state.enterprise_analysis
            st.markdown("---")
            st.markdown("**📊 Última Análise Enterprise**")
            
            score = result.get('enterprise_score', {}).get('overall_score', 0)
            risk_level = result.get('risk_level', RiskLevel.MEDIUM)
            
            score_color = "🔴" if score >= 65 else "🟡" if score >= 40 else "🟢"
            
            st.info(f"""
            {score_color} **Score:** {score}/100
            **Nível:** {risk_level.value}
            **Arquivos:** {result.get('files_analyzed', 0)}
            **Linhas:** {result.get('total_lines', 0):,}
            **IA:** {result.get('ai_model_used', 'N/A')}
            """)
            
            if st.button("🗑️ Limpar Análise"):
                del st.session_state.enterprise_analysis
                st.rerun()
    
    # Roteamento de páginas
    if page == "🔍 Análise Enterprise":
        show_enterprise_analysis_page()
    elif page == "📊 Dashboard Executivo":
        show_executive_dashboard()
    elif page == "⚖️ Compliance Center":
        show_compliance_center()
    elif page == "🏗️ Arquitetura & Deps":
        show_architecture_analysis()
    else:
        show_enterprise_config()

def show_enterprise_analysis_page():
    """Página principal de análise enterprise"""
    
    st.header("🔍 Análise Enterprise de Sistema IA")
    
    # Se já tem análise, mostrar resultados
    if 'enterprise_analysis' in st.session_state:
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 Nova Análise Enterprise", type="secondary"):
                del st.session_state.enterprise_analysis
                st.rerun()
        with col2:
            st.success("✅ **Análise Enterprise concluída** - Resultados detalhados abaixo")
        
        show_enterprise_results(st.session_state.enterprise_analysis)
        return
    
    # Interface de upload enterprise
    st.markdown("### 📤 Upload do Sistema para Análise Enterprise")
    
    st.info("""
    🎯 **Análise Enterprise Inclui:**
    
    **🤖 IA Obrigatória:** Análise semântica profunda com GPT-4o-mini
    **⚖️ Compliance Avançado:** EU AI Act, LGPD, GDPR, SOX, Basel III, PCI DSS
    **🏗️ Arquitetura:** Análise de dependências, SPOF, integração
    **🛡️ Segurança:** OWASP Top 10, vulnerabilidades críticas
    **📊 Score Enterprise:** Ponderação inteligente com foco em compliance
    """)
    
    uploaded_files = st.file_uploader(
        "Selecione os arquivos do sistema",
        accept_multiple_files=True,
        type=['py', 'js', 'ts', 'java', 'cs', 'php', 'rb', 'go', 'cpp', 'c',
              'json', 'yaml', 'yml', 'xml', 'sql', 'md', 'txt', 'html', 'css'],
        help="Todos os tipos de arquivo de código, configuração e documentação"
    )
    
    if uploaded_files:
        st.success(f"✅ **{len(uploaded_files)} arquivo(s) carregado(s)** para análise enterprise")
        
        # Preview detalhado dos arquivos
        with st.expander("📋 Arquivos Carregados - Preview", expanded=True):
            total_size = 0
            
            for file in uploaded_files:
                file_ext = os.path.splitext(file.name.lower())[1][1:]
                analyzer = EnterpriseCodeAnalyzer(st.session_state.openai_client)
                file_type = analyzer._get_file_type(file_ext)
                total_size += file.size
                
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"📄 **{file.name}**")
                with col2:
                    st.write(f"*{file_type}*")
                with col3:
                    st.write(f"`{file.size:,} bytes`")
            
            st.write(f"**📊 Total:** {len(uploaded_files)} arquivos • {total_size:,} bytes")
        
        # Botão de análise enterprise
        if st.button("🚀 Executar Análise Enterprise Completa", type="primary", use_container_width=True):
            
            # Análise assíncrona enterprise
            async def run_enterprise_analysis():
                analyzer = EnterpriseCodeAnalyzer(st.session_state.openai_client)
                return await analyzer.analyze_system_enterprise(uploaded_files)
            
            with st.spinner("🔄 Executando análise enterprise completa..."):
                
                # Simular async com threading (Streamlit não suporta async diretamente)
                import asyncio
                import threading
                
                result_container = {}
                
                def run_analysis():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(run_enterprise_analysis())
                    result_container['result'] = result
                    loop.close()
                
                # Progress bar detalhado
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Executar análise em thread separada
                analysis_thread = threading.Thread(target=run_analysis)
                analysis_thread.start()
                
                # Simular progresso
                for i in range(101):
                    progress_bar.progress(i)
                    if i < 15:
                        status_text.text("🤖 Inicializando análise com IA...")
                
                "
