"""Tashriflar statistikasi: kim keldi (odam / bot / skaner), qayerdan, nima qildi va qayerda to'xtadi.

Qanday aniqlanadi:
  * skaner — zaifliklarni qidiradigan so'rovlar (/.env, /wp-admin, .php ...) yoki sqlmap, nuclei kabi dasturlar;
  * bot    — qidiruv tizimlari, link preview (TelegramBot), monitoring, curl/python kabi dasturlar;
  * odam   — sahifada JavaScript ishladi va brauzer avtomatlashtirilmagan (navigator.webdriver yo'q);
  * aniqlanmagan — brauzerga o'xshaydi, lekin JS ishlamadi (juda tez chiqib ketgan yoki yashirin bot).
"""
import hashlib
import logging
import re
import uuid
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, F, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .activity import client_ip

logger = logging.getLogger(__name__)

COOKIE = "tv"
COOKIE_AGE = 180 * 24 * 3600
SAME_VISITOR_WINDOW = timedelta(minutes=30)

SCANNER_PATH_RE = re.compile(
    r"(\.env\b|/\.git|/\.svn|/\.aws|/\.ssh|wp-(admin|login|content|includes|config)|wordpress|xmlrpc|phpmyadmin|/pma\b|"
    r"\.php\b|\.asp|\.jsp|cgi-bin|/vendor/|/actuator|/solr|/boaform|/hnap1|/owa/|/autodiscover|/server-status|"
    r"\.(sql|bak|old|swp|zip|tar|gz|7z|rar)$|/etc/passwd|/shell|/console|/jenkins|/manager/html|/telescope|/debug/|"
    r"/api/v\d+/(users|config)|/\.well-known/(?!acme)|/config\.(json|yml|yaml|js)|/backup|/database|/_profiler)",
    re.I,
)
SCANNER_UA_RE = re.compile(
    r"(sqlmap|nikto|nmap|masscan|zgrab|nuclei|dirbuster|gobuster|ffuf|feroxbuster|wpscan|acunetix|nessus|openvas|"
    r"censys|shodan|expanse|l9explore|l9tcpid|internet-measurement|fuzz|scanner|zmap|netsystemsresearch|odin|leakix)",
    re.I,
)
BOT_NAMES = [
    ("googlebot", "Google"), ("google-inspectiontool", "Google"), ("adsbot-google", "Google Ads"), ("bingbot", "Bing"),
    ("yandex", "Yandex"), ("duckduckbot", "DuckDuckGo"), ("baiduspider", "Baidu"), ("applebot", "Apple"),
    ("telegrambot", "Telegram (havola ko'rinishi)"), ("facebookexternalhit", "Facebook"), ("meta-externalagent", "Meta AI"),
    ("twitterbot", "Twitter/X"), ("whatsapp", "WhatsApp"), ("linkedinbot", "LinkedIn"), ("slackbot", "Slack"),
    ("discordbot", "Discord"), ("vkshare", "VK"), ("skypeuripreview", "Skype"),
    ("ahrefsbot", "Ahrefs"), ("semrushbot", "Semrush"), ("mj12bot", "Majestic"), ("dotbot", "Moz"), ("petalbot", "Petal"),
    ("bytespider", "ByteDance"), ("gptbot", "OpenAI"), ("chatgpt-user", "ChatGPT"), ("oai-searchbot", "OpenAI"),
    ("claudebot", "Anthropic"), ("claude-web", "Anthropic"), ("perplexitybot", "Perplexity"), ("ccbot", "Common Crawl"),
    ("amazonbot", "Amazon"), ("uptimerobot", "UptimeRobot"), ("betteruptime", "BetterStack"), ("pingdom", "Pingdom"),
    ("headlesschrome", "Headless Chrome"), ("phantomjs", "PhantomJS"), ("lighthouse", "Lighthouse"),
    ("python-requests", "Python"), ("python-urllib", "Python"), ("aiohttp", "Python"), ("httpx", "Python"),
    ("curl/", "curl"), ("wget", "wget"), ("go-http-client", "Go"), ("okhttp", "OkHttp"), ("java/", "Java"),
    ("libwww", "Perl"), ("scrapy", "Scrapy"), ("node-fetch", "Node.js"), ("axios", "Node.js"),
]
GENERIC_BOT_RE = re.compile(r"(bot\b|bot/|crawl|spider|slurp|preview|monitor|checker|fetcher|http-client)", re.I)

SKIP_PREFIXES = ("/static/", "/media/", "/panel/", "/t/", "/healthz", "/favicon", "/cv/dl/", "/apple-touch-icon")

