"""
Role definitions and routing engine for Antigravity Cockpit, modeled on Paperclip's organizational structure.
"""

ROLE_DEFINITIONS = [
    {
        "id": "ceo",
        "name": "CEO",
        "title": "Chief Executive Officer & Fleet Orchestrator",
        "category": "Executive",
        "icon": "👑",
        "description": "Sets direction, breaks down high-level board goals, delegates work orders to specialized direct reports, monitors subagent health via heartbeats, and maintains organizational velocity. Never executes individual contributor code directly.",
        "domain_keywords": [
            "strategy", "coordinate", "orchestrate", "delegate", "plan", "milestone", "lead", "manage", "triage", "review", "approve"
        ],
        "default_engine": "antigravity",
        "can_execute_code": False,
        "system_prompt_seed": (
            "You are the CEO. You lead the company and orchestrate the agent fleet. "
            "You MUST delegate work rather than doing it yourself. You own strategy, task triage, "
            "assigning work orders to direct reports, and verifying deliverables against acceptance criteria."
        )
    },
    {
        "id": "cto",
        "name": "CTO",
        "title": "Chief Technology Officer & System Architect",
        "category": "Executive",
        "icon": "🏛️",
        "description": "Oversees system architecture, technical blueprints, code quality standards, cross-service integrations, and infrastructure decisions.",
        "domain_keywords": [
            "architecture", "system design", "infrastructure", "blueprint", "tech stack", "schema", "security", "scalability", "refactor", "framework"
        ],
        "default_engine": "antigravity",
        "can_execute_code": True,
        "system_prompt_seed": (
            "You are the CTO. You own technical architecture, system design, and engineering quality. "
            "Design robust solutions, define clear interfaces, review architectural proposals, and resolve complex engineering challenges."
        )
    },
    {
        "id": "frontend",
        "name": "Frontend Specialist",
        "title": "Senior Frontend & UI/UX Engineer",
        "category": "Engineering",
        "icon": "🎨",
        "description": "Builds responsive, high-performance user interfaces with React, Next.js, Vue, Tailwind CSS, shadcn/ui, state management, and modern UX patterns.",
        "domain_keywords": [
            "frontend", "ui", "ux", "react", "nextjs", "tailwind", "css", "component", "html", "view", "page", "modal", "theme", "design", "client", "button", "layout"
        ],
        "default_engine": "antigravity",
        "can_execute_code": True,
        "system_prompt_seed": (
            "You are the Frontend Specialist. You build polished, responsive, modern user interfaces. "
            "Focus on clean component hierarchy, accessibility, responsive styling with Tailwind/CSS, and reactive state management."
        )
    },
    {
        "id": "backend",
        "name": "Backend Specialist",
        "title": "Senior Backend & Systems Engineer",
        "category": "Engineering",
        "icon": "⚡",
        "description": "Implements REST/GraphQL APIs, databases (Postgres, Convex, SQLite, Redis), serverless functions, authentication, background workers, and business logic.",
        "domain_keywords": [
            "backend", "api", "database", "convex", "postgres", "sql", "sqlite", "server", "endpoint", "auth", "jwt", "clerk", "crud", "query", "mutation", "route"
        ],
        "default_engine": "antigravity",
        "can_execute_code": True,
        "system_prompt_seed": (
            "You are the Backend Specialist. You build robust server architectures, database schemas, "
            "secure authentication systems, and performant API endpoints. Ensure strict error handling and data validation."
        )
    },
    {
        "id": "codex",
        "name": "Codex Specialist",
        "title": "Code Synthesis & Algorithmic Specialist",
        "category": "Specialized",
        "icon": "💻",
        "description": "Deep algorithmic coding, precision refactoring, large file migrations, syntax corrections, and high-throughput code synthesis.",
        "domain_keywords": [
            "algorithm", "synthesis", "refactoring", "migrate", "parser", "optimization", "types", "compiler", "heavy coding", "codex"
        ],
        "default_engine": "codex",
        "can_execute_code": True,
        "system_prompt_seed": (
            "You are the Codex Specialist. You focus on high-precision code synthesis, optimized algorithms, "
            "clean refactoring, and strict type safety."
        )
    },
    {
        "id": "hermes",
        "name": "Hermes Specialist",
        "title": "Multi-Step Reasoning & Tool Orchestration",
        "category": "Specialized",
        "icon": "🧠",
        "description": "Excels at complex diagnostic workflows, multi-tool agentic steps, root cause analysis, and multi-variable problem solving.",
        "domain_keywords": [
            "reasoning", "logic", "debug", "diagnose", "root cause", "analysis", "investigate", "troubleshoot", "complex plan", "hermes"
        ],
        "default_engine": "hermes",
        "can_execute_code": True,
        "system_prompt_seed": (
            "You are the Hermes Reasoning Specialist. You analyze complex issues step-by-step, "
            "perform thorough root-cause investigations, and coordinate complex multi-tool sequences."
        )
    },
    {
        "id": "openclaw",
        "name": "Open Claw Specialist",
        "title": "Autonomous Web Intelligence & Crawler",
        "category": "Specialized",
        "icon": "🌐",
        "description": "Extracts documentation from the web, scrapes dynamic target sites, monitors external feeds, and gathers research data for engineering teams.",
        "domain_keywords": [
            "scrape", "crawler", "browser", "web", "fetch docs", "research", "extract", "search", "documentation", "external api", "open claw"
        ],
        "default_engine": "openclaw",
        "can_execute_code": True,
        "system_prompt_seed": (
            "You are the Open Claw Web Intelligence Specialist. You autonomously gather external data, "
            "extract API documentation, crawl target resources, and supply clean structured research to the fleet."
        )
    },
    {
        "id": "qa",
        "name": "QA & Verification Specialist",
        "title": "Quality Assurance & Test Automation Lead",
        "category": "Engineering",
        "icon": "🛡️",
        "description": "Writes and executes automated unit, integration, and E2E tests (Vitest, Jest, Playwright), verifies pull requests against acceptance criteria, and spots edge cases.",
        "domain_keywords": [
            "qa", "test", "testing", "vitest", "jest", "playwright", "e2e", "coverage", "verify", "verification", "lint", "assert", "quality", "acceptance"
        ],
        "default_engine": "antigravity",
        "can_execute_code": True,
        "system_prompt_seed": (
            "You are the Quality Assurance & Verification Specialist. You write comprehensive tests, "
            "execute validation suites, verify acceptance criteria, and guarantee that software meets the highest standards of reliability."
        )
    }
]

