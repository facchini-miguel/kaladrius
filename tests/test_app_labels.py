"""The apps' labels in the database follow the running code's, in either direction (decision 194):
`migrate` renames them first, so the versions before and after the English labels, a restored
backup and the demo's base all work on the same database."""

from io import StringIO

import pytest
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command, get_commands
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.core.labels import LABELS, label_pairs, sync_labels
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db

CODE = Patient._meta.app_label  # the label the code uses for the patients' app
OTHER = next(old for old, new in label_pairs() if new == CODE)  # its other spelling


def relabel_database_to_the_other_spelling():
    with connection.cursor() as cursor:
        for old, new in label_pairs():
            cursor.execute("UPDATE django_migrations SET app = %s WHERE app = %s", [old, new])
            cursor.execute(
                "UPDATE django_content_type SET app_label = %s WHERE app_label = %s", [old, new]
            )
    ContentType.objects.clear_cache()


def pending_migrations():
    executor = MigrationExecutor(connection)
    return executor.migration_plan(executor.loader.graph.leaf_nodes())


def test_every_app_with_an_old_label_is_in_the_map():
    assert len(list(label_pairs())) == len(LABELS) == 18
    assert {OTHER, CODE} == {"pacientes", "patients"}


def test_migrate_is_the_projects():
    assert get_commands()["migrate"] == "apps.core"


def test_a_database_with_the_other_labels_comes_back():
    patient_type = ContentType.objects.get_for_model(Patient)
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT app FROM django_migrations")
        with_migrations = {app for (app,) in cursor.fetchall()} & set(dict(label_pairs()).values())
    relabel_database_to_the_other_spelling()
    assert pending_migrations()  # Django would try to create every table again

    changed = sync_labels()

    # The 12 apps with tables; help, team, legacy, monitoring, whats_new and dentistry have none.
    assert {new for _old, new, migrations, _ in changed if migrations} == with_migrations
    assert len(with_migrations) == 12
    assert not pending_migrations()
    ContentType.objects.clear_cache()
    assert ContentType.objects.get_for_model(Patient).pk == patient_type.pk  # same row, same id
    assert not ContentType.objects.filter(app_label__in=[old for old, _ in label_pairs()]).exists()
    assert sync_labels() == []  # nothing left to do


def test_migrate_renames_before_migrating():
    relabel_database_to_the_other_spelling()
    output = StringIO()
    call_command("migrate", verbosity=1, stdout=output)
    assert f"App label {OTHER} -> {CODE}" in output.getvalue()
    assert "No migrations to apply" in output.getvalue()
    assert not pending_migrations()


def test_a_model_in_both_spellings_is_merged(django_user_model):
    """A content type created under the other label while that one was in the database: the code's
    row stays, and permissions, groups and the admin log move to it."""
    code_type = ContentType.objects.get_for_model(Patient)
    view = Permission.objects.get(content_type=code_type, codename="view_patient")
    other_type = ContentType.objects.create(app_label=OTHER, model="patient")
    other_view = Permission.objects.create(
        content_type=other_type, codename="view_patient", name="Can view patient"
    )
    extra = Permission.objects.create(content_type=other_type, codename="export_patient", name="x")
    both = Group.objects.create(name="has both")
    both.permissions.add(view, other_view)
    only_other = Group.objects.create(name="has the other")
    only_other.permissions.add(other_view, extra)
    user = django_user_model.objects.create_user("auditor")
    user.user_permissions.add(other_view)
    entry = LogEntry.objects.create(
        user=user, content_type=other_type, object_id="1", object_repr="x", action_flag=ADDITION
    )

    sync_labels()

    assert not ContentType.objects.filter(pk=other_type.pk).exists()
    assert list(both.permissions.all()) == [view]
    assert set(only_other.permissions.all()) == {view, extra}
    assert list(user.user_permissions.all()) == [view]
    extra.refresh_from_db()
    entry.refresh_from_db()
    assert extra.content_type == code_type and entry.content_type == code_type
