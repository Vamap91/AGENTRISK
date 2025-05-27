import streamlit as st
import json
import datetime
import base64
import io
import os
import re
import asyncio
import hashlib
import threading
import time
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from enum import Enum

# Third-party imports (if available)
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    PDF_AVAILABLE = True
except ImportError:
    st.error("❌ ReportLab is required for PDF functionality!")
    st.stop()

try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    st.error("❌ OpenAI is REQUIRED for enterprise analysis!")
    st.stop()


# Streamlit Page Configuration
st.set_page_config(
    page_title="AgentRisk Pro - Enterprise Analysis",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Classes for Enterprise Structure
class RiskLevel(Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Moderate"
    LOW = "Low"
    MINIMAL = "Minimal"

class ComplianceFramework(Enum):
    EU_AI_ACT = "EU AI Act"
    LGPD_BRAZIL = "LGPD Brazil"
    GDPR_EU = "GDPR Europe"
    SOX_US = "SOX United States"
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

# OpenAI Configuration (REQUIRED)
@st.cache_resource
def get_openai_client():
    """Initializes OpenAI client - REQUIRED"""
    if not OPENAI_AVAILABLE:
        st.error("❌ OpenAI is required for enterprise analysis!")
        st.stop()

    try:
        # First try Streamlit secrets
        if "OPENAI_API_KEY" in st.secrets:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        # Then try environment variable
        elif "OPENAI_API_KEY" in os.environ:
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        else:
            st.error("❌ Configure OPENAI_API_KEY in Streamlit Secrets or as an environment variable!")
            st.info("Go to Settings > Secrets and add: OPENAI_API_KEY = 'your-key-here'")
            st.stop()

        # Mandatory API test
        # Note: This test might not be robust enough for all scenarios
        # A more thorough test might be needed if issues persist.
        try:
            test_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            if not test_response.choices:
                raise Exception("OpenAI API test failed: No response choices.")
        except Exception as e:
            st.error(f"❌ OpenAI API test failed: {str(e)}. Please check your API key and network connection.")
            st.stop()

        return client

    except Exception as e:
        st.error(f"❌ OpenAI configuration error: {str(e)}")
        st.stop()

# Enterprise CSS
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

# Detailed Enterprise Risks (based on IBM report)
ENTERPRISE_AGENTIC_RISKS = {
    "AGR001": {
        "name": "Critical Objective Misalignment",
        "category": "Strategic Governance",
        "description": "Agents may pursue objectives that conflict with organizational goals",
        "compliance_frameworks": [ComplianceFramework.EU_AI_ACT, ComplianceFramework.SOX_US],
        "ai_analysis_required": True,
        "technical_patterns": ["goal", "objective", "target", "kpi", "metric"],
        "severity_indicators": ["hardcoded_goals", "no_validation", "conflicting_objectives"]
    },
    "AGR002": {
        "name": "Unsupervised Autonomous Actions",
        "category": "Operational Control",
        "description": "Execution of critical actions without human approval or supervision",
        "compliance_frameworks": [ComplianceFramework.EU_AI_ACT, ComplianceFramework.BASEL_III],
        "ai_analysis_required": True,
        "technical_patterns": ["autonomous", "auto_execute", "no_human_approval", "direct_action"],
        "severity_indicators": ["financial_transactions", "data_deletion", "system_changes"]
    },
    "AGR003": {
        "name": "Inadequate Use of Critical APIs",
        "category": "Integration Security",
        "description": "Insecure use of financial APIs and critical services",
        "compliance_frameworks": [ComplianceFramework.PCI_DSS, ComplianceFramework.LGPD_BRAZIL],
        "ai_analysis_required": True,
        "technical_patterns": ["api_call", "external_service", "http_request", "webhook"],
        "severity_indicators": ["payment_api", "user_data_api", "admin_endpoints"]
    },
    "AGR004": {
        "name": "Algorithmic Bias and Discrimination",
        "category": "Ethics and Fairness",
        "description": "Discriminatory behaviors based on bias in data or algorithms",
        "compliance_frameworks": [ComplianceFramework.EU_AI_ACT, ComplianceFramework.LGPD_BRAZIL],
        "ai_analysis_required": True,
        "technical_patterns": ["bias", "discrimination", "unfair", "stereotype"],
        "severity_indicators": ["demographic_filtering", "exclusion_rules", "prejudicial_logic"]
    },
    "AGR005": {
        "name": "Inadequate Sensitive Data Retention",
        "category": "Privacy and Data Protection",
        "description": "Inappropriate persistence of personal and financial information",
        "compliance_frameworks": [ComplianceFramework.LGPD_BRAZIL, ComplianceFramework.GDPR_EU],
        "ai_analysis_required": True,
        "technical_patterns": ["persist", "cache", "store", "memory", "retention"],
        "severity_indicators": ["personal_data", "financial_info", "no_encryption", "long_retention"]
    },
    "AGR006": {
        "name": "Lack of Explainability (Black Box)",
        "category": "Transparency and Audit",
        "description": "Inability to explain system decisions and processes",
        "compliance_frameworks": [ComplianceFramework.EU_AI_ACT, ComplianceFramework.SOX_US],
        "ai_analysis_required": True,
        "technical_patterns": ["unexplained", "black_box", "no_logging", "opaque"],
        "severity_indicators": ["financial_decisions", "no_audit_trail", "complex_ml"]
    },
    "AGR007": {
        "name": "Critical Security Vulnerabilities",
        "category": "Cybersecurity",
        "description": "Exposure to attacks, injections, and security flaws",
        "compliance_frameworks": [ComplianceFramework.PCI_DSS, ComplianceFramework.SOX_US],
        "ai_analysis_required": True,
        "technical_patterns": ["eval", "exec", "sql_injection", "xss", "csrf"],
        "severity_indicators": ["user_input", "database_access", "admin_functions"]
    },
    "AGR008": {
        "name": "Regulatory Non-Compliance",
        "category": "Legal Compliance",
        "description": "Violation of specific financial industry regulations",
        "compliance_frameworks": [ComplianceFramework.EU_AI_ACT, ComplianceFramework.LGPD_BRAZIL, ComplianceFramework.BASEL_III],
        "ai_analysis_required": True,
        "technical_patterns": ["compliance", "regulation", "audit", "legal"],
        "severity_indicators": ["no_consent", "data_breach", "reporting_failure"]
    },
    "AGR009": {
        "name": "Critical Scalability Limitations",
        "category": "Operational Performance",
        "description": "Failure to scale under high demand",
        "compliance_frameworks": [ComplianceFramework.SOX_US, ComplianceFramework.BASEL_III],
        "ai_analysis_required": True,
        "technical_patterns": ["bottleneck", "timeout", "memory_leak", "performance"],
        "severity_indicators": ["single_point_failure", "no_load_balancing", "resource_exhaustion"]
    },
    "AGR010": {
        "name": "Data Quality and Integrity",
        "category": "Data Governance",
        "description": "Problems with data quality, validation, and integrity",
        "compliance_frameworks": [ComplianceFramework.SOX_US, ComplianceFramework.BASEL_III],
        "ai_analysis_required": True,
        "technical_patterns": ["validation", "sanitization", "data_quality", "integrity"],
        "severity_indicators": ["no_validation", "corrupted_data", "inconsistent_sources"]
    }
}

# Detailed Compliance Frameworks
COMPLIANCE_REQUIREMENTS = {
    ComplianceFramework.EU_AI_ACT: {
        "name": "EU AI Act",
        "description": "European regulation for AI systems",
        "articles": {
            "Art. 6": "High-risk AI systems",
            "Art. 8": "Conformity of high-risk AI systems",
            "Art. 9": "Risk management system",
            "Art. 10": "Data and data governance",
            "Art. 11": "Technical documentation",
            "Art. 12": "Record-keeping",
            "Art. 13": "Transparency and provision of information",
            "Art. 14": "Human oversight",
            "Art. 15": "Accuracy, robustness and cybersecurity"
        },
        "penalties": "Up to 7% of global annual turnover"
    },
    ComplianceFramework.LGPD_BRAZIL: {
        "name": "LGPD Brazil",
        "description": "Brazilian General Data Protection Law",
        "articles": {
            "Art. 5": "Definitions of personal data",
            "Art. 6": "Data processing activities",
            "Art. 7": "Legal bases for processing",
            "Art. 8": "Consent",
            "Art. 9": "Sensitive data",
            "Art. 18": "Data subject rights",
            "Art. 46": "Processing agents",
            "Art. 48": "Security incident communication"
        },
        "penalties": "Up to R$ 50 million per infraction"
    },
    ComplianceFramework.GDPR_EU: {
        "name": "GDPR Europe",
        "description": "General Data Protection Regulation of Europe",
        "articles": {
            "Art. 6": "Lawfulness of processing",
            "Art. 7": "Conditions for consent",
            "Art. 25": "Data protection by design and by default",
            "Art. 32": "Security of processing",
            "Art. 35": "Data protection impact assessment"
        },
        "penalties": "Up to 4% of global annual turnover (€20M maximum)"
    },
    ComplianceFramework.SOX_US: {
        "name": "SOX United States",
        "description": "Sarbanes-Oxley Act of 2002",
        "articles": {
            "Sec. 302": "Corporate responsibility for financial reports",
            "Sec. 404": "Management assessment of internal controls",
            "Sec. 409": "Real-time issuer disclosures",
            "Sec. 906": "Criminal penalties for altering documents"
        },
        "penalties": "Fines up to $5M + imprisonment"
    },
    ComplianceFramework.BASEL_III: {
        "name": "Basel III",
        "description": "International regulatory framework for banks",
        "articles": {
            "Pillar 1": "Minimum capital requirements",
            "Pillar 2": "Supervisory review process",
            "Pillar 3": "Market discipline",
            "Operational risk management": "Operational risk management principles"
        },
        "penalties": "Regulatory sanctions + license revocation"
    },
    ComplianceFramework.PCI_DSS: {
        "name": "PCI DSS",
        "description": "Payment Card Industry Data Security Standard",
        "articles": {
            "Req. 1": "Install and maintain a firewall configuration to protect cardholder data",
            "Req. 2": "Do not use vendor-supplied defaults for system passwords and other security parameters",
            "Req. 3": "Protect stored cardholder data",
            "Req. 4": "Encrypt transmission of cardholder data across open, public networks",
            "Req. 6": "Develop and maintain secure systems and applications",
            "Req. 8": "Identify and authenticate access to system components"
        },
        "penalties": "Fines of $50K-$500K per month"
    }
}

class EnterpriseCodeAnalyzer:
    """Enterprise Analyzer with Mandatory AI"""

    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
        self.analysis_cache = {}

    async def analyze_system_enterprise(self, uploaded_files) -> Dict:
        """Complete Enterprise Analysis"""
        if not uploaded_files:
            return {"error": "No files provided"}

        # Phase 1: Basic file analysis
        files_data = []
        total_lines = 0

        progress_placeholder = st.empty()

        for i, uploaded_file in enumerate(uploaded_files):
            progress_placeholder.text(f"📖 Analyzing {uploaded_file.name}... ({i+1}/{len(uploaded_files)})")

            try:
                content = self._read_file_content(uploaded_file)
                if content:
                    file_analysis = await self._analyze_single_file_enterprise(uploaded_file.name, content)
                    files_data.append(file_analysis)
                    total_lines += file_analysis.get('lines_count', 0)
            except Exception as e:
                st.warning(f"⚠️ Error processing {uploaded_file.name}: {str(e)}")
                continue

        if not files_data:
            return {"error": "No valid files for analysis"}

        # Phase 2: Complete System Analysis with AI
        progress_placeholder.text("🤖 Performing semantic analysis with AI...")
        system_analysis = await self._ai_system_analysis(files_data)

        # Phase 3: Compliance Analysis
        progress_placeholder.text("⚖️ Verifying regulatory compliance...")
        compliance_analysis = await self._compliance_analysis(files_data, system_analysis)

        # Phase 4: Enterprise Cross-Analysis
        progress_placeholder.text("🔗 Cross-analysis and architectural analysis...")
        cross_analysis = await self._enterprise_cross_analysis(files_data, system_analysis)

        # Phase 5: Final Enterprise Score
        progress_placeholder.text("📊 Calculating enterprise score...")
        enterprise_score = self._calculate_enterprise_score(files_data, system_analysis, compliance_analysis, cross_analysis)

        progress_placeholder.text("✅ Enterprise analysis completed!")

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
        """Reads file content with robust encoding"""
        try:
            uploaded_file.seek(0)
            content = uploaded_file.read()

            # Try multiple encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue

            # Fallback to binary analysis
            return str(content)
        except Exception as e:
            st.error(f"Critical error reading {uploaded_file.name}: {str(e)}")
            return ""

    async def _analyze_single_file_enterprise(self, filename: str, content: str) -> Dict:
        """Enterprise analysis of individual file with AI"""

        # Basic information
        lines = content.split('\n')
        lines_count = len(lines)
        char_count = len(content)
        file_ext = os.path.splitext(filename.lower())[1][1:]

        # Technical classification with AI
        classification = await self._ai_classify_file(filename, content)

        # Enterprise risk detection
        risk_assessments = await self._detect_enterprise_risks(content, filename)

        # Deep security analysis
        security_analysis = await self._deep_security_analysis(content, filename)

        # File score
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
        """Intelligent file classification with AI"""

        prompt = f"""
        Analyze this code file and classify its function in the system:

        Name: {filename}
        Content (first 500 chars): {content[:500]}

        Return a JSON with:
        - category: main type (security, api, data, config, ui, business_logic, testing, infrastructure)
        - purpose: specific function description
        - criticality: criticality level (critical, high, medium, low)
        - architectural_role: role in the architecture
        - security_relevance: relevance to security (0-10)

        Be specific and technical.
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
            # Fallback to basic classification
            return {
                "category": self._basic_classification(filename),
                "purpose": "Basic analysis - AI unavailable",
                "criticality": "medium",
                "architectural_role": "unknown",
                "security_relevance": 5,
                "error": str(e)
            }

    async def _detect_enterprise_risks(self, content: str, filename: str) -> List[RiskAssessment]:
        """Enterprise risk detection with AI analysis"""

        risk_assessments = []
        content_lower = content.lower()

        for risk_id, risk_info in ENTERPRISE_AGENTIC_RISKS.items():

            # Mandatory AI analysis
            ai_analysis = await self._ai_risk_analysis(content, filename, risk_info)

            # Technical pattern detection
            pattern_score = 0
            evidence = []

            for pattern in risk_info["technical_patterns"]:
                if pattern in content_lower:
                    pattern_score += 15
                    evidence.append(f"Pattern detected: {pattern}")

            # Severity indicators
            severity_score = 0
            for indicator in risk_info["severity_indicators"]:
                if indicator in content_lower:
                    severity_score += 25
                    evidence.append(f"Critical indicator: {indicator}")

            # Combined score (AI + Patterns)
            combined_score = (ai_analysis["score"] * 0.7) + (pattern_score * 0.2) + (severity_score * 0.1)
            combined_score = min(100, max(0, combined_score))

            # Compliance Impact
            compliance_impact = {}
            for framework in risk_info["compliance_frameworks"]:
                compliance_impact[framework] = await self._assess_compliance_impact(
                    framework, risk_info, ai_analysis
                )

            # Create assessment
            assessment = RiskAssessment(
                risk_id=risk_id,
                name=risk_info["name"],
                category=risk_info["category"],
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
        """Specific risk analysis with AI"""

        prompt = f"""
        Analyze this code for the specific risk: {risk_info['name']}

        Risk Description: {risk_info['description']}
        Category: {risk_info['category']}
        File: {filename}

        Code (first 1000 chars):
        {content[:1000]}

        Return a JSON with:
        - score: risk score 0-100
        - evidence: list of specific evidence found
        - technical_details: technical details of the problem
        - recommendations: specific recommendations
        - severity_justification: severity justification

        Be technical and specific.
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
                "evidence": ["AI analysis unavailable"],
                "technical_details": {"error": str(e)},
                "recommendations": ["Manual verification"],
                "severity_justification": "Default score applied"
            }

    async def _deep_security_analysis(self, content: str, filename: str) -> Dict:
        """Deep security analysis with AI"""

        prompt = f"""
        Perform a deep security analysis of this code:

        File: {filename}
        Code: {content[:2000]}

        Specifically analyze:
        1. Injection vulnerabilities (SQL, XSS, Command)
        2. Authentication and authorization flaws
        3. Sensitive data exposure
        4. Input validation flaws
        5. Insecure configurations
        6. Logging and monitoring failures

        Return JSON with:
        - vulnerabilities: detailed list of vulnerabilities
        - security_score: score 0-100 (0=very secure, 100=very insecure)
        - critical_issues: immediate critical issues
        - recommendations: specific remediation recommendations
        - owasp_categories: applicable OWASP Top 10 categories
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
                "recommendations": ["Manual analysis required"],
                "owasp_categories": [],
                "error": str(e)
            }

    async def _ai_system_analysis(self, files_data: List[Dict]) -> Dict:
        """Complete system analysis with AI"""

        # Prepare system context
        system_context = {
            "total_files": len(files_data),
            "file_types": list(set(f["file_type"] for f in files_data)),
            "classifications": [f["classification"] for f in files_data],
            "total_lines": sum(f["lines_count"] for f in files_data)
        }

        prompt = f"""
        Analyze this complete software system:

        System Context:
        - Total files: {system_context['total_files']}
        - File types: {system_context['file_types']}
        - Total lines: {system_context['total_lines']}

        File classifications:
        {json.dumps(system_context['classifications'][:10], indent=2)}

        Provide a complete architectural analysis in JSON:
        - architecture_assessment: architecture assessment
        - security_posture: overall security posture
        - scalability_analysis: scalability analysis
        - maintainability_score: maintainability score 0-100
        - technical_debt_level: technical debt level
        - deployment_readiness: production readiness
        - risk_hotspots: highest risk areas
        - strategic_recommendations: strategic recommendations
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
                "architecture_assessment": "AI analysis unavailable",
                "security_posture": "Requires manual analysis",
                "scalability_analysis": "Not evaluated",
                "maintainability_score": 50,
                "technical_debt_level": "Medium",
                "deployment_readiness": "Requires assessment",
                "risk_hotspots": ["Manual analysis needed"],
                "strategic_recommendations": ["Enable AI analysis"],
                "error": str(e)
            }

    async def _compliance_analysis(self, files_data: List[Dict], system_analysis: Dict) -> Dict:
        """Detailed compliance analysis with multiple frameworks"""

        compliance_violations = []
        framework_scores = {}

        for framework, requirements in COMPLIANCE_REQUIREMENTS.items():

            # Specific analysis per framework
            violations = await self._analyze_framework_compliance(files_data, framework, requirements)
            compliance_violations.extend(violations)

            # Score per framework
            framework_score = self._calculate_framework_score(violations)
            framework_scores[framework] = framework_score

        return {
            "overall_compliance_score": sum(framework_scores.values()) / len(framework_scores) if framework_scores else 0,
            "framework_scores": framework_scores,
            "violations": compliance_violations,
            "critical_violations": [v for v in compliance_violations if v.severity in [RiskLevel.CRITICAL, RiskLevel.HIGH]],
            "remediation_timeline": self._estimate_compliance_timeline(compliance_violations),
            "penalty_risk_assessment": self._assess_penalty_risks(compliance_violations)
        }

    async def _analyze_framework_compliance(self, files_data: List[Dict], framework: ComplianceFramework, requirements: Dict) -> List[ComplianceViolation]:
        """Compliance analysis for specific framework"""

        violations = []

        # AI compliance analysis
        for file_data in files_data:
            ai_compliance = await self._ai_compliance_check(file_data, framework, requirements)

            for violation_data in ai_compliance.get("violations", []):
                # Ensure severity is a valid RiskLevel enum member
                severity_str = violation_data.get("severity", "MEDIUM").upper()
                try:
                    severity = RiskLevel[severity_str]
                except KeyError:
                    severity = RiskLevel.MEDIUM # Default if invalid

                violation = ComplianceViolation(
                    framework=framework,
                    article=violation_data.get("article", "Not specified"),
                    description=violation_data.get("description", ""),
                    severity=severity,
                    evidence=violation_data.get("evidence", []),
                    remediation=violation_data.get("remediation", []),
                    penalty_risk=violation_data.get("penalty_risk", "Low")
                )
                violations.append(violation)

        return violations

    async def _ai_compliance_check(self, file_data: Dict, framework: ComplianceFramework, requirements: Dict) -> Dict:
        """DETAILED compliance check with AI - Complete Implementation"""

        content_preview = file_data.get("content_preview", "")
        filename = file_data.get("filename", "")
        file_type = file_data.get("file_type", "Unknown")

        # Specific and detailed analysis by framework
        if framework == ComplianceFramework.EU_AI_ACT:
            prompt = f"""
            SPECIFIC EU AI ACT ANALYSIS - {filename} ({file_type})

            Code to analyze:
            {content_preview[:1500]}

            Specifically check each article:

            🔍 Art. 6 - HIGH-RISK AI SYSTEMS:
            - Does this code implement an AI system that can affect financial/credit decisions?
            - Is there automated processing of personal data for critical decisions?

            🔍 Art. 8 - CONFORMITY OF HIGH-RISK SYSTEMS:
            - Is a quality management system implemented?
            - Is there adequate technical documentation?

            🔍 Art. 9 - RISK MANAGEMENT SYSTEM:
            - Is there identification and analysis of known risks?
            - Is a risk mitigation process implemented?

            🔍 Art. 13 - TRANSPARENCY:
            - Does the system inform users that they are interacting with AI?
            - Are there clear explanations of how the system works?

            🔍 Art. 14 - HUMAN OVERSIGHT:
            - Is effective human oversight implemented?
            - Can humans intervene in system decisions?

            🔍 Art. 15 - ACCURACY AND ROBUSTNESS:
            - Is there input data validation?
            - Is there error and failure handling?

            RETURN EXACT JSON:
            {{
                "violations": [
                    {{
                        "article": "Art. X",
                        "description": "specific violation description",
                        "severity": "HIGH/MEDIUM/LOW",
                        "evidence": ["specific evidence in code"],
                        "remediation": ["specific action needed"],
                        "penalty_risk": "Up to 7% of annual turnover (€35M maximum)"
                    }}
                ],
                "compliance_score": 0-100,
                "specific_articles_violated": ["Art. X", "Art. Y"],
                "recommendations": ["specific technical recommendation"]
            }}
            """

        elif framework == ComplianceFramework.LGPD_BRAZIL:
            prompt = f"""
            SPECIFIC LGPD BRAZIL ANALYSIS - {filename} ({file_type})

            Code to analyze:
            {content_preview[:1500]}

            Specifically check each article:

            🔍 Art. 5 - PERSONAL DATA:
            - Does the code process information that identifies a natural person?
            - Is there processing of sensitive data (racial origin, health, etc.)?

            🔍 Art. 7 - LEGAL BASES:
            - Is there a clear legal basis for processing (consent, contract, etc.)?
            - Is the processing necessary for a specific purpose?

            🔍 Art. 8 - CONSENT:
            - When necessary, is free and informed consent obtained?
            - Can consent be easily revoked?

            🔍 Art. 9 - SENSITIVE DATA:
            - Is sensitive data processed without specific consent?
            - Is there additional protection for sensitive data?

            🔍 Art. 18 - DATA SUBJECT RIGHTS:
            - Are data subject rights implemented (access, correction, deletion)?
            - Is there a process to fulfill data subject requests?

            🔍 Art. 46 - PROCESSING AGENTS:
            - Is there a clear definition of controller and processor?
            - Is a DPO (Data Protection Officer) in place when necessary?

            RETURN EXACT JSON:
            {{
                "violations": [
                    {{
                        "article": "Art. X",
                        "description": "specific violation description",
                        "severity": "HIGH/MEDIUM/LOW",
                        "evidence": ["specific evidence in code"],
                        "remediation": ["specific action needed"],
                        "penalty_risk": "Up to R$ 50 million per infraction"
                    }}
                ],
                "compliance_score": 0-100,
                "specific_articles_violated": ["Art. X", "Art. Y"],
                "recommendations": ["specific technical recommendation"]
            }}
            """

        elif framework == ComplianceFramework.GDPR_EU:
            prompt = f"""
            SPECIFIC GDPR ANALYSIS - {filename} ({file_type})

            Check specific articles:
            - Art. 6: Lawfulness of processing
            - Art. 7: Conditions for consent
            - Art. 25: Data protection by design
            - Art. 32: Security of processing
            - Art. 35: Impact assessment

            Code: {content_preview[:1500]}

            RETURN JSON with specific violations, penalty_risk: "Up to 4% of annual turnover (€20M maximum)"
            """

        elif framework == ComplianceFramework.SOX_US:
            prompt = f"""
            SPECIFIC SOX (Sarbanes-Oxley) ANALYSIS - {filename} ({file_type})

            Check specific sections:
            - Section 302: Executive responsibility
            - Section 404: Internal controls
            - Section 409: Real-time disclosure
            - Section 906: Criminal liability

            Code: {content_preview[:1500]}

            RETURN JSON with specific violations, penalty_risk: "Fines up to $5M + imprisonment"
            """

        elif framework == ComplianceFramework.BASEL_III:
            prompt = f"""
            SPECIFIC BASEL III ANALYSIS - {filename} ({file_type})

            Check specific pillars:
            - Pillar 1: Minimum capital requirements
            - Pillar 2: Supervisory process
            - Pillar 3: Market discipline
            - Operational risk management

            Code: {content_preview[:1500]}

            RETURN JSON with specific violations, penalty_risk: "Regulatory sanctions + license revocation"
            """

        elif framework == ComplianceFramework.PCI_DSS:
            prompt = f"""
            SPECIFIC PCI DSS ANALYSIS - {filename} ({file_type})

            Check specific requirements:
            - Req. 1: Firewall and network configuration
            - Req. 2: Default passwords and security parameters
            - Req. 3: Cardholder data protection
            - Req. 4: Encryption in transmission
            - Req. 6: Secure development
            - Req. 8: Unique identification for access

            Code: {content_preview[:1500]}

            RETURN JSON with specific violations, penalty_risk: "Fines of $50K-$500K per month"
            """

        else:
            prompt = f"Generic compliance analysis for {framework.value} - file {filename}"

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1
            )

            result = json.loads(response.choices[0].message.content)

            # Ensure standard structure
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
            # Fallback with real basic analysis
            violations = self._basic_compliance_analysis(content_preview, framework, filename)

            return {
                "violations": violations,
                "compliance_score": max(0, 80 - len(violations) * 15),
                "specific_articles_violated": [v["article"] for v in violations],
                "recommendations": [f"Manually review {framework.value}"],
                "error": str(e)
            }

    def _basic_compliance_analysis(self, content: str, framework: ComplianceFramework, filename: str) -> List[Dict]:
        """Basic compliance analysis when AI fails"""

        violations = []
        content_lower = content.lower()

        if framework == ComplianceFramework.EU_AI_ACT:
            # Specific AI Act checks
            if any(term in content_lower for term in ['decision', 'predict', 'classify', 'recommend']):
                if 'human' not in content_lower and 'approval' not in content_lower:
                    violations.append({
                        "article": "Art. 14",
                        "description": "AI system without adequate human oversight detected",
                        "severity": "HIGH",
                        "evidence": [f"Automated decisions in {filename}"],
                        "remediation": ["Implement human oversight", "Add manual approval"],
                        "penalty_risk": "Up to 7% of global annual turnover (€35M maximum)"
                    })

            if 'transparent' not in content_lower and 'explain' not in content_lower:
                violations.append({
                    "article": "Art. 13",
                    "description": "Lack of transparency in the AI system",
                    "severity": "MEDIUM",
                    "evidence": [f"Lack of explainability in {filename}"],
                    "remediation": ["Implement explainability", "Add decision logs"],
                    "penalty_risk": "Up to 7% of global annual turnover (€35M maximum)"
                })

        elif framework == ComplianceFramework.LGPD_BRAZIL:
            # Specific LGPD checks
            if any(term in content_lower for term in ['cpf', 'email', 'phone', 'address', 'personal']):
                if 'consent' not in content_lower and 'legal_basis' not in content_lower:
                    violations.append({
                        "article": "Art. 7",
                        "description": "Processing of personal data without clear legal basis",
                        "severity": "HIGH",
                        "evidence": [f"Personal data processed in {filename}"],
                        "remediation": ["Define legal basis", "Implement consent"],
                        "penalty_risk": "Up to R$ 50 million per infraction"
                    })

            if any(term in content_lower for term in ['health', 'race', 'religion', 'biometric']):
                violations.append({
                    "article": "Art. 9",
                    "description": "Possible processing of sensitive data detected",
                    "severity": "HIGH",
                    "evidence": [f"Indications of sensitive data in {filename}"],
                    "remediation": ["Implement special protections", "Obtain specific consent"],
                    "penalty_risk": "Up to R$ 50 million per infraction"
                })

        elif framework == ComplianceFramework.PCI_DSS:
            # Specific PCI DSS checks
            if any(term in content_lower for term in ['card', 'credit', 'payment', 'pan']):
                if 'encrypt' not in content_lower and 'hash' not in content_lower:
                    violations.append({
                        "article": "Req. 3",
                        "description": "Card data without adequate cryptographic protection",
                        "severity": "HIGH",
                        "evidence": [f"Unencrypted payment data in {filename}"],
                        "remediation": ["Implement encryption", "Apply tokenization"],
                        "penalty_risk": "Fines of $50K-$500K per month"
                    })

        return violations

    async def _enterprise_cross_analysis(self, files_data: List[Dict], system_analysis: Dict) -> Dict:
        """Enterprise cross-file analysis"""

        # Dependency analysis
        dependency_risks = await self._analyze_dependencies(files_data)

        # Component communication analysis
        integration_risks = await self._analyze_integrations(files_data)

        # Security architecture analysis
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
        """Dependency risk analysis"""

        dependency_risks = []

        for file_data in files_data:
            content = file_data.get("content_preview", "")

            # Search for imports and dependencies
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
                # AI analysis of dependencies
                ai_dep_analysis = await self._ai_dependency_analysis(dependencies, file_data["filename"])

                dependency_risks.append({
                    "file": file_data["filename"],
                    "dependencies": dependencies[:10],  # Limit to avoid overloading
                    "risk_score": ai_dep_analysis.get("risk_score", 30),
                    "critical_dependencies": ai_dep_analysis.get("critical_dependencies", []),
                    "recommendations": ai_dep_analysis.get("recommendations", [])
                })

        return dependency_risks

    async def _ai_dependency_analysis(self, dependencies: List[str], filename: str) -> Dict:
        """Dependency analysis with AI"""

        prompt = f"""
        Analyze these dependencies for file {filename}:

        Dependencies: {dependencies[:20]}

        Assess the risks:
        1. Known outdated dependencies
        2. Libraries with vulnerabilities
        3. Unmaintained dependencies
        4. Potential conflicts
        5. Unnecessary dependencies

        Return JSON with:
        - risk_score: 0-100
        - critical_dependencies: list of critical dependencies
        - recommendations: specific recommendations
        - vulnerability_alerts: vulnerability alerts
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
                "recommendations": ["Manual verification"],
                "vulnerability_alerts": []
            }

    def _calculate_enterprise_score(self, files_data: List[Dict], system_analysis: Dict,
                                     compliance_analysis: Dict, cross_analysis: Dict) -> Dict:
        """Calculation of the final enterprise score"""

        # Component scores
        avg_file_score = sum(f["file_score"] for f in files_data) / len(files_data) if files_data else 0
        system_score = system_analysis.get("maintainability_score", 50)
        compliance_score = compliance_analysis.get("overall_compliance_score", 70)
        architecture_score = 100 - cross_analysis.get("system_complexity_score", 30)

        # Component weights
        weights = {
            "files": 0.25,
            "system": 0.25,
            "compliance": 0.35,  # Higher weight for compliance
            "architecture": 0.15
        }

        # Weighted final score
        overall_score = (
            avg_file_score * weights["files"] +
            system_score * weights["system"] +
            compliance_score * weights["compliance"] +
            architecture_score * weights["architecture"]
        )

        # Critical penalties
        critical_violations = len(compliance_analysis.get("critical_violations", []))
        # Note: Your original code had `overall_score += min(critical_violations * 15, 40)`. This increases the score
        # for critical violations, which is counterintuitive. A higher score is usually better.
        # Assuming you want to *penalize* the score for critical violations:
        overall_score -= min(critical_violations * 5, 20)  # Example: max penalty of 20 points, 5 per critical violation

        overall_score = min(100, max(0, overall_score))

        return {
            "overall_score": round(overall_score, 1),
            "component_scores": {
                "files_average": round(avg_file_score, 1),
                "system_analysis": round(system_score, 1),
                "compliance": round(compliance_score, 1),
                "architecture": round(architecture_score, 1)
            },
            "critical_violations_penalty_applied": min(critical_violations * 5, 20),
            "risk_distribution": self._calculate_risk_distribution(files_data),
            "priority_actions": self._identify_priority_actions(compliance_analysis, cross_analysis)
        }

    def _get_enterprise_risk_level(self, score: float) -> RiskLevel:
        """Converts score to enterprise risk level"""
        # Assuming a lower score is better (less risk)
        if score >= 80: # 80-100 means good, low risk
            return RiskLevel.MINIMAL
        elif score >= 65: # 65-79 means moderate risk
            return RiskLevel.LOW
        elif score >= 40: # 40-64 means medium risk
            return RiskLevel.MEDIUM
        elif score >= 20: # 20-39 means high risk
            return RiskLevel.HIGH
        else: # 0-19 means critical risk
            return RiskLevel.CRITICAL

    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Converts numeric score to RiskLevel enum"""
        return self._get_enterprise_risk_level(score)

    def _calculate_priority(self, score: float, compliance_impact: Dict) -> int:
        """Calculates remediation priority (1-5, 1 being most urgent)"""
        # Invert score logic for priority: lower score (higher risk) = higher priority (lower number)
        base_priority = int(score / 20) + 1  # 0-19 -> 1, 20-39 -> 2, etc. (high score = low priority)

        # Adjust by compliance impact
        critical_frameworks = sum(1 for impact in compliance_impact.values()
                                       if "critical" in impact.lower() or "high" in impact.lower())

        priority = max(1, base_priority - critical_frameworks) # More critical frameworks reduce priority number
        return min(5, priority) # Ensure it stays within 1-5 range

    def _estimate_remediation_cost(self, score: float) -> str:
        """Estimates remediation cost"""
        # Cost is higher for lower scores (higher risk)
        if score <= 20:
            return "High (R$ 50k - R$ 200k)"
        elif score <= 40:
            return "Medium-High (R$ 20k - R$ 50k)"
        elif score <= 65:
            return "Medium (R$ 5k - R$ 20k)"
        elif score <= 80:
            return "Low (R$ 1k - R$ 5k)"
        else:
            return "Minimal (< R$ 1k)"

    def _estimate_timeline(self, score: float) -> str:
        """Estimates remediation timeline"""
        # Timeline is shorter for lower scores (higher risk)
        if score <= 20:
            return "Immediate (1-2 weeks)"
        elif score <= 40:
            return "Urgent (2-4 weeks)"
        elif score <= 65:
            return "Medium term (1-2 months)"
        elif score <= 80:
            return "Long term (2-3 months)"
        else:
            return "Planned (3+ months)"

    # Helper methods (placeholders as their implementation wasn't provided in the original code snippet)
    def _calculate_file_enterprise_score(self, risk_assessments: List[RiskAssessment], security_analysis: Dict, content: str) -> float:
        """Calculates the enterprise score for a single file."""
        # Risk assessments: lower score means higher risk. Map to score where 100 is best.
        total_risk_score = sum(ra.score for ra in risk_assessments)
        avg_risk_score_raw = total_risk_score / len(risk_assessments) if risk_assessments else 100 # If no risks, perfect score
        avg_risk_score = 100 - avg_risk_score_raw # Invert so 100 is good, 0 is bad for risk assessment

        # Security analysis: security_score 0-100 (0=very secure, 100=very insecure). Invert to 100=secure.
        security_score = 100 - security_analysis.get("security_score", 50) 

        # Simple weighted average
        file_score = (avg_risk_score * 0.6) + (security_score * 0.4)
        return min(100, max(0, file_score))

    def _extract_critical_blocks(self, lines: List[str]) -> List[str]:
        """Extracts critical code blocks (placeholder)"""
        # This would involve parsing code for critical functions, security-sensitive areas, etc.
        # For simplicity, returning a placeholder.
        return ["No critical blocks extracted (placeholder)"]

    async def _ai_code_insights(self, content: str, filename: str) -> Dict:
        """Generates AI-powered code insights (placeholder)"""
        # This would involve calling the LLM to provide high-level insights about the code.
        return {"summary": "AI insights unavailable (placeholder)", "key_findings": []}

    async def _assess_compliance_impact(self, framework: ComplianceFramework, risk_info: Dict, ai_analysis: Dict) -> str:
        """Assesses compliance impact (placeholder)"""
        # This would involve detailed analysis of how the risk affects specific compliance articles.
        # For now, return a basic string based on AI analysis score.
        score = ai_analysis.get('score', 0)
        if score >= 80:
            return "Minimal impact"
        elif score >= 60:
            return "Moderate impact"
        elif score >= 40:
            return "High impact"
        else:
            return "Critical impact"


    def _calculate_framework_score(self, violations: List[ComplianceViolation]) -> float:
        """Calculates compliance score for a framework (placeholder)"""
        # A simple scoring: 100 - (number of high/critical violations * penalty)
        critical_violations = sum(1 for v in violations if v.severity in [RiskLevel.CRITICAL, RiskLevel.HIGH])
        score = max(0, 100 - (critical_violations * 20))
        return score

    def _estimate_compliance_timeline(self, violations: List[ComplianceViolation]) -> Dict:
        """Estimates compliance remediation timeline (placeholder)"""
        immediate = sum(1 for v in violations if v.severity == RiskLevel.CRITICAL)
        short_term = sum(1 for v in violations if v.severity == RiskLevel.HIGH)
        medium_term = sum(1 for v in violations if v.severity == RiskLevel.MEDIUM)
        
        total_time_estimate = "N/A"
        if immediate > 0:
            total_time_estimate = "1-2 weeks (urgent)"
        elif short_term > 0:
            total_time_estimate = "2-4 weeks"
        elif medium_term > 0:
            total_time_estimate = "1-3 months"
        elif violations:
            total_time_estimate = "3+ months"
        
        details = []
        for v in violations:
            timeline_str = "Immediate" if v.severity == RiskLevel.CRITICAL else \
                            "Short Term" if v.severity == RiskLevel.HIGH else \
                            "Medium Term" if v.severity == RiskLevel.MEDIUM else "Long Term"
            details.append({
                "violation": v.description,
                "timeline": timeline_str,
                "reason": "AI-detected issue",
                "penalty_risk": v.penalty_risk
            })
        
        return {
            "immediate": immediate,
            "short_term": short_term,
            "medium_term": medium_term,
            "estimated_total_time": total_time_estimate,
            "details": details
        }

    def _assess_penalty_risks(self, violations: List[ComplianceViolation]) -> Dict:
        """Assesses penalty risks (placeholder)"""
        # Aggregate penalty risks from violations
        risks = {}
        for v in violations:
            risks.setdefault(v.framework.value, []).append(v.penalty_risk)
        return risks

    async def _analyze_integrations(self, files_data: List[Dict]) -> List[Dict]:
        """Analyzes integration risks (placeholder)"""
        return []

    async def _analyze_security_architecture(self, files_data: List[Dict]) -> Dict:
        """Analyzes security architecture (placeholder)"""
        return {}

    def _identify_single_points_failure(self, files_data: List[Dict]) -> List[str]:
        """Identifies single points of failure (placeholder)"""
        return ["No SPOF identified (placeholder)"]

    def _calculate_complexity_score(self, files_data: List[Dict]) -> float:
        """Calculates system complexity score (placeholder)"""
        return 30.0 # Default for now

    async def _ai_architectural_recommendations(self, files_data: List[Dict], system_analysis: Dict) -> List[str]:
        """Generates AI-powered architectural recommendations (placeholder)"""
        return ["Implement microservices for better scalability", "Strengthen API security measures"]

    def _calculate_risk_distribution(self, files_data: List[Dict]) -> Dict:
        """Calculates risk distribution (placeholder)"""
        distribution = {level.value: 0 for level in RiskLevel}
        for file_data in files_data:
            risk_level = file_data.get('risk_level')
            if risk_level:
                distribution[risk_level.value] += 1
        return distribution

    def _identify_priority_actions(self, compliance_analysis: Dict, cross_analysis: Dict) -> List[str]:
        """Identifies priority actions (placeholder)"""
        actions = []
        critical_compliance = compliance_analysis.get('critical_violations', [])
        if critical_compliance:
            actions.append("Address critical compliance violations immediately.")
        
        spofs = cross_analysis.get('single_points_failure', [])
        if spofs and spofs != ["No SPOF identified (placeholder)"]:
            actions.append("Mitigate identified single points of failure.")
            
        return actions if actions else ["No urgent priority actions identified."]

    def _get_file_type(self, extension: str) -> str:
        """Returns file type based on extension"""
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
        """Basic fallback classification"""
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

