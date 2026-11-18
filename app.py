import sys


def main() -> None:
    """Start the UI server or dispatch an internal video-rendering worker."""
    if len(sys.argv) > 1 and sys.argv[1] == "--video-cli":
        del sys.argv[1]
        from services.video import main as video_main

        video_main()
        return

    from web.server import main as server_main

    server_main()


if __name__ == "__main__":
    main()
