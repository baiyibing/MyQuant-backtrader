#!/usr/bin/env python3
"""Push the current branch and open a GitHub PR via the Git Data / Pulls API.

Use this when ``git push`` to ``github.com:443`` is blocked but
``api.github.com`` works (``gh auth``). Remote commit SHAs will differ
from local SHAs; the named feature branch ref is replaced to match
``base..HEAD``. Refuses ``master`` / ``main``.

Usage::

  python scripts/ops/push_github_pr_via_api.py
  python scripts/ops/push_github_pr_via_api.py --title "..." --body-file path.md
  python scripts/ops/push_github_pr_via_api.py --no-pr
  python scripts/ops/push_github_pr_via_api.py --dry-run
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

API = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = "MyQuant-backtrader-push-github-pr-via-api"
PROTECTED_BRANCHES = frozenset({"master", "main"})
GITHUB_REPO_RE = re.compile(
    r"""
    (?:
        https?://github\.com/ |
        git@github\.com: |
        ssh://(?:git@)?github\.com/
    )
    (?P<owner>[^/]+)/(?P<name>[^/]+?)
    (?:\.git)?/?$
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class TreeEdit:
    path: str
    mode: str | None
    content: bytes | None


def parse_github_repo(url: str) -> RepoRef:
    text = (url or "").strip()
    match = GITHUB_REPO_RE.match(text)
    if match is None:
        raise ValueError(f"not a github.com remote: {url!r}")
    return RepoRef(match.group("owner"), match.group("name"))


def is_protected_branch(name: str) -> bool:
    return name.strip() in PROTECTED_BRANCHES


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def git_ok(*args: str) -> str | None:
    try:
        return git_output(*args)
    except subprocess.CalledProcessError:
        return None


def token() -> str:
    try:
        value = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("gh auth token failed; run `gh auth login` first") from exc
    if not value:
        raise SystemExit("gh auth token returned empty")
    return value