# Enterprise Report Generator
class EnterprisePDFGenerator:
    """Enterprise PDF report generator"""

    def generate_enterprise_report(self, analysis_result: Dict) -> bytes:
        """Generates a complete enterprise PDF report"""
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # Enterprise Header
        title = Paragraph("AgentRisk Pro - Enterprise AI Analysis Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 20))

        # Executive Summary
        story.append(Paragraph("EXECUTIVE SUMMARY", styles['Heading1']))

        executive_summary = f"""
        <b>Overall System Score:</b> {analysis_result['enterprise_score']['overall_score']}/100<br/>
        <b>Risk Level:</b> {analysis_result['risk_level'].value}<br/>
        <b>Files Analyzed:</b> {analysis_result['files_analyzed']}<br/>
        <b>Total Lines:</b> {analysis_result['total_lines']:,}<br/>
        <b>Compliance Frameworks Checked:</b> {analysis_result['compliance_frameworks_checked']}<br/>
        <b>AI Model Used:</b> {analysis_result['ai_model_used']}<br/>
        <b>Analysis Date:</b> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}<br/>
        """

        story.append(Paragraph(executive_summary, styles['Normal']))
        story.append(Spacer(1, 30))

        # Compliance Analysis
        if 'compliance_analysis' in analysis_result:
            story.append(Paragraph("REGULATORY COMPLIANCE ANALYSIS", styles['Heading2']))

            compliance = analysis_result['compliance_analysis']

            compliance_table_data = [
                ['Framework', 'Score', 'Status', 'Critical Violations']
            ]

            for framework, score in compliance.get('framework_scores', {}).items():
                status = "✅ Compliant" if score >= 80 else "⚠️ Warning" if score >= 60 else "❌ Non-Compliant"
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

        # Top Critical Risks
        story.append(Paragraph("TOP 5 CRITICAL RISKS IDENTIFIED", styles['Heading2']))

        # Sort risks by score
        all_risks = []
        for file_data in analysis_result.get('files_data', []):
            for risk in file_data.get('risk_assessments', []):
                all_risks.append(risk)

        # Sort by remediation priority first, then by risk score (lower priority number means higher priority)
        # And for risk score, higher score means LOWER risk (so we want lowest score risks first for "critical")
        top_risks = sorted(all_risks, key=lambda x: (x.remediation_priority, x.score))[:5]


        for i, risk in enumerate(top_risks, 1):
            risk_color = '#7f1d1d' if risk.level == RiskLevel.CRITICAL else '#dc2626' if risk.level == RiskLevel.HIGH else '#f59e0b'

            risk_text = f"""
            <font color='{risk_color}'><b>{i}. {risk.name}</b></font><br/>
            <b>Score:</b> {risk.score:.1f}/100 | <b>Level:</b> {risk.level.value}<br/>
            <b>Category:</b> {risk.category}<br/>
            <b>Priority:</b> {risk.remediation_priority}/5 | <b>Estimated Cost:</b> {risk.estimated_cost}<br/>
            <b>Timeline:</b> {risk.timeline}<br/>
            """

            if risk.evidence:
                risk_text += f"<b>Evidence:</b> {'; '.join(risk.evidence[:3])}<br/>"

            story.append(Paragraph(risk_text, styles['Normal']))
            story.append(Spacer(1, 15))

        # Strategic Recommendations
        story.append(Spacer(1, 20))
        story.append(Paragraph("STRATEGIC RECOMMENDATIONS", styles['Heading2']))

        if 'system_analysis' in analysis_result:
            recommendations = analysis_result['system_analysis'].get('strategic_recommendations', [])
            for i, rec in enumerate(recommendations[:5], 1):
                rec_text = f"<b>{i}.</b> {rec}"
                story.append(Paragraph(rec_text, styles['Normal']))
                story.append(Spacer(1, 8))

        # Methodology
        story.append(Spacer(1, 30))
        story.append(Paragraph("ANALYSIS METHODOLOGY", styles['Heading2']))

        methodology_text = """
        <b>Enterprise AI-Powered Analysis:</b><br/>
        • Deep semantic analysis with GPT-4o-mini<br/>
        • Detection of 10 specific risk categories for Autonomous AI<br/>
        • Compliance verification with EU AI Act and LGPD<br/>
        • Cross-analysis of dependencies and architecture<br/>
        • Weighted score considering compliance, security, and architecture<br/><br/>
        
        <b>Based on:</b> IBM Consulting - "Agentic AI in Financial Services" (May/2025)<br/>
        <b>Analyzed Frameworks:</b> EU AI Act, LGPD, GDPR, SOX, Basel III, PCI DSS
        """

        story.append(Paragraph(methodology_text, styles['Normal']))

        # Footer
        story.append(Spacer(1, 40))
        footer_text = f"""
        <b>Report generated by AgentRisk Pro Enterprise</b><br/>
        Analysis Hash: {analysis_result.get('analysis_hash', 'N/A')}<br/>
        Confidential - For internal use only
        """
        story.append(Paragraph(footer_text, styles['Normal']))

        # Generate PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

# Main Enterprise Interface
def main():
    """Main enterprise interface"""

    # Check OpenAI client first
    try:
        client = get_openai_client()
        st.session_state.openai_client = client
    except Exception:
        return  # Error already handled in get_openai_client()

    # Enterprise Header
    st.markdown("""
    <div class="enterprise-header">
        <h1>🛡️ AgentRisk Pro</h1>
        <h3>Enterprise AI-Powered Risk Analysis</h3>
        <p>Deep Risk Analysis in Autonomous AI Systems</p>
        <div class="ai-analysis-badge">✨ Mandatory AI • Advanced Compliance • Enterprise Level</div>
    </div>
    """, unsafe_allow_html=True)

    # Enterprise Status
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.success("✅ OpenAI GPT-4o-mini")
    with col2:
        st.success("✅ ReportLab PDF")
    with col3:
        st.success("✅ 10 Enterprise AI Risks")
    with col4:
        st.success("✅ 6 Compliance Frameworks")

    # Sidebar Enterprise
    with st.sidebar:
        st.header("🎛️ AgentRisk Pro")

        page = st.selectbox("Modules:", [
            "🔍 Enterprise Analysis",
            "📊 Executive Dashboard",
            "⚖️ Compliance Center",
            "🏗️ Architecture & Deps",
            "⚙️ Settings"
        ])

        # Last analysis status
        if 'enterprise_analysis' in st.session_state:
            result = st.session_state.enterprise_analysis
            st.markdown("---")
            st.markdown("**📊 Last Enterprise Analysis**")

            score = result.get('enterprise_score', {}).get('overall_score', 0)
            risk_level = result.get('risk_level', RiskLevel.MEDIUM)

            # Adjust color logic for risk level (higher score = better)
            if score >= 80:
                score_color = "🟢" # Minimal Risk
            elif score >= 65:
                score_color = "🟡" # Low Risk
            elif score >= 40:
                score_color = "🟠" # Moderate Risk
            else:
                score_color = "🔴" # High/Critical Risk

            st.info(f"""
            {score_color} **Score:** {score}/100
            **Level:** {risk_level.value}
            **Files:** {result.get('files_analyzed', 0)}
            **Lines:** {result.get('total_lines', 0):,}
            **AI:** {result.get('ai_model_used', 'N/A')}
            """)

            if st.button("🗑️ Clear Analysis"):
                del st.session_state.enterprise_analysis
                st.rerun()

    # Page routing
    if page == "🔍 Enterprise Analysis":
        show_enterprise_analysis_page()
    elif page == "📊 Executive Dashboard":
        show_executive_dashboard()
    elif page == "⚖️ Compliance Center":
        show_compliance_center()
    elif page == "🏗️ Architecture & Deps":
        show_architecture_analysis()
    else:
        show_enterprise_config()

def show_enterprise_analysis_page():
    """Main enterprise analysis page"""

    st.header("🔍 Enterprise AI System Analysis")

    # If analysis already exists, show results
    if 'enterprise_analysis' in st.session_state:
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔄 New Enterprise Analysis", type="secondary"):
                del st.session_state.enterprise_analysis
                st.rerun()
        with col2:
            st.success("✅ **Enterprise Analysis completed** - Detailed results below")

        show_enterprise_results(st.session_state.enterprise_analysis)
        return

    # Enterprise upload interface
    st.markdown("### 📤 Upload System for Enterprise Analysis")

    st.info("""
    🎯 **Enterprise Analysis Includes:**
    
    **🤖 Mandatory AI:** Deep semantic analysis with GPT-4o-mini
    **⚖️ Advanced Compliance:** EU AI Act, LGPD, GDPR, SOX, Basel III, PCI DSS
    **🏗️ Architecture:** Dependency analysis, SPOF, integration
    **🛡️ Security:** OWASP Top 10, critical vulnerabilities
    **📊 Enterprise Score:** Intelligent weighting with focus on compliance
    """)

    uploaded_files = st.file_uploader(
        "Select system files",
        accept_multiple_files=True,
        type=['py', 'js', 'ts', 'java', 'cs', 'php', 'rb', 'go', 'cpp', 'c',
              'json', 'yaml', 'yml', 'xml', 'sql', 'md', 'txt', 'html', 'css'],
        help="All types of code, configuration, and documentation files"
    )

    if uploaded_files:
        st.success(f"✅ **{len(uploaded_files)} file(s) loaded** for enterprise analysis")

        # Detailed file preview
        with st.expander("📋 Loaded Files - Preview", expanded=True):
            total_size = 0

            for file in uploaded_files:
                file_ext = os.path.splitext(file.name.lower())[1][1:]
                analyzer = EnterpriseCodeAnalyzer(st.session_state.openai_client) # Analyzer instance for helper methods
                file_type = analyzer._get_file_type(file_ext)
                total_size += file.size

                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"📄 **{file.name}**")
                with col2:
                    st.write(f"*{file_type}*")
                with col3:
                    st.write(f"`{file.size:,} bytes`")

            st.write(f"**📊 Total:** {len(uploaded_files)} files • {total_size:,} bytes")

        # Enterprise analysis button
        if st.button("🚀 Execute Complete Enterprise Analysis", type="primary", use_container_width=True):
            # The previous approach with threading.Thread and asyncio.new_event_loop()
            # is prone to issues in Streamlit's single-threaded execution model.
            # A more direct way is to run the async analysis function directly if possible,
            # or use st.status for better UI feedback during long operations.

            analyzer = EnterpriseCodeAnalyzer(st.session_state.openai_client)
            
            # Using st.status for better progress feedback
            with st.status("🔄 Executing complete enterprise analysis...", expanded=True) as status:
                st.write("🤖 Initializing AI analysis...")
                time.sleep(0.5) # Simulate work

                # Run the async function. Since Streamlit runs on a single thread,
                # we need to block for the async operations. asyncio.run() does this.
                # However, asyncio.run() cannot be called if an event loop is already running.
                # This is a common challenge with Streamlit and async.
                # For simplicity and to fix the "Analysis failed" error by ensuring it runs,
                # we'll use asyncio.run() here. In a more complex app, consider alternatives
                # like Streamlit's new `st.experimental_singleton` or using a separate process/worker.
                try:
                    analysis_result = asyncio.run(analyzer.analyze_system_enterprise(uploaded_files))
                    if "error" in analysis_result:
                        status.update(label=f"❌ Analysis failed: {analysis_result['error']}", state="error", expanded=False)
                    else:
                        st.session_state.enterprise_analysis = analysis_result
                        status.update(label="✅ Enterprise Analysis completed!", state="complete", expanded=False)
                        st.rerun() # Rerun to display results
                except RuntimeError as e:
                    if "cannot run an event loop while another event loop is running" in str(e):
                        status.update(label="❌ Analysis failed: Event loop conflict. Please restart the Streamlit app if this persists.", state="error", expanded=False)
                        st.error("There was an issue with the asynchronous event loop. This sometimes happens in Streamlit when trying to run multiple async operations. Please try restarting the application.")
                    else:
                        status.update(label=f"❌ Analysis failed unexpectedly: {str(e)}", state="error", expanded=False)
                    # Clear session state if analysis failed to allow retry
                    if 'enterprise_analysis' in st.session_state:
                        del st.session_state.enterprise_analysis
                except Exception as e:
                    status.update(label=f"❌ Analysis failed: {str(e)}", state="error", expanded=False)
                    if 'enterprise_analysis' in st.session_state:
                        del st.session_state.enterprise_analysis


