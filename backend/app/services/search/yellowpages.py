YELLOW_PAGES = {
    "US": "https://www.yellowpages.com/search?q={query}",
    "UK": "https://www.yell.com/s/{query}/",
    "DE": "https://www.gelbeseiten.de/suche/{query}",
    "FR": "https://www.pagesjaunes.fr/pros/chercherlespros?quoiqui={query}",
    "AU": "https://www.yellowpages.com.au/search/listings?clue={query}",
    "IN": "https://www.justdial.com/{query}",
    "CN": "https://www.51sole.com/search.htm?kw={query}",
    "JP": "https://itp.ne.jp/search/result/?skey={query}",
    "BR": "https://www.telelistas.net/busca/{query}",
    "MX": "https://www.seccionamarilla.com.mx/resultados/1/{query}",
}


class YellowPagesService:
    def build_url(self, country_code: str, query: str) -> str | None:
        template = YELLOW_PAGES.get(country_code.upper())
        return template.format(query=query) if template else None
