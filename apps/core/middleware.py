"""Telegram Mini App uchun ramka (iframe) ruxsati."""

# web.telegram.org Mini App'ni iframe ichida ochadi. X-Frame-Options: DENY buni butunlay taqiqlaydi,
# shuning uchun uning o'rniga CSP frame-ancestors bilan faqat o'zimiz va Telegram'ga ruxsat beramiz.
FRAME_ANCESTORS = "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org"


class TelegramFrameMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if "X-Frame-Options" in response and response["X-Frame-Options"].upper() == "DENY":
            del response["X-Frame-Options"]
            existing = response.get("Content-Security-Policy", "")
            if "frame-ancestors" not in existing:
                response["Content-Security-Policy"] = f"{existing}; {FRAME_ANCESTORS}".strip("; ")
        return response
