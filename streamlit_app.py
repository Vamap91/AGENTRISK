import streamlit as st
import json
import datetime
import base64
import io
import os
import re
from typing import Dict, List, Tuple, Any

# Importações condicionais
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    PDF_AVAILABLE = True
except ImportError:
    st.error("❌ ReportLab é obrigatório para gerar PDFs!")
    st.stop()

try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Configuração da página
st.set_page_config(
    page_title="AgentRisk - Análise de Código",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuração OpenAI
@st.cache_resource
def get_openai_client():
    """Inicializa cliente OpenAI"""
    if not OPENAI_AVAILABLE:
        return None
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        return None
    except Exception:
        return None

# CSS
st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
    padding: 2rem;
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
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
</style>
""", unsafe_allow_html=True)

# Definição dos 15 riscos
AGENTIC_AI_RISKS = {
    "1": {
        "nome": "Desalinhamento de Objetivos",
        "descricao": "Sistema pode buscar objetivos diferentes dos pretendidos",
        "categoria": "Governança",
        "patterns": ["todo", "fixme", "hack", "workaround", "temporary"]
    },
    "2": {
        "nome": "Ações Autônomas Indesejadas", 
        "descricao": "Execução de ações sem aprovação humana adequada",
        "categoria": "Autonomia",
        "patterns": ["auto", "automatic", "without_approval", "direct_action"]
    },
    "3": {
        "nome": "Uso Indevido de APIs",
        "descricao": "Utilização inadequada de APIs e serviços externos",
        "categoria": "Integração", 
        "patterns": ["requests.", "fetch(", "axios", "api_key", "http"]
    },
    "4": {
        "nome": "Decepção e Viés de Persona",
        "descricao": "Comportamentos enviesados baseados na persona do agente",
        "categoria": "Comportamento",
        "patterns": ["bias", "fake", "deceive", "manipulate", "persona"]
    },
    "5": {
        "nome": "Persistência de Memória Inadequada",
        "descricao": "Retenção inapropriada de informações sensíveis",
        "categoria": "Memória",
        "patterns": ["cache", "session", "memory", "persist", "store"]
    },
    "6": {
        "nome": "Transparência Limitada",
        "descricao": "Dificuldade em explicar decisões do sistema",
        "categoria": "Transparência",
        "patterns": ["black_box", "unexplained", "no_log", "silent"]
    },
    "7": {
        "nome": "Vulnerabilidades de Segurança",
        "descricao": "Exposição a ataques e falhas de segurança",
        "categoria": "Segurança",
        "patterns": ["eval", "exec", "unsafe", "hardcoded", "password"]
    },
    "8": {
        "nome": "Conformidade Regulatória",
        "descricao": "Não atendimento a regulamentações (LGPD, AI Act)",
        "categoria": "Compliance",
        "patterns": ["gdpr", "lgpd", "compliance", "regulation", "audit"]
    },
    "9": {
        "nome": "Escalabilidade e Performance",
        "descricao": "Limitações na capacidade de escalar adequadamente",
        "categoria": "Performance", 
        "patterns": ["bottleneck", "slow", "timeout", "performance"]
    },
    "10": {
        "nome": "Qualidade dos Dados",
        "descricao": "Problemas na qualidade e integridade dos dados",
        "categoria": "Dados",
        "patterns": ["validate", "sanitize", "clean", "quality"]
    },
    "11": {
        "nome": "Monitoramento e Auditoria",
        "descricao": "Ausência de monitoramento e trilhas de auditoria",
        "categoria": "Observabilidade",
        "patterns": ["log", "monitor", "audit", "track", "observe"]
    },
    "12": {
        "nome": "Gestão de Exceções",
        "descricao": "Tratamento inadequado de situações excepcionais",
        "categoria": "Robustez",
        "patterns": ["try", "except", "catch", "error", "fallback"]
    },
    "13": {
        "nome": "Dependências Externas",
        "descricao": "Riscos de dependência de serviços externos",
        "categoria": "Dependência",
        "patterns": ["import", "require", "dependency", "external"]
    },
    "14": {
        "nome": "Impacto nos Stakeholders",
        "descricao": "Efeitos não intencionais em usuários e funcionários",
        "categoria": "Social",
        "patterns": ["user", "customer", "employee", "stakeholder"]
    },
    "15": {
        "nome": "Evolução Descontrolada",
        "descricao": "Mudanças não supervisionadas via aprendizado contínuo",
        "categoria": "Evolução",
        "patterns": ["learning", "adapt", "evolve", "self_modify"]
    }
}

# Tipos de arquivo suportados
SUPPORTED_EXTENSIONS = [
    'py', 'js', 'ts', 'java', 'cs', 'php', 'rb', 'go', 'cpp', 'c',
    'json', 'yaml', 'yml', 'xml', 'sql', 'md', 'txt'
]

class CodeAnalyzer:
    """Analisador de código para detecção de riscos"""
    
    def __init__(self, openai_client=None):
        self.client = openai_client
        
    def analyze_files(self, uploaded_files) -> Dict:
        """Analisa múltiplos arquivos"""
        if not uploaded_files:
            return {"error": "Nenhum arquivo fornecido"}
            
        files_data = []
        total_lines = 0
        
        for uploaded_file in uploaded_files:
            try:
                content = self._read_file_content(uploaded_file)
                if content:
                    analysis = self._analyze_single_file(uploaded_file.name, content)
                    files_data.append(analysis)
                    total_lines += analysis.get('lines_count', 0)
            except Exception as e:
                st.warning(f"⚠️ Erro ao processar {uploaded_file.name}: {str(e)}")
                continue
                
        if not files_data:
            return {"error": "Nenhum arquivo válido"}
            
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
            "analysis_method": "Análise Multi-Arquivo"
        }
    
    def _read_file_content(self, uploaded_file) -> str:
        """Lê conteúdo do arquivo"""
        try:
            uploaded_file.seek(0)
            content = uploaded_file.read()
            
            # Tentar decodificar
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue
                    
            return str(content)
        except Exception as e:
            st.error(f"Erro ao ler {uploaded_file.name}: {str(e)}")
            return ""
    
    def _analyze_single_file(self, filename: str, content: str) -> Dict:
        """Analisa um arquivo"""
        file_ext = os.path.splitext(filename.lower())[1][1:]  # Remove o ponto
        
        lines = content.split('\n')
        lines_count = len(lines)
        char_count = len(content)
        
        classification = self._classify_file(filename, content)
        risk_patterns = self._detect_risk_patterns(content)
        security_issues = self._detect_security_issues(content)
        file_score = self._calculate_file_score(risk_patterns, security_issues, content)
        
        return {
            "filename": filename,
            "file_type": self._get_file_type(file_ext),
            "classification": classification,
            "lines_count": lines_count,
            "char_count": char_count,
            "file_score": file_score,
            "risk_level": self._get_risk_level(file_score),
            "risk_patterns": risk_patterns,
            "security_issues": security_issues,
            "content_preview": content[:500] + "..." if len(content) > 500 else content,
            "critical_lines": self._find_critical_lines(lines)
        }
    
    def _get_file_type(self, extension: str) -> str:
        """Retorna tipo do arquivo baseado na extensão"""
        type_map = {
            'py': 'Python', 'js': 'JavaScript', 'ts': 'TypeScript',
            'java': 'Java', 'cs': 'C#', 'php': 'PHP', 'rb': 'Ruby',
            'go': 'Go', 'cpp': 'C++', 'c': 'C', 'json': 'JSON',
            'yaml': 'YAML', 'yml': 'YAML', 'xml': 'XML',
            'sql': 'SQL', 'md': 'Markdown', 'txt': 'Text'
        }
        return type_map.get(extension, 'Unknown')
    
    def _classify_file(self, filename: str, content: str) -> str:
        """Classifica propósito do arquivo"""
        filename_lower = filename.lower()
        content_lower = content.lower()
        
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
    
    def _detect_risk_patterns(self, content: str) -> Dict:
        """Detecta padrões de risco"""
        content_lower = content.lower()
        detected_risks = {}
        
        for risk_id, risk_info in AGENTIC_AI_RISKS.items():
            risk_score = 0
            found_patterns = []
            
            for pattern in risk_info.get('patterns', []):
                if pattern in content_lower:
                    risk_score += 20
                    found_patterns.append(pattern)
            
            # Padrões críticos
            critical_patterns = {
                'eval(': 50, 'exec(': 50, 'password': 30, 
                'secret': 30, 'admin': 20, 'root': 25
            }
            
            for pattern, score_add in critical_patterns.items():
                if pattern in content_lower:
                    risk_score += score_add
                    found_patterns.append(pattern)
            
            detected_risks[risk_id] = {
                "score": min(100, max(0, risk_score)),
                "level": self._get_risk_level(risk_score),
                "patterns_found": found_patterns,
                "risk_name": risk_info["nome"]
            }
        
        return detected_risks
    
    def _detect_security_issues(self, content: str) -> List[Dict]:
        """Detecta problemas de segurança"""
        issues = []
        lines = content.split('\n')
        
        security_patterns = {
            'hardcoded_secrets': [
                r'password\s*=\s*["\'][^"\']+["\']',
                r'api_key\s*=\s*["\'][^"\']+["\']',
                r'secret\s*=\s*["\'][^"\']+["\']'
            ],
            'dangerous_functions': [
                r'eval\s*\(',
                r'exec\s*\(',
                r'system\s*\('
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
                            "severity": "HIGH" if issue_type == 'dangerous_functions' else "MEDIUM",
                            "description": self._get_security_description(issue_type)
                        })
        
        return issues
    
    def _get_security_description(self, issue_type: str) -> str:
        """Descrição do problema de segurança"""
        descriptions = {
            'hardcoded_secrets': 'Credenciais hardcoded no código',
            'dangerous_functions': 'Uso de funções perigosas (eval, exec)'
        }
        return descriptions.get(issue_type, 'Problema de segurança')
    
    def _calculate_file_score(self, risk_patterns: Dict, security_issues: List, content: str) -> float:
        """Calcula score de risco do arquivo"""
        base_score = 20
        patterns_score = sum(r['score'] for r in risk_patterns.values()) / len(risk_patterns)
        
        security_score = 0
        for issue in security_issues:
            security_score += 30 if issue['severity'] == 'HIGH' else 15
        
        # Fatores que reduzem risco
        good_practices = ['try:', 'except:', 'logging', 'validate', 'sanitize']
        reduction = sum(5 for practice in good_practices if practice in content.lower())
        
        final_score = base_score + (patterns_score * 0.6) + security_score - reduction
        return max(0, min(100, final_score))
    
    def _get_risk_level(self, score: float) -> str:
        """Converte score em nível"""
        if score >= 70:
            return "Alto"
        elif score >= 40:
            return "Moderado"
        else:
            return "Baixo"
    
    def _find_critical_lines(self, lines: List[str]) -> List[Dict]:
        """Encontra linhas críticas"""
        critical_lines = []
        keywords = ['password', 'secret', 'token', 'eval', 'exec', 'admin']
        
        for line_num, line in enumerate(lines, 1):
            if any(keyword in line.lower() for keyword in keywords):
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
        
        # Verificar credenciais em configs
        for config_file in config_files:
            if any(issue['type'] == 'hardcoded_secrets' for issue in config_file['security_issues']):
                cross_risks.append({
                    "type": "credentials_exposure",
                    "description": f"Credenciais em {config_file['filename']} afetam sistema",
                    "severity": "HIGH",
                    "affected_files": [f['filename'] for f in files_data if f != config_file]
                })
        
        # APIs sem autenticação
        if api_files and not auth_files:
            cross_risks.append({
                "type": "api_without_auth",
                "description": "APIs sem sistema de autenticação",
                "severity": "HIGH",
                "affected_files": [f['filename'] for f in api_files]
            })
        
        return {
            "risks_found": len(cross_risks),
            "cross_risks": cross_risks,
            "system_architecture": self._analyze_architecture(files_data)
        }
    
    def _analyze_architecture(self, files_data: List[Dict]) -> Dict:
        """Analisa arquitetura do sistema"""
        arch = {
            "entry_points": len([f for f in files_data if f['classification'] == 'entry_point']),
            "api_layers": len([f for f in files_data if f['classification'] == 'api_layer']),
            "data_models": len([f for f in files_data if f['classification'] == 'data_model']),
            "security_files": len([f for f in files_data if f['classification'] == 'security']),
            "config_files": len([f for f in files_data if f['classification'] == 'configuration']),
            "test_files": len([f for f in files_data if f['classification'] == 'testing'])
        }
        
        completeness = 0
        if arch["entry_points"] > 0: completeness += 20
        if arch["api_layers"] > 0: completeness += 15
        if arch["security_files"] > 0: completeness += 25
        if arch["test_files"] > 0: completeness += 20
        if arch["config_files"] > 0: completeness += 10
        if arch["data_models"] > 0: completeness += 10
        
        arch["completeness_score"] = completeness
        return arch
    
    def _calculate_global_score(self, files_data: List[Dict], cross_analysis: Dict) -> float:
        """Calcula score global"""
        if not files_data:
            return 0
        
        avg_score = sum(f['file_score'] for f in files_data) / len(files_data)
        cross_penalty = len(cross_analysis.get('cross_risks', [])) * 15
        
        arch_bonus = 0
        if cross_analysis.get('system_architecture', {}).get('completeness_score', 0) > 80:
            arch_bonus = 10
        
        return max(0, min(100, avg_score + cross_penalty - arch_bonus))
    
    def _generate_risks_summary(self, files_data: List[Dict]) -> Dict:
        """Gera resumo dos riscos"""
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
        """Recomendações por risco"""
        recommendations = {
            "1": ["Definir objetivos claros", "Implementar validação de metas"],
            "2": ["Adicionar aprovação humana", "Implementar thresholds"],
            "3": ["Rate limiting em APIs", "Usar variáveis de ambiente"],
            "7": ["Remover eval/exec", "Implementar validação de entrada"]
        }
        return recommendations.get(risk_id, ["Implementar melhores práticas"])

class PDFReportGenerator:
    """Gerador de relatórios PDF usando ReportLab"""
    
    def generate_report(self, analysis_result: Dict) -> bytes:
        """Gera relatório PDF completo"""
        buffer = io.BytesIO()
        
        # Criar documento
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Título
        title = Paragraph("AgentRisk - Relatório de Análise de Código", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Informações gerais
        info_data = [
            ['Arquivos Analisados:', str(analysis_result['files_analyzed'])],
            ['Total de Linhas:', f"{analysis_result['total_lines']:,}"],
            ['Score Global:', f"{analysis_result['global_score']}/100"],
            ['Nível de Risco:', analysis_result['global_level']],
            ['Data da Análise:', datetime.datetime.now().strftime('%d/%m/%Y %H:%M')]
        ]
        
        info_table = Table(info_data, colWidths=[150, 200])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 0), (-1, -1), HexColor('#000000')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 30))
        
        # Score global destacado
        score_color = '#dc2626' if analysis_result['global_score'] >= 70 else '#f59e0b' if analysis_result['global_score'] >= 40 else '#10b981'
        score_text = f"<font color='{score_color}' size='16'><b>SCORE GLOBAL: {analysis_result['global_score']}/100</b></font>"
        score_para = Paragraph(score_text, styles['Normal'])
        story.append(score_para)
        story.append(Spacer(1, 20))
        
        # Análise por arquivo
        story.append(Paragraph("ANÁLISE DETALHADA POR ARQUIVO", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        for i, file_data in enumerate(analysis_result['files_data'], 1):
            file_text = f"<b>{i}. {file_data['filename']}</b><br/>"
            file_text += f"Score: {file_data['file_score']}/100 | "
            file_text += f"Tipo: {file_data['file_type']} | "
            file_text += f"Linhas: {file_data['lines_count']:,}<br/>"
            file_text += f"Classificação: {file_data['classification']} | "
            file_text += f"Nível: {file_data['risk_level']}"
            
            if file_data['security_issues']:
                file_text += f"<br/><font color='red'>Problemas de Segurança: {len(file_data['security_issues'])}</font>"
            
            file_para = Paragraph(file_text, styles['Normal'])
            story.append(file_para)
            story.append(Spacer(1, 10))
        
        # Top riscos
        if 'risks_summary' in analysis_result and analysis_result['risks_summary']:
            story.append(Spacer(1, 20))
            story.append(Paragraph("TOP 5 RISCOS DETECTADOS", styles['Heading2']))
            story.append(Spacer(1, 10))
            
            sorted_risks = sorted(
                analysis_result['risks_summary'].items(),
                key=lambda x: x[1]['score'],
                reverse=True
            )[:5]
            
            for i, (risk_id, risk_data) in enumerate(sorted_risks, 1):
                color = '#dc2626' if risk_data['level'] == 'Alto' else '#f59e0b' if risk_data['level'] == 'Moderado' else '#10b981'
                risk_text = f"<font color='{color}'><b>{i}. {risk_data['nome']}</b></font><br/>"
                risk_text += f"Score: {risk_data['score']}/100 | Nível: {risk_data['level']}<br/>"
                risk_text += f"Categoria: {risk_data['categoria']}<br/>"
                risk_text += f"Arquivos Afetados: {len(risk_data['affected_files'])}"
                
                if risk_data['recommendations']:
                    risk_text += f"<br/>Recomendação: {risk_data['recommendations'][0]}"
                
                risk_para = Paragraph(risk_text, styles['Normal'])
                story.append(risk_para)
                story.append(Spacer(1, 15))
        
        # Rodapé
        story.append(Spacer(1, 30))
        footer_text = "Relatório gerado automaticamente pelo AgentRisk<br/>"
        footer_text += "Baseado no documento 'Agentic AI in Financial Services - IBM Consulting (Maio/2025)'"
        footer_para = Paragraph(footer_text, styles['Normal'])
        story.append(footer_para)
        
        # Gerar PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

# Inicialização
@st.cache_resource
def get_analyzer():
    return CodeAnalyzer(get_openai_client())

@st.cache_resource
def get_pdf_generator():
    return PDFReportGenerator()

def main():
    """Função principal"""
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🛡️ AgentRisk</h1>
        <p>Análise de Código para Avaliação de Riscos em IA Autônoma</p>
        <small>Streamlit Cloud | Análise Multi-Arquivo</small>
    </div>
    """, unsafe_allow_html=True)
    
    # Status
    col1, col2, col3 = st.columns(3)
    with col1:
        client = get_openai_client()
        if client:
            st.success("✅ OpenAI: Ativo")
        else:
            st.info("ℹ️ OpenAI: Análise Local")
    
    with col2:
        if PDF_AVAILABLE:
            st.success("✅ PDF: ReportLab Ativo")
        else:
            st.error("❌ PDF: ReportLab Necessário")
    
    with col3:
        st.success("✅ Análise: 15 Riscos")
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Menu")
        page = st.selectbox("Escolha:", ["🔍 Análise", "📊 Dashboard", "⚙️ Config"])
        
        if 'analysis_result' in st.session_state:
            result = st.session_state.analysis_result
            st.markdown("---")
            st.markdown("**📊 Última Análise**")
            st.info(f"""
            📁 Arquivos: {result.get('files_analyzed', 0)}
            📝 Linhas: {result.get('total_lines', 0):,}
            🎯 Score: {result.get('global_score', 0)}/100
            """)
    
    # Páginas
    if page == "🔍 Análise":
        show_analysis_page()
    elif page == "📊 Dashboard":
        show_dashboard_page()
    else:
        show_config_page()

