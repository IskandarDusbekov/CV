import json
import time
from decimal import Decimal

from django.conf import settings
from openai import OpenAI

_client = None


def get_client():
    # Kalit yo'q bo'lsa ham sayt ishga tushishi uchun klient faqat birinchi AI so'rovida yaratiladi
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY or None)
    return _client

DEFAULT_TEMPLATE  = "ats_modern"

# ── Section header labels per language ────────────────────────────────────────
SECTION_LABELS = {
    "uz": {
        "contact":         "Kontakt",
        "education":       "Ta'lim",
        "skills":          "Ko'nikmalar",
        "languages":       "Tillar",
        "profiles":        "Profillar",
        "profile_summary": "Profil",
        "experience":      "Ish tajribasi",
        "projects":        "Loyihalar",
        "about":           "Haqida",
        "position":        "Lavozim",
        "company":         "Kompaniya",
        "project":         "Loyiha",
    },
    "ru": {
        "contact":         "Контакты",
        "education":       "Образование",
        "skills":          "Навыки",
        "languages":       "Языки",
        "profiles":        "Профили",
        "profile_summary": "Профиль",
        "experience":      "Опыт работы",
        "projects":        "Проекты",
        "about":           "О себе",
        "position":        "Должность",
        "company":         "Компания",
        "project":         "Проект",
    },
    "en": {
        "contact":         "Contact",
        "education":       "Education",
        "skills":          "Skills",
        "languages":       "Languages",
        "profiles":        "Profiles",
        "profile_summary": "Profile",
        "experience":      "Work Experience",
        "projects":        "Projects",
        "about":           "About",
        "position":        "Position",
        "company":         "Company",
        "project":         "Project",
    },
}
TEMPLATE_ALIASES = {
    "free_classic": "classic",
    "premium_modern": "modern",
}

# Tartib — sahifalarda shu ketma-ketlikda ko'rsatiladi.
# ats=True — bir ustunli, jadvalsiz, standart sarlavhali: rezyume skanerlovchi tizimlar (ATS) to'g'ri o'qiydi.
TEMPLATE_META = {
    "ats_modern": {
        "label": "ATS Zamonaviy",
        "ats": True,
        "tagline": "Bir ustun, aniq sarlavhalar — HR tizimlaridan xatosiz o'tadi",
    },
    "ats": {
        "label": "ATS Standart",
        "ats": True,
        "tagline": "Eng xavfsiz format: yirik kompaniyalar va xalqaro vakansiyalar uchun",
    },
    "classic": {
        "label": "Klassik",
        "ats": False,
        "tagline": "To'q ko'k yon panel, universal va ishonchli",
    },
    "modern": {
        "label": "Zamonaviy",
        "ats": False,
        "tagline": "Toza sarlavha, firuza aksent, IT va startaplar uchun",
    },
    "minimal": {
        "label": "Minimal",
        "ats": True,
        "tagline": "Shveytsariya uslubi, ko'p havo, faqat mazmun",
    },
    "executive": {
        "label": "Executive",
        "ats": True,
        "tagline": "Serif shrift va oltin chiziqlar, rahbarlar uchun",
    },
    "creative": {
        "label": "Kreativ",
        "ats": False,
        "tagline": "Gradient sarlavha, dizayner va marketologlar uchun",
    },
    "dark": {
        "label": "Dark",
        "ats": False,
        "tagline": "Qora fon va amber aksent, dasturchilar uchun",
    },
    "elegant": {
        "label": "Elegant",
        "ats": False,
        "tagline": "Iliq krem ranglar va nafis serif sarlavhalar",
    },
    "simple": {
        "label": "Oddiy",
        "ats": True,
        "tagline": "Tushunarli va tartibli — sotuv, xizmat va ishchi kasblar uchun",
    },
    "teal": {
        "label": "Yashil panel",
        "ats": False,
        "tagline": "Yashil yon panel va ko'nikma chiziqlari, zamonaviy ko'rinish",
    },
    "bold": {
        "label": "Yorqin",
        "ats": False,
        "tagline": "To'q ko'k sarlavha va apelsin aksent — esda qoladigan dizayn",
    },
}
SUPPORTED_TEMPLATES = set(TEMPLATE_META)