def api(
    tok: str,
    method: str,
    path: str,
    payload: Any | None = None,
    *,
    not_found_ok: bool = False,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {tok}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read()
            return json.loads(body.decode("utf-8")) if body else {}
    except urllib.error.HTTPError as exc:
        if not_found_ok and exc.code == 404:
            return None
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub API {method} {path} failed: {exc.code} {detail}") from exc


def resolve_repo() -> RepoRef:
    for remote in ("github", "origin"):
        url = git_ok("remote", "get-url", remote)
        if not url:
            continue
        try:
            return parse_github_repo(url)
        except ValueError:
            continue
    try:
        slug = subprocess.check_output(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("cannot resolve github.com repo from remotes or `gh repo view`") from exc
    owner, _, name = slug.partition("/")
    if not owner or not name:
        raise SystemExit(f"gh repo view returned invalid slug: {slug!r}")
    return RepoRef(owner, name)


def resolve_local_base(name: str) -> str:
    for ref in (
        f"refs/remotes/github/{name}",
        f"refs/remotes/origin/{name}",
        f"refs/heads/{name}",
        name,
    ):
        sha = git_ok("rev-parse", "--verify", ref)
        if sha:
            return sha
    raise SystemExit(f"cannot resolve local base {name!r}")


def commit_range(base_sha: str, head: str) -> list[str]:
    shas = git_output("rev-list", "--reverse", f"{base_sha}..{head}").splitlines()
    for sha in shas:
        parts = git_output("rev-list", "--parents", "-n", "1", sha).split()
        if len(parts) > 2:
            raise SystemExit(f"merge commit {sha} is not supported")
    return shas


def parse_name_status(payload: str) -> list[tuple[str, str]]:
    edits: list[tuple[str, str]] = []
    for raw in payload.splitlines():
        if not raw:
            continue
        status, path = raw.split("\t", 1)
        if status.startswith("R") or status.startswith("C"):
            _old, new = path.split("\t", 1)
            edits.append(("D", _old))
            edits.append(("A", new))
            continue
        edits.append((status[0], path))
    return edits


def tree_edits(parent: str, commit: str) -> list[TreeEdit]:
    payload = git_output("diff-tree", "--no-commit-id", "-r", "--name-status", parent, commit)
    out: list[TreeEdit] = []
    for status, path in parse_name_status(payload):
        if status == "D":
            out.append(TreeEdit(path, None, None))
            continue
        meta = git_output("ls-tree", commit, "--", path)
        if not meta:
            raise SystemExit(f"ls-tree missed {path} in {commit}")
        mode_type_sha, listed = meta.split("\t", 1)
        mode, _typ, _sha = mode_type_sha.split()
        content = git_bytes("show", f"{commit}:{path}")
        out.append(TreeEdit(listed, mode, content))
    return out


def commit_meta(sha: str) -> dict[str, str]:
    fmt = "%B%x1f%an%x1f%ae%x1f%aI%x1f%cn%x1f%ce%x1f%cI"
    message, an, ae, ad, cn, ce, cd = git_output("show", "-s", f"--format={fmt}", sha).split(
        "\x1f"
    )
    return {
        "message": message,
        "author_name": an,
        "author_email": ae,
        "author_date": ad,
        "committer_name": cn,
        "committer_email": ce,
        "committer_date": cd,
    }


def publish_range(
    tok: str,
    repo: RepoRef,
    *,
    base: str,
    branch: str,
    head: str,
    dry_run: bool,
) -> str | None:
    if is_protected_branch(branch):
        raise SystemExit(f"refusing to publish protected branch {branch!r} via API")
    local_base = resolve_local_base(base)
    shas = commit_range(local_base, head)
    if not shas:
        print(f"nothing to publish: {base}..{head} is empty")
        return None
    print(f"repo={repo.slug} branch={branch} base={base} commits={len(shas)}")
    parents = [local_base] + shas[:-1]
    planned = [(sha, tree_edits(parent, sha)) for parent, sha in zip(parents, shas)]
    for sha, edits in planned:
        print(f"  {sha[:12]} {git_output('show', '-s', '--format=%s', sha)} ({len(edits)} paths)")
    if dry_run:
        return None

    remote_base = api(tok, "GET", f"/repos/{repo.slug}/git/ref/heads/{base}")
    parent_sha = remote_base["object"]["sha"]
    parent_commit = api(tok, "GET", f"/repos/{repo.slug}/git/commits/{parent_sha}")
    parent_tree = parent_commit["tree"]["sha"]
    tip = parent_sha
    for sha, edits in planned:
        items = []
        for edit in edits:
            if edit.mode is None or edit.content is None:
                items.append({"path": edit.path, "mode": "100644", "type": "blob", "sha": None})
                continue
            blob = api(
                tok,
                "POST",
                f"/repos/{repo.slug}/git/blobs",
                {
                    "content": base64.b64encode(edit.content).decode("ascii"),
                    "encoding": "base64",
                },
            )
            items.append(
                {"path": edit.path, "mode": edit.mode, "type": "blob", "sha": blob["sha"]}
            )
            print(f"blob {edit.path} sha={blob['sha']} bytes={len(edit.content)}")
        tree = api(
            tok,
            "POST",
            f"/repos/{repo.slug}/git/trees",
            {"base_tree": parent_tree, "tree": items},
        )
        meta = commit_meta(sha)
        created = api(
            tok,
            "POST",
            f"/repos/{repo.slug}/git/commits",
            {
                "message": meta["message"],
                "tree": tree["sha"],
                "parents": [parent_sha],
                "author": {
                    "name": meta["author_name"],
                    "email": meta["author_email"],
                    "date": meta["author_date"],
                },
                "committer": {
                    "name": meta["committer_name"],
                    "email": meta["committer_email"],
                    "date": meta["committer_date"],
                },
            },
        )
        print(f"created commit {created['sha']} from {sha}")
        parent_sha = created["sha"]
        parent_tree = tree["sha"]
        tip = created["sha"]

    ref_path = f"/repos/{repo.slug}/git/ref/heads/{branch}"
    existing = api(tok, "GET", ref_path, not_found_ok=True)
    if existing is None:
        api(
            tok,
            "POST",
            f"/repos/{repo.slug}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": tip},
        )
        print(f"created refs/heads/{branch} -> {tip}")
    else:
        api(tok, "PATCH", ref_path, {"sha": tip, "force": True})
        print(f"updated refs/heads/{branch} -> {tip}")
    return tip


def find_open_pr(tok: str, repo: RepoRef, branch: str) -> dict[str, Any] | None:
    pulls = api(
        tok,
        "GET",
        f"/repos/{repo.slug}/pulls?head={repo.owner}:{branch}&state=open",
    )
    return pulls[0] if pulls else None


def ensure_pr(
    tok: str,
    repo: RepoRef,
    *,
    branch: str,
    base: str,
    title: str,
    body: str,
    dry_run: bool,
) -> str:
    existing = None if dry_run else find_open_pr(tok, repo, branch)
    if existing:
        url = existing["html_url"]
        print(f"existing PR {url}")
        return url
    if dry_run:
        print(f"dry-run PR {repo.slug} {branch} -> {base}: {title}")
        return ""
    created = api(
        tok,
        "POST",
        f"/repos/{repo.slug}/pulls",
        {"title": title, "head": branch, "base": base, "body": body},
    )
    url = created["html_url"]
    print(f"opened PR {url}")
    return url


def default_title_body(head: str, base_sha: str) -> tuple[str, str]:
    shas = commit_range(base_sha, head)
    source = shas[0] if shas else head
    message = git_output("show", "-s", "--format=%B", source)
    title, _, rest = message.partition("\n")
    return title.strip(), rest.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="master", help="PR / replay base branch")
    parser.add_argument("--branch", help="feature branch to publish (default: current)")
    parser.add_argument("--head", default="HEAD", help="local rev to publish")
    parser.add_argument("--title", help="PR title (default: first published commit subject)")
    parser.add_argument("--body", default="", help="PR body text")
    parser.add_argument("--body-file", help="read PR body from a UTF-8 file")
    parser.add_argument("--no-pr", action="store_true", help="publish the branch only")
    parser.add_argument("--dry-run", action="store_true", help="print the plan; no writes")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    branch = args.branch or git_output("branch", "--show-current")
    if not branch:
        raise SystemExit("detached HEAD: pass --branch")
    if args.body and args.body_file:
        raise SystemExit("use only one of --body / --body-file")
    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    repo = resolve_repo()
    local_base = resolve_local_base(args.base)
    title = args.title
    if not title:
        title, default_body = default_title_body(args.head, local_base)
        if not body:
            body = default_body
    tok = "" if args.dry_run else token()
    publish_range(
        tok,
        repo,
        base=args.base,
        branch=branch,
        head=args.head,
        dry_run=args.dry_run,
    )
    if not args.no_pr:
        ensure_pr(
            tok,
            repo,
            branch=branch,
            base=args.base,
            title=title,
            body=body,
            dry_run=args.dry_run,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