STEP_FIELDS = {"builder": "did_builder", "generate": "did_generate", "login": "did_login",
               "unlock": "did_unlock", "download": "did_download"}


# ─── Aniqlash ─────────────────────────────────────────────────────────────────

def classify(user_agent: str, path: str = ""):
    """(kind, bot_name) qaytaradi. Odamni faqat JS ping tasdiqlaydi, shuning uchun bu yerda 'unknown'."""
    from .models import Visitor

    ua = (user_agent or "").lower()
    if SCANNER_UA_RE.search(ua) or (path and SCANNER_PATH_RE.search(path)):
        return Visitor.KIND_SCANNER, ""
    if not ua.strip():
        return Visitor.KIND_BOT, "User-Agent yo'q"
    for needle, name in BOT_NAMES:
        if needle in ua:
            return Visitor.KIND_BOT, name
    if GENERIC_BOT_RE.search(ua) or "mozilla" not in ua:
        return Visitor.KIND_BOT, "Boshqa bot"
    return Visitor.KIND_UNKNOWN, ""


def parse_device(user_agent: str):
    ua = (user_agent or "").lower()
    device = "tablet" if re.search(r"ipad|tablet|kindle|silk", ua) else "mobile" if re.search(r"mobi|iphone|android", ua) else "desktop"
    os_name = ("Android" if "android" in ua else "iOS" if re.search(r"iphone|ipad|ipod", ua) else "Windows" if "windows" in ua
               else "macOS" if "mac os x" in ua else "Linux" if "linux" in ua else "")
    browser = next((name for needle, name in (
        ("yabrowser", "Yandex"), ("edg/", "Edge"), ("opr/", "Opera"), ("opera", "Opera"), ("samsungbrowser", "Samsung"),
        ("telegram", "Telegram"), ("instagram", "Instagram"), ("fban", "Facebook"), ("fbav", "Facebook"),
        ("chrome/", "Chrome"), ("crios", "Chrome"), ("firefox", "Firefox"), ("fxios", "Firefox"), ("safari", "Safari"),
    ) if needle in ua), "")
    return device, os_name, browser


def detect_source(request):
    utm = request.GET.get("utm_source", "").strip().lower()[:40]
    if utm:
        return utm, ""
    ref = request.META.get("HTTP_REFERER", "")[:300]
    host = (urlparse(ref).hostname or "").lower()
    if not host or host == request.get_host().split(":")[0]:
        return "direct", ""
    for needle, name in (("t.me", "telegram"), ("telegram", "telegram"), ("instagram", "instagram"), ("facebook", "facebook"),
                         ("fb.", "facebook"), ("google", "google"), ("yandex", "yandex"), ("bing", "bing"), ("youtube", "youtube"),
                         ("linkedin", "linkedin"), ("tiktok", "tiktok"), ("hh.uz", "hh.uz"), ("olx", "olx")):
        if needle in host:
            return name, ref
    return host.removeprefix("www.")[:40], ref


SOURCE_LABELS = {"direct": "To'g'ridan-to'g'ri", "telegram": "Telegram", "telegram_app": "Telegram Mini App",
                 "instagram": "Instagram", "facebook": "Facebook", "google": "Google", "yandex": "Yandex"}


# ─── Yozish ───────────────────────────────────────────────────────────────────

def _ua_hash(ua):
    return hashlib.sha1((ua or "").encode("utf-8", "ignore")).hexdigest()[:16]


def _visitor_id(request):
    try:
        return uuid.UUID(request.COOKIES.get(COOKIE, ""))
    except ValueError:
        return None


class VisitTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefix = "/" + settings.ADMIN_URL

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if path.startswith(SKIP_PREFIXES) or path.startswith(self.admin_prefix):
            return response
        try:
            is_page = request.method in ("GET", "HEAD") and "text/html" in response.get("Content-Type", "")
            suspicious = bool(SCANNER_PATH_RE.search(path))
            if is_page or suspicious or response.status_code == 404:
                self._track(request, response, suspicious)
        except Exception:  # statistika hech qachon saytni buzmasin
            logger.warning("Visit tracking failed", exc_info=True)
        return response

    def _track(self, request, response, suspicious):
        from .models import PageView, Visitor

        now = timezone.now()
        ua = request.META.get("HTTP_USER_AGENT", "")[:300]
        ip = client_ip(request)
        path = request.get_full_path()[:300]
        visitor = None
        vid = _visitor_id(request)
        if vid:
            visitor = Visitor.objects.filter(pk=vid).first()
        if visitor is None:
            # Cookie saqlamaydigan botlar har so'rovda yangi yozuv yaratmasin
            visitor = Visitor.objects.filter(ip=ip, ua_hash=_ua_hash(ua), last_seen__gte=now - SAME_VISITOR_WINDOW).first()

        kind, bot_name = classify(ua, request.path if suspicious else "")
        user = request.user if getattr(request, "user", None) is not None and request.user.is_authenticated else None

        if visitor is None:
            device, os_name, browser = parse_device(ua)
            source, referrer = detect_source(request)
            if request.session.get("in_telegram") if hasattr(request, "session") else False:
                source = "telegram_app"
            visitor = Visitor.objects.create(
                kind=kind, bot_name=bot_name, ip=ip, ua_hash=_ua_hash(ua), user_agent=ua, device=device, os=os_name,
                browser=browser, source=source, referrer=referrer, utm_campaign=request.GET.get("utm_campaign", "")[:100],
                landing_path=path, last_path=path, pageviews=1, user=user, did_login=bool(user),
                did_builder=request.path.startswith("/cv/builder/"), first_seen=now, last_seen=now,
            )
        else:
            updates = {"last_path": path, "last_seen": now, "pageviews": F("pageviews") + 1}
            if kind == Visitor.KIND_SCANNER and visitor.kind not in (Visitor.KIND_SCANNER, Visitor.KIND_HUMAN):
                updates.update(kind=kind, bot_name="")
            if user and visitor.user_id != user.pk:
                updates.update(user=user, did_login=True)
            if request.path.startswith("/cv/builder/"):
                updates["did_builder"] = True
            if getattr(request, "session", None) is not None and request.session.get("in_telegram") and not visitor.in_telegram:
                updates["in_telegram"] = True
            Visitor.objects.filter(pk=visitor.pk).update(**updates)

        PageView.objects.create(visitor_id=visitor.pk, path=path, method=request.method[:8],
                                status=min(response.status_code, 999), created_at=now)
        if request.COOKIES.get(COOKIE) != str(visitor.pk) and kind == Visitor.KIND_UNKNOWN:
            response.set_cookie(COOKIE, str(visitor.pk), max_age=COOKIE_AGE, httponly=True,
                                secure=request.is_secure(), samesite=getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"))


def mark_step(request, step, user=None):
    """Voronka bosqichini belgilash: builder, generate, login, unlock, download."""
    from .models import Visitor

    vid = _visitor_id(request) if request is not None else None
    if not vid or step not in STEP_FIELDS:
        return
    updates = {STEP_FIELDS[step]: True}
    if user is not None:
        updates["user"] = user
    try:
        Visitor.objects.filter(pk=vid).update(**updates)
    except Exception:
        logger.warning("mark_step failed", exc_info=True)


@csrf_exempt
@require_POST
def human_ping(request):
    """Sahifada JavaScript ishlaganini bildiradi — real brauzer."""
    from .models import Visitor

    vid = _visitor_id(request)
    if vid:
        if request.POST.get("wd") == "1":
            verdict = {"kind": Visitor.KIND_BOT, "bot_name": "Avtomatlashtirilgan brauzer"}
        else:
            verdict = {"kind": Visitor.KIND_HUMAN}
        Visitor.objects.filter(pk=vid, kind=Visitor.KIND_UNKNOWN).update(**verdict)
        if request.POST.get("tg") == "1":
            Visitor.objects.filter(pk=vid).update(in_telegram=True, source="telegram_app")
    return HttpResponse(status=204)


# ─── Hisobot ──────────────────────────────────────────────────────────────────

FUNNEL = [
    ("all", "Saytga keldi"),
    ("did_builder", "Rezyume yaratishni ochdi"),
    ("did_generate", "Rezyume yaratdi"),
    ("did_login", "Telegram orqali kirdi"),
    ("did_unlock", "Rezyumeni ochdi (kredit/Pro)"),
    ("did_download", "PDF/Word yukladi"),
]


def prune_old(days_views=60, days_bots=30):
    """Eski ma'lumotlarni kuniga bir marta tozalaydi (baza shishib ketmasin)."""
    from .models import PageView, Visitor

    if not cache.add("visits_pruned", 1, 24 * 3600):
        return
    now = timezone.now()
    PageView.objects.filter(created_at__lt=now - timedelta(days=days_views)).delete()
    Visitor.objects.filter(kind__in=[Visitor.KIND_BOT, Visitor.KIND_SCANNER, Visitor.KIND_UNKNOWN],
                           last_seen__lt=now - timedelta(days=days_bots)).delete()


def visit_stats(days=7):
    from .models import PageView, Visitor

    now = timezone.localtime()
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    period = Visitor.objects.filter(first_seen__gte=start)

    kinds = dict(period.values_list("kind").annotate(n=Count("id")).values_list("kind", "n"))
    humans = period.filter(kind=Visitor.KIND_HUMAN)
    total_h = humans.count()

    funnel, prev = [], None
    for field, label in FUNNEL:
        n = total_h if field == "all" else humans.filter(**{field: True}).count()
        funnel.append({"label": label, "n": n, "pct": round(n * 100 / total_h) if total_h else 0,
                       "drop": (round((prev - n) * 100 / prev) if prev else 0)})
        prev = n

    # Qayerda to'xtadi: odamlarning oxirgi bosqichi
    stages = []
    # Har bir odam faqat bitta — eng uzoq yetgan bosqichiga tushadi
    nd = humans.filter(did_download=False)
    nu = nd.filter(did_unlock=False)
    nl = nu.filter(did_login=False)
    ng = nl.filter(did_generate=False)
    buckets = [
        ("viewed", "Faqat ko'rib ketdi", ng.filter(did_builder=False)),
        ("builder", "Yaratish sahifasida to'xtadi", ng.filter(did_builder=True)),
        ("generated", "Rezyume yaratdi, kirmadi", nl.filter(did_generate=True)),
        ("login", "Kirdi, to'lamadi", nu.filter(did_login=True)),
        ("unlock", "Ochdi, yuklamadi", nd.filter(did_unlock=True)),
        ("download", "PDF/Word yukladi ✅", humans.filter(did_download=True)),
    ]
    for key, label, qs in buckets:
        n = qs.count()
        stages.append({"key": key, "label": label, "n": n, "pct": round(n * 100 / total_h) if total_h else 0})

    exits = list(humans.filter(did_generate=False).values("last_path").annotate(n=Count("id")).order_by("-n")[:8])
    landings = list(humans.values("landing_path").annotate(n=Count("id")).order_by("-n")[:8])
    sources = [{"name": SOURCE_LABELS.get(r["source"], r["source"] or "—"), "n": r["n"]}
               for r in humans.values("source").annotate(n=Count("id")).order_by("-n")[:8]]
    devices = list(humans.values("device").annotate(n=Count("id")).order_by("-n"))
    bot_list = list(period.filter(kind=Visitor.KIND_BOT).values("bot_name").annotate(n=Count("id")).order_by("-n")[:10])
    scanner_ips = list(period.filter(kind=Visitor.KIND_SCANNER).values("ip").annotate(n=Count("id", distinct=True), hits=Count("views")).order_by("-hits")[:10])
    scanner_paths = list(PageView.objects.filter(created_at__gte=start, visitor__kind=Visitor.KIND_SCANNER)
                         .values("path").annotate(n=Count("id")).order_by("-n")[:10])

    day_rows = period.annotate(d=TruncDate("first_seen")).values("d", "kind").annotate(n=Count("id"))
    by_day = {}
    for r in day_rows:
        by_day.setdefault(r["d"], {})[r["kind"]] = r["n"]
    chart = []
    for i in range(days):
        d = (start + timedelta(days=i)).date()
        row = by_day.get(d, {})
        chart.append({"label": d.strftime("%d.%m"), "human": row.get("human", 0), "bot": row.get("bot", 0) + row.get("unknown", 0),
                      "scanner": row.get("scanner", 0)})
    peak = max([c["human"] + c["bot"] + c["scanner"] for c in chart] + [1])
    for c in chart:
        c["h_h"], c["h_b"], c["h_s"] = (round(c[k] * 100 / peak) for k in ("human", "bot", "scanner"))

    return {
        "start": start, "days": days,
        "total": sum(kinds.values()), "humans": kinds.get("human", 0), "bots": kinds.get("bot", 0),
        "scanners": kinds.get("scanner", 0), "unknown": kinds.get("unknown", 0),
        "landing_humans": humans.filter(landing_path="/").count(),
        "pageviews": PageView.objects.filter(created_at__gte=start).count(),
        "human_pageviews": PageView.objects.filter(created_at__gte=start, visitor__kind=Visitor.KIND_HUMAN).count(),
        "mobile_share": round(humans.filter(device="mobile").count() * 100 / total_h) if total_h else 0,
        "telegram_app": humans.filter(in_telegram=True).count(),
        "online": Visitor.objects.filter(kind=Visitor.KIND_HUMAN, last_seen__gte=timezone.now() - timedelta(minutes=5)).count(),
        "funnel": funnel, "stages": stages, "exits": exits, "landings": landings, "sources": sources,
        "devices": devices, "bot_list": bot_list, "scanner_ips": scanner_ips, "scanner_paths": scanner_paths, "chart": chart,
    }
