"""CLI tooling for siwe-django.

The wizard scaffolds a Django project to use ``siwe-django``: it patches
``settings.py`` and the root ``urls.py`` via libcst, drops a ready-to-use
Django template, and runs ``manage.py migrate`` so adopters can sign in with
Ethereum within a minute of ``pip install siwe-django[cli]``.

The CLI is opt-in (lives behind the ``cli`` extra) so the runtime package
stays free of Typer / Rich / libcst dependencies.
"""