# Panelda o'zgartirilmagan bo'lsa shu shablonlar Pro hisoblanadi
DEFAULT_PRO_TEMPLATES = {"modern", "executive", "creative", "dark", "elegant", "teal", "bold"}


def template_settings():
    """Paneldagi «Shablonlar» sozlamalari (Bepul/Pro, tartib, ko'rinish) — 60 soniya keshda."""
    from django.core.cache import cache

    data = cache.get("template_settings")
    if data is None:
        try:
            from .models import TemplateSetting

            data = {t.code: (t.is_pro, t.is_active, t.sort_order) for t in TemplateSetting.objects.all()}
        except Exception:  # migratsiyadan oldin
            data = {}
        cache.set("template_settings", data, 60)
    return data


def template_is_pro(code):
    code = resolve_template_name(code)
    setting = template_settings().get(code)
    return setting[0] if setting else code in DEFAULT_PRO_TEMPLATES


def ordered_templates(include_hidden=False):
    settings_map = template_settings()
    order = list(TEMPLATE_META)
    codes = [c for c in order if include_hidden or settings_map.get(c, (None, True, 0))[1]]
    return sorted(codes, key=lambda c: (settings_map.get(c, (None, True, order.index(c)))[2], order.index(c)))


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _clean_list(values):
    if not isinstance(values, list):
        return []
    return [_clean_text(item) for item in values if _clean_text(item)]


def _clean_languages(values):
    """Handle both plain strings and dict objects like {'language': 'русский', 'level': 'родной'}."""
    if not isinstance(values, list):
        return []
    result = []
    for item in values:
        if isinstance(item, str):
            text = item.strip()
            if text:
                result.append(text)
        elif isinstance(item, dict):
            lang = _clean_text(
                item.get("language") or item.get("name") or
                item.get("lang") or item.get("language_name") or ""
            )
            level = _clean_text(
                item.get("level") or item.get("proficiency") or
                item.get("language_level") or ""
            )
            if lang:
                result.append(f"{lang} ({level})" if level else lang)
    return result


def _clean_experience(items):
    if not isinstance(items, list):
        return []

    experience = []
    for item in items:
        if not isinstance(item, dict):
            continue

        position = _clean_text(item.get("position"))
        company = _clean_text(item.get("company"))
        duration = _clean_text(item.get("duration"))
        responsibilities = _clean_list(item.get("responsibilities"))

        if position or company or duration or responsibilities:
            experience.append(
                {
                    "position": position,
                    "company": company,
                    "duration": duration,
                    "responsibilities": responsibilities,
                }
            )

    return experience


def _clean_education(items):
    if not isinstance(items, list):
        return []

    education = []
    for item in items:
        if not isinstance(item, dict):
            continue

        institution = _clean_text(item.get("institution"))
        degree = _clean_text(item.get("degree"))
        year = _clean_text(item.get("year"))

        if institution or degree or year:
            education.append(
                {
                    "institution": institution,
                    "degree": degree,
                    "year": year,
                }
            )

    return education


def _clean_projects(items):
    if not isinstance(items, list):
        return []

    projects = []
    for item in items:
        if not isinstance(item, dict):
            continue

        title = _clean_text(item.get("title"))
        description = _clean_text(item.get("description"))
        technologies = _clean_list(item.get("technologies"))

        if title or description or technologies:
            projects.append(
                {
                    "title": title,
                    "description": description,
                    "technologies": technologies,
                }
            )

    return projects


