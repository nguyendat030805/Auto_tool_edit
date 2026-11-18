#!/usr/bin/env python3
"""Backward-compatible command-line entry point for post-template rendering."""

from services.post import MAX_COMMENTS, render_post
from services.post.cli import main

__all__ = ["MAX_COMMENTS", "render_post"]


if __name__ == "__main__":
    main()