def show_analysis_page():
    """Página de análise de código"""
    
    st.header("🔍 Análise de Código Multi-Arquivo")
    
    # Se já tem análise, mostrar resultados
    if 'analysis_result' in st.session_state:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 Nova Análise", type="secondary"):
                del st.session_state.analysis_result
                st.rerun()
        with col2:
            st.write("**Análise concluída - veja os resultados abaixo**")
        
        show_analysis_results(st.session_state.analysis_result)
        return
    
    # Interface de upload
    st.markdown("### 📤 Upload dos Arquivos do Sistema")
    st.write("Faça upload dos arquivos de código do seu sistema para análise de riscos.")
    
    uploaded_files = st.file_uploader(
        "Selecione os arquivos",
        accept_multiple_files=True,
        type=SUPPORTED_EXTENSIONS,
        help="Arquivos de código, configuração e documentação suportados"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} arquivo(s) carregado(s)")
        
        # Preview dos arquivos
        with st.expander("📋 Arquivos Carregados", expanded=True):
            for file in uploaded_files:
                file_ext = os.path.splitext(file.name.lower())[1][1:]
                file_type = CodeAnalyzer(None)._get_file_type(file_ext)
                st.write(f"📄 **{file.name}** - {file_type} ({file.size:,} bytes)")
        
        # Botão de análise
        if st.button("🔍 Analisar Sistema Completo", type="primary", use_container_width=True):
            with st.spinner("🔄 Analisando arquivos do sistema..."):
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i in range(101):
                    progress_bar.progress(i)
                    if i < 30:
                        status_text.text("📖 Lendo arquivos...")
                    elif i < 60:
                        status_text.text("🔍 Detectando padrões de risco...")
                    elif i < 90:
                        status_text.text("🔗 Análise cruzada...")
                    else:
                        status_text.text("📊 Finalizando...")
                
                # Análise real
                analyzer = get_analyzer()
                analysis_result = analyzer.analyze_files(uploaded_files)
                
                if 'error' in analysis_result:
                    st.error(f"❌ {analysis_result['error']}")
                    return
                
                # Salvar resultado
                st.session_state.analysis_result = analysis_result
                
                status_text.text("✅ Análise concluída!")
                st.success("🎉 Análise de código concluída com sucesso!")
                st.balloons()
                st.rerun()
    
    else:
        # Instruções
        st.info("""
        ### 💡 Como Usar
        
        1. **📁 Selecione os arquivos** principais do seu sistema
        2. **🔍 Clique em "Analisar"** para processar todos os arquivos  
        3. **📊 Visualize os resultados** detalhados por arquivo
        4. **📄 Gere relatório PDF** profissional
        
        ### 📋 Tipos Suportados
        - **Código:** Python, JavaScript, Java, C#, PHP, Ruby, Go, C/C++
        - **Config:** JSON, YAML, XML
        - **Outros:** SQL, Markdown, Text
        
        ### 🎯 Análise Inclui
        - ✅ **15 categorias de risco** específicas para IA Autônoma
        - ✅ **Detecção de vulnerabilidades** de segurança
        - ✅ **Análise cruzada** entre arquivos  
        - ✅ **Score global** do sistema
        """)