def normalize_cv_data(cv_json):
    data = cv_json if isinstance(cv_json, dict) else {}

    # Extract stored language code (injected by generate_cv_from_text)
    lang_code = _clean_text(data.get("_language", "uz")) or "uz"
    if lang_code not in SECTION_LABELS:
        lang_code = "uz"

    normalized = {
        "full_name": _clean_text(data.get("full_name")) or "Your Name",
        "job_title": _clean_text(data.get("job_title")) or "Professional Title",
        "email": _clean_text(data.get("email")),
        "phone": _clean_text(data.get("phone")),
        "location": _clean_text(data.get("location")),
        "github": _clean_text(data.get("github")),
        "linkedin": _clean_text(data.get("linkedin")),
        "summary": _clean_text(data.get("summary")),
        "skills": _clean_list(data.get("skills")),
        "languages": _clean_languages(data.get("languages")),  # handles dict/str
        "experience": _clean_experience(data.get("experience")),
        "education": _clean_education(data.get("education")),
        "projects": _clean_projects(data.get("projects")),
        "cv_language": lang_code,
        "labels": SECTION_LABELS[lang_code],
    }

    normalized["contact_items"] = [
        item
        for item in [
            {"label": "Email", "value": normalized["email"], "href": f"mailto:{normalized['email']}" if normalized["email"] else ""},
            {"label": "Phone", "value": normalized["phone"], "href": f"tel:{normalized['phone']}" if normalized["phone"] else ""},
            {"label": "Location", "value": normalized["location"], "href": ""},
        ]
        if item["value"]
    ]

    normalized["profile_links"] = [
        item
        for item in [
            {"label": "GitHub", "value": normalized["github"], "href": normalized["github"]},
            {"label": "LinkedIn", "value": normalized["linkedin"], "href": normalized["linkedin"]},
        ]
        if item["value"]
    ]

    normalized["skills_summary"] = ", ".join(normalized["skills"][:8])
    normalized["photo_url"] = ""   # filled in by build_cv_context from model field
    return normalized


def resolve_template_name(selected_template):
    resolved = TEMPLATE_ALIASES.get(selected_template, selected_template)
    if resolved in SUPPORTED_TEMPLATES:
        return resolved
    return DEFAULT_TEMPLATE


# ── Kirish huquqlari ──────────────────────────────────────────────────────────
#
# Monetizatsiya modeli (limit raqamlari: SiteSettings, PricingPlan.max_* va TemplateSetting):
#   Bepul     — AI bilan 2 ta CV, 1 ta moslashtirish, namunalardan cheksiz CV, barcha shablonlarda ko'rish.
#               Har bir foydalanuvchiga free_pdf_downloads ta PDF — faqat bepul shablonda, bitta rezyumega. Word yo'q.
#   Kredit    — shu CV (va uning moslashtirilgan nusxalari) ochiladi: barcha shablonlar, PDF + Word, 5 ta moslashtirish, umrbod
#   Pro       — davr ichida 30 ta CV, 50 ta moslashtirish, hamma CV ochiq, brending

def user_has_pro(user):
    if not getattr(user, "is_authenticated", False):
        return False
    profile = getattr(user, "profile", None)
    return bool(profile and profile.has_active_premium)


def cv_is_unlocked(cv, user):
    if cv is not None:
        if getattr(cv, "is_unlocked", False):
            return True
        # Ochilgan CV dan yaratilgan moslashtirilgan nusxa ham ochiq
        if getattr(cv, "parent_id", None) and cv.parent.is_unlocked:
            return True
    return user_has_pro(user)


PDF_FULL = "full"                  # kredit yoki Pro bilan ochilgan
PDF_FREE = "free"                  # bepul PDF shu rezyumega ishlatilgan
PDF_FREE_AVAILABLE = "free_available"
PDF_PRO_TEMPLATE = "pro_template"  # Pro shablon — bepul PDF unga tegishli emas
PDF_NO_FREE = "no_free"            # bepul PDF boshqa rezyumega ishlatilgan
PDF_LOGIN = "login"


def free_pdf_left(user):
    if not getattr(user, "is_authenticated", False):
        return 0
    from apps.core.models import SiteSettings

    profile = getattr(user, "profile", None)
    return max(0, SiteSettings.load().free_pdf_downloads - (profile.free_pdf_used if profile else 0))


def pdf_access(user, cv):
    if not getattr(user, "is_authenticated", False):
        return PDF_LOGIN
    if cv_is_unlocked(cv, user) or getattr(user, "is_staff", False):  # adminlar tekshirish uchun hammasini yuklaydi
        return PDF_FULL
    if template_is_pro(getattr(cv, "selected_template", "")):
        return PDF_PRO_TEMPLATE
    if getattr(cv, "free_pdf", False):
        return PDF_FREE
    return PDF_FREE_AVAILABLE if free_pdf_left(user) > 0 else PDF_NO_FREE


