import streamlit as st
import json
import datetime
import base64
import io
from typing import Dict, List, Tuple, Any
import re
import zipfile
import tempfile
import os

# Importações condicionais para evitar erros
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

# Configuração da página
st.set_page_config(
    page_title="AgentRisk - Análise de Código para Avaliação de Riscos",
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
            return None
    except Exception as e:
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
    .file-card {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .risk-high { border-left: 5px solid #dc2626; background: #fef2f2; }
    .risk-medium { border-left: 5px solid #f59e0b; background: #fffbeb; }
    .risk-low { border-left: 5px solid #10b981; background: #f0fdf4; }
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
    .code-preview {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 4px;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        max-height: 200px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# Definição dos 15 riscos baseados no documento IBM
AGENTIC_AI_RISKS = {
    "1": {
        "nome": "Desalinhamento de Objetivos",
        "descricao": "Agente pode buscar objetivos diferentes dos pretendidos pela organização",
        "categoria": "Governança",
        "code_patterns": ["todo", "fixme", "hack", "workaround", "temporary"]
    },
    "2": {
        "nome": "Ações Autônomas Indesejadas",
        "descricao": "Execução de ações sem aprovação humana adequada em contextos críticos",
        "categoria": "Autonomia",
        "code_patterns": ["auto", "automatic", "without_approval", "no_human", "direct_action"]
    },
    "3": {
        "nome": "Uso Indevido de APIs",
        "descricao": "Utilização inadequada ou excessiva de APIs e serviços externos",
        "categoria": "Integração",
        "code_patterns": ["requests.", "fetch(", "axios", "api_key", "http"]
    },
    "4": {
        "nome": "Decepção e Viés de Persona",
        "descricao": "Comportamentos enganosos ou enviesados baseados na persona do agente",
        "categoria": "Comportamento",
        "code_patterns": ["bias", "fake", "deceive", "manipulate", "persona"]
    },
    "5": {
        "nome": "Persistência de Memória Inadequada",
        "descricao": "Retenção inapropriada de informações sensíveis ou contextos obsoletos",
        "categoria": "Memória",
        "code_patterns": ["cache", "session", "memory", "persist", "store"]
    },
    "6": {
        "nome": "Transparência e Explicabilidade Limitada",
        "descricao": "Dificuldade em explicar decisões e processos de raciocínio do agente",
        "categoria": "Transparência",
        "code_patterns": ["black_box", "unexplained", "no_log", "silent"]
    },
    "7": {
        "nome": "Vulnerabilidades de Segurança",
        "descricao": "Exposição a ataques, vazamentos de dados e falhas de segurança",
        "categoria": "Segurança",
        "code_patterns": ["eval", "exec", "unsafe", "no_auth", "hardcoded"]
    },
    "8": {
        "nome": "Conformidade Regulatória",
        "descricao": "Não atendimento a regulamentações como AI Act, LGPD e normas setoriais",
        "categoria": "Compliance",
        "code_patterns": ["gdpr", "lgpd", "compliance", "regulation", "audit"]
    },
    "9": {
        "nome": "Escalabilidade e Performance",
        "descricao": "Limitações na capacidade de escalar e manter performance adequada",
        "categoria": "Performance",
        "code_patterns": ["bottleneck", "slow", "timeout", "performance", "scale"]
    },
    "10": {
        "nome": "Qualidade e Integridade dos Dados",
        "descricao": "Problemas na qualidade, completude e veracidade dos dados utilizados",
        "categoria": "Dados",
        "code_patterns": ["validate", "sanitize", "clean", "quality", "integrity"]
    },
    "11": {
        "nome": "Monitoramento e Auditoria",
        "descricao": "Ausência de sistemas adequados de monitoramento e trilhas de auditoria",
        "categoria": "Observabilidade",
        "code_patterns": ["log", "monitor", "audit", "track", "observe"]
    },
    "12": {
        "nome": "Gestão de Exceções e Falhas",
        "descricao": "Tratamento inadequado de situações excepcionais e recuperação de falhas",
        "categoria": "Robustez",
        "code_patterns": ["try", "except", "catch", "error", "fallback"]
    },
    "13": {
        "nome": "Dependências Externas",
        "descricao": "Riscos associados à dependência de serviços e recursos externos",
        "categoria": "Dependência",
        "code_patterns": ["import", "require", "dependency", "external", "third_party"]
    },
    "14": {
        "nome": "Impacto nos Stakeholders",
        "descricao": "Efeitos não intencionais em usuários, funcionários e outras partes interessadas",
        "categoria": "Social",
        "code_patterns": ["user", "customer", "employee", "stakeholder", "impact"]
    },
    "15": {
        "nome": "Evolução e Adaptação Descontrolada",
        "descricao": "Mudanças não supervisionadas no comportamento através de aprendizado contínuo",
        "categoria": "Evolução",
        "code_patterns": ["learning", "adapt", "evolve", "self_modify", "update_model"]
    }
}

# Tipos de arquivo suportados
SUPPORTED_EXTENSIONS = {
    '.py': 'Python',
    '.js': 'JavaScript', 
    '.ts': 'TypeScript',
    '.java': 'Java',
    '.cs': 'C#',
    '.php': 'PHP',
    '.rb': 'Ruby',
    '.go': 'Go',
    '.cpp': 'C++',
    '.c': 'C',
    '.json': 'JSON Config',
    '.yaml': 'YAML Config',
    '.yml': 'YAML Config',
    '.xml': 'XML Config',
    '.sql': 'SQL',
    '.md': 'Documentation',
    '.txt': 'Text'
}

class CodeFileAnalyzer:
    """Analisador de arquivos de código para detecção de riscos"""
    
    def __init__(self, openai_client=None):
        self.client = openai_client
    
    def analyze_files(self, uploaded_files) -> Dict:
        """Analisa múltiplos arquivos de código"""
        
        if not uploaded_files:
            return {"error": "Nenhum arquivo fornecido"}
        
        files_data = []
        total_lines = 0
        
        for uploaded_file in uploaded_files:
            try:
                file_content = self._read_file_content(uploaded_file)
                
                if file_content:
                    file_analysis = self._analyze_single_file(uploaded_file.name, file_content)
                    files_data.append(file_analysis)
                    total_lines += file_analysis.get('lines_count', 0)
                    
            except Exception as e:
                st.warning(f"⚠️ Erro ao processar {uploaded_file.name}: {str(e)}")
                continue
        
        if not files_data:
            return {"error": "Nenhum arquivo válido encontrado"}
        
        cross_analysis = self._cross_file_analysis(files_data)
        global_score = self._calculate_global_score(files_data, cross_analysis)
        
        return {
            "files_analyzed": len(files_data),
            "total_lines": total_lines,
            "global_score": global_score,
            "global_level": self._get_risk_level(global_score),
            "files_data": files_data,
            "cross_analysis": cross_analysis,
            "risks_summary": self._generate_risks_summary(files_data),
            "analysis_date": datetime.datetime.now().isoformat(),
            "analysis_method": "Análise de Código Multi-Arquivo"
        }
    
    def _read_file_content(self, uploaded_file) -> str:
        """Lê o conteúdo de um arquivo uploaded"""
        try:
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    uploaded_file.seek(0)
                    content = uploaded_file.read().decode(encoding)
                    return content
                except UnicodeDecodeError:
                    continue
            
            uploaded_file.seek(0)
            return str(uploaded_file.read())
            
        except Exception as e:
            st.error(f"Erro ao ler arquivo {uploaded_file.name}: {str(e)}")
            return ""
    
    def _analyze_single_file(self, filename: str, content: str) -> Dict:
        """Analisa um único arquivo de código"""
        
        file_ext = os.path.splitext(filename.lower())[1]
        file_type = SUPPORTED_EXTENSIONS.get(file_ext, 'Unknown')
        
        lines = content.split('\n')
        lines_count = len(lines)
        char_count = len(content)
        
        file_classification = self._classify_file_purpose(filename, content)
        risk_patterns = self._detect_risk_patterns(content)
        security_issues = self._detect_security_issues(content, file_ext)
        file_score = self._calculate_file_score(risk_patterns, security_issues, content)
        
        return {
            "filename": filename,
            "file_type": file_type,
            "file_extension": file_ext,
            "classification": file_classification,
            "lines_count": lines_count,
            "char_count": char_count,
            "file_score": file_score,
            "risk_level": self._get_risk_level(file_score),
            "risk_patterns": risk_patterns,
            "security_issues": security_issues,
            "content_preview": self._get_content_preview(content),
            "critical_lines": self._find_critical_lines(lines)
        }
    
    def _classify_file_purpose(self, filename: str, content: str) -> str:
        """Classifica o propósito do arquivo"""
        filename_lower = filename.lower()
        content_lower = content.lower()
        
        if any(term in filename_lower for term in ['main', 'app', 'server', 'index']):
            return "entry_point"
        elif any(term in filename_lower for term in ['auth', 'login', 'security']):
            return "security"
        elif any(term in filename_lower for term in ['model', 'schema', 'database', 'db']):
            return "data_model"
        elif any(term in filename_lower for term in ['config', 'setting', 'env']):
            return "configuration"
        elif any(term in filename_lower for term in ['api', 'endpoint', 'route']):
            return "api_layer"
        elif any(term in filename_lower for term in ['test', 'spec']):
            return "testing"
        elif filename_lower.endswith('.md'):
            return "documentation"
        else:
            return "business_logic"
    
    def _detect_risk_patterns(self, content: str) -> Dict:
        """Detecta padrões de risco no código"""
        content_lower = content.lower()
        detected_risks = {}
        
        for risk_id, risk_info in AGENTIC_AI_RISKS.items():
            risk_score = 0
            found_patterns = []
            
            for pattern in risk_info.get('code_patterns', []):
                if pattern in content_lower:
                    risk_score += 20
                    found_patterns.append(pattern)
            
            critical_patterns = {
                'eval(': 50, 'exec(': 50, 'unsafe': 30,
                'hardcoded': 40, 'password': 30, 'secret': 30,
                'admin': 20, 'root': 25, 'sudo': 30
            }
            
            for pattern, score_increase in critical_patterns.items():
                if pattern in content_lower:
                    risk_score += score_increase
                    found_patterns.append(pattern)
            
            detected_risks[risk_id] = {
                "score": min(100, max(0, risk_score)),
                "level": self._get_risk_level(risk_score),
                "patterns_found": found_patterns,
                "risk_name": risk_info["nome"]
            }
        
        return detected_risks
    
    def _detect_security_issues(self, content: str, file_ext: str) -> List[Dict]:
        """Detecta problemas específicos de segurança"""
        issues = []
        lines = content.split('\n')
        
        security_patterns = {
            'hardcoded_secrets': [
                r'password\s*=\s*["\'][^"\']+["\']',
                r'api_key\s*=\s*["\'][^"\']+["\']',
                r'secret\s*=\s*["\'][^"\']+["\']',
                r'token\s*=\s*["\'][^"\']+["\']'
            ],
            'dangerous_functions': [
                r'eval\s*\(',
                r'exec\s*\(',
                r'system\s*\(',
                r'shell_exec\s*\('
            ]
        }
        
        for line_num, line in enumerate(lines, 1):
            for issue_type, patterns in security_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append({
                            "type": issue_type,
                            "line": line_num,
                            "content": line.strip(),
                            "severity": "HIGH" if issue_type in ['dangerous_functions', 'hardcoded_secrets'] else "MEDIUM",
                            "description": self._get_security_issue_description(issue_type)
                        })
        
        return issues
    
    def _get_security_issue_description(self, issue_type: str) -> str:
        """Retorna descrição do problema de segurança"""
        descriptions = {
            'hardcoded_secrets': 'Credenciais hardcoded no código',
            'dangerous_functions': 'Uso de funções perigosas (eval, exec)'
        }
        return descriptions.get(issue_type, 'Problema de segurança detectado')
    
    def _calculate_file_score(self, risk_patterns: Dict, security_issues: List, content: str) -> float:
        """Calcula score de risco para um arquivo"""
        base_score = 20
        patterns_score = sum(risk['score'] for risk in risk_patterns.values()) / len(risk_patterns)
        
        security_score = 0
        for issue in security_issues:
            if issue['severity'] == 'HIGH':
                security_score += 30
            elif issue['severity'] == 'MEDIUM':
                security_score += 15
        
        good_practices = ['try:', 'except:', 'logging.', 'log.', 'validate']
        reduction = sum(5 for practice in good_practices if practice in content.lower())
        
        final_score = base_score + (patterns_score * 0.6) + security_score - reduction
        return max(0, min(100, final_score))
    
    def _get_risk_level(self, score: float) -> str:
        """Converte score em nível de risco"""
        if score >= 70:
            return "Alto"
        elif score >= 40:
            return "Moderado"
        else:
            return "Baixo"
    
    def _get_content_preview(self, content: str, max_lines: int = 10) -> str:
        """Gera preview do conteúdo do arquivo"""
        lines = content.split('\n')[:max_lines]
        return '\n'.join(lines)
    
    def _find_critical_lines(self, lines: List[str]) -> List[Dict]:
        """Encontra linhas críticas no código"""
        critical_lines = []
        critical_keywords = ['password', 'secret', 'token', 'api_key', 'eval', 'exec']
        
        for line_num, line in enumerate(lines, 1):
            if any(keyword in line.lower() for keyword in critical_keywords):
                critical_lines.append({
                    "line_number": line_num,
                    "content": line.strip(),
                    "reason": "Contém palavras-chave críticas"
                })
        
        return critical_lines[:5]
    
    def _cross_file_analysis(self, files_data: List[Dict]) -> Dict:
        """Análise cruzada entre arquivos"""
        cross_risks = []
        
        config_files = [f for f in files_data if f['classification'] == 'configuration']
        api_files = [f for f in files_data if f['classification'] == 'api_layer']
        auth_files = [f for f in files_data if f['classification'] == 'security']
        
        if config_files:
            for config_file in config_files:
                if any(issue['type'] == 'hardcoded_secrets' for issue in config_file['security_issues']):
                    cross_risks.append({
                        "type": "credentials_exposure",
                        "description": f"Credenciais em {config_file['filename']} podem afetar toda aplicação",
                        "severity": "HIGH",
                        "affected_files": [f['filename'] for f in files_data if f != config_file]
                    })
        
        if api_files and not auth_files:
            cross_risks.append({
                "type": "api_without_auth",
                "description": "APIs detectadas sem sistema de autenticação correspondente",
                "severity": "HIGH",
                "affected_files": [f['filename'] for f in api_files]
            })
        
        return {
            "risks_found": len(cross_risks),
            "cross_risks": cross_risks,
            "system_architecture": self._analyze_system_architecture(files_data)
        }
    
    def _analyze_system_architecture(self, files_data: List[Dict]) -> Dict:
        """Analisa a arquitetura geral do sistema"""
        architecture = {
            "entry_points": len([f for f in files_data if f['classification'] == 'entry_point']),
            "api_layers": len([f for f in files_data if f['classification'] == 'api_layer']),
            "data_models": len([f for f in files_data if f['classification'] == 'data_model']),
            "security_files": len([f for f in files_data if f['classification'] == 'security']),
            "config_files": len([f for f in files_data if f['classification'] == 'configuration']),
            "test_files": len([f for f in files_data if f['classification'] == 'testing'])
        }
        
        completeness_score = 0
        if architecture["entry_points"] > 0: completeness_score += 20
        if architecture["api_layers"] > 0: completeness_score += 15
        if architecture["security_files"] > 0: completeness_score += 25
        if architecture["test_files"] > 0: completeness_score += 20
        if architecture["config_files"] > 0: completeness_score += 10
        if architecture["data_models"] > 0: completeness_score += 10
        
        architecture["completeness_score"] = completeness_score
        return architecture
    
    def _calculate_global_score(self, files_data: List[Dict], cross_analysis: Dict) -> float:
        """Calcula score global do sistema"""
        if not files_data:
            return 0
        
        avg_file_score = sum(f['file_score'] for f in files_data) / len(files_data)
        cross_penalty = len(cross_analysis.get('cross_risks', [])) * 15
        
        arch_bonus = 0
        if cross_analysis.get('system_architecture', {}).get('completeness_score', 0) > 80:
            arch_bonus = 10
        
        global_score = avg_file_score + cross_penalty - arch_bonus
        return max(0, min(100, global_score))
    
    def _generate_risks_summary(self, files_data: List[Dict]) -> Dict:
        """Gera resumo dos riscos encontrados"""
        all_risks = {}
        
        for risk_id, risk_info in AGENTIC_AI_RISKS.items():
            risk_scores = []
            affected_files = []
            
            for file_data in files_data:
                file_risk = file_data['risk_patterns'].get(risk_id, {})
                if file_risk.get('score', 0) > 0:
                    risk_scores.append(file_risk['score'])
                    affected_files.append(file_data['filename'])
            
            if risk_scores:
                avg_score = sum(risk_scores) / len(risk_scores)
                all_risks[risk_id] = {
                    "nome": risk_info["nome"],
                    "categoria": risk_info["categoria"],
                    "score": round(avg_score, 1),
                    "level": self._get_risk_level(avg_score),
                    "affected_files": affected_files,
                    "recommendations": self._get_recommendations(risk_id)
                }
        
        return all_risks
    
    def _get_recommendations(self, risk_id: str) -> List[str]:
        """Gera recomendações específicas para cada risco"""
        recommendations_map = {
            "1": ["Definir objetivos claros nos comentários", "Implementar validação de metas"],
            "2": ["Adicionar aprovação humana para ações críticas", "Implementar thresholds"],
            "3": ["Implementar rate limiting nas APIs", "Usar variáveis de ambiente"],
            "7": ["Remover funções eval() e exec()", "Implementar validação de entrada"]
        }
        return recommendations_map.get(risk_id, ["Implementar melhores práticas de segurança"])

class PDFGenerator:
    """Gerador de relatórios em PDF para análise de código"""
    
    def __init__(self):
        self.pdf_available = PDF_AVAILABLE
    
    def generate_code_analysis_report(self, analysis_result: Dict) -> bytes:
        """Gera relatório PDF da análise de código"""
        
        if not self.pdf_available:
            return self._generate_text_report(analysis_result)
        
        try:
            pdf = FPDF()
            pdf.add_page()
            
            pdf.set_font("Arial", "B", 18)
            pdf.cell(0, 15, "AgentRisk - Analise de Codigo", 0, 1, 'C')
            
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 8, f"Arquivos: {analysis_result['files_analyzed']}", 0, 1, 'C')
            pdf.cell(0, 8, f"Linhas: {analysis_result['total_lines']}", 0, 1, 'C')
            pdf.cell(0, 8, f"Data: {datetime.datetime.now().strftime('%d/%m/%Y')}", 0, 1, 'C')
            pdf.ln(10)
            
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "RESUMO EXECUTIVO", 0, 1)
            pdf.set_font("Arial", size=11)
            
            global_score = analysis_result['global_score']
            pdf.cell(0, 8, f"Score Global: {global_score}/100", 0, 1)
            pdf.cell(0, 8, f"Nivel: {analysis_result['global_level']}", 0, 1)
            pdf.ln(8)
            
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "ANALISE POR ARQUIVO", 0, 1)
            pdf.set_font("Arial", size=9)
            
            for file_data in analysis_result['files_data'][:5]:
                pdf.cell(0, 6, f"Arquivo: {file_data['filename']}", 0, 1)
                pdf.cell(0, 5, f"Score: {file_data['file_score']}/100", 0, 1)
                pdf.ln(2)
            
            return pdf.output(dest='S').encode('latin-1')
            
        except Exception as e:
            return self._generate_text_report(analysis_result)
    
    def _generate_text_report(self, analysis_result: Dict) -> bytes:
        """Gera relatório em texto como fallback"""
        
        report = f"""
AGENTRISK - ANÁLISE DE CÓDIGO
============================

Arquivos: {analysis_result['files_analyzed']}
Linhas: {analysis_result['total_lines']}
Score: {analysis_result['global_score']}/100
Nível: {analysis_result['global_level']}
Data: {datetime.datetime.now().strftime('%d/%m/%Y')}

ANÁLISE POR ARQUIVO
==================
"""
        
        for file_data in analysis_result['files_data']:
            report += f"\n📄 {file_data['filename']}\n"
            report += f"   Score: {file_data['file_score']}/100\n"
            report += f"   Tipo: {file_data['file_type']}\n"
        
        return report.encode('utf-8')

@st.cache_resource
def get_code_analyzer():
    client = get_openai_client()
    return CodeFileAnalyzer(client)

@st.cache_resource  
def get_pdf_generator():
    return PDFGenerator()

def main():
    """Função principal da aplicação"""
    
    st.markdown("""
    <div class="main-header">
        <h1>🛡️ AgentRisk</h1>
        <p>Análise de Código para Avaliação de Riscos em IA Autônoma</p>
        <small>🚀 Streamlit Cloud | Análise Multi-Arquivo</small>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        client = get_openai_client()
        if client:
            st.success("✅ OpenAI: Ativo")
        else:
            st.info("ℹ️ OpenAI: Local")
    
    with col2:
        if PDF_AVAILABLE:
            st.success("✅ PDF: Disponível")
        else:
            st.info("ℹ️ PDF: Texto")
            
    with col3:
        st.success("✅ Análise: Ativo")
    
    with st.sidebar:
        st.header("📋 Menu")
        page = st.selectbox("Escolha:", ["🔍 Análise", "📊 Dashboard", "⚙️ Config"])
    
    if page == "🔍 Análise":
        show_settings_page()

def show_code_analysis_page():
    """Página principal de análise de código"""
    
    st.header("🔍 Análise de Código Multi-Arquivo")
    
    if 'analysis_result' in st.session_state:
        if st.button("🔄 Nova Análise", type="secondary"):
            del st.session_state.analysis_result
            st.rerun()
        
        show_analysis_results(st.session_state.analysis_result)
        return
    
    st.markdown("### 📤 Upload dos Arquivos do Sistema")
    
    uploaded_files = st.file_uploader(
        "Selecione os arquivos do seu sistema",
        accept_multiple_files=True,
        type=list(SUPPORTED_EXTENSIONS.keys()),
        help="Arquivos de código, configuração e documentação"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} arquivo(s) carregado(s)")
        
        with st.expander("📋 Arquivos Carregados", expanded=True):
            for file in uploaded_files:
                file_ext = os.path.splitext(file.name.lower())[1]
                file_type = SUPPORTED_EXTENSIONS.get(file_ext, 'Desconhecido')
                st.write(f"📄 **{file.name}** - {file_type} ({file.size:,} bytes)")
        
        if st.button("🔍 Analisar Sistema Completo", type="primary", use_container_width=True):
            with st.spinner("🔄 Analisando arquivos..."):
                progress_bar = st.progress(0)
                
                for i in range(100):
                    progress_bar.progress(i + 1)
                
                analyzer = get_code_analyzer()
                analysis_result = analyzer.analyze_files(uploaded_files)
                
                if 'error' in analysis_result:
                    st.error(f"❌ {analysis_result['error']}")
                    return
                
                st.session_state.analysis_result = analysis_result
                st.success("🎉 Análise concluída!")
                st.balloons()
                st.rerun()
    
    else:
        st.info("""
        ### 💡 Como Usar
        
        1. **📁 Selecione os arquivos** do seu sistema
        2. **🔍 Clique em "Analisar"** para processar
        3. **📊 Visualize os resultados** detalhados
        4. **📄 Gere relatórios** em PDF/texto
        
        ### 📋 Tipos Suportados
        Python, JavaScript, Java, C#, PHP, JSON, YAML, etc.
        """)

def show_analysis_results(analysis_result: Dict):
    """Exibe os resultados da análise de código"""
    
    st.header("📊 Resultados da Análise")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📁 Arquivos", analysis_result['files_analyzed'])
    with col2:
        st.metric("📝 Linhas", f"{analysis_result['total_lines']:,}")
    with col3:
        st.metric("🎯 Score", f"{analysis_result['global_score']}/100")
    with col4:
        st.metric("⏰ Método", "Multi-Arquivo")
    
    global_score = analysis_result['global_score']
    global_level = analysis_result['global_level']
    
    score_class = "score-low" if global_score < 40 else "score-medium" if global_score < 70 else "score-high"
    emoji = "🟢" if global_score < 40 else "🟡" if global_score < 70 else "🔴"
    
    st.markdown(f"""
    <div class="score-container {score_class}">
        <h2>{emoji} Score Global do Sistema</h2>
        <h1>{global_score}/100</h1>
        <h3>Nível: {global_level}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.subheader("📁 Análise por Arquivo")
    
    for file_data in analysis_result['files_data']:
        risk_class = f"risk-{file_data['risk_level'].lower()}"
        level_emoji = "🟢" if file_data['risk_level'] == "Baixo" else "🟡" if file_data['risk_level'] == "Moderado" else "🔴"
        
        st.markdown(f"""
        <div class="file-card {risk_class}">
            <h4>{level_emoji} 📄 {file_data['filename']}</h4>
            <p><strong>Score:</strong> {file_data['file_score']}/100 | 
               <strong>Tipo:</strong> {file_data['file_type']} | 
               <strong>Linhas:</strong> {file_data['lines_count']:,}</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander(f"🔍 Detalhes - {file_data['filename']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Score", f"{file_data['file_score']}/100")
                st.write(f"**Tipo:** {file_data['file_type']}")
            
            with col2:
                st.metric("Linhas", f"{file_data['lines_count']:,}")
                st.write(f"**Classificação:** {file_data['classification']}")
            
            if file_data['security_issues']:
                st.write("**🚨 Problemas de Segurança:**")
                for issue in file_data['security_issues']:
                    severity_color = "🔴" if issue['severity'] == 'HIGH' else "🟡"
                    st.write(f"{severity_color} **Linha {issue['line']}:** {issue['description']}")
            
            if file_data['content_preview']:
                st.write("**📄 Preview:**")
                st.code(file_data['content_preview'][:500] + "..." if len(file_data['content_preview']) > 500 else file_data['content_preview'])
    
    if 'cross_analysis' in analysis_result and analysis_result['cross_analysis']['risks_found'] > 0:
        st.subheader("🔗 Análise Cruzada")
        
        for cross_risk in analysis_result['cross_analysis']['cross_risks']:
            severity_color = "🔴" if cross_risk['severity'] == 'HIGH' else "🟡"
            st.warning(f"{severity_color} **{cross_risk['description']}**")
    
    if 'risks_summary' in analysis_result and analysis_result['risks_summary']:
        st.subheader("📋 Top Riscos Detectados")
        
        sorted_risks = sorted(
            analysis_result['risks_summary'].items(), 
            key=lambda x: x[1]['score'], 
            reverse=True
        )[:5]
        
        for risk_id, risk_data in sorted_risks:
            level_emoji = "🔴" if risk_data['level'] == "Alto" else "🟡" if risk_data['level'] == "Moderado" else "🟢"
            
            with st.expander(f"{level_emoji} {risk_id}. {risk_data['nome']} - {risk_data['score']}/100"):
                st.write(f"**Categoria:** {risk_data['categoria']}")
                st.write(f"**Arquivos afetados:** {len(risk_data['affected_files'])}")
                
                st.write("**💡 Recomendações:**")
                for i, rec in enumerate(risk_data['recommendations'], 1):
                    st.write(f"{i}. {rec}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Gerar Relatório", use_container_width=True):
            pdf_generator = get_pdf_generator()
            report_bytes = pdf_generator.generate_code_analysis_report(analysis_result)
            
            if PDF_AVAILABLE:
                file_name = f"AgentRisk_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                mime_type = "application/pdf"
            else:
                file_name = f"AgentRisk_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt"
                mime_type = "text/plain"
            
            st.download_button(
                label="⬇️ Download",
                data=report_bytes,
                file_name=file_name,
                mime=mime_type,
                use_container_width=True
            )
    
    with col2:
        if st.button("📊 Dashboard", use_container_width=True):
            st.session_state.show_dashboard = True 
            st.rerun()
    
    with col3:
        if st.button("🔄 Nova Análise", use_container_width=True):
            del st.session_state.analysis_result
            st.rerun()

def show_dashboard_page():
    """Dashboard com métricas da análise"""
    
    st.header("📊 Dashboard")
    
    if 'analysis_result' not in st.session_state:
        st.warning("⚠️ Nenhuma análise disponível.")
        return
    
    analysis = st.session_state.analysis_result
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Score Global", f"{analysis['global_score']}/100")
    
    with col2:
        high_risk_files = len([f for f in analysis['files_data'] if f['risk_level'] == 'Alto'])
        st.metric("Arquivos Alto Risco", high_risk_files)
    
    with col3:
        total_security_issues = sum(len(f['security_issues']) for f in analysis['files_data'])
        st.metric("Problemas Segurança", total_security_issues)
    
    with col4:
        st.metric("Total Linhas", f"{analysis['total_lines']:,}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Distribuição de Riscos")
        risk_levels = [f['risk_level'] for f in analysis['files_data']]
        risk_counts = {
            'Alto': risk_levels.count('Alto'),
            'Moderado': risk_levels.count('Moderado'), 
            'Baixo': risk_levels.count('Baixo')
        }
        st.bar_chart(risk_counts)
    
    with col2:
        st.subheader("🔧 Tipos de Arquivo")
        file_types = [f['file_type'] for f in analysis['files_data']]
        type_counts = {}
        for ftype in set(file_types):
            type_counts[ftype] = file_types.count(ftype)
        st.bar_chart(type_counts)
    
    st.subheader("🚨 Top 5 Arquivos Críticos")
    
    sorted_files = sorted(analysis['files_data'], key=lambda x: x['file_score'], reverse=True)[:5]
    
    for i, file_data in enumerate(sorted_files, 1):
        level_emoji = "🔴" if file_data['risk_level'] == "Alto" else "🟡" if file_data['risk_level'] == "Moderado" else "🟢"
        st.write(f"**#{i}** {level_emoji} {file_data['filename']} - {file_data['file_score']}/100")

def show_settings_page():
    """Página de configurações"""
    
    st.header("⚙️ Configurações")
    
    st.subheader("📊 Status")
    
    col1, col2 = st.columns(2)
    
    with col1:
        client = get_openai_client()
        if client:
            st.success("✅ OpenAI: Configurada")
        else:
            st.warning("⚠️ OpenAI: Não configurada")
    
    with col2:
        st.info(f"""
        **Funcionalidades:**
        
        ✅ Análise multi-arquivo
        {'✅' if PDF_AVAILABLE else '⚠️'} Geração PDF
        ✅ Detecção de riscos
        ✅ Análise cruzada
        """)
    
    st.subheader("📁 Tipos Suportados")
    st.write("**Código:** Python, JavaScript, Java, C#, PHP, Ruby, Go")
    st.write("**Config:** JSON, YAML, XML")
    st.write("**Outros:** SQL, Markdown, Text")
    
    if st.button("🗑️ Limpar Análise"):
        if 'analysis_result' in st.session_state:
            del st.session_state.analysis_result
            st.success("✅ Limpeza concluída!")
        else:
            st.info("ℹ️ Nada para limpar")

if __name__ == "__main__":
    main()code_analysis_page()
    elif page == "📊 Dashboard":
        show_dashboard_page()
    else:
        show_
