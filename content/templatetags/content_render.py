import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from content.models import LessonResource


register = template.Library()
HTML_TAG_RE = re.compile(r'</?[a-zA-Z][^>]*>')
CONTENT_ID_RE = re.compile(r'data-content-id=(["\'])(\d+)\1')
TAG_WITH_CONTENT_ID_RE = re.compile(r'<(?P<tag>[a-zA-Z][^>]*)data-content-id=(?P<quote>["\'])(?P<id>\d+)(?P=quote)(?P<rest>[^>]*)>')


def _variant_for_content(item):
    if item.content_type == 'image':
        return 'image'
    if item.content_type == 'audio':
        return 'audio'
    if item.content_type == 'youtube':
        return 'youtube'
    if item.content_type == 'video':
        return 'youtube' if item.get_youtube_embed_url() else 'video'
    return 'link'


def _enrich_highlight_links(text):
    content_ids = {
        int(match.group(2))
        for match in CONTENT_ID_RE.finditer(text)
    }
    if not content_ids:
        return text

    contents = {
        item.id: item
        for item in LessonResource.objects.filter(id__in=content_ids)
    }

    def replace_tag(match):
        raw_tag = match.group(0)
        content_id = int(match.group('id'))
        item = contents.get(content_id)
        if not item:
            return raw_tag

        variant = _variant_for_content(item)
        class_match = re.search(r'class=(["\'])(.*?)\1', raw_tag)

        if class_match:
            classes = class_match.group(2).split()
            normalized = [
                css_class for css_class in classes
                if not css_class.startswith('highlight-link--')
            ]
            if 'highlight-link' not in normalized:
                normalized.append('highlight-link')
            normalized.append(f'highlight-link--{variant}')
            class_attr = f'class={class_match.group(1)}{" ".join(normalized)}{class_match.group(1)}'
            return raw_tag[:class_match.start()] + class_attr + raw_tag[class_match.end():]

        return raw_tag[:-1] + f' class="highlight-link highlight-link--{variant}">'

    return TAG_WITH_CONTENT_ID_RE.sub(replace_tag, text)


@register.filter
def render_stored_content(value):
    if value is None:
        return ''

    text = str(value)
    if not text:
        return ''

    if HTML_TAG_RE.search(text):
        return mark_safe(_enrich_highlight_links(text))

    return mark_safe(escape(text).replace('\n', '<br>'))
