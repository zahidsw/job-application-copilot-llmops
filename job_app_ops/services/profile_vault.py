from __future__ import annotations

import io
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from job_app_ops.config import Settings
from job_app_ops.schemas import CandidateProfile, CandidateSkill, ProfileAssetKind, ProfileAssetRecord, ProfileVault
from job_app_ops.services.tool_gateway import KNOWN_SKILLS


class ProfileVaultService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._vault_path = self.settings.profiles_dir / "profile-vault.json"
        self._uploads_dir = self.settings.profiles_dir / "uploads"
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_vault()

    def get_vault(self, profile_id: str = "primary-candidate") -> ProfileVault:
        vault = self._load_vault()
        if vault.profile_id != profile_id:
            vault.profile.profile_id = profile_id
            vault.profile_id = profile_id
            self._save_vault(vault)
        return vault

    def get_profile(self, profile_id: str = "primary-candidate") -> CandidateProfile:
        return self.get_vault(profile_id).profile

    def save_profile(self, profile: CandidateProfile) -> ProfileVault:
        vault = self.get_vault(profile.profile_id)
        vault.profile = profile
        vault.profile_id = profile.profile_id
        return self._save_vault(vault)

    def merge_request_profile(self, profile_id: str, profile: CandidateProfile | None) -> CandidateProfile:
        vault = self.get_vault(profile_id)
        if profile is None:
            return vault.profile

        merged = _merge_profiles(profile, vault.profile)
        vault.profile = merged
        vault.profile_id = merged.profile_id
        self._save_vault(vault)
        return merged

    def upload_asset(self, file_name: str, content: bytes, kind: ProfileAssetKind | None = None) -> ProfileVault:
        inferred_kind = kind or _infer_kind(file_name)
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", file_name).strip("-") or "upload.bin"
        stored_name = f"{uuid4().hex[:10]}-{safe_name}"
        stored_path = self._uploads_dir / stored_name
        stored_path.write_bytes(content)

        extracted_text = _extract_text(stored_path, content)
        excerpt = _excerpt(extracted_text)

        vault = self.get_vault()
        vault.assets.append(
            ProfileAssetRecord(
                asset_id=uuid4().hex[:12],
                kind=inferred_kind,
                file_name=file_name,
                stored_path=str(stored_path),
                extracted_text_excerpt=excerpt,
                extracted_text=_excerpt(extracted_text, length=12000),
            )
        )

        if inferred_kind in {ProfileAssetKind.cv, ProfileAssetKind.previous_application} and excerpt:
            vault.cv_style_samples = _append_sample(vault.cv_style_samples, excerpt)
        if inferred_kind == ProfileAssetKind.motivation_letter and excerpt:
            vault.motivation_letter_samples = _append_sample(vault.motivation_letter_samples, excerpt)
        if inferred_kind == ProfileAssetKind.reference_letter and excerpt:
            vault.reference_highlights = _append_sample(vault.reference_highlights, excerpt)

        vault.profile = _enrich_profile_from_text(vault.profile, extracted_text, file_name)
        return self._save_vault(vault)

    def get_reference_texts(
        self,
        profile_id: str = "primary-candidate",
        kinds: Iterable[ProfileAssetKind] | None = None,
        limit: int = 5,
    ) -> list[str]:
        vault = self.get_vault(profile_id)
        allowed_kinds = set(kinds or [])
        texts: list[str] = []

        for asset in vault.assets:
            if allowed_kinds and asset.kind not in allowed_kinds:
                continue

            text = asset.extracted_text or ""
            if not text and asset.stored_path:
                stored_path = Path(asset.stored_path)
                if stored_path.is_file():
                    try:
                        text = _extract_text(stored_path, stored_path.read_bytes())
                    except Exception:
                        text = ""
            if not text:
                text = asset.extracted_text_excerpt

            normalized = _excerpt(text, length=12000)
            if normalized:
                texts.append(normalized)
            if len(texts) >= limit:
                break

        return texts

    def _ensure_vault(self) -> None:
        if self._vault_path.exists():
            return
        self._save_vault(ProfileVault())

    def _load_vault(self) -> ProfileVault:
        return ProfileVault.model_validate_json(self._vault_path.read_text(encoding="utf-8"))

    def _save_vault(self, vault: ProfileVault) -> ProfileVault:
        vault.updated_at = datetime.utcnow()
        self._vault_path.write_text(vault.model_dump_json(indent=2), encoding="utf-8")
        return vault


