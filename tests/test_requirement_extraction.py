from __future__ import annotations

from job_app_ops.services.tool_gateway import extract_job_requirements


def test_extract_job_requirements_from_german_data_engineer_ad():
    description = """
    Verantwortung Du entwickelst und betreibst Datenpipelines zwischen internen und externen Systemen.
    Du modellierst Datenstrukturen und harmonisierst unterschiedliche Datenquellen (z. B. CRM, ERP, APIs).
    Du erstellst Reports, Dashboards und Ad-hoc-Auswertungen.
    Qualifikationen Du hast Erfahrung im Data Engineering, in Datenanalyse sowie im Aufbau von Datenpipelines und Datenmodellen.
    Sehr gute Deutschkenntnisse in Wort und Schrift.
    """

    requirements = extract_job_requirements(description)

    assert "Data pipelines" in requirements.required_skills
    assert "Data modeling" in requirements.required_skills
    assert "CRM" in requirements.required_skills
    assert "ERP" in requirements.required_skills
    assert "Reporting" in requirements.required_skills
    assert "German" in requirements.language_requirements
    assert requirements.hard_blockers


def test_extract_job_requirements_from_ai_first_fullstack_ad():
    description = """
    Deine Aufgaben Entwicklung von Frontend-Features mit Vue.js / Nuxt.
    Entwicklung und Pflege von Backend-Diensten mit ASP.NET Core / .NET.
    Integration und Erprobung von KI-Agenten zur Optimierung unserer Entwicklungsprozesse
    Code-Generierung, Testing, Dokumentation, CI/CD.
    Was du mitbringst Gute Kenntnisse in REST / GraphQL APIs und praktische Erfahrung mit GitHub Copilot, Cursor oder Claude Code.
    Deutsch und Englisch fliessend.
    """

    requirements = extract_job_requirements(description)

    assert "Vue.js" in requirements.required_skills
    assert "Nuxt" in requirements.required_skills
    assert "ASP.NET Core" in requirements.required_skills
    assert ".NET" in requirements.required_skills
    assert "GraphQL" in requirements.required_skills
    assert "AI agents" in requirements.required_skills
    assert "German" in requirements.language_requirements
    assert "English" in requirements.language_requirements