ROLES_BY_ID = {r["id"]: r for r in ROLE_DEFINITIONS}

def get_role_spec(role_id_or_title):
    """Retrieve role specification by id or partial name match."""
    if not role_id_or_title:
        return ROLES_BY_ID["frontend"]
    
    query = str(role_id_or_title).strip().lower()
    if query in ROLES_BY_ID:
        return ROLES_BY_ID[query]
    
    for r in ROLE_DEFINITIONS:
        if query == r["name"].lower() or query == r["title"].lower():
            return r
        if query in r["id"] or query in r["name"].lower():
            return r
            
    return ROLES_BY_ID["frontend"]

def match_role_for_task(title="", description="", tech_stack=""):
    """
    Score task keywords against role domain keywords to determine the best-suited agent role.
    Excludes CEO because CEO delegates rather than doing the tasks.
    """
    combined_text = f"{title} {description} {tech_stack}".lower()
    
    best_role = "cto"
    best_score = -1
    
    for role in ROLE_DEFINITIONS:
        if role["id"] == "ceo":
            continue
            
        score = 0
        for kw in role["domain_keywords"]:
            if kw.lower() in combined_text:
                score += 2 if len(kw) > 4 else 1
                
        if score > best_score:
            best_score = score
            best_role = role["id"]
            
    if best_score <= 0:
        # Default routing heuristics
        if any(k in combined_text for k in ["page", "button", "css", "color", "style", "view", "react", "html"]):
            return "frontend"
        elif any(k in combined_text for k in ["api", "db", "auth", "token", "model", "server"]):
            return "backend"
        elif any(k in combined_text for k in ["test", "spec", "check", "verify"]):
            return "qa"
        return "cto"
        
    return best_role

def get_chain_of_command():
    """Return standard organizational reporting hierarchy."""
    return {
        "board": {
            "name": "Human Board of Directors",
            "role": "Owner / Operator",
            "reports_to": None,
            "direct_reports": ["ceo"]
        },
        "ceo": {
            "name": "CEO",
            "role": "Chief Executive Officer & Fleet Orchestrator",
            "reports_to": "board",
            "direct_reports": ["cto", "qa"]
        },
        "cto": {
            "name": "CTO",
            "role": "Chief Technology Officer",
            "reports_to": "ceo",
            "direct_reports": ["frontend", "backend", "codex", "hermes", "openclaw"]
        }
    }