def user_can_download_pdf(user, cv):
    return pdf_access(user, cv) in (PDF_FULL, PDF_FREE)


def claim_pdf_access(user, cv):
    """PDF yuklashga ruxsat. Kerak bo'lsa foydalanuvchining bepul PDF'ini shu rezyumega ishlatadi (atomar)."""
    from django.db.models import F

    from apps.core.models import SiteSettings
    from apps.users.models import UserProfile

    state = pdf_access(user, cv)
    if state in (PDF_FULL, PDF_FREE):
        return True
    if state != PDF_FREE_AVAILABLE:
        return False
    limit = SiteSettings.load().free_pdf_downloads
    claimed = UserProfile.objects.filter(user=user, free_pdf_used__lt=limit).update(free_pdf_used=F("free_pdf_used") + 1)
    if not claimed:
        return False
    cv.free_pdf = True
    cv.save(update_fields=["free_pdf", "updated_at"])
    user.profile.free_pdf_used += 1
    return True


def user_can_download_docx(user, cv):
    return getattr(user, "is_authenticated", False) and (cv_is_unlocked(cv, user) or getattr(user, "is_staff", False))


def user_can_share_cv(user, cv=None):
    return getattr(user, "is_authenticated", False) and cv_is_unlocked(cv, user)


def template_choices(selected_template=None):
    codes = ordered_templates()
    if selected_template in TEMPLATE_META and selected_template not in codes:
        codes.append(selected_template)
    return [
        {
            "code": code,
            "label": TEMPLATE_META[code]["label"],
            "tagline": TEMPLATE_META[code]["tagline"],
            "ats": TEMPLATE_META[code]["ats"],
            "pro": template_is_pro(code),
            "selected": code == selected_template,
        }
        for code in codes
    ]


def build_cv_context(cv, user=None):
    template_key = resolve_template_name(getattr(cv, "selected_template", ""))
    normalized = normalize_cv_data(getattr(cv, "cv_json", {}))

    if cv and getattr(cv, "photo", None):
        try:
            normalized["photo_url"] = cv.photo.url
        except Exception:
            normalized["photo_url"] = ""

    from apps.core.models import SiteSettings

    unlocked = cv_is_unlocked(cv, user)
    is_pro = user_has_pro(user)
    free_pdf = bool(getattr(cv, "free_pdf", False))
    return {
        "cv": cv,
        "cv_data": normalized,
        "is_pro": is_pro,
        "is_unlocked": unlocked,
        "show_watermark": not unlocked and (SiteSettings.load().free_pdf_watermark or not free_pdf),
        "pdf_access": pdf_access(user, cv),
        "free_pdf_left": free_pdf_left(user),
        "template_is_pro": template_is_pro(template_key),
        "company_branding": None,
        "template_key": template_key,
        "template_partial": f"cv/partials/cv_template_{template_key}.html",
        "template_label": TEMPLATE_META[template_key]["label"],
        "template_is_ats": TEMPLATE_META[template_key]["ats"],
        "template_choices": template_choices(template_key),
        "can_download_pdf": user_can_download_pdf(user, cv),
        "can_download_docx": user_can_download_docx(user, cv),
        "share_available": user_can_share_cv(user, cv),
    }