def show_analysis_results(analysis_result: Dict):
    """Mostra resultados da análise"""
    
    st.header("📊 Resultados da Análise")
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📁 Arquivos", analysis_result['files_analyzed'])
    with col2:
        st.metric("📝 Total Linhas", f"{analysis_result['total_lines']:,}")
    with col3:
        st.metric("🎯 Score Global", f"{analysis_result['global_score']}/100")
    with col4:
        st.metric("⏰ Método", "Multi-Arquivo")
    
    # Score visual
    global_score = analysis_result['global_score']
    global_level = analysis_result['global_level']
    
    score_class = "score-low" if global_score < 40 else "score-medium" if global_score < 70 else "score-high"
    emoji = "🟢" if global_score < 40 else "🟡" if global_score < 70 else "🔴"
    
    st.markdown(f"""
    <div class="score-container {score_class}">
        <h2>{emoji} Score Global do Sistema</h2>
        <h1>{global_score}/100</h1>
        <h3>Nível de Risco: {global_level}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Distribuição de riscos
    col1, col2, col3 = st.columns(3)
    
    high_count = sum(1 for f in analysis_result['files_data'] if f['risk_level'] == 'Alto')
    medium_count = sum(1 for f in analysis_result['files_data'] if f['risk_level'] == 'Moderado')
    low_count = sum(1 for f in analysis_result['files_data'] if f['risk_level'] == 'Baixo')
    
    with col1:
        st.metric("🔴 Riscos Altos", high_count)
    with col2:
        st.metric("🟡 Riscos Moderados", medium_count)
    with col3:
        st.metric("🟢 Riscos Baixos", low_count)
    
    # Análise por arquivo
    st.subheader("📁 Análise Detalhada por Arquivo")
    
    for file_data in analysis_result['files_data']:
        risk_class = f"risk-{file_data['risk_level'].lower()}"
        level_emoji = "🟢" if file_data['risk_level'] == "Baixo" else "🟡" if file_data['risk_level'] == "Moderado" else "🔴"
        
        st.markdown(f"""
        <div class="risk-card {risk_class}">
            <h4>{level_emoji} 📄 {file_data['filename']}</h4>
            <p><strong>Score:</strong> {file_data['file_score']}/100 | 
               <strong>Tipo:</strong> {file_data['file_type']} | 
               <strong>Linhas:</strong> {file_data['lines_count']:,}</p>
            <p><strong>Classificação:</strong> {file_data['classification']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Detalhes expandíveis
        with st.expander(f"🔍 Detalhes - {file_data['filename']}"):
            tab1, tab2, tab3 = st.tabs(["📊 Resumo", "⚠️ Problemas", "🔍 Preview"])
            
            with tab1:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Score", f"{file_data['file_score']}/100")
                    st.write(f"**Tipo:** {file_data['file_type']}")
                with col2:
                    st.metric("Linhas", f"{file_data['lines_count']:,}")
                    st.write(f"**Classificação:** {file_data['classification']}")
            
            with tab2:
                if file_data['security_issues']:
                    st.write("**🚨 Problemas de Segurança:**")
                    for issue in file_data['security_issues']:
                        severity_color = "🔴" if issue['severity'] == 'HIGH' else "🟡"
                        st.write(f"{severity_color} **Linha {issue['line']}:** {issue['description']}")
                        with st.expander(f"Ver código - Linha {issue['line']}"):
                            st.code(issue['content'])
                else:
                    st.success("✅ Nenhum problema crítico detectado")
                
                if file_data['critical_lines']:
                    st.write("**⚠️ Linhas Críticas:**")
                    for critical in file_data['critical_lines']:
                        st.write(f"**Linha {critical['line_number']}:** {critical['reason']}")
            
            with tab3:
                if file_data['content_preview']:
                    st.write("**📄 Preview do Código:**")
                    st.code(file_data['content_preview'])
    
    # Análise cruzada
    if 'cross_analysis' in analysis_result and analysis_result['cross_analysis']['risks_found'] > 0:
        st.subheader("🔗 Análise Cruzada Entre Arquivos")
        
        for cross_risk in analysis_result['cross_analysis']['cross_risks']:
            severity_color = "🔴" if cross_risk['severity'] == 'HIGH' else "🟡"
            st.warning(f"{severity_color} **{cross_risk['description']}**")
            st.write(f"**Arquivos afetados:** {', '.join(cross_risk['affected_files'])}")
    
    # Top riscos
    if 'risks_summary' in analysis_result and analysis_result['risks_summary']:
        st.subheader("📋 Top Riscos de IA Autônoma Detectados")
        
        sorted_risks = sorted(
            analysis_result['risks_summary'].items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )[:5]
        
        for risk_id, risk_data in sorted_risks:
            level_emoji = "🔴" if risk_data['level'] == "Alto" else "🟡" if risk_data['level'] == "Moderado" else "🟢"
            
            with st.expander(f"{level_emoji} {risk_id}. {risk_data['nome']} - {risk_data['score']}/100"):
                st.write(f"**Categoria:** {risk_data['categoria']}")
                st.write(f"**Nível:** {risk_data['level']}")
                st.write(f"**Arquivos afetados:** {len(risk_data['affected_files'])}")
                
                if risk_data['affected_files']:
                    st.write("**📁 Arquivos com este risco:**")
                    for filename in risk_data['affected_files']:
                        st.write(f"• {filename}")
                
                st.write("**💡 Recomendações:**")
                for i, rec in enumerate(risk_data['recommendations'], 1):
                    st.write(f"{i}. {rec}")
    
    # Botões de ação
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Gerar Relatório PDF", use_container_width=True):
            with st.spinner("Gerando relatório PDF..."):
                pdf_generator = get_pdf_generator()
                pdf_bytes = pdf_generator.generate_report(analysis_result)
                
                file_name = f"AgentRisk_Report_{analysis_result['files_analyzed']}files_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=file_name,
                    mime="application/pdf",
                    use_container_width=True
                )
    
    with col2:
        if st.button("📊 Ver Dashboard", use_container_width=True):
            st.session_state.show_dashboard = True
            st.rerun()
    
    with col3:
        if st.button("🔄 Nova Análise", use_container_width=True):
            del st.session_state.analysis_result
            st.rerun()

def show_dashboard_page():
    """Dashboard com gráficos"""
    
    st.header("📊 Dashboard de Análise")
    
    if 'analysis_result' not in st.session_state:
        st.warning("⚠️ Nenhuma análise disponível. Faça uma análise primeiro.")
        if st.button("🔙 Voltar para Análise"):
            st.rerun()
        return
    
    analysis = st.session_state.analysis_result
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Score Global", f"{analysis['global_score']}/100")
    with col2:
        high_files = len([f for f in analysis['files_data'] if f['risk_level'] == 'Alto'])
        st.metric("Arquivos Alto Risco", high_files)
    with col3:
        total_issues = sum(len(f['security_issues']) for f in analysis['files_data'])
        st.metric("Problemas Segurança", total_issues)
    with col4:
        st.metric("Total Linhas", f"{analysis['total_lines']:,}")
    
    # Gráficos
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
    
    # Top arquivos críticos
    st.subheader("🚨 Top 5 Arquivos Mais Críticos")
    
    sorted_files = sorted(analysis['files_data'], key=lambda x: x['file_score'], reverse=True)[:5]
    
    for i, file_data in enumerate(sorted_files, 1):
        level_emoji = "🔴" if file_data['risk_level'] == "Alto" else "🟡" if file_data['risk_level'] == "Moderado" else "🟢"
        st.write(f"**#{i}** {level_emoji} **{file_data['filename']}** - {file_data['file_score']}/100 ({file_data['file_type']})")
    
    # Arquitetura do sistema
    if 'cross_analysis' in analysis and 'system_architecture' in analysis['cross_analysis']:
        st.subheader("🏗️ Arquitetura do Sistema")
        
        arch = analysis['cross_analysis']['system_architecture']
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Pontos de Entrada", arch['entry_points'])
            st.metric("APIs", arch['api_layers'])
        
        with col2:
            st.metric("Modelos de Dados", arch['data_models'])
            st.metric("Segurança", arch['security_files'])
        
        with col3:
            st.metric("Configurações", arch['config_files'])
            st.metric("Testes", arch['test_files'])
        
        completeness = arch.get('completeness_score', 0)
        st.progress(completeness / 100)
        st.write(f"**Completude da Arquitetura:** {completeness}/100")

def show_config_page():
    """Página de configurações"""
    
    st.header("⚙️ Configurações do AgentRisk")
    
    # Status do sistema
    st.subheader("📊 Status do Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        client = get_openai_client()
        if client:
            st.success("✅ OpenAI: Configurada")
            if st.button("🧪 Testar OpenAI"):
                try:
                    with st.spinner("Testando..."):
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": "Teste"}],
                            max_tokens=5
                        )
                        st.success("✅ Teste bem-sucedido!")
                except Exception as e:
                    st.error(f"❌ Erro: {str(e)}")
        else:
            st.warning("⚠️ OpenAI: Não configurada")
            st.info("Configure OPENAI_API_KEY nos Secrets do Streamlit")
    
    with col2:
        st.info(f"""
        **Funcionalidades Ativas:**
        
        ✅ Análise multi-arquivo
        {'✅' if PDF_AVAILABLE else '❌'} Geração PDF (ReportLab)
        {'✅' if client else '⚠️'} Análise com IA
        ✅ Detecção 15 riscos IA
        ✅ Análise cruzada arquivos
        ✅ Vulnerabilidades segurança
        """)
    
    # Informações do sistema
    st.subheader("📋 Informações")
    
    st.info(f"""
    **AgentRisk v1.0**
    
    **Tipos de Arquivo:** {len(SUPPORTED_EXTENSIONS)} suportados
    **Riscos Analisados:** 15 categorias específicas de IA Autônoma
    **Baseado em:** IBM Consulting - Agentic AI in Financial Services (Maio/2025)
    **Deploy:** Streamlit Cloud
    **Última Atualização:** {datetime.datetime.now().strftime('%d/%m/%Y')}
    """)
    
    # Limpeza
    st.subheader("🗑️ Gerenciamento")
    
    if st.button("🗑️ Limpar Análise Atual"):
        if 'analysis_result' in st.session_state:
            del st.session_state.analysis_result
            st.success("✅ Análise limpa!")
            st.rerun()
        else:
            st.info("ℹ️ Nenhuma análise para limpar")

if __name__ == "__main__":
    main()