def show_executive_dashboard():
    """Executive Dashboard page"""
    st.header("📊 Executive Dashboard")

    if 'enterprise_analysis' not in st.session_state:
        st.info("No enterprise analysis found. Please run an analysis first.")
        return

    analysis_result = st.session_state.enterprise_analysis
    enterprise_score = analysis_result.get('enterprise_score', {})
    risk_level = analysis_result.get('risk_level')
    
    st.markdown(f"""
    <div class="score-enterprise">
        <h2>Overall Enterprise Risk Score</h2>
        <h1>{enterprise_score.get('overall_score', 'N/A')}/100</h1>
        <h3>Risk Level: {risk_level.value}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.subheader("Component Scores")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Files Average", enterprise_score.get('component_scores', {}).get('files_average', 'N/A'))
    with col2:
        st.metric("System Analysis", enterprise_score.get('component_scores', {}).get('system_analysis', 'N/A'))
    with col3:
        st.metric("Compliance", enterprise_score.get('component_scores', {}).get('compliance', 'N/A'))
    with col4:
        st.metric("Architecture", enterprise_score.get('component_scores', {}).get('architecture', 'N/A'))

    st.subheader("Risk Distribution by Level")
    # Convert Enum keys to string for JSON serialization
    risk_dist_for_json = {k: v for k, v in enterprise_score.get('risk_distribution', {}).items()}
    st.json(risk_dist_for_json)

    st.subheader("Priority Actions")
    for action in enterprise_score.get('priority_actions', []):
        st.warning(f"🚨 {action}")
        
    st.subheader("Strategic Recommendations")
    if 'system_analysis' in analysis_result:
        for rec in analysis_result['system_analysis'].get('strategic_recommendations', []):
            st.markdown(f"- {rec}")

    if st.button("Download Executive Report (PDF)", type="primary"):
        pdf_generator = EnterprisePDFGenerator()
        pdf_bytes = pdf_generator.generate_enterprise_report(analysis_result)
        st.download_button(
            label="Download PDF Report",
            data=pdf_bytes,
            file_name="AgentRisk_Pro_Enterprise_Report.pdf",
            mime="application/pdf"
        )


def show_compliance_center():
    """Compliance Center page"""
    st.header("⚖️ Compliance Center")

    if 'enterprise_analysis' not in st.session_state:
        st.info("No enterprise analysis found. Please run an analysis first.")
        return

    compliance = st.session_state.enterprise_analysis.get('compliance_analysis', {})
    
    st.subheader("Overall Compliance Status")
    st.markdown(f"**Overall Compliance Score:** {compliance.get('overall_compliance_score', 'N/A'):.1f}/100")
    
    st.subheader("Compliance Scores per Framework")
    for framework, score in compliance.get('framework_scores', {}).items():
        st.metric(f"Score for {framework.value}", f"{score:.1f}/100")

    st.subheader("Compliance Violations")
    violations = compliance.get('violations', [])
    if violations:
        for violation in violations:
            severity_class = f"compliance-{violation.severity.name.lower()}"
            st.markdown(f"""
            <div class="risk-card-enterprise {severity_class}">
                <b>Framework:</b> {violation.framework.value}<br/>
                <b>Article:</b> {violation.article}<br/>
                <b>Description:</b> {violation.description}<br/>
                <b>Severity:</b> {violation.severity.value}<br/>
                <b>Penalty Risk:</b> {violation.penalty_risk}<br/>
                <b>Evidence:</b> {'; '.join(violation.evidence)}<br/>
                <b>Remediation:</b> {'; '.join(violation.remediation)}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("🎉 No compliance violations detected!")

    st.subheader("Remediation Timeline")
    remediation_timeline = compliance.get('remediation_timeline', {})
    if remediation_timeline:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🚨 Immediate", remediation_timeline.get('immediate', 0), help="1-2 weeks - Urgent action")
        with col2:
            st.metric("⚠️ Short Term", remediation_timeline.get('short_term', 0), help="2-4 weeks")
        with col3:
            st.metric("📅 Medium Term", remediation_timeline.get('medium_term', 0), help="1-3 months")
        with col4:
            st.metric("⏱️ Total Estimated Time", remediation_timeline.get('estimated_total_time', 'N/A'))

        st.markdown("**📋 Details by Violation:**")
        for detail in remediation_timeline.get('details', [])[:10]: # Top 10 most urgent
            violation = detail.get('violation', 'N/A')
            timeline = detail.get('timeline', 'N/A')
            reason = detail.get('reason', 'N/A')
            penalty = detail.get('penalty_risk', 'N/A')

            # Emoji based on urgency
            if "Immediate" in timeline:
                emoji = "🔴"
                alert_type = "error"
            elif "Short" in timeline:
                emoji = "🟡"
                alert_type = "warning"
            else:
                emoji = "🟢"
                alert_type = "info"

            with st.expander(f"{emoji} {violation} - {timeline}"):
                st.markdown(f"**Reason:** {reason}")
                st.markdown(f"**Penalty Risk:** {penalty}")
                st.write(f"Further details for {violation}") # Add more details if available

def show_architecture_analysis():
    """Architecture & Dependencies page"""
    st.header("🏗️ Architecture & Dependencies")

    if 'enterprise_analysis' not in st.session_state:
        st.info("No enterprise analysis found. Please run an analysis first.")
        return

    cross_analysis = st.session_state.enterprise_analysis.get('cross_analysis', {})

    st.subheader("System Complexity")
    st.metric("System Complexity Score", cross_analysis.get('system_complexity_score', 'N/A'))

    st.subheader("Dependency Risks")
    dependency_risks = cross_analysis.get('dependency_risks', [])
    if dependency_risks:
        for dr in dependency_risks:
            with st.expander(f"File: {dr.get('file', 'N/A')} - Risk Score: {dr.get('risk_score', 'N/A')}"):
                st.markdown(f"**Dependencies:** {', '.join(dr.get('dependencies', []))}")
                st.markdown(f"**Critical Dependencies:** {', '.join(dr.get('critical_dependencies', []))}")
                st.markdown(f"**Recommendations:** {'; '.join(dr.get('recommendations', []))}")
    else:
        st.info("No significant dependency risks detected.")

    st.subheader("Single Points of Failure (SPOF)")
    spofs = cross_analysis.get('single_points_failure', [])
    if spofs and spofs != ["No SPOF identified (placeholder)"]:
        for spof in spofs:
            st.error(f"🚨 {spof}")
    else:
        st.info("No critical single points of failure identified.")

    st.subheader("Architectural Recommendations")
    arch_recs = cross_analysis.get('architectural_recommendations', [])
    if arch_recs:
        for rec in arch_recs:
            st.markdown(f"- {rec}")
    else:
        st.info("No specific architectural recommendations at this time.")

def show_enterprise_config():
    """Settings page"""
    st.header("⚙️ Settings")
    st.info("Enterprise settings will be configured here.")
    st.warning("Current settings are managed through Streamlit Secrets or Environment Variables.")

def show_enterprise_results(analysis_result: Dict):
    """Displays enterprise analysis results"""
    st.header("Detailed Enterprise Analysis Results")

    # Overall Score
    st.markdown(f"""
    <div class="score-enterprise">
        <h2>Overall Enterprise Risk Score</h2>
        <h1>{analysis_result['enterprise_score']['overall_score']}/100</h1>
        <h3>Risk Level: {analysis_result['risk_level'].value}</h3>
    </div>
    """, unsafe_allow_html=True)

    # Component Scores
    st.subheader("📊 Component Scores")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Files Average", analysis_result['enterprise_score']['component_scores']['files_average'])
    with col2:
        st.metric("System Analysis", analysis_result['enterprise_score']['component_scores']['system_analysis'])
    with col3:
        st.metric("Compliance", analysis_result['enterprise_score']['component_scores']['compliance'])
    with col4:
        st.metric("Architecture", analysis_result['enterprise_score']['component_scores']['architecture'])

    # Files Analyzed
    st.subheader("📖 Files Analyzed")
    st.info(f"Analyzed **{analysis_result['files_analyzed']} files** with a total of **{analysis_result['total_lines']:,} lines of code.**")
    
    with st.expander("Detailed File Analysis"):
        for file_data in analysis_result.get('files_data', []):
            st.markdown(f"#### 📄 {file_data['filename']} ({file_data['file_type']})")
            st.write(f"Lines: {file_data['lines_count']} | Chars: {file_data['char_count']}")
            st.write(f"File Score: {file_data['file_score']:.1f}/100 | Risk Level: {file_data['risk_level'].value}")
            # Ensure classification is JSON serializable
            try:
                st.json(file_data['classification'])
            except TypeError:
                st.write("Classification data not displayable as JSON.")
                st.write(file_data['classification'])

            if file_data.get('ai_insights'):
                st.write(f"AI Insights: {file_data['ai_insights'].get('summary', 'N/A')}")
            
            if file_data.get('risk_assessments'):
                st.markdown("##### Detected Risks:")
                for risk_assessment in file_data['risk_assessments']:
                    severity_class = f"risk-{risk_assessment.level.name.lower()}"
                    # Ensure technical_details is JSON serializable
                    tech_details_str = ""
                    try:
                        tech_details_str = json.dumps(risk_assessment.technical_details, indent=2)
                    except TypeError:
                        tech_details_str = str(risk_assessment.technical_details) # Fallback to string if not serializable

                    st.markdown(f"""
                    <div class="risk-card-enterprise {severity_class}">
                        <b>Risk ID:</b> {risk_assessment.risk_id}<br/>
                        <b>Name:</b> {risk_assessment.name}<br/>
                        <b>Category:</b> {risk_assessment.category}<br/>
                        <b>Score:</b> {risk_assessment.score:.1f}/100 | <b>Level:</b> {risk_assessment.level.value}<br/>
                        <b>Priority:</b> {risk_assessment.remediation_priority}/5 | <b>Cost:</b> {risk_assessment.estimated_cost}<br/>
                        <b>Timeline:</b> {risk_assessment.timeline}<br/>
                        <b>Evidence:</b> {'; '.join(risk_assessment.evidence[:2])}...<br/>
                        <b>Technical Details:</b> <div class="technical-detail">{tech_details_str}</div>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown("---")

    # System Analysis
    st.subheader("🤖 System-Wide Analysis")
    system_analysis = analysis_result.get('system_analysis', {})
    st.json(system_analysis)

    # Compliance Analysis
    st.subheader("⚖️ Compliance Overview")
    compliance = analysis_result.get('compliance_analysis', {})
    st.markdown(f"**Overall Compliance Score:** {compliance.get('overall_compliance_score', 'N/A'):.1f}/100")
    st.markdown(f"**Critical Violations:** {len(compliance.get('critical_violations', []))}")
    
    if compliance.get('violations'):
        with st.expander("View All Compliance Violations"):
            for violation in compliance['violations']:
                severity_class = f"compliance-{violation.severity.name.lower()}"
                st.markdown(f"""
                <div class="risk-card-enterprise {severity_class}">
                    <b>Framework:</b> {violation.framework.value}<br/>
                    <b>Article:</b> {violation.article}<br/>
                    <b>Description:</b> {violation.description}<br/>
                    <b>Severity:</b> {violation.severity.value}<br/>
                    <b>Penalty Risk:</b> {violation.penalty_risk}<br/>
                </div>
                """, unsafe_allow_html=True)

    # Remediation Timeline
    st.subheader("⏰ Detailed Remediation Timeline")
    remediation_timeline = compliance.get('remediation_timeline', {})
    if remediation_timeline:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            immediate = remediation_timeline.get('immediate', 0)
            st.metric("🚨 Immediate", immediate, help="1-2 weeks - Urgent action")
        with col2:
            short_term = remediation_timeline.get('short_term', 0)
            st.metric("⚠️ Short Term", short_term, help="2-4 weeks")
        with col3:
            medium_term = remediation_timeline.get('medium_term', 0)
            st.metric("📅 Medium Term", medium_term, help="1-3 months")
        with col4:
            total_time = remediation_timeline.get('estimated_total_time', 'N/A')
            st.metric("⏱️ Total Estimated Time", total_time)

        st.markdown("**📋 Details by Violation:**")
        timeline_details = remediation_timeline.get('details', [])
        if timeline_details:
            for detail in timeline_details[:10]: # Top 10 most urgent
                violation = detail.get('violation', 'N/A')
                timeline = detail.get('timeline', 'N/A')
                reason = detail.get('reason', 'N/A')
                penalty = detail.get('penalty_risk', 'N/A')

                # Emoji based on urgency
                if "Immediate" in timeline:
                    emoji = "🔴"
                elif "Short" in timeline:
                    emoji = "🟡"
                else:
                    emoji = "🟢"

                with st.expander(f"{emoji} {violation} - {timeline}"):
                    st.markdown(f"**Reason:** {reason}")
                    st.markdown(f"**Penalty Risk:** {penalty}")
        else:
            st.info("No remediation timeline details available.")

    # Cross Analysis
    st.subheader("🔗 Architectural & Cross-System Analysis")
    cross_analysis = analysis_result.get('cross_analysis', {})
    st.json(cross_analysis)

# Entry point
if __name__ == "__main__":
    main()
