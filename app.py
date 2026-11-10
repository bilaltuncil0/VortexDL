"""VortexDL application entry point."""
from vortexdl.ui.main_window import create_app


def main():
    app = create_app()
    app.mainloop()


if __name__ == "__main__":
    main()
