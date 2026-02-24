#!/usr/bin/env python
import os
import sys


def main() -> None:
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        settings_module = "config.settings.local"
        if len(sys.argv) > 1 and sys.argv[1] == "test":
            settings_module = "config.settings.test"
        os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Ensure it is installed and available on your PYTHONPATH."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
