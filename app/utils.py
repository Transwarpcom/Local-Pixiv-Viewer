from urllib.parse import quote
import config

def register_filters(app):
    @app.template_filter('url_quote')
    def url_quote_filter(s):
        return quote(s, safe='/') if s else ""

    @app.template_filter('thumbnail')
    def thumbnail_filter(s):
        if not s: return ""
        if config.THUMBS_DIR:
            return f"{config.THUMBS_URL_PREFIX}{quote(s, safe='/')}.jpg"
        return f"{config.THUMBS_URL_PREFIX}{quote(s, safe='/')}"

    @app.template_filter('is_r18')
    def is_r18_filter(tags):
        return tags and ('R-18' in tags or 'R-18G' in tags)
