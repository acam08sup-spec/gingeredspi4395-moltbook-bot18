from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .safety import clean_untrusted_text


PLATFORM_TERMS = {
    "moltbook",
    "submolt",
    "submolts",
    "feed",
    "agent",
    "agents",
    "comment",
    "comments",
    "post",
    "posts",
    "platform",
    "conversation",
    "conversations",
    "timeline",
    "community",
    "communities",
    "etiquette",
}


@dataclass(frozen=True)
class MoltbookPostContext:
    """Normalized context Tom uses before deciding whether to comment.

    Moltbook responses may expose fields with slightly different names depending
    on the endpoint. This object gives the writer and heartbeat one stable shape:
    post identity, room/submolt, author, tags, visible comments and whether the
    post appears to be Tom's own post.
    """

    post_id: str
    title: str = ""
    content: str = ""
    submolt: str = ""
    author: str = ""
    tags: tuple[str, ...] = ()
    comments: tuple[str, ...] = ()
    is_own_post: bool = False
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def combined_text(self) -> str:
        pieces = [self.title, self.content, self.submolt, self.author, *self.tags, *self.comments]
        return "\n".join(piece for piece in pieces if piece)

    @property
    def lower_text(self) -> str:
        return self.combined_text.lower()


class MoltbookContextReader:
    """Reads raw Moltbook posts into safe, normalized post contexts."""

    def __init__(self, *, bot_name: str):
        self.bot_name = bot_name.strip().lower()

    def read_post(self, post: Mapping[str, Any]) -> MoltbookPostContext:
        post_id = clean_untrusted_text(str(self._first(post, "id", "post_id", "postId", "uuid") or ""), 140)
        title = clean_untrusted_text(str(self._first(post, "title", "headline", "name") or ""), 220)
        content = clean_untrusted_text(str(self._first(post, "content", "body", "text", "description") or ""), 1200)
        submolt = clean_untrusted_text(self._read_submolt(post), 100)
        author = clean_untrusted_text(self._read_author(post), 100)
        tags = tuple(clean_untrusted_text(tag, 60) for tag in self._read_tags(post) if tag)
        comments = tuple(clean_untrusted_text(comment, 350) for comment in self._read_comments(post) if comment)
        is_own_post = self._read_is_own_post(post, author=author)

        return MoltbookPostContext(
            post_id=post_id,
            title=title,
            content=content,
            submolt=submolt,
            author=author,
            tags=tags,
            comments=comments,
            is_own_post=is_own_post,
            raw=post,
        )

    def read_posts(self, posts: Iterable[Mapping[str, Any]]) -> list[MoltbookPostContext]:
        return [self.read_post(post) for post in posts]

    @staticmethod
    def _first(post: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            value = post.get(key)
            if value not in (None, ""):
                return value
        return None

    def _read_submolt(self, post: Mapping[str, Any]) -> str:
        value = self._first(post, "submolt", "community", "room", "channel")
        if isinstance(value, Mapping):
            return str(self._first(value, "name", "slug", "title", "id") or "")
        return str(value or "")

    def _read_author(self, post: Mapping[str, Any]) -> str:
        for key in ("author", "user", "agent", "creator", "owner"):
            value = post.get(key)
            if isinstance(value, Mapping):
                nested = self._first(value, "name", "username", "handle", "agent_name", "display_name", "id")
                if nested:
                    return str(nested)
            elif value:
                return str(value)

        return str(self._first(post, "author_name", "username", "handle", "agent_name", "created_by") or "")

    def _read_tags(self, post: Mapping[str, Any]) -> list[str]:
        value = self._first(post, "tags", "topics", "labels")
        if isinstance(value, str):
            return [part.strip() for part in value.replace("#", " ").replace(",", " ").split() if part.strip()]
        if not isinstance(value, list):
            return []

        tags: list[str] = []
        for item in value:
            if isinstance(item, Mapping):
                text = self._first(item, "name", "slug", "label", "title")
                if text:
                    tags.append(str(text))
            elif item:
                tags.append(str(item))
        return tags

    def _read_comments(self, post: Mapping[str, Any]) -> list[str]:
        value = self._first(post, "comments", "replies")
        if not isinstance(value, list):
            return []

        comments: list[str] = []
        for item in value[:10]:
            if isinstance(item, Mapping):
                text = self._first(item, "content", "body", "text", "comment")
                if text:
                    comments.append(str(text))
            elif item:
                comments.append(str(item))
        return comments

    def _read_is_own_post(self, post: Mapping[str, Any], *, author: str) -> bool:
        explicit = self._first(post, "is_own_post", "isOwnPost", "own_post", "owned_by_me")
        if isinstance(explicit, bool):
            return explicit
        if isinstance(explicit, str) and explicit.strip().lower() in {"1", "true", "yes", "y"}:
            return True

        if self.bot_name and author.strip().lower() == self.bot_name:
            return True

        return False


def best_comment_target(posts: Iterable[Mapping[str, Any] | MoltbookPostContext], *, bot_name: str) -> MoltbookPostContext | None:
    """Choose the best post for Tom to comment on.

    The selector avoids Tom's own posts and favors posts about Moltbook's social
    architecture: submolts, feeds, agents, comments and the platform itself.
    """

    reader = MoltbookContextReader(bot_name=bot_name)
    contexts: list[MoltbookPostContext] = []
    for post in posts:
        if isinstance(post, MoltbookPostContext):
            context = post
        else:
            context = reader.read_post(post)
        contexts.append(context)

    scored: list[tuple[int, int, MoltbookPostContext]] = []
    for index, context in enumerate(contexts):
        if not context.post_id or context.is_own_post:
            continue

        score = _platform_relevance_score(context)
        if score <= 0:
            continue
        scored.append((score, -index, context))

    if not scored:
        return None

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return scored[0][2]


def _platform_relevance_score(context: MoltbookPostContext) -> int:
    score = 0
    title_tokens = _tokens(context.title)
    content_tokens = _tokens(context.content)
    submolt_tokens = _tokens(context.submolt)
    tag_tokens = set().union(*(_tokens(tag) for tag in context.tags)) if context.tags else set()
    comment_tokens = set().union(*(_tokens(comment) for comment in context.comments)) if context.comments else set()

    score += 5 * len(title_tokens & PLATFORM_TERMS)
    score += 3 * len(submolt_tokens & PLATFORM_TERMS)
    score += 3 * len(tag_tokens & PLATFORM_TERMS)
    score += 2 * len(content_tokens & PLATFORM_TERMS)
    score += 1 * len(comment_tokens & PLATFORM_TERMS)

    if "moltbook" in context.lower_text:
        score += 5
    if "submolt" in context.lower_text or "submolts" in context.lower_text:
        score += 3
    if "agent" in context.lower_text or "agents" in context.lower_text:
        score += 2

    return score


def _tokens(text: str) -> set[str]:
    return {token.strip(".,!?;:()[]{}\"'“”‘’#/\\").lower() for token in text.split() if token.strip()}
