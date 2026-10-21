"""Development and PyInstaller entry point."""

if __name__ == "__main__":
    import sys
    if '--ocr-worker' in sys.argv:
        from mini_whiteboard.ocr_worker import worker_main
        raise SystemExit(worker_main(sys.argv[sys.argv.index('--ocr-worker') + 1:]))
    from mini_whiteboard.app import main
    raise SystemExit(main())