DEMO_CV_JSON = {
    "full_name": "Sardor Nazarov",
    "job_title": "Senior Python Backend Developer",
    "email": "sardor.nazarov@gmail.com",
    "phone": "+998 90 123 45 67",
    "location": "Toshkent, O'zbekiston",
    "github": "github.com/sardor-dev",
    "linkedin": "linkedin.com/in/sardor",
    "summary": "6 yillik tajribaga ega backend muhandis. Yuqori yuklamali to'lov va e-commerce tizimlarini loyihalash, "
               "REST API va mikroservislar qurish bo'yicha mutaxassis. Jamoani boshqarish va kod sifatini oshirishni yaxshi ko'raman.",
    "skills": ["Python", "Django", "FastAPI", "PostgreSQL", "Redis", "Docker", "Celery", "AWS", "CI/CD"],
    "languages": ["O'zbek (ona tili)", "Rus (C1)", "Ingliz (B2)"],
    "experience": [
        {
            "position": "Senior Backend Developer",
            "company": "Uzum Market",
            "duration": "2022 — hozir",
            "responsibilities": [
                "Kuniga 2 mln+ so'rovga xizmat qiluvchi buyurtmalar servisini qayta loyihaladim",
                "API javob vaqtini Redis kesh orqali 40% ga qisqartirdim",
                "4 kishilik backend jamoaga mentorlik qildim, code review jarayonini joriy etdim",
            ],
        },
        {
            "position": "Python Developer",
            "company": "Click",
            "duration": "2019 — 2022",
            "responsibilities": [
                "To'lov shlyuzi uchun Django REST Framework asosida 30+ endpoint yozdim",
                "Celery bilan fon vazifalari tizimini yaratib, hisobotlarni avtomatlashtirdim",
            ],
        },
    ],
    "education": [
        {"institution": "TATU", "degree": "Dasturiy injiniring, bakalavr", "year": "2015 — 2019"},
    ],
    "projects": [
        {
            "title": "tezrezyume.uz — AI rezyume yaratuvchi",
            "description": "Matndan professional rezyume yaratuvchi platforma, 12 ta shablon va PDF/Word eksport.",
            "technologies": ["Django", "OpenAI", "Playwright"],
        },
        {
            "title": "PayFlow",
            "description": "Click va Payme integratsiyali ochiq manbali to'lov kutubxonasi.",
            "technologies": ["FastAPI", "Redis"],
        },
    ],
}


def demo_template_context(code):
    """Demo ma'lumotlar bilan shablonni ko'rsatish uchun kontekst."""
    code = resolve_template_name(code)
    return {
        "cv_data": normalize_cv_data(DEMO_CV_JSON),
        "show_watermark": False,
        "company_branding": None,
        "template_key": code,
        "template_partial": f"cv/partials/cv_template_{code}.html",
        "template_label": TEMPLATE_META[code]["label"],
    }


LANGUAGE_MAP = {
    "uz": "Uzbek (Latin script)",
    "ru": "Russian",
    "en": "English",
}


ATS_RULES = """ATS (applicant tracking system) rules — the CV must parse cleanly:
- Plain text only: no emojis, no decorative symbols, no markdown, no tables
- One clear job title; each experience has position, company and duration
- duration: copy exactly what the user gave. Use "YYYY — YYYY" only if the user stated the years. If only a length is known
  write it as a length ("2 yil", "3 года", "2 years"); if the job is current add "hozir/настоящее время/present". NEVER calculate or guess years.
- Bullets start with a strong action verb and show impact; use numbers only if the user gave them
- skills: short standard keyword names (e.g. "PostgreSQL", "Meta Ads", "1C: Buxgalteriya"), max 15, most relevant first
- Spell out tools and certifications exactly as recruiters search for them"""


class AIError(Exception):
    """AI chaqiruvi muvaffaqiyatsiz — meta da sarflangan vaqt/model saqlanadi."""

    def __init__(self, message, meta):
        super().__init__(message)
        self.meta = meta