def _extract_text(path: Path, content: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".html", ".htm"}:
        return content.decode("utf-8-sig", errors="ignore")
    if suffix == ".docx":
        from docx import Document

        document = Document(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".odt":
        return _extract_odt_text(content)
    return content.decode("utf-8-sig", errors="ignore")


def _extract_odt_text(content: bytes) -> str:
    from xml.etree import ElementTree
    from zipfile import ZipFile

    with ZipFile(io.BytesIO(content)) as archive:
        xml_content = archive.read("content.xml")

    root = ElementTree.fromstring(xml_content)
    paragraphs: list[str] = []
    for element in root.iter():
        if element.tag.endswith("}p") or element.tag.endswith("}h"):
            text = re.sub(r"\s+", " ", "".join(element.itertext())).strip()
            if text:
                paragraphs.append(text)
    return "\n".join(paragraphs)


def _excerpt(text: str, length: int = 6000) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    normalized = "\n".join(line for line in lines if line)
    if not normalized:
        normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[:length]


def _infer_kind(file_name: str) -> ProfileAssetKind:
    lowered = file_name.lower()
    if "reference" in lowered or "recommend" in lowered:
        return ProfileAssetKind.reference_letter
    if "motivation" in lowered or "cover" in lowered or "letter" in lowered:
        return ProfileAssetKind.motivation_letter
    if "application" in lowered:
        return ProfileAssetKind.previous_application
    if "cv" in lowered or "resume" in lowered:
        return ProfileAssetKind.cv
    return ProfileAssetKind.other


def _append_sample(existing: list[str], sample: str, limit: int = 5) -> list[str]:
    combined = [item for item in existing if item != sample]
    combined.insert(0, sample)
    return combined[:limit]


def _enrich_profile_from_text(profile: CandidateProfile, text: str, file_name: str) -> CandidateProfile:
    lowered = text.lower()
    existing_skills = {skill.name.lower(): skill for skill in profile.skills}
    updated_skills = list(profile.skills)

    for raw_skill in KNOWN_SKILLS:
        if raw_skill not in lowered or raw_skill in existing_skills:
            continue
        updated_skills.append(
            CandidateSkill(
                name=_display_skill(raw_skill),
                years=0,
                evidence=_skill_evidence(text, raw_skill) or f"Mentioned in uploaded profile asset {file_name}",
            )
        )

    languages = list(profile.languages)
    for language in ("English", "German", "French"):
        if language.lower() in lowered and language not in languages:
            languages.append(language)

    achievements = list(profile.achievements)
    highlights = re.findall(r"(reduced .*?|built .*?|delivered .*?|led .*?)(?:\.|\n)", text, flags=re.IGNORECASE)
    for highlight in highlights[:4]:
        normalized = highlight.strip().capitalize()
        if normalized and normalized not in achievements:
            achievements.append(normalized)

    return profile.model_copy(
        update={
            "skills": updated_skills,
            "languages": languages,
            "achievements": achievements[:12],
        }
    )


def _skill_evidence(text: str, raw_skill: str) -> str:
    pattern = re.compile(re.escape(raw_skill), flags=re.IGNORECASE)
    for line in _evidence_lines(text):
        if pattern.search(line):
            return line[:220]
    return ""


def _evidence_lines(text: str) -> list[str]:
    candidates: list[str] = []
    for raw_line in re.split(r"[\n\r]+|(?<=[.!?])\s+", text):
        line = re.sub(r"\s+", " ", raw_line).strip(" -\u2022\t")
        if len(line) < 20:
            continue
        if any(
            marker in line.lower()
            for marker in (
                "develop",
                "build",
                "operate",
                "designed",
                "delivered",
                "maintained",
                "technical skills",
                "cloud",
                "data",
                "backend",
                "production",
                "automation",
            )
        ):
            candidates.append(line)
    return candidates


def _merge_profiles(primary: CandidateProfile, fallback: CandidateProfile) -> CandidateProfile:
    merged_skills: dict[str, CandidateSkill] = {skill.name.lower(): skill for skill in fallback.skills}
    for skill in primary.skills:
        merged_skills[skill.name.lower()] = skill

    merged_achievements = list(dict.fromkeys(primary.achievements + fallback.achievements))
    merged_languages = list(dict.fromkeys(primary.languages + fallback.languages))
    merged_locations = list(dict.fromkeys(primary.preferred_locations + fallback.preferred_locations))
    merged_education = list(dict.fromkeys(primary.education + fallback.education))

    return primary.model_copy(
        update={
            "profile_id": primary.profile_id or fallback.profile_id,
            "display_name": primary.display_name or fallback.display_name,
            "headline": primary.headline or fallback.headline,
            "work_authorization": primary.work_authorization or fallback.work_authorization,
            "preferred_locations": merged_locations,
            "salary_floor": primary.salary_floor or fallback.salary_floor,
            "languages": merged_languages,
            "education": merged_education,
            "experience_summary": primary.experience_summary or fallback.experience_summary,
            "skills": list(merged_skills.values()),
            "achievements": merged_achievements[:12],
        }
    )


def _display_skill(skill: str) -> str:
    mapping = {
        "c#": "C#",
        ".net": ".NET",
        "asp.net core": "ASP.NET Core",
        "sql": "SQL",
        "ci/cd": "CI/CD",
        "wpf": "WPF",
        "akka.net": "Akka.NET",
        "fastapi": "FastAPI",
        "llmops": "LLMOps",
        "rest api": "REST APIs",
        "graphql": "GraphQL",
        "vue.js": "Vue.js",
        "github copilot": "GitHub Copilot",
        "ai agents": "AI agents",
        "ai tools": "AI tools",
        "crm": "CRM",
        "erp": "ERP",
        "etl": "ETL",
        "elt": "ELT",
        "microsoft graph": "Microsoft Graph",
        "gmail api": "Gmail API",
    }
    return mapping.get(skill, skill.title())
