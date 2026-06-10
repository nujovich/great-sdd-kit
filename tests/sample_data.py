"""
GREAT Pre-Estimation — Sample Test Data.

Mirrors the data from the UX prototype for realistic testing.
"""
from __future__ import annotations

# Sample project lines matching the UX prototype
SAMPLE_PROJECT_LINES = [
    {
        "id": "PL-001",
        "name": "API refactor de autenticación",
        "project": "Auth Platform",
        "organ_type": "Thermal Engine",
        "energy_fuel_type": "Gasoline",
        "project_ranking": "Mother",
        "injection_system": "Direct Injection",
        "assignee": "Ana Martinez",
        "metier": "H-DESIGN",
        "status": "to_do",
        "sp_date": "2026-01-01",
        "duration_months": 6,
        "description": "Refactor the authentication API to support OAuth2.0 with JWT tokens, including refresh token rotation and session management.",
    },
    {
        "id": "PL-002",
        "name": "OAuth provider integration",
        "project": "Auth Platform",
        "organ_type": "Thermal Engine",
        "energy_fuel_type": "Gasoline",
        "project_ranking": "Mother",
        "injection_system": "Direct Injection",
        "assignee": "Ana Martinez",
        "metier": "H-DESIGN",
        "status": "to_do",
        "sp_date": "2026-02-01",
        "duration_months": 4,
        "description": "Integrate Google, GitHub, and Microsoft OAuth providers for SSO login.",
    },
    {
        "id": "PL-009",
        "name": "SSO con SAML",
        "project": "Auth Platform",
        "organ_type": "Thermal Engine",
        "energy_fuel_type": "Gasoline",
        "project_ranking": "Mother",
        "injection_system": "Direct Injection",
        "assignee": "Ana Martinez",
        "metier": "H-DESIGN",
        "status": "draft",
        "sp_date": "2026-03-01",
        "duration_months": 3,
        "description": "Implement SAML-based Single Sign-On for enterprise clients.",
    },
    {
        "id": "PL-015",
        "name": "MFA con TOTP",
        "project": "Auth Platform",
        "organ_type": "Thermal Engine",
        "energy_fuel_type": "Gasoline",
        "project_ranking": "Mother",
        "injection_system": "Direct Injection",
        "assignee": "Ana Martinez",
        "metier": "H-DESIGN",
        "status": "estimated",
        "sp_date": "2026-04-01",
        "duration_months": 5,
        "description": "Add multi-factor authentication using Time-based One-Time Passwords.",
    },
    {
        "id": "PL-021",
        "name": "Recuperar contraseña v2",
        "project": "Auth Platform",
        "organ_type": "Thermal Engine",
        "energy_fuel_type": "Gasoline",
        "project_ranking": "Mother",
        "injection_system": "Direct Injection",
        "assignee": "Ana Martinez",
        "metier": "H-DESIGN",
        "status": "modification_requested",
        "sp_date": "2026-05-01",
        "duration_months": 2,
        "description": "Redesign password recovery flow with transactional emails and rate limiting.",
    },
]

# Incompatible line (different organ_type)
INCOMPATIBLE_LINE = {
    "id": "PL-030",
    "name": "Mobile dashboard",
    "project": "Customer Portal",
    "organ_type": "Electric Motor",
    "energy_fuel_type": "Electric",
    "project_ranking": "Child",
    "injection_system": None,  # Null injection system
    "assignee": "Carlos Ruiz",
    "metier": "H-SOFTWARE",
    "status": "to_do",
    "sp_date": "2026-06-01",
    "duration_months": 4,
    "description": "Build a mobile-responsive customer dashboard.",
}

# Sample job units for estimation calculation
SAMPLE_JOB_UNITS = [
    {
        "short_name": "API-DEV",
        "description": "API Development",
        "variable": 2.0,
        "fixed": 0.5,
        "occurrence": 5,
        "unit_type": "man_day",
        "cran": "Simple",
    },
    {
        "short_name": "API-TEST",
        "description": "API Testing",
        "variable": 1.0,
        "fixed": 0.25,
        "occurrence": 5,
        "unit_type": "man_day",
        "cran": "Simple",
    },
    {
        "short_name": "DB-DESIGN",
        "description": "Database Design",
        "variable": 1.0,
        "fixed": 0.0,
        "occurrence": 3,
        "unit_type": "man_day",
        "cran": "Medium",
    },
]


# Sample role-based test scenarios
ENGINEER_ANA = {"role": "Engineer", "user": "Ana Martinez"}
ENGINEER_CARLOS = {"role": "Engineer", "user": "Carlos Ruiz"}
PMO_USER = {"role": "PMO", "user": "Laura Gomez"}
ADMIN_USER = {"role": "Admin", "user": "Admin User"}
CPO_USER = {"role": "CPO", "user": "CPO User"}