def _chat_json(system, prompt, temperature=0.3):
    """OpenAI ga JSON so'rov. Qaytaradi: (data, meta) — meta da model, tokenlar, narx ($) va vaqt."""
    from apps.core.models import SiteSettings

    site = SiteSettings.load()
    meta = {"model": site.ai_model, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": Decimal("0"), "duration_ms": 0}
    started = time.monotonic()
    try:
        response = get_client().chat.completions.create(
            model=site.ai_model,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=temperature,
        )
        usage = getattr(response, "usage", None)
        meta["prompt_tokens"] = getattr(usage, "prompt_tokens", 0) or 0
        meta["completion_tokens"] = getattr(usage, "completion_tokens", 0) or 0
        meta["cost_usd"] = (
            Decimal(meta["prompt_tokens"]) * site.ai_price_input_per_1m
            + Decimal(meta["completion_tokens"]) * site.ai_price_output_per_1m
        ) / Decimal(1_000_000)
        meta["duration_ms"] = int((time.monotonic() - started) * 1000)
        return json.loads(response.choices[0].message.content), meta
    except Exception as exc:
        meta["duration_ms"] = int((time.monotonic() - started) * 1000)
        raise AIError(str(exc), meta) from exc


def _language_instruction(language):
    if language in LANGUAGE_MAP:
        return f"Write all CV text in {LANGUAGE_MAP[language]}."
    return "Write all CV text in the same language the user wrote in (Uzbek Latin, Russian or English)."


def _detect_language(text):
    cyr = sum(1 for ch in text if "а" <= ch.lower() <= "я" or ch in "ёўқғҳ")
    if cyr > len(text) * 0.25:
        return "ru"
    lowered = text.lower()
    uz_markers = ("man ", "ishla", "bilan", "yil", "o'", "g'", "ta'lim", "bo'l", "qil")
    if sum(m in lowered for m in uz_markers) >= 2:
        return "uz"
    return "en"


def generate_cv_from_text(user_text, target_job="", language="auto", enrich=False):
    """Erkin, tartibsiz matndan tayyor CV JSON.

    Foydalanuvchilar odatda kam va chalkash yozadi — shuning uchun standart rejim matnni o'zi
    tartiblaydi va professional qilib qayta yozadi, lekin fakt o'ylab topmaydi.
    """
    if language not in LANGUAGE_MAP:
        language = _detect_language(user_text)

    mode = (
        """ENRICH MODE: the user asked you to expand. You may add 2-4 realistic bullets per role and
typical skills for the stated profession, but never invent employers, dates, degrees or numbers."""
        if enrich else
        """POLISH MODE: use only facts from the user text. Rewrite them professionally: split run-on
sentences into bullets, fix grammar, turn "I did X" into achievement-style bullets. Do not invent facts."""
    )

    prompt = f"""The user wrote messy free-form text about themselves (it may be short, unordered, with typos,
mixed languages or chat style). Turn it into a structured, professional CV.

{_language_instruction(language)} Company names, tool names and proper nouns keep their original form.
{mode}
{ATS_RULES}
- summary: 2-3 sentences that sell the candidate for the target role (write it even if the user did not).
  Resume style: no "I/men/я", no third person ("u ... ishlaydi", "faoliyat yuritmoqda"); start with the role and years of experience.
- job_title: from target job, or inferred from the most recent experience
- If a field is missing, use "" or []. Do not output placeholder text.
- Order experience from newest to oldest.

Target job: {target_job or "not specified"}

User text:
\"\"\"{user_text}\"\"\"

Return ONLY JSON with exactly this structure:
{{
  "full_name": "",
  "job_title": "",
  "email": "",
  "phone": "",
  "location": "",
  "github": "",
  "linkedin": "",
  "summary": "",
  "skills": [],
  "languages": [],
  "experience": [
    {{
      "position": "",
      "company": "",
      "duration": "",
      "responsibilities": []
    }}
  ],
  "education": [
    {{
      "institution": "",
      "degree": "",
      "year": ""
    }}
  ],
  "projects": [
    {{
      "title": "",
      "description": "",
      "technologies": []
    }}
  ]
}}"""

    result, meta = _chat_json(
        "You are an expert multilingual CV writer and recruiter. Always return valid JSON only.",
        prompt,
        temperature=0.45 if enrich else 0.25,
    )
    # Bo'lim sarlavhalarini tilga moslash uchun
    result["_language"] = language
    return result, meta


def tailor_cv_to_job(cv_json, job_description):
    """CV ni aniq bir vakansiya e'loniga moslab qayta yozadi.

    Qaytaradi: (yangi_cv_json, hisobot). Hisobotda moslik bali (oldin/keyin), mos va yetishmayotgan
    kalit so'zlar hamda nimalar o'zgargani bor. Tajriba, kompaniya, sana va ta'lim o'ylab topilmaydi.
    """
    language = cv_json.get("_language") if isinstance(cv_json, dict) else None
    source = {k: v for k, v in (cv_json or {}).items() if not k.startswith("_")}

    prompt = f"""You are a senior recruiter. Tailor the candidate's CV to the job posting below so it passes ATS
keyword screening and convinces the hiring manager.

{_language_instruction(language)}
Rules (truthfulness is the top priority — a recruiter will interview the candidate on every line):
- NEVER invent employers, positions, dates, degrees, certificates or metrics that are not in the CV
- NEVER add a responsibility, achievement or skill the CV does not already show. If the posting asks for something the
  CV does not show (e.g. team management, a tool, a budget size), put it in missing_keywords and leave the CV without it.
  Example: posting wants "TikTok Ads", CV only has "Meta Ads" → keep "Meta Ads", add "TikTok Ads" to missing_keywords.
- matched_keywords may only contain terms the ORIGINAL CV already proves
- job_title: align with the posting's title if the candidate's experience supports it
- summary: rewrite in 2-3 sentences aimed at THIS role, using the posting's key terms naturally
- experience: keep every role; rewrite and reorder bullets so the most relevant to the posting come first;
  mirror the posting's wording where it truthfully describes what the candidate did
- skills: put skills required by the posting that the candidate evidently has first; you may add a skill
  only if the CV clearly shows it (e.g. a tool used in a project); remove clearly irrelevant ones
- projects/education/languages/contacts: keep, lightly reorder or reword for relevance
{ATS_RULES}

Also produce a report:
- match_before / match_after: integer 0-100 estimate of how well the CV matches the posting
- matched_keywords: up to 12 posting keywords now present in the CV
- missing_keywords: up to 8 important posting requirements the candidate does NOT show — do not add them to the CV
- changes: 3-5 short sentences describing what you changed (in the CV language)
- vacancy_title: the job title from the posting; company: company name if stated, else ""

CV JSON:
{json.dumps(source, ensure_ascii=False)}

Job posting:
\"\"\"{job_description}\"\"\"

Return ONLY JSON: {{"cv": <same structure as the input CV JSON>, "report": {{"match_before": 0, "match_after": 0,
"matched_keywords": [], "missing_keywords": [], "changes": [], "vacancy_title": "", "company": ""}}}}"""

    data, meta = _chat_json("You are an expert recruiter and ATS optimization specialist. You never fabricate experience. Always return valid JSON only.", prompt, 0.2)
    new_cv = data.get("cv") if isinstance(data.get("cv"), dict) else {}
    if not new_cv.get("full_name"):
        raise AIError("AI moslashtirilgan CV qaytarmadi", meta)
    if language:
        new_cv["_language"] = language

    raw = data.get("report") if isinstance(data.get("report"), dict) else {}

    # Himoya: asl CV da umuman uchramaydigan ko'nikma qo'shilgan bo'lsa — olib tashlab, "yetishmayotgan" ga o'tkazamiz
    source_text = json.dumps(source, ensure_ascii=False).lower()
    invented = [s for s in _clean_list(new_cv.get("skills")) if s.lower() not in source_text]
    if invented:
        new_cv["skills"] = [s for s in _clean_list(new_cv.get("skills")) if s not in invented]
        raw["missing_keywords"] = _clean_list(raw.get("missing_keywords")) + invented
    raw["matched_keywords"] = [k for k in _clean_list(raw.get("matched_keywords")) if k.lower() in source_text]

    def _score(value):
        try:
            return max(0, min(100, int(value)))
        except (TypeError, ValueError):
            return None

    report = {
        "match_before": _score(raw.get("match_before")),
        "match_after": _score(raw.get("match_after")),
        "matched_keywords": _clean_list(raw.get("matched_keywords"))[:12],
        "missing_keywords": _clean_list(raw.get("missing_keywords"))[:8],
        "changes": _clean_list(raw.get("changes"))[:5],
        "vacancy_title": _clean_text(raw.get("vacancy_title")),
        "company": _clean_text(raw.get("company")),
    }
    return new_cv, report, meta
